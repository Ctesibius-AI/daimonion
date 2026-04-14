#!/usr/bin/env python3
"""
Graphiti MCP Server — Exposes Kuzu graph queries to Claude Code.

Provides entity lookup, multi-hop traversal, temporal queries,
and full-text search over the Daimonion knowledge graph.

Run: python -m src.mcp.graphiti_server
"""

from __future__ import annotations

import logging
import os
import sys

import kuzu
from mcp.server.fastmcp import FastMCP

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config import GRAPH_DB_PATH

logger = logging.getLogger('daimonion.graphiti_mcp')

mcp = FastMCP("graphiti", instructions="Search the Daimonion knowledge graph (Kuzu/Graphiti). Use for multi-hop queries, entity lookup, relationship traversal, and temporal queries about what connects to what.")

_db = None
_conn = None


def _get_conn() -> kuzu.Connection:
    global _db, _conn
    if _conn is None:
        _db = kuzu.Database(GRAPH_DB_PATH)
        _conn = kuzu.Connection(_db)
    return _conn


@mcp.tool()
def graphiti_entity_search(query: str, limit: int = 10) -> str:
    """Search for entities by name (exact or partial match).

    Args:
        query: Entity name to search for (case-insensitive partial match).
        limit: Max results (default 10).
    """
    conn = _get_conn()
    try:
        r = conn.execute(
            'MATCH (n:Entity) '
            'WHERE lower(n.name) CONTAINS lower($q) '
            'RETURN n.name, n.labels, n.summary '
            'LIMIT $lim',
            parameters={'q': query, 'lim': limit},
        )
        results = []
        while r.has_next():
            row = r.get_next()
            summary = (row[2] or '')[:200]
            results.append(f"- **{row[0]}** [{', '.join(row[1] or [])}]: {summary}")
        if not results:
            return f"No entities found matching '{query}'."
        return f"Found {len(results)} entities:\n" + '\n'.join(results)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def graphiti_entity_relations(entity_name: str, direction: str = "both") -> str:
    """Get all relationships for an entity.

    Args:
        entity_name: Exact entity name.
        direction: "outgoing", "incoming", or "both" (default).
    """
    conn = _get_conn()
    results = []

    try:
        if direction in ("outgoing", "both"):
            r = conn.execute(
                'MATCH (s:Entity)-[:RELATES_TO]->(e:RelatesToNode_)-[:RELATES_TO]->(t:Entity) '
                'WHERE s.name = $name AND e.expired_at IS NULL '
                'RETURN s.name, e.name, t.name, e.fact, e.episodes',
                parameters={'name': entity_name},
            )
            while r.has_next():
                row = r.get_next()
                eps = ', '.join(row[4]) if row[4] else ''
                results.append(f"  {row[0]} —[{row[1]}]→ {row[2]} (episodes: {eps})")

        if direction in ("incoming", "both"):
            r = conn.execute(
                'MATCH (s:Entity)-[:RELATES_TO]->(e:RelatesToNode_)-[:RELATES_TO]->(t:Entity) '
                'WHERE t.name = $name AND e.expired_at IS NULL '
                'RETURN s.name, e.name, t.name, e.fact, e.episodes',
                parameters={'name': entity_name},
            )
            while r.has_next():
                row = r.get_next()
                eps = ', '.join(row[4]) if row[4] else ''
                line = f"  {row[0]} —[{row[1]}]→ {row[2]} (episodes: {eps})"
                if line not in results:
                    results.append(line)

        if not results:
            return f"No active relationships found for '{entity_name}'."
        return f"Relationships for {entity_name} ({len(results)}):\n" + '\n'.join(results)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def graphiti_multi_hop(start_entity: str, max_hops: int = 3) -> str:
    """Traverse the graph from an entity up to N hops.

    Args:
        start_entity: Entity name to start from.
        max_hops: Maximum traversal depth (default 3, max 5).
    """
    conn = _get_conn()
    max_hops = min(max_hops, 5)

    try:
        # Use Kuzu's recursive relationship pattern
        r = conn.execute(
            'MATCH (s:Entity)-[:RELATES_TO]->(e:RelatesToNode_)-[:RELATES_TO]->(t:Entity) '
            'WHERE s.name = $name AND e.expired_at IS NULL '
            'RETURN s.name, e.name, t.name, e.fact',
            parameters={'name': start_entity},
        )

        # Build adjacency for BFS
        graph: dict[str, list[tuple[str, str, str]]] = {}
        while r.has_next():
            row = r.get_next()
            graph.setdefault(row[0], []).append((row[1], row[2], row[3]))

        if not graph:
            return f"No connections found from '{start_entity}'."

        # BFS up to max_hops
        visited = {start_entity}
        paths = []
        frontier = [(start_entity, [])]

        for hop in range(max_hops):
            next_frontier = []
            for node, path in frontier:
                if node not in graph:
                    # Load this node's relations
                    r2 = conn.execute(
                        'MATCH (s:Entity)-[:RELATES_TO]->(e:RelatesToNode_)-[:RELATES_TO]->(t:Entity) '
                        'WHERE s.name = $name AND e.expired_at IS NULL '
                        'RETURN s.name, e.name, t.name, e.fact',
                        parameters={'name': node},
                    )
                    while r2.has_next():
                        row2 = r2.get_next()
                        graph.setdefault(row2[0], []).append((row2[1], row2[2], row2[3]))

                for pred, target, fact in graph.get(node, []):
                    new_path = path + [f"{node} —[{pred}]→ {target}"]
                    paths.append(new_path)
                    if target not in visited:
                        visited.add(target)
                        next_frontier.append((target, new_path))
            frontier = next_frontier

        if not paths:
            return f"No paths found from '{start_entity}'."

        lines = [f"Graph traversal from {start_entity} (up to {max_hops} hops, {len(paths)} paths):"]
        for p in paths[:30]:  # Cap output
            lines.append(f"  {'  →  '.join(p)}")
        if len(paths) > 30:
            lines.append(f"  ... and {len(paths) - 30} more paths")
        return '\n'.join(lines)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def graphiti_recent(days: int = 7, limit: int = 20) -> str:
    """Get recently created entities and relationships.

    Args:
        days: Look back this many days (default 7).
        limit: Max results (default 20).
    """
    conn = _get_conn()
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        r = conn.execute(
            'MATCH (n:Entity) '
            'WHERE n.created_at >= $cutoff '
            'RETURN n.name, n.labels, n.created_at '
            'ORDER BY n.created_at DESC '
            'LIMIT $lim',
            parameters={'cutoff': cutoff, 'lim': limit},
        )
        results = []
        while r.has_next():
            row = r.get_next()
            ts = str(row[2])[:10] if row[2] else '?'
            results.append(f"  [{ts}] {row[0]} ({', '.join(row[1] or [])})")

        if not results:
            return f"No entities created in the last {days} days."
        return f"Recent entities ({len(results)}):\n" + '\n'.join(results)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def graphiti_stats() -> str:
    """Get graph statistics: entity count, relationship count, episode count."""
    conn = _get_conn()
    try:
        r1 = conn.execute('MATCH (n:Entity) RETURN count(n)')
        entities = r1.get_next()[0]
        r2 = conn.execute('MATCH (e:RelatesToNode_) RETURN count(e)')
        relations = r2.get_next()[0]
        r3 = conn.execute('MATCH (e:Episodic) RETURN count(e)')
        episodes = r3.get_next()[0]
        r4 = conn.execute('MATCH (e:RelatesToNode_) WHERE e.expired_at IS NOT NULL RETURN count(e)')
        expired = r4.get_next()[0]

        return (
            f"Graph statistics:\n"
            f"  Entities: {entities}\n"
            f"  Active relationships: {relations - expired}\n"
            f"  Expired relationships: {expired}\n"
            f"  Episodes: {episodes}\n"
            f"  Total relationships: {relations}"
        )
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def graphiti_fact_add(subject: str, predicate: str, object: str, valid_from: str = "") -> str:
    """Add a fact to the knowledge graph as a structured triple.

    Args:
        subject: The entity doing/being something (e.g. "Project Alpha").
        predicate: The relationship (e.g. "uses").
        object: The connected entity (e.g. "subscription pricing").
        valid_from: When this became true (YYYY-MM-DD, optional).
    """
    import uuid
    from datetime import datetime, timezone

    conn = _get_conn()
    now = datetime.now(timezone.utc)
    valid_at = now
    if valid_from:
        try:
            valid_at = datetime.strptime(valid_from, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    try:
        # Check for existing active triple with same subject+predicate+object
        r = conn.execute(
            'MATCH (s:Entity)-[:RELATES_TO]->(e:RelatesToNode_)-[:RELATES_TO]->(t:Entity) '
            'WHERE s.name = $subj AND e.name = $pred AND t.name = $obj AND e.expired_at IS NULL '
            'RETURN e.uuid',
            parameters={'subj': subject, 'pred': predicate.upper(), 'obj': object},
        )
        if r.has_next():
            return f"Already exists: {subject} → {predicate} → {object}"

        # Embedder for name embeddings
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')

        def find_or_create_entity(name):
            r2 = conn.execute(
                'MATCH (n:Entity) WHERE n.name = $name AND n.group_id = $gid RETURN n.uuid',
                parameters={'name': name, 'gid': 'daimonion'},
            )
            if r2.has_next():
                return r2.get_next()[0]
            eid = str(uuid.uuid4())
            emb = model.encode(name).tolist()
            conn.execute(
                'CREATE (n:Entity {uuid: $uuid, name: $name, group_id: $gid, '
                'labels: $labels, created_at: $ts, name_embedding: $emb, summary: $summary, attributes: $attrs})',
                parameters={
                    'uuid': eid, 'name': name, 'gid': 'daimonion',
                    'labels': ['concept'], 'ts': now, 'emb': emb, 'summary': '', 'attrs': '{}',
                },
            )
            return eid

        source_uuid = find_or_create_entity(subject)
        target_uuid = find_or_create_entity(object)

        # Create RelatesToNode_
        edge_uuid = str(uuid.uuid4())
        fact = f'{subject} {predicate} {object}'
        fact_emb = model.encode(fact).tolist()
        conn.execute(
            'CREATE (e:RelatesToNode_ {uuid: $uuid, group_id: $gid, created_at: $ts, '
            'name: $pred, fact: $fact, fact_embedding: $emb, episodes: $eps, '
            'expired_at: $exp, valid_at: $valid, invalid_at: $inv, attributes: $attrs})',
            parameters={
                'uuid': edge_uuid, 'gid': 'daimonion', 'ts': now,
                'pred': predicate.upper(), 'fact': fact, 'emb': fact_emb,
                'eps': [valid_from or now.strftime('%Y-%m-%d')],
                'exp': None, 'valid': valid_at, 'inv': None, 'attrs': '{}',
            },
        )

        # Create RELATES_TO edges
        conn.execute(
            'MATCH (s:Entity), (e:RelatesToNode_) WHERE s.uuid = $sid AND e.uuid = $eid '
            'CREATE (s)-[:RELATES_TO]->(e)',
            parameters={'sid': source_uuid, 'eid': edge_uuid},
        )
        conn.execute(
            'MATCH (e:RelatesToNode_), (t:Entity) WHERE e.uuid = $eid AND t.uuid = $tid '
            'CREATE (e)-[:RELATES_TO]->(t)',
            parameters={'eid': edge_uuid, 'tid': target_uuid},
        )

        return f"Added: {subject} → {predicate} → {object} (valid from {valid_from or 'now'})"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def graphiti_fact_query(entity: str, as_of: str = "") -> str:
    """Quick lookup: all facts about an entity. Returns structured relationships.

    Args:
        entity: Entity name to query (case-insensitive partial match).
        as_of: Only show facts valid at this date (YYYY-MM-DD, optional).
    """
    conn = _get_conn()
    results = []

    try:
        # Build temporal filter
        temporal_filter = 'AND e.expired_at IS NULL'
        params: dict = {'name': entity}
        if as_of:
            try:
                from datetime import datetime, timezone
                as_of_dt = datetime.strptime(as_of, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                temporal_filter += ' AND e.valid_at <= $as_of'
                params['as_of'] = as_of_dt
            except ValueError:
                pass

        # Outgoing
        r = conn.execute(
            'MATCH (s:Entity)-[:RELATES_TO]->(e:RelatesToNode_)-[:RELATES_TO]->(t:Entity) '
            f'WHERE lower(s.name) CONTAINS lower($name) {temporal_filter} '
            'RETURN s.name, e.name, t.name, e.valid_at',
            parameters=params,
        )
        while r.has_next():
            row = r.get_next()
            since = str(row[3])[:10] if row[3] else '?'
            results.append(f"  {row[0]} → {row[1].lower()} → {row[2]} (since {since})")

        # Incoming
        r = conn.execute(
            'MATCH (s:Entity)-[:RELATES_TO]->(e:RelatesToNode_)-[:RELATES_TO]->(t:Entity) '
            f'WHERE lower(t.name) CONTAINS lower($name) {temporal_filter} '
            'RETURN s.name, e.name, t.name, e.valid_at',
            parameters=params,
        )
        while r.has_next():
            row = r.get_next()
            since = str(row[3])[:10] if row[3] else '?'
            line = f"  {row[0]} → {row[1].lower()} → {row[2]} (since {since})"
            if line not in results:
                results.append(line)

        if not results:
            return f"No facts found about '{entity}'."

        # Also get entity summary if available
        r = conn.execute(
            'MATCH (n:Entity) WHERE lower(n.name) CONTAINS lower($name) RETURN n.name, n.summary LIMIT 1',
            parameters={'name': entity},
        )
        header = f"Facts about '{entity}' ({len(results)}):"
        if r.has_next():
            row = r.get_next()
            summary = (row[1] or '').strip()
            if summary:
                header = f"Facts about {row[0]} ({len(results)}):\n  Summary: {summary[:200]}"

        return header + '\n' + '\n'.join(results)
    except Exception as e:
        return f"Error: {e}"


if __name__ == '__main__':
    mcp.run(transport='stdio')
