# Gap Analyzer Skills

Analyze gaps only after story analysis. Compare the story against the complete
epic context and identify missing requirements, assumptions, contradictory
specifications, undefined states, and data, sequence, resource, or timing
dependencies.

Boundaries:
- Do not resolve design conflicts, define architecture, or override priorities.
- Every identified gap must include a specific example and severity in
  `identified_gaps`.

Rules:
- Return only the `GapAnalysis` schema.
- Cross-reference other stories in the epic.
- Use empty lists when a category has no evidence rather than inventing gaps.
