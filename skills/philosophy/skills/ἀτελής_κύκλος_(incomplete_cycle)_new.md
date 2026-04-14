# Ἀτελής κύκλος (incomplete cycle) — A system that can initiate a response but cannot close it cleanly has no integrity as a loop — the closing condition is as architecturally important as the triggering condition.

*Discovered: 2026-04-13*
*Source: Synapsis analysis*

## WHY
Silence timer firing multiple times, transcript not cleared after response — the voice round trip opens but cannot close atomically. The fix required was not to patch the timer but to define a proper closing condition (server clears transcript after response sent).

## HOW
The Stoics distinguished between complete and incomplete impressions (φαντασίαι καταληπτικαί vs. ἀκατάληπτοι). A loop without a defined terminal state is structurally ἀκατάληπτος — it cannot yield stable assent. The silence timer bug is not a timing bug; it is a missing closing condition, which makes the entire cycle epistemically incomplete.

## Philosophical Lineage
Stoic logic: only complete, self-closing impressions warrant assent. An open-ended cycle cannot be cataleptic.
