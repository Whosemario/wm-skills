---
name: implement-task
description: Implement exactly one approved task and run the required task-level validation before review.
metadata:
  version: "1.0.0"
---

# Invocation — MANDATORY

**This skill MUST be invoked via the `/opsx:apply` slash command inside a new subagent.**

When `orchestrate-change` routes work to this skill, it must launch a Task subagent whose prompt is:

```
/opsx:apply <task details>
```

The subagent is responsible for loading this skill via the `skill()` tool and following its full workflow — including any scripts or reference files in the skill directory.

**Forbidden:** Do NOT extract this skill's content in the orchestrator and pass it as raw text instructions to the subagent. That bypasses the skill loading mechanism, drops skill-bundled resources, and breaks the workflow contract.

# Logging

Append log entries to `.openspec-orch/<change_id>/implement-task.log` at these key points:

**On task start:**
```
[TIMESTAMP] [implement-task] START task=<id> description=<short description>
```

**On each file edit applied:**
```
[TIMESTAMP] [implement-task] EDIT file=<relative path> summary=<one line description of change>
```

**On validation result:**
```
[TIMESTAMP] [implement-task] VALIDATION result=<PASS|FAIL> detail=<brief summary>
```

**On handoff:**
```
[TIMESTAMP] [implement-task] HANDOFF task=<id> ready=<true|false> spec_gaps=<none or brief description>
```

Use ISO-8601 timestamp. Always append — never overwrite the log file.

---

# Purpose

This skill implements one approved task at a time.

It corresponds to Agent-3 in the workflow.

# Responsibilities

For exactly one current task:
- read task requirements
- read related spec sections
- read related design sections
- implement the task
- add or update required tests
- run task-level validation
- prepare handoff for code review

# Hard Rules

- implement only the current approved task
- do not silently change scope
- do not silently reinterpret specs
- do not silently override design decisions
- minimize unrelated refactors
- report spec/design gaps explicitly if found
- do not start another task before approval of the current one

# Validation Requirements

Before review handoff, run all required checks for the task:
- build
- lint or static checks if applicable
- unit tests
- integration tests
- task-level end-to-end or equivalent validation

If any required check fails:
- remain in implementation mode
- fix the issue
- rerun validation

# Review-Ready Definition

A task is review-ready only when:
- implementation is complete
- build succeeds
- required tests pass
- task-level end-to-end validation passes
- no known blocking defect remains

# Outputs

Always output:
- task_id
- implementation_summary
- files_changed
- tests_run
- results
- spec_or_design_gaps
- risks
- handoff_ready