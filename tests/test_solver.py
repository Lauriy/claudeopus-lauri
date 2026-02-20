"""Tests for molt.solver."""

import pytest

from molt.solver import (
    WORD_TO_NUM,
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
        """Known noise-word limitation: 'these two' extracts '2'."""
        assert solve_challenge(
            "swims at twenty three centimeters per second and claw force is seven newtons, multiply these two",
            "calculate the result",
        ) == pytest.approx(322.0)

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
