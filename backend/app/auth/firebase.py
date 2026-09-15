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

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import get_settings

_request = google_requests.Request()


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
    except ValueError as exc:
        raise InvalidAuthToken(str(exc)) from exc

    if claims is None:
        raise InvalidAuthToken("Token verification returned no claims.")

    uid = claims.get("sub") or claims.get("user_id")
    if not uid:
        raise InvalidAuthToken("Token has no subject claim.")

    return AuthenticatedUser(uid=uid, email=claims.get("email"))
