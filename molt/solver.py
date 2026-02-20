"""Verification challenge solver — pure computation, no API dependency."""

import re

WORD_TO_NUM = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
}


def decode_obfuscated(text):
    """Decode obfuscated challenge text: strip special chars, collapse doubled letters.
    Uses greedy pair matching: if current and next char are same letter (ignoring case),
    collapse to one and skip the next. This correctly handles 'EeEe' -> 'ee' (sixteen)."""
    words = text.split()
    decoded = []
    for word in words:
        clean = "".join(c for c in word if c.isalpha())
        if not clean:
            continue
        result = []
        i = 0
        while i < len(clean):
            if i + 1 < len(clean) and clean[i].lower() == clean[i + 1].lower():
                result.append(clean[i].lower())
                i += 2  # skip the duplicate
            else:
                result.append(clean[i].lower())
                i += 1
        decoded.append("".join(result))
    return " ".join(decoded)


def _fuzzy_num(token):
    """Try to match a potentially truncated number word. Returns value or None.
    Handles decoder artifacts: dropped letters ('fourten' -> 'fourteen'),
    truncated suffixes ('thre' -> 'three')."""
    if token in WORD_TO_NUM:
        return WORD_TO_NUM[token]
    if len(token) < 3:
        return None
    # Strategy 1: try inserting one letter at each position (handles decoder dropping a letter)
    for i in range(len(token) + 1):
        for c in "aeeioou":  # only vowels + common doubles
            candidate = token[:i] + c + token[i:]
            if candidate in WORD_TO_NUM:
                return WORD_TO_NUM[candidate]
    # Strategy 2: suffix truncation (decoder lost trailing chars)
    for word, val in WORD_TO_NUM.items():
        if word.startswith(token) and len(token) >= len(word) - 2:
            return val
    return None


def words_to_number(words):
    """Convert a sequence of number words to a single number. E.g. ['thirty','two'] -> 32."""
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
    total += current
    return total


def extract_numbers(text):
    """Extract number groups from decoded text, return list of ints."""
    tokens = text.lower().split()
    numbers = []
    buf = []
    for t in tokens:
        val = _fuzzy_num(t)
        if val is not None:
            buf.append(t)
        elif buf:
            numbers.append(words_to_number(buf))
            buf = []
    if buf:
        numbers.append(words_to_number(buf))
    # Also extract bare digits
    numbers.extend(float(m.group()) for m in re.finditer(r"\b\d+\.?\d*\b", text))
    return numbers


def solve_challenge(challenge_text, instructions=""):
    """Decode obfuscated challenge text, extract numbers, compute answer."""
    decoded = decode_obfuscated(challenge_text)
    print(f"  Challenge decoded: {decoded}")
    nums = extract_numbers(decoded)
    print(f"  Numbers found: {nums}")
    if not nums:
        # Fallback: try extracting numbers from raw text too
        nums = extract_numbers(challenge_text.lower())
        print(f"  Fallback numbers from raw: {nums}")
    if not nums:
        return None
    # Check instructions for operation hints
    inst_lower = (instructions + " " + decoded).lower()

    def _has_stem(text, stems):
        return any(s in text for s in stems)

    if _has_stem(inst_lower, ("multipl", "product", "times")):
        result = 1
        for n in nums:
            result *= n
    elif _has_stem(inst_lower, ("subtract", "minus", "differ", "lose", "lost", "decreas", "less", "reduc", "slow")):
        result = nums[0]
        for n in nums[1:]:
            result -= n
    elif _has_stem(inst_lower, ("divid", "ratio", "split")):
        result = nums[0]
        for n in nums[1:]:
            if n != 0:
                result /= n
    else:
        # Default: sum
        result = sum(nums)
    return result
