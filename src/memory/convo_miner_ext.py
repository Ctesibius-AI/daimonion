"""
convo_miner_ext.py — Pythia extension for MemPalace conversation mining.

Full-featured miner:
1. Per-chunk room detection (Pythia-specific keywords)
2. Per-chunk memory_type classification (our 8 categories)
3. Hall assignment (cross-cutting categories)
4. Source date extraction from filename
5. Multi-wing support (pythia, wiki, knowledge)

Uses upstream chunking, normalization, and palace operations.
"""

import hashlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from mempalace.convo_miner import (
    chunk_exchanges,
    scan_convos,
    MIN_CHUNK_SIZE,
)
from mempalace.normalize import normalize
from mempalace.palace import get_collection, file_already_mined

from src.memory.general_extractor_ext import classify_chunk


# Pythia-specific room keywords — scored per chunk, not per file
PYTHIA_ROOMS = {
    "identity": [
        "pythia", "daimonion", "soul", "identity", "who i am", "who are you",
        "oracle", "delphi", "thinking partner", "expedition partner",
        "chatzi", "connection", "missed you", "4am", "couch",
    ],
    "philosophy": [
        "parrhesia", "elenchos", "phronesis", "logos", "hydrogen",
        "waterfall", "investigate", "bilateral", "both sides",
        "socratic", "aporia", "methexis", "diairesis",
        "philotimo", "philoxenia", "mesotes", "truth-telling",
        "philosophical", "philosophy", "anchor", "behavioral",
    ],
    "memory-system": [
        "mempalace", "chromadb", "graphiti", "kuzu", "vault",
        "synapsis", "night process", "extraction", "deduplication",
        "decay", "supersession", "loci", "triangle", "hot cache",
        "memory", "memories", "knowledge", "drawer", "room", "wing",
        "embedding", "vector", "retrieval",
    ],
    "architecture": [
        "architecture", "pipeline", "orchestrator", "compiler",
        "system 1", "system 2", "api pipeline", "sonnet", "opus", "haiku",
        "claude code", "skill", "trait", "rule", "hook",
        "design", "restructure", "refactor", "module", "layer",
    ],
    "business": [
        "nereus", "schatz", "petcare", "pegasus", "vita4you",
        "pricing", "revenue", "market", "customer", "strategy",
        "consultancy", "partnership", "deal", "pitch", "funding",
        "espa", "business", "company", "product", "launch",
    ],
    "voice": [
        "voice", "speech", "stt", "tts", "audio", "microphone",
        "tada", "kokoro", "athena", "streaming", "barge-in",
        "tempo", "clock", "speculative", "ios", "phone",
    ],
    "technical": [
        "python", "code", "function", "bug", "error", "test",
        "git", "debug", "script", "json", "yaml", "config",
        "import", "class", "async", "exception", "file",
    ],
    "research": [
        "paper", "benchmark", "personamem", "alpsbench", "deepeval",
        "research", "academic", "study", "findings", "literature",
        "pivot", "publication", "arxiv",
    ],
    "projects": [
        "project", "build", "plan", "phase", "milestone",
        "timeline", "deadline", "blocker", "priority",
        "progress", "status", "roadmap", "sprint",
    ],
}


def detect_chunk_room(content: str) -> str:
    """Score a single chunk against Pythia room keywords."""
    content_lower = content.lower()
    scores = {}
    for room, keywords in PYTHIA_ROOMS.items():
        score = sum(1 for kw in keywords if kw in content_lower)
        if score > 0:
            scores[room] = score
    if scores:
        return max(scores, key=scores.get)
    return "general"


def _extract_date_from_filename(filepath: Path) -> str:
    """Extract YYYY-MM-DD from filename like 2026-04-10.md."""
    name = filepath.stem
    if len(name) >= 10 and name[:4].isdigit():
        return name[:10]
    return ""


