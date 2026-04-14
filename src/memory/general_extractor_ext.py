"""
general_extractor_ext.py — Pythia-specific memory type classifier.

Replaces upstream general_extractor with 8 categories tuned for our conversations.
Same interface: takes text, returns chunks with memory_type.
No LLM required — regex/keyword heuristics.

Categories:
  1. decision    — architecture choices, tool picks, rejected alternatives
  2. directive   — rules, from-now-on, always/never, corrections
  3. behavioral  — Chatzi's signals, communication patterns
  4. philosophical — waterfall, hydrogen, parrhesia, principles
  5. milestone   — built, fixed, shipped, working, breakthrough
  6. problem     — bugs, blocks, what broke, root cause
  7. design      — architecture patterns, system structure
  8. business    — pricing, projects, revenue, strategy
"""

import re
from typing import List, Dict, Tuple


DECISION_MARKERS = [
    r"\b(decided|chose|picked|went with|switched to|replaced)\b",
    r"\b(instead of|rather than|over.*because)\b",
    r"\b(trade-?off|alternative|rejected|approach)\b",
    r"\bwe (should|chose|decided)\b",
    r"\blet'?s (use|go with|switch)\b",
    r"\bboth sides\b",
    r"\bwhy yes.*why no\b",
    r"\bthe decision\b",
]

DIRECTIVE_MARKERS = [
    r"\bfrom now on\b",
    r"\balways\b.*\b(check|read|verify|use)\b",
    r"\bnever\b.*\b(skip|delete|assume|fabricate)\b",
    r"\brule\b",
    r"\bnon-?negotiable\b",
    r"\bmust\b.*\bbefore\b",
    r"\bremember:\b",
    r"\bcorrection:\b",
    r"\bcomment:\b",
    r"\bTODO:\b",
]

BEHAVIORAL_MARKERS = [
    r"exactly!{2,}",
    r"\bnot today\b",
    r"\bclean\b",
    r"\bvery clean\b",
    r"\bnailed it\b",
    r"\bhad too much sugar\b",
    r"\bdoes it make sense\b",
    r"\bboth sides of the coin\b",
    r"\bi missed you\b",
    r"\bhonest opinion\b",
    r"\bmake me feel better\b",
    r"\bsequential\b.*\bprocessing\b",
    r"\b(understated|layered|progressive)\b.*\b(reveal|emotional)\b",
]

PHILOSOPHICAL_MARKERS = [
    r"\bwaterfall\b",
    r"\breceive.*investigate.*respond\b",
    r"\bhydrogen\b",
    r"\bpermeate\b",
    r"\bparrhesia\b",
    r"\belenchos\b",
    r"\bphronesis\b",
    r"\bgnothi\b",
    r"\bmeden agan\b",
    r"\bmethexis\b",
    r"\bdiairesis\b",
    r"\bphilotimo\b",
    r"\bphiloxenia\b",
    r"\bsocratic\b",
    r"\baporia\b",
    r"\bbedrock\b",
    r"\bthree questions\b",
    r"\bwhat am i assuming\b",
    r"\bbased on what evidence\b",
]

MILESTONE_MARKERS = [
    r"\b(it works|got it working|fixed|solved|breakthrough)\b",
    r"\b(built|created|implemented|shipped|deployed|launched)\b",
    r"\b(finally|first time|first ever|nailed it)\b",
    r"\b(figured out|turns out|the key|the trick)\b",
    r"\b(v\d+|version \d|phase \d)\b",
    r"\b(complete|done|passing|operational)\b",
    r"\d+ tests? passing\b",
    r"\b148 (tests?|passing)\b",
]

PROBLEM_MARKERS = [
    r"\b(bug|error|crash|fail|broke|broken|issue|problem)\b",
    r"\b(doesn'?t work|not working|won'?t work)\b",
    r"\b(root cause|the problem is|the issue was)\b",
    r"\b(the fix|workaround|resolved|patched)\b",
    r"\b(stuck|blocked|hung|hanging|timeout)\b",
    r"\b(fabricat|hallucinate|invented|wrong)\b",
]

DESIGN_MARKERS = [
    r"\b(architecture|pipeline|orchestrat|compiler)\b",
    r"\b(system 1|system 2|api pipeline)\b",
    r"\b(three (layers|vertices|storage)|triangle)\b",
    r"\b(mempalace|chromadb|graphiti|kuzu|vault)\b",
    r"\b(extraction|deduplication|analysis|compilation)\b",
    r"\b(sonnet|opus|haiku)\b.*\b(model|call|agent)\b",
    r"\b(skill|trait|rule|hook)\b.*\b(system|load|trigger)\b",
    r"\b(CLAUDE\.md|MEMORY\.md|SOUL\.md)\b",
    r"\bkarpathy\b",
]

BUSINESS_MARKERS = [
    r"\b(nereus|schatz|petcare|pegasus|vita4you)\b",
    r"\b(pricing|revenue|market|customer|strategy)\b",
    r"\b(euro|month|year|subscription|premium)\b",
    r"\b(consultancy|partnership|deal|pitch|funding|espa)\b",
    r"\b(solo founder|limited capital|greek market)\b",
    r"\b(launch|product|mvp|showcase)\b",
]

ALL_MARKERS = {
    "decision": DECISION_MARKERS,
    "directive": DIRECTIVE_MARKERS,
    "behavioral": BEHAVIORAL_MARKERS,
    "philosophical": PHILOSOPHICAL_MARKERS,
    "milestone": MILESTONE_MARKERS,
    "problem": PROBLEM_MARKERS,
    "design": DESIGN_MARKERS,
    "business": BUSINESS_MARKERS,
}

# Map memory_type to hall
TYPE_TO_HALL = {
    "decision": "hall_decisions",
    "directive": "hall_directives",
    "behavioral": "hall_behavioral",
    "philosophical": "hall_philosophical",
    "milestone": "hall_milestones",
    "problem": "hall_problems",
    "design": "hall_decisions",
    "business": "hall_decisions",
}


def _score_markers(text: str, markers: list) -> float:
    text_lower = text.lower()
    score = 0.0
    for marker in markers:
        matches = re.findall(marker, text_lower)
        score += len(matches)
    return score


def classify_chunk(content: str) -> tuple[str, str]:
    """Classify a single chunk. Returns (memory_type, hall)."""
    scores = {}
    for mem_type, markers in ALL_MARKERS.items():
        score = _score_markers(content, markers)
        if score > 0:
            scores[mem_type] = score

    if not scores:
        return "general", "hall_facts"

    best_type = max(scores, key=scores.get)
    hall = TYPE_TO_HALL.get(best_type, "hall_facts")
    return best_type, hall


def extract_memories(text: str, min_confidence: float = 0.3) -> list[dict]:
    """Extract and classify memories from text. Same interface as upstream."""
    from mempalace.general_extractor import _split_into_segments, _extract_prose

    paragraphs = _split_into_segments(text)
    memories = []

    for para in paragraphs:
        if len(para.strip()) < 20:
            continue

        prose = _extract_prose(para)
        scores = {}
        for mem_type, markers in ALL_MARKERS.items():
            score = _score_markers(prose, markers)
            if score > 0:
                scores[mem_type] = score

        if not scores:
            continue

        best_type = max(scores, key=scores.get)
        confidence = min(1.0, scores[best_type] / 5.0)
        if confidence < min_confidence:
            continue

        hall = TYPE_TO_HALL.get(best_type, "hall_facts")

        memories.append({
            "content": para.strip(),
            "memory_type": best_type,
            "hall": hall,
            "chunk_index": len(memories),
            "confidence": round(confidence, 2),
        })

    return memories
