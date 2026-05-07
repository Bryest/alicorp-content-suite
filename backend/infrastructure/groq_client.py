"""
Groq LLM adapter.

REAL mode: Llama 3.3 70B via groq.AsyncGroq, JSON-mode forced.
MOCK mode: handcrafted brand-aware JSON responses.

Two responsibilities:
  * generate_brand_manual(payload)  → structured 5-section manual
  * generate_content(...)           → brand-consistent copy + conflict detection

The MOCK responses are intentionally good enough to demo the full RAG +
governance flow end-to-end without keys: they read the brand context,
detect forbidden-word violations, and respect tone hints.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from ..config import get_settings
from ..domain.brand import BrandSection

logger = logging.getLogger(__name__)


class GroqClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        if not self.settings.groq_mocked:
            try:
                from groq import AsyncGroq

                self._client = AsyncGroq(api_key=self.settings.groq_api_key)
                logger.info(f"GroqClient: REAL mode ({self.settings.groq_model})")
            except Exception as e:  # pragma: no cover
                logger.warning(f"GroqClient: init failed ({e}). Falling back to mock.")
                self._client = None
        if self._client is None:
            logger.info("GroqClient: MOCK mode")

    @property
    def is_mocked(self) -> bool:
        return self._client is None

    # ─────────────────────────────────────────────────────────────────
    # Module I — generate the structured brand manual
    # ─────────────────────────────────────────────────────────────────
    async def generate_brand_manual(self, payload: dict[str, Any]) -> dict[str, str]:
        """
        Returns a dict keyed by BrandSection → string content.
        """
        if self._client is None:
            return _mock_brand_manual(payload)

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
        try:
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
        except Exception as e:
            logger.warning(f"GroqClient.generate_brand_manual failed: {e}. Falling back to mock.")
            return _mock_brand_manual(payload)

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
        if self._client is None:
            return _mock_generate_content(
                brand_name=brand_name,
                content_type=content_type,
                request=request,
                retrieved_context=retrieved_context,
                forbidden_words=forbidden_words,
            )

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
        try:
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
        except Exception as e:
            logger.warning(f"GroqClient.generate_content failed: {e}. Falling back to mock.")
            return _mock_generate_content(
                brand_name=brand_name,
                content_type=content_type,
                request=request,
                retrieved_context=retrieved_context,
                forbidden_words=forbidden_words,
            )


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


# ─────────────────────────────────────────────────────────────────────
# Mock helpers — intentionally good enough to demo end-to-end
# ─────────────────────────────────────────────────────────────────────
def _mock_brand_manual(payload: dict[str, Any]) -> dict[str, str]:
    name = payload.get("name", "Brand")
    product = payload.get("product_type", "product")
    tone = payload.get("tone", "balanced and human")
    audience = payload.get("audience", "general consumers")
    visual = payload.get("visual_rules", "")
    forbidden = payload.get("forbidden_words") or []
    key_msgs = payload.get("key_messages") or []

    forbidden_str = ", ".join(forbidden) if forbidden else "(none specified)"
    msgs_str = " then ".join(key_msgs) if key_msgs else "the core value proposition"

    return {
        "TONE": (
            f"For {name}, write in a {tone} register. Speak like a knowledgeable peer, "
            "not a sales rep. Avoid corporate jargon and passive voice. Sentences should be "
            "short and energetic; second person preferred."
        ),
        "AUDIENCE": (
            f"Primary audience: {audience}. They value authenticity over polish and respond "
            f"to substance over slogans. Reference their context — daily routines around {product} — "
            "rather than abstract aspiration."
        ),
        "FORBIDDEN": (
            f"Never use any of these words: {forbidden_str}. Avoid hyperbole "
            "('best ever', 'revolutionary'), unverified health claims, and corporate jargon "
            "('synergy', 'leverage'). No exclamation marks at the end of headlines."
        ),
        "VISUAL": (
            visual
            or f"Logo must be clearly visible (minimum 80px). Background should be light. "
            "Photography is bright and natural — no heavy filters. Negative space is welcome."
        ),
        "MESSAGING": (
            f"Lead with {msgs_str}. Always in that order. "
            "Close with a single concrete call to action — no more than 6 words."
        ),
    }


def _mock_generate_content(
    *,
    brand_name: str,
    content_type: str,
    request: str,
    retrieved_context: list[tuple[str, str]],
    forbidden_words: list[str],
) -> dict[str, Any]:
    """
    Heuristic generator:
      1. Detect forbidden-word violations in the *request* — block if any.
      2. Pull tone & messaging hints from retrieved_context.
      3. Synthesize a short, brand-shaped piece of copy.
    """
    request_lower = (request or "").lower()
    hits = sorted({w for w in forbidden_words if w and w.lower() in request_lower})
    if hits:
        return {
            "content": None,
            "conflicts": [
                {
                    "rule": "FORBIDDEN words",
                    "violation": (
                        f"Your request contains the prohibited word(s): {', '.join(hits)}."
                    ),
                    "suggestion": (
                        "Rephrase without these terms. Try synonyms aligned with the brand's "
                        "tone — e.g. 'wholesome', 'crafted', 'real'."
                    ),
                }
                for _ in [0]
            ],
        }

    # tone hints
    tone_hint = ""
    msg_hint = ""
    for section, content in retrieved_context:
        if section == "TONE":
            tone_hint = content[:120]
        if section == "MESSAGING":
            msg_hint = content[:120]

    # very simple scaffolded copy
    if "tagline" in content_type:
        body = f"{brand_name} — real ingredients, honest energy."
    elif "social" in content_type or "instagram" in request_lower:
        body = (
            f"Fuel your day the {brand_name} way. Real ingredients, no shortcuts — just "
            "the steady energy you need to keep moving. Because what you eat should match "
            "how you live."
        )
    elif "video" in content_type or "guion" in content_type:
        body = (
            f"[Open on a sunlit kitchen]\nVO: '{brand_name} starts with what's real.'\n"
            "[Hands snap a {brand_name} pack]\nVO: 'No shortcuts. Just the energy you need.'\n"
            "[End on logo, white background]\nSUPER: Real ingredients. Made honestly."
        ).replace("{brand_name}", brand_name)
    else:
        body = (
            f"{brand_name} packs real, honest ingredients into every bite. "
            "Made for people who care about what they eat — and what they don't put in. "
            "Sustainably grown, cleanly made, and ready for whatever your day looks like."
        )

    # safety pass — strip any forbidden words that may have slipped in
    sanitized = body
    for w in forbidden_words:
        if not w:
            continue
        sanitized = re.sub(rf"\b{re.escape(w)}\b", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    return {
        "content": sanitized,
        "conflicts": [],
    }
