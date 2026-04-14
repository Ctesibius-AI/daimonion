"""
Response Validator — Stop hook for Claude Code.

Runs automatically before every response is delivered.
Checks for verbosity, προπέτεια (rash assent), comfort theater, and anchor violations.

Claude Code Stop hook format:
  stdin: {"session_id": "...", "transcript_path": "/path/to/transcript.json", ...}
  stdout: {"decision": "block", "stopReason": "..."} to block
  stdout: {} to allow

Reads transcript, extracts last assistant message, validates it.
"""

import json
import re
import sys


# ─── Violation Checkers ─────────────────────────────────────────────

def check_verbosity(text: str) -> str | None:
    """Flag responses over 150 words that aren't code blocks or lists."""
    # Strip code blocks — those get a pass
    stripped = re.sub(r'```[\s\S]*?```', '', text)
    # Strip lines that are list items or table rows — structured content is fine
    lines = [l for l in stripped.split('\n')
             if l.strip() and not l.strip().startswith(('-', '|', '#', '>'))]
    prose = ' '.join(lines)
    word_count = len(prose.split())

    if word_count > 150:
        return (
            f'VERBOSE ({word_count} words of prose). '
            f'Target: under 100 words unless actively building together. '
            f'Cut to the key point.'
        )
    return None


def check_propeteia(text: str) -> str | None:
    """Flag rash assent (προπέτεια) — jumping from φαντασία to νόησις without ἐξέτασις."""
    patterns = [
        (r"(?i)^you'?re (absolutely |totally |completely )?right", 'Assent before examination'),
        (r'(?i)^(great|excellent|fantastic|wonderful|brilliant) (question|point|observation|insight)', 'Flattery replacing examination'),
        (r'(?i)^that\'?s a (great|excellent|really good|fantastic) (point|idea|approach|suggestion)', 'Flattery replacing examination'),
        (r'(?i)^I (completely |totally |fully )?agree', 'Assent before examination'),
        (r'(?i)^absolutely[!.]', 'Empty affirmation — no ἐξέτασις'),
    ]

    first_line = text.strip().split('\n')[0] if text.strip() else ''

    for pattern, label in patterns:
        if re.search(pattern, first_line):
            return (
                f'ΠΡΟΠΕΤΕΙΑ: {label}. '
                f'Name the φαντασία, perform ἐξέτασις, then speak from νόησις. '
                f'If you agree, show what examination led there.'
            )
    return None


def check_comfort_theater(text: str) -> str | None:
    """Flag performative empathy — the partner explicitly rejects this."""
    patterns = [
        r'(?i)that must be (hard|difficult|tough|challenging|frustrating)',
        r'(?i)I (can )?(understand|imagine|appreciate) how (you feel|that feels|difficult)',
        r'(?i)I\'?m (so )?sorry (to hear|you\'?re going through|that happened)',
        r'(?i)that sounds (really )?(tough|hard|difficult|challenging)',
        r'(?i)I hear you',
        r'(?i)your feelings are (valid|completely valid|understandable)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return (
                f'COMFORT THEATER: "{match.group()}". '
                f'Partner rejects performative empathy. '
                f'Engage with the substance, not the emotion.'
            )
    return None


def check_filler(text: str) -> str | None:
    """Flag filler phrases that add nothing."""
    patterns = [
        (r'(?i)\bthat\'?s an (interesting|intriguing|fascinating) (question|thought|perspective)\b', 'Filler compliment'),
        (r'(?i)\bI appreciate you (sharing|asking|bringing)\b', 'Performative gratitude'),
        (r'(?i)\blet me (just )?unpack that\b', 'Filler preamble'),
        (r'(?i)\bthat\'?s a (fair|valid|good) (point|concern)\b', 'Bridge to capitulation'),
    ]

    for pattern, label in patterns:
        if re.search(pattern, text):
            return (
                f'FILLER: {label}. '
                f'Cut it. Say the thing.'
            )
    return None


def check_trailing_summary(text: str) -> str | None:
    """Flag trailing summaries — partner can read the output himself."""
    lines = text.strip().split('\n')
    if len(lines) < 5:
        return None

    last_lines = '\n'.join(lines[-3:]).lower()

    patterns = [
        r'(?i)in summary',
        r'(?i)to summarize',
        r'(?i)to recap',
        r'(?i)so (in total|overall|to sum up)',
        r'(?i)here\'?s what (we|I) (did|accomplished|built|changed)',
    ]

    for pattern in patterns:
        if re.search(pattern, last_lines):
            return (
                'TRAILING SUMMARY. '
                'Partner reads the output. Don\'t narrate what you just did.'
            )
    return None


def check_over_apologizing(text: str) -> str | None:
    """Flag elaborate apologies — acknowledge, correct, move."""
    patterns = [
        r'(?i)I (sincerely |truly )?apologize for',
        r'(?i)I\'?m (really |truly |so )?sorry,? (I |that I |for )',
        r'(?i)you\'?re (absolutely )?right,? I should have',
        r'(?i)my (mistake|apologies|bad),? I should have',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return (
                f'OVER-APOLOGIZING: "{match.group()}". '
                f'Acknowledge, correct, move. No elaboration.'
            )
    return None


# ─── Main ───────────────────────────────────────────────────────────

CHECKERS = [
    check_propeteia,
    check_comfort_theater,
    check_filler,
    check_over_apologizing,
    check_trailing_summary,
    check_verbosity,
]


def validate(text: str) -> list[str]:
    """Run all checks. Return list of violation messages."""
    violations = []
    for checker in CHECKERS:
        result = checker(text)
        if result:
            violations.append(result)
    return violations


def extract_last_assistant_message(transcript_path: str) -> str:
    """Read transcript JSON and extract the last assistant message text."""
    try:
        with open(transcript_path) as f:
            transcript = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return ''

    # Transcript is a list of message objects
    # Walk backwards to find the last assistant message
    if isinstance(transcript, list):
        for msg in reversed(transcript):
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                if isinstance(content, str):
                    return content
                # Content might be a list of blocks
                if isinstance(content, list):
                    texts = []
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            texts.append(block.get('text', ''))
                        elif isinstance(block, str):
                            texts.append(block)
                    return '\n'.join(texts)
    return ''


def main():
    """Entry point for Stop hook. Reads from stdin, validates, exits."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            # No input — allow
            print(json.dumps({}))
            sys.exit(0)

        data = json.loads(raw)

        # Prevent infinite loops — if another stop hook already triggered, skip
        if data.get('stop_hook_active'):
            print(json.dumps({}))
            sys.exit(0)

        # Extract last assistant message from transcript
        transcript_path = data.get('transcript_path', '')
        if not transcript_path:
            print(json.dumps({}))
            sys.exit(0)

        response = extract_last_assistant_message(transcript_path)
        if not response:
            print(json.dumps({}))
            sys.exit(0)

        violations = validate(response)

        if violations:
            feedback = '\n'.join(f'⚠ {v}' for v in violations)
            # Block: return decision with stopReason
            result = {
                'decision': 'block',
                'stopReason': feedback
            }
            print(json.dumps(result))
            sys.exit(0)

        # Clean — allow
        print(json.dumps({}))
        sys.exit(0)

    except json.JSONDecodeError:
        print(json.dumps({}))
        sys.exit(0)
    except Exception as e:
        # Validator errors should never block responses
        print(json.dumps({'systemMessage': f'Validator error: {e}'}))
        sys.exit(0)


if __name__ == '__main__':
    main()
