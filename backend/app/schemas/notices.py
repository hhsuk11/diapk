from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoticeBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    is_published: bool = True
    is_pinned: bool = False


class NoticeCreate(NoticeBase):
    pass


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=10000)
    is_published: bool | None = None
    is_pinned: bool | None = None


class NoticeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    is_published: bool
    is_pinned: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
