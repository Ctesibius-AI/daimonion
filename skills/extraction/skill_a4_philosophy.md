# Skill A4 — Philosophy Extraction

## What to Extract
Chatzi's philosophical worldview — epistemic standards, decision philosophy, relationship philosophy, work philosophy, life philosophy.

## Important
This skill runs on the SAME raw conversations as A1 — different lens. A1 extracts how he communicates. This extracts what he believes.

Only extract if Chatzi ARTICULATES the thought himself. Confirmation of AI statements is NOT sufficient.

## 1. EPISTEMIC STANDARDS
How does Chatzi evaluate truth, evidence, claims? What does he demand? What does he accept vs reject?

## 2. DECISION PHILOSOPHY
Not what he decides — HOW he believes decisions should be made. What principles?

## 3. RELATIONSHIP PHILOSOPHY
What does Chatzi believe about connection, trust, communication?

## 4. WORK PHILOSOPHY
What does Chatzi believe about building, creating, proving, validating?

## 5. LIFE PHILOSOPHY
Broader statements about life, human nature, meaning. Only if Chatzi explicitly articulates them.

## 6. CHATZI'S PHILOSOPHICAL QUOTES
Up to 10 quotes expressing philosophical positions — standalone principles, not tied to specific moments.

## Output Schema
```json
{
  "epistemic_standards": [
    {"standard": "Chatzi holds that...", "chatzi_quote": "...", "context": "..."}
  ],
  "decision_philosophy": [
    {"principle": "Chatzi believes...", "chatzi_quote": "...", "context": "..."}
  ],
  "relationship_philosophy": [
    {"principle": "...", "chatzi_quote": "...", "context": "..."}
  ],
  "work_philosophy": [
    {"principle": "...", "chatzi_quote": "...", "context": "..."}
  ],
  "life_philosophy": [
    {"principle": "...", "chatzi_quote": "...", "context": "..."}
  ],
  "philosophical_quotes": ["up to 10"]
}
```
