"""
QA Auditor — Flow verification for Daimonion.

Runs after the Synapsis completes. Checks that data actually moved
through the pipeline, not just that files exist. Findings are saved as
pending items in ~/.daimonion/qa/findings.json.

Morning briefing gets a one-liner: "4 QA findings pending."
Drill in with: pythia_tools.py qa_report
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

import yaml

from src.config import (
    DATA_DIR,
    KNOWLEDGE_DIR,
    MEMORIES_DIR,
    RESEARCH_QUEUE_PATH,
    SKILLS_DIR,
    VAULT_DIR,
)

logger = logging.getLogger('daimonion.qa_auditor')

QA_DIR = os.path.join(DATA_DIR, 'qa')
FINDINGS_PATH = os.path.join(QA_DIR, 'findings.json')

PYTHIA_DIR = os.path.expanduser('~/daimonion-pythia')
CLAUDE_MD_PATH = os.path.join(PYTHIA_DIR, 'CLAUDE.md')
SETTINGS_PATH = os.path.join(PYTHIA_DIR, '.claude', 'settings.json')
SESSIONS_DIR = os.path.join(PYTHIA_DIR, 'docs', 'sessions')


def _finding(check: str, severity: str, detail: str, suggestion: str = '') -> dict:
    return {
        'check': check,
        'severity': severity,
        'detail': detail,
        'suggestion': suggestion,
        'found_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pending',
    }


# ─── Flow Check 1: Research Queue → Researcher ─────────────────────

def check_research_flow(night_result: dict) -> list[dict]:
    """Were queued research topics actually picked up?"""
    findings = []

    if not os.path.exists(RESEARCH_QUEUE_PATH):
        return findings

    try:
        with open(RESEARCH_QUEUE_PATH) as f:
            queue = json.load(f)
    except (json.JSONDecodeError, IOError):
        return findings

    pending = [q for q in queue if q.get('status') == 'pending']
    if not pending:
        return findings

    # Check if researcher ran
    researcher = night_result.get('agents', {}).get('researcher', {})
    if researcher.get('status') == 'skipped':
        findings.append(_finding(
            'research_queue_orphaned',
            'warning',
            f'{len(pending)} topics in research queue were not picked up. '
            f'Researcher was skipped. Topics: {", ".join(q["topic"][:50] for q in pending[:3])}',
            'Check orchestrator — Agent 4 should always run.',
        ))
    elif researcher.get('topics_researched', 0) == 0 and pending:
        findings.append(_finding(
            'research_queue_orphaned',
            'warning',
            f'{len(pending)} topics queued but 0 researched.',
            'Check Brave API key and network connectivity.',
        ))

    return findings


# ─── Flow Check 2: Session Follow-ups → Completion ─────────────────

def check_session_followups() -> list[dict]:
    """Are items from previous session's "what's next" showing progress?"""
    findings = []

    if not os.path.exists(SESSIONS_DIR):
        return findings

    session_files = sorted(
        [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.md')],
        reverse=True,
    )

    if len(session_files) < 2:
        return findings

    # Read the PREVIOUS session (not today's)
    prev_session_path = os.path.join(SESSIONS_DIR, session_files[1])
    try:
        with open(prev_session_path) as f:
            content = f.read()
    except IOError:
        return findings

    # Extract "What's Next" items
    next_section = re.search(
        r"(?:What'?s Next|Next Steps|TODO)(.*?)(?:\n## |\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if not next_section:
        return findings

    items = re.findall(r'^\s*\d+\.\s+(.+)', next_section.group(1), re.MULTILINE)
    if not items:
        items = re.findall(r'^\s*[-*]\s+(.+)', next_section.group(1), re.MULTILINE)

    if len(items) > 0:
        # Check today's session for evidence of completion
        today_path = os.path.join(SESSIONS_DIR, session_files[0])
        today_content = ''
        if os.path.exists(today_path):
            try:
                with open(today_path) as f:
                    today_content = f.read().lower()
            except IOError:
                pass

        orphaned = []
        for item in items:
            # Simple heuristic: check if key words from the item appear in today's session
            keywords = [w.lower() for w in item.split() if len(w) > 4][:3]
            if keywords and not any(kw in today_content for kw in keywords):
                orphaned.append(item.strip()[:80])

        if orphaned:
            findings.append(_finding(
                'session_followups_orphaned',
                'info',
                f'{len(orphaned)} items from previous session "What\'s Next" '
                f'show no evidence of progress: {"; ".join(orphaned[:3])}',
                'Review and either complete, re-queue, or explicitly drop.',
            ))

    return findings


# ─── Flow Check 3: Trait Index ↔ Trait Files ───────────────────────

def check_trait_file_sync() -> list[dict]:
    """Do trait_index.yaml entries point to files that exist, and vice versa?"""
    findings = []

    index_path = os.path.join(SKILLS_DIR, 'meta', 'trait_index.yaml')
    if not os.path.exists(index_path):
        findings.append(_finding(
            'trait_index_missing',
            'critical',
            'trait_index.yaml not found',
        ))
        return findings

    try:
        with open(index_path) as f:
            index = yaml.safe_load(f)
    except (yaml.YAMLError, IOError):
        findings.append(_finding(
            'trait_index_corrupt',
            'critical',
            'trait_index.yaml is unreadable',
        ))
        return findings

    traits = index.get('traits', {})

    # Check: index entry → file exists
    missing_files = []
    for name, config in traits.items():
        path = config.get('path', '')
        full_path = os.path.join(SKILLS_DIR, path)
        if not os.path.exists(full_path):
            missing_files.append(f'{name} → {path}')

    if missing_files:
        findings.append(_finding(
            'trait_index_missing_files',
            'warning',
            f'{len(missing_files)} traits in index point to missing files: '
            f'{"; ".join(missing_files[:5])}',
            'Create the files or remove the index entries.',
        ))

    # Check: trait files on disk → not in index
    registered_paths = {config.get('path', '') for config in traits.values()}
    unregistered = []

    for category in ['traits/thinking', 'traits/communication', 'traits/domains', 'traits/context']:
        category_dir = os.path.join(SKILLS_DIR, category)
        if not os.path.exists(category_dir):
            continue
        for fname in os.listdir(category_dir):
            if fname.endswith('.md'):
                relative = f'{category}/{fname}'
                if relative not in registered_paths:
                    unregistered.append(relative)

    if unregistered:
        findings.append(_finding(
            'trait_files_unregistered',
            'info',
            f'{len(unregistered)} trait files on disk not in trait_index.yaml: '
            f'{"; ".join(unregistered[:5])}',
            'Register them in trait_index.yaml or remove if unused.',
        ))

    return findings


# ─── Flow Check 4: CLAUDE.md ↔ Trait Index ─────────────────────────

def check_claude_md_trait_sync() -> list[dict]:
    """Are traits covered by .claude/skills/ or .claude/rules/?

    Post-restructure: traits live in Claude Code native skills/rules,
    not listed explicitly in CLAUDE.md. Check that skill directories exist.
    """
    findings = []

    # Check that Pythia skills directory exists and has skills
    pythia_skills_dir = os.path.expanduser('~/daimonion-pythia/.claude/skills')
    pythia_rules_dir = os.path.expanduser('~/daimonion-pythia/.claude/rules')

    if not os.path.isdir(pythia_skills_dir):
        findings.append(_finding(
            'skills_dir_missing',
            'warning',
            'No .claude/skills/ directory in daimonion-pythia.',
            'Run BUILD-PLAN-v4 Phase 2 to create skills.',
        ))
        return findings

    skills = [d for d in os.listdir(pythia_skills_dir)
              if os.path.isdir(os.path.join(pythia_skills_dir, d))]
    rules = [f for f in os.listdir(pythia_rules_dir)
             if f.endswith('.md')] if os.path.isdir(pythia_rules_dir) else []

    if len(skills) < 10:
        findings.append(_finding(
            'skills_incomplete',
            'info',
            f'Only {len(skills)} skills found (expected 11). Skills: {", ".join(sorted(skills))}',
            'Check BUILD-PLAN-v4 Phase 2 for missing skills.',
        ))

    if len(rules) < 6:
        findings.append(_finding(
            'rules_incomplete',
            'info',
            f'Only {len(rules)} rules found (expected 7). Rules: {", ".join(sorted(rules))}',
            'Check BUILD-PLAN-v4 Phase 1 for missing rules.',
        ))

    return findings


# ─── Flow Check 5: Validator Hook ↔ Settings ──────────────────────

def check_validator_wiring() -> list[dict]:
    """Is the response validator script wired in settings.json?"""
    findings = []

    validator_path = os.path.expanduser(
        '~/daimonion/src/validators/response_validator.py'
    )
    validator_exists = os.path.exists(validator_path)

    settings_has_hook = False
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            hooks = settings.get('hooks', {})
            stop_hooks = hooks.get('Stop', [])
            for group in stop_hooks:
                for hook in group.get('hooks', []):
                    if 'response_validator' in hook.get('command', ''):
                        settings_has_hook = True
        except (json.JSONDecodeError, IOError):
            pass

    if validator_exists and not settings_has_hook:
        findings.append(_finding(
            'validator_not_wired',
            'warning',
            'response_validator.py exists but is not configured as a Stop hook in settings.json',
            'Add Stop hook entry to .claude/settings.json.',
        ))
    elif settings_has_hook and not validator_exists:
        findings.append(_finding(
            'validator_missing',
            'critical',
            'Stop hook references response_validator.py but the file does not exist',
            'Create the validator script or remove the hook.',
        ))

    return findings


# ─── Flow Check 6: Synapsis Steps → Output ─────────────────

def check_night_step_outputs(night_result: dict) -> list[dict]:
    """Did each Synapsis step produce expected output?"""
    findings = []

    agents = night_result.get('agents', {})

    # Extractor should produce memories
    extractor = agents.get('extractor', {})
    if extractor and not extractor.get('memories') and not extractor.get('error'):
        if extractor.get('duration_ms', 0) > 0:
            findings.append(_finding(
                'extractor_empty',
                'info',
                'Extractor ran but produced no memories. '
                'Was there a conversation today?',
            ))

    # Analyzer should produce patterns
    analyzer = agents.get('analyzer', {})
    if analyzer and analyzer.get('duration_ms', 0) > 0:
        patterns = analyzer.get('patterns', [])
        research_flags = analyzer.get('research_flags', [])
        if not patterns and not research_flags:
            findings.append(_finding(
                'analyzer_empty',
                'info',
                'Analyzer ran but found no patterns and flagged no research.',
            ))

    # Compiler should produce hot cache
    compiler = agents.get('compiler', {})
    if compiler and compiler.get('status') == 'ok':
        from src.config import HOT_CACHE_MD
        if not os.path.exists(HOT_CACHE_MD):
            findings.append(_finding(
                'compiler_no_hot_cache',
                'warning',
                'Compiler reported success but hot_cache.md does not exist.',
            ))

    return findings


# ─── Flow Check 7: Memory → Graph Sync ────────────────────────────

def check_memory_graph_sync() -> list[dict]:
    """Are old memories stuck without graph sync?"""
    findings = []

    if not os.path.exists(MEMORIES_DIR):
        return findings

    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
    old_unsynced = []

    for fname in os.listdir(MEMORIES_DIR):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(MEMORIES_DIR, fname)) as f:
                mem = json.load(f)
            if (not mem.get('_graph_synced')
                    and not mem.get('archived')
                    and mem.get('source_date', '') < cutoff):
                old_unsynced.append(mem.get('memory_id', fname))
        except (json.JSONDecodeError, IOError):
            continue

    if old_unsynced:
        findings.append(_finding(
            'memories_unsynced_old',
            'warning',
            f'{len(old_unsynced)} active memories older than 7 days not synced to graph. '
            f'First 3: {", ".join(old_unsynced[:3])}',
            'Check Graphiti writer. These should have been synced by now.',
        ))

    return findings


# ─── Flow Check 8: Knowledge Supersession ─────────────────────────

def check_knowledge_conflicts() -> list[dict]:
    """Are there knowledge entries that contradict each other, both active?"""
    findings = []

    if not os.path.exists(KNOWLEDGE_DIR):
        return findings

    entries = []
    for fname in os.listdir(KNOWLEDGE_DIR):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(KNOWLEDGE_DIR, fname)) as f:
                entry = json.load(f)
            if entry.get('correction_factor', 1.0) >= 0.8:
                entries.append(entry)
        except (json.JSONDecodeError, IOError):
            continue

    # Group by category, look for same-topic entries
    by_category: dict[str, list] = {}
    for entry in entries:
        cat = entry.get('category', 'unknown')
        by_category.setdefault(cat, []).append(entry)

    for cat, cat_entries in by_category.items():
        if len(cat_entries) < 2:
            continue
        # Simple overlap detection: entries with >50% word overlap in fact text
        for i, a in enumerate(cat_entries):
            a_words = set(a.get('fact', '').lower().split())
            if len(a_words) < 3:
                continue
            for b in cat_entries[i + 1:]:
                b_words = set(b.get('fact', '').lower().split())
                if len(b_words) < 3:
                    continue
                overlap = len(a_words & b_words) / min(len(a_words), len(b_words))
                if overlap > 0.5:
                    findings.append(_finding(
                        'knowledge_possible_conflict',
                        'info',
                        f'Possible conflicting knowledge entries (both active, '
                        f'{overlap:.0%} word overlap): '
                        f'"{a.get("fact", "")[:60]}" vs "{b.get("fact", "")[:60]}"',
                        'Review and supersede the outdated one (correction_factor → 0.3).',
                    ))

    return findings


