from datetime import datetime

from pydantic import BaseModel, Field


class AuthRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=200)
    display_name: str | None = Field(default=None, max_length=80)


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class AuthUser(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str
    created_at: datetime


class AuthSessionResponse(BaseModel):
    access_token: str = Field(min_length=1)
    token_type: str = "Bearer"
    expires_at: datetime
    expires_in_seconds: int = Field(ge=60)
    user: AuthUser
