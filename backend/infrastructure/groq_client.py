"""Groq adapter (Llama 3.3 70B). JSON-mode forced for both calls."""


import json
import logging
from typing import Any

from groq import AsyncGroq

from ..config import get_settings
from ..domain.brand import BrandSection

logger = logging.getLogger(__name__)


class GroqClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY must be set. Configure it in environment "
                "variables before starting the API."
            )
        self._client = AsyncGroq(api_key=self.settings.groq_api_key)
        logger.info(f"GroqClient: ready ({self.settings.groq_model})")

    # ─────────────────────────────────────────────────────────────────
    # Module I — generate the structured brand manual
    # ─────────────────────────────────────────────────────────────────
    async def generate_brand_manual(self, payload: dict[str, Any]) -> dict[str, str]:
        """Returns a dict keyed by BrandSection → string content."""
        system = (
            "You are a senior brand strategist. Given the inputs, produce a structured "
            "brand manual with exactly these five sections: TONE, AUDIENCE, FORBIDDEN, "
            "VISUAL, MESSAGING. Each section is one paragraph (40–80 words), concrete "
            "and enforceable. Output ONLY valid JSON of shape "
            '{"TONE":"...","AUDIENCE":"...","FORBIDDEN":"...","VISUAL":"...","MESSAGING":"..."}'
        )
        user = (
            "Inputs:\n"
            f"- Brand name: {payload.get('name')}\n"
            f"- Product type: {payload.get('product_type')}\n"
            f"- Tone: {payload.get('tone')}\n"
            f"- Audience: {payload.get('audience')}\n"
            f"- Visual rules: {payload.get('visual_rules')}\n"
            f"- Forbidden words: {payload.get('forbidden_words')}\n"
            f"- Key messages: {payload.get('key_messages')}\n"
        )
        resp = await self._client.chat.completions.create(
            model=self.settings.groq_model,
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        return {k: str(v) for k, v in data.items() if k in {s.value for s in BrandSection}}

    # ─────────────────────────────────────────────────────────────────
    # Module II — RAG-grounded content generation
    # ─────────────────────────────────────────────────────────────────
    async def generate_content(
        self,
        *,
        brand_name: str,
        content_type: str,
        request: str,
        retrieved_context: list[tuple[str, str]],  # [(section, content)]
        forbidden_words: list[str],
    ) -> dict[str, Any]:
        """
        Returns:
          {"content": str | None, "conflicts": [{"rule","violation","suggestion"}, ...]}
        """
        ctx_block = "\n\n".join(f"[{s}]\n{c}" for s, c in retrieved_context) or "(no context)"
        system = (
            f"You are a brand copywriter for {brand_name}. The CRITICAL RULES below are "
            "non-negotiable; if the user request would force a violation, do NOT generate "
            "content — return {\"content\": null, \"conflicts\": [...]} explaining each rule "
            "violated and a constructive suggestion.\n\n"
            f"CRITICAL RULES (retrieved from the brand manual):\n{ctx_block}\n\n"
            f"FORBIDDEN WORDS (case-insensitive, never use any): {forbidden_words}\n\n"
            "Output ONLY valid JSON of shape:\n"
            '{"content": "<string or null>", "conflicts": [{"rule":"...","violation":"...","suggestion":"..."}]}'
        )
        resp = await self._client.chat.completions.create(
            model=self.settings.groq_model,
            temperature=self.settings.llm_temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Content type: {content_type}\nRequest: {request}"},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        return _normalize_generation(data)


def _normalize_generation(data: dict[str, Any]) -> dict[str, Any]:
    content = data.get("content")
    if content is not None and not isinstance(content, str):
        content = str(content)
    raw_conflicts = data.get("conflicts") or []
    conflicts = []
    for c in raw_conflicts:
        if not isinstance(c, dict):
            continue
        conflicts.append(
            {
                "rule": str(c.get("rule", "")),
                "violation": str(c.get("violation", "")),
                "suggestion": str(c.get("suggestion", "")),
            }
        )
    return {"content": content, "conflicts": conflicts}
