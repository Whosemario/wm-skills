---
name: capture-web-article
description: Archive a single web article, blog post, or social post into a local Markdown package with downloaded inline images. Use when Codex must require a user-provided URL and destination directory, open the page in Chrome DevTools, wait for the user to complete authentication if needed, extract the rendered body content plus content images, and save everything into a timestamp-title subfolder on disk.
---

# Capture Web Article

Use this skill only when the user explicitly invokes `$capture-web-article`. Do not invoke it implicitly from a plain-language request.

Require two user inputs before doing anything substantial:

- `url`: the page to archive
- `output_dir`: an existing local directory where the archive subfolder will be created

If either field is missing, stop and ask only for the missing field. Do not infer either value. Do not write directly into `output_dir`; always create a new child directory named `<YYYYMMDD-HHMMSS>-<title>`.

## Workflow

1. Validate inputs.
   - Confirm `url` looks like an absolute `http` or `https` URL.
   - Confirm `output_dir` exists and is a directory.
   - Refuse to continue if either check fails.
2. Open the page with Chrome DevTools MCP.
   - Use `new_page` or `navigate_page` for the target `url`.
   - Let the page finish rendering before extracting content.
   - Prefer the browser-rendered DOM over raw HTTP fetches; this preserves client-side rendering and logged-in state.
3. Handle authentication explicitly.
   - If the page is gated by login, consent, age-check, or similar interstitials, pause and ask the user to finish authentication in the browser.
   - Resume only after the user confirms the content is visible.
   - After auth, re-check that the article/post body is actually present instead of archiving the login wall.
4. Extract the article body and content images from the rendered page.
   - Prefer an `article`, `main`, or `[role="main"]` root.
   - If those are noisy, select the densest visible content container instead.
   - Exclude navigation, sidebars, comments, share bars, ads, and hidden nodes.
   - Convert the body to readable Markdown, preserving heading levels, paragraphs, lists, blockquotes, fenced code blocks, and inline links where practical.
   - Preserve document order. When an inline image appears between two text blocks in the DOM, place its placeholder at that exact point in `body_markdown` instead of collecting all images at the end.
   - Capture only images that are part of the body content. Ignore avatars, logos, emoji sprites, badges, and decorative assets.
   - Download image bytes from within the page context with `fetch(..., { credentials: "include" })` so authenticated images still work.
   - Prefer returning compressed `data:` URLs for body images; do not rely on bare remote URLs for the final archive.
5. Write the archive locally.
   - Save the extraction payload to a temporary JSON file.
   - Run `scripts/write_archive.py` to create the timestamp-title subfolder, write `<folder-name>.md`, decode images into `images/`, and patch image placeholders to local Markdown links.
6. Verify the result.
   - Open the generated Markdown file and make sure the body is readable.
   - Confirm image links resolve to local files.
   - If the extraction is noisy, rerun with a tighter root selector or manually remove noisy blocks before writing the final archive.

## Extraction Guidance

Use `evaluate_script` to return a compact JSON payload with this shape:

```json
{
  "title": "Page title",
  "source_url": "https://example.com/post",
  "captured_at": "2026-04-07T15:04:05+08:00",
  "author": "Author name",
  "published_at": "2026-04-01T09:00:00Z",
  "body_markdown": "# Optional heading\n\nParagraph.\n\n__IMG_1__",
  "images": [
    {
      "placeholder": "__IMG_1__",
      "alt": "Figure caption",
      "source_url": "https://example.com/image.jpg",
      "filename": "hero.jpg",
      "data_url": "data:image/jpeg;base64,..."
    }
  ]
}
```

The payload must contain Markdown in `body_markdown` and image placeholders that match the `images[].placeholder` entries. If there are no images, return an empty `images` array.

Do not append a synthetic `## Images` section unless the source page itself has such a section. Prefer inline placement:

```markdown
Paragraph before image.

__IMG_1__

Paragraph after image.
```

## Browser Snippet

Adapt this `evaluate_script` function to the target page. Keep the root selection conservative, only return body images, and insert image placeholders in reading order.

