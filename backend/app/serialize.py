"""把数据库对象拼成前端要用的结构（含媒体 URL、时间码、要点列表）。"""
from __future__ import annotations

import json

from .models import Frame, Highlight, Job, Segment, Tag, TranscriptCue, Video
from .timeutil import ms_to_tc


def media_url(relative: str) -> str:
    if not relative:
        return ""
    return "/media/" + relative.lstrip("/")


def cue_out(cue: TranscriptCue) -> dict:
    return {
        "id": cue.id,
        "start_ms": cue.start_ms,
        "end_ms": cue.end_ms,
        "text": cue.text,
        "sort_order": cue.sort_order,
    }


def tag_out(tag: Tag) -> dict:
    return {"id": tag.id, "name": tag.name, "category": tag.category}


def frame_out(frame: Frame) -> dict:
    return {
        "id": frame.id,
        "segment_id": frame.segment_id,
        "timestamp_ms": frame.timestamp_ms,
        "file_path": frame.file_path,
        "caption": frame.caption,
        "is_reference": frame.is_reference,
        "url": media_url(frame.file_path),
    }


def highlight_out(h: Highlight, video: Video | None = None, extra_frames: list[Frame] | None = None) -> dict:
    video = video or h.video
    start_ms = h.segment.start_ms if h.segment else 0
    end_ms = h.segment.end_ms if h.segment else 0
    frames = extra_frames
    if frames is None:
        if h.segment:
            frames = [f for f in (h.segment.frames or []) if f.is_reference] or list(h.segment.frames or [])[:3]
        else:
            frames = []
    return {
        "id": h.id,
        "video_id": h.video_id,
        "segment_id": h.segment_id,
        "title": h.title,
        "copy_advice": h.copy_advice,
        "visual_advice": h.visual_advice,
        "audience": h.audience,
        "in_library": h.in_library,
        "tags": [tag_out(t) for t in h.tags],
        "video_title": video.title if video else "",
        "genre": video.genre if video else "",
        "start_ms": start_ms,
        "end_ms": end_ms,
        "time_label": f"{ms_to_tc(start_ms)}-{ms_to_tc(end_ms)}",
        "reference_frames": [frame_out(f) for f in frames],
    }


def segment_out(seg: Segment) -> dict:
    points = []
    try:
        points = json.loads(seg.points_json or "[]")
    except json.JSONDecodeError:
        points = []
    if not isinstance(points, list):
        points = []
    return {
        "id": seg.id,
        "start_ms": seg.start_ms,
        "end_ms": seg.end_ms,
        "topic": seg.topic,
        "points": [str(p) for p in points],
        "technique": seg.technique,
        "sort_order": seg.sort_order,
        "frames": [frame_out(f) for f in sorted(seg.frames, key=lambda x: x.timestamp_ms)],
        "highlight": highlight_out(seg.highlight, seg.video) if seg.highlight else None,
    }


def job_out(job: Job) -> dict:
    return {
        "id": job.id,
        "video_id": job.video_id,
        "job_type": job.job_type,
        "status": job.status,
        "step": job.step,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
    }


def video_list_out(v: Video) -> dict:
    return {
        "id": v.id,
        "title": v.title,
        "source_type": v.source_type,
        "source_url": v.source_url,
        "genre": v.genre,
        "duration_ms": v.duration_ms,
        "status": v.status,
        "error_message": v.error_message,
        "thumb_url": media_url(v.thumb_path),
        "created_at": v.created_at.isoformat() if v.created_at else "",
        "highlight_count": len(v.highlights or []),
    }


def video_detail_out(v: Video) -> dict:
    data = video_list_out(v)
    jobs = sorted(v.jobs or [], key=lambda j: j.created_at or 0, reverse=True)
    data.update(
        {
            "file_url": media_url(v.file_path),
            "cues": [cue_out(c) for c in sorted(v.cues, key=lambda x: x.start_ms)],
            "segments": [segment_out(s) for s in sorted(v.segments, key=lambda x: x.start_ms)],
            "latest_job": job_out(jobs[0]) if jobs else None,
        }
    )
    return data
