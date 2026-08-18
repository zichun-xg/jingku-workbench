"""接口出入数据结构。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VideoCreateUrl(BaseModel):
    url: str
    title: str = ""
    genre: str = "b2b_demo"


class VideoUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None


class CueUpdate(BaseModel):
    text: Optional[str] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None


class SegmentUpdate(BaseModel):
    topic: Optional[str] = None
    points: Optional[list[str]] = None
    technique: Optional[str] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None


class HighlightUpdate(BaseModel):
    title: Optional[str] = None
    copy_advice: Optional[str] = None
    visual_advice: Optional[str] = None
    audience: Optional[str] = None
    in_library: Optional[bool] = None
    tags: Optional[list[str]] = None


class SettingsIn(BaseModel):
    asr_provider: str = "whisper"
    asr_model: str = "small"
    asr_api_key: str = ""
    asr_base_url: str = ""
    text_provider: str = "openai_compatible"
    text_model: str = "qwen-plus"
    text_api_key: str = ""
    text_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    vision_provider: str = "openai_compatible"
    vision_model: str = "qwen-vl-plus"
    vision_api_key: str = ""
    vision_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    use_same_key: bool = True


class CueOut(BaseModel):
    id: int
    start_ms: int
    end_ms: int
    text: str
    sort_order: int

    class Config:
        from_attributes = True


class FrameOut(BaseModel):
    id: int
    segment_id: Optional[int] = None
    timestamp_ms: int
    file_path: str
    caption: str
    is_reference: bool
    url: str = ""

    class Config:
        from_attributes = True


class TagOut(BaseModel):
    id: int
    name: str
    category: str

    class Config:
        from_attributes = True


class HighlightOut(BaseModel):
    id: int
    video_id: str
    segment_id: Optional[int] = None
    title: str
    copy_advice: str
    visual_advice: str
    audience: str
    in_library: bool
    tags: list[TagOut] = Field(default_factory=list)
    video_title: str = ""
    genre: str = ""
    start_ms: int = 0
    end_ms: int = 0
    time_label: str = ""
    reference_frames: list[FrameOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class SegmentOut(BaseModel):
    id: int
    start_ms: int
    end_ms: int
    topic: str
    points: list[str] = Field(default_factory=list)
    technique: str
    sort_order: int
    frames: list[FrameOut] = Field(default_factory=list)
    highlight: Optional[HighlightOut] = None

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: str
    video_id: str
    job_type: str
    status: str
    step: str
    progress: int
    message: str
    error: str

    class Config:
        from_attributes = True


class VideoListOut(BaseModel):
    id: str
    title: str
    source_type: str
    source_url: str
    genre: str
    duration_ms: int
    status: str
    error_message: str
    thumb_url: str = ""
    created_at: datetime
    highlight_count: int = 0

    class Config:
        from_attributes = True


class VideoDetailOut(VideoListOut):
    file_url: str = ""
    cues: list[CueOut] = Field(default_factory=list)
    segments: list[SegmentOut] = Field(default_factory=list)
    latest_job: Optional[JobOut] = None
