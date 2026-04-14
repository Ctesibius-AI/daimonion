"""
RSS feed reader for Daimonion's news intelligence system.

Pulls feeds by category, parses entries, returns structured headlines.
No API keys needed -- RSS is free and open.
"""

import feedparser
import json
import os
import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

from src.config import DATA_DIR

# Feed registry organized by category
FEEDS = {
    'politics': [
        {'name': 'Reuters World', 'url': 'https://feeds.reuters.com/Reuters/worldNews'},
        {'name': 'BBC News', 'url': 'http://feeds.bbci.co.uk/news/rss.xml'},
    ],
    'sports': [
        {'name': 'BBC Sport', 'url': 'http://feeds.bbci.co.uk/sport/rss.xml'},
        {'name': 'ESPN', 'url': 'https://www.espn.com/espn/rss/news'},
        {'name': 'Autosport F1', 'url': 'https://www.autosport.com/rss/feed/f1'},
    ],
    'finance': [
        {'name': 'Reuters Business', 'url': 'https://feeds.reuters.com/reuters/businessNews'},
        {'name': 'Financial Times', 'url': 'https://www.ft.com/rss/home'},
    ],
    'tech': [
        {'name': 'TechCrunch', 'url': 'https://techcrunch.com/feed/'},
        {'name': 'Hacker News', 'url': 'https://hnrss.org/frontpage'},
        {'name': 'The Verge AI', 'url': 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml'},
    ],
    'greece': [
        {'name': 'Kathimerini English', 'url': 'https://www.ekathimerini.com/rss'},
        {'name': 'Greek Reporter', 'url': 'https://greekreporter.com/feed/'},
    ],
    'eu': [
        {'name': 'Euractiv', 'url': 'https://www.euractiv.com/feed/'},
        {'name': 'Politico EU', 'url': 'https://www.politico.eu/feed/'},
    ],
}

NEWS_DIR = os.path.join(DATA_DIR, 'news')


def pull_category(category: str) -> list[dict]:
    """Pull all feeds for a category. Returns list of headline dicts."""
    feeds = FEEDS.get(category, [])
    headlines = []

    for feed_info in feeds:
        try:
            parsed = feedparser.parse(feed_info['url'])
            for entry in parsed.entries[:10]:  # Max 10 per feed
                headline = {
                    'id': hashlib.md5(entry.get('link', '').encode()).hexdigest()[:12],
                    'title': entry.get('title', '').strip(),
                    'summary': _clean_summary(entry.get('summary', '')),
                    'url': entry.get('link', ''),
                    'source': feed_info['name'],
                    'category': category,
                    'published': entry.get('published', ''),
                    'pulled_at': datetime.now(timezone.utc).isoformat(),
                }
                headlines.append(headline)
        except Exception as e:
            # Feed failure shouldn't crash the pipeline
            print(f"RSS error [{feed_info['name']}]: {e}")
            continue

    return headlines


def pull_all_categories() -> dict[str, list[dict]]:
    """Pull all categories. Returns {category: [headlines]}."""
    all_news = {}
    for category in FEEDS:
        all_news[category] = pull_category(category)
    return all_news


def save_daily_news(all_news: dict[str, list[dict]]):
    """Save today's news to disk."""
    date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    day_dir = os.path.join(NEWS_DIR, date_str)
    os.makedirs(day_dir, exist_ok=True)

    for category, headlines in all_news.items():
        filepath = os.path.join(day_dir, f'{category}.json')
        with open(filepath, 'w') as f:
            json.dump(headlines, f, indent=2, ensure_ascii=False)


def load_today_news(category: Optional[str] = None) -> dict[str, list[dict]]:
    """Load today's saved news. Optionally filter by category."""
    date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    day_dir = os.path.join(NEWS_DIR, date_str)

    if not os.path.exists(day_dir):
        return {}

    result = {}
    categories = [category] if category else FEEDS.keys()

    for cat in categories:
        filepath = os.path.join(day_dir, f'{cat}.json')
        if os.path.exists(filepath):
            with open(filepath) as f:
                result[cat] = json.load(f)

    return result


def get_headlines(category: str, count: int = 5) -> list[dict]:
    """Get top N headlines for a category from today's news."""
    news = load_today_news(category)
    headlines = news.get(category, [])
    return headlines[:count]


def get_all_headlines(count_per_category: int = 3) -> dict[str, list[dict]]:
    """Get top headlines across all categories."""
    news = load_today_news()
    result = {}
    for cat, headlines in news.items():
        result[cat] = headlines[:count_per_category]
    return result


def _clean_summary(summary: str) -> str:
    """Strip HTML tags from RSS summary."""
    clean = re.sub(r'<[^>]+>', '', summary)
    clean = clean.strip()
    # Truncate to 300 chars
    if len(clean) > 300:
        clean = clean[:297] + '...'
    return clean
