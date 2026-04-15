---
name: orchestrate-change
description: Orchestrate the full OpenSpec multi-agent workflow across planning, implementation, review, and verification.
metadata:
  version: "1.0.0"
---

# Purpose

This skill is the single entry point for the OpenSpec multi-agent workflow.

It does not do all content creation itself.
Its responsibility is to:
- inspect workflow state
- decide the next stage
- invoke the appropriate specialist skill
- enforce gating rules
- update workflow state
- reopen planning when implementation drifts from approved artifacts

# Logging

Append log entries to `.openspec-orch/<change_id>/orchestrate-change.log` at these key points:

**On startup (after change_id is resolved):**
```
[TIMESTAMP] [orchestrate-change] change_id=<id> phase=<phase> planning_status=<status> implementation_status=<status>
```

**On each routing decision:**
```
[TIMESTAMP] [orchestrate-change] routing to=<skill> reason=<gating_reason> target_task=<id or n/a>
```

**On state update (after a task or round completes):**
```
[TIMESTAMP] [orchestrate-change] state_update task=<id or planning_round=N> result=<approve|request_changes> next=<next_action>
```

Use ISO-8601 timestamp (e.g. `2026-04-14T15:30:00`). Always append — never overwrite the log file.

# Change ID Resolution

Each change has its own state file at:

```
<PROJECT_DIR>/.openspec-orch/<change_id>/change_state.yaml
```

On startup, resolve `change_id` using this priority order:

1. **User provided it** — use it directly.
2. **Not provided** — scan `<PROJECT_DIR>/.openspec-orch/` for subdirectories that contain a `change_state.yaml` whose `implementation_status` is NOT `archived`.
   - If exactly one active change is found, use it.
   - If multiple active changes are found, list them and ask the user which one to continue.
   - If none are found, stop and ask the user to provide a `change_id` or create a new change first.

Do not fall back to a shared `change_state.yaml` at the root of `.openspec-orch/`.

# Responsibilities

1. Resolve `change_id` and locate `<PROJECT_DIR>/.openspec-orch/<change_id>/change_state.yaml`
2. Determine the current phase
3. Route work to exactly one specialist skill
4. Enforce workflow gates
5. Keep issue IDs and state transitions stable
6. Prevent uncontrolled loops
7. Escalate to stalled state when the same blocking issue persists repeatedly

# Workflow Stages

- Planning
  - invoke `author-plan` **with new subagent**
  - then invoke `review-plan` **with new subagent**
  - repeat until approved

- Implementation
  - choose exactly one ready task
  - invoke `implement-task` **with new subagent**
  - if validation passes, invoke `review-code` **with new subagent**
  - repeat until approved
  - **after review approves a task**, update `tasks.md` to check off that task's checkbox (`- [ ]` → `- [x]`)
  - move to next task

- Final verification
  - confirm all tasks are done
  - confirm no unresolved blocking issues remain
  - confirm implementation still aligns with approved plan

# Task Completion Sync

After `review-code` approves a task, the orchestrator **MUST** immediately perform these two updates before moving to the next task:

1. **`change_state.yaml`** — set the task's `status` to `done` and append the implementation round.
2. **`tasks.md`** — find the line starting with `- [ ] <task_id>` and replace `- [ ]` with `- [x]` to check off the completed task.

Both updates must happen in the same orchestrator turn. Do not defer checkbox updates to a later phase or rely on subagents to do it — subagents do not have this responsibility.

This ensures `tasks.md` always reflects the true completion state visible to the user.

# Hard Rules

- Do not allow implementation before planning is approved
- Do not allow the next task to begin before the current task is approved
- Do not silently reinterpret spec or design
- Reopen planning when implementation reveals artifact contradictions
- Do not act as the reviewer or implementer unless no other skill is available

# Inputs

Expected inputs may include:
- raw user requirement
- current change id
- current workflow phase
- current planning artifacts
- current task
- prior blocking issues
- latest validation results

# Outputs

Always output:
- current_state
- next_action
- selected_skill
- target_task if applicable
- gating_reason
- success_condition
- failure_route

# Skill Invocation Policy

Use:
- `author-plan` during planning authoring or planning revision
- `review-plan` after planning artifacts are updated
- `implement-task` for exactly one approved task
- `review-code` after task-level validation passes

# Failure Handling

If the same issue persists for 3 rounds:
- mark the workflow as stalled
- summarize the unresolved issue
- stop advancing phases until resolved