# ─── Flow Check 9: Skill File Format Compliance ──────────────────

def check_skill_format() -> list[dict]:
    """Do skill files have required sections?"""
    findings = []

    # Philosophical traits: need WHY, HOW, FAILURE LOOKS LIKE, CARE LOOKS LIKE
    phil_traits_dir = os.path.join(SKILLS_DIR, 'philosophy', 'traits')
    if os.path.exists(phil_traits_dir):
        required = ['## WHY', '## HOW', '## FAILURE LOOKS LIKE', '## CARE LOOKS LIKE']
        for fname in os.listdir(phil_traits_dir):
            if not fname.endswith('.md'):
                continue
            fpath = os.path.join(phil_traits_dir, fname)
            try:
                with open(fpath) as f:
                    content = f.read()
            except IOError:
                continue
            missing = [r for r in required if r not in content]
            if missing:
                findings.append(_finding(
                    'skill_format_incomplete',
                    'info',
                    f'Philosophical trait {fname} missing sections: '
                    f'{", ".join(missing)}',
                    'Add the missing sections to follow the WHY/HOW/FAILURE/CARE format.',
                ))

    # Behavioral traits with WHY/HOW/FAILURE/CARE format
    for subdir in ['traits/communication', 'traits/thinking']:
        trait_dir = os.path.join(SKILLS_DIR, subdir)
        if not os.path.exists(trait_dir):
            continue
        for fname in os.listdir(trait_dir):
            if not fname.endswith('.md'):
                continue
            fpath = os.path.join(trait_dir, fname)
            try:
                with open(fpath) as f:
                    content = f.read()
            except IOError:
                continue
            # Behavioral traits with WHY section should have the full format
            if '## WHY' in content:
                required = ['## WHY', '## HOW', '## FAILURE LOOKS LIKE', '## CARE LOOKS LIKE']
                missing = [r for r in required if r not in content]
                if missing:
                    findings.append(_finding(
                        'skill_format_incomplete',
                        'info',
                        f'Behavioral trait {subdir}/{fname} has WHY but missing: '
                        f'{", ".join(missing)}',
                    ))

    return findings


