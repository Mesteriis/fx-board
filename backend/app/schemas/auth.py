from pydantic import BaseModel, Field


class TelegramWebAppAuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=8192)


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    is_admin: bool
    is_banned: bool


class RequiredChannelResponse(BaseModel):
    chat_id: str
    title: str | None
    is_member: bool


class AccessResponse(BaseModel):
    allowed: bool
    required_channels: list[RequiredChannelResponse] = Field(default_factory=list)
    missing_channels: list[RequiredChannelResponse] = Field(default_factory=list)


class AuthResponse(BaseModel):
    user: UserResponse
    access: AccessResponse
    csrf_token: str
