"""
Real-time MemPalace capture — Stop hook for Claude Code.

After every response, extracts the last user+assistant exchange
and files it as a drawer in MemPalace. Real-time verbatim capture.

Claude Code Stop hook format:
  stdin: {"session_id": "...", "transcript_path": "/path/to/transcript.json", ...}
  stdout: {} (never blocks)
"""

import hashlib
import json
import os
import sys
from datetime import datetime

PALACE_PATH = os.path.expanduser("~/.daimonion/mempalace")
WING = "pythia"


def get_collection():
    """Get or create the MemPalace ChromaDB collection."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=PALACE_PATH)
        return client.get_or_create_collection("mempalace_drawers")
    except Exception:
        return None


def extract_last_exchange(transcript_path: str) -> tuple[str, str]:
    """Extract the last user message and assistant response from transcript."""
    try:
        with open(transcript_path) as f:
            transcript = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return "", ""

    if not isinstance(transcript, list):
        return "", ""

    last_user = ""
    last_assistant = ""

    for msg in reversed(transcript):
        role = msg.get("role", "")
        content = msg.get("content", "")

        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)
            content = "\n".join(texts)

        if not last_assistant and role == "assistant":
            last_assistant = content.strip()
        elif not last_user and role == "user" and last_assistant:
            last_user = content.strip()
            break

    return last_user, last_assistant


def detect_room(text: str) -> str:
    """Simple keyword-based room detection matching MemPalace config."""
    text_lower = text.lower()
    rooms = [
        ("memory-system", ["mempalace", "chromadb", "graphiti", "kuzu", "synapsis",
                           "extraction", "decay", "loci", "triangle", "vault",
                           "embedding", "retrieval"]),
        ("architecture", ["architecture", "pipeline", "orchestrator", "compiler",
                          "system", "skill", "design", "module"]),
        ("philosophy", ["parrhesia", "elenchos", "phronesis", "waterfall",
                        "hydrogen", "bilateral", "socratic", "anchor"]),
        ("business", ["nereus", "schatz", "petcare", "pegasus", "pricing",
                      "revenue", "market", "strategy", "business"]),
        ("voice", ["voice", "speech", "stt", "tts", "audio", "kokoro",
                   "streaming"]),
        ("technical", ["python", "code", "function", "bug", "error", "test",
                       "git", "debug", "script", "json"]),
        ("research", ["paper", "benchmark", "research", "academic", "arxiv",
                      "karpathy"]),
        ("projects", ["project", "build", "plan", "phase", "milestone",
                      "timeline", "deadline", "blocker", "priority"]),
        ("identity", ["pythia", "daimonion", "oracle", "identity", "soul",
                      "chatzi", "connection"]),
    ]

    best_room = "general"
    best_score = 0

    for room, keywords in rooms:
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_room = room

    return best_room


def file_exchange(col, user_msg: str, assistant_msg: str):
    """File a single exchange as a MemPalace drawer."""
    content = f"**User**: {user_msg}\n**Pythia**: {assistant_msg}"

    # Skip trivial exchanges
    if len(content) < 50:
        return

    now = datetime.now()
    room = detect_room(content)
    drawer_id = (
        f"drawer_{WING}_{room}_"
        f"{hashlib.sha256((WING + room + content[:100]).encode()).hexdigest()[:24]}"
    )

    # Idempotency check
    try:
        existing = col.get(ids=[drawer_id])
        if existing and existing["ids"]:
            return
    except Exception:
        pass

    try:
        date_str = now.strftime("%Y-%m-%d")
        col.upsert(
            ids=[drawer_id],
            documents=[content],
            metadatas=[{
                "wing": WING,
                "room": room,
                "hall": "hall_facts",
                "source_file": f"realtime_{date_str}",
                "source_date": date_str,
                "date": date_str,
                "chunk_index": 0,
                "added_by": "realtime_hook",
                "memory_type": "general",
                "ingest_mode": "convos",
                "extract_mode": "exchange",
                "filed_at": now.isoformat(),
            }],
        )
    except Exception:
        pass


def main():
    """Entry point for Stop hook. Capture exchange, never block."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({}))
            sys.exit(0)

        data = json.loads(raw)
        transcript_path = data.get("transcript_path", "")

        if not transcript_path:
            print(json.dumps({}))
            sys.exit(0)

        user_msg, assistant_msg = extract_last_exchange(transcript_path)

        if user_msg and assistant_msg:
            col = get_collection()
            if col:
                file_exchange(col, user_msg, assistant_msg)

    except Exception:
        pass

    # Never block
    print(json.dumps({}))
    sys.exit(0)


if __name__ == "__main__":
    main()
