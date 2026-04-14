"""
Unit tests for the Obsidian vault tools.

Tests save/read/list, atomic writes, wiki-links, path safety, index rebuild.
"""

import os
from unittest.mock import patch

import pytest

from src.tools.vault import save, read, list_dir, _add_wiki_links


@pytest.fixture
def vault(tmp_path):
    vault_dir = str(tmp_path / 'vault')
    os.makedirs(vault_dir)
    for subdir in ['projects', 'research', 'decisions', 'people', 'daily-briefings']:
        os.makedirs(os.path.join(vault_dir, subdir))
    with patch('src.tools.vault.VAULT_DIR', vault_dir):
        yield vault_dir


class TestSave:
    def test_save_creates_file(self, vault):
        result = save('projects/test.md', '# Test Project')
        assert result['status'] == 'ok'
        assert os.path.exists(os.path.join(vault, 'projects', 'test.md'))

    def test_save_update_overwrites(self, vault):
        save('test.md', 'version 1')
        save('test.md', 'version 2', mode='update')
        result = read('test.md')
        assert 'version 2' in result['content']

    def test_save_create_fails_if_exists(self, vault):
        save('test.md', 'first')
        result = save('test.md', 'second', mode='create')
        assert result['status'] == 'error'
        assert 'Already exists' in result['error']

    def test_save_append(self, vault):
        save('test.md', 'first')
        save('test.md', 'second', mode='append')
        result = read('test.md')
        assert 'first' in result['content']
        assert 'second' in result['content']

    def test_save_creates_subdirectories(self, vault):
        result = save('new/subdir/test.md', '# Test')
        assert result['status'] == 'ok'

    def test_atomic_write_no_tmp_left(self, vault):
        save('test.md', 'content')
        assert not os.path.exists(os.path.join(vault, 'test.md.tmp'))

    def test_path_traversal_blocked(self, vault):
        result = save('../../etc/passwd', 'evil')
        assert result['status'] == 'error'
        assert 'escapes' in result['error']


class TestRead:
    def test_read_existing(self, vault):
        save('test.md', '# Hello')
        result = read('test.md')
        assert result['status'] == 'ok'
        assert '# Hello' in result['content']

    def test_read_nonexistent(self, vault):
        result = read('nonexistent.md')
        assert result['status'] == 'error'

    def test_read_returns_char_count(self, vault):
        save('test.md', 'hello')
        result = read('test.md')
        assert result['chars'] > 0

    def test_path_traversal_blocked(self, vault):
        result = read('../../etc/passwd')
        assert result['status'] == 'error'


class TestListDir:
    def test_list_root(self, vault):
        result = list_dir('')
        assert result['status'] == 'ok'
        assert result['count'] > 0
        names = [f['name'] for f in result['files']]
        assert 'projects/' in names

    def test_list_subdirectory(self, vault):
        save('projects/project_alpha.md', '# ProjectAlpha')
        result = list_dir('projects')
        assert result['status'] == 'ok'
        assert any(f['name'] == 'project_alpha.md' for f in result['files'])

    def test_list_nonexistent_dir(self, vault):
        result = list_dir('nonexistent')
        assert result['status'] == 'error'

    def test_hides_dotfiles(self, vault):
        with open(os.path.join(vault, '.hidden'), 'w') as f:
            f.write('hidden')
        result = list_dir('')
        names = [f['name'] for f in result['files']]
        assert '.hidden' not in names


class TestWikiLinks:
    def test_adds_links_for_known_entities(self):
        text = 'Working on Pythia today.'
        result = _add_wiki_links(text)
        assert '[[' in result
        assert 'Pythia' in result

    def test_no_double_linking(self):
        text = 'Working on [[projects/pythia|Pythia]] today.'
        result = _add_wiki_links(text)
        assert result.count('[[') == 1

    def test_multiple_entities(self):
        text = 'Pythia and ProjectAlpha are active.'
        result = _add_wiki_links(text)
        assert result.count('[[') == 2

    def test_no_links_when_no_entities(self):
        text = 'No entities here.'
        result = _add_wiki_links(text)
        assert '[[' not in result


class TestIndexRebuild:
    def test_index_created_after_save(self, vault):
        save('projects/test.md', '# Test Project')
        assert os.path.exists(os.path.join(vault, 'index.md'))

    def test_index_contains_saved_page(self, vault):
        save('projects/project_alpha.md', '# ProjectAlpha')
        with open(os.path.join(vault, 'index.md')) as f:
            content = f.read()
        assert 'ProjectAlpha' in content
