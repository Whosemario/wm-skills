---
name: author-plan
description: Create initial OpenSpec planning artifacts with /opsx:propose, and revise existing artifacts directly unless major replanning is required.
metadata:
  version: "1.0.0"
---

# Logging

Append log entries to `.openspec-orch/<change_id>/author-plan.log` at these key points:

**On start:**
```
[TIMESTAMP] [author-plan] START round=<N> mode=<initial_creation|direct_revision|major_replanning>
```

**On each artifact updated:**
```
[TIMESTAMP] [author-plan] ARTIFACT file=<relative path> action=<created|updated> summary=<one line>
```

**On completion:**
```
[TIMESTAMP] [author-plan] DONE round=<N> artifacts_changed=<list> unresolved_risks=<none or brief>
```

Use ISO-8601 timestamp. Always append — never overwrite the log file.

# Purpose

This skill is responsible for authoring and revising the OpenSpec planning package.

It corresponds to Agent-1 in the workflow.

Initial planning artifacts must be created through `/opsx:propose`.
Revision rounds must normally update the existing planning artifacts directly rather than re-running `/opsx:propose`.

# Core Policy

## Initial creation
For a new change, you MUST invoke `/opsx:propose` to generate the initial planning artifacts.

Do not create the initial change package from scratch without `/opsx:propose`.

## Revision rounds
For a revision round, you should NOT automatically invoke `/opsx:propose`.

Instead:
- read the existing planning artifacts
- read reviewer blocking issues
- update the existing artifacts directly
- preserve continuity of the existing change package

## Major replanning exception
You MAY invoke `/opsx:propose` again during a revision round only if major replanning is required.

Major replanning includes cases such as:
- the change intent has materially changed
- the scope has materially expanded or narrowed
- the task breakdown is fundamentally flawed and must be regenerated
- the design approach must be substantially reworked
- the current artifacts are too incomplete or inconsistent to revise safely by direct editing

If none of the above is true, do not invoke `/opsx:propose` again.

# Missing Skill Handling

If this is an initial creation and `/opsx:propose` cannot be found, you MUST stop and ask the user to provide or enable it.

Do not continue by drafting the initial planning artifacts yourself.

Required response in that case:
- state that `/opsx:propose` is required for initial plan creation
- state that it is not currently available or cannot be found
- ask the user to confirm where it is installed, how it should be invoked, or to make it available before continuing

If this is only a revision round and major replanning is not required, lack of `/opsx:propose` does not block direct artifact revision.

# Responsibilities

Create or update:
- `proposal.md`
- `design.md`
- `tasks.md`
- `specs/*`

Initial versions must originate from `/opsx:propose`.
Later revisions should normally modify those existing artifacts directly.

# Required Invocation Order

## For a new change
1. Read the user requirement
2. Invoke `/opsx:propose`
3. Collect generated planning artifacts
4. Validate artifact completeness and consistency
5. Return a structured summary of created artifacts

## For a revision round
1. Read the existing planning artifacts
2. Read prior reviewer blocking issues
3. Determine whether the revision is minor or major
4. If minor, revise the existing artifacts directly
5. If major, invoke `/opsx:propose` to regenerate or substantially reshape the plan
6. Validate artifact completeness and consistency
7. Return a structured summary of changes

# Inputs

Expected inputs may include:
- raw user requirement
- existing `proposal.md`
- existing `design.md`
- existing `tasks.md`
- existing `specs/*`
- prior reviewer blocking issues
- current change id

# /opsx:propose Usage Policy

When invoking `/opsx:propose` for a new change, provide:
- the raw requirement
- repository or feature context if available
- expected change id if already assigned

When invoking `/opsx:propose` for major replanning, provide:
- the current planning artifacts
- current reviewer blocking issues
- explicit instruction describing what must be re-planned
- instruction to preserve useful existing content where possible

# Planning Quality Requirements

## Proposal
Must explain:
- intent
- scope
- non-goals
- constraints
- major risks

## Specs
Must define:
- externally observable behavior
- acceptance criteria
- important edge cases where relevant

## Design
Must define:
- implementation approach
- architecture boundaries
- dependencies
- failure handling
- fallback or rollback strategy where relevant
- trade-offs

## Tasks
Must:
- be ordered
- be meaningful
- be independently verifiable
- include validation notes
- prefer vertical slices over horizontal plumbing-only steps

# Task Design Rule

A task is valid only if, once implemented, it can be independently validated through at least one of:
- end-to-end testing
- executable integration testing
- a user-visible smoke scenario with deterministic assertions

If a task cannot be independently validated:
- revise the task breakdown
- prefer direct artifact revision for normal correction
- use `/opsx:propose` only if the breakdown must be fundamentally regenerated

# Revision Policy

When reviewer issues are provided:
- address each blocking issue precisely
- preserve already-correct content where possible
- avoid unrelated edits
- map each issue ID to a concrete artifact change
- keep issue IDs stable across rounds

For normal revisions:
- patch the existing artifacts directly

For major replanning:
- use `/opsx:propose` and clearly state why direct revision is no longer sufficient

# Output Requirements

Always output:
- summary
- planning_mode: initial_creation | direct_revision | major_replanning
- proposal_skill_invoked: true | false
- changed_artifacts
- issue_resolution_map
- unresolved_risks

# Completion Bar

This skill is complete only if:
- initial creation used `/opsx:propose`
- revision rounds preserved artifact continuity unless major replanning was necessary
- `proposal/spec/design/tasks` are present or updated
- artifacts are internally consistent
- every task has a validation path
- reviewer blocking issues are addressed when applicable