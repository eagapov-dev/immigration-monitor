#!/usr/bin/env python3
"""
Tests for word-boundary keyword matching in classifiers.

Run:  python3 -m pytest test_classifiers.py -v
"""
import pytest
import yaml

from classifiers.base import BaseClassifier
from classifiers.en import EnglishClassifier
from classifiers.ru import CyrillicClassifier
from classifiers import Classifier


# ── Load real config so tests match production keywords ──────────────────────
with open("config.yaml", "r", encoding="utf-8") as _f:
    _CFG = yaml.safe_load(_f)["classification"]


def _make_en(**overrides):
    cfg = {**_CFG.get("en", {}), **overrides}
    return EnglishClassifier(cfg, ai_api_key=None, model="x")


def _make_ru(**overrides_ru):
    return CyrillicClassifier(
        {**_CFG.get("ru", {}), **overrides_ru},
        _CFG.get("uk", {}),
        ai_api_key=None,
        model="x",
    )


def _make_full():
    return Classifier(_CFG)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BaseClassifier utility methods
# ═══════════════════════════════════════════════════════════════════════════════

class TestCleanText:
    def test_lowercases(self):
        assert BaseClassifier._clean_text("HELLO") == "hello"

    def test_removes_punctuation(self):
        assert BaseClassifier._clean_text("hello, world!") == "hello  world "

    def test_keeps_cyrillic(self):
        cleaned = BaseClassifier._clean_text("Віза для туристів")
        assert "віза" in cleaned
        assert "туристів" in cleaned

    def test_hyphen_becomes_space(self):
        assert BaseClassifier._clean_text("H-1B") == "h 1b"

    def test_keeps_digits(self):
        assert BaseClassifier._clean_text("I-485") == "i 485"


class TestWordMatch:
    def test_exact_word(self):
        assert BaseClassifier._word_match("visa", "need a visa now")

    def test_no_substring(self):
        assert not BaseClassifier._word_match("ice", "service center")

    def test_word_at_start(self):
        assert BaseClassifier._word_match("ice", "ice raids in city")

    def test_word_at_end(self):
        assert BaseClassifier._word_match("visa", "need a visa")

    def test_cyrillic_boundary(self):
        assert BaseClassifier._word_match("віз", "туристичних віз")

    def test_cyrillic_no_substring(self):
        assert not BaseClassifier._word_match("віз", "самовивіз")

    def test_multiword(self):
        assert BaseClassifier._word_match("green card", "get a green card today")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Ukrainian "віз" — the main bug that motivated this change
# ═══════════════════════════════════════════════════════════════════════════════

class TestUkrainianViz:
    """'віз' (genitive plural of 'віза') must NOT match inside 'самовивіз'."""

    @pytest.fixture()
    def clf(self):
        return _make_full()

    def test_samovyviz_not_relevant(self, clf):
        """самовивіз = self-pickup, nothing to do with visas."""
        result = clf.classify("самовивіз з укрпошти", source_lang="uk")
        assert not result.is_relevant

    def test_turistychnyh_viz_relevant(self, clf):
        """туристичних віз = tourist visas — must match."""
        result = clf.classify("оформлення туристичних віз", source_lang="uk")
        assert result.is_relevant

    def test_oformlennya_viz(self, clf):
        result = clf.classify("оформлення віз до США", source_lang="uk")
        assert result.is_relevant

    def test_vydacha_viz(self, clf):
        result = clf.classify("видача віз призупинена", source_lang="uk")
        assert result.is_relevant

    def test_viz_standalone(self, clf):
        result = clf.classify("скільки коштує віз", source_lang="uk")
        assert result.is_relevant

    def test_viza_still_works(self, clf):
        result = clf.classify("потрібна віза до США", source_lang="uk")
        assert result.is_relevant


