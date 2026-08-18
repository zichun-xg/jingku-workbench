"""片库与拉片相关接口：导入、详情、开始分析、改段落/文案。"""
from __future__ import annotations

import json
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Highlight, Job, Segment, TranscriptCue, Video
from ..serialize import job_out, video_detail_out, video_list_out
from ..services import media
from ..services.pipeline import enqueue_job, run_analyze_job, run_download_job

router = APIRouter(prefix="/api/videos", tags=["videos"])

ALLOWED_GENRE = {"b2b_demo", "corp_promo", "other"}


def _video_or_404(db: Session, video_id: str) -> Video:
    video = (
        db.query(Video)
        .options(
            selectinload(Video.cues),
            selectinload(Video.segments).selectinload(Segment.frames),
            selectinload(Video.segments).selectinload(Segment.highlight).selectinload(Highlight.tags),
            selectinload(Video.jobs),
            selectinload(Video.highlights),
        )
        .filter(Video.id == video_id)
        .one_or_none()
    )
    if not video:
        raise HTTPException(404, "找不到这条视频")
    return video


@router.get("")
def list_videos(db: Session = Depends(get_db)):
    rows = db.query(Video).order_by(Video.created_at.desc()).all()
    return [video_list_out(v) for v in rows]


@router.get("/{video_id}")
def get_video(video_id: str, db: Session = Depends(get_db)):
    return video_detail_out(_video_or_404(db, video_id))


@router.post("/upload")
def upload_video(
    file: UploadFile = File(...),
    title: str = Form(""),
    genre: str = Form("b2b_demo"),
    db: Session = Depends(get_db),
):
    if genre not in ALLOWED_GENRE:
        genre = "other"
    video_id = str(uuid.uuid4())
    try:
        dest = media.save_upload(video_id, file.filename or "video.mp4", file.file)
        duration_ms, source, thumb = media.prepare_imported(video_id, dest)
    except media.MediaError as exc:
        raise HTTPException(400, str(exc)) from exc
    video = Video(
        id=video_id,
        title=title.strip() or (file.filename or "未命名视频"),
        source_type="local",
        file_path=media.rel_path(source),
        thumb_path=media.rel_path(thumb) if thumb and thumb.exists() else "",
        genre=genre,
        duration_ms=duration_ms,
        status="ready",
    )
    db.add(video)
    db.commit()
    return video_list_out(video)


@router.post("/from-url")
def import_from_url(payload: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    url = str(payload.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "请粘贴视频链接")
    genre = str(payload.get("genre") or "b2b_demo")
    if genre not in ALLOWED_GENRE:
        genre = "other"
    video_id = str(uuid.uuid4())
    video = Video(
        id=video_id,
        title=str(payload.get("title") or "").strip() or url,
        source_type="url",
        source_url=url,
        genre=genre,
        status="downloading",
    )
    db.add(video)
    db.commit()
    job = enqueue_job(db, video_id, "download")
    background_tasks.add_task(run_download_job, job.id)
    return {"video": video_list_out(video), "job": job_out(job)}


@router.patch("/{video_id}")
def update_video(video_id: str, payload: dict, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "找不到这条视频")
    if "title" in payload and payload["title"] is not None:
        video.title = str(payload["title"]).strip() or video.title
    if payload.get("genre") in ALLOWED_GENRE:
        video.genre = payload["genre"]
    db.commit()
    return video_list_out(video)


@router.delete("/{video_id}")
def delete_video(video_id: str, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "找不到这条视频")
    folder = media.video_dir(video_id)
    db.delete(video)
    db.commit()
    shutil.rmtree(folder, ignore_errors=True)
    return {"ok": True}


@router.post("/{video_id}/analyze")
def analyze_video(video_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "找不到这条视频")
    if video.status == "downloading":
        raise HTTPException(400, "还在下载，请稍后再拉片")
    if not video.file_path:
        raise HTTPException(400, "视频文件还没就绪")
    running = (
        db.query(Job)
        .filter(Job.video_id == video_id, Job.job_type == "analyze", Job.status.in_(["queued", "running"]))
        .first()
    )
    if running:
        return job_out(running)
    video.status = "analyzing"
    db.commit()
    job = enqueue_job(db, video_id, "analyze")
    background_tasks.add_task(run_analyze_job, job.id)
    return job_out(job)


@router.get("/{video_id}/jobs/{job_id}")
def get_job(video_id: str, job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.video_id != video_id:
        raise HTTPException(404, "找不到这个任务")
    return job_out(job)


@router.put("/{video_id}/cues/{cue_id}")
def update_cue(video_id: str, cue_id: int, payload: dict, db: Session = Depends(get_db)):
    cue = db.get(TranscriptCue, cue_id)
    if not cue or cue.video_id != video_id:
        raise HTTPException(404, "找不到这句文案")
    if "text" in payload and payload["text"] is not None:
        cue.text = str(payload["text"])
    if payload.get("start_ms") is not None:
        cue.start_ms = int(payload["start_ms"])
    if payload.get("end_ms") is not None:
        cue.end_ms = int(payload["end_ms"])
    db.commit()
    return {"ok": True}


@router.put("/{video_id}/segments/{segment_id}")
def update_segment(video_id: str, segment_id: int, payload: dict, db: Session = Depends(get_db)):
    seg = db.get(Segment, segment_id)
    if not seg or seg.video_id != video_id:
        raise HTTPException(404, "找不到这段")
    if payload.get("topic") is not None:
        seg.topic = str(payload["topic"])
    if payload.get("technique") is not None:
        seg.technique = str(payload["technique"])
    if payload.get("points") is not None:
        seg.points_json = json.dumps(payload["points"], ensure_ascii=False)
    if payload.get("start_ms") is not None:
        seg.start_ms = int(payload["start_ms"])
    if payload.get("end_ms") is not None:
        seg.end_ms = int(payload["end_ms"])
    db.commit()
    return {"ok": True}


@router.put("/{video_id}/highlights/{highlight_id}")
def update_highlight(video_id: str, highlight_id: int, payload: dict, db: Session = Depends(get_db)):
    from ..services.pipeline import _get_or_create_tag

    hl = db.get(Highlight, highlight_id)
    if not hl or hl.video_id != video_id:
        raise HTTPException(404, "找不到这张亮点卡")
    for field in ("title", "copy_advice", "visual_advice", "audience"):
        if field in payload and payload[field] is not None:
            setattr(hl, field, str(payload[field]))
    if payload.get("in_library") is not None:
        hl.in_library = bool(payload["in_library"])
    if payload.get("tags") is not None:
        names = [str(n).strip() for n in payload["tags"] if str(n).strip()]
        hl.tags = [_get_or_create_tag(db, n) for n in names]
    db.commit()
    return {"ok": True}
