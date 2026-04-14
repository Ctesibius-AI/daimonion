"""
Pythia Pipeline v4 — Sonnet front desk with tools, Opus for thinking.

Sonnet handles everything via tools: search_memory, load_skill, escalate_to_opus,
save_to_vault, read_from_vault, web_search.

The conversation log is the single source of truth. All interfaces
write to it. Pythia reads the full log when responding.
"""

from __future__ import annotations

import json
import logging
import time

import anthropic

from src.config import SONNET_MODEL, OPUS_MODEL, SOUL_SONNET_PATH, SOUL_OPUS_PATH
from src.core.conversation import Conversation
from src.core.hot_cache import load_hot_cache
from src.core.skill_loader import SkillLoader
from src.tools.vault import save as vault_save, read as vault_read, list_dir as vault_list_dir
from src.tools.web_search import search as web_search
from src.tools.usage_tracker import tracker as usage_tracker

logger = logging.getLogger('daimonion.pipeline')

# Tool definitions for Sonnet
TOOLS = [
    {
        'name': 'search_memory',
        'description': (
            'Search Pythia\'s long-term memory (Graphiti knowledge graph) for facts, '
            'decisions, and past conversations. Use this when the answer is NOT in the '
            'current conversation or the hot cache (recent 3 days). '
            'Good for: "what did we decide about X last month?", "remind me about Y", '
            '"what do I know about Z?"'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'Natural language search query',
                },
            },
            'required': ['query'],
        },
    },
    {
        'name': 'load_skill',
        'description': (
            'Load a domain expertise skill when the conversation enters a specific '
            'project or technical domain. Skills provide specialized knowledge and '
            'context that Pythia doesn\'t have from training. '
            'Load skills when starting a project discussion. They persist until the topic changes.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'skill_name': {
                    'type': 'string',
                    'description': 'Name of the skill to load from the skill library',
                },
            },
            'required': ['skill_name'],
        },
    },
    {
        'name': 'escalate_to_opus',
        'description': (
            'Hand the conversation to Opus (deep thinker) for questions that need '
            'reasoning, opinions, strategic analysis, or decision-making. '
            'Use when the user asks: "what do you think?", "should I?", "compare", '
            '"analyze", "evaluate", or any question requiring judgment, not just facts. '
            'Include a brief summarizing what the user wants and relevant context.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'brief': {
                    'type': 'string',
                    'description': 'Context brief for Opus: what the user is asking about, relevant background, what kind of thinking is needed',
                },
                'question': {
                    'type': 'string',
                    'description': 'The specific question or request for Opus to address',
                },
            },
            'required': ['brief', 'question'],
        },
    },
    {
        'name': 'save_to_vault',
        'description': (
            'Save or update a page in the knowledge vault (Obsidian-compatible Markdown wiki). '
            'Use for: project plans, research findings, decisions with reasoning, compiled knowledge, '
            'meeting notes. The vault is browsable in Obsidian. '
            'Wiki-links [[page]] are auto-inserted for known entities.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'path': {
                    'type': 'string',
                    'description': 'Vault path, e.g. "projects/nereus.md", "decisions/pricing-v2.md", "research/eu-ai-regulation.md"',
                },
                'content': {
                    'type': 'string',
                    'description': 'Markdown content to write',
                },
                'mode': {
                    'type': 'string',
                    'enum': ['create', 'update', 'append'],
                    'description': 'create=fail if exists, update=overwrite, append=add to end. Default: update',
                },
            },
            'required': ['path', 'content'],
        },
    },
    {
        'name': 'read_from_vault',
        'description': (
            'Read a page from the knowledge vault, or list pages in a directory. '
            'Use to check existing project pages, research reports, past decisions. '
            'Pass path to read a file, or list_dir to see directory contents.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'path': {
                    'type': 'string',
                    'description': 'Vault path to read, e.g. "projects/nereus.md" or "index.md"',
                },
                'list_dir': {
                    'type': 'string',
                    'description': 'Vault directory to list, e.g. "projects/" or "" for root',
                },
            },
        },
    },
    {
        'name': 'web_search',
        'description': (
            'Quick web search for current information. Use when conversation log + memory + '
            'hot cache don\'t have the answer. Returns top results with titles, URLs, and descriptions. '
            'Set flag_for_research=true if the topic deserves overnight deep research by the Synapsis.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'Search query',
                },
                'num_results': {
                    'type': 'integer',
                    'description': 'Number of results (default 5)',
                },
                'flag_for_research': {
                    'type': 'boolean',
                    'description': 'Set true to flag this topic for overnight deep research',
                },
            },
            'required': ['query'],
        },
    },
]


