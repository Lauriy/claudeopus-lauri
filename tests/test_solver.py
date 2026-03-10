"""Tests for molt.solver."""

import pytest

from molt.solver import (
    WORD_TO_NUM,
    _extract_raw_operators,
    _fuzzy_num,
    _join_split_tokens,
    decode_obfuscated,
    extract_numbers,
    solve_challenge,
    words_to_number,
)


class TestDecodeObfuscated:
    def test_doubled_letters(self) -> None:
        assert decode_obfuscated("HhEeLlLlOo") == "hello"

    def test_strips_special_chars(self) -> None:
        assert decode_obfuscated("h@e#l!l%o") == "helo"

    def test_mixed_case_pairs(self) -> None:
        assert decode_obfuscated("EeEe") == "ee"

    def test_preserves_non_doubled(self) -> None:
        assert decode_obfuscated("abc") == "abc"

    def test_multiple_words(self) -> None:
        assert decode_obfuscated("TtHhIiRrTtYy TtWwOo") == "thirty two"

    def test_empty_input(self) -> None:
        assert decode_obfuscated("") == ""

    def test_only_special_chars(self) -> None:
        assert decode_obfuscated("@#$% !@#$") == ""


class TestFuzzyNum:
    def test_exact_match(self) -> None:
        for word, val in WORD_TO_NUM.items():
            assert _fuzzy_num(word) == val

    def test_fourten(self) -> None:
        assert _fuzzy_num("fourten") == 14

    def test_fiften(self) -> None:
        assert _fuzzy_num("fiften") == 15

    def test_thre(self) -> None:
        assert _fuzzy_num("thre") == 3

    def test_too_short(self) -> None:
        assert _fuzzy_num("ab") is None

    def test_nonsense(self) -> None:
        assert _fuzzy_num("lobster") is None
        assert _fuzzy_num("claw") is None

    def test_blocklist(self) -> None:
        assert _fuzzy_num("for") is None
        assert _fuzzy_num("the") is None
        assert _fuzzy_num("ore") is None

    def test_elven(self) -> None:
        assert _fuzzy_num("elven") == 11

    def test_thiirty(self) -> None:
        assert _fuzzy_num("thiirty") == 30

    def test_tweny(self) -> None:
        """'tweny' missing 't' from 'twenty' — consonant insertion."""
        assert _fuzzy_num("tweny") == 20

    def test_ttwelve(self) -> None:
        assert _fuzzy_num("ttwelve") == 12


class TestJoinSplitTokens:
    def test_joins_split_number(self) -> None:
        assert _join_split_tokens(["t", "welve"]) == ["twelve"]

    def test_joins_in_context(self) -> None:
        assert "twelve" in _join_split_tokens(["force", "is", "t", "welve", "newtons"])

    def test_no_false_joins(self) -> None:
        tokens = ["claw", "force", "is", "thirty"]
        assert _join_split_tokens(tokens) == tokens

    def test_three_way_join(self) -> None:
        assert _join_split_tokens(["f", "if", "teen"]) == ["fifteen"]

    def test_three_way_in_context(self) -> None:
        result = _join_split_tokens(["exerts", "f", "if", "teen", "newtons"])
        assert "fifteen" in result


class TestWordsToNumber:
    def test_simple(self) -> None:
        assert words_to_number(["five"]) == 5

    def test_compound(self) -> None:
        assert words_to_number(["thirty", "two"]) == 32

    def test_twenty_three(self) -> None:
        assert words_to_number(["twenty", "three"]) == 23

    def test_hundred(self) -> None:
        assert words_to_number(["one", "hundred"]) == 100

    def test_hundred_and_unit(self) -> None:
        assert words_to_number(["two", "hundred", "fifty"]) == 250


