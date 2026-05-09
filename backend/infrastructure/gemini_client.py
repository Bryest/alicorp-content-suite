"""Gemini Vision adapter (gemini-2.5-flash multimodal). Audits image vs brand visual rules."""


import json
import logging
import re
from typing import Any

import google.generativeai as genai

from ..config import get_settings

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.google_api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY must be set. Configure it in environment "
                "variables before starting the API."
            )
        genai.configure(api_key=self.settings.google_api_key)
        self._model = genai.GenerativeModel(self.settings.gemini_vision_model)
        logger.info(f"GeminiClient: ready ({self.settings.gemini_vision_model})")

    async def audit_image(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        visual_rules: str,
        brand_name: str,
    ) -> dict[str, Any]:
        prompt = (
            f"Eres un auditor de cumplimiento de marca para {brand_name}. Analiza la imagen "
            "adjunta y evalúala contra las REGLAS VISUALES de abajo. Para cada regla, produce "
            "un check con passed (bool) y una nota corta EN ESPAÑOL explicando exactamente "
            "lo que observaste.\n\n"
            f"REGLAS VISUALES:\n{visual_rules}\n\n"
            "Responde ÚNICAMENTE con JSON válido en español, con esta forma exacta:\n"
            '{"compliant": <bool>, "checks": [{"rule": "...", "passed": <bool>, "note": "..."}], "summary": "..."}\n\n'
            "IMPORTANTE: TODOS los textos del JSON (rule, note, summary) deben estar en español."
        )
        resp = await self._model.generate_content_async(
            [
                prompt,
                {"mime_type": mime_type, "data": image_bytes},
            ]
        )
        text = (resp.text or "").strip()
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
        data = json.loads(text)
        return _normalize_audit(data)


def _normalize_audit(data: dict[str, Any]) -> dict[str, Any]:
    checks_raw = data.get("checks") or []
    checks = []
    for c in checks_raw:
        if not isinstance(c, dict):
            continue
        checks.append(
            {
                "rule": str(c.get("rule", "")),
                "passed": bool(c.get("passed", False)),
                "note": str(c.get("note", "")),
            }
        )
    compliant = bool(data.get("compliant"))
    if checks and not data.get("compliant"):
        compliant = all(c["passed"] for c in checks)
    return {
        "compliant": compliant,
        "checks": checks,
        "summary": str(data.get("summary", "")),
        "final_status": "approved" if compliant else "rejected",
    }