```javascript
async () => {
  const absolute = (value) => {
    try {
      return new URL(value, location.href).href;
    } catch {
      return null;
    }
  };

  const meta = (...names) => {
    for (const name of names) {
      const el = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
      const value = el?.content?.trim();
      if (value) return value;
    }
    return "";
  };

  const isVisible = (el) => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== "none" &&
      style.visibility !== "hidden" &&
      rect.width > 0 &&
      rect.height > 0;
  };

  const scoreRoot = (el) => {
    const text = (el.innerText || "").replace(/\s+/g, " ").trim();
    const pCount = el.querySelectorAll("p").length;
    const mediaCount = el.querySelectorAll("img, figure").length;
    const chromeCount = el.querySelectorAll("nav, aside, footer, form, button").length;
    return text.length + pCount * 200 + mediaCount * 80 - chromeCount * 1200;
  };

  const candidates = [
    ...document.querySelectorAll("article, main, [role='main'], section, div")
  ].filter(isVisible);
  const root = candidates.sort((a, b) => scoreRoot(b) - scoreRoot(a))[0] || document.body;

  for (const noisy of root.querySelectorAll("nav, aside, footer, form, button, script, style, noscript, iframe")) {
    noisy.remove();
  }

  const blobToDataUrl = (blob) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });

  const fetchImage = async (src) => {
    const url = absolute(src);
    if (!url) return null;
    const response = await fetch(url, { credentials: "include" });
    const blob = await response.blob();
    return {
      source_url: url,
      data_url: await blobToDataUrl(blob)
    };
  };

  const blocks = [];
  const images = [];
  let imageIndex = 0;

  const pushText = (value) => {
    const text = (value || "").replace(/\n{3,}/g, "\n\n").trim();
    if (text) blocks.push(text);
  };

  const toInlineMarkdown = (node) => {
    const clone = node.cloneNode(true);
    for (const a of clone.querySelectorAll("a[href]")) {
      const label = (a.textContent || "").replace(/\s+/g, " ").trim();
      const href = absolute(a.getAttribute("href"));
      a.replaceWith(label && href ? `[${label}](${href})` : label);
    }
    return (clone.textContent || "").replace(/\s+/g, " ").trim();
  };

  const handleImageNode = async (img) => {
    const src = img.currentSrc || img.getAttribute("src");
    if (!src) return;
    if ((img.naturalWidth || 0) < 80 && (img.naturalHeight || 0) < 80) return;
    imageIndex += 1;
    const placeholder = `__IMG_${imageIndex}__`;
    const fetched = await fetchImage(src);
    if (!fetched) return;
    images.push({
      placeholder,
      alt: (img.getAttribute("alt") || "").trim(),
      filename: `image-${String(imageIndex).padStart(2, "0")}`,
      ...fetched
    });
    blocks.push(placeholder);
  };

  const nodes = [...root.children];
  for (const node of nodes) {
    if (!isVisible(node)) continue;

    if (node.matches("p, div") && node.querySelector("img") && !node.querySelector("p, ul, ol, blockquote, pre")) {
      const fragment = [];
      for (const child of [...node.childNodes]) {
        if (child.nodeType === Node.TEXT_NODE) {
          const text = child.textContent.replace(/\s+/g, " ").trim();
          if (text) fragment.push(text);
          continue;
        }
        if (!(child instanceof Element) || !isVisible(child)) continue;
        if (child.matches("img")) {
          const before = fragment.join(" ").trim();
          if (before) blocks.push(before);
          fragment.length = 0;
          await handleImageNode(child);
          continue;
        }
        const text = toInlineMarkdown(child);
        if (text) fragment.push(text);
      }
      const after = fragment.join(" ").trim();
      if (after) blocks.push(after);
      continue;
    }

    if (node.matches("figure")) {
      const img = node.querySelector("img");
      if (img) {
        await handleImageNode(img);
        const caption = node.querySelector("figcaption")?.innerText?.trim();
        if (caption) blocks.push(`_${caption}_`);
      }
      continue;
    }

    if (node.matches("img")) {
      if (node.closest("figure")) continue;
      await handleImageNode(node);
      continue;
    }

    if (node.matches("ul,ol")) {
      const items = [...node.querySelectorAll(":scope > li")]
        .map((li, index) => {
          const text = toInlineMarkdown(li);
          if (!text) return "";
          return node.matches("ol") ? `${index + 1}. ${text}` : `- ${text}`;
        })
        .filter(Boolean)
        .join("\n");
      pushText(items);
      continue;
    }

    const text = toInlineMarkdown(node);
    if (!text) continue;

    if (/^H[1-6]$/.test(node.tagName)) {
      const level = Number(node.tagName.slice(1));
      pushText(`${"#".repeat(level)} ${text}`);
    } else if (node.matches("blockquote")) {
      pushText(text.split("\n").map((line) => `> ${line}`).join("\n"));
    } else if (node.matches("pre, code")) {
      pushText(`\`\`\`\n${node.innerText.trim()}\n\`\`\``);
    } else {
      pushText(text);
    }
  }

  return {
    title: document.querySelector("h1")?.innerText?.trim() || document.title || "Untitled",
    source_url: location.href,
    captured_at: new Date().toISOString(),
    author: meta("author", "og:article:author", "article:author"),
    published_at: meta("article:published_time", "og:published_time", "datePublished"),
    body_markdown: blocks.join("\n\n"),
    images
  };
}
```

## Writing The Archive

Write the JSON payload to a temporary file and then run:

```bash
python3 /Users/whosemario/.codex/skills/capture-web-article/scripts/write_archive.py \
  --output-dir "/absolute/output/dir" \
  --json /tmp/capture-web-article.json
```

The script creates:

- `<output_dir>/<timestamp>-<title>/<timestamp>-<title>.md`
- `<output_dir>/<timestamp>-<title>/images/...`

The script expects `body_markdown` or `markdown` plus optional `images`. It replaces placeholders with local image links and prints the created archive directory to stdout.

## Output Expectations

The final archive must satisfy all of these:

- Markdown is readable without network access.
- All kept body images are local files referenced by relative paths.
- Images are placed as close as possible to the paragraphs they belong to instead of being dumped into a trailing gallery.
- The subfolder name includes the local timestamp and page title.
- The Markdown filename matches the archive folder name.
- The Markdown file includes the source URL and capture time near the top.
- No unrelated chrome, comments, or sidebars remain in the body.
