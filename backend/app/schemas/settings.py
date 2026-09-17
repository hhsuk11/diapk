from pydantic import AnyUrl, BaseModel, Field, field_validator


class PublicSettingsRead(BaseModel):
    discord_url: str | None = None


class AdminSettingsUpdate(BaseModel):
    discord_url: str | None = Field(default=None, max_length=1000)

    @field_validator("discord_url")
    @classmethod
    def validate_discord_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        AnyUrl(stripped)
        return stripped


class AdminSettingsRead(PublicSettingsRead):
    pass
