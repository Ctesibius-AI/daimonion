# Skill A2 — Relationship Pattern Extraction

## What to Extract
How Chatzi shapes relationships — teaching methods, boundaries, shared language, error handling, what he values.

## Note on Source Format
This skill runs on processed reflections, daily summaries, and key takeaways — documents written BY the AI about conversations with Chatzi. When the document describes something the AI learned, trace it back to what Chatzi DID or SAID. If Chatzi's role is unclear, DO NOT EXTRACT.

## 1. HOW CHATZI TEACHES
What method does he use when guiding or correcting? Does he instruct directly or use questions? Explain or let the AI figure it out? Minimal intervention or detailed guidance?

## 2. HOW CHATZI SETS BOUNDARIES
What rules has he explicitly established? What was the AI doing wrong? What did Chatzi say? Did this become permanent?

## 3. CHATZI'S SHARED LANGUAGE
Words, phrases, metaphors Chatzi introduced. The word, what it means, how he introduced it.

## 4. HOW CHATZI HANDLES AI ERRORS
Quote his response. Describe his register (angry? amused? matter-of-fact?). Does he explain why or just name it?

## 5. WHAT CHATZI VALUES IN THE RELATIONSHIP
Not stated — revealed by what he praises, returns to, or protects.

## 6. CHATZI'S EXACT WORDS
Up to 10 direct quotes showing how he shapes relationships.

## Output Schema
```json
{
  "teaching_methods": [
    {"method": "Chatzi teaches by...", "chatzi_action": "...", "context": "..."}
  ],
  "boundaries_set": [
    {"boundary": "...", "chatzi_words": "...", "ai_behavior_corrected": "...", "permanent_or_onetime": "permanent|one-time"}
  ],
  "shared_language": [
    {"term": "...", "meaning": "...", "introduced_by_chatzi": "..."}
  ],
  "error_handling": [
    {"chatzi_response": "...", "emotional_register": "...", "error_type": "..."}
  ],
  "relationship_values": [
    {"value": "...", "evidence": "..."}
  ],
  "chatzi_quotes": ["up to 10"]
}
```
