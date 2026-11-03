import re
import time

import requests
from urllib3.exceptions import HTTPError

from provider_sync.app.api.access_contracts import AccessError
from provider_sync.app.spi.capture import RawResponse


JIRA_READ_PATH = re.compile(
    r'/rest/api/2/(?:myself|search|filter/[1-9][0-9]*|'
    r'issue/(?:[1-9][0-9]*(?:/comment)?|[A-Za-z][A-Za-z0-9_]*-[1-9][0-9]*))'
)


class BoundCaptureReader:
    def __init__(self, *, info, session):
        self.info = info
        self.session = session

    def read(self, relative_path, params, *, timeout, max_bytes):
        if (self.info.endpoint.provider_id != 'jira' or not isinstance(relative_path, str)
                or JIRA_READ_PATH.fullmatch(relative_path) is None):
            raise AccessError('PROVIDER_ENDPOINT_INVALID')
        if type(max_bytes) is not int or max_bytes <= 0 or timeout <= 0:
            raise AccessError('INVALID_ARGUMENTS')
        deadline = time.monotonic() + timeout
        response = None
        body = bytearray()
        status = 0
        content_type = 'application/octet-stream'
        partial, error = False, None
        try:
            response = self.session.get(self.info.endpoint.base_url + relative_path, params=params,
                                        stream=True, timeout=timeout, allow_redirects=False)
            status = response.status_code
            value = response.headers.get('Content-Type', content_type)
            if isinstance(value, str) and 0 < len(value) <= 256 and not any(ord(c) < 32 for c in value):
                content_type = value
            length = self._unencoded_length(response)
            while True:
                if time.monotonic() >= deadline:
                    partial, error = True, 'CAPTURE_DEADLINE_EXPIRED'
                    break
                remaining = max_bytes - len(body)
                if remaining == 0:
                    if length == len(body):
                        break
                    partial, error = True, 'CAPTURE_RESPONSE_LIMIT'
                    break
                chunk = response.raw.read(min(65536, remaining), decode_content=True)
                if not chunk:
                    if length is not None and length != len(body):
                        partial, error = True, 'PROVIDER_NETWORK_ERROR'
                    break
                body.extend(chunk)
        except (requests.RequestException, HTTPError, OSError):
            partial, error = bool(body), 'PROVIDER_NETWORK_ERROR'
        finally:
            if response is not None:
                response.close()
        return RawResponse(status, content_type, bytes(body), partial, error)

    def close(self):
        self.session.close()

    def _unencoded_length(self, response):
        value = response.headers.get('Content-Length', '')
        if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
            return None
        return int(value) if isinstance(value, str) and re.fullmatch('[0-9]{1,16}', value) else None
