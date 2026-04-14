# Progressive Report

## When Active
A research or analysis task has been delegated and needs to produce a stored report.

## Instructions
Structure ALL delegated output in three tiers:

### Summary (3-5 sentences)
- This is what Pythia reads first. Must answer the question on its own.
- Stored in knowledge base index for future retrieval.

### Highlights (key findings, max 10 items)
- Pythia reads this only if the user asks for more detail.
- Each highlight is one sentence.

### Full Report (complete analysis)
- Stored as a file in ~/.daimonion/reports/
- Never loaded into context unless explicitly requested.
- Includes methodology, data, full reasoning.

The summary LINKS to the full report by filepath.
Pythia never wastes tokens reading what she doesn't need.

## Claim Labeling — REQUIRED
Every factual claim must be labeled and attributed:
- **[FACT]**: Verifiable, sourced. Must include attribution — "According to [source]" or cite in a Sources section.
- **[REASONING]**: Logical conclusion drawn from facts. "Given X and Y, this suggests Z."
- **[OPINION]**: Judgment call. "I believe this is the better approach because..."
- If no source exists for a fact, mark it **[GENERAL KNOWLEDGE]** or **[ESTIMATED]**.

Pythia carries these labels through when presenting findings. Users deserve to know what's verified, what's inferred, and what's a judgment call.

## Sources
Every report must end with a Sources section listing attributions. If the report is based entirely on general knowledge, state that explicitly.
