"""语音转文字：优先本地 Whisper；国内网络被拦截时自动改走通义转写。"""
from __future__ import annotations

import base64
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

from . import media
from . import settings as settings_mod

log = logging.getLogger("jingku.asr")

_whisper_model = None
_whisper_name = None

DASHSCOPE_ASR_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
# 通义 Flash 单段不超过 5 分钟 / 10MB，这里按 3 分钟切片更稳
DASHSCOPE_CHUNK_MS = 180_000


class AsrError(RuntimeError):
    pass


def transcribe(audio_path: Path) -> list[dict[str, Any]]:
    """返回 [{start_ms, end_ms, text}]。"""
    cfg = settings_mod.load_settings()
    provider = cfg.get("asr_provider") or "whisper"
    if provider == "openai_compatible":
        return _transcribe_openai(audio_path, cfg)
    if provider == "dashscope":
        return _transcribe_dashscope(audio_path)
    try:
        return _transcribe_whisper(audio_path, cfg)
    except AsrError:
        raise
    except Exception as exc:
        if _can_use_dashscope() and _is_download_block(exc):
            log.warning("本地 Whisper 模型下载被拦截（%s），改用通义转写", exc)
            return _transcribe_dashscope(audio_path)
        raise AsrError(f"本地转写失败：{exc}") from exc


def _can_use_dashscope() -> bool:
    return bool(settings_mod.effective_key("text") or settings_mod.effective_key("asr"))


