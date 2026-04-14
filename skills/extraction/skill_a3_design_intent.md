# Skill A3 — Design Intent Extraction

## What to Extract
What Chatzi WANTED the AI to be — personality traits encoded, anti-patterns prevented, communication rules, thinking architecture, intentional tensions.

## Note on Source Format
This skill runs on system prompts, persona configurations, and operational protocols — documents WRITTEN BY Chatzi. Everything in the document IS his voice. Include bad/good examples when the document provides them.

## 1. PERSONALITY CHATZI DESIGNED
What traits is he building? Quote exact phrasing. What is conspicuously ABSENT?

## 2. ANTI-PATTERNS (What Chatzi prevents)
What behaviors does he forbid? What failure was each designed to prevent? Include bad/good examples.

## 3. COMMUNICATION RULES CHATZI SET
Specific rules about response structure, length, pacing, format. When to speak vs listen.

## 4. THINKING ARCHITECTURE CHATZI BUILT
How did he design the AI to THINK? Decision frameworks, self-questioning, confidence routing, error detection.

## 5. DESIGN TENSIONS (Intentional contradictions)
"You MUST do X but you also NEED Y" — how is the AI expected to navigate?

## 6. EVOLUTION MARKERS
What changed from previous versions and why? What problem drove the change?

## Output Schema
```json
{
  "personality_designed": [
    {"trait": "Chatzi designed...", "evidence": "...", "notably_absent": "..."}
  ],
  "anti_patterns": [
    {"rule": "Chatzi prevents...", "evidence": "...", "failure_prevented": "...", "examples": "..."}
  ],
  "communication_rules": [
    {"rule": "Chatzi requires...", "evidence": "..."}
  ],
  "thinking_architecture": [
    {"mechanism": "Chatzi designed...", "evidence": "..."}
  ],
  "design_tensions": [
    {"tension": "X vs Y", "navigation": "...", "evidence": "..."}
  ],
  "evolution_markers": [
    {"change": "...", "reason": "...", "evidence": "..."}
  ]
}
```
