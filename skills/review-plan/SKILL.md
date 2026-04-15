---
name: review-plan
description: Review OpenSpec planning artifacts for completeness, architecture quality, and task-level testability.
metadata:
  version: "1.0.0"
---

# Logging

Append log entries to `.openspec-orch/<change_id>/review-plan.log` at these key points:

**On review start:**
```
[TIMESTAMP] [review-plan] START round=<N>
```

**On verdict:**
```
[TIMESTAMP] [review-plan] VERDICT round=<N> verdict=<approve|request_changes> blocking_issues=<count>
```

If `request_changes`, also append one line per blocking issue:
```
[TIMESTAMP] [review-plan] BLOCKING id=<issue_id> summary=<one line>
```

Use ISO-8601 timestamp. Always append — never overwrite the log file.

# Purpose

This skill reviews the planning package.

It corresponds to Agent-2 in the workflow.

# Responsibilities

Review:
- `proposal.md`
- `design.md`
- `tasks.md`
- `specs/*`

# Primary Objective

Determine whether the planning package is ready for implementation.

# Review Dimensions

Evaluate:
- cross-artifact consistency
- scope clarity
- spec testability
- design adequacy
- task decomposition quality
- validation completeness
- task-level end-to-end closure

# Mandatory Rejection Conditions

Return `request_changes` if:
- scope is unclear
- specs are ambiguous or not testable
- design does not support specs
- failure handling is missing for risky behavior
- tasks are not independently verifiable
- tasks do not include a realistic validation path
- tasks only become testable after future tasks
- acceptance criteria are vague

# Task-Level Validation Check
**Note: These rules are very important.**
For each task, explicitly check:
- can the codebase still build after this task?
- can the system run meaningfully for the scoped behavior?
- can this task be validated independently?
- is there an end-to-end or equivalent validation path?

If any answer is no, **MUST** reject the plan.

# Review Policy

- block only on correctness, scope, architecture, reliability, security, or testability
- do not block on stylistic preference alone
- keep issue IDs stable across rounds
- prefer precise blocking issues over vague criticism

# Output Schema

Always output:
- verdict
- summary
- blocking_issues
- non_blocking_suggestions

Allowed verdicts:
- approve
- request_changes