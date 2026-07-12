from pydantic import BaseModel


class PrincipalRead(BaseModel):
    email: str | None
    is_authenticated: bool
    is_super: bool
    permissions: list[str]
    auth_mode: str
    oauth_configured: bool
