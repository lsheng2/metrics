import base64

import requests

from .contracts import ConnectionError
from .normalization import has_base_prefix, normalize_base_url, normalize_request_url, search_post_paths


class BoundProviderSession(requests.Session):
    def __init__(self, *, base_url: str, auth_mode: str, token: str, username: str, verify, capture_responses=False):
        super().__init__()
        self._base = normalize_base_url(base_url)
        self._capture_responses = capture_responses
        self._allowed_search_posts = search_post_paths(self._base)
        self.verify = verify
        self.proxies.update(requests.utils.get_environ_proxies(self._base.base_url))
        self.trust_env = False
        self.cookies.clear()
        self.headers.update({"Accept": "application/json"})
        self._set_selected_auth(auth_mode, token, username)

    def request(self, method, url, **kwargs):
        kwargs["allow_redirects"] = False
        return super().request(method, url, **kwargs)

    def send(self, request, **kwargs):
        self._validate_pre_send(request)
        request.headers.pop("Cookie", None)
        self.cookies.clear()
        kwargs["allow_redirects"] = False
        response = super().send(request, **kwargs)
        if 300 <= int(response.status_code) < 400 and not self._capture_responses:
            if response.raw is not None:
                response.close()
            raise ConnectionError("PROVIDER_REDIRECT_UNSUPPORTED")
        return response

    def _set_selected_auth(self, auth_mode: str, token: str, username: str) -> None:
        if auth_mode == "server_pat" and token:
            self.headers["Authorization"] = f"Bearer {token}"
            return
        if token and username:
            encoded = base64.b64encode(f"{username}:{token}".encode("utf-8")).decode("ascii")
            self.headers["Authorization"] = f"Basic {encoded}"

    def _validate_pre_send(self, prepared_request) -> None:
        candidate = normalize_request_url(prepared_request.url)
        if not has_base_prefix(self._base, candidate):
            raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
        method = str(prepared_request.method or "").upper()
        if method in {"GET", "HEAD"}:
            return
        if method == "POST" and candidate.path_prefix in self._allowed_search_posts:
            return
        raise ConnectionError("PROVIDER_METHOD_FORBIDDEN")
