"""
wiki_compiler.py — Karpathy-style wiki compilation for Synapsis.

Takes extraction output (memories, entities, directives, signals, analysis)
and compiles proper wiki pages: entities, concepts, decisions.
Cross-links with [[wikilinks]], updates index.md, appends to log.md.

One Sonnet call per day to produce all wiki updates.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import anthropic

from src.config import SONNET_MODEL, VAULT_DIR

logger = logging.getLogger('daimonion.wiki_compiler')

WIKI_COMPILER_PROMPT = """You are compiling a Karpathy-style wiki from conversation extractions.

You receive: today's extracted memories, entities, directives, signals, and analysis from a day of conversation between Chatzi (human) and Pythia (AI thinking partner).

Your job: produce wiki page updates. Each page is a standalone markdown file.

## Output Format

Return a JSON object with this structure:
```json
{
  "pages": [
    {
      "path": "entities/pythia.md",
      "title": "Pythia",
      "content": "# Pythia\\n\\nPythia is the AI thinking partner...\\n\\n## Related\\n- [[Daimonion]]\\n- [[Chatzi]]",
      "action": "create" or "update"
    }
  ],
  "index_entries": [
    {"path": "entities/pythia.md", "title": "Pythia", "summary": "AI thinking partner, Oracle of Delphi reborn"}
  ],
  "log_entry": "Ingested 2026-04-08: 20 memories, 12 entities. Created 8 pages, updated 5."
}
```

## Page Types

### entities/ — One page per person, tool, system, organization
- Who/what is this?
- Key facts (with dates)
- Relationships to other entities → [[wikilinks]]
- Status (active, deprecated, planned)

### concepts/ — One page per idea, pattern, principle, method
- What is this concept?
- Where did it come from? (quote if available)
- How does it work operationally?
- Related concepts → [[wikilinks]]

### decisions/ — One page per significant decision
- What was decided?
- Why? What alternatives were rejected?
- Date and context
- Related entities/concepts → [[wikilinks]]

### projects/ — One page per project
- Current status
- Key milestones
- Related decisions → [[wikilinks]]

### research/ — One page per research topic
- Findings
- Sources
- Relevance to Daimonion

## Rules

1. **Cross-link aggressively.** Every entity mention in any page should be a [[wikilink]].
2. **Accumulate, don't replace.** If a page exists, ADD new information. Don't rewrite from scratch.
3. **Date everything.** Facts should carry dates: "Switched to Opus (2026-04-03)."
4. **Be specific.** "Revenue target 250-300 euro/month" not "premium pricing."
5. **One page per entity.** Don't merge. Pythia, Daimonion, and Synapsis are three separate entities.
6. **Skip trivial entities.** Not every noun needs a page. Focus on recurring, meaningful entities.
7. **Decisions need rationale.** "Chose X over Y because Z." Always.
"""

EXISTING_PAGES_PROMPT = """## Existing Wiki Pages

The following pages already exist. When producing updates, INCLUDE their existing content and ADD to it. Do not drop existing facts.