class TestExtractNumbers:
    def test_two_numbers(self) -> None:
        assert extract_numbers("thirty and five") == [30, 5]

    def test_compound(self) -> None:
        assert extract_numbers("twenty four") == [24]

    def test_bare_digits(self) -> None:
        assert 42.0 in extract_numbers("the value is 42")

    def test_mixed(self) -> None:
        nums = extract_numbers("twenty three and 7")
        assert 23 in nums
        assert 7.0 in nums

    def test_no_numbers(self) -> None:
        assert extract_numbers("lobster claw force") == []


class TestExtractRawOperators:
    """Unit tests for _extract_raw_operators — literal math operator detection in raw text."""

    def test_star_with_spaces(self) -> None:
        assert "*" in _extract_raw_operators("FoRcE * SeVeN")

    def test_star_no_leading_space(self) -> None:
        """Session 16 bug: 'iS* ThRe' — star without leading space must still be detected."""
        assert "*" in _extract_raw_operators("iT/ iS* ThRe E, HoW")

    def test_star_embedded_in_word(self) -> None:
        assert "*" in _extract_raw_operators("LoB*StEr")

    def test_plus_with_spaces(self) -> None:
        assert "+" in _extract_raw_operators("ThIrTy TwO + EiGhT")

    def test_no_operators(self) -> None:
        assert _extract_raw_operators("LoOoBbSsTtEeR SwImS") == set()

    def test_slash_not_detected_without_context(self) -> None:
        """Slash (/) is common in obfuscation noise — should not be detected without word boundaries."""
        ops = _extract_raw_operators("aT/ tWeNtY tHrEe")
        assert "/" not in ops


