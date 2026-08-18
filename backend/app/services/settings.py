"""本地设置：转写 / 看画面 / 写亮点 可分别填不同模型的 Key。"""
from __future__ import annotations

import json
from typing import Any

from ..config import SETTINGS_PATH, ensure_dirs
from ..schemas import SettingsIn

DEFAULTS: dict[str, Any] = {
    "asr_provider": "whisper",
    "asr_model": "small",
    "asr_api_key": "",
    "asr_base_url": "",
    "text_provider": "openai_compatible",
    "text_model": "qwen-plus",
    "text_api_key": "",
    "text_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "vision_provider": "openai_compatible",
    "vision_model": "qwen-vl-plus",
    "vision_api_key": "",
    "vision_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "use_same_key": True,
}

PRESETS = [
    {
        "id": "dashscope",
        "label": "阿里云百炼（通义，推荐）",
        "hint": "一个 Key 可同时用于转写、写亮点和看画面。国内网络访问 HuggingFace 容易被拦截，转写建议走通义。",
        "text_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "text_model": "qwen-plus",
        "vision_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "vision_model": "qwen-vl-plus",
    },
    {
        "id": "volcengine",
        "label": "豆包 / 火山方舟",
        "hint": "在方舟控制台创建推理接入点后，把接入点 ID 填到模型名。",
        "text_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "text_model": "doubao-seed-1-6-250615",
        "vision_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "vision_model": "doubao-seed-1-6-250615",
    },
    {
        "id": "deepseek",
        "label": "DeepSeek（只负责写亮点）",
        "hint": "便宜、长文案稳。看画面请另配通义或豆包视觉模型。",
        "text_base_url": "https://api.deepseek.com",
        "text_model": "deepseek-chat",
        "vision_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "vision_model": "qwen-vl-plus",
    },
]


def load_settings() -> dict[str, Any]:
    ensure_dirs()
    if not SETTINGS_PATH.exists():
        return dict(DEFAULTS)
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    return merged


def save_settings(payload: SettingsIn | dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    current = load_settings()
    if isinstance(payload, SettingsIn):
        incoming = payload.model_dump()
    else:
        incoming = {k: v for k, v in payload.items() if k in DEFAULTS}
    data = dict(current)
    for key, value in incoming.items():
        if key.endswith("_api_key") and value == "":
            continue  # 前端留空表示不改已保存的 Key
        data[key] = value
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def public_settings() -> dict[str, Any]:
    """返回给前端的设置：Key 只暴露是否已填写，避免在界面回显完整密钥。"""
    data = load_settings()
    out = dict(data)
    for key in ("asr_api_key", "text_api_key", "vision_api_key"):
        secret = str(out.get(key) or "")
        out[key + "_set"] = bool(secret)
        out[key] = ""
    out["presets"] = PRESETS
    return out


def effective_key(role: str) -> str:
    """取某个任务实际使用的 Key。勾选「同一把 Key」时，云端任务共用文本模型的 Key。"""
    s = load_settings()
    if role == "asr":
        return str(s.get("asr_api_key") or "")
    text_key = str(s.get("text_api_key") or "")
    if s.get("use_same_key"):
        if role == "vision":
            return str(s.get("vision_api_key") or text_key)
        return text_key
    if role == "vision":
        return str(s.get("vision_api_key") or "")
    return text_key