class PythiaPipeline:
    """Sonnet front desk with tools. Opus for deep thinking."""

    def __init__(
        self,
        retriever=None,
        api_key: str | None = None,
        soul_sonnet_path: str = SOUL_SONNET_PATH,
        soul_opus_path: str = SOUL_OPUS_PATH,
    ):
        import os
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        self.retriever = retriever  # Optional — memory search disabled if None
        self.skill_loader = SkillLoader()
        self._soul_sonnet = self._load_soul(soul_sonnet_path)
        self._soul_opus = self._load_soul(soul_opus_path) or self._soul_sonnet
        self._hot_cache = load_hot_cache()

    @staticmethod
    def _load_soul(path: str) -> str:
        try:
            with open(path) as f:
                return f.read().strip()
        except FileNotFoundError:
            return ''

    def _build_system_prompt(self, conversation: Conversation, interface: str | None = None,
                             model: str = 'sonnet') -> str:
        """Build the system prompt with SOUL.md + hot cache + active skills.

        Sonnet gets the lean core SOUL.md (~500 words).
        Opus gets the full SOUL.md (~3000 words) with identity depth.
        """
        parts = []

        # SOUL.md — model-specific
        soul = self._soul_opus if model == 'opus' else self._soul_sonnet
        if soul:
            parts.append(soul)

        # Hot cache — always present
        if self._hot_cache:
            parts.append(self._hot_cache)

        # Active skills — persist until topic changes (lag-by-one-turn)
        for skill_name in conversation.active_skills:
            try:
                content = self.skill_loader.load_skill(skill_name)
                parts.append(content)
            except (ValueError, FileNotFoundError):
                logger.warning('Skill not found: %s', skill_name)

        # Interface-specific instructions
        if interface == 'telegram':
            parts.append(
                '## Response Format — Telegram\n'
                'Keep responses under 80 words. No markdown headers. '
                'If the user is thinking aloud, document and ask clarifying questions — '
                'do NOT give opinions unless explicitly asked.'
            )
        elif interface == 'voice':
            parts.append(
                '## Response Format — Voice\n'
                'MAX 50 WORDS. No markdown. Natural speech. Short sentences. '
                'End with a specific follow-up question.'
            )

        return '\n\n---\n\n'.join(parts)

    def _is_topic_shift(self, text: str) -> bool:
        """Detect if a message signals a topic shift back to operational/simple mode.

        Returns True if Opus should hand back to Sonnet.
        """
        text_lower = text.lower().strip()

        # Short operational commands
        if len(text_lower) < 30 and any(w in text_lower for w in [
            'send', 'check', 'save', 'delete', 'show', 'list', 'status',
            'run', 'start', 'stop', 'restart', 'deploy', 'test',
        ]):
            return True

        # Greetings / closings
        if any(text_lower.startswith(w) for w in [
            'hello', 'hi ', 'good morning', 'good night', 'bye',
            'thanks', 'thank you', 'ok', 'done', 'perfect',
        ]):
            return True

        # Explicit topic change
        if any(w in text_lower for w in [
            'different topic', 'change subject', 'moving on', 'next topic',
            'something else', 'new question',
        ]):
            return True

        return False

    async def process(
        self,
        conversation: Conversation,
        interface: str | None = None,
    ) -> dict:
        """Process the conversation through Sonnet or Opus.

        Routing logic:
        - If Opus is active (previous turn was Opus) AND no topic shift -> route to Opus
        - Otherwise -> Sonnet front desk with tools
        - When Sonnet escalates to Opus -> set active_model flag
        - When topic shifts to operational/simple -> clear flag, back to Sonnet

        Returns dict with: response, model, timing, tool_calls.
        """
        t0 = time.time()
        pending = conversation.get_pending_user_text()
        if not pending:
            return {'response': '', 'model': 'none', 'timing': {}, 'tool_calls': []}

        messages = conversation.get_messages_for_api()
        if not messages or messages[-1]['role'] != 'user':
            messages.append({'role': 'user', 'content': pending})

        timing = {}
        tool_calls_log = []
        response_text = ''

        # -- Check Opus persistence --
        opus_active = conversation._opus_active

        if opus_active:
            if self._is_topic_shift(pending):
                # Topic shifted — hand back to Sonnet
                conversation._opus_active = False
                opus_active = False
                logger.info('Topic shift detected — returning to Sonnet')
            else:
                # Continue with Opus
                logger.info('Opus persistence — continuing deep conversation')
                return await self._process_opus_direct(
                    conversation, messages, interface, t0,
                )

        # -- Sonnet front desk --
        system_prompt = self._build_system_prompt(conversation, interface, model='sonnet')
        model_used = SONNET_MODEL

        t_sonnet = time.time()
        response = await self.client.messages.create(
            model=SONNET_MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
            tools=TOOLS,
        )
        timing['sonnet_ms'] = int((time.time() - t_sonnet) * 1000)
        usage_tracker.log(response, 'daytime.sonnet_direct', timing['sonnet_ms'])

        # Process tool calls in a loop
        while response.stop_reason == 'tool_use':
            tool_results = []
            for block in response.content:
                if block.type == 'tool_use':
                    tool_name = block.name
                    tool_input = block.input
                    tool_calls_log.append({'tool': tool_name, 'input': tool_input})
                    logger.info('Tool call: %s(%s)', tool_name, json.dumps(tool_input)[:100])

                    result = await self._handle_tool(tool_name, tool_input, conversation, system_prompt, messages)
                    tool_results.append({
                        'type': 'tool_result',
                        'tool_use_id': block.id,
                        'content': result,
                    })

                    # If escalate_to_opus returned a response, activate Opus persistence
                    if tool_name == 'escalate_to_opus' and result.startswith('[OPUS_RESPONSE]'):
                        response_text = result.replace('[OPUS_RESPONSE]', '').strip()
                        model_used = OPUS_MODEL
                        timing['total_ms'] = int((time.time() - t0) * 1000)

                        # Set Opus persistence flag
                        conversation._opus_active = True
                        logger.info('Opus activated — will persist until topic shift')

                        # Update conversation log
                        conversation.add_assistant_message(response_text)

                        return {
                            'response': response_text,
                            'model': model_used,
                            'timing': timing,
                            'tool_calls': tool_calls_log,
                        }

            # Continue the conversation with tool results
            messages = messages + [
                {'role': 'assistant', 'content': response.content},
                {'role': 'user', 'content': tool_results},
            ]

            t_cont = time.time()
            response = await self.client.messages.create(
                model=SONNET_MODEL,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
                tools=TOOLS,
            )
            timing['sonnet_continue_ms'] = int((time.time() - t_cont) * 1000)
            usage_tracker.log(response, 'daytime.sonnet_continue', timing['sonnet_continue_ms'])

        # Extract text response
        for block in response.content:
            if hasattr(block, 'text'):
                response_text += block.text

        timing['total_ms'] = int((time.time() - t0) * 1000)

        # Update conversation log
        if response_text.strip():
            conversation.add_assistant_message(response_text.strip())

        # Update active skills based on Sonnet's tool calls
        new_skills = [tc['input']['skill_name'] for tc in tool_calls_log if tc['tool'] == 'load_skill']
        if new_skills:
            conversation.set_active_skills(new_skills)

        logger.info('Pipeline: %dms, model=%s, tools=%s',
                    timing['total_ms'], model_used,
                    [tc['tool'] for tc in tool_calls_log] or 'none')

        return {
            'response': response_text.strip(),
            'model': model_used,
            'timing': timing,
            'tool_calls': tool_calls_log,
        }

    async def _process_opus_direct(
        self,
        conversation: Conversation,
        messages: list[dict],
        interface: str | None,
        t0: float,
    ) -> dict:
        """Process directly through Opus (persistence mode — no Sonnet routing).

        Called when Opus was active on previous turn and no topic shift detected.
        Opus gets full SOUL.md and responds directly.
        """
        system_prompt = self._build_system_prompt(conversation, interface, model='opus')
        timing = {}

        t_opus = time.time()
        try:
            response = await self.client.messages.create(
                model=OPUS_MODEL,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
            )

            timing['opus_ms'] = int((time.time() - t_opus) * 1000)
            timing['total_ms'] = int((time.time() - t0) * 1000)
            usage_tracker.log(response, 'daytime.opus_direct', timing['opus_ms'])

            response_text = response.content[0].text
            conversation.add_assistant_message(response_text)

            logger.info('Opus direct: %dms, %d chars', timing['opus_ms'], len(response_text))

            return {
                'response': response_text,
                'model': OPUS_MODEL,
                'timing': timing,
                'tool_calls': [],
            }

        except Exception as e:
            logger.error('Opus direct failed: %s — falling back to Sonnet', e)
            # Clear Opus flag and fall back
            conversation._opus_active = False
            system_prompt = self._build_system_prompt(conversation, interface, model='sonnet')
            response = await self.client.messages.create(
                model=SONNET_MODEL,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
                tools=TOOLS,
            )
            usage_tracker.log(response, 'daytime.opus_fallback_sonnet')
            response_text = ''
            for block in response.content:
                if hasattr(block, 'text'):
                    response_text += block.text
            if response_text.strip():
                conversation.add_assistant_message(response_text.strip())
            timing['total_ms'] = int((time.time() - t0) * 1000)
            return {
                'response': response_text.strip(),
                'model': SONNET_MODEL,
                'timing': timing,
                'tool_calls': [],
            }

    async def _handle_tool(
        self,
        tool_name: str,
        tool_input: dict,
        conversation: Conversation,
        system_prompt: str,
        messages: list[dict],
    ) -> str:
        """Execute a tool call and return the result as a string."""

        if tool_name == 'search_memory':
            return await self._tool_search_memory(tool_input['query'])

        elif tool_name == 'load_skill':
            return self._tool_load_skill(tool_input['skill_name'])

        elif tool_name == 'escalate_to_opus':
            return await self._tool_escalate_to_opus(
                tool_input['brief'],
                tool_input['question'],
                conversation,
                system_prompt,
            )

        elif tool_name == 'save_to_vault':
            return self._tool_save_to_vault(
                tool_input['path'],
                tool_input['content'],
                tool_input.get('mode', 'update'),
            )

        elif tool_name == 'read_from_vault':
            if 'list_dir' in tool_input and tool_input['list_dir'] is not None:
                return self._tool_list_vault(tool_input['list_dir'])
            elif 'path' in tool_input and tool_input['path'] is not None:
                return self._tool_read_from_vault(tool_input['path'])
            return 'Provide either path (to read a file) or list_dir (to list a directory).'

        elif tool_name == 'web_search':
            return await self._tool_web_search(
                tool_input['query'],
                tool_input.get('num_results', 5),
                tool_input.get('flag_for_research', False),
            )

        return f'Unknown tool: {tool_name}'

    async def _tool_search_memory(self, query: str) -> str:
        """Search Graphiti knowledge graph."""
        if not self.retriever:
            return 'Memory search unavailable — no retriever configured.'

        t0 = time.time()
        try:
            config = {
                'retrieval_mode': 'general_knowledge',
                'top_k': 5,
                'semantic_weight': 0.7,
                'recency_weight': 0.3,
                'suppress_decay': False,
                'sort_by': None,
                'entity_filter': [],
            }
            results = await self.retriever.retrieve(query, config)
            elapsed = int((time.time() - t0) * 1000)

            memories = results.get('memory_candidates', [])
            knowledge = results.get('knowledge_candidates', [])

            if not memories and not knowledge:
                return f'No relevant memories found for: "{query}" ({elapsed}ms)'

            parts = []
            for mem in memories[:5]:
                fact = mem.get('fact', '')
                if fact:
                    parts.append(f'- {fact}')
            for kb in knowledge[:3]:
                fact = kb.get('fact', '')
                if fact:
                    parts.append(f'- [knowledge] {fact}')

            return f'Memory search results ({elapsed}ms):\n' + '\n'.join(parts)

        except Exception as e:
            logger.error('Memory search failed: %s', e)
            return f'Memory search failed: {e}'

    def _tool_load_skill(self, skill_name: str) -> str:
        """Load a skill file from the skill library."""
        try:
            content = self.skill_loader.load_skill(skill_name)
            logger.info('Skill loaded: %s (%d chars)', skill_name, len(content))
            return f'Skill "{skill_name}" loaded:\n\n{content}'
        except (ValueError, FileNotFoundError):
            available = self.skill_loader.list_skills()
            return f'Skill "{skill_name}" not found. Available: {", ".join(available)}'

    async def _tool_escalate_to_opus(
        self,
        brief: str,
        question: str,
        conversation: Conversation,
        system_prompt: str,
    ) -> str:
        """Call Opus for deep thinking. Returns the response prefixed with [OPUS_RESPONSE].

        Opus gets the FULL SOUL.md (not Sonnet's lean core) for complete identity depth.
        """
        t0 = time.time()

        # Build Opus prompt with FULL identity + Sonnet's brief
        opus_system = self._build_system_prompt(conversation, model='opus') + (
            f'\n\n---\n\n## Sonnet\'s Brief\n'
            f'{brief}\n\n'
            f'The user is asking for your opinion, reasoning, or strategic thinking. '
            f'Respond in Pythia\'s voice. Be direct, give your honest opinion, push back if you disagree.'
        )

        # Full conversation history for Opus
        messages = conversation.get_messages_for_api()
        if not messages or messages[-1]['role'] != 'user':
            messages.append({'role': 'user', 'content': question})

        try:
            response = await self.client.messages.create(
                model=OPUS_MODEL,
                max_tokens=2048,
                system=opus_system,
                messages=messages,
            )

            elapsed = int((time.time() - t0) * 1000)
            usage_tracker.log(response, 'daytime.escalate_to_opus', elapsed)
            text = response.content[0].text
            logger.info('Opus response: %dms, %d chars', elapsed, len(text))

            return f'[OPUS_RESPONSE]{text}'

        except Exception as e:
            logger.error('Opus escalation failed: %s', e)
            return f'Opus escalation failed: {e}. Responding as Sonnet instead.'

    def _tool_save_to_vault(self, path: str, content: str, mode: str = 'update') -> str:
        """Save a page to the knowledge vault."""
        result = vault_save(path, content, mode)
        if result['status'] == 'ok':
            logger.info('Vault saved: %s (%d chars, mode=%s)', path, result['chars'], mode)
            return f'Saved to vault: {path} ({result["chars"]} chars, mode={mode})'
        else:
            logger.warning('Vault save failed: %s — %s', path, result['error'])
            return f'Vault save failed: {result["error"]}'

    def _tool_read_from_vault(self, path: str) -> str:
        """Read a page from the knowledge vault."""
        result = vault_read(path)
        if result['status'] == 'ok':
            logger.info('Vault read: %s (%d chars)', path, result['chars'])
            return f'Vault page: {path}\n\n{result["content"]}'
        else:
            return f'Vault read failed: {result["error"]}'

    def _tool_list_vault(self, subdir: str) -> str:
        """List files in a vault directory."""
        result = vault_list_dir(subdir)
        if result['status'] == 'ok':
            lines = [f'Vault directory: {result["directory"]} ({result["count"]} items)']
            for f in result['files']:
                if f['type'] == 'directory':
                    lines.append(f'  [dir] {f["name"]} ({f["files"]} files)')
                else:
                    lines.append(f'  [file] {f["name"]} ({f["chars"]} chars)')
            return '\n'.join(lines)
        else:
            return f'Vault list failed: {result["error"]}'

    async def _tool_web_search(self, query: str, num_results: int = 5,
                                flag_research: bool = False) -> str:
        """Search the web for current information."""
        result = await web_search(query, num_results, flag_research)
        if result['status'] == 'ok':
            lines = [f'Web search: "{query}" ({result["count"]} results)']
            for r in result['results']:
                lines.append(f'- {r["title"]}')
                lines.append(f'  {r["url"]}')
                if r['description']:
                    lines.append(f'  {r["description"][:200]}')
            if result.get('research_flag'):
                lines.append(f'\n[Research flagged] {result["research_flag"]["message"]}')
            return '\n'.join(lines)
        else:
            return f'Web search failed: {result["error"]}'
