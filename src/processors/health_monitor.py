"""
Health Monitor -- Check all Daimonion subsystems after Synapsis runs.

Produces a health report saved to HEALTH_DIR/YYYY-MM-DD.json.
Summary included in morning briefing.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from src.config import (
    DATA_DIR,
    GRAPH_DB_PATH,
    GRAPH_DIR,
    HEALTH_DIR,
    HOT_CACHE_JSON,
    KNOWLEDGE_DIR,
    MEMORIES_DIR,
    NIGHT_RUNS_DIR,
    RESEARCH_QUEUE_PATH,
    USAGE_DIR,
    VAULT_DIR,
)

logger = logging.getLogger('daimonion.health_monitor')


def _check(name: str, status: str, detail: str = '') -> dict:
    return {'check': name, 'status': status, 'detail': detail}


def check_synapsis(night_stats: dict, date: str) -> list[dict]:
    """Check Synapsis step completion and performance."""
    results = []
    night_runs = os.path.join(NIGHT_RUNS_DIR, date)

    # Step 1: Extract
    if night_stats.get('memories_extracted', 0) > 0 or night_stats.get('log_entries', 0) > 0:
        results.append(_check(
            'step1_extract', 'healthy',
            f'{night_stats.get("memories_extracted", 0)} memories, {night_stats.get("knowledge_promoted", 0)} knowledge'
        ))
    elif night_stats.get('log_entries', 0) == 0:
        results.append(_check('step1_extract', 'warning', 'No log entries found -- was there a conversation today?'))
    else:
        results.append(_check('step1_extract', 'critical', 'Extraction produced no memories from available log entries'))

    # Step 2: Analyze
    step2_path = os.path.join(night_runs, 'step2_analyze.json')
    if os.path.exists(step2_path):
        try:
            with open(step2_path) as f:
                analysis = json.load(f)
            topics = len(analysis.get('recurring_topics', []))
            decisions = len(analysis.get('pending_decisions', []))
            results.append(_check('step2_analyze', 'healthy', f'{topics} topics, {decisions} decisions'))
        except (json.JSONDecodeError, IOError):
            results.append(_check('step2_analyze', 'warning', 'Output file corrupt'))
    elif night_stats.get('analyze_error'):
        results.append(_check('step2_analyze', 'warning', f'Failed: {night_stats["analyze_error"][:100]}'))
    else:
        results.append(_check('step2_analyze', 'warning', 'Not run'))

    # Step 3: Research
    step3_path = os.path.join(night_runs, 'step3_research.json')
    if os.path.exists(step3_path):
        try:
            with open(step3_path) as f:
                research = json.load(f)
            ok = sum(1 for r in research if r.get('status') == 'ok')
            results.append(_check('step3_research', 'healthy', f'{ok}/{len(research)} topics researched'))
        except (json.JSONDecodeError, IOError):
            results.append(_check('step3_research', 'warning', 'Output file corrupt'))
    elif night_stats.get('research_error'):
        results.append(_check('step3_research', 'warning', f'Failed: {night_stats["research_error"][:100]}'))
    else:
        results.append(_check('step3_research', 'healthy', 'No research topics tonight'))

    # Step 4: Compile
    step4_path = os.path.join(night_runs, 'step4_compile.json')
    if os.path.exists(step4_path):
        results.append(_check('step4_compile', 'healthy',
                              f'{night_stats.get("briefing_chars", 0)} chars briefing'))
    elif night_stats.get('compile_error'):
        results.append(_check('step4_compile', 'critical', f'Failed: {night_stats["compile_error"][:100]}'))
    else:
        results.append(_check('step4_compile', 'warning', 'Not run'))

    # Step 5: Graph sync
    synced = night_stats.get('graph_episodes', 0)
    errors = night_stats.get('graph_errors', 0)
    if errors == 0 and synced >= 0:
        results.append(_check('step5_graph_sync', 'healthy', f'{synced} episodes synced'))
    elif errors > 0:
        results.append(_check('step5_graph_sync', 'warning', f'{synced} synced, {errors} errors'))
    else:
        results.append(_check('step5_graph_sync', 'healthy', 'No new episodes to sync'))

    # Dedup ratio
    extracted = night_stats.get('memories_extracted', 0)
    deduped = night_stats.get('memories_deduped', 0)
    if extracted > 0:
        ratio = deduped / extracted * 100
        status = 'healthy' if ratio < 30 else 'warning'
        results.append(_check('dedup_ratio', status, f'{ratio:.0f}% deduped ({deduped}/{extracted})'))

    return results


def check_memory_system() -> list[dict]:
    """Check memory and knowledge file health."""
    results = []

    # Memory count
    if os.path.exists(MEMORIES_DIR):
        mem_files = [f for f in os.listdir(MEMORIES_DIR) if f.endswith('.json')]
        active = 0
        archived = 0
        for fname in mem_files:
            try:
                with open(os.path.join(MEMORIES_DIR, fname)) as f:
                    mem = json.load(f)
                if mem.get('archived'):
                    archived += 1
                else:
                    active += 1
            except (json.JSONDecodeError, IOError):
                continue

        total = active + archived
        results.append(_check('memory_count', 'healthy', f'{active} active, {archived} archived, {total} total'))

        # Archive ratio
        if total > 0:
            archive_pct = archived / total * 100
            status = 'healthy' if archive_pct < 50 else 'warning'
            results.append(_check('archive_ratio', status, f'{archive_pct:.0f}% archived'))
    else:
        results.append(_check('memory_count', 'warning', 'Memories directory not found'))

    # Knowledge count
    if os.path.exists(KNOWLEDGE_DIR):
        kb_files = [f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith('.json')]
        results.append(_check('knowledge_count', 'healthy', f'{len(kb_files)} entries'))
    else:
        results.append(_check('knowledge_count', 'warning', 'Knowledge directory not found'))

    return results


def check_graph() -> list[dict]:
    """Check Graphiti/Kuzu database health."""
    results = []

    # Database exists and has size
    if os.path.exists(GRAPH_DIR):
        size_mb = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, _, fns in os.walk(GRAPH_DIR)
            for f in fns
        ) / (1024 * 1024)
        results.append(_check('database_exists', 'healthy', f'{size_mb:.1f} MB'))
    else:
        results.append(_check('database_exists', 'warning', 'Graph directory not found'))
        return results

    # Check for unsynced memories
    if os.path.exists(MEMORIES_DIR):
        unsynced = 0
        old_unsynced = 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).strftime('%Y-%m-%d')
        for fname in os.listdir(MEMORIES_DIR):
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(MEMORIES_DIR, fname)) as f:
                        mem = json.load(f)
                    if not mem.get('_graph_synced') and not mem.get('archived'):
                        unsynced += 1
                        if mem.get('source_date', '') < cutoff:
                            old_unsynced += 1
                except (json.JSONDecodeError, IOError):
                    continue

        if old_unsynced > 0:
            results.append(_check('sync_status', 'warning', f'{unsynced} unsynced ({old_unsynced} older than 3 days)'))
        elif unsynced > 0:
            results.append(_check('sync_status', 'healthy', f'{unsynced} unsynced (recent, will sync tonight)'))
        else:
            results.append(_check('sync_status', 'healthy', 'All memories synced'))

    return results


def check_vault() -> list[dict]:
    """Check vault integrity."""
    results = []

    if not os.path.exists(VAULT_DIR):
        results.append(_check('vault_exists', 'critical', 'Vault directory not found'))
        return results

    # Count pages
    total_pages = 0
    for root, dirs, files in os.walk(VAULT_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.md'):
                total_pages += 1
    results.append(_check('page_count', 'healthy', f'{total_pages} pages'))

    # Check index exists
    index_path = os.path.join(VAULT_DIR, 'index.md')
    if os.path.exists(index_path):
        results.append(_check('index_exists', 'healthy'))
    else:
        results.append(_check('index_exists', 'warning', 'index.md missing'))

    # Check for broken wiki-links
    broken_links = 0
    for root, dirs, files in os.walk(VAULT_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for fname in files:
            if not fname.endswith('.md'):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath) as f:
                    content = f.read()
                # Find [[links]]
                links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
                for link in links:
                    target = os.path.join(VAULT_DIR, link)
                    if not target.endswith('.md'):
                        target += '.md'
                    if not os.path.exists(target):
                        broken_links += 1
            except IOError:
                continue

    status = 'healthy' if broken_links == 0 else 'warning'
    results.append(_check('broken_links', status, f'{broken_links} broken wiki-links'))

    # Check today's briefing
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    briefing_path = os.path.join(VAULT_DIR, 'daily-briefings', f'{today}.md')
    if os.path.exists(briefing_path):
        results.append(_check('briefing_today', 'healthy'))
    else:
        results.append(_check('briefing_today', 'warning', 'No briefing generated today'))

    return results


def check_infrastructure() -> list[dict]:
    """Check infrastructure health: cron, API, disk, hot cache."""
    results = []

    # Cron health -- check last night_stats file age
    stats_files = sorted(
        [f for f in os.listdir(DATA_DIR) if f.startswith('night_stats_') and f.endswith('.json')],
        reverse=True,
    ) if os.path.exists(DATA_DIR) else []

    if stats_files:
        latest = stats_files[0]
        latest_path = os.path.join(DATA_DIR, latest)
        age_hours = (datetime.now(timezone.utc).timestamp() - os.path.getmtime(latest_path)) / 3600
        if age_hours < 36:
            results.append(_check('cron_running', 'healthy', f'Last run {age_hours:.0f}h ago'))
        elif age_hours < 48:
            results.append(_check('cron_running', 'warning', f'Last run {age_hours:.0f}h ago'))
        else:
            results.append(_check('cron_running', 'critical', f'Last run {age_hours:.0f}h ago -- cron may be dead'))
    else:
        results.append(_check('cron_running', 'warning', 'No night_stats files found'))

    # Disk space
    total_size = 0
    if os.path.exists(DATA_DIR):
        for root, dirs, files in os.walk(DATA_DIR):
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except OSError:
                    continue
    size_mb = total_size / (1024 * 1024)
    status = 'healthy' if size_mb < 500 else 'warning' if size_mb < 2000 else 'critical'
    results.append(_check('disk_usage', status, f'{size_mb:.0f} MB'))

    # Hot cache freshness
    if os.path.exists(HOT_CACHE_JSON):
        try:
            with open(HOT_CACHE_JSON) as f:
                cache_meta = json.load(f)
            built_at = cache_meta.get('built_at', '')
            if built_at:
                built = datetime.fromisoformat(built_at.replace('Z', '+00:00'))
                age_hours = (datetime.now(timezone.utc) - built).total_seconds() / 3600
                status = 'healthy' if age_hours < 36 else 'warning'
                results.append(_check('hot_cache', status, f'Built {age_hours:.0f}h ago'))
            else:
                results.append(_check('hot_cache', 'warning', 'No built_at timestamp'))
        except (json.JSONDecodeError, IOError):
            results.append(_check('hot_cache', 'warning', 'hot_cache.json unreadable'))
    else:
        results.append(_check('hot_cache', 'warning', 'hot_cache.json not found'))

    # Research queue status
    if os.path.exists(RESEARCH_QUEUE_PATH):
        try:
            with open(RESEARCH_QUEUE_PATH) as f:
                queue = json.load(f)
            pending = sum(1 for q in queue if q.get('status') == 'pending')
            if pending > 10:
                results.append(_check('research_queue', 'warning', f'{pending} pending (backlog growing)'))
            else:
                results.append(_check('research_queue', 'healthy', f'{pending} pending'))
        except (json.JSONDecodeError, IOError):
            results.append(_check('research_queue', 'healthy', 'No queue file (normal if no flags)'))
    else:
        results.append(_check('research_queue', 'healthy', 'No queue file'))

    return results


async def health_check(night_stats: dict, date: str) -> dict:
    """Run all health checks. Called at end of Synapsis.

    Args:
        night_stats: Stats dict from the Synapsis run
        date: Date string (YYYY-MM-DD)

    Returns:
        Health report dict with overall status and per-category results.
    """
    results = {
        'date': date,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'synapsis': check_synapsis(night_stats, date),
        'memory_system': check_memory_system(),
        'graph': check_graph(),
        'vault': check_vault(),
        'infrastructure': check_infrastructure(),
        'overall': 'healthy',
    }

    # Determine overall status
    all_statuses = []
    for section in ['synapsis', 'memory_system', 'graph', 'vault', 'infrastructure']:
        for check in results[section]:
            all_statuses.append(check['status'])

    if 'critical' in all_statuses:
        results['overall'] = 'critical'
    elif 'warning' in all_statuses:
        results['overall'] = 'warning'

    # Count
    results['summary'] = {
        'healthy': all_statuses.count('healthy'),
        'warning': all_statuses.count('warning'),
        'critical': all_statuses.count('critical'),
        'total_checks': len(all_statuses),
    }

    # Save (atomic write)
    os.makedirs(HEALTH_DIR, exist_ok=True)
    health_path = os.path.join(HEALTH_DIR, f'{date}.json')
    tmp = health_path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(results, f, indent=2)
    os.replace(tmp, health_path)

    logger.info('Health check: %s (%d healthy, %d warning, %d critical)',
                results['overall'],
                results['summary']['healthy'],
                results['summary']['warning'],
                results['summary']['critical'])

    return results


def get_health_summary(date: str | None = None) -> str:
    """Get a text summary for the morning briefing."""
    if date is None:
        date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    health_path = os.path.join(HEALTH_DIR, f'{date}.json')
    if not os.path.exists(health_path):
        return ''

    try:
        with open(health_path) as f:
            report = json.load(f)
    except (json.JSONDecodeError, IOError):
        return ''

    overall = report.get('overall', 'unknown')
    summary = report.get('summary', {})

    if overall == 'healthy':
        return f'All systems healthy ({summary.get("total_checks", 0)} checks passed)'

    lines = ['## System Health']
    for section in ['synapsis', 'memory_system', 'graph', 'vault', 'infrastructure']:
        for check in report.get(section, []):
            if check['status'] == 'critical':
                lines.append(f'CRITICAL {check["check"]}: {check.get("detail", "")}')
            elif check['status'] == 'warning':
                lines.append(f'WARNING {check["check"]}: {check.get("detail", "")}')

    healthy = summary.get('healthy', 0)
    total = summary.get('total_checks', 0)
    lines.append(f'{healthy}/{total} checks healthy')

    return '\n'.join(lines)
