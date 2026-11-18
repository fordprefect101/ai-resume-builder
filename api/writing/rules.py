"""Code-only checks for the writing team. No AI, no network, same answer every time.

Two checkpoints in the pipeline use these:
  check_facts   after the analyst: a fact stays only if its quoted words are really in
                the person's story, and it adds no number the quote does not hold.
  check_points  after the writer: every number and tool in a point must exist in the
                facts it cites, plus style and honesty rules.

Code is literal. "forty percent" and "40%" are handled below, but synonyms are not, so
expect some false alarms; the list of known equivalents grows from the test set.
"""

from __future__ import annotations

import re

# Terms that sound bigger than a story usually supports. Shared with api/claim_verify.py.
BOASTFUL_WORDS = (
    "millions",
    "billions",
    "enterprise",
    "large-scale",
    "petabyte",
    "global",
)

FACT_KINDS = ("context", "action", "tool", "result", "scale", "unsorted")
FACT_OWNERS = ("me", "team", "unclear")

MAX_POINTS = 5
MAX_WORDS = 35
MIN_WORDS = 3

# Openers that say nothing about what the person did.
WEAK_STARTS = {
    "i", "we", "my", "our", "the", "a", "an", "responsible", "worked", "helped",
    "assisted", "participated", "involved", "tasked", "duties", "was", "were", "am",
    "is", "had", "have", "got", "did", "does",
}
# Verbs and words that claim leadership or sole credit.
OWNERSHIP_CLAIMS = {
    "led", "lead", "owned", "spearheaded", "architected", "founded", "directed",
    "headed", "pioneered", "solely", "single-handedly", "independently",
}


# Issue codes meaning a point says more than its facts do. Counted by code, so these
# are never opinion. A point carrying one can never be marked as backed.
INVENTION_CODES = {
    "number_not_in_facts", "tool_not_in_facts", "ownership_not_in_facts",
    "boastful_term", "unknown_fact", "no_supporting_fact",
}
STYLE_CODES = {"weak_start", "first_person", "too_long", "too_short", "empty"}


def issue(code: str, message: str) -> dict:
    return {"code": code, "message": message}


# --- text matching -------------------------------------------------------------------

def normalize(text: str) -> str:
    """Lowercase, straighten quotes and dashes, collapse whitespace."""
    text = str(text or "").lower()
    for fancy, plain in (("‘", "'"), ("’", "'"), ("“", '"'),
                         ("”", '"'), ("–", "-"), ("—", "-")):
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text).strip()


def _quote_parts(quote: str) -> list[str]:
    """A quote may skip words with "..."; each remaining piece must appear, in order."""
    pieces = re.split(r"\.\.\.|…", normalize(quote))
    return [p.strip(" .,;:!?\"'") for p in pieces if len(p.strip(" .,;:!?\"'")) >= 3]


def _found_in_order(parts: list[str], text: str) -> bool:
    start = 0
    for part in parts:
        at = text.find(part, start)
        if at < 0:
            return False
        start = at + len(part)
    return bool(parts)


# --- numbers -------------------------------------------------------------------------

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90}
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
_DIGITS = re.compile(
    r"(?P<num>\d[\d,]*(?:\.\d+)?)"
    r"(?:\s?(?P<suffix>[kmb])(?![a-z0-9])|\s+(?P<scale>hundred|thousand|million|billion)(?![a-z]))?"
    r"(?![a-z0-9])",
    re.I,
)
_SUFFIX = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}


def numbers_in(text: str) -> set[float]:
    """Every number in the text as a value: 40, 40%, "forty percent", 10k, 1.2M, 10,000,
    2 million."""
    text = str(text or "").lower()
    found: set[float] = set()
    for match in _DIGITS.finditer(text):
        digits = re.sub(r"[^\d.]", "", match.group("num"))
        if not digits:
            continue
        try:
            value = float(digits)
        except ValueError:
            continue
        if match.group("suffix"):
            value *= _SUFFIX[match.group("suffix")]
        elif match.group("scale"):
            value *= _SCALES[match.group("scale")]
        found.add(value)
    # Number words: "twenty five", "two hundred", "three thousand".
    total, current, in_number = 0, 0, False
    for word in re.findall(r"[a-z]+", text) + [""]:
        if word in _UNITS:
            current += _UNITS[word]
            in_number = True
        elif word in _TENS:
            current += _TENS[word]
            in_number = True
        elif word in _SCALES and in_number:
            if word == "hundred":
                current = (current or 1) * 100
            else:
                total += (current or 1) * _SCALES[word]
                current = 0
        else:
            if in_number:
                found.add(float(total + current))
            total, current, in_number = 0, 0, False
    return found


# --- step 3: facts -------------------------------------------------------------------

def check_facts(facts: list[dict], story: list[dict]) -> tuple[list[dict], list[dict]]:
    """(kept, dropped). A kept fact gets the id of the story chunk its quote came from.

    story: [{"id", "text", ...}]. A dropped entry is {"fact", "reason"}.
    """
    chunks = [(str(c.get("id") or ""), normalize(c.get("text"))) for c in story]
    kept: list[dict] = []
    dropped: list[dict] = []
    for fact in facts:
        content = str(fact.get("content") or "").strip()
        quote = str(fact.get("quote") or "").strip()
        if not content:
            dropped.append({"fact": fact, "reason": "empty fact"})
            continue
        parts = _quote_parts(quote)
        if not parts:
            dropped.append({"fact": fact, "reason": "no usable quote"})
            continue
        source = next((cid for cid, text in chunks if _found_in_order(parts, text)), None)
        if source is None:
            dropped.append({"fact": fact, "reason": "quote is not in the story"})
            continue
        invented = sorted(numbers_in(content) - numbers_in(quote))
        if invented:
            dropped.append({
                "fact": fact,
                "reason": f"number not in its quote: {_show(invented)}",
            })
            continue
        kind = fact.get("kind") if fact.get("kind") in FACT_KINDS else "unsorted"
        owner = fact.get("owner") if fact.get("owner") in FACT_OWNERS else "unclear"
        kept.append({**fact, "content": content, "quote": quote,
                     "kind": kind, "owner": owner, "storyId": source})
    return kept, dropped


