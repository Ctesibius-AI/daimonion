"""
Daimonion test configuration.

Sets up tmp directories and patches config paths for isolated testing.
"""

import os
import pytest


@pytest.fixture
def tmp_data(tmp_path):
    """Create a temporary ~/.daimonion/ structure for testing."""
    dirs = {
        'data': str(tmp_path / 'daimonion'),
        'memories': str(tmp_path / 'daimonion' / 'memories'),
        'knowledge': str(tmp_path / 'daimonion' / 'knowledge'),
        'graph': str(tmp_path / 'daimonion' / 'graph'),
        'vault': str(tmp_path / 'daimonion' / 'vault'),
        'conversations': str(tmp_path / 'daimonion' / 'conversations'),
        'daily_logs': str(tmp_path / 'daimonion' / 'daily_logs'),
        'usage': str(tmp_path / 'daimonion' / 'usage'),
        'health': str(tmp_path / 'daimonion' / 'health'),
        'sessions': str(tmp_path / 'daimonion' / 'sessions'),
        'night_runs': str(tmp_path / 'daimonion' / 'night_runs'),
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)

    # Vault subdirs
    for subdir in ['projects', 'research', 'decisions', 'people', 'daily-briefings']:
        os.makedirs(os.path.join(dirs['vault'], subdir), exist_ok=True)

    return dirs
