from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.auth import (
    AuthBootstrapResponse,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthSessionResponse,
    AuthUser,
)
from app.services.auth_service import auth_service, require_current_user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/bootstrap", response_model=AuthBootstrapResponse)
def bootstrap_auth() -> AuthBootstrapResponse:
    return AuthBootstrapResponse(setup_required=auth_service.setup_required())


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRegisterRequest) -> AuthSessionResponse:
    try:
        return auth_service.register(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=AuthSessionResponse)
def login(payload: AuthLoginRequest) -> AuthSessionResponse:
    try:
        return auth_service.login(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get("/me", response_model=AuthUser)
def get_current_user(user: AuthUser = Depends(require_current_user)) -> AuthUser:
    return user