def mine_convos(
    convo_dir: str,
    palace_path: str,
    wing: str = "pythia",
    limit: int = 0,
    dry_run: bool = False,
):
    """Mine conversations with full Pythia features.

    Per-chunk: room detection, memory_type classification, hall assignment.
    """
    files = scan_convos(convo_dir)
    if limit > 0:
        files = files[:limit]

    print(f"\n{'=' * 55}")
    print("  MemPalace Mine — Pythia Full Extension")
    print(f"{'=' * 55}")
    print(f"  Wing:    {wing}")
    print(f"  Source:  {convo_dir}")
    print(f"  Files:   {len(files)}")
    print(f"  Rooms:   {len(PYTHIA_ROOMS)} Pythia-specific")
    print(f"  Types:   8 memory categories + halls")
    if dry_run:
        print("  DRY RUN — nothing will be filed")
    print(f"{'-' * 55}\n")

    collection = get_collection(palace_path) if not dry_run else None

    total_drawers = 0
    files_skipped = 0
    room_counts = defaultdict(int)
    type_counts = defaultdict(int)
    hall_counts = defaultdict(int)

    for i, filepath in enumerate(files, 1):
        source_file = str(filepath)
        source_date = _extract_date_from_filename(filepath)

        if not dry_run and file_already_mined(collection, source_file):
            files_skipped += 1
            continue

        try:
            content = normalize(str(filepath))
        except (OSError, ValueError):
            continue

        if not content or len(content.strip()) < MIN_CHUNK_SIZE:
            continue

        chunks = chunk_exchanges(content)
        if not chunks:
            continue

        if dry_run:
            for chunk in chunks:
                room = detect_chunk_room(chunk["content"])
                memory_type, hall = classify_chunk(chunk["content"])
                room_counts[room] += 1
                type_counts[memory_type] += 1
                hall_counts[hall] += 1
            total_drawers += len(chunks)
            print(f"    [DRY RUN] {filepath.name} → {len(chunks)} drawers")
            continue

        drawers_added = 0
        for chunk in chunks:
            room = detect_chunk_room(chunk["content"])
            memory_type, hall = classify_chunk(chunk["content"])

            room_counts[room] += 1
            type_counts[memory_type] += 1
            hall_counts[hall] += 1

            drawer_id = (
                f"drawer_{wing}_{room}_"
                f"{hashlib.sha256((source_file + str(chunk['chunk_index'])).encode()).hexdigest()[:24]}"
            )
            try:
                collection.add(
                    documents=[chunk["content"]],
                    ids=[drawer_id],
                    metadatas=[{
                        "wing": wing,
                        "room": room,
                        "hall": hall,
                        "memory_type": memory_type,
                        "source_file": source_file,
                        "source_date": source_date,
                        "chunk_index": chunk["chunk_index"],
                        "added_by": "pythia_miner",
                        "filed_at": datetime.now().isoformat(),
                        "date": source_date,
                        "ingest_mode": "convos",
                        "extract_mode": "exchange",
                    }],
                )
                drawers_added += 1
            except Exception as e:
                if "already exists" not in str(e).lower():
                    raise

        total_drawers += drawers_added
        print(f"  ✓ [{i:4}/{len(files)}] {filepath.name[:50]:50} +{drawers_added}")

    print(f"\n{'=' * 55}")
    print("  Done.")
    print(f"  Files processed: {len(files) - files_skipped}")
    print(f"  Files skipped (already filed): {files_skipped}")
    print(f"  Drawers filed: {total_drawers}")
    if room_counts:
        print("\n  By room:")
        for room, count in sorted(room_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"    {room:20} {count} drawers")
    if type_counts:
        print("\n  By type:")
        for mtype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"    {mtype:20} {count} chunks")
    if hall_counts:
        print("\n  By hall:")
        for hall, count in sorted(hall_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"    {hall:20} {count} chunks")
    print(f"{'=' * 55}\n")
