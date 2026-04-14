"""
Verbatim Capture — Stop hook that stores conversation turns in MemPalace.

Runs as a Claude Code Stop hook alongside the response validator.
Reads the transcript, extracts the last user+assistant exchange,
and files it as a MemPalace drawer via direct ChromaDB write.

Does NOT block — always exits 0 with empty JSON.
Capture failures are logged but never prevent response delivery.
"""

import json
import os
import sys
from datetime import datetime, timezone


def extract_last_exchange(transcript_path: str) -> dict | None:
    """Extract the last user message + assistant response from transcript."""
    try:
        with open(transcript_path) as f:
            if transcript_path.endswith('.jsonl'):
                transcript = []
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            transcript.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            else:
                transcript = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    if not isinstance(transcript, list):
        return None

    last_user = None
    last_assistant = None

    for entry in reversed(transcript):
        # JSONL format: type is top-level, role+content inside message
        entry_type = entry.get('type', '')
        message = entry.get('message', {})
        if not message:
            # Fall back to top-level role/content for plain JSON transcripts
            role = entry.get('role', '')
            content = entry.get('content', '')
        else:
            role = message.get('role', '')
            content = message.get('content', '')

        # Map entry type to role when role not in message
        if not role and entry_type in ('user', 'human'):
            role = 'user'
        elif not role and entry_type == 'assistant':
            role = 'assistant'

        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'text':
                    texts.append(block.get('text', ''))
                elif isinstance(block, str):
                    texts.append(block)
            content = '\n'.join(texts)

        if not content or not isinstance(content, str):
            continue

        if role == 'assistant' and last_assistant is None:
            last_assistant = content
        elif role == 'user' and last_assistant is not None and last_user is None:
            last_user = content
            break

    if not last_user or not last_assistant:
        return None

    return {
        'user': last_user,
        'assistant': last_assistant,
    }


def store_in_chromadb(exchange: dict):
    """Write the exchange directly to MemPalace's ChromaDB collection."""
    try:
        import chromadb
    except ImportError:
        return

    palace_path = os.path.expanduser('~/.daimonion/mempalace')
    if not os.path.exists(palace_path):
        return

    client = chromadb.PersistentClient(path=palace_path)
    collection = client.get_or_create_collection('mempalace_drawers')

    now = datetime.now(timezone.utc)
    drawer_id = f'verbatim_{now.strftime("%Y%m%d_%H%M%S")}_{os.getpid()}'

    verbatim = f"User: {exchange['user']}\n\nAssistant: {exchange['assistant']}"

    collection.add(
        ids=[drawer_id],
        documents=[verbatim],
        metadatas=[{
            'wing': 'pythia',
            'room': 'conversations',
            'timestamp': now.isoformat(),
            'epoch': int(now.timestamp()),
            'source': 'claude-code-stop-hook',
            'added_by': 'verbatim_capture',
        }],
    )


def main():
    """Entry point for Stop hook. Capture verbatim, never block."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({}))
            sys.exit(0)

        data = json.loads(raw)

        # Don't double-capture if another stop hook already active
        if data.get('stop_hook_active'):
            print(json.dumps({}))
            sys.exit(0)

        transcript_path = data.get('transcript_path', '')
        if not transcript_path:
            print(json.dumps({}))
            sys.exit(0)

        exchange = extract_last_exchange(transcript_path)
        if not exchange:
            # Fallback: use last_assistant_message from hook payload
            last_msg = data.get('last_assistant_message', '')
            if last_msg:
                exchange = {'user': '(not captured)', 'assistant': last_msg}
        if exchange:
            store_in_chromadb(exchange)

    except Exception:
        pass

    # Never block
    print(json.dumps({}))
    sys.exit(0)


if __name__ == '__main__':
    main()
