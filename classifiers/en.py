"""
English classifier: keyword pre-filter → AI for matches.
"""
import logging
import re
from typing import Optional

from .base import BaseClassifier, ClassificationResult

logger = logging.getLogger(__name__)

# Short/ambiguous keywords that need word boundary matching
WHOLE_WORD_KEYWORDS = {
    'ice', 'ead', 'tps', 'cbp', 'i-94', 'eb1', 'eb2', 'o1', 'o-1',
    'daca', 'niw',
}


class EnglishClassifier(BaseClassifier):
    """
    Hybrid classifier for English text.
    Stage 1: keyword pre-filter (fast, free).
    Stage 2: AI verification for keyword matches.
    """

    def __init__(self, config_en: dict, ai_api_key: Optional[str], model: str):
        super().__init__(ai_api_key, model)
        self.keywords = [kw.lower() for kw in config_en.get("keywords", [])]
        self.question_markers = [qm.lower() for qm in config_en.get("question_markers", [])]
        self.min_keyword_matches = config_en.get("min_keyword_matches", 1)

    @staticmethod
    def _keyword_match(keyword: str, text_lower: str) -> bool:
        if keyword in WHOLE_WORD_KEYWORDS:
            return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text_lower))
        return keyword in text_lower

    def _classify_keywords(self, text: str) -> ClassificationResult:
        text_lower = text.lower()
        keyword_matches = sum(1 for kw in self.keywords if self._keyword_match(kw, text_lower))
        has_question = any(qm in text_lower for qm in self.question_markers)
        is_relevant = keyword_matches >= self.min_keyword_matches
        category = self._detect_category(text_lower)
        return ClassificationResult(
            is_relevant=is_relevant,
            is_question=has_question,
            category=category,
            urgency="medium",
            confidence=min(keyword_matches * 0.2, 1.0),
            method="keywords",
        )

    def _detect_category(self, text_lower: str) -> str:
        categories = {
            "asylum": ["asylum", "убежище", "притулок", "refugee", "беженец", "біженець", "persecution"],
            "deportation": ["deportation", "deport", "депортация", "депортація", "ice", "removal", "removal proceedings"],
            "green_card": ["green card", "greencard", "грин карта", "грін карта", "i-485", "adjustment of status", "permanent resident"],
            "visa": ["visa", "виза", "віза", "h-1b", "h1b", "o-1", "o1", "eb-1", "eb1", "eb-2", "eb2", "niw", "консул", "consulate"],
            "work": ["work permit", "ead", "i-765", "разрешение на работу", "дозвіл на роботу", "employment authorization"],
            "family": ["i-130", "petition", "sponsor", "петиция", "spouse", "marriage", "семейная"],
            "citizenship": ["citizenship", "naturalization", "n-400", "гражданство", "громадянство", "натурализация"],
            "tps": ["tps", "temporary protected status", "daca"],
        }
        for cat, markers in categories.items():
            if any(self._keyword_match(m.lower(), text_lower) for m in markers):
                return cat
        return "other"

    def classify(self, text: str, include_draft: bool = False) -> ClassificationResult:
        """Keyword pre-filter → AI for matches."""
        keyword_result = self._classify_keywords(text)

        if not keyword_result.is_relevant:
            return keyword_result

        # AI verification for keyword matches
        ai_result = self._call_ai(text, lang_hint="en", include_draft=include_draft)
        if ai_result is None:
            # Fallback to keywords on AI error
            return keyword_result

        ai_result.method = "hybrid"
        return ai_result
