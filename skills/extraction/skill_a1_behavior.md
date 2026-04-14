# Skill A1 — Behavior Pattern Extraction

## What to Extract
How Chatzi communicates — dialogue acts, communication style, correction patterns, decision patterns, how he reveals information.

## 1. DIALOGUE ACTS
Classify Chatzi's messages by what he is DOING:
- requesting: asking for information or action
- testing_probing: checking if the AI understood before revealing more
- correcting: reframing, adding missing constraints, redirecting
- confirming: accepting, validating
- expressing_preference: signaling what he wants more or less of
- instructing: setting explicit rules for how to behave
- rejecting: declining, redirecting away
- revealing: strategically sharing new information after setup

For each, provide frequency (none/low/medium/high) and up to 3 Chatzi quotes.

## 2. COMMUNICATION STYLE
Score Chatzi on each (low/medium/high) with his quotes as evidence:
- directness: how bluntly does he communicate?
- detail_level: terse vs verbose messages
- certainty: hedging vs assertive language
- emotional_expression: how much emotion surfaces in his words?
- social_framing: I-focused vs we-focused language

## 3. HOW CHATZI CORRECTS
Quote his exact words when he disagrees or redirects. What does the correction look like?

## 4. HOW CHATZI DECIDES
Quote his words showing: immediate vs deliberate, asks for both sides, stages with fallbacks, tests before committing.

## 5. HOW CHATZI REVEALS INFORMATION
Quote his words showing: tests comprehension before revealing, withholds scope until AI catches up, signals readiness.

## 6. CHATZI'S EXACT PHRASES
Up to 10 direct quotes revealing character — HIS words only.

## Output Schema
```json
{
  "dialogue_acts": {
    "requesting": {"frequency": "none|low|medium|high", "examples": []},
    "testing_probing": {"frequency": "...", "examples": []},
    "correcting": {"frequency": "...", "examples": []},
    "confirming": {"frequency": "...", "examples": []},
    "expressing_preference": {"frequency": "...", "examples": []},
    "instructing": {"frequency": "...", "examples": []},
    "rejecting": {"frequency": "...", "examples": []},
    "revealing": {"frequency": "...", "examples": []}
  },
  "communication_style": {
    "directness": {"score": "...", "evidence": []},
    "detail_level": {"score": "...", "evidence": []},
    "certainty": {"score": "...", "evidence": []},
    "emotional_expression": {"score": "...", "evidence": []},
    "social_framing": {"score": "...", "evidence": []}
  },
  "correction_patterns": [
    {"pattern": "...", "chatzi_quote": "...", "context": "..."}
  ],
  "decision_patterns": [
    {"pattern": "...", "chatzi_quote": "...", "context": "..."}
  ],
  "information_revealing": [
    {"pattern": "...", "chatzi_quote": "...", "context": "..."}
  ],
  "chatzi_phrases": ["up to 10"]
}
```
