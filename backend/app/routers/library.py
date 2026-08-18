"""灵感库：跨视频筛选亮点，按标签 / 片种 / 受众查找。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Highlight, Segment, Tag, Video
from ..serialize import highlight_out, tag_out

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/tags")
def list_tags(db: Session = Depends(get_db)):
    rows = db.query(Tag).order_by(Tag.name.asc()).all()
    return [tag_out(t) for t in rows]


@router.get("/highlights")
def list_highlights(
    tag: str = "",
    genre: str = "",
    audience: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    query = (
        db.query(Highlight)
        .join(Video, Highlight.video_id == Video.id)
        .options(
            selectinload(Highlight.tags),
            selectinload(Highlight.video),
            selectinload(Highlight.segment).selectinload(Segment.frames),
        )
        .filter(Highlight.in_library.is_(True))
    )
    if tag:
        query = query.join(Highlight.tags).filter(Tag.name == tag)
    if genre:
        query = query.filter(Video.genre == genre)
    if audience:
        query = query.filter(Highlight.audience.contains(audience))
    if q:
        query = query.filter(
            or_(
                Highlight.title.contains(q),
                Highlight.copy_advice.contains(q),
                Highlight.visual_advice.contains(q),
                Highlight.audience.contains(q),
                Video.title.contains(q),
            )
        )
    rows = query.distinct().order_by(Highlight.updated_at.desc()).all()
    result = []
    for hl in rows:
        frames = []
        if hl.segment:
            frames = [f for f in hl.segment.frames if f.is_reference] or list(hl.segment.frames or [])[:2]
        result.append(highlight_out(hl, hl.video, frames))
    return result
