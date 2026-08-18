from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()


class Video(Base):
    __tablename__ = "videos"
    video_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(512))
    upload_date: Mapped[str | None] = mapped_column(String(32))
    transcript_with_ts: Mapped[str | None] = mapped_column(Text)
    transcript_no_ts: Mapped[str | None] = mapped_column(Text)
    tokens_with_ts: Mapped[int] = mapped_column(Integer, default=0)
    tokens_no_ts: Mapped[int] = mapped_column(Integer, default=0)
    last_modified: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC)
    )

    folders: Mapped[list[VideoFolder]] = relationship("VideoFolder", back_populates="video")
    summaries_v2: Mapped[list[SummariesV2]] = relationship("SummariesV2", back_populates="video")


class VideoFolder(Base):
    __tablename__ = "video_folders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    folder_name: Mapped[str | None] = mapped_column(String(255))
    original_playlist_id: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(20), default="playlist")
    video_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("videos.video_id"))
    last_modified: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC)
    )

    video: Mapped[Video | None] = relationship("Video", back_populates="folders")


class SummariesV2(Base):
    __tablename__ = "summaries_v2"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("videos.video_id"))
    video_title: Mapped[str | None] = mapped_column(String(512))
    model_name: Mapped[str | None] = mapped_column(String(50))
    date_generated: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC)
    )
    concise_summary: Mapped[str | None] = mapped_column(Text)
    key_topics: Mapped[str | None] = mapped_column(Text)
    important_takeaways: Mapped[str | None] = mapped_column(Text)
    comprehensive_notes: Mapped[str | None] = mapped_column(Text)

    video: Mapped[Video | None] = relationship("Video", back_populates="summaries_v2")


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    end_time: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="in_progress")
    message: Mapped[str | None] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="reader")
