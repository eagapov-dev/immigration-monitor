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

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove punctuation/special chars, keep letters, digits, spaces."""
        return re.sub(r'[^\w\s]', ' ', text.lower())

    @staticmethod
    def _word_match(keyword: str, cleaned_text: str) -> bool:
        """Match whole word using \\b boundaries."""
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', cleaned_text))

    # Category markers — covers EN, RU, UK.  Order matters: first match wins.
    _CATEGORY_MARKERS = {
        "asylum": [
            # EN
            "asylum", "refugee", "persecution",
            # RU
            "убежище", "убежища", "убежищу", "убежищем",
            "политическое убежище", "политического убежища",
            "беженец", "беженца", "беженцу", "беженцем",
            "беженцы", "беженцев", "беженцам", "беженцами",
            "статус беженца", "статуса беженца",
            # UK
            "притулок", "притулку", "притулком",
            "політичний притулок", "політичного притулку",
            "біженець", "біженця", "біженцю", "біженцем",
            "біженці", "біженців", "біженцям",
            "статус біженця", "статусу біженця",
        ],
        "deportation": [
            # EN
            "deportation", "deport", "removal", "removal proceedings",
            "ice",
            # RU
            "депортация", "депортации", "депортацию", "депортацией",
            "депортировали", "депортируют", "депортирован", "депортирована",
            "принудительное выдворение",
            "рейд", "рейды", "рейдов",
            "задержали", "задержан", "задержана", "задержание", "задержания",
            # UK
            "депортація", "депортації", "депортацію", "депортацією",
            "депортували", "депортують", "депортований", "депортована",
            "затримали", "затримання", "затриманий", "затримана",
        ],
        "green_card": [
            # EN
            "green card", "greencard", "i-485", "adjustment of status",
            "permanent resident",
            # RU
            "грин карта", "грин карту", "грин карты", "грин картой",
            "грин-карта", "грин-карту", "грин-карты", "грин-картой",
            # UK
            "грін карта", "грін карту", "грін карти", "грін картою",
            "грін-карта", "грін-карту", "грін-карти",
        ],
        "visa": [
            # EN
            "visa", "h-1b", "h1b", "o-1", "o1",
            "eb-1", "eb1", "eb-2", "eb2", "niw",
            "consulate",
            # RU
            "виза", "визу", "визы", "визой", "визе",
            "визовый", "визовая", "визовую", "визового", "визовой", "визовые",
            "рабочая виза", "рабочей визы", "рабочую визу",
            "консульство", "консульства", "консульству", "консульством", "консульстве",
            # UK
            "віза", "візу", "візи", "візою", "візі", "віз",
            "візовий", "візову", "візової", "візових",
            "робоча віза", "робочої візи", "робочу візу",
            "туристична віза",
            "консульство", "консульства", "консульству", "консульством", "консульстві",
        ],
        "work": [
            # EN
            "work permit", "ead", "i-765", "employment authorization",
            # RU
            "разрешение на работу", "разрешения на работу", "разрешению на работу",
            # UK
            "дозвіл на роботу", "дозволу на роботу", "дозволом на роботу",
        ],
        "family": [
            # EN
            "i-130", "petition", "sponsor", "spouse", "marriage",
            # RU
            "петиция", "петиции", "петицию", "петицией",
            "семейная",
            # UK
        ],
        "citizenship": [
            # EN
            "citizenship", "naturalization", "n-400",
            # RU
            "гражданство", "гражданства", "гражданству", "гражданством",
            "натурализация", "натурализации", "натурализацию", "натурализацией",
            # UK
            "громадянство", "громадянства", "громадянству", "громадянством",
        ],
        "tps": [
            # EN
            "tps", "temporary protected status", "daca",
            # RU / UK
            "парол", "пароля", "паролю", "паролем",
            "гуманитарный пароль", "гуманитарного пароля",
            "гуманітарний пароль", "гуманітарного пароля",
        ],
    }

    def _detect_category(self, cleaned: str) -> str:
        """Detect immigration category from cleaned text."""
        for cat, markers in self._CATEGORY_MARKERS.items():
            if any(self._word_match(self._clean_text(m), cleaned) for m in markers):
                return cat
        return "other"

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
        if not self.anthropic_api_key or self.anthropic_api_key == "YOUR_ANTHROPIC_API_KEY":
            return None
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
