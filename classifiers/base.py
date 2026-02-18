"""
Base classes for the modular classifier system.
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    is_relevant: bool
    is_question: bool
    category: Optional[str] = None  # visa, asylum, deportation, green_card, work, family, other
    urgency: Optional[str] = None  # high, medium, low
    summary: Optional[str] = None
    confidence: float = 0.0
    method: str = "keywords"  # keywords, ai, hybrid
    draft_response: Optional[str] = None


class BaseClassifier:
    """Shared AI call logic for all language classifiers."""

    def __init__(self, ai_api_key: Optional[str], model: str):
        self.anthropic_api_key = ai_api_key
        self.model = model
        self._client = None

    def _get_ai_client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.anthropic_api_key)
            except ImportError:
                logger.error("anthropic package not installed. Run: pip install anthropic")
                raise
        return self._client

    def _call_ai(
        self, text: str, lang_hint: str = "en", include_draft: bool = False,
        extra_prompt: str = ""
    ) -> ClassificationResult:
        """Call Claude AI and return ClassificationResult."""
        client = self._get_ai_client()

        draft_instruction = ""
        if include_draft:
            draft_instruction = """
Also generate a brief, helpful draft response (2-3 sentences) in the SAME language
as the original post. The response should:
- Be empathetic and professional
- Provide a brief helpful insight
- Subtly suggest consulting with an immigration attorney for their specific case
Include it in the "draft_response" field.
"""

        prompt = f"""Analyze this social media post about potential US immigration topic.
Language hint: {lang_hint}
{extra_prompt}
Post text: "{text[:2000]}"

Classify it and respond ONLY with valid JSON (no markdown, no backticks):
{{
  "is_relevant": true/false (is this about US immigration/visa/legal status?),
  "is_question": true/false (is the person asking for help/advice/information?),
  "category": "visa|asylum|deportation|green_card|work|family|citizenship|tps|other",
  "urgency": "high|medium|low" (high = person in immediate danger/deadline, medium = needs help soon, low = general question),
  "summary": "one sentence summary in English",
  "confidence": 0.0-1.0{', "draft_response": "helpful response in source language"' if include_draft else ''}
}}
{draft_instruction}"""

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            result_text = response.content[0].text.strip()
            result_text = re.sub(r"^```json\s*", "", result_text)
            result_text = re.sub(r"\s*```$", "", result_text)

            data = json.loads(result_text)

            return ClassificationResult(
                is_relevant=data.get("is_relevant", False),
                is_question=data.get("is_question", False),
                category=data.get("category", "other"),
                urgency=data.get("urgency", "medium"),
                summary=data.get("summary"),
                confidence=data.get("confidence", 0.5),
                method="ai",
                draft_response=data.get("draft_response"),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            return None
        except Exception as e:
            logger.error(f"AI classification error: {e}")
            return None
