"""OpenStack proxy for live Nova server-status retrieval.

The backend performs the two-step OpenStack flow server-side so that the
application-credential secret and the Keystone token never leave the server:

1. ``_get_token`` obtains a Keystone token via the application-credential
   method (``POST {auth_url}/auth/tokens``) and reads it from the
   ``X-Subject-Token`` response header.
2. ``_list_servers`` lists Nova servers (``GET {nova_endpoint}/servers`` with
   the ``X-Auth-Token`` header) and maps each server to ``{id, name, status}``.

All outbound HTTP uses :class:`httpx.AsyncClient`, matching the existing
outbound-call pattern in ``app/oracle/ai_providers.py``.

Security invariant: the credential secret and the Keystone token are held only
in local variables. They are never placed in response bodies, exception
messages, or logs. Logging references non-sensitive context only (endpoints,
upstream status codes).
"""
import ssl
from dataclasses import dataclass
from typing import Any, List

import httpx

from app.config import settings
from app.logging_config import logger

# Timeout (seconds) for each OpenStack HTTP call, matching the outbound-call
# convention used in app/oracle/ai_providers.py.
_HTTP_TIMEOUT = 60.0


def _resolve_proxy() -> str | None:
    """Return the configured forward-proxy URL, or ``None`` for direct connection.

    Reads ``settings.OPENSTACK_HTTPS_PROXY`` and treats empty/whitespace-only
    values as "no proxy configured". Returning ``None`` yields httpx's default
    (no explicit proxy), preserving today's direct-connection behaviour.
    """
    proxy = settings.OPENSTACK_HTTPS_PROXY
    return proxy if proxy and proxy.strip() else None


class OpenStackError(Exception):
    """Base class for OpenStack proxy failures, carrying a stable error code.

    The ``code`` is a machine-readable identifier the router maps to an HTTP
    status and the frontend maps to a localized message. Error messages never
    include the credential secret or the Keystone token.
    """

    code: str = "OPENSTACK_ERROR"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class OpenStackAuthError(OpenStackError):
    """OpenStack rejected the credentials during token acquisition (401/403)."""

    code = "AUTH_FAILED"


class OpenStackConnectionError(OpenStackError):
    """A network failure occurred while contacting OpenStack."""

    code = "CONNECTION_FAILED"


class OpenStackServiceError(OpenStackError):
    """OpenStack returned an error status other than an auth rejection."""

    code = "OPENSTACK_ERROR"


class OpenStackCACertificateError(OpenStackError):
    """The supplied CA certificate could not be parsed as valid PEM."""

    code = "INVALID_CA_CERTIFICATE"


def _build_verify(ca_certificate: str) -> ssl.SSLContext | bool:
    """Return an httpx ``verify`` value for the effective CA certificate.

    Empty/whitespace-only ``ca_certificate`` yields ``True`` (the system default
    trust store), matching today's implicit behaviour. Otherwise an
    :class:`ssl.SSLContext` is built from the PEM text and returned so both
    outbound calls verify identically. A non-empty value that cannot be parsed
    as a certificate raises :class:`OpenStackCACertificateError` before any
    network call is attempted. The certificate content is never logged.
    """
    if not ca_certificate or not ca_certificate.strip():
        return True
    try:
        context = ssl.create_default_context(cadata=ca_certificate)
    except ssl.SSLError:
        raise OpenStackCACertificateError(
            "Le certificat CA fourni est invalide (format PEM illisible)."
        )
    return context


@dataclass(frozen=True)
class NovaServerDTO:
    """A single Nova server mapped to the fields exposed to the client."""

    id: str
    name: str
    status: str


