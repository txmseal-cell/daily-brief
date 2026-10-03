"""
templates.py — daily-brief v3 HTML/Markdown 模板

关键设计：
  - 原文直存，标题/摘要都是英文
  - 每条新闻有「中文翻译」「归纳」按钮，点击调用 Cloudflare Functions
  - 响应式 + 暗色模式
"""

from datetime import datetime
from html import escape as _esc

# ============================================================
# Markdown 模板
# ============================================================

MARKDOWN_TEMPLATE = """# 每日世界简报 — {date}

> 自动生成 · {generated_at} · 共 {fact_count} 条原文事实 · {source_count} 个来源

> 原文直存。中文翻译和归纳请到网页版点击按钮。

---

## 1. 分类要点

{category_sections}

---

## 2. 来源列表

{source_list}

---

## 3. 候选议题（待看池）

{pending_topics}

---

*生成时间：{generated_at} · 共 {fact_count} 条事实 · 活跃议题：{active_topic_count}*
"""

CATEGORY_SECTION_MD = """### {category}（{count} 条）

{facts}
"""

FACT_MD = """- **{fid}** · 🔥{hot} · {source} · {published}
  - 原文：[{original_title}]({url})
  - 摘要：{summary}
  - 图片：{image}
"""

SOURCE_LIST_MD = """- {source}（{count} 条）"""

PENDING_TOPIC_MD = """- **{topic}**（{status} · {source_count} 源）
  - 关键词：{keywords}
  - 首次出现：{first_seen}
  - 最近出现：{last_seen}
  - 关联事实：{fact_count} 条
"""

# ============================================================
# HTML 模板 — 每日页面
# ============================================================

