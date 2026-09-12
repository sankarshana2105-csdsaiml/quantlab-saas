from fastapi import APIRouter, Depends, status

from quantlab.auth import AuthService
from quantlab.repository import UserRecord

from .dependencies import current_user, get_auth_service
from .models import LoginRequest, RegisterRequest, TokenResponse, UserResponse


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Register a user")
def register(payload: RegisterRequest, auth: AuthService = Depends(get_auth_service)) -> UserResponse:
    return UserResponse.model_validate(auth.register(str(payload.email), payload.password))


@router.post("/login", response_model=TokenResponse, summary="Log in")
def login(payload: LoginRequest, auth: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return TokenResponse(access_token=auth.login(str(payload.email), payload.password))


@router.get("/me", response_model=UserResponse, summary="Get the current user")
def me(user: UserRecord = Depends(current_user)) -> UserResponse:
    return UserResponse.model_validate(user)