class OpenStackProxy:
    """Encapsulates the two OpenStack calls needed to list servers.

    Neither the credential secret nor the Keystone token is ever logged or
    returned; both stay in local variables for the duration of a call.
    """

    async def retrieve(
        self,
        auth_url: str,
        credential_id: str,
        secret: str,
        nova_endpoint: str,
        ca_certificate: str = "",
    ) -> List[NovaServerDTO]:
        """Obtain a token then list servers, chaining the two OpenStack calls.

        The ``secret`` argument stays local to this call and is passed only to
        ``_get_token``; the resulting token stays local and is passed only to
        ``_list_servers``. Neither is logged.

        The effective ``verify`` value is built once via :func:`_build_verify`
        before any network call, so an invalid PEM raises
        :class:`OpenStackCACertificateError` before any outbound request is
        attempted. The same ``verify`` value is shared by both calls so they
        verify TLS identically.
        """
        verify = _build_verify(ca_certificate)
        token = await self._get_token(auth_url, credential_id, secret, verify)
        return await self._list_servers(nova_endpoint, token, verify)

    async def _get_token(
        self,
        auth_url: str,
        credential_id: str,
        secret: str,
        verify: ssl.SSLContext | bool = True,
    ) -> str:
        """POST the Keystone application-credential body and return the token.

        The token is read from the ``X-Subject-Token`` response header. Maps
        401/403 to :class:`OpenStackAuthError`, connection/timeout failures to
        :class:`OpenStackConnectionError`, and any other non-2xx response to
        :class:`OpenStackServiceError`.
        """
        url = f"{auth_url.rstrip('/')}/auth/tokens"
        payload = {
            "auth": {
                "identity": {
                    "methods": ["application_credential"],
                    "application_credential": {
                        "id": credential_id,
                        "secret": secret,
                    },
                }
            }
        }

        client_kwargs: dict = {"verify": verify}
        proxy = _resolve_proxy()
        if proxy is not None:
            client_kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=_HTTP_TIMEOUT,
                )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            # Never include payload/secret in the log or message.
            logger.error(
                f"OpenStack token request connection failure: {type(e).__name__}"
            )
            raise OpenStackConnectionError(
                "Impossible de contacter OpenStack Keystone pour l'authentification."
            )

        if response.status_code in (401, 403):
            logger.warning(
                f"OpenStack Keystone rejected credentials "
                f"(status {response.status_code})"
            )
            raise OpenStackAuthError(
                "Les identifiants OpenStack ont été refusés."
            )

        if not response.is_success:
            logger.error(
                f"OpenStack Keystone returned an error status "
                f"{response.status_code} for token acquisition"
            )
            raise OpenStackServiceError(
                f"OpenStack Keystone a retourné une erreur (statut {response.status_code})."
            )

        token = response.headers.get("X-Subject-Token")
        if not token:
            logger.error(
                "OpenStack Keystone token response missing X-Subject-Token header"
            )
            raise OpenStackServiceError(
                "La réponse OpenStack Keystone ne contient pas de jeton d'authentification."
            )

        return token

    async def _list_servers(
        self,
        nova_endpoint: str,
        token: str,
        verify: ssl.SSLContext | bool = True,
    ) -> List[NovaServerDTO]:
        """GET the Nova server list and map each server to id/name/status.

        Sends ``X-Auth-Token: <token>``. Maps connection/timeout failures to
        :class:`OpenStackConnectionError` and any non-2xx response to
        :class:`OpenStackServiceError`.
        """
        url = f"{nova_endpoint.rstrip('/')}/servers"

        client_kwargs: dict = {"verify": verify}
        proxy = _resolve_proxy()
        if proxy is not None:
            client_kwargs["proxy"] = proxy

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get(
                    url,
                    headers={"X-Auth-Token": token},
                    timeout=_HTTP_TIMEOUT,
                )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(
                f"OpenStack Nova request connection failure: {type(e).__name__}"
            )
            raise OpenStackConnectionError(
                "Impossible de contacter le service OpenStack Nova."
            )

        if not response.is_success:
            logger.error(
                f"OpenStack Nova returned an error status "
                f"{response.status_code} for the server list"
            )
            raise OpenStackServiceError(
                f"OpenStack Nova a retourné une erreur (statut {response.status_code})."
            )

        try:
            data: Any = response.json()
        except ValueError:
            logger.error("OpenStack Nova returned a non-JSON server list response")
            raise OpenStackServiceError(
                "La réponse OpenStack Nova est illisible."
            )

        servers = data.get("servers", []) if isinstance(data, dict) else []
        return [
            NovaServerDTO(
                id=str(server.get("id", "")),
                name=str(server.get("name", "")),
                status=str(server.get("status", "")),
            )
            for server in servers
            if isinstance(server, dict)
        ]
