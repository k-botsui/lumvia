from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Record, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str | None] = mapped_column(Text)
    oidc_subject: Mapped[str | None] = mapped_column(String(500), unique=True)


class Library(Record, Base):
    __tablename__ = "libraries"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(String(100), default="My Library")


class Session(Record, Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Source(Record, Base):
    __tablename__ = "sources"
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="local_upload")
    original_name: Mapped[str] = mapped_column(String(255))
    external_url: Mapped[str | None] = mapped_column(String(2048))
    external_id: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    __table_args__ = (UniqueConstraint("library_id", "kind", "external_id", name="uq_source_external"),)


class Media(Record, Base):
    __tablename__ = "media"
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    note: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="PROCESSING")
    kind: Mapped[str] = mapped_column(String(20), default="video")
    storage_mode: Mapped[str] = mapped_column(String(20), default="MANAGED")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(36))
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        Index("ix_media_library_created", "library_id", "created_at"),
        UniqueConstraint("library_id", "idempotency_key"),
    )


class Asset(Record, Base):
    __tablename__ = "assets"
    media_id: Mapped[str] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(500), unique=True)
    role: Mapped[str] = mapped_column(String(30))
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (UniqueConstraint("media_id", "role"),)


class PersonTarget(Record, Base):
    __tablename__ = "person_targets"
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    embedding: Mapped[list] = mapped_column(JSONB)
    model_version: Mapped[str] = mapped_column(String(200))
    image_key: Mapped[str] = mapped_column(String(500), unique=True)


class Batch(Record, Base):
    __tablename__ = "batches"
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="動画の追加")


class AnalysisRun(Record, Base):
    __tablename__ = "analysis_runs"
    media_id: Mapped[str] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), index=True)
    analyzer: Mapped[str] = mapped_column(String(50))
    model_version: Mapped[str] = mapped_column(String(200))
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Job(Record, Base):
    __tablename__ = "jobs"
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id", ondelete="SET NULL"), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(50))
    request_id: Mapped[str | None] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(30), default="PENDING")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(String(300))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("progress BETWEEN 0 AND 100"),
        Index("ix_job_dispatch", "state", "updated_at"),
        Index(
            "uq_job_active",
            "media_id",
            "kind",
            unique=True,
            postgresql_where=text("state IN ('PENDING','QUEUED','RUNNING','RETRYING','CANCEL_REQUESTED')"),
        ),
    )


class Cell(Record, Base):
    __tablename__ = "cells"
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    note: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(30), default="user")
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="SET NULL"))
    __table_args__ = (CheckConstraint("start_ms >= 0 AND end_ms > start_ms"),)


class Shelf(Record, Base):
    __tablename__ = "shelves"
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    color: Mapped[str] = mapped_column(String(7), default="#4f7bff")
    header_key: Mapped[str | None] = mapped_column(String(500))
    header_frame: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: {"x": 50, "y": 50, "zoom": 1},
        server_default=text('\'{"x": 50, "y": 50, "zoom": 1}\'::jsonb'),
    )
    __table_args__ = (UniqueConstraint("library_id", "name"),)


class Collection(Record, Base):
    __tablename__ = "collections"
    library_id: Mapped[str] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    color: Mapped[str] = mapped_column(String(7), default="#4f7bff")
    header_key: Mapped[str | None] = mapped_column(String(500))
    header_frame: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: {"x": 50, "y": 50, "zoom": 1},
        server_default=text('\'{"x": 50, "y": 50, "zoom": 1}\'::jsonb'),
    )
    __table_args__ = (UniqueConstraint("library_id", "name"),)


shelf_media = Table(
    "shelf_media",
    Base.metadata,
    Column("shelf_id", ForeignKey("shelves.id", ondelete="CASCADE"), primary_key=True),
    Column("media_id", ForeignKey("media.id", ondelete="CASCADE"), primary_key=True),
)
shelf_cells = Table(
    "shelf_cells",
    Base.metadata,
    Column("shelf_id", ForeignKey("shelves.id", ondelete="CASCADE"), primary_key=True),
    Column("cell_id", ForeignKey("cells.id", ondelete="CASCADE"), primary_key=True),
)
collection_media = Table(
    "collection_media",
    Base.metadata,
    Column("collection_id", ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("media_id", ForeignKey("media.id", ondelete="CASCADE"), primary_key=True),
)
collection_cells = Table(
    "collection_cells",
    Base.metadata,
    Column("collection_id", ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("cell_id", ForeignKey("cells.id", ondelete="CASCADE"), primary_key=True),
)


class AnalysisEvent(Record, Base):
    __tablename__ = "analysis_events"
    media_id: Mapped[str] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50))
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(200))
    confidence: Mapped[float | None]
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class Transcript(Record, Base):
    __tablename__ = "transcripts"
    media_id: Mapped[str] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(20))


class Audit(Record, Base):
    __tablename__ = "audit_events"
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(36))
    request_id: Mapped[str | None] = mapped_column(String(36))


class Deletion(Record, Base):
    __tablename__ = "asset_deletions"
    key: Mapped[str] = mapped_column(String(500), unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
