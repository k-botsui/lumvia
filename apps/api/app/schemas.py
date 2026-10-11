from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Tags = Annotated[
    list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]],
    Field(max_length=20),
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Strict):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)


class MediaPatch(Strict):
    title: Title | None = None
    note: str | None = Field(default=None, max_length=10000)
    tags: Tags | None = None
    favorite: bool | None = None

    @field_validator("title", "note", "tags", "favorite")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("null is not permitted")
        return value


class CellInput(Strict):
    media_id: str = Field(max_length=36)
    title: Title
    start_ms: int = Field(ge=0, strict=True)
    end_ms: int = Field(gt=0, strict=True)
    note: str = Field(default="", max_length=10000)
    tags: Tags = []
    event_id: str | None = Field(default=None, max_length=36)


class CellPatch(Strict):
    title: Title
    start_ms: int = Field(ge=0, strict=True)
    end_ms: int = Field(gt=0, strict=True)
    note: str = Field(default="", max_length=10000)
    tags: Tags = []


class GroupInput(Strict):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    description: str = Field(default="", max_length=500)
    color: str = Field(default="#4f7bff", pattern=r"^#[0-9a-fA-F]{6}$")


class HeaderFrame(Strict):
    x: float = Field(ge=0, le=100, allow_inf_nan=False)
    y: float = Field(ge=0, le=100, allow_inf_nan=False)
    zoom: float = Field(ge=1, le=3, allow_inf_nan=False)


class Membership(Strict):
    media_id: str | None = Field(default=None, max_length=36)
    cell_id: str | None = Field(default=None, max_length=36)


class BatchMembership(Strict):
    media_ids: list[Annotated[str, StringConstraints(min_length=1, max_length=36)]] = Field(
        default_factory=list, max_length=100
    )
    cell_ids: list[Annotated[str, StringConstraints(min_length=1, max_length=36)]] = Field(
        default_factory=list, max_length=100
    )


class AnalyzeInput(Strict):
    analyzer: str = Field(default="scenes", pattern="^scenes$")


class PasswordChange(Strict):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=12, max_length=256)
