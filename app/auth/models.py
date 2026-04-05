from pydantic import BaseModel, Field


class SessionUser(BaseModel):
    id: str = Field(..., description="Discord user ID")
    display_name: str = Field(..., description="Discord display name")
    avatar_url: str | None = Field(default=None, description="Discord avatar URL")
    authorized: bool = Field(..., description="Whether this user is allowed to use the app")


class SessionState(BaseModel):
    authenticated: bool = Field(..., description="Whether a valid session exists")
    user: SessionUser | None = Field(default=None, description="Logged-in Discord user")
