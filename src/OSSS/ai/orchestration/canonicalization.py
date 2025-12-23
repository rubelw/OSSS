import re
from typing import Optional

DCG_CANON = "Dallas Center-Grimes School District"

def canonicalize_dcg(text: str) -> str:
    # Replace DCG as a standalone token (case-insensitive)
    return re.sub(r"\bDCG\b", DCG_CANON, text, flags=re.IGNORECASE)

def _strip_wrapping_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1].strip()
    return s

def extract_refined_question(raw: str) -> str:
    """
    HARD GUARD: Reduce refiner output to a single refined question.

    Handles common "blob" patterns like:
      - "Reframed Query: \"...\""
      - "Refined query: ... Here's a refined version: ... Reframed Query: \"...\""
      - A single quoted question somewhere in the text
    Falls back to: first non-empty non-meta line.
    """
    if not raw:
        return ""

    text = raw.strip()

    # 1) Prefer explicit "Reframed Query:" line
    m = re.search(r"(?im)^\s*Reframed\s*Query\s*:\s*(.+?)\s*$", text)
    if m:
        return _strip_wrapping_quotes(m.group(1))

    # 2) Prefer explicit "Refined query:" line (but only the part after colon)
    m = re.search(r"(?im)^\s*Refined\s*query\s*:\s*(.+?)\s*$", text)
    if m:
        candidate = _strip_wrapping_quotes(m.group(1))
        # If it still looks like meta ("I will refine..."), keep searching below
        if not re.match(r"(?i)^\s*i\s+will\s+refine\b", candidate):
            return candidate

    # 3) Look for the first quoted question-like chunk (common in your logs)
    #    This is intentionally conservative: grabs a quote containing a "?"
    qm = re.search(r"\"([^\"]{5,300}\?)\"", text)
    if qm:
        return qm.group(1).strip()

    # 4) Look for "List ..." / "Show ..." / question-like sentences after labels
    m = re.search(
        r"(?is)(?:Reframed\s*Query|Refined\s*Query|Final\s*Query)\s*:\s*\"?(.+?)\"?\s*(?:\n|$)",
        text,
    )
    if m:
        return _strip_wrapping_quotes(m.group(1))

    # 5) Fallback: first non-empty line that isn't obviously meta/header
    for line in (ln.strip() for ln in text.splitlines()):
        if not line:
            continue
        if re.match(r"(?i)^(refined\s*query|reframed\s*query|here'?s|this\s+refinement|introduction|##|###)\b", line):
            continue
        return _strip_wrapping_quotes(line)

    return _strip_wrapping_quotes(text)
