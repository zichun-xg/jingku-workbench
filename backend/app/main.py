"""镜库后端入口：本地接口服务 + 素材文件访问。"""
from __future__ import annotations

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import DATA_DIR, ensure_dirs
from .db import init_db
from .routers import library as library_router
from .routers import settings as settings_router
from .routers.videos import router as videos_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="镜库", description="视频拉片与灵感库工作台")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(videos_router)
app.include_router(library_router.router)
app.include_router(settings_router.router)


@app.on_event("startup")
def on_startup() -> None:
    ensure_dirs()
    init_db()
    _seed_tags()


def _seed_tags() -> None:
    from .db import SessionLocal
    from .models import Tag

    names = [
        "痛点开场",
        "政策卡点",
        "穿透式监管",
        "数据金句",
        "场景对位",
        "产品演示",
        "界面特写",
        "前后对比",
        "分屏对比",
        "字幕强调",
        "行动号召",
        "开场钩子",
        "空镜意境",
        "领导出镜",
        "员工故事",
        "品牌升华",
        "片尾记忆点",
        "客户口播",
    ]
    db = SessionLocal()
    try:
        existing = {t.name for t in db.query(Tag).all()}
        for name in names:
            if name not in existing:
                db.add(Tag(name=name, category="technique"))
        db.commit()
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"ok": True, "name": "jingku"}


@app.get("/media/{path:path}")
def media_file(path: str):
    """按 Range 返回本地视频/图片，供播放器和参考图使用。"""
    full = (DATA_DIR / path).resolve()
    root = DATA_DIR.resolve()
    if root not in full.parents and full != root:
        raise HTTPException(403, "不允许访问该路径")
    if not full.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(full)
