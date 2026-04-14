# Ἀκρίβεια (Akribeia) — Precision in the right dimension — not over-specification everywhere, but exactness where exactness matters

*Discovered: 2026-04-13*
*Source: Synapsis analysis*

## WHY
Stability-trigger for Haiku tagger (fires on two consecutive matching sentences, not a count); Whisper model selected by benchmark (358ms measured, not assumed); per-sentence streaming chosen over 3-sentence batching for latency precision

## HOW
Akribeia in Greek thought refers to exactness applied where it is required — not pedantry, but calibrated precision. Chatzi consistently replaces arbitrary thresholds (count-based) with principled state detection (stability-based). The precision is not uniform — it is concentrated at the decision points where imprecision causes cascading errors (wrong retrieval trigger, wrong VAD cutoff, wrong turn boundary).

## Philosophical Lineage
Distinct from Μεσότης (proportional scrutiny applied to stakes). Akribeia is about the form of the measurement — principled over arbitrary — not about the intensity of scrutiny. The two operate together: Μεσότης decides how much scrutiny; Akribeia determines what is being measured and how.