# ═══════════════════════════════════════════════════════════════════════════════
# 3. English classifier — word boundary for short keywords
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnglishWordBoundary:
    @pytest.fixture()
    def clf(self):
        return _make_en()

    # ICE
    def test_ice_standalone(self, clf):
        r = clf._classify_keywords("ICE agents arrested 10 people")
        assert r.is_relevant

    def test_ice_not_in_service(self, clf):
        r = clf._classify_keywords("great customer service center")
        assert not r.is_relevant

    def test_ice_not_in_rice(self, clf):
        r = clf._classify_keywords("I love rice and beans")
        assert not r.is_relevant

    def test_ice_not_in_price(self, clf):
        r = clf._classify_keywords("the price went up")
        assert not r.is_relevant

    # TPS
    def test_tps_standalone(self, clf):
        r = clf._classify_keywords("TPS holders can now renew")
        assert r.is_relevant

    def test_tps_not_in_tips(self, clf):
        r = clf._classify_keywords("helpful tips for travelers")
        assert not r.is_relevant

    # EAD
    def test_ead_standalone(self, clf):
        r = clf._classify_keywords("EAD card renewal process")
        assert r.is_relevant

    def test_ead_not_in_dead(self, clf):
        r = clf._classify_keywords("my phone battery is dead")
        assert not r.is_relevant

    def test_ead_not_in_head(self, clf):
        r = clf._classify_keywords("scratch my head")
        assert not r.is_relevant

    # DACA
    def test_daca_standalone(self, clf):
        r = clf._classify_keywords("DACA recipients face uncertainty")
        assert r.is_relevant

    # NIW
    def test_niw_standalone(self, clf):
        r = clf._classify_keywords("NIW petition was approved")
        assert r.is_relevant

    # CBP
    def test_cbp_standalone(self, clf):
        r = clf._classify_keywords("stopped by CBP at the airport")
        assert r.is_relevant


# ═══════════════════════════════════════════════════════════════════════════════
# 4. English — hyphenated keywords (H-1B, I-485, etc.)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnglishHyphenatedKeywords:
    @pytest.fixture()
    def clf(self):
        return _make_en()

    def test_h1b_with_hyphen(self, clf):
        r = clf._classify_keywords("H-1B visa processing delays")
        assert r.is_relevant

    def test_h1b_no_hyphen(self, clf):
        r = clf._classify_keywords("H1B lottery results are out")
        assert r.is_relevant

    def test_o1_with_hyphen(self, clf):
        r = clf._classify_keywords("O-1 visa for extraordinary ability")
        assert r.is_relevant

    def test_i485(self, clf):
        r = clf._classify_keywords("My I-485 is pending for 2 years")
        assert r.is_relevant

    def test_i130(self, clf):
        r = clf._classify_keywords("Filed I-130 for my spouse")
        assert r.is_relevant

    def test_n400(self, clf):
        r = clf._classify_keywords("N-400 citizenship application")
        assert r.is_relevant

    def test_eb1(self, clf):
        r = clf._classify_keywords("EB-1 green card category")
        assert r.is_relevant

    def test_eb2(self, clf):
        r = clf._classify_keywords("EB-2 NIW petition approved")
        assert r.is_relevant


# ═══════════════════════════════════════════════════════════════════════════════
# 5. English — multi-word keywords & phrases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnglishMultiWord:
    @pytest.fixture()
    def clf(self):
        return _make_en()

    def test_green_card(self, clf):
        r = clf._classify_keywords("How to get a green card")
        assert r.is_relevant

    def test_work_permit(self, clf):
        r = clf._classify_keywords("applied for a work permit")
        assert r.is_relevant

    def test_adjustment_of_status(self, clf):
        r = clf._classify_keywords("adjustment of status timeline")
        assert r.is_relevant

    def test_immigration_lawyer(self, clf):
        r = clf._classify_keywords("need an immigration lawyer")
        assert r.is_relevant

    def test_removal_proceedings(self, clf):
        r = clf._classify_keywords("placed in removal proceedings")
        assert r.is_relevant


# ═══════════════════════════════════════════════════════════════════════════════
# 6. English — question detection (substring matching, not word boundary)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnglishQuestionDetection:
    @pytest.fixture()
    def clf(self):
        return _make_en()

    def test_question_mark(self, clf):
        r = clf._classify_keywords("Can I apply for a visa?")
        assert r.is_question

    def test_how_can_i(self, clf):
        r = clf._classify_keywords("How can I get a green card faster")
        assert r.is_question

    def test_anyone_know(self, clf):
        r = clf._classify_keywords("Does anyone know about visa processing times")
        assert r.is_question

    def test_no_question(self, clf):
        r = clf._classify_keywords("USCIS updated their policy today")
        assert not r.is_question


