# C++ Codemap Generator

三个独立脚本，基于 libclang 为大型 C++ 工程生成供 Claude Code 使用的代码地图。

## 文件清单

| 文件                        | 作用                                                 |
| --------------------------- | ---------------------------------------------------- |
| `common.py`                 | 共享工具：配置加载、libclang 初始化、文件遍历       |
| `extract_skeleton.py`       | **Step 1** - 按模块输出 Markdown 骨架文档            |
| `build_dep_graph.py`        | **Step 2** - 输出 Mermaid 依赖图 + 分层违规报告      |
| `extract_symbols.py`        | **Step 3** - 输出结构化 JSON 符号清单                |
| `codemap.json.example`      | 配置样例                                             |
| `requirements.txt`          | `libclang>=16.0`                                     |

三个脚本互相独立，`common.py` 只是共享工具。可单独跑任何一个。

## 安装

```bash
pip install libclang
# 或 pip install -r requirements.txt
```

`libclang` 这个 wheel 自带 clang 动态库，不需要系统装 clang。若 wheel 找不到动态库，可在 `codemap.json` 里设 `"libclang_path": "/path/to/libclang.so"`。

## 快速上手

```bash
cp codemap.json.example codemap.json
# 编辑 codemap.json：至少把 src_root 改成你的路径

python extract_skeleton.py --config codemap.json
python build_dep_graph.py  --config codemap.json
python extract_symbols.py  --config codemap.json
```

输出目录结构：

```
codemap/
├── skeleton/          # Step 1 输出
│   ├── core.md
│   ├── render.md
│   └── platform.md
├── deps.mermaid.md    # Step 2 输出
├── deps.json
├── violations.md      # 违反 layering_rules 时才生成
└── symbols/           # Step 3 输出
    ├── _summary.json
    ├── core.json
    └── render.json
```

## 配置详解

```jsonc
{
  "src_root": "src",                  // 源码根目录
  "output_dir": "codemap",            // 输出目录
  "module_depth": 1,                  // 模块 = src_root 下第 N 层目录
                                      // 1 → "render"；2 → "render/rhi"

  "exclude_dirs": ["third_party", "build", ...],

  // 优先使用 compile_commands.json（CMake: -DCMAKE_EXPORT_COMPILE_COMMANDS=ON）
  "compile_commands": "build/compile_commands.json",

  // 找不到 compile_commands 时的兜底参数
  "default_compile_args": ["-std=c++20", "-xc++"],

  "include_paths": ["src", "src/core"],
  "system_include_paths": [],

  // 关键：把干扰 libclang 的工程宏定义成空，解析成功率会大幅提升
  "defines": [
    "MY_ENGINE_API=",
    "DECLARE_CLASS(x)=",
    "GENERATED_BODY()="
  ],

  // 分层约束：列出的模块**只能**依赖其白名单；未列出的模块不受约束
  "layering_rules": {
    "core":     [],
    "platform": ["core"],
    "render":   ["core", "platform", "math"]
  }
}
```

## 常见问题

**解析失败 / 类没抽到？**

1. 检查 libclang 的 diagnostics：加 `-v` 参数
2. 多半是宏/模板问题，把相关宏加到 `defines` 里 "定义为空"
3. 项目有 DLL export 宏（如 `MY_ENGINE_API`）必须处理掉
4. 生成 `compile_commands.json` 一劳永逸：CMake 项目 `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`

**"`stddef.h` file not found" 警告？**

libclang 找不到系统头。不影响类/函数级的提取（`PARSE_INCOMPLETE` 标志允许继续），
但 `size_t` 之类类型可能降级为 `int`。用 compile_commands.json 或把 clang 的
resource dir 加到 `system_include_paths` 可消除。

**模块粒度怎么选？**

- `module_depth=1`：每个顶层目录一个模块（适合子系统较清晰的项目）
- `module_depth=2`：到二级目录（适合 `render/rhi`、`render/pipeline` 要分开）

**想只重跑一个模块？**

```bash
python extract_skeleton.py --config codemap.json --module render
```

## 建议的集成方式

### 1. 一次性全量生成

```bash
python extract_skeleton.py --config codemap.json
python build_dep_graph.py  --config codemap.json
python extract_symbols.py  --config codemap.json
```

把 `codemap/skeleton/*.md` 人工 review 后，作为各子系统的 `CLAUDE.md` 初稿。

### 2. Git pre-push hook / CI 增量

```bash
# 只重新生成 diff 涉及的模块
changed_modules=$(git diff --name-only origin/main...HEAD -- 'src/*' \
    | awk -F/ '{print $2}' | sort -u)
for m in $changed_modules; do
    python extract_skeleton.py --config codemap.json --module "$m"
done
```

### 3. 喂给下一步（Claude 填充）

Step 4（即上文讨论的 "Claude 填充"）不在本仓库里。用法示意：

```python
# pseudo
for module in os.listdir("codemap/symbols"):
    symbols = json.load(open(f"codemap/symbols/{module}"))
    deps = json.load(open("codemap/deps.json"))
    skeleton = open(f"codemap/skeleton/{module}.md").read()
    # 把三份内容 + 代表性头文件原文喂给 Claude，生成最终 CLAUDE.md
```

## 实现注意

- 所有脚本使用 `TranslationUnit.PARSE_SKIP_FUNCTION_BODIES | PARSE_INCOMPLETE`：
  只解析声明，容忍缺失头文件，大型工程速度显著提升。
- Step 1/3 只收录 **在当前文件内定义的** 顶层符号，避免同一个类被多个 header
  重复输出。
- Step 2 用正则抓 `#include "..."`（不抓 `<>`），然后用后缀索引解析路径。
  不依赖 libclang，在几百万行的代码里也只需秒级。
- `namespace` 会递归展开，所以 `namespace render::rhi { class IRHIDevice; }`
  能被正确归到 `render::rhi::IRHIDevice`。
