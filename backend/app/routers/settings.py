"""设置页接口：读取/保存模型配置，不把完整 Key 回传给前端。"""
from __future__ import annotations

from fastapi import APIRouter

from ..schemas import SettingsIn
from ..services.settings import public_settings, save_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings():
    return public_settings()


@router.put("")
def put_settings(payload: SettingsIn):
    save_settings(payload)
    return public_settings()
