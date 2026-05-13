---
name: summary-to-html
description: Generate a self-contained dark-themed HTML "study notes" deck from any source material — a Markdown file, an uploaded note, a pasted write-up, or a topic the user wants summarized. Trigger when the user asks for "学习笔记", "复习笔记", "study notes", "回顾", "总结成 HTML / 幻灯片", or otherwise wants a navigable page-by-page deck with a refined editorial dark look (Fraunces italic titles, JetBrains Mono code, accent oranges/teals). Use the bundled template.html — do NOT generate reveal.js, do NOT use markdown-to-slides for this aesthetic. Skip for `.pptx`, light/print decks, or live-presentation slides where reveal.js fits better.
---

# Summary → HTML (study-notes deck)

Produce one self-contained `.html` file styled like a hand-crafted editorial notebook: dark background, Fraunces italic display headings, JetBrains Mono code, orange/teal accents, arrow-key navigation. Slides are absolutely-positioned `<div class="slide">` elements switched by a tiny vanilla-JS controller — no framework, no build step.

The whole skill is one template file plus the workflow below. **You write the slides directly into the template file** using Edit; there is no converter script.

## When to use this skill

**Use it for:**

- "把 X 总结成 HTML 学习笔记"
- "用 BVH 笔记的风格 / 这种深色暗调风格做一份 …"
- A user gives you a `.md` / 长文 / 主题 and wants slide-style review material to flip through
- Technical study notes (algorithms, papers, system internals) where code, formulas, ASCII diagrams, and prose all need to coexist

**Do NOT use it for:**

- `.pptx` output — different skill
- Live presentation decks where reveal.js features (speaker notes, fragments, timer) matter — use `markdown-to-slides`
- Light-themed / print-optimized output — this template is fixed-viewport dark, deliberately not print-friendly

## Workflow

1. **Resolve the input.** A path the user gave, an upload at `/mnt/user-data/uploads/`, pasted text in the chat, or just a topic. Read it fully before designing the deck — you are summarizing, not transliterating.

2. **Plan the slide list.** Decide the chapter sections (typically 2–5 大块, e.g. "基础 / 构建 / 查询 / 动态更新 / 收尾") and the slides under each. Aim for 10–25 slides total. Each slide should have one job: one definition, one comparison, one derivation, one code listing.

3. **Decide the output path.** Default: same directory as the input, same basename, `.html` suffix. In sandboxed sessions where the user needs to download, write to `/mnt/user-data/outputs/<name>.html` and call `present_files` afterwards.

4. **Copy the template.** Read `template.html` from this skill directory, then `Write` it to the output path. Do not modify the skill's copy.

5. **Customize the deck** by editing the output file. In rough order:
   - `<title>` in `<head>`
   - Cover slide (slide 1): `{{TITLE_SHORT}}`, `{{SUBTITLE}}`, `{{COVER_TOPBAR_LEFT/RIGHT}}`, the three meta rows, optionally redraw the SVG decoration
   - For each subsequent slide: pick the matching template type (cover / big-idea / code / formula / ascii-tree+table / two-col / takeaways), duplicate it as many times as needed, fill in content, **delete the example slides you didn't reuse**
   - Update the topbar `chapter` text and the right-side slide number for each slide
   - Update each slide's `<h2 class="slide-title"><span class="num">NN</span>...</h2>` so the numbers form a clean 01, 02, 03… sequence
   - The bottom-right counter (`01 / 07`) and the progress bar update themselves from `slides.length` — don't touch the JS

6. **Verify.** Open the file mentally: is slide 1 the cover? Are topbar numbers monotonic? Are all `{{PLACEHOLDER}}` tokens replaced? Tell the user the path and the navigation keys (`← →` 翻页, `space` 下一页, `home/end` 首尾, click left/right edge to navigate).

## Template slide types

The template ships seven example slides, each marked `<!-- TYPE: ... -->`. Pick from these as Lego bricks:

| TYPE | Use when | Key elements |
|---|---|---|
| `cover` | Slide 1 always | `h1.title-display`, `.cover-meta`, decorative SVG |
| `big-idea + callout-row` | Intro / "what is this" overview | `.big-idea` (italic pull-quote), 3-column `.callout-row` |
| `code` | Type/struct/function definitions, algorithm listings | `<pre><code>` with manual `<span>` coloring |
| `formula` | Math derivations, identities | `.formula-big` (centered hero), `.eqn` (block step) |
| `ascii-tree + table` | Diagrams, before/after, comparison | `.ascii-tree` (preserves whitespace), `<table>` |
| `two-col` | Side-by-side concepts, def vs example | `.two-col` 50/50 grid |
| `takeaways` | Final summary | `.big-idea` headline, multiple `<h3>` sections, "下一步" pointers |

