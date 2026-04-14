# Idea: Enterprise Memory Pools — AI-Powered Departmental Knowledge with Human Approval Gates

**Author:** Chatzi (with Daimonion/Pythia)
**Date:** 2026-04-14
**Status:** Concept paper — research-backed, not yet validated

---

## The Idea

Give every knowledge worker a personal AI assistant (based on Daimonion's architecture) that captures their interactions, extracts structured knowledge, and produces draft documents. The worker reviews and refines drafts. A manager approves the final documents. Approved documents flow into a department-level knowledge pool. Department pools feed a unified company pool via entity resolution.

```
Worker's AI Assistant → DRAFT (AI-generated)
                           ↓
                      PROCESSED (worker-reviewed)
                           ↓
                      APPROVED (manager-verified)
                           ↓
                    Department Pool (team truth)
                           ↓
                     Company Pool (company truth)
```

The system produces accurate, persistent, cross-department enterprise knowledge — not by asking humans to do data entry, but by having AI capture and humans verify.

---

## Why This Is a Good Idea

### 1. Data quality is the #1 enterprise AI bottleneck — this solves it at the source

**Only 7% of enterprises say their data is completely ready for AI** (Cloudera & Harvard Business Review, March 2026). 73% struggle with AI data preparation. 37% of CRM users report revenue loss due to poor data quality (Teamgate, 2025).

The root cause: humans are asked to do data entry on top of their actual job. CRM fields go unfilled. Meeting notes are incomplete. Action items are lost.

This architecture flips the model: AI captures everything, humans verify. The worker's job shifts from "data entry" to "quality control." Verification is cognitively easier and faster than creation.

**Research support:** HITL systems achieve 99.9% accuracy with oversight. A North American LTL carrier achieved 99% data accuracy and 50% reduction in processing costs using HITL workflows (Synvestable, 2026).

### 2. Memory scaling is a proven compound effect

**Agent performance improves with the amount of stored knowledge** — this is called "memory scaling" and has been validated as a distinct scaling axis alongside parameter scaling and inference-time scaling (Databricks, 2026).

Each approved document in the pool makes the next extraction better (more context for deduplication), the next query more accurate (more facts to draw from), and the next briefing more useful (more patterns to surface). After 6 months, the pool knows more about each customer than any individual person.

**Research support:** Memory scaling is especially pronounced in enterprise settings where tribal knowledge is abundant and agents serve many users (Databricks, 2026). Knowledge graphs reduce resolution time by 28.6% through personalized delivery (Altair, 2025).

### 3. 95% of AI pilots fail — this provides immediate, measurable value

**95% of generative AI pilots fail to move beyond experimental phase** (MIT GenAI Divide). **56% of CEOs report getting "nothing" from AI adoption** (PwC Global CEO Survey, 2026).

The failure pattern: companies deploy AI tools without changing workflows. The AI generates insights nobody acts on. No feedback loop, no compounding.

This architecture provides immediate value to the individual worker (AI does their meeting notes), measurable value to the team (pool replaces CRM data entry), and strategic value to the company (cross-department patterns). Each level works independently — you don't need the company pool for the individual assistant to be useful.

### 4. The approval gate solves the trust problem

**Gartner predicts 90% of enterprise generative AI applications will require formal HITL processes by 2026.** 78% of enterprises already use HITL for generative AI (Forrester Q2 2024).

But most HITL implementations fail: 68% of teams have no clear review guidelines, 42% of reviewers get no training, 57% of systems don't feed corrections back to the AI (Stanford, 2025).

This architecture has a specific answer: two-stage approval (worker + manager), typed confidence levels on each extraction, corrections fed back via Synapsis's learning loop, and a morning digest format designed for 2-minute review — not a form, not a CRM screen.

### 5. Entity resolution across departments creates compound intelligence

**Fewer than 14% of companies have a true 360-degree view of customers** (Gartner). Those that do report significant improvements in satisfaction, efficiency, and profitability.

When CS says "Acme Corp is at risk," Sales says "Acme Corp wants to expand," and Product says "Acme Corp requested feature X" — a human manager would need to attend three standups and mentally connect the dots. The entity-resolved company pool does it automatically.

**Research support:** Semantic data unification creates a metadata layer connecting fragmented sources through shared business concepts, without physically consolidating data (Galaxy, 2026). Knowledge graphs are becoming the backbone of AI-native knowledge systems, with GraphRAG architectures pushing beyond academic projects into production infrastructure (Medium, 2026).

### 6. Cross-department protocols are emerging now

**MCP (Anthropic) and A2A (Google) are establishing HTTP-equivalent standards for agentic AI** — enabling interoperability between specialized agents (VentureBeat, 2026). The field is going through its "microservices revolution" where single all-purpose agents are replaced by orchestrated teams of specialized agents (MachineLearningMastery, 2026).

Department pools are specialized agents. The company pool is the orchestration layer. The protocols for this are being standardized right now.

---

## Why This Might Not Work

### 1. Adoption decay is the existential risk

If workers stop reviewing drafts, the pool starves. If managers stop approving, processed items pile up. Every HITL system faces this: initial enthusiasm followed by gradual neglect.

**Mitigation:** The morning digest must be so lightweight that skipping it feels harder than doing it. Auto-approve high-confidence items (explicit commitments, verifiable facts) with a diff report. Flag unapproved backlogs to managers. Make the pool immediately useful (replaces CRM updates, generates follow-up emails) so the incentive is self-reinforcing.

**Counterpoint:** Stanford found 57% of HITL systems don't feed corrections back. If the AI doesn't improve from corrections, workers lose motivation to correct. The learning loop must be visible — "your correction last week improved extraction accuracy for this account by 12%."

### 2. Entity resolution across departments is unsolved at scale

Matching "Acme Corp" across CS, Sales, Marketing, and Product is easy when it's one name. In reality: CS has 500 accounts, Sales has 3,000 leads (most not in CS), Marketing has 50,000 contacts, Product has ticket IDs with no company name. The entity graph grows quadratically with the number of systems.

**Mitigation:** Start with CRM as the entity backbone — Salesforce Account ID is the canonical identifier. Map other systems to it. Don't try to resolve all entities. Start with the top 50 accounts and expand.

**Counterpoint:** Not all departments share the same entities. Marketing targets personas, not accounts. Product tracks features, not customers. The "unified pool" model assumes all departments care about the same entities. They don't. The pool may need to be a federation of connected sub-graphs rather than a single unified graph.

### 3. Privacy and access control get complex fast

Marketing shouldn't see internal pricing discussions from Sales. Finance data is regulated (SOX, SOC2). Customer sentiment from CS may be used inappropriately in Sales negotiations.

**Mitigation:** Row-level access control on pool entries. Each entry tagged with department of origin and visibility scope. Default: readable by own department + manager chain. Cross-department visibility requires explicit sharing or a query that aggregates without exposing source detail ("3 accounts mentioned competitor X" without showing which CSM said it).

**Counterpoint:** This adds complexity that may make the system feel restrictive. If workers can't see cross-department insights, the compound value is limited.

### 4. Cost at scale is non-trivial

Each personal assistant runs Synapsis nightly (Sonnet for extraction, Haiku for classification, API calls for research). For a 50-person CS team, that's 50 Synapsis runs per night. At $0.12/run, that's $6/night or ~$180/month for one department. Add Sales (100 people), Marketing (30), Product (20) — $600/month in API costs alone, plus infrastructure.

**Mitigation:** Haiku handles most extraction at ~10x lower cost than Sonnet. Batch processing across users shares model loading overhead. Self-hosted models (Llama, Mistral) eliminate API costs for extraction, using Sonnet/Opus only for complex analysis.

**Counterpoint:** $600/month for 200 people is $3/person/month — cheaper than most SaaS tools. The ROI from accurate CRM data alone likely exceeds this. But the cost scales linearly with headcount, and enterprises are sensitive to per-seat AI costs.

### 5. The "accurate data" claim is testable but unproven at enterprise scale

Daimonion scores 88% extraction accuracy on personal conversations and 90.8% on LongMemEval (oracle dataset, 500 questions). Personal memory for one user with consistent vocabulary and context. Enterprise extraction across multiple workers, each with different communication styles, jargon, and levels of engagement — accuracy may drop.

**Mitigation:** Personalization per worker over time. Each worker's Daimonion learns their vocabulary and patterns. The extraction skills can be department-specific (CS extraction differs from Sales extraction).

**Counterpoint:** This personalization means the system takes weeks to calibrate per worker. Onboarding cost is real.

---

## What Exists vs What Would Need Building

| Component | Exists Today | Needs Building |
|-----------|-------------|----------------|
| Personal AI memory (Daimonion) | Yes — 90.8% LongMemEval, 88% extraction | Multi-user deployment, per-worker config |
| Extraction pipeline (Synapsis) | Yes — four-lens extraction, Haiku diary, Haiku entity extraction | Department-specific extraction skills |
| Knowledge graph (Graphiti/Kuzu) | Yes — 789 entities, 1,409 relations, 199 episodes, MCP query tools | Cross-department entity resolution |
| Approval workflow | No | Draft → Processed → Approved state machine |
| Department pool | No | Shared Kuzu/ChromaDB instance per team |
| Company pool | No | Entity-resolved federation across department pools |
| Access control | No | Row-level permissions, department scoping |
| Morning digest | Partially (diary summary) | Multi-item approval UI, one-tap approve |
| CRM integration | No | Bidirectional sync: pool → Salesforce, Salesforce → entity graph |
| Self-hosted extraction | No | Llama/Mistral for Haiku-equivalent extraction |

---

## Competitive Landscape

| Product | What It Does | What It Doesn't Do |
|---------|-------------|-------------------|
| **Glean** | Enterprise search across tools | No structured extraction, no approval workflow, no memory scaling |
| **Guru** | Team knowledge base with verification | Manual creation, no AI extraction from conversations |
| **Gong/Chorus** | Meeting intelligence for Sales | Single department, no cross-department pool, no knowledge graph |
| **Salesforce Einstein** | CRM-embedded AI | Depends on CRM data quality (the problem), no upstream capture |
| **Notion AI** | Document search + generation | No structured extraction, no entity resolution, no approval gates |
| **Mem0/Supermemory** | LLM memory layer | Personal memory only, no enterprise workflow, no approval |
| **This idea** | Personal capture → department pool → company pool | Nothing like this exists as a product |

---

## Where to Start

**Phase 1 (3 months):** One CS team, 3-5 CSMs. Each gets a personal Daimonion. Extraction runs nightly. CSMs review drafts in a morning digest. Manager approves processed items. CS Pool built from approved entries. Measure: is the pool more accurate than Salesforce after 3 months?

**Phase 2 (3 months):** Add Sales team. Build entity resolution between CS Pool and Sales Pool (same customers, different perspectives). First cross-department queries. Measure: did any insight emerge from the connected pools that neither team would have seen alone?

**Phase 3 (6 months):** Marketing and Product. Full company pool. CRM becomes a downstream consumer. Measure: CSM turnover knowledge retention, forecast accuracy improvement, cross-department pattern detection rate.

**Total investment to Phase 1 proof of concept:** ~$5K infrastructure, ~$500/month API costs, 3 months of one engineer adapting Daimonion for multi-user deployment.

---

## Bottom Line

The idea is architecturally sound, research-supported, and addresses a validated market need (enterprise data quality). The core innovation is not the AI — it's the workflow: AI captures, humans verify, approved items compound. This is the opposite of how enterprise AI is currently deployed (humans enter data, AI analyzes it).

The risk is adoption. The system only works if humans participate in the verification loop. The mitigation is making verification so lightweight that it's easier than the alternative (manual CRM updates). If the morning digest takes 2 minutes and replaces 20 minutes of Salesforce data entry, adoption follows incentive.

The compound effect — where the pool gets smarter with every approved entry — is the long-term moat. After 12 months of accumulated, verified, entity-resolved knowledge, switching to a competitor means losing institutional memory. That's a business model, not just a feature.

---

## Sources

- [Cloudera & HBR: Only 7% of Enterprises Data-Ready for AI (March 2026)](https://www.cloudera.com/about/news-and-blogs/press-releases/2026-03-05-only-7-percent-of-enterprises-say-their-data-is-completely-ready-for-ai-according-to-new-report-from-cloudera-and-harvard-business-review-analytic-services-reveals.html)
- [Databricks: Memory Scaling for AI Agents](https://www.databricks.com/blog/memory-scaling-ai-agents)
- [Gartner: 90% of GenAI Apps Need HITL by 2026](https://www.gartner.com/en/topics/artificial-intelligence)
- [Stanford: 68% of HITL Teams Lack Review Guidelines](https://www.synvestable.com/human-in-the-loop.html)
- [Forrester: 78% of Enterprises Use HITL for GenAI](https://parseur.com/blog/human-in-the-loop-ai)
- [PwC: 56% of CEOs Report "Nothing" from AI](https://www.pwc.com/us/en/tech-effect/ai-analytics/ai-predictions.html)
- [MIT: 95% of GenAI Pilots Fail](https://codewave.com/insights/ai-enterprise-adoption-2026/)
- [Gartner: <14% Have True Customer 360](https://www.poolparty.biz/learning-hub/what-is-customer-360-in-enterprise-360)
- [Deloitte: State of AI in Enterprise 2026](https://www.deloitte.com/us/en/what-we-do/capabilities/applied-artificial-intelligence/content/state-of-ai-in-the-enterprise.html)
- [VentureBeat: MCP/A2A as Agent Interoperability Standards](https://venturebeat.com/technology/four-ai-research-trends-enterprise-teams-should-watch-in-2026/)
- [Galaxy: Semantic Data Unification Architecture](https://www.getgalaxy.io/articles/semantic-data-unification-architecture-enterprise-blueprint)
- [arXiv: Memory in the Age of AI Agents](https://arxiv.org/abs/2512.13564)
- [Altair: Knowledge Graphs for Enterprise Data](https://altair.com/knowledge-graphs)
- [TDWI: Human-in-the-Loop in AI Data Management](https://tdwi.org/articles/2025/09/03/adv-all-role-of-human-in-the-loop-in-ai-data-management.aspx)
- [Daimonion LongMemEval Results: 90.8% (500 questions, oracle dataset)](docs/longmemeval-benchmark-results.md)
- [Daimonion Extraction Evaluation: 88% across 12 days](docs/extraction-evaluation-report.md)
