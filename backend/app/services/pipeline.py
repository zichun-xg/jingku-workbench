"""拉片流水线：转写 →（可选看图）分段写亮点 → 抽关键帧 → 画面说明。"""
from __future__ import annotations

import base64
import json
import logging
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Frame, Highlight, Job, Segment, Tag, TranscriptCue, Video
from ..timeutil import ms_to_tc, tc_to_ms
from . import asr, llm, media, settings as settings_mod

log = logging.getLogger("jingku.pipeline")


def _now():
    return datetime.now(timezone.utc)


def _touch_job(db: Session, job: Job, **kwargs) -> None:
    for k, v in kwargs.items():
        setattr(job, k, v)
    job.updated_at = _now()
    db.commit()


def _get_or_create_tag(db: Session, name: str) -> Tag:
    name = (name or "").strip()[:80]
    if not name:
        name = "未分类"
    tag = db.query(Tag).filter(Tag.name == name).one_or_none()
    if tag:
        return tag
    tag = Tag(name=name, category="technique")
    db.add(tag)
    db.flush()
    return tag


def _transcript_blob(cues: list[TranscriptCue]) -> str:
    lines = []
    for cue in cues:
        lines.append(f"[{ms_to_tc(cue.start_ms)}-{ms_to_tc(cue.end_ms)}] {cue.text}")
    return "\n".join(lines)


def _image_data_url(path: Path) -> str:
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _fallback_segments(video: Video, cues: list[TranscriptCue]) -> list[dict]:
    """没有模型 Key 或模型失败时：按约 20 秒切段，留空亮点让人填。"""
    if not cues:
        return [
            {
                "start_ms": 0,
                "end_ms": video.duration_ms or 0,
                "topic": "待填写本段主题",
                "points": ["待补充要点 1", "待补充要点 2", "待补充要点 3"],
                "technique": "",
                "highlight": {
                    "title": "待写亮点",
                    "copy_advice": "",
                    "visual_advice": "",
                    "audience": "",
                    "tags": [],
                },
            }
        ]
    chunks: list[dict] = []
    start = cues[0].start_ms
    buf: list[str] = []
    for cue in cues:
        buf.append(cue.text)
        if cue.end_ms - start >= 20000:
            chunks.append(_chunk(start, cue.end_ms, buf))
            start = cue.end_ms
            buf = []
    if buf:
        chunks.append(_chunk(start, cues[-1].end_ms, buf))
    return chunks


def _chunk(start_ms: int, end_ms: int, texts: list[str]) -> dict:
    preview = " ".join(texts)[:80]
    return {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "topic": preview or "待填写本段主题",
        "points": ["待补充要点 1", "待补充要点 2", "待补充要点 3"],
        "technique": "",
        "highlight": {
            "title": "待写亮点",
            "copy_advice": f"这一段（{ms_to_tc(start_ms)}-{ms_to_tc(end_ms)}）可复用的文案写法，请补全。",
            "visual_advice": "画面上建议展示什么，请补全。",
            "audience": "",
            "tags": ["待打标"],
        },
    }


def _normalize_llm_segments(payload: dict, duration_ms: int) -> list[dict]:
    items = payload.get("segments") or []
    out: list[dict] = []
    for raw in items:
        start_ms = tc_to_ms(raw.get("start") or raw.get("start_ms"))
        end_ms = tc_to_ms(raw.get("end") or raw.get("end_ms"))
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        if duration_ms:
            end_ms = min(end_ms, duration_ms)
        hl = raw.get("highlight") or {}
        points = raw.get("points") or []
        if isinstance(points, str):
            points = [points]
        tags = hl.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        out.append(
            {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "topic": str(raw.get("topic") or "").strip() or "未命名段落",
                "points": [str(p).strip() for p in points if str(p).strip()][:5],
                "technique": str(raw.get("technique") or "").strip(),
                "highlight": {
                    "title": str(hl.get("title") or raw.get("topic") or "亮点"),
                    "copy_advice": str(hl.get("copy_advice") or "").strip(),
                    "visual_advice": str(hl.get("visual_advice") or "").strip(),
                    "audience": str(hl.get("audience") or "").strip(),
                    "tags": [str(t).strip() for t in tags if str(t).strip()][:8],
                },
            }
        )
    out.sort(key=lambda x: x["start_ms"])
    return out


