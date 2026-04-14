"""
Web Search — Brave API with research queue flagging.
"""

import logging
import os

import httpx

from src.config import RESEARCH_QUEUE_PATH
from src.tools.research_queue import flag_for_research
from src.tools.usage_tracker import tracker

logger = logging.getLogger('daimonion.web_search')

BRAVE_API_KEY = os.environ.get('BRAVE_SEARCH_API_KEY', '')
BRAVE_URL = 'https://api.search.brave.com/res/v1/web/search'


async def search(query: str, num_results: int = 5, flag_research: bool = False) -> dict:
    """Search the web via Brave API.

    Args:
        query: Search query
        num_results: Max results (default 5)
        flag_research: Flag for overnight deep research
    """
    if not BRAVE_API_KEY:
        return {'status': 'error', 'error': 'Brave API key not configured'}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                BRAVE_URL,
                params={'q': query, 'count': num_results},
                headers={'X-Subscription-Token': BRAVE_API_KEY, 'Accept': 'application/json'},
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get('web', {}).get('results', [])[:num_results]:
            results.append({
                'title': item.get('title', ''),
                'url': item.get('url', ''),
                'description': item.get('description', ''),
            })

        tracker.log_brave(query, len(results))

        result = {'status': 'ok', 'query': query, 'count': len(results), 'results': results}

        if flag_research:
            flag_result = flag_for_research(query, 'Flagged during daytime web search', 'daytime')
            result['research_flag'] = flag_result

        return result

    except Exception as e:
        logger.error('Web search failed: %s', e)
        return {'status': 'error', 'error': str(e)}
