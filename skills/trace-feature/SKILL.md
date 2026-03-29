---
name: trace-feature
description: Trace a feature from entry points to concrete side effects in a large codebase. Use when users ask how a feature runs end-to-end, provide a function/class and want upstream-downstream flow, or need impact analysis before modifying a feature.
---

# Trace Feature

Trace one feature from entry to observable result, keep only the critical call chain, and surface risks.

## Goal

Trace a feature from entry to result with a clear, minimal, and verifiable execution path.

## Workflow

1. Determine feature entry points.
- Identify function, command, event, message, callback, or script entry.
- List all plausible entries when there is no single obvious entry.

2. Follow the call chain to real side effects.
- Continue tracing until at least one concrete side effect appears:
  - Render submission
  - Network send
  - File read/write
  - Resource load
  - State update

3. Skip low-value hops.
- Skip pure forwarding wrappers, thin adapters, and repeated boilerplate.
- Keep only steps that change control flow, data, ownership, scheduling, or behavior.

4. Record each retained step.
- State what the function/type does.
- State what key state is read/written.
- State whether it crosses thread/async boundaries.
- State whether it depends on cache/config/script.

5. Mark invariants and failure-prone points.
- Mark assumptions that must hold before/after a step.
- Mark potential fault points: null/invalid state, ordering, stale cache, missing config, reentrancy, lifetime.

6. Produce a minimum understanding path.
- Provide 3-5 symbols that let a newcomer grasp the main path quickly.
- Prefer symbols that define flow boundaries and key mutations.

## Analysis Rules

- Prefer code facts over generic assumptions.
- Mark uncertainty explicitly when code does not confirm a claim.
- Distinguish confirmed behavior from inference.
- Keep terminology consistent with nearby code.

## Output Format

### 结论
一句话总结这个功能的执行路径。

### 入口
- 入口点 1
- 入口点 2

### 关键调用链
1. A -> 做了什么
2. B -> 做了什么
3. C -> 做了什么

### 核心数据结构
- 类型 / 对象
- 作用
- 谁创建
- 谁持有
- 谁修改

### 线程/异步点
- 主线程
- worker
- render thread
- callback / queue / future / task

### 关键副作用
- 改了什么状态
- 提交了什么资源
- 触发了什么后续流程

### 风险点
- 竞态
- 生命周期
- 重入
- 失效顺序
- 隐式前置条件

### 最小理解路径
列出最值得看的 3~5 个符号。
