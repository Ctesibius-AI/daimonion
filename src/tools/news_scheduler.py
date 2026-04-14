"""
Time-aware, personalized news delivery.

Picks categories based on time of day, then prioritizes headlines
matching the user's tracked interests (F1, Middle East, etc.)
so the digest leads with what matters most.

Schedule:
  7:00 AM  -- Politics + Sports + Greece (coffee briefing)
  9:00 AM  -- Tech + EU (work start)
  12:00 PM -- Finance + EU + Tech (midday)
  6:00 PM  -- Light digest of anything missed (wind down)
"""

from datetime import datetime

from src.tools.user_interests import get_interests, matches_interests

# Time slots: (hour_start, hour_end, categories, label)
NEWS_SCHEDULE = [
    (5, 9, ['politics', 'sports', 'greece'], 'Morning briefing'),
    (9, 12, ['tech', 'eu'], 'Work briefing'),
    (12, 17, ['finance', 'eu', 'tech'], 'Midday update'),
    (17, 23, ['politics', 'sports', 'greece', 'tech', 'finance'], 'Evening digest'),
]

# Default if outside schedule (night)
DEFAULT_SLOT = (['politics', 'tech', 'greece'], 'News digest')


def get_current_slot() -> tuple[list[str], str]:
    """Return the categories and label for the current time slot."""
    hour = datetime.now().hour

    for start, end, categories, label in NEWS_SCHEDULE:
        if start <= hour < end:
            return categories, label

    return DEFAULT_SLOT


def _prioritize_headlines(
    headlines: dict[str, list[dict]],
    interests: list[str],
) -> tuple[list[dict], list[dict]]:
    """Split headlines into matched (prioritized) and rest.

    Returns (matched, rest) where matched items have an 'interest_match'
    field listing which interests they hit.
    """
    matched = []
    rest = []

    for category, items in headlines.items():
        for item in items:
            text = f"{item['title']} {item.get('summary', '')}"
            hits = matches_interests(text, interests)
            if hits:
                item_copy = dict(item)
                item_copy['interest_match'] = hits
                matched.append(item_copy)
            else:
                rest.append(item)

    return matched, rest


def format_news_digest(headlines: dict[str, list[dict]], label: str) -> str:
    """Format headlines into a personalized digest.

    Headlines matching user interests appear first.
    Ends with "Want details on any of these?"
    """
    interests = get_interests()
    matched, rest = _prioritize_headlines(headlines, interests)

    lines = [f"**{label}**\n"]
    count = 0

    # Prioritized headlines first
    for item in matched[:4]:
        lines.append(f"\u2022 {item['title']} ({item['source']})")
        count += 1

    # Fill remaining slots with other headlines
    for item in rest:
        if count >= 8:
            break
        lines.append(f"\u2022 {item['title']} ({item['source']})")
        count += 1

    if count == 0:
        return "No fresh news available right now. Try again in a bit."

    lines.append("\nWant details on any of these?")
    return '\n'.join(lines)


def format_single_category_digest(category: str, headlines: list[dict]) -> str:
    """Format headlines for a single requested category, interests first."""
    if not headlines:
        return f"No {category} news available today. The feeds might not have updated yet."

    interests = get_interests()
    matched, rest = _prioritize_headlines({category: headlines}, interests)

    lines = [f"Latest {category} headlines:\n"]
    for item in (matched + rest)[:5]:
        lines.append(f"\u2022 {item['title']} ({item['source']})")

    lines.append("\nWant me to dig deeper on any of these?")
    return '\n'.join(lines)
