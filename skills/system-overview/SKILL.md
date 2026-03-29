---
name: system-overview
description: 快速理解复杂仓库或子系统并建立全局心智模型。Use when users ask how a system is organized, when someone just took over a module, when they need a prioritized reading path, or when they want architecture orientation before code changes.
---

# System Overview

## Goal

快速理解一个复杂仓库或子系统，建立全局心智模型。

## When to Use

- 用户问“这个系统怎么组织的”
- 用户刚接手一个模块
- 用户想知道先看哪些代码
- 用户准备改代码前，需要先摸清架构

## Instructions

1. 先识别仓库或子系统的边界。
2. 找入口：启动点、初始化点、注册点、主循环。
3. 识别模块分层：接口层、调度层、核心逻辑层、数据层、平台层。
4. 找关键全局对象、manager、service、cache、context。
5. 找线程模型和关键异步链。
6. 找配置、脚本、资源数据对运行逻辑的影响。
7. 跳过样板和薄封装，只保留关键结构。
8. 明确列出不确定项，不要猜。

## Output Format

### 结论
一句话说明该系统本质上负责什么。

### 模块分层
- 模块 A：
- 模块 B：
- 模块 C：

### 主要入口
- 入口函数 / 注册点 / 初始化点

### 运行主流程
按顺序列出关键步骤。

### 核心对象
- 名称
- 职责
- 生命周期
- 线程归属

### 关键依赖
- 外部系统
- 配置/资源/脚本依赖
- 平台差异

### 风险点
- 竞态
- 状态同步
- 隐式依赖
- 生命周期错配
- 缓存失效

### 新人阅读顺序
给出最值得先看的文件/类/函数。
