import base64
import os
import ssl
import subprocess
from urllib import error, request

from .contracts import ConnectionError
from .normalization import has_base_prefix, normalize_base_url, normalize_request_url


class NoRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BoundHsdesOpener:
    def __init__(self, base_url: str, opener=None, verify=True):
        self._base = normalize_base_url(base_url)
        self._opener = opener or self._default_opener(verify)

    def set_transport(self, opener) -> None:
        self._opener = opener

    def __call__(self, http_request, timeout=None):
        if str(http_request.get_method()).upper() not in {"GET", "HEAD"}:
            raise ConnectionError("PROVIDER_METHOD_FORBIDDEN")
        candidate = normalize_request_url(http_request.full_url)
        if not has_base_prefix(self._base, candidate):
            raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
        try:
            response = self._opener(http_request, timeout=timeout)
        except error.HTTPError as exception:
            self._close_response(exception.fp)
            if 300 <= int(exception.code) < 400:
                raise ConnectionError("PROVIDER_REDIRECT_UNSUPPORTED") from None
            if int(exception.code) == 401:
                raise ConnectionError("PROVIDER_AUTH_FAILED") from None
            if int(exception.code) == 403:
                raise ConnectionError("PROVIDER_PERMISSION_DENIED") from None
            raise ConnectionError("PROVIDER_NETWORK_ERROR") from None
        status_code = _response_status_code(response)
        if 300 <= status_code < 400:
            self._close_response(response)
            raise ConnectionError("PROVIDER_REDIRECT_UNSUPPORTED")
        return response

    def _default_opener(self, verify):
        handlers = [NoRedirectHandler()]
        if isinstance(verify, str):
            try:
                context = ssl.create_default_context(cafile=verify)
            except Exception:
                raise ConnectionError("PROVIDER_TRUST_INVALID") from None
            handlers.append(request.HTTPSHandler(context=context))
        return request.build_opener(*handlers).open

    def _close_response(self, response) -> None:
        close = getattr(response, "close", None)
        if close:
            close()


class BoundHsdesIntegratedPowershellRunner:
    def __init__(self, base_url: str, runner=None):
        self._base = normalize_base_url(base_url)
        self._runner = runner or subprocess.run

    def set_runner(self, runner) -> None:
        self._runner = runner

    def build_command(self, url: str, timeout_seconds: int) -> list[str]:
        candidate = normalize_request_url(url)
        if not has_base_prefix(self._base, candidate):
            raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
        escaped_url = url.replace("'", "''")
        script = (
            '$ProgressPreference = "SilentlyContinue"; '
            f"$response = Invoke-WebRequest -Uri '{escaped_url}' "
            f"-UseDefaultCredentials -UseBasicParsing -TimeoutSec {int(timeout_seconds)} "
            '-MaximumRedirection 0 -Headers @{Accept="application/json"}; '
            "$response.Content"
        )
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        return ["powershell", "-NoProfile", "-EncodedCommand", encoded_script]

    def run(self, url: str, timeout_seconds: int):
        command = self.build_command(url, timeout_seconds)
        return self._run_command(command, timeout_seconds)

    def _run_command(self, command: list[str], timeout_seconds: int):
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=int(timeout_seconds) + 5,
                env=dict(os.environ),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ConnectionError("PROVIDER_NETWORK_ERROR") from None
        if completed.returncode != 0:
            raise ConnectionError(_powershell_error_code(completed.stderr)) from None
        return completed

def _response_status_code(response) -> int:
    if hasattr(response, "getcode"):
        code = response.getcode()
        if code is not None:
            return int(code)
    return int(getattr(response, "status", getattr(response, "code", 0)) or 0)


def _powershell_error_code(stderr: str) -> str:
    lowered = str(stderr or "").lower()
    if "401" in lowered or "unauthorized" in lowered:
        return "PROVIDER_AUTH_FAILED"
    if "403" in lowered or "forbidden" in lowered:
        return "PROVIDER_PERMISSION_DENIED"
    if "redirect" in lowered:
        return "PROVIDER_REDIRECT_UNSUPPORTED"
    return "PROVIDER_NETWORK_ERROR"
