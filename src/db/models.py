from sqlmodel import SQLModel, Field, Column
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Index, Text, func
import enum


class Visibility(str, enum.Enum):
    public = "public"
    unlisted = "unlisted"
    private = "private"


class ImageStatus(str, enum.Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class ReportStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


def created_at_column() -> Column:
    return Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class User(SQLModel, table=True):
    __tablename__ = "users"

    uid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    email: str = Field(unique=True, index=True)
    password_hash: str = Field(exclude=True)
    is_admin: bool = Field(default=False)

    created_at: datetime | None = Field(default=None, sa_column=created_at_column())


class LoginSession(SQLModel, table=True):
    __tablename__ = "login_sessions"

    token_hash: str = Field(primary_key=True)  
    user_uid: uuid.UUID = Field(foreign_key="users.uid", ondelete="CASCADE", index=True)

    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Paste(SQLModel, table=True):
    __tablename__ = "pastes"
    __table_args__ = (
        Index("ix_pastes_public", "visibility", "created_at"),  
        Index("ix_pastes_owner", "owner_uid", "created_at"),  
        Index("ix_pastes_expires", "expires_at"), 
    )

    uid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    owner_uid: uuid.UUID | None = Field(
        default=None, foreign_key="users.uid", ondelete="CASCADE"
    )  
    title: str | None = None
    content: str | None = Field(
        default=None, sa_column=Column(Text)
    )  
    language: str | None = None  
    visibility: Visibility
    burn_after_reading: bool = Field(default=False)
    size_bytes: int

    expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )  
    created_at: datetime | None = Field(default=None, sa_column=created_at_column())


class Image(SQLModel, table=True):
    __tablename__ = "images"

    uid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    paste_uid: uuid.UUID = Field(
        foreign_key="pastes.uid", ondelete="CASCADE", index=True
    )
    object_key: str
    thumb_key: str | None = None  
    content_type: str
    size_bytes: int
    status: ImageStatus = Field(default=ImageStatus.pending)

    created_at: datetime | None = Field(default=None, sa_column=created_at_column())


class Report(SQLModel, table=True):
    __tablename__ = "reports"

    uid: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    paste_uid: uuid.UUID = Field(
        foreign_key="pastes.uid", ondelete="CASCADE", index=True
    )
    reason: str
    reporter_ip_hash: str = Field(exclude=True)
    status: ReportStatus = Field(default=ReportStatus.open)

    created_at: datetime | None = Field(default=None, sa_column=created_at_column())