HTML_HEAD = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日世界简报 · {date}</title>
<style>
  :root {{
    --bg: #fafafa; --fg: #1a1a1a; --muted: #666; --border: #e5e5e5;
    --accent: #2563eb; --high: #dc2626; --medium: #d97706; --low: #6b7280;
    --card: #ffffff; --hover: #f3f4f6;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0f0f0f; --fg: #e5e5e5; --muted: #999; --border: #2a2a2a;
      --card: #1a1a1a; --hover: #262626;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg); color: var(--fg);
    line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 16px;
  }}
  h1 {{ font-size: 1.6em; margin: 0 0 8px; }}
  h2 {{ font-size: 1.25em; margin: 32px 0 12px; padding-bottom: 8px; border-bottom: 2px solid var(--border); }}
  h3 {{ font-size: 1.05em; margin: 20px 0 8px; color: var(--muted); }}
  .meta {{ color: var(--muted); font-size: 0.9em; margin-bottom: 24px; }}
  .back-home {{
    display: inline-block; margin-bottom: 16px; padding: 6px 12px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: 4px; font-size: 0.9em; color: var(--fg); text-decoration: none;
  }}
  .back-home:hover {{ background: var(--hover); }}

  .fact {{
    background: var(--card); border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 6px; padding: 12px 14px; margin: 8px 0;
  }}
  .fact-header {{ display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }}
  .fact-id {{ font-family: ui-monospace, monospace; font-size: 0.85em; color: var(--muted); }}
  .hot {{
    font-size: 0.8em; padding: 1px 6px; border-radius: 3px;
    background: #fde68a; color: #92400e;
  }}
  .hot.high {{ background: #fecaca; color: #991b1b; }}
  .hot.medium {{ background: #fed7aa; color: #9a3412; }}
  .category-tag {{
    font-size: 0.75em; padding: 1px 6px; border-radius: 3px;
    background: var(--border); color: var(--muted);
  }}
  .fact-title {{ font-weight: 600; margin: 6px 0; font-size: 1.05em; }}
  .fact-title a {{ color: var(--fg); text-decoration: none; }}
  .fact-title a:hover {{ color: var(--accent); text-decoration: underline; }}
  .fact-meta {{ font-size: 0.85em; color: var(--muted); margin: 4px 0; }}
  .fact-summary {{ margin: 6px 0; font-size: 0.95em; color: var(--fg); }}
  .fact-image {{ max-width: 100%; border-radius: 4px; margin: 6px 0; }}

  .btn-row {{ margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }}
  .btn {{
    padding: 4px 10px; border: 1px solid var(--border);
    background: var(--card); color: var(--fg);
    border-radius: 4px; font-size: 0.85em; cursor: pointer;
    transition: all 0.15s;
  }}
  .btn:hover {{ background: var(--hover); border-color: var(--accent); }}
  .btn:disabled {{ opacity: 0.5; cursor: wait; }}
  .btn-primary {{ background: var(--accent); color: white; border-color: var(--accent); }}
  .btn-primary:hover {{ background: #1d4ed8; }}

  .ai-result {{
    margin-top: 8px; padding: 10px 12px;
    background: rgba(37, 99, 235, 0.05);
    border-left: 3px solid var(--accent);
    border-radius: 4px; font-size: 0.92em;
    white-space: pre-wrap;
  }}
  .ai-result.error {{
    background: rgba(220, 38, 38, 0.05);
    border-left-color: var(--high); color: var(--high);
  }}
  .ai-tag {{
    display: inline-block; font-size: 0.7em;
    background: var(--accent); color: white;
    padding: 1px 6px; border-radius: 3px; margin-right: 6px;
  }}
  .pending-card {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 6px; padding: 10px 12px; margin: 6px 0;
  }}
  .pending-name {{ font-weight: 600; }}
  .pending-meta {{ color: var(--muted); font-size: 0.85em; margin-top: 4px; }}
  .status-tag {{
    display: inline-block; font-size: 0.7em; padding: 1px 5px;
    border-radius: 3px; background: var(--border);
  }}
  .status-tag.tracking {{ background: #d1fae5; color: #065f46; }}
  .status-tag.pending {{ background: #fef3c7; color: #92400e; }}
  .status-tag.archived {{ background: var(--border); color: var(--muted); }}

  @media (max-width: 600px) {{
    body {{ padding: 10px; }}
    h1 {{ font-size: 1.3em; }}
    h2 {{ font-size: 1.1em; }}
    .fact {{ padding: 10px; }}
  }}
</style>
</head>
<body>
<a class="back-home" href="index.html">← 回到首页</a>
<h1>每日世界简报 · {date}</h1>
<div class="meta">生成于 {generated_at} · {fact_count} 条原文事实 · {source_count} 个来源</div>
<div class="meta" style="background:var(--card);padding:8px 12px;border-radius:4px;border:1px solid var(--border);">
  💡 <strong>原文直存</strong>：默认显示英文标题和摘要。点 <strong>「中文翻译」</strong> 看译文，点 <strong>「归纳」</strong> 看分析。AI 只在点击时调用。
</div>
"""

HTML_TAIL = """<script>
// AI 调用逻辑
async function callAI(endpoint, payload, btn, resultContainer) {
  btn.disabled = true;
  btn.textContent = '调用中...';
  resultContainer.innerHTML = '<span class="ai-tag">AI</span>正在调用...';
  resultContainer.classList.remove('error');

  try {
    const resp = await fetch('/api/' + endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || 'HTTP ' + resp.status);
    }
    const data = await resp.json();
    let text = '';
    if (data.translation) text = data.translation;
    else if (data.summarize) text = data.summarize;
    else if (data.summary) text = data.summary;
    else if (data.topic) text = data.topic;
    else text = JSON.stringify(data, null, 2);
    resultContainer.innerHTML = '<span class="ai-tag">AI</span>' + escapeHtml(text);
    btn.textContent = '✓ 完成';
  } catch (e) {
    resultContainer.classList.add('error');
    resultContainer.innerHTML = '<span class="ai-tag">ERROR</span>' + escapeHtml(e.message || '调用失败');
    btn.textContent = '重试';
    btn.disabled = false;
  }
}

function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

document.addEventListener('click', function (e) {
  const btn = e.target.closest('.ai-btn');
  if (!btn) return;
  const factId = btn.dataset.fid;
  const action = btn.dataset.action; // 'translate' | 'summarize'
  const endpoint = action;
  const resultId = 'result-' + action + '-' + factId;
  const resultContainer = document.getElementById(resultId);
  if (!resultContainer) return;

  // 收集这条 fact 的内容（从 DOM 读）
  const factEl = btn.closest('.fact');
  const title = factEl.querySelector('.fact-title a')?.textContent || '';
  const url = factEl.querySelector('.fact-title a')?.href || '';
  const summary = factEl.querySelector('.fact-summary')?.textContent || '';
  const source = factEl.querySelector('.source-name')?.textContent || '';
  const date = document.querySelector('h1')?.textContent?.replace('每日世界简报 · ', '').trim() || '';

  const payload = { fid: factId, title, summary, url, source, date };

  if (action === 'summarize') {
    // 归纳需要更多上下文
    payload.fact = { id: factId, title, summary, url, source, date };
  }

  callAI(endpoint, payload, btn, resultContainer);
});
</script>
</body></html>"""


def render_daily_html(date: str, sections: dict) -> str:
    """渲染每日 HTML 页面"""
    parts = [HTML_HEAD.format(**sections)]

    # 1. 分类要点
    parts.append("<h2>1. 分类要点</h2>")
    for cat in ["农业", "经济", "金融", "科技", "政治", "军事", "娱乐", "社会", "新闻"]:
        facts = sections.get("by_category", {}).get(cat, [])
        if not facts:
            continue
        parts.append(f"<h3>{cat}（{len(facts)} 条）</h3>")
        for f in facts:
            parts.append(_render_fact_html(f))

    # 2. 来源列表
    parts.append("<h2>2. 来源列表</h2>")
    parts.append("<ul>")
    for src, count in sections.get("source_summary", []):
        parts.append(f"<li>{_esc(src)}（{count} 条）</li>")
    parts.append("</ul>")

    # 3. 候选议题
    parts.append("<h2>3. 候选议题（待看池）</h2>")
    if sections.get("pending_topics"):
        for t in sections["pending_topics"]:
            parts.append(_render_pending_html(t))
    else:
        parts.append('<p class="meta">暂无</p>')

    parts.append(HTML_TAIL)
    return "\n".join(parts)


def _render_fact_html(f: dict) -> str:
    hot = f.get("hot_score", 0)
    hot_class = "high" if hot >= 60 else ("medium" if hot >= 30 else "")
    cat = f.get("category", "")
    fid = f.get("fid", "")
    image_html = ""
    if f.get("image"):
        image_html = f'<img class="fact-image" src="{_esc(f["image"])}" alt="" loading="lazy">'

    summary = f.get("summary", "")
    if len(summary) > 300:
        summary = summary[:300] + "…"

    hot_class = _esc(hot_class)

    return (
        f'<div class="fact" data-fid="{_esc(fid)}">'
        f'<div class="fact-header">'
        f'<span class="fact-id">{_esc(fid)}</span>'
        f'<span class="hot {hot_class}">🔥{hot}</span>'
        f'<span class="category-tag">{_esc(cat)}</span>'
        f'<span class="fact-meta source-name">{_esc(f.get("source", ""))} · {_esc(f.get("published_display", ""))}</span>'
        f'</div>'
        f'<div class="fact-title"><a href="{_esc(f.get("url", "#"), quote=True)}" target="_blank" rel="noopener">{_esc(f.get("title", ""))}</a></div>'
        f'{image_html}'
        f'<div class="fact-summary">{_esc(summary)}</div>'
        f'<div class="btn-row">'
        f'<button class="btn btn-primary ai-btn" data-fid="{_esc(fid)}" data-action="translate">中文翻译</button>'
        f'<button class="btn ai-btn" data-fid="{_esc(fid)}" data-action="summarize">归纳</button>'
        f'</div>'
        f'<div class="ai-result" id="result-translate-{_esc(fid)}" style="display:none;"></div>'
        f'<div class="ai-result" id="result-summarize-{_esc(fid)}" style="display:none;"></div>'
        f'</div>'
    )


def _render_pending_html(t: dict) -> str:
    status = t.get("status", "pending")
    keywords = ", ".join(str(k) for k in t.get("keywords", [])[:5])
    return (
        f'<div class="pending-card">'
        f'<div class="pending-name">'
        f'<span class="status-tag {_esc(status)}">{_esc(status)}</span> '
        f'{_esc(t.get("topic", ""))}'
        f'</div>'
        f'<div class="pending-meta">'
        f'{_esc(str(t.get("source_count", 0)))} 个来源 · '
        f'首次 {_esc(t.get("first_seen", ""))} · '
        f'最近 {_esc(t.get("last_seen", ""))} · '
        f'{_esc(str(len(t.get("fact_ids", []))))} 条事实'
        f'</div>'
        f'<div class="pending-meta">关键词：{_esc(keywords)}</div>'
        f'</div>'
    )


# ============================================================
# Index HTML
# ============================================================

INDEX_HEAD = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日世界简报 · 归档</title>
<style>
  :root {{ --bg:#fafafa; --fg:#1a1a1a; --muted:#666; --border:#e5e5e5; --accent:#2563eb; --card:#ffffff; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#0f0f0f; --fg:#e5e5e5; --muted:#999; --border:#2a2a2a; --card:#1a1a1a; }} }}
  * {{ box-sizing: border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; background:var(--bg); color:var(--fg); max-width:900px; margin:0 auto; padding:16px; line-height:1.6; }}
  h1 {{ font-size:1.6em; margin:0 0 8px; }}
  h2 {{ font-size:1.25em; margin:24px 0 12px; padding-bottom:8px; border-bottom:2px solid var(--border); }}
  .meta {{ color:var(--muted); font-size:0.9em; margin-bottom:16px; }}
  .search-box {{ width:100%; padding:10px 14px; border:1px solid var(--border); border-radius:6px; font-size:1em; background:var(--card); color:var(--fg); margin:16px 0; }}
  .day-list {{ list-style:none; padding:0; }}
  .day-list li {{ padding:8px 0; border-bottom:1px solid var(--border); }}
  .day-list a {{ color:var(--accent); text-decoration:none; font-weight:500; }}
  .day-list a:hover {{ text-decoration:underline; }}
  .results {{ margin-top:24px; }}
  .result {{ background:var(--card); border:1px solid var(--border); border-radius:6px; padding:10px 12px; margin:6px 0; }}
  .result-title {{ font-weight:600; }}
  .result-meta {{ color:var(--muted); font-size:0.85em; margin:4px 0; }}
  .result-snippet {{ font-size:0.9em; }}
  .empty {{ color:var(--muted); padding:16px; text-align:center; }}
  mark {{ background:#fde68a; color:#000; }}
  @media (max-width:600px) {{ body {{ padding:10px; }} }}
</style>
</head>
<body>
<h1>每日世界简报</h1>
<div class="meta">手机、电脑都能看 · 离线搜索可用 · 原文直存，按需翻译</div>
<input type="text" id="search" class="search-box" placeholder="搜索关键词、日期、来源、事实编号…">
<div class="results" id="results"></div>
<h2>历史归档</h2>
<ul class="day-list">
"""


def render_index_html(entries: list, search_index: list) -> str:
    parts = [INDEX_HEAD]
    for stem, label in entries:
        parts.append(f'<li><a href="archive/{stem}.html">{_esc(label)}</a></li>')
    parts.append("</ul>")
    parts.append('<script>window.__SEARCH_INDEX__ = ' + _to_json(search_index) + ';</script>')
    parts.append('<script src="search.js"></script>')
    parts.append("</body></html>")
    return "\n".join(parts)


def _to_json(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


# ============================================================
# 主题页面
# ============================================================

def render_topic_html(topic: str, facts: list, year: str) -> str:
    """主题档案页面"""
    facts_html = "\n".join(
        f'<div class="fact" data-fid="{_esc(f.get("id", ""))}">'
        f'<div class="fact-id">{_esc(f.get("id", ""))}</div>'
        f'<div class="fact-title"><a href="{_esc(f.get("url", "#"), quote=True)}" target="_blank" rel="noopener">{_esc(f.get("title", ""))}</a></div>'
        f'<div class="fact-meta">{_esc(f.get("source", ""))} · {f.get("date", "")}</div>'
        f'<div class="fact-summary">{_esc((f.get("summary", "") or "")[:200])}</div>'
        f'<div class="btn-row">'
        f'<button class="btn btn-primary ai-btn" data-fid="{_esc(f.get("id", ""))}" data-action="translate">中文翻译</button>'
        f'</div>'
        f'<div class="ai-result" id="result-translate-{_esc(f.get("id", ""))}" style="display:none;"></div>'
        f'</div>'
        for f in facts
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>主题：{_esc(topic)} · {_esc(year)}</title>
<style>
  body {{ font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; max-width:900px; margin:0 auto; padding:16px; line-height:1.6; }}
  h1 {{ font-size:1.6em; margin:0 0 8px; }}
  .fact {{ background:#fafafa; border:1px solid #e5e5e5; border-left:4px solid #2563eb; border-radius:6px; padding:12px 14px; margin:8px 0; }}
  .fact-id {{ font-family:ui-monospace,monospace; font-size:0.85em; color:#666; }}
  .fact-title {{ font-weight:600; margin:6px 0; }}
  .fact-title a {{ color:#1a1a1a; text-decoration:none; }}
  .fact-title a:hover {{ color:#2563eb; }}
  .fact-meta {{ font-size:0.85em; color:#666; margin:4px 0; }}
  .fact-summary {{ margin:6px 0; font-size:0.95em; }}
  .btn {{ padding:4px 10px; border:1px solid #e5e5e5; background:white; color:#1a1a1a; border-radius:4px; font-size:0.85em; cursor:pointer; margin-top:8px; }}
  .btn-primary {{ background:#2563eb; color:white; border-color:#2563eb; }}
  .ai-result {{ margin-top:8px; padding:10px 12px; background:rgba(37,99,235,0.05); border-left:3px solid #2563eb; border-radius:4px; font-size:0.92em; white-space:pre-wrap; display:none; }}
  .ai-result.error {{ background:rgba(220,38,38,0.05); border-left-color:#dc2626; color:#dc2626; }}
  .ai-tag {{ display:inline-block; font-size:0.7em; background:#2563eb; color:white; padding:1px 6px; border-radius:3px; margin-right:6px; }}
  .back-home {{ display:inline-block; margin-bottom:16px; padding:6px 12px; background:white; border:1px solid #e5e5e5; border-radius:4px; font-size:0.9em; color:#1a1a1a; text-decoration:none; }}
  .topic-meta {{ background:#fef3c7; border-left:4px solid #f59e0b; padding:10px 12px; border-radius:4px; margin:16px 0; font-size:0.9em; }}
  .btn-row {{ display:flex; gap:6px; flex-wrap:wrap; }}
  .big-btn {{ padding:8px 16px; background:#2563eb; color:white; border:none; border-radius:4px; cursor:pointer; font-size:0.95em; }}
  .big-btn:hover {{ background:#1d4ed8; }}
</style>
</head>
<body>
<a class="back-home" href="index.html">← 回到首页</a>
<h1>主题：{_esc(topic)} · {_esc(year)}</h1>
<div class="topic-meta">
  📌 共 {len(facts)} 条事实。<br>
  💡 点击下方「归纳这个主题」按钮可让 AI 总结过去一个月的关键事件、转折点、关联议题。
</div>
<button class="big-btn" id="topic-summary-btn">归纳这个主题</button>
<div class="ai-result" id="topic-summary-result" style="display:none;"></div>
<h2>事实时间线</h2>
{facts_html}
<script>
document.getElementById('topic-summary-btn').addEventListener('click', async function() {{
  const btn = this;
  const result = document.getElementById('topic-summary-result');
  btn.disabled = true; btn.textContent = '调用中...';
  result.style.display = 'block';
  result.innerHTML = '<span class="ai-tag">AI</span>正在调用...';
  try {{
    const resp = await fetch('/api/topic', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ topic: {_to_json(topic)}, year: {_to_json(year)}, facts: {facts_json} }}),
    }});
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    const text = data.topic || data.summary || JSON.stringify(data, null, 2);
    result.innerHTML = '<span class="ai-tag">AI</span>' + escapeHtml(text);
    btn.textContent = '✓ 完成';
  }} catch (e) {{
    result.classList.add('error');
    result.innerHTML = '<span class="ai-tag">ERROR</span>' + escapeHtml(e.message);
    btn.disabled = false; btn.textContent = '重试';
  }}
}});

// 单条翻译按钮
document.addEventListener('click', async function(e) {{
  const btn = e.target.closest('.ai-btn');
  if (!btn || btn.dataset.action !== 'translate') return;
  const factEl = btn.closest('.fact');
  const title = factEl.querySelector('.fact-title a')?.textContent || '';
  const url = factEl.querySelector('.fact-title a')?.href || '';
  const summary = factEl.querySelector('.fact-summary')?.textContent || '';
  const fid = btn.dataset.fid;
  const result = document.getElementById('result-translate-' + fid);
  btn.disabled = true; btn.textContent = '调用中...';
  result.style.display = 'block';
  result.innerHTML = '<span class="ai-tag">AI</span>正在调用...';
  try {{
    const resp = await fetch('/api/translate', {{
      method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ title, summary, url }}),
    }});
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    result.innerHTML = '<span class="ai-tag">AI</span>' + escapeHtml(data.translation || '');
    btn.textContent = '✓ 完成';
  }} catch (e) {{
    result.classList.add('error');
    result.innerHTML = '<span class="ai-tag">ERROR</span>' + escapeHtml(e.message);
    btn.disabled = false; btn.textContent = '重试';
  }}
}});

function escapeHtml(s) {{
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}
</script>
</body></html>"""


# ============================================================
# 月度页面
# ============================================================

def render_monthly_html(month: str, facts_count: int, summary: str = "") -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>月度总结 · {month}</title>
<style>
  body {{ font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; max-width:900px; margin:0 auto; padding:16px; line-height:1.6; }}
  h1 {{ font-size:1.6em; margin:0 0 8px; }}
  .meta {{ color:#666; font-size:0.9em; margin-bottom:24px; }}
  .ai-result {{ margin:16px 0; padding:14px; background:rgba(37,99,235,0.05); border-left:4px solid #2563eb; border-radius:4px; white-space:pre-wrap; }}
  .ai-result.error {{ background:rgba(220,38,38,0.05); border-left-color:#dc2626; color:#dc2626; }}
  .ai-tag {{ display:inline-block; font-size:0.7em; background:#2563eb; color:white; padding:1px 6px; border-radius:3px; margin-right:6px; }}
  .big-btn {{ padding:10px 20px; background:#2563eb; color:white; border:none; border-radius:4px; cursor:pointer; font-size:1em; }}
  .big-btn:hover {{ background:#1d4ed8; }}
  .back-home {{ display:inline-block; margin-bottom:16px; padding:6px 12px; background:white; border:1px solid #e5e5e5; border-radius:4px; font-size:0.9em; color:#1a1a1a; text-decoration:none; }}
</style>
</head>
<body>
<a class="back-home" href="../../index.html">← 回到首页</a>
<h1>月度总结 · {month}</h1>
<div class="meta">本月共抓取 {facts_count} 条事实</div>
<button class="big-btn" id="monthly-btn">生成月度总结</button>
<div class="ai-result" id="monthly-result" style="display:none;"></div>
<script>
document.getElementById('monthly-btn').addEventListener('click', async function() {{
  const btn = this, result = document.getElementById('monthly-result');
  btn.disabled = true; btn.textContent = '生成中...';
  result.style.display = 'block';
  result.innerHTML = '<span class="ai-tag">AI</span>正在生成月度总结（可能需要 1-2 分钟）...';
  try {{
    const resp = await fetch('/api/monthly', {{
      method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ month: "{month}" }}),
    }});
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    result.innerHTML = '<span class="ai-tag">AI</span>' + escapeHtml(data.summary || '');
    btn.textContent = '✓ 完成';
  }} catch (e) {{
    result.classList.add('error');
    result.innerHTML = '<span class="ai-tag">ERROR</span>' + escapeHtml(e.message);
    btn.disabled = false; btn.textContent = '重试';
  }}
}});
function escapeHtml(s) {{
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}
</script>
</body></html>"""