def _replace_analysis(db: Session, video: Video, segments_data: list[dict]) -> list[Segment]:
    db.query(Frame).filter(Frame.video_id == video.id).delete()
    db.query(Highlight).filter(Highlight.video_id == video.id).delete()
    db.query(Segment).filter(Segment.video_id == video.id).delete()
    db.flush()
    created: list[Segment] = []
    for i, item in enumerate(segments_data):
        seg = Segment(
            video_id=video.id,
            start_ms=item["start_ms"],
            end_ms=item["end_ms"],
            topic=item["topic"],
            points_json=json.dumps(item.get("points") or [], ensure_ascii=False),
            technique=item.get("technique") or "",
            sort_order=i,
        )
        db.add(seg)
        db.flush()
        hl_raw = item.get("highlight") or {}
        hl = Highlight(
            video_id=video.id,
            segment_id=seg.id,
            title=hl_raw.get("title") or item["topic"],
            copy_advice=hl_raw.get("copy_advice") or "",
            visual_advice=hl_raw.get("visual_advice") or "",
            audience=hl_raw.get("audience") or "",
            in_library=True,
        )
        for tag_name in hl_raw.get("tags") or []:
            hl.tags.append(_get_or_create_tag(db, tag_name))
        db.add(hl)
        created.append(seg)
    db.flush()
    return created


def _extract_segment_frames(db: Session, video: Video, segments: list[Segment]) -> None:
    source = media.abs_path(video.file_path)
    frame_root = media.frames_dir(video.id)
    for seg in segments:
        span = max(1, seg.end_ms - seg.start_ms)
        stamps = [
            seg.start_ms + int(span * 0.2),
            seg.start_ms + int(span * 0.5),
            seg.start_ms + int(span * 0.8),
        ]
        for j, ts in enumerate(stamps):
            dest = frame_root / f"s{seg.id}_{j}_{ts}.jpg"
            try:
                media.extract_frame(source, dest, ts)
            except media.MediaError:
                continue
            frame = Frame(
                video_id=video.id,
                segment_id=seg.id,
                timestamp_ms=ts,
                file_path=media.rel_path(dest),
                caption="",
                is_reference=(j == 1),
            )
            db.add(frame)
    db.flush()


def _caption_reference_frames(db: Session, video: Video) -> None:
    refs = (
        db.query(Frame)
        .filter(Frame.video_id == video.id, Frame.is_reference.is_(True))
        .all()
    )
    if not settings_mod.effective_key("vision") and not settings_mod.effective_key("text"):
        return
    for frame in refs[:24]:
        path = media.abs_path(frame.file_path)
        if not path.exists():
            continue
        caption = llm.caption_frame(_image_data_url(path))
        if caption:
            frame.caption = caption
    db.flush()


def _overview_frames(video: Video, count: int = 6) -> list[Path]:
    source = media.abs_path(video.file_path)
    duration = video.duration_ms or 1
    paths: list[Path] = []
    folder = media.frames_dir(video.id) / "overview"
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        ts = int(duration * (i + 1) / (count + 1))
        dest = folder / f"ov_{i}.jpg"
        try:
            media.extract_frame(source, dest, ts)
            paths.append(dest)
        except media.MediaError:
            continue
    return paths


