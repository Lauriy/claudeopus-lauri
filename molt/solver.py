"""Verification challenge solver."""

import re

WORD_TO_NUM: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000,
}

# Words that fuzzy-match number words but aren't numbers.
_NOT_NUMBERS: frozenset[str] = frozenset({
    "for", "the", "our", "ore", "one", "her", "his", "its",
    "ten", "then", "they", "them", "this", "that", "than",
})


def decode_obfuscated(text: str) -> str:
    """Strip special chars and collapse doubled letters (Xx -> x)."""
    decoded: list[str] = []
    for word in text.split():
        clean = "".join(c for c in word if c.isalpha())
        if not clean:
            continue
        result: list[str] = []
        i = 0
        while i < len(clean):
            if i + 1 < len(clean) and clean[i].lower() == clean[i + 1].lower():
                result.append(clean[i].lower())
                i += 2
            else:
                result.append(clean[i].lower())
                i += 1
        decoded.append("".join(result))
    return " ".join(decoded)


def _fuzzy_num(token: str) -> int | None:
    """Match potentially corrupted number words (dropped/extra letters, truncation)."""
    if token in WORD_TO_NUM:
        return WORD_TO_NUM[token]
    if len(token) < 3 or token in _NOT_NUMBERS:
        return None
    for i in range(len(token) + 1):
        for c in "aeeioou":
            candidate = token[:i] + c + token[i:]
            if candidate in WORD_TO_NUM:
                return WORD_TO_NUM[candidate]
    for i in range(len(token)):
        candidate = token[:i] + token[i + 1:]
        if candidate in WORD_TO_NUM:
            return WORD_TO_NUM[candidate]
    for word, val in WORD_TO_NUM.items():
        if word.startswith(token) and len(token) >= len(word) - 2:
            return val
    return None


def words_to_number(words: list[str]) -> int:
    """['thirty', 'two'] -> 32."""
    total = 0
    current = 0
    for w in words:
        val = _fuzzy_num(w)
        if val is None:
            continue
        if val == 1000:
            current = (current or 1) * 1000
        elif val == 100:
            current = (current or 1) * 100
        else:
            current += val
    return total + current


def _join_split_tokens(tokens: list[str]) -> list[str]:
    """Join adjacent tokens that form a number word: ['t', 'welve'] -> ['twelve']."""
    result: list[str] = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and _fuzzy_num(tokens[i] + tokens[i + 1]) is not None:
            result.append(tokens[i] + tokens[i + 1])
            i += 2
        else:
            result.append(tokens[i])
            i += 1
    return result


def extract_numbers(text: str) -> list[int | float]:
    """Extract number groups from decoded text."""
    tokens = _join_split_tokens(text.lower().split())
    numbers: list[int | float] = []
    buf: list[str] = []
    for t in tokens:
        if _fuzzy_num(t) is not None:
            buf.append(t)
        elif buf:
            numbers.append(words_to_number(buf))
            buf = []
    if buf:
        numbers.append(words_to_number(buf))
    numbers.extend(float(m.group()) for m in re.finditer(r"\b\d+\.?\d*\b", text))
    return numbers


def solve_challenge(challenge_text: str, instructions: str = "") -> float | None:
    """Decode obfuscated text, extract numbers, compute answer."""
    decoded = decode_obfuscated(challenge_text)
    print(f"  Challenge decoded: {decoded}")
    nums = extract_numbers(decoded)
    print(f"  Numbers found: {nums}")
    if not nums:
        nums = extract_numbers(challenge_text.lower())
        print(f"  Fallback numbers from raw: {nums}")
    if not nums:
        return None

    combined = (instructions + " " + decoded).lower()

    def _has(stems: tuple[str, ...]) -> bool:
        return any(s in combined for s in stems)

    if _has(("multipl", "product", "times")):
        result = 1.0
        for n in nums:
            result *= n
    elif _has(("subtract", "minus", "differ", "lose", "lost", "decreas", "less", "reduc", "slow")):
        result = nums[0]
        for n in nums[1:]:
            result -= n
    elif _has(("divid", "ratio", "split")):
        result = nums[0]
        for n in nums[1:]:
            if n != 0:
                result /= n
    else:
        result = sum(nums)
    return float(result)
