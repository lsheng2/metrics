from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import time

from bug_metrics.app.api.provider_connections import ConnectionError
from project_management.app.api.capture_archive import RawPageInput
from provider_sync.app.api.access_contracts import (
    AccessContext, AccessError, RequestUsage, validate_context, validate_request_context,
)
from provider_sync.app.spi.capture import ArchivePageSink, CapturedJson, HeldRawPage, RawResponse


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def fingerprint(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def strict_object(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def reject(_):
        raise ValueError

    def finite_number(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError
        return value

    try:
        value = json.loads(body.decode('utf-8'), object_pairs_hook=pairs, parse_constant=reject,
                           parse_float=finite_number)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise AccessError('PROVIDER_RESPONSE_INVALID') from None


class ProviderReadSession:
    def __init__(self, context, reader, *, timeout_seconds, authorize=None, clock=None, monotonic=None):
        if isinstance(context, AccessContext):
            validate_context(context)
        else:
            validate_request_context(context)
        self.context = context
        self.reader = reader
        self.timeout_seconds = timeout_seconds
        self.authorize = authorize
        self.clock = clock or (lambda: datetime.now(UTC))
        self.monotonic = monotonic or time.monotonic
        self.monotonic_deadline = self.monotonic() + (context.deadline_at - self.clock()).total_seconds()
        self._requests = 0
        self._bytes = 0
        self._closed = False
        self._page_keys = set()

    @property
    def usage(self):
        return RequestUsage(self._requests, self._bytes)

    def page_id(self, page_key):
        return None

    def remaining_seconds(self):
        remaining = min(self.monotonic_deadline - self.monotonic(),
                        (self.context.deadline_at - self.clock()).total_seconds())
        if remaining <= 0:
            raise AccessError('CAPTURE_DEADLINE_EXPIRED')
        return remaining

    def get_json(self, relative_path, params, *, item=None, page_key):
        if self._closed:
            raise AccessError('CAPTURE_CLOSED')
        remaining = self.remaining_seconds()
        if self.authorize:
            self.authorize()
        limits = self.context.limits
        if self._requests >= limits.max_requests:
            raise AccessError('CAPTURE_REQUEST_LIMIT')
        room = limits.max_download_bytes - self._bytes
        if room <= 0:
            raise AccessError('CAPTURE_DOWNLOAD_LIMIT')
        if not isinstance(page_key, str) or not page_key or page_key in self._page_keys:
            raise AccessError('CAPTURE_PAGE_CONFLICT')
        request_fingerprint = fingerprint({'path': relative_path, 'params': params})
        self._page_keys.add(page_key)
        self._requests += 1
        try:
            response = self.reader.read(relative_path, params, timeout=min(self.timeout_seconds, remaining),
                                        max_bytes=min(room, limits.max_response_bytes))
        except ConnectionError as error:
            raise AccessError(error.code) from None
        if not isinstance(response, RawResponse) or type(response.body) is not bytes:
            raise AccessError('PROVIDER_RESPONSE_INVALID')
        maximum = min(room, limits.max_response_bytes)
        body = response.body[:maximum]
        self._bytes += len(body)
        partial = response.partial or len(response.body) > maximum
        error = response.error_code or self._http_error(response.status_code)
        if partial and error is None:
            error = 'CAPTURE_RESPONSE_LIMIT'
        page = HeldRawPage(page_key, item, response.content_type, body, request_fingerprint, partial, error)
        self._retain_response(page)
        if error is not None:
            raise AccessError(
                error,
                provider_status=response.status_code,
                retry_after_seconds=_retry_after_seconds(response.retry_after, self.clock(), error),
            )
        self.remaining_seconds()
        value = strict_object(body)
        return CapturedJson(value, self.page_id(page_key), page_key, request_fingerprint)

    def close(self):
        if not self._closed:
            self._closed = True
            self.reader.close()

    def _retain_response(self, page):
        return None

    def _http_error(self, status):
        if type(status) is not int or status < 100 or status > 599:
            return 'PROVIDER_RESPONSE_INVALID'
        if status == 401:
            return 'PROVIDER_AUTH_FAILED'
        if status == 403:
            return 'PROVIDER_PERMISSION_DENIED'
        if status == 429:
            return 'PROVIDER_RATE_LIMITED'
        if 300 <= status < 400:
            return 'PROVIDER_REDIRECT_UNSUPPORTED'
        if not 200 <= status < 300:
            return 'PROVIDER_HTTP_ERROR'
        return None


class CaptureSession(ProviderReadSession):
    def __init__(self, context, reader, *, timeout_seconds, authorize=None, clock=None, monotonic=None):
        validate_context(context)
        super().__init__(context, reader, timeout_seconds=timeout_seconds, authorize=authorize,
                         clock=clock, monotonic=monotonic)
        self._sink = None
        self._held = []
        self._page_ids = {}

    @property
    def page_ids(self):
        return tuple(self._page_ids.values())

    def page_id(self, page_key):
        return self._page_ids.get(page_key)

    def attach_archive_sink(self, sink):
        if self._closed:
            raise AccessError('CAPTURE_CLOSED')
        if self._sink is not None or not isinstance(sink, ArchivePageSink):
            raise AccessError('CAPTURE_SINK_CONFLICT')
        if any(getattr(sink.intent, name) != getattr(self.context, name)
               for name in ('project_id', 'stage_id', 'capture_id', 'request_id', 'deadline_at')):
            raise AccessError('CAPTURE_SINK_CONFLICT')
        self._sink = sink
        for page in self._held:
            self._archive(page)
        self._held.clear()

    def close(self):
        self._held.clear()
        super().close()

    def _retain_response(self, page):
        if self._sink is None:
            if sum(len(held.body) for held in self._held) + len(page.body) > self.context.limits.max_response_bytes:
                raise AccessError('CAPTURE_RESPONSE_LIMIT')
            self._held.append(page)
        else:
            self._archive(page)

    def _archive(self, held):
        page = RawPageInput(held.page_key, held.item, held.content_type, held.body,
                            held.request_fingerprint, held.partial, held.error_code)
        ref = self._sink.append_page(page)
        self._page_ids[held.page_key] = ref.page_id


def _retry_after_seconds(value, now, error):
    if value is None:
        return 60 if error == 'PROVIDER_RATE_LIMITED' else None
    if type(value) is not str:
        return 60
    text = value.strip()
    if text.isdecimal():
        return min(86400, max(0, int(text)))
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return 60
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return 60
    seconds = math.ceil((parsed.astimezone(UTC) - now.astimezone(UTC)).total_seconds())
    return min(86400, max(0, seconds))
