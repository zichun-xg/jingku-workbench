"""本地数据库表：视频、逐字稿、段落、画面帧、亮点卡、标签、分析任务。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Video(Base):
    """一条被收藏的视频（片库条目）。"""

    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    source_type: Mapped[str] = mapped_column(String(20), default="local")  # local=本地文件 url=公开链接
    source_url: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(Text, default="")  # 相对 data/ 的路径
    thumb_path: Mapped[str] = mapped_column(Text, default="")
    genre: Mapped[str] = mapped_column(String(40), default="b2b_demo")  # b2b_demo=B端演示 corp_promo=企业宣传片 other=其他
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="ready")  # downloading/ready/analyzing/analyzed/error
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    cues: Mapped[list["TranscriptCue"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    segments: Mapped[list["Segment"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    frames: Mapped[list["Frame"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    highlights: Mapped[list["Highlight"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class TranscriptCue(Base):
    """逐字稿一句，带起止时间，点击可跳转播放。"""

    __tablename__ = "transcript_cues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    start_ms: Mapped[int] = mapped_column(Integer, default=0)
    end_ms: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    video: Mapped["Video"] = relationship(back_populates="cues")


class Segment(Base):
    """拉片段落：某段时间在讲什么、要点 1/2/3、制作手法。"""

    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    start_ms: Mapped[int] = mapped_column(Integer, default=0)
    end_ms: Mapped[int] = mapped_column(Integer, default=0)
    topic: Mapped[str] = mapped_column(String(500), default="")
    points_json: Mapped[str] = mapped_column(Text, default="[]")  # 要点列表 JSON
    technique: Mapped[str] = mapped_column(Text, default="")  # 制作手法
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    video: Mapped["Video"] = relationship(back_populates="segments")
    frames: Mapped[list["Frame"]] = relationship(back_populates="segment")
    highlight: Mapped["Highlight"] = relationship(back_populates="segment", uselist=False, cascade="all, delete-orphan")


class Frame(Base):
    """从视频抽出的关键画面帧，可当亮点参考图。"""

    __tablename__ = "frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    segment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("segments.id", ondelete="SET NULL"), nullable=True)
    timestamp_ms: Mapped[int] = mapped_column(Integer, default=0)
    file_path: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")  # 画面说明
    is_reference: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否作为亮点参考图

    video: Mapped["Video"] = relationship(back_populates="frames")
    segment: Mapped[Optional["Segment"]] = relationship(back_populates="frames")


class Highlight(Base):
    """可复用亮点卡：文案建议 + 画面建议 + 参考图 + 标签。"""

    __tablename__ = "highlights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    segment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("segments.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    copy_advice: Mapped[str] = mapped_column(Text, default="")  # 文案上可以怎么写
    visual_advice: Mapped[str] = mapped_column(Text, default="")  # 画面上建议展示什么
    audience: Mapped[str] = mapped_column(String(200), default="")  # 受众，如国企领导
    in_library: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否进入灵感库
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    video: Mapped["Video"] = relationship(back_populates="highlights")
    segment: Mapped[Optional["Segment"]] = relationship(back_populates="highlight")
    tags: Mapped[list["Tag"]] = relationship(secondary="highlight_tags", back_populates="highlights")


class Tag(Base):
    """灵感标签，用于筛选（痛点开场、数据金句等）。"""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    category: Mapped[str] = mapped_column(String(40), default="technique")  # audience/genre/technique/structure

    highlights: Mapped[list["Highlight"]] = relationship(secondary="highlight_tags", back_populates="tags")


class HighlightTag(Base):
    """亮点与标签的多对多关系。"""

    __tablename__ = "highlight_tags"
    __table_args__ = (UniqueConstraint("highlight_id", "tag_id"),)

    highlight_id: Mapped[int] = mapped_column(ForeignKey("highlights.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Job(Base):
    """后台任务：下载或 AI 拉片，前端轮询进度。"""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    job_type: Mapped[str] = mapped_column(String(40), default="analyze")  # analyze / download
    status: Mapped[str] = mapped_column(String(40), default="queued")  # queued/running/done/error
    step: Mapped[str] = mapped_column(String(40), default="")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    video: Mapped["Video"] = relationship(back_populates="jobs")
