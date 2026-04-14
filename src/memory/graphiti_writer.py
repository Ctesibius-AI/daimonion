"""
Graphiti Writer — Feeds Synapsis extractions into the Graphiti knowledge graph.

Two write modes:
1. add_episode: Feed verbatim + extracted context. Graphiti auto-extracts entities/relations.
   Used for: memories, conversation chunks, research findings.

2. add_triplet: Directly add entity → relation → entity. Manual, precise.
   Used for: explicit facts from knowledge extraction, floor assignments.

The writer manages Graphiti initialization, handles graceful degradation
when Graphiti/Kuzu is unavailable, and adds cross-references (source_drawer_id).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from src.config import GRAPH_DB_PATH, HAIKU_MODEL

logger = logging.getLogger('daimonion.graphiti_writer')

# Graphiti imports — optional, graceful degradation
try:
    from graphiti_core import Graphiti
    from graphiti_core.driver.kuzu_driver import KuzuDriver
    from graphiti_core.llm_client.anthropic_client import AnthropicClient
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.nodes import EpisodeType
    from src.memory.local_embedder import LocalEmbedder
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False
    logger.info('Graphiti not available — knowledge graph writes disabled')


class GraphitiWriter:
    """Writes Synapsis extractions to the Graphiti knowledge graph."""

    def __init__(self, db_path: str | None = None, model: str = HAIKU_MODEL):
        self.db_path = db_path or GRAPH_DB_PATH
        self.model = model
        self._graphiti = None
        self._initialized = False

    async def initialize(self):
        """Initialize Graphiti connection. Call once before writing."""
        if not GRAPHITI_AVAILABLE:
            logger.warning('Graphiti not installed — writer disabled')
            return

        if self._initialized:
            return

        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'

            driver = KuzuDriver(db=self.db_path)
            # Graphiti core expects _database for group_id routing — KuzuDriver doesn't set it
            driver._database = 'daimonion'
            # Create FTS indexes that Graphiti expects but KuzuDriver doesn't create
            self._ensure_fts_indexes(self.db_path)
            llm = AnthropicClient(config=LLMConfig(model=self.model))
            embedder = LocalEmbedder()
            # Bypass OpenAI key requirement — we use Anthropic + local embeddings
            if 'OPENAI_API_KEY' not in os.environ:
                os.environ['OPENAI_API_KEY'] = 'not-used'
            self._graphiti = Graphiti(
                graph_driver=driver,
                llm_client=llm,
                embedder=embedder,
            )
            await self._graphiti.build_indices_and_constraints()
            self._initialized = True
            logger.info('Graphiti writer initialized: %s', self.db_path)
        except Exception as e:
            logger.error('Graphiti initialization failed: %s', e)
            self._graphiti = None

    async def close(self):
        """Close the Graphiti connection."""
        if self._graphiti:
            try:
                await self._graphiti.close()
            except Exception:
                pass
            self._graphiti = None
            self._initialized = False

    @staticmethod
    def _ensure_fts_indexes(db_path: str):
        """Create FTS indexes Graphiti needs but KuzuDriver's setup_schema doesn't create."""
        try:
            import kuzu
            db = kuzu.Database(db_path)
            conn = kuzu.Connection(db)
            for table, index, cols in [
                ('Entity', 'node_name_and_summary', ['name', 'summary']),
                ('RelatesToNode_', 'edge_name_and_fact', ['name', 'fact']),
            ]:
                try:
                    conn.execute(f'CALL CREATE_FTS_INDEX("{table}", "{index}", {cols})')
                except Exception:
                    pass  # Already exists
            conn.close()
        except Exception as e:
            logger.warning('FTS index creation failed: %s', e)

    @property
    def available(self) -> bool:
        return self._initialized and self._graphiti is not None

    async def write_episode(
        self,
        name: str,
        body: str,
        source_description: str,
        reference_time: datetime | None = None,
        group_id: str = 'daimonion',
        source_drawer_id: str | None = None,
        floor: int | None = None,
    ) -> dict:
        """Write an episode to Graphiti. Graphiti auto-extracts entities and relations.

        Args:
            name: Episode name (e.g., "Project Alpha pricing decision")
            body: Episode content (verbatim or extracted summary)
            source_description: Where this came from (e.g., "Synapsis extraction 2026-04-09")
            reference_time: When this happened
            group_id: Graph partition
            source_drawer_id: Cross-reference to ChromaDB drawer
            floor: Floor number for temporal layering

        Returns:
            dict with status, episode_uuid, entities_created, edges_created
        """
        if not self.available:
            return {'status': 'unavailable', 'reason': 'Graphiti not initialized'}

        ref_time = reference_time or datetime.now(timezone.utc)

        # Add cross-reference metadata to the body
        metadata_lines = []
        if source_drawer_id:
            metadata_lines.append(f'[source_drawer_id: {source_drawer_id}]')
        if floor is not None:
            metadata_lines.append(f'[floor: {floor}]')
        if metadata_lines:
            body = ' '.join(metadata_lines) + '\n' + body

        try:
            result = await self._graphiti.add_episode(
                name=name,
                episode_body=body,
                source_description=source_description,
                reference_time=ref_time,
                source=EpisodeType.text,
                group_id=group_id,
            )

            logger.info(
                'Episode written: %s (%d nodes, %d edges)',
                name,
                len(result.nodes) if hasattr(result, 'nodes') else 0,
                len(result.edges) if hasattr(result, 'edges') else 0,
            )

            return {
                'status': 'ok',
                'episode_uuid': result.episode.uuid if hasattr(result, 'episode') else None,
                'nodes_created': len(result.nodes) if hasattr(result, 'nodes') else 0,
                'edges_created': len(result.edges) if hasattr(result, 'edges') else 0,
            }

        except Exception as e:
            logger.error('Episode write failed: %s', e)
            return {'status': 'error', 'error': str(e)}

    async def write_entities(
        self,
        entities: list[dict],
        date: str,
        group_id: str = 'daimonion',
    ) -> dict:
        """Write extracted entities + relations from Synapsis Agent 1.

        Each entity dict has:
            name: str
            type: str (project, person, tool, concept)
            relations: list of {predicate, object, confidence}

        Uses add_episode for each entity cluster — lets Graphiti handle
        entity resolution and deduplication.
        """
        if not self.available:
            return {'status': 'unavailable', 'entities': 0, 'edges': 0}

        total_nodes = 0
        total_edges = 0
        errors = 0

        for entity in entities:
            name = entity.get('name', '')
            entity_type = entity.get('type', 'concept')
            relations = entity.get('relations', [])

            if not name or not relations:
                continue

            # Build episode body from entity + relations
            lines = [f'{name} ({entity_type}):']
            for rel in relations:
                predicate = rel.get('predicate', '')
                obj = rel.get('object', '')
                confidence = rel.get('confidence', 1.0)
                lines.append(f'- {name} {predicate} {obj} (confidence: {confidence})')

            body = '\n'.join(lines)
            source_drawer_id = entity.get('source_drawer_id', '')

            result = await self.write_episode(
                name=f'{name} — {date}',
                body=body,
                source_description=f'Synapsis entity extraction {date}',
                reference_time=datetime.fromisoformat(f'{date}T23:00:00+00:00'),
                group_id=group_id,
                source_drawer_id=source_drawer_id,
                floor=entity.get('floor'),
            )

            if result['status'] == 'ok':
                total_nodes += result.get('nodes_created', 0)
                total_edges += result.get('edges_created', 0)
            else:
                errors += 1

        return {
            'status': 'ok' if errors == 0 else 'partial',
            'entities_processed': len(entities),
            'nodes_created': total_nodes,
            'edges_created': total_edges,
            'errors': errors,
        }

    async def invalidate_entity(
        self,
        entity_name: str,
        predicate: str | None = None,
        group_id: str = 'daimonion',
    ) -> dict:
        """Invalidate (soft-delete) edges related to an entity.

        Used when supersession is detected — the old fact's edges get
        expired_at set to now. The entity node stays (entities don't expire,
        only their relationships do).
        """
        if not self.available:
            return {'status': 'unavailable'}

        try:
            # Search for edges related to this entity
            results = await self._graphiti.search(
                query=entity_name,
                num_results=20,
                group_ids=[group_id],
            )

            invalidated = 0
            now = datetime.now(timezone.utc)

            for edge in results:
                # If predicate specified, only invalidate matching edges
                if predicate and predicate.lower() not in (edge.fact or '').lower():
                    continue

                # Skip already expired
                if edge.expired_at is not None:
                    continue

                # Set expired_at
                edge.expired_at = now
                await edge.save(self._graphiti.driver)
                invalidated += 1

            logger.info('Invalidated %d edges for entity: %s', invalidated, entity_name)
            return {'status': 'ok', 'invalidated': invalidated}

        except Exception as e:
            logger.error('Entity invalidation failed: %s — %s', entity_name, e)
            return {'status': 'error', 'error': str(e)}

    async def write_memories_as_episodes(
        self,
        memories: list[dict],
        date: str,
        group_id: str = 'daimonion',
    ) -> dict:
        """Write extracted memories as Graphiti episodes for rich graph building.

        Each memory becomes an episode. Graphiti extracts entities and relations
        from the memory content automatically. This is the bridge between
        ChromaDB (vector storage) and Graphiti (graph storage).
        """
        if not self.available:
            return {'status': 'unavailable', 'episodes': 0}

        episodes_written = 0
        errors = 0

        for mem in memories:
            content = mem.get('content', '')
            collection = mem.get('collection', 'episodic')
            significance = mem.get('significance', 'medium')

            if not content:
                continue

            # Only write significant memories to the graph
            if significance == 'low':
                continue

            result = await self.write_episode(
                name=f'{collection}: {content[:60]}',
                body=content,
                source_description=f'Synapsis memory extraction {date}',
                reference_time=datetime.fromisoformat(f'{date}T23:00:00+00:00'),
                group_id=group_id,
                floor=mem.get('floor'),
            )

            if result['status'] == 'ok':
                episodes_written += 1
            else:
                errors += 1

        return {
            'status': 'ok' if errors == 0 else 'partial',
            'episodes_written': episodes_written,
            'errors': errors,
        }