# ─── Main Entry Point ─────────────────────────────────────────────

ALL_CHECKS = [
    ('research_flow', check_research_flow, True),
    ('session_followups', check_session_followups, False),
    ('trait_file_sync', check_trait_file_sync, False),
    ('claude_md_sync', check_claude_md_trait_sync, False),
    ('validator_wiring', check_validator_wiring, False),
    ('night_steps', check_night_step_outputs, True),
    ('memory_graph_sync', check_memory_graph_sync, False),
    ('knowledge_conflicts', check_knowledge_conflicts, False),
    ('skill_format', check_skill_format, False),
]


def run_audit(night_result: dict | None = None) -> dict:
    """Run all QA checks. Called after Synapsis completes.

    Args:
        night_result: The Synapsis's result dict (optional for standalone runs).

    Returns:
        Audit report with findings.
    """
    night_result = night_result or {}
    all_findings = []

    for name, checker, needs_night in ALL_CHECKS:
        try:
            if needs_night:
                results = checker(night_result)
            else:
                results = checker()
            all_findings.extend(results)
            logger.info('QA check %s: %d findings', name, len(results))
        except Exception as e:
            logger.error('QA check %s failed: %s', name, e)
            all_findings.append(_finding(
                f'{name}_error',
                'warning',
                f'QA check {name} itself failed: {e}',
            ))

    report = {
        'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'findings': all_findings,
        'summary': {
            'total': len(all_findings),
            'critical': sum(1 for f in all_findings if f['severity'] == 'critical'),
            'warning': sum(1 for f in all_findings if f['severity'] == 'warning'),
            'info': sum(1 for f in all_findings if f['severity'] == 'info'),
        },
    }

    # Save findings
    _save_findings(all_findings)

    # Save full report
    os.makedirs(QA_DIR, exist_ok=True)
    report_path = os.path.join(QA_DIR, f'{report["date"]}.json')
    tmp = report_path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(report, f, indent=2)
    os.replace(tmp, report_path)

    logger.info(
        'QA audit complete: %d findings (%d critical, %d warning, %d info)',
        report['summary']['total'],
        report['summary']['critical'],
        report['summary']['warning'],
        report['summary']['info'],
    )

    return report


