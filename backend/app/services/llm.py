from __future__ import annotations

import json
import logging
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from google.generativeai import types as genai_types

from ..config import get_settings

logger = logging.getLogger(__name__)

_GEMINI_CLIENT: "GeminiClient | None" = None
_GEMINI_VISION_CLIENT: "GeminiVisionClient | None" = None

_SYSTEM_PROMPT = (
    "You are a helpful digital forensics analyst. Given structured evidence snippets, "
    "answer the investigator's question. Cite evidence by referencing the provided "
    "evidence identifiers in square brackets (e.g., [msg:messages.sqlite:message:42]). "
    "If the evidence is insufficient, say so explicitly and suggest next steps."
)

_VISION_SYSTEM_PROMPT = (
    "You analyze digital evidence images for investigators. Keep descriptions concise, "
    "objective, and forensically appropriate."
)


@dataclass
class ImageDescription:
    caption: str
    tags: List[str]
    detected_text: Optional[str] = None


class GeminiClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings

        if not settings.gemini_api_key:
            raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY in the environment.")

        genai.configure(api_key=settings.gemini_api_key)
        model_name = _normalize_model_name(settings.gemini_model_name)

        self._model_name = model_name
        self._model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=_SYSTEM_PROMPT,
        )
        self._generation_config = genai_types.GenerationConfig(
            temperature=settings.gemini_temperature,
            top_p=settings.gemini_top_p,
            max_output_tokens=settings.gemini_max_output_tokens,
        )

    def model_name(self) -> str:
        return self._model_name

    def generate_answer(
        self,
        *,
        question: str,
        context_sections: Sequence[str],
        conversation: Iterable[Tuple[str, str]] | None = None,
    ) -> str:
        contents: List[genai_types.ContentDict] = []

        if conversation:
            for role, message in conversation:
                genai_role = "model" if role.lower() in {"assistant", "model"} else "user"
                contents.append({"role": genai_role, "parts": [{"text": message}]})

        context_block = "\n\n".join(context_sections) if context_sections else "No additional context provided."
        user_prompt = (
            "Context:\n"
            f"{context_block}\n\n"
            f"Question: {question}\n\n"
            "Respond clearly and reference evidence IDs in square brackets when applicable."
        )
        contents.append({"role": "user", "parts": [{"text": user_prompt}]})

        last_error: Exception | None = None
        for attempt in range(1, self._settings.gemini_retry_attempts + 1):
            try:
                response = self._model.generate_content(
                    contents,
                    generation_config=self._generation_config,
                )
                if response and response.text:
                    return response.text.strip()
                last_error = RuntimeError("Gemini returned an empty response.")
            except (GoogleAPIError, ValueError) as exc:  # pragma: no cover - network dependent
                last_error = exc
                logger.warning(
                    "Gemini request failed (attempt %s/%s): %s",
                    attempt,
                    self._settings.gemini_retry_attempts,
                    exc,
                )
        raise RuntimeError(f"Gemini request failed: {last_error}")


class GeminiVisionClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings

        if not settings.gemini_api_key:
            raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY in the environment.")

        genai.configure(api_key=settings.gemini_api_key)
        model_name = _normalize_model_name(settings.gemini_vision_model_name)

        self._model_name = model_name
        self._model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=_VISION_SYSTEM_PROMPT,
        )
        self._generation_config = genai_types.GenerationConfig(
            temperature=settings.gemini_vision_temperature,
            top_p=settings.gemini_vision_top_p,
            max_output_tokens=settings.gemini_vision_max_output_tokens,
        )

    def model_name(self) -> str:
        return self._model_name

    def describe_image(self, image_path: Path) -> ImageDescription:
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        mime_type, _ = mimetypes.guess_type(str(image_path))
        if mime_type is None:
            if image_path.suffix.lower() in {".heic", ".heif"}:
                mime_type = "image/heic"
            else:
                mime_type = "image/jpeg"

        image_bytes = image_path.read_bytes()

        user_prompt = (
            "Provide a JSON object with keys caption (<=40 word string), tags (array of up to 6 short "
            "descriptive strings), and detected_text (string of any prominent on-image text or null)."
        )

        contents = [
            {
                "role": "user",
                "parts": [
                    {"text": user_prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_bytes}},
                ],
            }
        ]

        last_error: Exception | None = None
        for attempt in range(1, self._settings.gemini_retry_attempts + 1):
            try:
                response = self._model.generate_content(
                    contents,
                    generation_config=self._generation_config,
                )
                if not response or not response.text:
                    last_error = RuntimeError("Gemini Vision returned an empty response.")
                    continue
                payload = _parse_structured_json(response.text)
                caption = payload.get("caption") or payload.get("description")
                if not caption:
                    raise ValueError("Caption missing from Gemini Vision response")
                tags_raw = payload.get("tags")
                tags = _normalize_tags(tags_raw)
                detected_text_value = payload.get("detected_text") or payload.get("ocr")
                if isinstance(detected_text_value, list):
                    detected_text = " ".join(str(part).strip() for part in detected_text_value if str(part).strip()) or None
                else:
                    detected_text = detected_text_value if detected_text_value else None
                return ImageDescription(caption=caption.strip(), tags=tags, detected_text=detected_text)
            except (GoogleAPIError, ValueError, json.JSONDecodeError) as exc:  # pragma: no cover - network dependent
                last_error = exc
                logger.warning(
                    "Gemini Vision request failed (attempt %s/%s): %s",
                    attempt,
                    self._settings.gemini_retry_attempts,
                    exc,
                )

        raise RuntimeError(f"Gemini Vision request failed: {last_error}")


def get_gemini_client() -> GeminiClient:
    global _GEMINI_CLIENT
    settings = get_settings()
    target_model = _normalize_model_name(settings.gemini_model_name)
    if _GEMINI_CLIENT is None or _GEMINI_CLIENT.model_name() != target_model:
        _GEMINI_CLIENT = GeminiClient()
    return _GEMINI_CLIENT


def get_gemini_vision_client() -> GeminiVisionClient:
    global _GEMINI_VISION_CLIENT
    settings = get_settings()
    target_model = _normalize_model_name(settings.gemini_vision_model_name)
    if _GEMINI_VISION_CLIENT is None or _GEMINI_VISION_CLIENT.model_name() != target_model:
        _GEMINI_VISION_CLIENT = GeminiVisionClient()
    return _GEMINI_VISION_CLIENT


def _normalize_model_name(model_name: str | None) -> str:
    if not model_name:
        raise ValueError("Gemini model name is not configured")

    normalized = model_name.strip()
    if not normalized:
        raise ValueError("Gemini model name is blank")

    if not normalized.startswith("models/"):
        normalized = f"models/{normalized}"

    lower_name = normalized.lower()
    if lower_name.startswith("models/models/"):
        normalized = normalized[7:]
        lower_name = normalized.lower()

    legacy_patterns = (
        "models/gemini-1.5-flash",
        "models/gemini-1.5-pro",
        "models/gemini-1.5-pro-vision",
        "models/gemini-pro-vision",
    )
    if any(lower_name == pattern for pattern in legacy_patterns) and not lower_name.endswith("-latest"):
        normalized = f"{normalized}-latest"

    return normalized


def _parse_structured_json(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    if not text:
        raise ValueError("Gemini response was empty")

    if text.startswith("```"):
        newline_index = text.find("\n")
        if newline_index != -1:
            text = text[newline_index + 1 :]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start == -1 or brace_end == -1 or brace_end <= brace_start:
        raise ValueError("No JSON object found in Gemini response")

    json_blob = text[brace_start : brace_end + 1]
    return json.loads(json_blob)


def _normalize_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,\n]\s*", value)
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, (list, tuple, set)):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized
    return [str(value).strip()]
