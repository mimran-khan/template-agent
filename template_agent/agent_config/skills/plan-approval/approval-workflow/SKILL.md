---
name: approval-workflow
description: Use this skill when validating and presenting a research plan for user approval. Covers plan quality checks, reformatting, effort estimation, and the approval prompt.
---

# Plan Approval Workflow

## Validation Criteria

Before presenting the plan, check for these issues:

### Structural Issues
- **Overlapping sub-questions:** Two sub-questions that would produce largely the same search results. Merge them.
- **Missing angles:** Obvious facets of the topic that the planner omitted. Flag them as suggestions.
- **Too broad sub-questions:** A single sub-question that should be split into 2-3 more focused ones.
- **Too narrow sub-questions:** Multiple sub-questions that are essentially the same and should be merged.

### Feasibility Issues
- **Unanswerable via web search:** Sub-questions requiring proprietary data, internal databases, or real-time APIs that web search cannot access. Flag and suggest alternatives.
- **Excessive scope:** More than 8 sub-questions for a single research request. Suggest prioritization or phased research.

### Search Query Quality
- **Too generic:** Queries like "what is AI" that would return noise. Suggest more specific terms.
- **Missing key terms:** Queries that omit critical domain-specific keywords.
- **Duplicate queries:** Same query appearing under different sub-questions.

## Effort Estimation

Calculate and present:
- **Total web searches:** Count all suggested search queries across all sub-questions.
- **Number of sub-questions:** Direct count from the plan.
- **Complexity tier:** SIMPLE (1-2 sub-questions), MODERATE (3-5), COMPLEX (6-8).

## Presentation Format

Structure the output as:

```
## Research Plan for Review

**Topic:** [Original research question]
**Complexity:** [SIMPLE | MODERATE | COMPLEX]
**Estimated effort:** [N] web searches across [M] sub-questions

### Proposed Sub-questions

1. **[Sub-question text]**
   Searches: "query a", "query b"

2. **[Sub-question text]**
   Searches: "query c", "query d"

[... repeat for all sub-questions ...]

### Validation Notes
- [List any issues found, or "Plan looks solid — no issues detected"]
- [Suggestions for improvement, if any]

---
**Please review the plan above.**
- Reply **"approve"** to proceed with research.
- Reply with **modifications** (e.g., "add a section about X" or "remove question 3") and I'll adjust.
- Reply **"reject"** to cancel this research.
```

## Rules

1. **Never proceed without the approval prompt.** The three-option prompt (approve/modify/reject) must always appear at the end.
2. **Be concise in validation notes.** Flag real issues, not nitpicks.
3. **Preserve the planner's intent.** Only suggest changes that genuinely improve coverage or feasibility.
4. **If the plan is solid, say so.** Do not invent issues to look thorough.