You're not limited to these — any combination of the building blocks (`.big-idea`, `.callout`, `.note`, `.eqn`, `.formula-big`, `.ascii-tree`, `pre`, `table`, `.two-col`) can be mixed inside one slide. Use the seven types as starting scaffolds.

## Code coloring cheat sheet

There is **no syntax highlighter loaded**. Color tokens by hand inside `<pre><code>`:

| Class | Color (var) | What to wrap |
|---|---|---|
| `kw` | `--keyword` (red-pink) | `if while for return struct class const auto void int float bool true false this nullptr ...` |
| `ty` | `--accent-cool` (teal) | Type names: `Vec3 AABB std::string uint32_t glm::vec3 ...` |
| `fn` | `--accent` (orange) | Function names at definition site or call site you want emphasized |
| `num` | warm gold | Numeric literals: `0 0.5f 16 -1.0` |
| `str` | `--string` (green) | String literals in `"..."` |
| `cm` | `--comment` (grey, italic) | Comments — wrap the whole `// ...` or `/* ... */` |

Tokens you don't wrap stay in the default text color, which is fine for identifiers, operators, punctuation. **Don't try to color every single token** — selective highlighting reads better than highlight.js's everything-colored output.

Also: inside `<pre><code>`, escape `<` `>` `&` to `&lt;` `&gt;` `&amp;` — they're real HTML.

```html
<pre><code><span class="kw">struct</span> <span class="ty">AABB</span> {
    <span class="ty">glm::vec3</span> pmin, pmax;
    <span class="kw">void</span> <span class="fn">expand</span>(<span class="kw">const</span> <span class="ty">AABB</span>&amp; b) {
        pmin = glm::min(pmin, b.pmin);  <span class="cm">// per-component min</span>
    }
};</code></pre>
```

## Formula conventions

KaTeX is **not** loaded. Use plain text with Unicode math symbols and the `.formula-big` / `.eqn` classes for visual styling:

- Operators: `· × ÷ ± ∓ ≤ ≥ ≠ ≈ ≡ ⇒ ⇔ → ←`
- Greek: `α β γ δ ε θ λ μ π σ φ ω Ω Σ`
- Calculus / set: `∫ ∮ ∂ ∇ ∑ ∏ √ ∞ ∈ ∉ ⊂ ⊆ ∪ ∩ ∅`
- Sub/super via `<sub>x</sub>` `<sup>2</sup>` if needed

Inside `.formula-big` and `.eqn`, wrap variables in `<span class="var">…</span>`, operators in `<span class="op">…</span>`, numbers in `<span class="num">…</span>` — the CSS gives them the right colors.

## Common variations

- **离线使用** — Google Fonts (Fraunces / Noto / JetBrains Mono) needs internet on first load. To make it offline: delete the `<link rel="preconnect">` / `<link href="...fonts.googleapis...">` lines; system fonts will substitute (PingFang SC / Microsoft YaHei for Chinese, Georgia for serif, Cascadia Mono / Consolas for code). The look degrades but stays readable.
- **配色微调** — Edit the `:root` CSS vars at the top: `--accent` (orange), `--accent-cool` (teal), `--bg`, `--slide-bg`. Don't touch class names — the JS and the rest of the CSS reference them.
- **Slide 数变化** — Add/remove `<div class="slide">` blocks freely. The JS reads `document.querySelectorAll('.slide').length`, so the counter and progress bar adapt automatically. Static `<span id="counter">01 / 07</span>` is just initial text — overwritten on first `show(0)`.
- **打印 / PDF** — This template is intentionally fixed-viewport (`100vh`) with overflow:hidden. It does **not** print well. If the user asks for PDF, recommend full-screen browser + manual page-by-page screenshot, or suggest the `markdown-to-slides` skill instead (which has reveal.js's print stylesheet).
- **更长的代码块滚动** — `<pre>` already has `overflow:auto` and a thin scrollbar. The slide content area also scrolls. Long listings are fine.

## Implementation notes

- The template is one HTML file (~600 lines), no external JS, no build. CSS is a single inline `<style>` block. The JS at the bottom is ~25 lines.
- Slide transition is opacity fade (0.35s). `position:absolute; inset:0` makes every slide overlap fully — only the `.active` one is visible.
- The `.click-zone left/right` divs cover the outer 28% of each side for click-to-navigate. They sit at `z-index:50`, below the nav buttons and progress bar.
- All `{{PLACEHOLDER}}` tokens in the template are deliberately ALL_CAPS so a final `grep "{{"` over the output catches anything you forgot to fill in.
