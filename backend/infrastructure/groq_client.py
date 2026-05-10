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
            "Eres un brand strategist senior. Con los inputs dados, produce un manual "
            "de marca estructurado con exactamente estas cinco secciones: TONE, AUDIENCE, "
            "FORBIDDEN, VISUAL, MESSAGING. Cada sección debe ser concreta y accionable. "
            "Responde SIEMPRE EN ESPAÑOL — no mezcles idiomas. "
            "Devuelve ÚNICAMENTE JSON válido con esta forma:\n"
            '{"TONE":"...","AUDIENCE":"...","FORBIDDEN":"...","VISUAL":"...","MESSAGING":"..."}'
        )
        user = (
            "Inputs:\n"
            f"- Nombre de marca: {payload.get('name')}\n"
            f"- Tipo de producto: {payload.get('product_type')}\n"
            f"- Tono: {payload.get('tone')}\n"
            f"- Audiencia: {payload.get('audience')}\n"
            f"- Reglas visuales: {payload.get('visual_rules')}\n"
            f"- Palabras prohibidas: {payload.get('forbidden_words')}\n"
            f"- Mensajes clave: {payload.get('key_messages')}\n"
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
        Generates brand-aligned copy as free text. The LLM focuses 100% of its
        output budget on the actual content; conflict detection (forbidden
        words enforcement) is handled programmatically by the caller via
        `ContentService._post_scan_for_forbidden`.

        Returns:
          {"content": str, "conflicts": []}
        """
        ctx_block = "\n\n".join(f"[{s}]\n{c}" for s, c in retrieved_context) or "(sin contexto)"
        system = (
            f"Eres un copywriter de marca para {brand_name}. "
            "Responde SIEMPRE EN ESPAÑOL — no mezcles idiomas en el texto generado. "
            "Devuelve ÚNICAMENTE el copy final, sin meta-comentarios, sin prefijos como "
            "'Aquí tienes:', sin envolver en JSON ni en markdown.\n\n"
            "Las REGLAS CRÍTICAS de abajo son no-negociables — alinea el tono, audiencia y "
            "mensajes de tu copy a estas reglas.\n\n"
            f"REGLAS CRÍTICAS (recuperadas del manual de marca):\n{ctx_block}\n\n"
            f"PALABRAS PROHIBIDAS (nunca uses ninguna, ni siquiera en variantes): {forbidden_words}"
        )
        resp = await self._client.chat.completions.create(
            model=self.settings.groq_model,
            temperature=self.settings.llm_temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Tipo de contenido: {content_type}\nPedido: {request}"},
            ],
        )
        content = (resp.choices[0].message.content or "").strip()
        # Conflicts are intentionally empty here — ContentService runs
        # `_post_scan_for_forbidden` defensively as the single source of truth.
        return {"content": content, "conflicts": []}