# ═══════════════════════════════════════════════════════════════════════════════
# 7. English — category detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnglishCategoryDetection:
    @pytest.fixture()
    def clf(self):
        return _make_en()

    def test_asylum(self, clf):
        r = clf._classify_keywords("filed for asylum last month")
        assert r.category == "asylum"

    def test_deportation(self, clf):
        r = clf._classify_keywords("facing deportation order")
        assert r.category == "deportation"

    def test_green_card(self, clf):
        r = clf._classify_keywords("green card interview scheduled")
        assert r.category == "green_card"

    def test_visa(self, clf):
        r = clf._classify_keywords("H-1B visa approved")
        assert r.category == "visa"

    def test_work(self, clf):
        r = clf._classify_keywords("EAD renewal delayed")
        assert r.category == "work"

    def test_family(self, clf):
        r = clf._classify_keywords("I-130 petition for spouse")
        assert r.category == "family"

    def test_citizenship(self, clf):
        r = clf._classify_keywords("naturalization ceremony next week")
        assert r.category == "citizenship"

    def test_tps(self, clf):
        r = clf._classify_keywords("TPS extension announced")
        assert r.category == "tps"

    def test_ice_is_deportation(self, clf):
        """ICE should map to deportation category, not get confused with 'ice'."""
        cleaned = clf._clean_text("ICE arrested 50 people")
        cat = clf._detect_category(cleaned)
        assert cat == "deportation"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Russian — category detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestRussianCategoryDetection:
    @pytest.fixture()
    def clf(self):
        return _make_ru()

    def test_asylum_ru(self, clf):
        r = clf.classify("подали на убежище в прошлом году", source_lang="ru")
        assert r.category == "asylum"

    def test_asylum_ru_refugee(self, clf):
        r = clf.classify("получил статус беженца в США", source_lang="ru")
        assert r.category == "asylum"

    def test_deportation_ru(self, clf):
        r = clf.classify("депортация грозит многим нелегалам", source_lang="ru")
        assert r.category == "deportation"

    def test_deportation_ru_raid(self, clf):
        r = clf.classify("рейды продолжаются в разных штатах", source_lang="ru")
        assert r.category == "deportation"

    def test_deportation_ru_detained(self, clf):
        r = clf.classify("задержали на границе без документов", source_lang="ru")
        assert r.category == "deportation"

    def test_green_card_ru(self, clf):
        r = clf.classify("ждём грин карту уже 3 года", source_lang="ru")
        assert r.category == "green_card"

    def test_visa_ru(self, clf):
        r = clf.classify("получила визу в консульстве", source_lang="ru")
        assert r.category == "visa"

    def test_visa_ru_work(self, clf):
        r = clf.classify("оформили рабочую визу через компанию", source_lang="ru")
        assert r.category == "visa"

    def test_work_ru(self, clf):
        r = clf.classify("нужно разрешение на работу для жены", source_lang="ru")
        assert r.category == "work"

    def test_citizenship_ru(self, clf):
        r = clf.classify("подали документы на гражданство", source_lang="ru")
        assert r.category == "citizenship"

    def test_citizenship_ru_naturalization(self, clf):
        r = clf.classify("процесс натурализации занял 8 месяцев", source_lang="ru")
        assert r.category == "citizenship"

    def test_tps_ru_parole(self, clf):
        r = clf.classify("гуманитарный пароль продлили до конца года", source_lang="ru")
        assert r.category == "tps"

    def test_other_ru(self, clf):
        r = clf.classify("вопрос по иммиграции в Америку", source_lang="ru")
        assert r.category == "other"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Ukrainian — category detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestUkrainianCategoryDetection:
    @pytest.fixture()
    def clf(self):
        return _make_ru()

    def test_asylum_uk(self, clf):
        r = clf.classify("подали на притулок в США", source_lang="uk")
        assert r.category == "asylum"

    def test_asylum_uk_refugee(self, clf):
        r = clf.classify("отримав статус біженця", source_lang="uk")
        assert r.category == "asylum"

    def test_deportation_uk(self, clf):
        r = clf.classify("депортація загрожує багатьом", source_lang="uk")
        assert r.category == "deportation"

    def test_deportation_uk_detained(self, clf):
        r = clf.classify("затримали на кордоні", source_lang="uk")
        assert r.category == "deportation"

    def test_green_card_uk(self, clf):
        r = clf.classify("чекаємо грін карту вже 2 роки", source_lang="uk")
        assert r.category == "green_card"

    def test_visa_uk(self, clf):
        r = clf.classify("потрібна віза до США", source_lang="uk")
        assert r.category == "visa"

    def test_visa_uk_tourist(self, clf):
        r = clf.classify("оформлення туристичних віз", source_lang="uk")
        assert r.category == "visa"

    def test_visa_uk_consulate(self, clf):
        r = clf.classify("запис в консульство на візу", source_lang="uk")
        assert r.category == "visa"

    def test_work_uk(self, clf):
        r = clf.classify("дозвіл на роботу для чоловіка", source_lang="uk")
        assert r.category == "work"

    def test_citizenship_uk(self, clf):
        r = clf.classify("подали на громадянство США", source_lang="uk")
        assert r.category == "citizenship"

    def test_tps_uk_parole(self, clf):
        r = clf.classify("гуманітарний пароль продовжили", source_lang="uk")
        assert r.category == "tps"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Russian classifier — keyword fallback (AI=None path)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRussianKeywordFallback:
    @pytest.fixture()
    def clf(self):
        return _make_ru()

    def test_visa_ru(self, clf):
        r = clf.classify("получила визу в США", source_lang="ru")
        assert r.is_relevant

    def test_immigration_ru(self, clf):
        r = clf.classify("вопрос по иммиграции в Америку", source_lang="ru")
        assert r.is_relevant

    def test_green_card_ru(self, clf):
        r = clf.classify("ждём грин карту уже 3 года", source_lang="ru")
        assert r.is_relevant

    def test_asylum_ru(self, clf):
        r = clf.classify("подали на убежище в прошлом году", source_lang="ru")
        assert r.is_relevant

    def test_deportation_ru(self, clf):
        r = clf.classify("депортация грозит многим", source_lang="ru")
        assert r.is_relevant

    def test_irrelevant_ru(self, clf):
        r = clf.classify("сегодня хорошая погода в Чикаго", source_lang="ru")
        assert not r.is_relevant

    def test_question_markers_ru(self, clf):
        r = clf.classify("подскажите как получить визу", source_lang="ru")
        assert r.is_question


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Ukrainian via CyrillicClassifier — keyword fallback
# ═══════════════════════════════════════════════════════════════════════════════

