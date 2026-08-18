"""媒体处理：探测时长、抽封面、抽音频、抽关键帧、公开链接下载。"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..config import DATA_DIR, VIDEOS_DIR


class MediaError(RuntimeError):
    pass


def video_dir(video_id: str) -> Path:
    path = VIDEOS_DIR / video_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def frames_dir(video_id: str) -> Path:
    path = video_dir(video_id) / "frames"
    path.mkdir(parents=True, exist_ok=True)
    return path


def abs_path(relative: str) -> Path:
    return DATA_DIR / relative


def rel_path(path: Path) -> str:
    return str(path.resolve().relative_to(DATA_DIR.resolve()))


def _run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise MediaError("找不到 ffmpeg/ffprobe，请确认本机已安装") from exc
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise MediaError(err[:800] or "ffmpeg 执行失败")
    return (result.stdout or "").strip()


def probe_duration_ms(file_path: Path) -> int:
    out = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(file_path),
        ]
    )
    try:
        return int(float(out) * 1000)
    except ValueError:
        return 0


def extract_thumbnail(file_path: Path, dest: Path, at_ms: int = 3000) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ss = max(0, at_ms) / 1000
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{ss:.2f}",
            "-i",
            str(file_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(dest),
        ]
    )


def extract_audio_wav(file_path: Path, dest: Path) -> None:
    """抽出 16k 单声道 wav，给 Whisper 转写用。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(file_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(dest),
        ]
    )


def extract_audio_segment_mp3(file_path: Path, dest: Path, start_s: float, duration_s: float) -> None:
    """切出一小段 mp3，给通义转写用（单段约 3 分钟，避免超过 10MB 限制）。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{max(0.0, start_s):.2f}",
            "-t",
            f"{max(0.1, duration_s):.2f}",
            "-i",
            str(file_path),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-b:a",
            "64k",
            str(dest),
        ]
    )


def extract_frame(file_path: Path, dest: Path, at_ms: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ss = max(0, at_ms) / 1000
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{ss:.2f}",
            "-i",
            str(file_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=960:-2",
            "-q:v",
            "3",
            str(dest),
        ]
    )


def save_upload(video_id: str, src_name: str, chunks) -> Path:
    suffix = Path(src_name).suffix.lower() or ".mp4"
    dest = video_dir(video_id) / f"source{suffix}"
    with dest.open("wb") as out:
        shutil.copyfileobj(chunks, out)
    return dest


def copy_local_file(video_id: str, src: Path) -> Path:
    suffix = src.suffix.lower() or ".mp4"
    dest = video_dir(video_id) / f"source{suffix}"
    shutil.copy2(src, dest)
    return dest


def download_url(video_id: str, url: str) -> Path:
    """用 yt-dlp 下载公开链接，合并成 mp4。"""
    dest_tmpl = str(video_dir(video_id) / "source.%(ext)s")
    try:
        import yt_dlp
    except ImportError as exc:
        raise MediaError("未安装 yt-dlp，无法从链接下载") from exc

    opts = {
        "outtmpl": dest_tmpl,
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        raise MediaError(f"下载失败：{exc}") from exc

    folder = video_dir(video_id)
    candidates = list(folder.glob("source.*"))
    if not candidates:
        raise MediaError("下载完成但没有找到视频文件")
    # 优先 mp4
    for item in candidates:
        if item.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}:
            return item
    return candidates[0]


def prepare_imported(video_id: str, file_path: Path) -> tuple[int, Path, Path]:
    """探测时长、抽封面，返回 duration_ms, source, thumb。"""
    duration_ms = probe_duration_ms(file_path)
    thumb = video_dir(video_id) / "thumb.jpg"
    try:
        extract_thumbnail(file_path, thumb, at_ms=min(3000, max(0, duration_ms // 5)))
    except MediaError:
        thumb = Path()
    return duration_ms, file_path, thumb
