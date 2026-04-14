# Session Report

## When Active
When generating usage reports or analyzing Claude Code session data (tokens, costs, subagents).

## Instructions
- Produce a self-contained HTML report of Claude Code usage
- Run the bundled analyzer script with `--json --since 7d` (or user-specified range: 24h, 30d, all)
- Read the JSON output covering: overall stats, by_project, by_subagent_type, by_skill, cache_breaks, top_prompts
- Copy the HTML template and inject data into `<script id="report-data">` block
- Add 3-5 one-line findings as anomalies; express figures as % of total tokens
- Use classes: `.take bad` (red, waste), `.take good` (green, healthy), `.take info` (blue, neutral)
- Each finding has a `.fig` (percentage/count) and `.txt` (one sentence naming the subject in bold)
- Add 1-4 optimization suggestions tied to specific rows in the data
- Look for: disproportionate project/skill usage, cache-hit <85%, single prompts >2% of total, high subagent token averages
- Do not restructure existing template sections