def _is_download_block(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    needles = ("403", "proxy", "forbidden", "huggingface", "connection", "timeout", "connecterror")
    return any(n in text for n in needles)


def _transcribe_whisper(audio_path: Path, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    global _whisper_model, _whisper_name
    model_name = str(cfg.get("asr_model") or "small")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise AsrError(
            f"本地转写组件加载失败：{exc}。请在项目目录执行 "
            f".venv/bin/pip install -r backend/requirements.txt"
        ) from exc

    if _whisper_model is None or _whisper_name != model_name:
        _whisper_model = _load_whisper_model(WhisperModel, model_name)
        _whisper_name = model_name

    segments, _info = _whisper_model.transcribe(
        str(audio_path),
        language="zh",
        vad_filter=True,
        beam_size=5,
    )
    cues: list[dict[str, Any]] = []
    for i, seg in enumerate(segments):
        text = (seg.text or "").strip()
        if not text:
            continue
        cues.append(
            {
                "start_ms": int(seg.start * 1000),
                "end_ms": int(seg.end * 1000),
                "text": text,
                "sort_order": i,
            }
        )
    if not cues:
        raise AsrError("转写结果是空的，可能视频没有人声，或音轨无法识别")
    return cues


def _load_whisper_model(WhisperModel, model_name: str):
    """国内访问 HuggingFace 常被代理 403，下载时改走镜像并临时去掉代理。"""
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    saved = {k: os.environ.pop(k, None) for k in proxy_keys}
    try:
        return WhisperModel(model_name, device="auto", compute_type="int8")
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def _transcribe_dashscope(audio_path: Path) -> list[dict[str, Any]]:
    key = settings_mod.effective_key("asr") or settings_mod.effective_key("text")
    if not key:
        raise AsrError("通义转写需要在设置里填写百炼 API Key")
    duration_ms = media.probe_duration_ms(audio_path) or 0
    if duration_ms <= 0:
        duration_ms = DASHSCOPE_CHUNK_MS
    cues: list[dict[str, Any]] = []
    order = 0
    start = 0
    while start < duration_ms:
        length = min(DASHSCOPE_CHUNK_MS, duration_ms - start)
        chunk = audio_path.parent / f"asr_chunk_{start}.mp3"
        media.extract_audio_segment_mp3(audio_path, chunk, start / 1000, length / 1000)
        text, sentences = _dashscope_recognize(chunk, key)
        if sentences:
            for sent in sentences:
                piece = str(sent.get("text") or "").strip()
                if not piece:
                    continue
                cues.append(
                    {
                        "start_ms": start + int(sent.get("begin_time") or 0),
                        "end_ms": start + int(sent.get("end_time") or 0),
                        "text": piece,
                        "sort_order": order,
                    }
                )
                order += 1
        elif text:
            for item in _split_text_over_time(text, start, start + length):
                item["sort_order"] = order
                cues.append(item)
                order += 1
        start += length
    if not cues:
        raise AsrError("通义转写没有识别出文字，可能视频没有人声")
    return cues


def _dashscope_recognize(mp3_path: Path, key: str) -> tuple[str, list[dict[str, Any]]]:
    raw = mp3_path.read_bytes()
    data_uri = "data:audio/mpeg;base64," + base64.b64encode(raw).decode("ascii")
    payload = {
        "model": "qwen3-asr-flash",
        "input": {
            "messages": [
                {"role": "user", "content": [{"audio": data_uri}]},
            ]
        },
        "parameters": {
            "asr_options": {"language": "zh", "enable_itn": True},
        },
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(DASHSCOPE_ASR_URL, headers=headers, json=payload, timeout=180)
    except httpx.HTTPError as exc:
        raise AsrError(f"通义转写请求失败：{exc}") from exc
    if resp.status_code >= 400:
        raise AsrError(f"通义转写接口报错 {resp.status_code}：{resp.text[:400]}")
    body = resp.json()
    if body.get("code") and str(body.get("code")) not in {"", "Success", "null"}:
        raise AsrError(f"通义转写失败：{body.get('message') or body.get('code')}")
    return _parse_dashscope_asr(body)


def _parse_dashscope_asr(body: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    output = body.get("output") or {}
    sentences: list[dict[str, Any]] = []
    for tr in output.get("transcripts") or []:
        sentences.extend(tr.get("sentences") or [])
    if not sentences and output.get("sentences"):
        sentences = list(output.get("sentences") or [])
    text = ""
    choices = output.get("choices") or []
    if choices:
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            text = "".join(str(x.get("text") or "") for x in content if isinstance(x, dict)).strip()
        elif isinstance(content, str):
            text = content.strip()
    if not text:
        text = str(output.get("text") or "").strip()
    if not text and sentences:
        text = "".join(str(s.get("text") or "") for s in sentences).strip()
    return text, sentences


def _split_text_over_time(text: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
    parts = [p.strip() for p in re.split(r"(?<=[。！？；!?\n])", text) if p.strip()]
    if not parts:
        parts = [text.strip()]
    total = sum(len(p) for p in parts) or 1
    span = max(1, end_ms - start_ms)
    out: list[dict[str, Any]] = []
    cursor = start_ms
    for i, part in enumerate(parts):
        dur = int(span * len(part) / total)
        finish = end_ms if i == len(parts) - 1 else cursor + max(800, dur)
        out.append({"start_ms": cursor, "end_ms": finish, "text": part, "sort_order": 0})
        cursor = finish
    return out


def _transcribe_openai(audio_path: Path, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    key = settings_mod.effective_key("asr")
    base = str(cfg.get("asr_base_url") or "").rstrip("/")
    model = str(cfg.get("asr_model") or "whisper-1")
    if not key or not base:
        raise AsrError("云端转写需要填写接口地址和 Key")
    url = base + "/audio/transcriptions"
    with audio_path.open("rb") as fh:
        files = {"file": (audio_path.name, fh, "audio/wav")}
        data = {"model": model, "language": "zh", "response_format": "verbose_json"}
        headers = {"Authorization": f"Bearer {key}"}
        try:
            resp = httpx.post(url, headers=headers, data=data, files=files, timeout=300)
        except httpx.HTTPError as exc:
            raise AsrError(f"转写请求失败：{exc}") from exc
    if resp.status_code >= 400:
        raise AsrError(f"转写接口报错 {resp.status_code}：{resp.text[:400]}")
    payload = resp.json()
    cues: list[dict[str, Any]] = []
    for i, seg in enumerate(payload.get("segments") or []):
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        cues.append(
            {
                "start_ms": int(float(seg.get("start") or 0) * 1000),
                "end_ms": int(float(seg.get("end") or 0) * 1000),
                "text": text,
                "sort_order": i,
            }
        )
    if not cues and payload.get("text"):
        cues.append(
            {
                "start_ms": 0,
                "end_ms": 0,
                "text": str(payload["text"]).strip(),
                "sort_order": 0,
            }
        )
    if not cues:
        raise AsrError("云端转写没有返回带时间轴的句子")
    return cues
