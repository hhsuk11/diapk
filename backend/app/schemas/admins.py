from datetime import datetime

from pydantic import BaseModel, Field


class AdminUserRead(BaseModel):
    id: int
    email: str
    display_name: str | None
    is_super: bool
    is_disabled: bool
    permissions: list[str]
    created_at: datetime
    updated_at: datetime


class AdminPermissionUpdate(BaseModel):
    is_super: bool = False
    permissions: list[str] = Field(default_factory=list)