{existing_pages}
"""


async def compile_wiki(
    client: anthropic.AsyncAnthropic | None = None,
    extract_output: dict | None = None,
    dedup_output: dict | None = None,
    analyze_output: dict | None = None,
    research_output: dict | None = None,
    target_date: str | None = None,
    model: str = SONNET_MODEL,
) -> dict:
    """Compile wiki pages from extraction output.

    Returns dict with pages created, updated, and total.
    """
    if client is None:
        client = anthropic.AsyncAnthropic()

    date = target_date or datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # Build input from all extraction outputs
    sections = []

    sections.append(f'## Date: {date}')

    # Memories
    memories = (dedup_output or {}).get('memories', [])
    if memories:
        mem_text = '\n'.join(
            f'- [{m.get("collection", "?")}] {m.get("content", "")}'
            for m in memories
        )
        sections.append(f'## Memories ({len(memories)})\n{mem_text}')

    # Entities from extraction
    entities = (extract_output or {}).get('entities', [])
    if entities:
        ent_text = '\n'.join(
            f'- {e.get("name", "?")}: {e.get("type", "?")} — {e.get("description", "")}'
            if isinstance(e, dict) else f'- {e}'
            for e in entities
        )
        sections.append(f'## Entities ({len(entities)})\n{ent_text}')

    # Directives
    directives = (extract_output or {}).get('directives', [])
    if directives:
        dir_text = '\n'.join(f'- {d}' if isinstance(d, str) else f'- {d.get("content", "")}' for d in directives)
        sections.append(f'## Directives ({len(directives)})\n{dir_text}')

    # Signals (behavioral, relationship, design, philosophy)
    signals = (extract_output or {}).get('signals', {})
    if signals:
        for lens, items in signals.items():
            if items:
                sig_text = '\n'.join(f'- {s}' for s in items)
                sections.append(f'## Signals: {lens}\n{sig_text}')

    # Analysis
    if analyze_output:
        if analyze_output.get('patterns'):
            pat_text = '\n'.join(f'- {p}' for p in analyze_output['patterns'])
            sections.append(f'## Patterns\n{pat_text}')
        if analyze_output.get('pending_decisions'):
            dec_text = '\n'.join(
                f'- {d.get("decision", "?")}: {d.get("context", "")}'
                for d in analyze_output['pending_decisions']
                if isinstance(d, dict)
            )
            sections.append(f'## Pending Decisions\n{dec_text}')
        if analyze_output.get('new_philosophical_entries'):
            phil_text = '\n'.join(
                f'- {p.get("name", "?")}: {p.get("content", "")}'
                if isinstance(p, dict) else f'- {p}'
                for p in analyze_output['new_philosophical_entries']
            )
            sections.append(f'## Philosophical Entries\n{phil_text}')

    # Research results
    if research_output and research_output.get('results'):
        for r in research_output['results']:
            if r.get('status') == 'ok':
                sections.append(f'## Research: {r.get("topic", "?")}\n{r.get("summary", "")}')

    if len(sections) <= 1:
        return {'status': 'ok', 'pages_created': 0, 'pages_updated': 0, 'reason': 'no data'}

    # Load existing wiki pages for context
    existing = _load_existing_pages()
    existing_prompt = ''
    if existing:
        existing_text = '\n\n---\n\n'.join(
            f'### {path}\n{content[:2000]}'
            for path, content in existing.items()
        )
        # Cap to avoid blowing context
        if len(existing_text) > 30000:
            existing_text = existing_text[:30000] + '\n\n[... truncated ...]'
        existing_prompt = EXISTING_PAGES_PROMPT.format(existing_pages=existing_text)

    input_text = '\n\n'.join(sections)

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=16384,
            system=WIKI_COMPILER_PROMPT + '\n\n' + existing_prompt,
            messages=[{'role': 'user', 'content': input_text}],
        )

        result_text = response.content[0].text
        logger.info('Wiki compiler: %d input tokens, %d output tokens',
                     response.usage.input_tokens, response.usage.output_tokens)

        # Parse JSON from response
        wiki_result = _parse_json_response(result_text)
        if not wiki_result or not wiki_result.get('pages'):
            logger.warning('Wiki compiler returned no pages')
            return {'status': 'ok', 'pages_created': 0, 'pages_updated': 0, 'reason': 'no pages in output'}

        # Write pages
        created = 0
        updated = 0
        for page in wiki_result['pages']:
            path = page.get('path', '')
            content = page.get('content', '')
            if not path or not content:
                continue

            full_path = os.path.join(VAULT_DIR, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            action = page.get('action', 'create')
            if os.path.exists(full_path):
                action = 'update'
                updated += 1
            else:
                created += 1

            with open(full_path, 'w') as f:
                f.write(content)
            logger.info('Wiki page %s: %s', action, path)

        # Update index
        index_entries = wiki_result.get('index_entries', [])
        if index_entries:
            _update_index(index_entries)

        # Append to log
        log_entry = wiki_result.get('log_entry', f'Ingested {date}')
        _append_log(date, log_entry)

        return {
            'status': 'ok',
            'pages_created': created,
            'pages_updated': updated,
            'total_pages': created + updated,
        }

    except Exception as e:
        logger.error('Wiki compilation failed: %s', e)
        return {'status': 'error', 'error': str(e)}


def _load_existing_pages() -> dict[str, str]:
    """Load all existing wiki pages for context."""
    pages = {}
    if not os.path.isdir(VAULT_DIR):
        return pages

    for root, _, files in os.walk(VAULT_DIR):
        for fname in files:
            if not fname.endswith('.md'):
                continue
            if fname in ('index.md', 'log.md'):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, VAULT_DIR)
            try:
                with open(full_path) as f:
                    pages[rel_path] = f.read()
            except IOError:
                continue
    return pages


def _update_index(entries: list[dict]):
    """Rewrite index.md with all known pages."""
    index_path = os.path.join(VAULT_DIR, 'index.md')

    # Load existing index entries
    existing_entries = {}
    if os.path.exists(index_path):
        try:
            with open(index_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('- ['):
                        # Parse: - [Title](path) — summary
                        import re
                        m = re.match(r'- \[(.+?)\]\((.+?)\)(?: — (.+))?', line)
                        if m:
                            existing_entries[m.group(2)] = {
                                'title': m.group(1),
                                'path': m.group(2),
                                'summary': m.group(3) or '',
                            }
        except IOError:
            pass

    # Merge new entries
    for entry in entries:
        path = entry.get('path', '')
        if path:
            existing_entries[path] = entry

    # Group by directory
    grouped = {}
    for path, entry in sorted(existing_entries.items()):
        directory = os.path.dirname(path) or 'root'
        grouped.setdefault(directory, []).append(entry)

    # Write index
    lines = ['# Daimonion Wiki — Index\n']
    lines.append(f'*{len(existing_entries)} pages. Auto-maintained by Synapsis.*\n')

    for directory in ['entities', 'concepts', 'projects', 'decisions', 'research', 'daily-briefings']:
        entries_in_dir = grouped.get(directory, [])
        if entries_in_dir:
            lines.append(f'\n## {directory.replace("-", " ").title()}\n')
            for entry in sorted(entries_in_dir, key=lambda e: e.get('title', '')):
                title = entry.get('title', '')
                path = entry.get('path', '')
                summary = entry.get('summary', '')
                if summary:
                    lines.append(f'- [{title}]({path}) — {summary}')
                else:
                    lines.append(f'- [{title}]({path})')

    with open(index_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    logger.info('Index updated: %d entries', len(existing_entries))


def _append_log(date: str, entry: str):
    """Append to log.md."""
    log_path = os.path.join(VAULT_DIR, 'log.md')

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    log_line = f'[{timestamp}] {entry}\n'

    # Read existing, append
    content = ''
    if os.path.exists(log_path):
        with open(log_path) as f:
            content = f.read()

    # Find the ## Log section and append
    if '## Log\n' in content:
        content = content.replace(
            '## Log\n',
            f'## Log\n\n{log_line}',
            1,
        )
    else:
        content += f'\n## Log\n\n{log_line}'

    with open(log_path, 'w') as f:
        f.write(content)


def _parse_json_response(text: str) -> dict | None:
    """Extract JSON from LLM response, handling markdown code blocks."""
    import re

    # Try to find JSON in code block
    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try the whole text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning('Could not parse JSON from wiki compiler response')
    return None
