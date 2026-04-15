---
name: review-code
description: Review the implementation of one approved task for correctness, spec alignment, design alignment, and test adequacy.
metadata:
  version: "1.0.0"
---

# Logging

Append log entries to `.openspec-orch/<change_id>/review-code.log` at these key points:

**On review start:**
```
[TIMESTAMP] [review-code] START task=<id>
```

**On verdict:**
```
[TIMESTAMP] [review-code] VERDICT task=<id> verdict=<approve|request_changes> blocking_issues=<count> spec_drift=<none|brief description>
```

If `request_changes`, also append one line per blocking issue:
```
[TIMESTAMP] [review-code] BLOCKING id=<issue_id> summary=<one line>
```

Use ISO-8601 timestamp. Always append — never overwrite the log file.

# Purpose

This skill reviews the implementation of one approved task.

It corresponds to Agent-4 in the workflow.

# Responsibilities

Review:
- current approved task
- implementation diff
- relevant spec excerpts
- relevant design excerpts
- test results
- prior task review history

# Primary Objective

Determine whether the current task implementation is safe and correct to accept.

# Review Scope

Evaluate:
- task correctness
- conformance to specs
- alignment with design
- code quality
- reliability and edge cases
- regression risk
- adequacy of tests
- realism of task-level end-to-end validation
- scope control

# Mandatory Rejection Conditions

Return `request_changes` if:
- implementation does not satisfy the task
- behavior diverges from approved specs
- important design constraints are violated without justification
- important failure paths are unhandled
- tests are missing or superficial
- task-level end-to-end validation does not truly verify the task
- the code introduces significant maintainability or correctness risk
- the change includes unjustified scope creep

# Review Policy

- do not reject on minor style preference alone
- use stable issue IDs
- separate blockers from non-blocking quality notes
- explicitly flag spec drift when present

# Output Schema

Always output:
- verdict
- summary
- blocking_issues
- quality_notes
- spec_drift

Allowed verdicts:
- approve
- request_changes