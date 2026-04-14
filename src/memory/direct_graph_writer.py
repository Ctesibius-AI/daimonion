"""
Direct Graph Writer — writes Sonnet-extracted entities and relationships to Kuzu.

Bypasses Graphiti's LLM extraction (Haiku) since Sonnet already did the work.
Handles: entity creation, dedup by name, relationship creation, embeddings,
temporal tracking (valid_at, expired_at).

Cost: zero API calls. Sonnet extraction + direct Kuzu writes.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

import kuzu

from src.config import GRAPH_DB_PATH

logger = logging.getLogger('daimonion.direct_graph_writer')

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedder


class DirectGraphWriter:
    """Writes pre-extracted entities and relationships directly to Kuzu."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or GRAPH_DB_PATH
        self._db = None
        self._conn = None

    def initialize(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._db = kuzu.Database(self.db_path)
        self._conn = kuzu.Connection(self._db)
        self._ensure_schema()
        self._ensure_fts_indexes()

    def _ensure_schema(self):
        """Ensure Graphiti schema tables exist. Uses Graphiti's own initialization."""
        try:
            # Check if Entity table exists
            self._conn.execute('MATCH (n:Entity) RETURN count(n) LIMIT 1')
        except Exception:
            # Schema missing — initialize via Graphiti
            import asyncio
            from graphiti_core import Graphiti
            from graphiti_core.driver.kuzu_driver import KuzuDriver
            from graphiti_core.llm_client.anthropic_client import AnthropicClient
            from graphiti_core.llm_client.config import LLMConfig
            from src.memory.local_embedder_adapter import (
                LocalSentenceTransformerEmbedder,
                LocalCrossEncoder,
            )

            async def _init():
                driver = KuzuDriver(db=self.db_path)
                llm = AnthropicClient(config=LLMConfig(model='claude-sonnet-4-6'))
                emb = LocalSentenceTransformerEmbedder()
                ce = LocalCrossEncoder()
                g = Graphiti(graph_driver=driver, llm_client=llm, embedder=emb, cross_encoder=ce)
                await g.build_indices_and_constraints()
                await driver.close()

            asyncio.run(_init())
            # Reconnect after Graphiti's async init
            self._db = kuzu.Database(self.db_path)
            self._conn = kuzu.Connection(self._db)
            logger.info('Graphiti schema initialized')

    def close(self):
        self._conn = None
        self._db = None

    @property
    def available(self) -> bool:
        return self._conn is not None

    def _ensure_fts_indexes(self):
        for table, index, cols in [
            ('Entity', 'node_name_and_summary', ['name', 'summary']),
            ('RelatesToNode_', 'edge_name_and_fact', ['name', 'fact']),
        ]:
            try:
                self._conn.execute(
                    f'CALL CREATE_FTS_INDEX("{table}", "{index}", {cols})'
                )
            except Exception:
                pass

    def _find_entity_by_name(self, name: str, group_id: str = 'daimonion') -> str | None:
        """Find existing entity UUID by name."""
        try:
            r = self._conn.execute(
                'MATCH (n:Entity) WHERE n.name = $name AND n.group_id = $gid RETURN n.uuid',
                parameters={'name': name, 'gid': group_id},
            )
            if r.has_next():
                return r.get_next()[0]
        except Exception:
            pass
        return None

    def _embed(self, text: str) -> list[float]:
        model = _get_embedder()
        return model.encode(text).tolist()

    def write_entities(
        self,
        entities: list[dict],
        date: str,
        group_id: str = 'daimonion',
    ) -> dict:
        """Write Sonnet-extracted entities and their relationships to Kuzu.

        Each entity dict has:
            name: str
            type: str (project, person, tool, concept)
            relations: list of {predicate, object, confidence}
        """
        if not self.available:
            return {'status': 'unavailable'}

        now = datetime.now(timezone.utc)
        nodes_created = 0
        nodes_updated = 0
        edges_created = 0
        errors = 0

        for entity in entities:
            name = entity.get('name', '').strip()
            entity_type = entity.get('type', 'concept')
            relations = entity.get('relations', [])

            if not name:
                continue

            try:
                # Find or create source entity
                source_uuid = self._find_entity_by_name(name, group_id)
                if source_uuid:
                    # Update summary
                    summary_addition = '; '.join(
                        f"{name} {r['predicate']} {r['object']}"
                        for r in relations if r.get('predicate') and r.get('object')
                    )
                    self._conn.execute(
                        'MATCH (n:Entity) WHERE n.uuid = $uuid '
                        'SET n.summary = n.summary + $sep + $addition',
                        parameters={
                            'uuid': source_uuid,
                            'sep': '\n',
                            'addition': summary_addition,
                        },
                    )
                    nodes_updated += 1
                else:
                    source_uuid = str(uuid.uuid4())
                    summary = '; '.join(
                        f"{name} {r['predicate']} {r['object']}"
                        for r in relations if r.get('predicate') and r.get('object')
                    )
                    embedding = self._embed(name)
                    self._conn.execute(
                        'CREATE (n:Entity {'
                        '  uuid: $uuid, name: $name, group_id: $gid,'
                        '  labels: $labels, created_at: $ts,'
                        '  name_embedding: $emb, summary: $summary,'
                        '  attributes: $attrs'
                        '})',
                        parameters={
                            'uuid': source_uuid,
                            'name': name,
                            'gid': group_id,
                            'labels': [entity_type],
                            'ts': now,
                            'emb': embedding,
                            'summary': summary,
                            'attrs': '{}',
                        },
                    )
                    nodes_created += 1

                # Create relationships
                for rel in relations:
                    predicate = rel.get('predicate', '').strip()
                    obj_name = rel.get('object', '').strip()
                    if not predicate or not obj_name:
                        continue

                    # Find or create target entity
                    target_uuid = self._find_entity_by_name(obj_name, group_id)
                    if not target_uuid:
                        target_uuid = str(uuid.uuid4())
                        target_emb = self._embed(obj_name)
                        self._conn.execute(
                            'CREATE (n:Entity {'
                            '  uuid: $uuid, name: $name, group_id: $gid,'
                            '  labels: $labels, created_at: $ts,'
                            '  name_embedding: $emb, summary: $summary,'
                            '  attributes: $attrs'
                            '})',
                            parameters={
                                'uuid': target_uuid,
                                'name': obj_name,
                                'gid': group_id,
                                'labels': ['concept'],
                                'ts': now,
                                'emb': target_emb,
                                'summary': '',
                                'attrs': '{}',
                            },
                        )
                        nodes_created += 1

                    # Create edge (RelatesToNode_ + two RELATES_TO edges)
                    edge_uuid = str(uuid.uuid4())
                    fact = f'{name} {predicate} {obj_name}'
                    fact_emb = self._embed(fact)

                    self._conn.execute(
                        'CREATE (e:RelatesToNode_ {'
                        '  uuid: $uuid, group_id: $gid, created_at: $ts,'
                        '  name: $pred, fact: $fact, fact_embedding: $emb,'
                        '  episodes: $eps, expired_at: $exp,'
                        '  valid_at: $valid, invalid_at: $inv,'
                        '  attributes: $attrs'
                        '})',
                        parameters={
                            'uuid': edge_uuid,
                            'gid': group_id,
                            'ts': now,
                            'pred': predicate.upper(),
                            'fact': fact,
                            'emb': fact_emb,
                            'eps': [date],
                            'exp': None,
                            'valid': now,
                            'inv': None,
                            'attrs': '{}',
                        },
                    )

                    # Source -> Edge
                    self._conn.execute(
                        'MATCH (s:Entity), (e:RelatesToNode_) '
                        'WHERE s.uuid = $sid AND e.uuid = $eid '
                        'CREATE (s)-[:RELATES_TO]->(e)',
                        parameters={'sid': source_uuid, 'eid': edge_uuid},
                    )
                    # Edge -> Target
                    self._conn.execute(
                        'MATCH (e:RelatesToNode_), (t:Entity) '
                        'WHERE e.uuid = $eid AND t.uuid = $tid '
                        'CREATE (e)-[:RELATES_TO]->(t)',
                        parameters={'eid': edge_uuid, 'tid': target_uuid},
                    )
                    edges_created += 1

            except Exception as e:
                logger.error('Error writing entity %s: %s', name, e)
                errors += 1

        return {
            'status': 'ok' if errors == 0 else 'partial',
            'nodes_created': nodes_created,
            'nodes_updated': nodes_updated,
            'edges_created': edges_created,
            'errors': errors,
        }

    def write_memories_as_episodes(
        self,
        memories: list[dict],
        date: str,
        group_id: str = 'daimonion',
    ) -> dict:
        """Write memories as Episodic nodes."""
        if not self.available:
            return {'status': 'unavailable', 'episodes': 0}

        now = datetime.now(timezone.utc)
        written = 0

        for mem in memories:
            content = mem.get('content', '')
            collection = mem.get('collection', 'episodic')
            if not content:
                continue

            try:
                ep_uuid = str(uuid.uuid4())
                self._conn.execute(
                    'CREATE (e:Episodic {uuid: $a, name: $b, group_id: $c,'
                    ' created_at: $d, source: $e, source_description: $f,'
                    ' content: $g, valid_at: $h, entity_edges: $i})',
                    parameters={
                        'a': ep_uuid,
                        'b': f'{collection}: {content[:60]}',
                        'c': group_id,
                        'd': now,
                        'e': 'synapsis',
                        'f': f'Synapsis extraction {date}',
                        'g': content,
                        'h': now,
                        'i': [],
                    },
                )
                written += 1
            except Exception as e:
                logger.error('Error writing memory episode: %s', e)

        return {'status': 'ok', 'episodes_written': written}

    def invalidate_entity(self, entity_name: str, group_id: str = 'daimonion') -> dict:
        """Expire all edges for an entity (supersession)."""
        if not self.available:
            return {'status': 'unavailable'}

        now = datetime.now(timezone.utc)
        try:
            # Find entity
            entity_uuid = self._find_entity_by_name(entity_name, group_id)
            if not entity_uuid:
                return {'status': 'not_found'}

            # Expire all outgoing edges
            r = self._conn.execute(
                'MATCH (s:Entity)-[:RELATES_TO]->(e:RelatesToNode_) '
                'WHERE s.uuid = $uuid AND e.expired_at IS NULL '
                'SET e.expired_at = $now '
                'RETURN count(e)',
                parameters={'uuid': entity_uuid, 'now': now},
            )
            count = r.get_next()[0] if r.has_next() else 0
            return {'status': 'ok', 'invalidated': count}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
