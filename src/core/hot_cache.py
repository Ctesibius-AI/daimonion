"""
Tier 1 Hot Cache — compiled daily knowledge for instant context.

Built by the Synapsis, loaded into the system prompt at session start.
Contains: 3-day conversation takeaways, news digest, 3-day weather forecast,
open follow-ups.

Cap: 500 tokens / 20 items max. Pruned by recency + relevance.
Single-session assumption: one active user, one active session.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

from src.config import HOT_CACHE_MD, HOT_CACHE_JSON, MEMORIES_DIR, DAILY_LOG_DIR, DEFAULT_CITY

logger = logging.getLogger('daimonion.hot_cache')

# Weather
GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'

WMO_CODES = {
    0: 'clear', 1: 'mostly clear', 2: 'partly cloudy', 3: 'overcast',
    45: 'fog', 48: 'rime fog',
    51: 'light drizzle', 53: 'drizzle', 55: 'heavy drizzle',
    61: 'light rain', 63: 'rain', 65: 'heavy rain',
    71: 'light snow', 73: 'snow', 75: 'heavy snow',
    80: 'rain showers', 81: 'moderate showers', 82: 'heavy showers',
    95: 'thunderstorm', 96: 'thunderstorm + hail', 99: 'severe thunderstorm',
}


def build_hot_cache(
    news_headlines: list[dict] | None = None,
    interests: list[str] | None = None,
    city: str = DEFAULT_CITY,
) -> str:
    """Build the Tier 1 hot cache Markdown and save to disk.

    Called by the Synapsis after all other steps.
    Returns the compiled Markdown string.
    """
    sections = []

    # 1. Conversation takeaways (last 3 days)
    takeaways = _get_conversation_takeaways(days=3)
    if takeaways:
        sections.append('## Recent Context (last 3 days)')
        for item in takeaways[:10]:  # Cap at 10 items
            sections.append(f'- {item}')

    # 2. News digest (filtered by interests)
    news = _compile_news_digest(news_headlines, interests)
    if news:
        sections.append('\n## Today\'s News')
        for item in news[:5]:  # Cap at 5 stories
            sections.append(f'- {item}')

    # 3. Weather forecast (3 days)
    weather = _get_weather_forecast(city, days=3)
    if weather:
        sections.append(f'\n## Weather — {city}')
        for line in weather:
            sections.append(f'- {line}')

    # 4. Open follow-ups from recent conversations
    followups = _get_open_followups(days=3)
    if followups:
        sections.append('\n## Open Follow-ups')
        for item in followups[:5]:  # Cap at 5
            sections.append(f'- {item}')

    compiled = '\n'.join(sections)

    # Enforce 500 token cap (~2000 chars)
    if len(compiled) > 2000:
        compiled = compiled[:2000] + '\n[...truncated]'

    # Save to disk
    os.makedirs(os.path.dirname(HOT_CACHE_MD), exist_ok=True)
    with open(HOT_CACHE_MD, 'w') as f:
        f.write(compiled)

    # Save metadata
    meta = {
        'built_at': datetime.now(timezone.utc).isoformat(),
        'sections': {
            'takeaways': len(takeaways) if takeaways else 0,
            'news': len(news) if news else 0,
            'weather': len(weather) if weather else 0,
            'followups': len(followups) if followups else 0,
        },
        'chars': len(compiled),
    }
    with open(HOT_CACHE_JSON, 'w') as f:
        json.dump(meta, f, indent=2)

    logger.info('Hot cache built: %d chars, %d takeaways, %d news, %d weather, %d followups',
                len(compiled),
                meta['sections']['takeaways'],
                meta['sections']['news'],
                meta['sections']['weather'],
                meta['sections']['followups'])

    return compiled


def load_hot_cache() -> str:
    """Load the hot cache from disk. Returns empty string if not available."""
    if not os.path.exists(HOT_CACHE_MD):
        return ''
    try:
        with open(HOT_CACHE_MD) as f:
            return f.read()
    except Exception as e:
        logger.warning('Failed to load hot cache: %s', e)
        return ''


# --- Internal helpers ---

def _get_conversation_takeaways(days: int = 3) -> list[str]:
    """Extract key takeaways from recent memories (last N days)."""
    takeaways = []
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=days)).strftime('%Y-%m-%d')

    if not os.path.exists(MEMORIES_DIR):
        return takeaways

    for fname in sorted(os.listdir(MEMORIES_DIR), reverse=True):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(MEMORIES_DIR, fname)) as f:
                mem = json.load(f)
            source_date = mem.get('source_date', mem.get('source_conversation_date', ''))
            if source_date >= cutoff:
                content = mem.get('content', '').strip()
                if content and len(content) > 10:
                    # Truncate long memories
                    if len(content) > 150:
                        content = content[:147] + '...'
                    takeaways.append(content)
        except (json.JSONDecodeError, KeyError):
            continue

    # Deduplicate by rough similarity
    seen = set()
    unique = []
    for t in takeaways:
        key = t[:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(t)

    return unique[:10]  # Hard cap


def _compile_news_digest(
    headlines: list[dict] | None = None,
    interests: list[str] | None = None,
) -> list[str]:
    """Compile news digest from headlines, filtered by user interests."""
    if not headlines:
        # Try loading from RSS cache
        try:
            from src.tools.rss_reader import get_all_headlines
            all_news = get_all_headlines(count_per_category=10)
            headlines = [h for items in all_news.values() for h in items]
        except Exception as e:
            logger.warning('Failed to load RSS headlines: %s', e)
            return []

    if not interests:
        try:
            from src.tools.user_interests import get_interests
            interests = get_interests()
        except Exception:
            interests = []

    digest = []

    # Prioritize headlines matching user interests
    if interests:
        for h in headlines:
            title = h.get('title', '')
            summary = h.get('summary', '')
            text = f'{title} {summary}'.lower()
            matched = [i for i in interests if i.lower() in text]
            if matched:
                source = h.get('source', '')
                entry = f'{title} ({source})'
                if len(entry) > 120:
                    entry = entry[:117] + '...'
                digest.append(entry)

    # Fill remaining slots with top headlines
    if len(digest) < 5:
        for h in headlines[:10]:
            title = h.get('title', '')
            source = h.get('source', '')
            entry = f'{title} ({source})'
            if entry not in digest:
                if len(entry) > 120:
                    entry = entry[:117] + '...'
                digest.append(entry)
            if len(digest) >= 5:
                break

    return digest[:5]


def _get_weather_forecast(city: str, days: int = 3) -> list[str]:
    """Fetch weather forecast for the next N days."""
    try:
        geo_resp = httpx.get(GEOCODE_URL, params={'name': city, 'count': 1}, timeout=5)
        geo_resp.raise_for_status()
        results = geo_resp.json().get('results', [])
        if not results:
            return []

        loc = results[0]
        weather_resp = httpx.get(WEATHER_URL, params={
            'latitude': loc['latitude'],
            'longitude': loc['longitude'],
            'current': 'temperature_2m,weather_code',
            'daily': 'temperature_2m_max,temperature_2m_min,weather_code',
            'forecast_days': days + 1,  # today + N days
            'timezone': 'auto',
        }, timeout=5)
        weather_resp.raise_for_status()
        data = weather_resp.json()

        lines = []

        # Current
        current = data.get('current', {})
        temp = current.get('temperature_2m', '?')
        code = current.get('weather_code', 0)
        lines.append(f'Now: {temp}\u00b0C, {WMO_CODES.get(code, "unknown")}')

        # Daily forecast
        daily = data.get('daily', {})
        dates = daily.get('time', [])
        maxs = daily.get('temperature_2m_max', [])
        mins = daily.get('temperature_2m_min', [])
        codes = daily.get('weather_code', [])

        day_names = ['Today', 'Tomorrow']
        for i in range(min(days + 1, len(dates))):
            if i >= len(maxs):
                break
            day_label = day_names[i] if i < len(day_names) else dates[i]
            cond = WMO_CODES.get(codes[i] if i < len(codes) else 0, 'unknown')
            lines.append(f'{day_label}: {mins[i]}\u2013{maxs[i]}\u00b0C, {cond}')

        return lines

    except Exception as e:
        logger.warning('Weather forecast failed: %s', e)
        return []


def _get_open_followups(days: int = 3) -> list[str]:
    """Extract open follow-ups from recent daily logs.

    Looks for patterns like "TODO", "follow up", "pending", "need to",
    "check on", "revisit" in conversation logs.
    """
    followups = []
    now = datetime.now(timezone.utc)

    for d in range(days):
        date_str = (now - timedelta(days=d)).strftime('%Y-%m-%d')
        log_path = os.path.join(DAILY_LOG_DIR, f'{date_str}.md')
        if not os.path.exists(log_path):
            continue

        try:
            with open(log_path) as f:
                content = f.read()

            # Simple pattern matching for follow-ups
            import re
            patterns = [
                r'(?:TODO|FIXME|FOLLOW.?UP|PENDING|NEED TO|CHECK ON|REVISIT)[:\s]+(.+?)(?:\n|$)',
                r'(?:will|should|need to|must|going to)\s+(.+?)(?:\.|$)',
            ]
            for pattern in patterns[:1]:  # Only use explicit markers
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    item = match.group(1).strip()
                    if 10 < len(item) < 150:
                        followups.append(f'[{date_str}] {item}')
        except Exception:
            continue

    return followups[:5]