class TestSolveChallenge:
    """Regression tests using collected challenge samples."""

    def test_add_30_5(self) -> None:
        assert solve_challenge(
            "claw force is thirty newtons and it gains five newtons after molting",
            "add the two numbers",
        ) == pytest.approx(35.0)

    def test_add_50_24(self) -> None:
        assert solve_challenge(
            "left claw exerts fifty newtons, right claw exerts twenty four newtons",
            "calculate total force",
        ) == pytest.approx(74.0)

    def test_add_32_14(self) -> None:
        assert solve_challenge(
            "claw exerts thirty two newtons and another claw exerts fourteen newtons",
            "calculate total force",
        ) == pytest.approx(46.0)

    def test_add_22_15(self) -> None:
        assert solve_challenge(
            "claw exerts twenty two newtons and another claw exerts fifteen newtons",
            "calculate total force",
        ) == pytest.approx(37.0)

    def test_sub_24_7(self) -> None:
        assert solve_challenge(
            "swims at twenty four meters per second and loses seven meters per second",
            "calculate the resulting speed",
        ) == pytest.approx(17.0)

    def test_sub_23_7(self) -> None:
        assert solve_challenge(
            "swims at twenty three meters per second, slows by seven meters per second",
            "calculate the resulting speed",
        ) == pytest.approx(16.0)

    def test_mul_23_3(self) -> None:
        assert solve_challenge(
            "claw force expresses twenty three newtons and it grips object three times",
            "calculate total force",
        ) == pytest.approx(69.0)

    def test_mul_23_4(self) -> None:
        assert solve_challenge(
            "exerts twenty three newtons with one claw and multiplies by four",
            "calculate the result",
        ) == pytest.approx(92.0)

    def test_add_42_16_split_force(self) -> None:
        """'for ce' must NOT match 'four'."""
        assert solve_challenge(
            "a lobster claw exerts for ty two notons and the other exerts six ten notons what is the total for ce",
            "Solve the math problem",
        ) == pytest.approx(58.0)

    def test_add_30_12_split_token(self) -> None:
        """'thiirty' (extra i) + 't welve' (split token) = 42."""
        assert solve_challenge(
            "claw force is thiirty neutons and other claw has t welve neutons whats the total force",
            "Solve the math problem",
        ) == pytest.approx(42.0)

    def test_mul_23_7_noise(self) -> None:
        """'these two' must NOT extract 2 — 'two' is a pronoun reference, not a measurement. Fixed session 15."""
        assert solve_challenge(
            "swims at twenty three centimeters per second and claw force is seven newtons, multiply these two",
            "calculate the result",
        ) == pytest.approx(161.0)

    def test_add_32_15_three_way_split(self) -> None:
        """'F iF tEeN' decodes to 'f if teen' — needs 3-way token join."""
        assert solve_challenge(
            "a lobster claw exert sthirty two newtons and other claw exerts f if teen total force",
            "Solve the math problem",
        ) == pytest.approx(47.0)

    def test_sub_23_7_split_operation(self) -> None:
        """'slo ws' splits the 'slow' stem — operation detection must handle split tokens."""
        assert solve_challenge(
            "a lobster swims in the velawcite of twen ty thre meters per second um and slo ws by seven how much new veloocity",
            "Solve the math problem",
        ) == pytest.approx(16.0)

    def test_sub_32_12_doubled_operation(self) -> None:
        """'diifference' has doubled chars from decoder — stem 'differ' must still match."""
        assert solve_challenge(
            "a lobster exerts thirty two neewtons cllaw foorce resists twelve neewtons what is the diifference",
            "Solve the math problem",
        ) == pytest.approx(20.0)

    def test_mul_33_7_raw_asterisk(self) -> None:
        """Literal '*' in raw challenge text means multiplication — decoder strips it."""
        assert solve_challenge(
            "LoO.oBbSsTt-Err] ClLaAaWw^ FoOrRcEe] Is/ ThIrRtTyY ThHrReEe] NeEwWoOtToOnNs~ * SeEvVeEn, WhHaAt] Is/ ToOtTaAlLl^ FoOrRcEe?",
            "Solve the math problem",
        ) == pytest.approx(231.0)

    def test_mul_25_3_compound_before_split(self) -> None:
        """'t wenty f ive' must join as 'twenty'+'five'=25, NOT eat 'f' into 3-way 'twentyf'→20."""
        assert solve_challenge(
            "A] LoB- StEr S^hArE d ClAw FoRcE Is tHiRty TwOoO NeU- ToNs / AnD iT MuLtIpLiEs By <fOuR tEeN> , WhAt Is ThE ToTaL FoRcE?",
            "Solve the math problem",
        ) == pytest.approx(448.0)

    def test_mul_25_3_decoded_form(self) -> None:
        """Regression: 'twenty five' x 3 from the decoded challenge text."""
        assert solve_challenge(
            "A] L oB-StEr S cLaW E xErTs T wEnTy F iVe N ooOtOnS^ aNd- M oL tInG iNcReAsEs I t B y T hReE~ tImEs, W hAt/ iS T hE N eW C lAw F oR cE?",
            "Solve the math problem",
        ) == pytest.approx(75.0)

    def test_add_24_9_gains_with_noise_slash(self) -> None:
        """'gains' must trigger addition; noise '/' in obfuscation must not trigger division."""
        assert solve_challenge(
            "A] LoB- sT eRrR ~ClAw^ FoR cE Is] TwEnTy- FoU r {NeWtOnS} aNd] GaInS ^NiNe, /DuRiNg <DoM iNaNcE> fIgHt, hOw/ MuCh }ToTaL |FoRcE?",
            "Solve the math problem",
        ) == pytest.approx(33.0)

    def test_add_23_7_consonant_dropped(self) -> None:
        """'tweny thre' — missing consonants, should still get 23+7=30."""
        assert solve_challenge(
            "A] lOoObSsTtEeR^ sW/iMmSs [aT tW/eNnY ThRrEe] mEeTtEeRs- pEr\\ sEeCoNd] aNd- aCcEeLlEeRrAaTeEs/] bY[ sEeVvEeN, wH/aT\\ Is] tHe/ nEeW^ vEeLlOoCiTy?",
            "Solve the math problem",
        ) == pytest.approx(30.0)

    def test_no_correction_drops_previous_number(self) -> None:
        """'twenty six no sixteen' — 'no' corrects 26→16, so only 35+16=51."""
        assert solve_challenge(
            "Lo^bS.tEr] SwImS/ iN~ cOoL wAtEr, lOoObsssstEr- ClAwS^ ExErT/ tHiRty FiVe] nEu-TonS/ Of FoRce, aNd< aN oThEr- ClAw Is/ PuShInG tWeNty- SiX? um Um, nO, sIxTeEn] nEuToNs^ PlUs/ hOw/ mUcH ToTaL{ fOrCe?",
            "Solve the math problem and respond with ONLY the number (with 2 decimal places, e.g., '525.00'). Send your answer to POST /api/v1/verify with the verification_code.",
        ) == pytest.approx(51.0)

    def test_no_correction_extract_numbers(self) -> None:
        """extract_numbers should drop the corrected number when 'no' appears between groups."""
        nums = extract_numbers("thirty five and twenty six no sixteen plus total")
        assert 26 not in nums
        assert 35 in nums
        assert 16 in nums

    def test_join_preserves_adjacent_number_starts(self) -> None:
        """2-way exact match 'twenty' must not let 3-way eat 'f' from the next number."""
        result = _join_split_tokens(["t", "wenty", "f", "ive"])
        assert "twenty" in result
        assert "five" in result

    # --- Session 15 regression tests (2026-03-02) ---

    def test_add_22_3_accelerates(self) -> None:
        """Real challenge: 'swims at twenty two ... accelerates by three'."""
        assert solve_challenge(
            "A] LoOoObSssTeR^ sW/iMmS[ aT tW/eNtY- tWo] cMeEteR sS PeR- sEcOnD~ aNd| aCcEeLeR/aTeS bY{ tHrEe<, wHaT} iS~ tHe| nEw- sPeeD?",
            "Solve the math problem",
        ) == pytest.approx(25.0)

    def test_add_23_7_velocity(self) -> None:
        """Real challenge: 'swims at twenty three ... accelerates by seven'."""
        assert solve_challenge(
            "A] lO-bStEr S^wImS aT tW/eN tY tHrEe vE+lAwCiTeE CmS PeR SeC, aNd] iT AcCeLeRaTeS| bY sE-vEeN, wHaT] iS ThE nEw/ sPeE-d? umm^ lo.b sst errr velooocityyy nootons ~ uh",
            "Solve the math problem",
        ) == pytest.approx(30.0)

    def test_add_24_12_total_force(self) -> None:
        """Real challenge: 'claw force is twenty four newtons + twelve newtons'."""
        assert solve_challenge(
            "A] L oO oObB sStTeErR' S C lAw^ F oR cCeE iS tW eN tY fO uR N eW tO nS ] + [ tW eL vE N eW tO nS, hOw/ mUcH T oTaL F oR cE? ummm xx qqq",
            "Solve the math problem",
        ) == pytest.approx(36.0)

    def test_sub_24_5_slows(self) -> None:
        """Real challenge: 'swims at twenty four ... slows by five'."""
        assert solve_challenge(
            "A] LoOoBbSsTtEeRrr S^wImS[ aT tWeN tY fOuR MeTeRs PeR sEcOnD ~ um , BuT/ sLoW s-By F IvE MeTeRs PeR sEcOnD ] WhAt Is ThE NeT SpEeD?",
            "Solve the math problem",
        ) == pytest.approx(19.0)

    def test_mul_23_10_product(self) -> None:
        """Real challenge: 'twenty three ... claw force ten ... product'."""
        assert solve_challenge(
            "A] lOoObSsTtEeR] sW^iMmS/ aT tWeN tY tHrEe mEeTtEeRs] pEr/ sEeC O/nD, aNd- iTs] cLlAaW^ fOoRrCce] iS tEeN< nEu-TtOnS, hOw/ mAnY] iS tHe* pRoDuC t?",
            "Solve the math problem",
        ) == pytest.approx(230.0)

    def test_add_35_12_one_claw_noise(self) -> None:
        """'one claw' must NOT extract 1 — 'one' is a determiner, not a measurement.

        Correct answer: 35 + 12 = 47. Fixed in session 15.
        """
        result = solve_challenge(
            "Lo.bS]tEr ExErTs ThIrTy FiVe NoOtOnS / WiTh OnE CcLaW ~ AnD ThE OtHeR ClAw ExErTs TwElVe NoOtOnS < Um , WhAt Is ThE ToTaL FoRcE?",
            "Solve the math problem",
        )
        assert result == pytest.approx(47.0)

    def test_noise_word_one_claw_extract(self) -> None:
        """extract_numbers should filter 'one' from 'one claw' context."""
        nums = extract_numbers("thirty five notons with one claw and twelve notons total force")
        assert 1 not in nums
        assert 35 in nums
        assert 12 in nums

    def test_noise_word_these_two_extract(self) -> None:
        """extract_numbers should filter 'two' from 'these two' context."""
        nums = extract_numbers("multiply these two values twenty three and seven")
        assert 2 not in nums
        assert 23 in nums
        assert 7 in nums

    def test_small_num_preserved_with_unit(self) -> None:
        """Small numbers (1, 2) followed by units must NOT be filtered."""
        nums = extract_numbers("claw force is two newtons and gains three")
        assert 2 in nums
        assert 3 in nums

    def test_small_num_preserved_as_speed(self) -> None:
        """'one meter per second' — 'one' is a measurement, not noise."""
        nums = extract_numbers("swims at one meter per second and accelerates by five")
        assert 1 in nums
        assert 5 in nums

    # Session 16 regression tests (real challenges)
    def test_sub_23_7_slows_velocity(self) -> None:
        """Session 16: velocity 23, slows by 7 → 16."""
        result = solve_challenge(
            "A] LoO-bBsT^Er \\\\ VeLeOoCiTy| Is] TwEnTy ^ThReE {MeTeRs}/PeR SeCoNd ~, BuT/ It SlOwS\\ By SeVeN <MeTeRs> PeR SeCoNd - WhAt Is] ThE NeW} VeLoOoCiTy?? umm errr",
            "Solve the math problem",
        )
        assert result == pytest.approx(16.0)

    def test_add_22_8_total_newtons(self) -> None:
        """Session 16: swims at 22 newtons, claw force 8 → total 30."""
        result = solve_challenge(
            "A] LoOoBbSsTtEeR S^wIiMmSs /aT tWeNtY tW[o NeEwW tOoNs ] , ItS ClAaW F^oRcEe Is EiIgGhHt NoOtToOnSs ~, HoW MaNy NeWtOnS ToTaL < >?",
            "Solve the math problem",
        )
        assert result == pytest.approx(30.0)

    def test_mul_3_2_doubles(self) -> None:
        """Session 16: 'doubles by two' means multiply. Solver bug: _collapse_doubles('less')='les' matched in 'doubles'."""
        result = solve_challenge(
            "A] lO bS t-ErS S^wImS[ aT/ tHrEe MeT]eRs PeR\\ sEcOnD, AnD ThEn D^oUbLeS| By~ TwO, wHaT< Is- tHe NeW/ SpEeD?",
            "Solve the math problem",
        )
        assert result == pytest.approx(6.0)

    def test_doubles_detected_as_multiply(self) -> None:
        """'doubles' should trigger multiplication, not subtraction via 'les' in 'doubles'."""
        result = solve_challenge(
            "FoRcE Is TwEnTy AnD DoUbLeS bY tHrEe",
            "Solve the math problem",
        )
        assert result == pytest.approx(60.0)

    def test_add_32_8_literal_plus(self) -> None:
        """Session 16: literal + between numbers, 32 + 8 = 40."""
        result = solve_challenge(
            "LoOoBbSsTtEeR] sW/iMmS^ liKe Um] aN eEeRr, Mo.vInG } aT tHiRtY TwO + EiGhT < cEnTiMeTeRs\\ pEr] sEcOnD ~, hIs ClAw- fOrCe Is LoOkEd/ aFtEr, HoW> mUcH iS ThE/ nEw SpEeD?",
            "Solve the math problem",
        )
        assert result == pytest.approx(40.0)

    def test_mul_12_3_star_no_space(self) -> None:
        """Session 16: literal * without leading space ('iS* ThRe') must still trigger multiplication."""
        result = solve_challenge(
            "ThIs] lOoObsT-Er^ ClAw/ FoRce| Is~ TwEl Ve {nEw}ToNs <AnD> iT/ iS* ThRe E, HoW^ MuCh/ ToTaL- FoRce?",
            "Solve the math problem and respond with ONLY the number (with 2 decimal places, e.g., '525.00'). Send your answer to POST /api/v1/verify with the verification_code.",
        )
        assert result == pytest.approx(36.0)

    def test_add_23_5_accelerates(self) -> None:
        """Session 16: 'accelerates by five' should detect add via 'acceler' stem, not fall to default."""
        result = solve_challenge(
            "] A lOoB sT-Er S^wImS[ aT tW/En Ty ThReE cEmMeN tErS PeR sEcOnD- aNd] aCcElErAtEs By fI/Ve, wH-aTs T]hE nEw SpEeD? ~ lo.b st errr um lxobqstwer phyysxics",
            "Solve the math problem and respond with ONLY the number (with 2 decimal places, e.g., '525.00'). Send your answer to POST /api/v1/verify with the verification_code.",
        )
        assert result == pytest.approx(28.0)

    def test_add_32_12_split_t_wo(self) -> None:
        """Session 17: 'ThIrTy T wWo' splits 'two' as 't wo'. Joiner must not greedily consume 't' into 'thirtyt'."""
        result = solve_challenge(
            "A] LoBbSsTtEeR] wItH/ ClLaW^- FoRcE] oF- ThIrTy T wWo] NeEwWtToOnSs + TwElVvEe] NeEwWtToOnSs, WhAt/ Is] ThE- ToTaL^ FoRcE?",
            "Solve the math problem and respond with ONLY the number (with 2 decimal places, e.g., '525.00'). Send your answer to POST /api/v1/verify with the verification_code.",
        )
        assert result == pytest.approx(44.0)

    def test_join_no_steal_from_next_exact(self) -> None:
        """Joiner must not steal 't' from 't'+'wo'='two' into 'thirty'+'t'='thirtyt'."""
        result = _join_split_tokens(["thirty", "t", "wo", "newtons"])
        assert "thirty" in result
        assert "two" in result

    def test_add_not_sum_false_positive(self) -> None:
        """'swims um' must not false-match 'sum' stem in space-stripped text."""
        result = solve_challenge(
            "A] lOoB-StEr S^wImS Um LiKe A] cLaW HaS tW/eNtY ThReE NooTohNs ~ aNd- WiNs \\\\ fOuR DoMiNaN-ce FiGhTs, WhAt] Is ToTaL FoR-cE <oH>?",
            "Solve the math problem",
        )
        # Should detect 'total' for addition, NOT 'sum' from 'swimsum'
        assert result == pytest.approx(27.0)

    def test_add_28_4_strikes_total_force(self) -> None:
        """Session 17: server rejected 32.00 for '28+4 total force'. Solver says 32. Open question."""
        raw = r"A] LoB bSsTtErS^ ClAwWw FoRrCeE IsS/ tWeNtY eIgHhT] NeWwToNs- AnNd~ iTt StRrIkEsS\ FoUuR, WhAaT]s ThE/ ToTaLl- FoRrCeE?"
        decoded = decode_obfuscated(raw)
        nums = extract_numbers(decoded)
        assert nums == [28, 4]
        result = solve_challenge(raw)
        # Solver says 32.0 (addition via 'total'). Server rejected this.
        # Keeping test at 32.0 to document solver behavior; server expected answer unknown.
        assert result == pytest.approx(32.0)