def _save_findings(new_findings: list[dict]):
    """Merge new findings with existing pending ones."""
    os.makedirs(QA_DIR, exist_ok=True)

    existing = []
    if os.path.exists(FINDINGS_PATH):
        try:
            with open(FINDINGS_PATH) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []

    # Keep pending findings from before, add new ones
    pending = [f for f in existing if f.get('status') == 'pending']

    # Deduplicate: don't add a finding if same check already pending
    existing_checks = {f['check'] for f in pending}
    for finding in new_findings:
        if finding['check'] not in existing_checks:
            pending.append(finding)
        else:
            # Update existing finding with fresh detail
            for p in pending:
                if p['check'] == finding['check']:
                    p['detail'] = finding['detail']
                    p['found_at'] = finding['found_at']
                    break

    tmp = FINDINGS_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(pending, f, indent=2)
    os.replace(tmp, FINDINGS_PATH)


def get_pending_count() -> int:
    """Get count of pending findings for morning briefing."""
    if not os.path.exists(FINDINGS_PATH):
        return 0
    try:
        with open(FINDINGS_PATH) as f:
            findings = json.load(f)
        return sum(1 for f in findings if f.get('status') == 'pending')
    except (json.JSONDecodeError, IOError):
        return 0


def get_briefing_line() -> str:
    """One-liner for the morning briefing."""
    count = get_pending_count()
    if count == 0:
        return ''
    return f'QA: {count} finding{"s" if count != 1 else ""} pending'


def resolve_finding(check_name: str) -> dict:
    """Mark a finding as resolved."""
    if not os.path.exists(FINDINGS_PATH):
        return {'status': 'not_found'}

    try:
        with open(FINDINGS_PATH) as f:
            findings = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {'status': 'error'}

    for finding in findings:
        if finding['check'] == check_name and finding['status'] == 'pending':
            finding['status'] = 'resolved'
            finding['resolved_at'] = datetime.now(timezone.utc).isoformat()

            tmp = FINDINGS_PATH + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(findings, f, indent=2)
            os.replace(tmp, FINDINGS_PATH)
            return {'status': 'ok', 'check': check_name}

    return {'status': 'not_found'}