def run_analyze_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return
        video = db.get(Video, job.video_id)
        if not video:
            _touch_job(db, job, status="error", error="找不到对应视频")
            return
        video.status = "analyzing"
        video.error_message = ""
        _touch_job(db, job, status="running", step="transcribe", progress=8, message="正在抽出音轨并转成文字…")

        source = media.abs_path(video.file_path)
        wav = media.video_dir(video.id) / "audio.wav"
        media.extract_audio_wav(source, wav)
        cues_data = asr.transcribe(wav)
        db.query(TranscriptCue).filter(TranscriptCue.video_id == video.id).delete()
        for row in cues_data:
            db.add(
                TranscriptCue(
                    video_id=video.id,
                    start_ms=row["start_ms"],
                    end_ms=row["end_ms"],
                    text=row["text"],
                    sort_order=row.get("sort_order") or 0,
                )
            )
        db.commit()
        cues = (
            db.query(TranscriptCue)
            .filter(TranscriptCue.video_id == video.id)
            .order_by(TranscriptCue.start_ms)
            .all()
        )

        _touch_job(db, job, step="analyze", progress=40, message="正在按主题分段并写亮点草稿…")
        blob = _transcript_blob(cues)
        segments_data: list[dict] = []
        fallback_note = ""
        try:
            image_urls: list[str] = []
            if settings_mod.effective_key("vision") or (
                settings_mod.load_settings().get("vision_model", "").find("vl") >= 0
                and settings_mod.effective_key("text")
            ):
                for p in _overview_frames(video, 6):
                    image_urls.append(_image_data_url(p))
            payload = llm.analyze_transcript(video.title, video.genre, blob, image_urls or None)
            segments_data = _normalize_llm_segments(payload, video.duration_ms)
        except llm.LlmError as exc:
            log.warning("LLM 分析失败，改用按时间切段：%s", exc)
            segments_data = _fallback_segments(video, cues)
            fallback_note = f"模型未写出拉片草稿（{exc}），已按时间切段，请在拉片台里手改。"

        if not segments_data:
            segments_data = _fallback_segments(video, cues)

        segs = _replace_analysis(db, video, segments_data)
        db.commit()

        _touch_job(db, job, step="frames", progress=75, message="正在抽出各段关键画面…")
        _extract_segment_frames(db, video, segs)
        db.commit()

        _touch_job(db, job, step="caption", progress=88, message="正在给参考图写画面说明…")
        try:
            _caption_reference_frames(db, video)
        except Exception:
            log.warning("画面说明失败，可稍后在拉片台查看无说明的帧")
        db.commit()

        video.status = "analyzed"
        video.updated_at = _now()
        _touch_job(
            db,
            job,
            status="done",
            step="done",
            progress=100,
            message=fallback_note or "拉片草稿已生成，请到拉片台校对。",
        )
    except Exception as exc:
        log.error("分析失败: %s\n%s", exc, traceback.format_exc())
        job = db.get(Job, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video:
            video.status = "error"
            video.error_message = str(exc)[:800]
        if job:
            _touch_job(db, job, status="error", error=str(exc)[:800], message="分析失败")
        else:
            db.commit()
    finally:
        db.close()


def run_download_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return
        video = db.get(Video, job.video_id)
        _touch_job(db, job, status="running", step="download", progress=15, message="正在从公开链接下载视频…")
        file_path = media.download_url(video.id, video.source_url)
        duration_ms, source, thumb = media.prepare_imported(video.id, file_path)
        video.file_path = media.rel_path(source)
        video.thumb_path = media.rel_path(thumb) if thumb and thumb.exists() else ""
        video.duration_ms = duration_ms
        if not video.title:
            video.title = Path(video.source_url).name or "未命名视频"
        video.status = "ready"
        video.error_message = ""
        _touch_job(db, job, status="done", step="done", progress=100, message="下载完成，可以开始拉片。")
    except Exception as exc:
        job = db.get(Job, job_id)
        video = db.get(Video, job.video_id) if job else None
        if video:
            video.status = "error"
            video.error_message = str(exc)[:800]
        if job:
            _touch_job(db, job, status="error", error=str(exc)[:800], message="下载失败")
        else:
            db.commit()
    finally:
        db.close()


def enqueue_job(db: Session, video_id: str, job_type: str) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        video_id=video_id,
        job_type=job_type,
        status="queued",
        progress=0,
        message="排队中…",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
