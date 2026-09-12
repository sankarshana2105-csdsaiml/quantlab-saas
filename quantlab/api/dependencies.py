from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from quantlab.auth import AuthService, InvalidCredentials
from quantlab.repository import UserRecord


bearer = HTTPBearer(auto_error=False)


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    auth: AuthService = Depends(get_auth_service),
) -> UserRecord:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidCredentials("Authentication required")
    return auth.current_user(credentials.credentials)