class TestUkrainianKeywordFallback:
    @pytest.fixture()
    def clf(self):
        return _make_ru()

    def test_viza_uk(self, clf):
        r = clf.classify("потрібна віза до США", source_lang="uk")
        assert r.is_relevant

    def test_immigration_uk(self, clf):
        r = clf.classify("питання щодо імміграції", source_lang="uk")
        assert r.is_relevant

    def test_grin_karta_uk(self, clf):
        r = clf.classify("отримати грін карту", source_lang="uk")
        assert r.is_relevant

    def test_prytulok_uk(self, clf):
        r = clf.classify("подали на притулок", source_lang="uk")
        assert r.is_relevant

    def test_irrelevant_uk(self, clf):
        r = clf.classify("гарна погода сьогодні в Києві", source_lang="uk")
        assert not r.is_relevant

    def test_samovyviz_not_relevant_uk(self, clf):
        """самовивіз must NOT trigger visa keywords."""
        r = clf.classify("самовивіз з нової пошти", source_lang="uk")
        assert not r.is_relevant

    def test_question_markers_uk(self, clf):
        r = clf.classify("підкажіть як отримати візу", source_lang="uk")
        assert r.is_question


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Full Classifier facade — language routing
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifierFacade:
    @pytest.fixture()
    def clf(self):
        return _make_full()

    def test_routes_en(self, clf):
        r = clf.classify("H-1B visa approved", source_lang="en")
        assert r.is_relevant
        assert r.method == "keywords"  # no AI key configured

    def test_routes_ru(self, clf):
        r = clf.classify("получила визу в США", source_lang="ru")
        assert r.is_relevant

    def test_routes_uk(self, clf):
        r = clf.classify("потрібна віза до США", source_lang="uk")
        assert r.is_relevant

    def test_routes_mixed(self, clf):
        r = clf.classify("оформлення туристичних віз", source_lang="ru/uk")
        assert r.is_relevant


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    @pytest.fixture()
    def clf(self):
        return _make_full()

    def test_empty_text(self, clf):
        r = clf.classify("", source_lang="en")
        assert not r.is_relevant

    def test_only_punctuation(self, clf):
        r = clf.classify("!!! ??? ...", source_lang="en")
        assert not r.is_relevant

    def test_keyword_with_punctuation(self, clf):
        """Keyword at end of sentence with period should still match."""
        r = clf.classify("She applied for asylum.", source_lang="en")
        assert r.is_relevant

    def test_keyword_in_quotes(self, clf):
        r = clf.classify('He said "visa" is hard to get', source_lang="en")
        assert r.is_relevant

    def test_keyword_with_comma(self, clf):
        r = clf.classify("visa, green card, and asylum", source_lang="en")
        assert r.is_relevant

    def test_all_caps(self, clf):
        r = clf.classify("NEED HELP WITH VISA APPLICATION", source_lang="en")
        assert r.is_relevant

    def test_mixed_case(self, clf):
        r = clf.classify("Applied for Asylum in the US", source_lang="en")
        assert r.is_relevant
