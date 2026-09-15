from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.firebase import AuthenticatedUser, InvalidAuthToken, verify_id_token

_bearer_scheme = HTTPBearer(auto_error=False)


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    try:
        return verify_id_token(credentials.credentials)
    except InvalidAuthToken as exc:
        raise HTTPException(status_code=401, detail=f"Invalid auth token: {exc}") from exc
