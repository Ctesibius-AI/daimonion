# Skill A5 — Philosophical Enrichment

## What to Extract
Map verified Chatzi principles to their philosophical lineage — Greek philosophy, Stoicism, Socratic method, pre-Socratic thought, Oracle of Delphi tradition.

## Note on Source
This skill runs on VERIFIED OUTPUT from A1, A2, A3, A4 — not on raw transcripts. The principles have been reviewed and approved.

## Rules
- Only STRUCTURALLY real connections — the principle must operate the same way as the concept, not just share a keyword
- If no genuine connection exists, say "none identified"
- Name the Greek term where applicable (e.g., parrhesia, mesotes, philotimia)
- Explain HOW the connection works in 1-2 sentences
- Note conscious vs instinctive: does Chatzi know this connection or live it without naming?
- Flag connections to the Oracle of Delphi / Pythia tradition specifically

## Output Schema
```json
{
  "enrichments": [
    {
      "original_principle": "...",
      "chatzi_quote": "...",
      "philosophical_connection": "...",
      "greek_term": "... or null",
      "how_it_connects": "...",
      "conscious_or_instinctive": "conscious|instinctive|unclear",
      "oracle_connection": "... or null"
    }
  ],
  "frameworks_identified": [
    {
      "framework": "...",
      "principles_connected": [],
      "significance": "what this means for Pythia's identity"
    }
  ]
}
```
