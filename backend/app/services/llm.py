"""调用 OpenAI 兼容接口：写亮点的文本模型、看画面的视觉模型。"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from . import settings as settings_mod
from .prompts import FRAME_CAPTION_PROMPT, analysis_system_prompt, analysis_user_prompt


class LlmError(RuntimeError):
    pass


def _chat(base_url: str, api_key: str, model: str, messages: list[dict[str, Any]], timeout: int = 180) -> str:
    if not base_url or not api_key:
        raise LlmError("还没有配置模型 Key，请到「设置」里填写")
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": 0.4}
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    except httpx.HTTPError as exc:
        raise LlmError(f"模型请求失败：{exc}") from exc
    if resp.status_code >= 400:
        raise LlmError(f"模型接口报错 {resp.status_code}：{resp.text[:500]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError(f"模型返回格式不对：{data}") from exc


def parse_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            raw = match.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0:
        raise LlmError("模型没有返回 JSON")
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LlmError(f"无法解析模型 JSON：{exc}") from exc


def analyze_transcript(
    title: str,
    genre: str,
    transcript: str,
    image_data_urls: list[str] | None = None,
) -> dict[str, Any]:
    cfg = settings_mod.load_settings()
    use_vision = bool(image_data_urls) and bool(settings_mod.effective_key("vision") or settings_mod.effective_key("text"))
    system = analysis_system_prompt(genre)
    user_text = analysis_user_prompt(title, genre, transcript)
    if use_vision:
        content: list[dict[str, Any]] = [{"type": "text", "text": user_text + "\n\n下面附上若干关键帧，请结合画面写制作手法和画面建议。"}]
        for url in image_data_urls[:8]:
            content.append({"type": "image_url", "image_url": {"url": url}})
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ]
        key = settings_mod.effective_key("vision") or settings_mod.effective_key("text")
        text = _chat(cfg["vision_base_url"], key, cfg["vision_model"], messages, timeout=240)
    else:
        key = settings_mod.effective_key("text")
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ]
        text = _chat(cfg["text_base_url"], key, cfg["text_model"], messages, timeout=180)
    return parse_json_object(text)


def caption_frame(image_data_url: str) -> str:
    cfg = settings_mod.load_settings()
    key = settings_mod.effective_key("vision") or settings_mod.effective_key("text")
    if not key:
        return ""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": FRAME_CAPTION_PROMPT},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        }
    ]
    try:
        return _chat(cfg["vision_base_url"] or cfg["text_base_url"], key, cfg["vision_model"] or cfg["text_model"], messages, timeout=60).strip()
    except LlmError:
        return ""
