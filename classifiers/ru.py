"""
Cyrillic (Russian + Ukrainian) classifier: AI-first.

Russian/Ukrainian are morphologically rich ("виза" ≠ "визу/визой/визы"), so keyword
pre-filtering is unreliable. We go AI-first and use keywords only as a secondary signal.

Also handles implicit questions common in Telegram:
  "ситуация такая...", "отказали", "не знаю что делать" — no "?" needed.
"""
import logging
from typing import Optional

from .base import BaseClassifier, ClassificationResult

logger = logging.getLogger(__name__)

# Extra prompt hint for AI about implicit questions in Russian
_RU_EXTRA_PROMPT = """
IMPORTANT: In Russian/Ukrainian texts, questions are often IMPLICIT — people describe
their situation without using "?" or explicit question words. Examples of implicit
questions: "ситуация такая, отказали в визе", "задержали на границе, не знаю что делать",
"продление закончилось, куда обратиться". Treat these as is_question=true when the
person clearly needs help/advice even without explicit question markers.
"""


class CyrillicClassifier(BaseClassifier):
    """
    AI-first classifier for Russian and Ukrainian text.
    Keywords are loaded from config but used only for stats/logging, not as a gate.
    """

    def __init__(
        self,
        config_ru: dict,
        config_uk: dict,
        ai_api_key: Optional[str],
        model: str,
    ):
        super().__init__(ai_api_key, model)
        self.ru_keywords = [self._clean_text(kw) for kw in config_ru.get("keywords", [])]
        self.ru_question_markers = [qm.lower() for qm in config_ru.get("question_markers", [])]
        self.uk_keywords = [self._clean_text(kw) for kw in config_uk.get("keywords", [])]
        self.uk_question_markers = [qm.lower() for qm in config_uk.get("question_markers", [])]

    def _has_implicit_question(self, text_lower: str, source_lang: str) -> bool:
        """Check for implicit question markers specific to Telegram RU/UK."""
        markers = self.ru_question_markers[:]
        if source_lang in ("uk", "uk/ru", "ru/uk"):
            markers.extend(self.uk_question_markers)
        return any(m in text_lower for m in markers)

    def classify(
        self, text: str, source_lang: str = "ru", include_draft: bool = False
    ) -> ClassificationResult:
        """AI-first classification for Russian/Ukrainian text."""
        lang_label = "Ukrainian" if source_lang == "uk" else "Russian"

        ai_result = self._call_ai(
            text,
            lang_hint=f"{lang_label} ({source_lang})",
            include_draft=include_draft,
            extra_prompt=_RU_EXTRA_PROMPT,
        )

        if ai_result is None:
            # Fallback: keyword heuristic
            cleaned = self._clean_text(text)
            keywords = self.ru_keywords[:]
            if source_lang in ("uk", "uk/ru", "ru/uk"):
                keywords.extend(self.uk_keywords)
            kw_matches = sum(1 for kw in keywords if self._word_match(kw, cleaned))
            has_question = self._has_implicit_question(text.lower(), source_lang)
            category = self._detect_category(cleaned) if kw_matches >= 1 else "other"
            return ClassificationResult(
                is_relevant=kw_matches >= 1,
                is_question=has_question,
                category=category,
                urgency="medium",
                confidence=min(kw_matches * 0.2, 1.0),
                method="keywords",
            )

        ai_result.method = "ai"
        return ai_result
