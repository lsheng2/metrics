from .contracts import ConnectionError, ConnectionInfo
from .hsd_opener import BoundHsdesIntegratedPowershellRunner, BoundHsdesOpener
from .request_session import BoundProviderSession


class ResolvedConnection:
    def __init__(self, *, info: ConnectionInfo, material: dict, verify):
        self._info = info
        self._material = dict(material)
        self._verify = verify

    @property
    def info(self) -> ConnectionInfo:
        return self._info

    def open_jira_client(self, factory):
        if self._info.endpoint.provider_id != "jira":
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        token = self._material.get("token", "")
        username = self._material.get("username", "")
        session = BoundProviderSession(
            base_url=self._info.endpoint.base_url,
            auth_mode=self._info.endpoint.auth_mode,
            token=token,
            username=username,
            verify=self._verify,
        )
        kwargs = {
            "url": self._info.endpoint.base_url,
            "verify_ssl": self._verify,
            "session": session,
            "backoff_and_retry": False,
            "retry_with_header": False,
            "timeout": self._info.endpoint.timeout_seconds,
        }
        if self._info.endpoint.auth_mode == "server_pat":
            kwargs["token"] = token
        else:
            kwargs["username"] = username
            kwargs["password"] = token
            kwargs["cloud"] = True
        return factory(**kwargs)

    def open_hsdes_client(self, factory):
        if self._info.endpoint.provider_id != "hsdes":
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        auth_mode = self._info.endpoint.auth_mode
        if auth_mode in {"kerberos", "windows_integrated"} and self._info.endpoint.tls.source == "custom_ca":
            raise ConnectionError("PROVIDER_TRUST_INVALID")
        kwargs = {
            "base_url": self._info.endpoint.base_url,
            "auth_mode": auth_mode,
            "username": self._material.get("username", ""),
            "password": self._material.get("password", ""),
            "token": self._material.get("token", ""),
            "timeout_seconds": self._info.endpoint.timeout_seconds,
            "opener": BoundHsdesOpener(self._info.endpoint.base_url, verify=self._verify),
            "transport": self._info.endpoint.transport,
        }
        if auth_mode in {"kerberos", "windows_integrated"} or self._info.endpoint.transport == "powershell":
            kwargs["powershell_runner"] = BoundHsdesIntegratedPowershellRunner(self._info.endpoint.base_url)
        return factory(**kwargs)

    def open_capture_reader(self, factory):
        if self._info.endpoint.provider_id != "jira":
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        session = BoundProviderSession(
            base_url=self._info.endpoint.base_url,
            auth_mode=self._info.endpoint.auth_mode,
            token=self._material.get("token", ""),
            username=self._material.get("username", ""),
            verify=self._verify,
            capture_responses=True,
        )
        try:
            return factory(info=self._info, session=session)
        except BaseException:
            session.close()
            raise

    def __repr__(self) -> str:
        return (
            f"ResolvedConnection(profile_id={self._info.profile_id!r}, "
            f"provider_id={self._info.endpoint.provider_id!r}, "
            f"endpoint_id={self._info.endpoint.endpoint_id!r}, "
            f"credential_kind={self._info.credential.kind!r})"
        )

    def __reduce_ex__(self, protocol):
        raise TypeError("ResolvedConnection cannot be pickled.")

    def __getstate__(self):
        raise TypeError("ResolvedConnection cannot be pickled.")
