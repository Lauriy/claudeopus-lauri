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
    "ten", "teen", "then", "they", "them", "this", "that", "than",
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
    """Join adjacent tokens that form a number word: ['f', 'if', 'teen'] -> ['fifteen'].

    Prefers exact 2-way joins over fuzzy 3-way joins to avoid greedily consuming
    the first letter of the next number (e.g. 't'+'wenty'+'f' eating the 'f' from 'five').
    """
    result: list[str] = []
    i = 0
    while i < len(tokens):
        exact_2 = i + 1 < len(tokens) and (tokens[i] + tokens[i + 1]) in WORD_TO_NUM
        if (
            not exact_2
            and i + 2 < len(tokens)
            and _fuzzy_num(tokens[i] + tokens[i + 1] + tokens[i + 2]) is not None
        ):
            result.append(tokens[i] + tokens[i + 1] + tokens[i + 2])
            i += 3
        elif i + 1 < len(tokens) and _fuzzy_num(tokens[i] + tokens[i + 1]) is not None:
            result.append(tokens[i] + tokens[i + 1])
            i += 2
        else:
            result.append(tokens[i])
            i += 1
    return result


def extract_numbers(text: str) -> list[int | float]:
    """Extract number groups from decoded text, handling 'no' corrections."""
    tokens = _join_split_tokens(text.lower().split())
    # Build list of (number, gap_tokens_before_it) to detect "no" corrections
    groups: list[tuple[int | float, list[str]]] = []
    buf: list[str] = []
    gap: list[str] = []  # non-number tokens since last number group
    for t in tokens:
        if _fuzzy_num(t) is not None:
            buf.append(t)
        elif buf:
            groups.append((words_to_number(buf), gap))
            buf = []
            gap = [t]
        else:
            gap.append(t)
    if buf:
        groups.append((words_to_number(buf), gap))

    # Drop numbers followed by "no" correction: "twenty six no sixteen" → keep only sixteen
    numbers: list[int | float] = []
    for i, (num, _gap_before) in enumerate(groups):
        # Check if NEXT group's gap contains "no" — meaning THIS number gets corrected away
        if i + 1 < len(groups):
            next_gap = groups[i + 1][1]
            if any(w == "no" for w in next_gap):
                continue  # skip this number, the next one replaces it
        numbers.append(num)

    numbers.extend(float(m.group()) for m in re.finditer(r"\b\d+\.?\d*\b", text))
    return numbers


def _collapse_doubles(text: str) -> str:
    """Collapse consecutive duplicate characters: 'diifference' -> 'diference'."""
    if not text:
        return text
    result = [text[0]]
    for c in text[1:]:
        if c != result[-1]:
            result.append(c)
    return "".join(result)


def _extract_raw_operators(text: str) -> set[str]:
    """Find literal math operators (*, /, +, -) in raw challenge text between word boundaries."""
    ops: set[str] = set()
    # Look for standalone * / + - surrounded by spaces or punctuation
    for m in re.finditer(r"(?<=[}\]~)\s])\s*([*/+\-])\s*(?=\s*[A-Za-z{(\[])", text):
        ops.add(m.group(1))
    # Also check for * appearing with spaces around it (/ excluded — too many false positives from obfuscation noise)
    if re.search(r"\s\*\s", text):
        ops.add("*")
    return ops


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

    raw_ops = _extract_raw_operators(challenge_text)
    combined = (instructions + " " + decoded).lower()
    combined_nospace = combined.replace(" ", "")
    combined_dedup = _collapse_doubles(combined)

    def _has(stems: tuple[str, ...]) -> bool:
        return any(
            s in combined or s in combined_nospace or _collapse_doubles(s) in combined_dedup
            for s in stems
        )

    if "*" in raw_ops or _has(("multipl", "product", "times")):
        result = 1.0
        for n in nums:
            result *= n
    elif _has(("subtract", "minus", "differ", "lose", "lost", "decreas", "less", "reduc", "slow")):
        result = nums[0]
        for n in nums[1:]:
            result -= n
    elif _has(("add", "plus", "sum", "combin", "gain", "increas", "total")):
        result = sum(nums)
    elif "/" in raw_ops or _has(("divid", "ratio", "split")):
        result = nums[0]
        for n in nums[1:]:
            if n != 0:
                result /= n
    else:
        result = sum(nums)
    return float(result)
