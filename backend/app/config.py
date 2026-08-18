"""路径与运行配置。所有素材默认只存在本机 data/（本地素材库目录）。"""
from __future__ import annotations

from pathlib import Path

# 项目根目录（Video/）
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
VIDEOS_DIR = DATA_DIR / "videos"
DB_PATH = DATA_DIR / "jingku.db"
SETTINGS_PATH = DATA_DIR / "settings.json"

API_HOST = "127.0.0.1"
API_PORT = 8765


def ensure_dirs() -> None:
    """启动时创建本地素材目录，避免第一次导入失败。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