def _show(values) -> str:
    return ", ".join(f"{v:g}" for v in values)


# --- step 5: points ------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#.']*")
_SELF = re.compile(r"(?<![\w/])(?:I|[Ww]e|[Mm]y|[Oo]ur|[Uu]s|[Mm]e)(?![\w/'])")


def _tool_like(token: str, first: bool) -> bool:
    """A word that names a tool, product or proper noun, judged by its shape."""
    bare = token.rstrip(".")
    if not bare:
        return False
    if any(ch.isdigit() for ch in bare) or "+" in bare or "#" in bare:
        return True
    if "." in bare:  # Node.js
        return True
    if any(ch.isupper() for ch in bare[1:]):  # AWS, PostgreSQL, FastAPI
        return True
    return bare[0].isupper() and not first


def check_point(
    point: dict,
    facts: list[dict],
    allowed_terms: list[str] | tuple[str, ...] = (),
) -> list[dict]:
    """Issues with one written point. `facts` are the kept facts, `allowed_terms` names
    that may appear without a fact (the entry's own company, title or project name)."""
    issues: list[dict] = []
    content = str(point.get("content") or "").strip()
    cited_ids = list(point.get("supportedBy") or [])
    by_id = {f.get("id"): f for f in facts}
    cited = [by_id[i] for i in cited_ids if i in by_id]

    if not content:
        return [issue("empty", "The point is empty.")]
    if not cited_ids:
        issues.append(issue("no_supporting_fact", "The point cites no fact."))
    for fid in cited_ids:
        if fid not in by_id:
            issues.append(issue("unknown_fact", f"The point cites a fact that does not exist: {fid}."))

    evidence = normalize(" ".join(
        f"{f.get('content', '')} {f.get('quote', '')}" for f in cited
    ))
    allowed = normalize(" ".join(allowed_terms))

    words = content.split()
    if len(words) > MAX_WORDS:
        issues.append(issue("too_long", f"{len(words)} words; keep points under {MAX_WORDS}."))
    if len(words) < MIN_WORDS:
        issues.append(issue("too_short", "The point is too short to say anything."))

    first = re.sub(r"[^a-z-]", "", words[0].lower())
    if first in WEAK_STARTS or first.endswith("ing"):
        issues.append(issue("weak_start", f"Starts with \"{words[0]}\"; start with what was done."))
    if _SELF.search(content):
        issues.append(issue("first_person", "Resume points do not use I, we, my or our."))

    evidence_numbers: set[float] = set()
    for f in cited:
        evidence_numbers |= numbers_in(f.get("content")) | numbers_in(f.get("quote"))
    unsupported_numbers = sorted(numbers_in(content) - evidence_numbers)
    if unsupported_numbers:
        issues.append(issue(
            "number_not_in_facts",
            f"Number not in the cited facts: {_show(unsupported_numbers)}.",
        ))

    seen: set[str] = set()
    for index, match in enumerate(_WORD.finditer(content)):
        token = match.group(0).strip("'")
        lowered = normalize(token.rstrip("."))
        if lowered in seen or not _tool_like(token, index == 0):
            continue
        seen.add(lowered)
        if lowered not in evidence and lowered not in allowed:
            issues.append(issue("tool_not_in_facts", f"\"{token.rstrip('.')}\" is not in the cited facts."))

    lowered_content = normalize(content)
    for word in BOASTFUL_WORDS:
        if re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", lowered_content) and word not in evidence:
            issues.append(issue("boastful_term", f"\"{word}\" is not backed by the cited facts."))

    claims_ownership = (
        first in OWNERSHIP_CLAIMS
        or any(w in OWNERSHIP_CLAIMS for w in re.findall(r"[a-z-]+", lowered_content))
    )
    if claims_ownership and cited and not any(f.get("owner") == "me" for f in cited):
        issues.append(issue(
            "ownership_not_in_facts",
            "Claims leadership or sole credit, but no cited fact says the person did it.",
        ))
    return issues


def check_points(
    points: list[dict],
    facts: list[dict],
    allowed_terms: list[str] | tuple[str, ...] = (),
) -> dict:
    """{"perPoint": [issues for each point], "listIssues": [...]}."""
    list_issues: list[dict] = []
    if not points:
        list_issues.append(issue("no_points", "No points were written."))
    if len(points) > MAX_POINTS:
        list_issues.append(issue("too_many_points", f"{len(points)} points; at most {MAX_POINTS}."))
    seen: dict[str, int] = {}
    for index, point in enumerate(points):
        key = normalize(point.get("content"))
        if key in seen:
            list_issues.append(issue("duplicate", f"Points {seen[key] + 1} and {index + 1} are the same."))
        seen.setdefault(key, index)
    return {
        "perPoint": [check_point(p, facts, allowed_terms) for p in points],
        "listIssues": list_issues,
    }
