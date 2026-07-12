from pydantic import BaseModel, Field, field_validator


class PlayerCharacterIn(BaseModel):
    class_name: str = Field(min_length=1, max_length=40)
    character_name: str | None = Field(default=None, max_length=80)


class PlayerCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    characters: list[PlayerCharacterIn] = Field(default_factory=list)

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class PlayerUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class PlayerAdminRead(BaseModel):
    player_id: int
    player_name: str
    current_tier: str | None
    is_active: bool
    total_games: int
    game_refs: int
    stats_refs: int
    character_count: int


class PlayerDeleteRead(BaseModel):
    player_id: int
    deleted: bool
    deactivated: bool
