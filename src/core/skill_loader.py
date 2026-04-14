"""
Trait & Skill Loader — Load composable Markdown traits and skills.

Traits: WHO Pythia is, HOW she thinks (from traits/ directory, trait_index.yaml)
Skills: WHAT she can do (from Anthropic's plugin system, external)

This loader handles traits. Skills are managed by Claude Code's plugin system.
"""

import os

import yaml

from src.config import SKILLS_DIR


class TraitLoader:
    """Loads behavioral traits from the trait library.

    Reads skills/meta/trait_index.yaml for the registry.
    Caches loaded trait files in memory.
    """

    def __init__(self, skills_dir: str | None = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self.index = self._load_index()
        self.cache: dict[str, str] = {}

    def _load_index(self) -> dict:
        # Try trait_index first, fall back to skill_index for compatibility
        trait_path = os.path.join(self.skills_dir, 'meta', 'trait_index.yaml')
        skill_path = os.path.join(self.skills_dir, 'meta', 'skill_index.yaml')

        if os.path.exists(trait_path):
            with open(trait_path) as f:
                data = yaml.safe_load(f)
                # Normalize: trait_index uses 'traits' key
                if 'traits' in data:
                    return {'skills': data['traits']}
                return data
        elif os.path.exists(skill_path):
            with open(skill_path) as f:
                return yaml.safe_load(f)
        else:
            return {'skills': {}}

    def load_trait(self, trait_name: str) -> str:
        """Load a single trait file. Cached after first load."""
        if trait_name in self.cache:
            return self.cache[trait_name]

        trait_config = self.index['skills'].get(trait_name)
        if not trait_config:
            raise ValueError(f'Unknown trait: {trait_name}')

        filepath = os.path.join(self.skills_dir, trait_config['path'])
        with open(filepath) as f:
            content = f.read()

        self.cache[trait_name] = content
        return content

    # Backward compatibility aliases
    def load_skill(self, skill_name: str) -> str:
        return self.load_trait(skill_name)

    def assemble_prompt(self, trait_names: list[str]) -> str:
        """Assemble multiple traits into a single prompt."""
        sections = []
        for name in trait_names:
            sections.append(self.load_trait(name))
        return '\n\n---\n\n'.join(sections)

    def get_always_loaded(self) -> list[str]:
        """Return traits that should always be loaded."""
        return [
            name
            for name, config in self.index['skills'].items()
            if config.get('always_loaded', False)
        ]

    def get_available_domains(self) -> str:
        """Auto-generate domain list with triggers."""
        lines = []
        for name, config in self.index['skills'].items():
            if config.get('triggers'):
                triggers = ', '.join(config['triggers'][:5])
                lines.append(f'- {name}: triggers on [{triggers}]')
        return '\n'.join(lines)

    def list_traits(self) -> list[str]:
        """Return all registered trait names."""
        return list(self.index['skills'].keys())

    # Backward compatibility
    def list_skills(self) -> list[str]:
        return self.list_traits()

    def total_tokens(self, trait_names: list[str]) -> int:
        """Estimate total tokens for a set of traits."""
        total = 0
        for name in trait_names:
            config = self.index['skills'].get(name, {})
            total += config.get('tokens', 0)
        return total


# Backward compatibility alias
SkillLoader = TraitLoader
