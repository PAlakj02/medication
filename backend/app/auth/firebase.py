"""Firebase ID token verification — login gate only.

Deliberately does NOT use the firebase-admin SDK, which needs a service
account key (a real secret) to talk to Firebase's Admin API. We never call
that API: verifying a token a client already obtained from Firebase Auth
only requires checking its signature against Google's public certs and
confirming the audience/issuer match our project id, both of which
google-auth's verify_firebase_token() does with no secret at all. This
also keeps the architecture honest with the "no per-user data stored"
decision — the backend has no credential capable of looking up or writing
Firebase user records even if it wanted to.
"""

from dataclasses import dataclass

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from requests.adapters import HTTPAdapter

from app.config import get_settings

_CERT_FETCH_TIMEOUT_SECONDS = 8


class _TimeoutHTTPAdapter(HTTPAdapter):
    """Without this, a slow/unreachable Google endpoint hangs this call
    indefinitely — the request only ends when Render's own proxy gives up
    and resets the connection, which surfaces to the browser as a generic
    network failure ("Load failed") with zero diagnostic information,
    instead of a clean, fast 401.
    """

    def send(self, request, **kwargs):
        kwargs.setdefault("timeout", _CERT_FETCH_TIMEOUT_SECONDS)
        return super().send(request, **kwargs)


_session = requests.Session()
_session.mount("https://", _TimeoutHTTPAdapter())
_session.mount("http://", _TimeoutHTTPAdapter())
_request = google_requests.Request(session=_session)


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    email: str | None


class InvalidAuthToken(Exception):
    pass


def verify_id_token(token: str) -> AuthenticatedUser:
    settings = get_settings()
    try:
        claims = id_token.verify_firebase_token(token, _request, audience=settings.firebase_project_id)
    except Exception as exc:
        # Broad on purpose: this function's whole contract is "never let a
        # bad/unverifiable token propagate as anything but InvalidAuthToken"
        # — a malformed token raises ValueError, but a network failure
        # fetching Google's certs raises requests/urllib3 exceptions that
        # need the exact same clean handling, not an unhandled 500.
        raise InvalidAuthToken(str(exc)) from exc

    if claims is None:
        raise InvalidAuthToken("Token verification returned no claims.")

    uid = claims.get("sub") or claims.get("user_id")
    if not uid:
        raise InvalidAuthToken("Token has no subject claim.")

    return AuthenticatedUser(uid=uid, email=claims.get("email"))
