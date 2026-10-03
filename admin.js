// admin.js — 管理页面交互
// 数据全部存到 Cloudflare Workers KV（通过 /api/config）

(function () {
  "use strict";

  const API = "/api/config";

  let config = {
    sources: [],
    manual_topics: [],
    failed_sources: [],
    updated_at: "",
  };

  // ============================================================
  // 工具
  // ============================================================
  function $(id) { return document.getElementById(id); }
  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
  function toast(msg, type) {
    const el = $("toast");
    el.textContent = msg;
    el.className = "toast show " + (type || "");
    setTimeout(() => { el.className = "toast " + (type || ""); }, 2500);
  }

  // ============================================================
  // API 调用
  // ============================================================
  async function loadConfig() {
    try {
      const resp = await fetch(API);
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      config = await resp.json();
    } catch (e) {
      toast("加载失败：" + e.message, "error");
      // fallback：默认空
      config = { sources: [], manual_topics: [], failed_sources: [], updated_at: "" };
    }
  }

  async function saveConfig() {
    config.updated_at = new Date().toISOString();
    try {
      const resp = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || "HTTP " + resp.status);
      }
      toast("✓ 保存成功！下次抓取生效", "success");
    } catch (e) {
      toast("保存失败：" + e.message, "error");
    }
  }

  async function resetConfig() {
    if (!confirm("确定要清空所有自定义配置吗？这会让 fetch.py 用 GitHub repo 里的 config.yaml。")) return;
    try {
      const resp = await fetch(API, { method: "DELETE" });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      toast("✓ 已清空，刷新页面看效果", "success");
      await loadConfig();
      render();
    } catch (e) {
      toast("重置失败：" + e.message, "error");
    }
  }

  // ============================================================
  // 渲染
  // ============================================================
  function renderRssList() {
    const list = $("rss-list");
    $("rss-count").textContent = config.sources.length;
    if (!config.sources.length) {
      list.innerHTML = '<div class="empty">还没有 RSS 源，点上面「+ 添加」加一个</div>';
      return;
    }
    list.innerHTML = config.sources.map((s, i) => {
      const failed = (config.failed_sources || []).includes(s.name);
      return `
        <div class="item" style="${failed ? 'border-left: 3px solid var(--danger);' : ''}">
          <div style="flex:1;">
            <div class="item-name">
              ${escapeHtml(s.name)}
              ${failed ? '<span style="color:var(--danger); font-size:0.85em; margin-left:6px;">⚠ 失效</span>' : ''}
              <span style="color:var(--muted); font-size:0.85em; margin-left:6px;">[${escapeHtml(s.category)}]</span>
            </div>
            <div class="item-meta">${escapeHtml(s.url)} · 最多 ${s.max_items || 2} 条</div>
          </div>
          <button data-idx="${i}" data-action="edit">编辑</button>
          <button data-idx="${i}" data-action="del" class="danger">删除</button>
        </div>
      `;
    }).join("");
  }

  function renderKwList() {
    const list = $("kw-list");
    $("kw-count").textContent = config.manual_topics.length;
    if (!config.manual_topics.length) {
      list.innerHTML = '<div class="empty">还没有关键词，点上面「+ 添加」加一个</div>';
      return;
    }
    list.innerHTML = config.manual_topics.map((t, i) => `
      <div class="item">
        <div style="flex:1;">
          <div class="item-name">${escapeHtml(t.name)}</div>
          <div class="item-meta">${escapeHtml((t.keywords || []).join(", "))}</div>
        </div>
        <button data-idx="${i}" data-action="edit-kw">编辑</button>
        <button data-idx="${i}" data-action="del-kw" class="danger">删除</button>
      </div>
    `).join("");
  }

  function render() {
    renderRssList();
    renderKwList();
    $("rss-status").textContent = config.updated_at
      ? `最后保存：${new Date(config.updated_at).toLocaleString("zh-CN")}`
      : "";
  }

  // ============================================================
  // 操作
  // ============================================================
  function addRss() {
    const name = $("new-rss-name").value.trim();
    const url = $("new-rss-url").value.trim();
    const category = $("new-rss-category").value;
    const max_items = parseInt($("new-rss-max").value) || 2;

    if (!name || !url) { toast("名称和 URL 都要填", "error"); return; }
    if (!url.startsWith("http")) { toast("URL 必须以 http 开头", "error"); return; }

    // 查重
    if (config.sources.some(s => s.url === url)) {
      toast("URL 已存在", "error"); return;
    }

    config.sources.push({ name, url, category, max_items });
    $("new-rss-name").value = "";
    $("new-rss-url").value = "";
    renderRssList();
    toast("已添加，点底部「保存」生效", "success");
  }

  function deleteRss(idx) {
    if (!confirm("删除这个 RSS 源？")) return;
    config.sources.splice(idx, 1);
    renderRssList();
  }

  function editRss(idx) {
    const s = config.sources[idx];
    $("new-rss-name").value = s.name;
    $("new-rss-url").value = s.url;
    $("new-rss-category").value = s.category;
    $("new-rss-max").value = s.max_items || 2;
    config.sources.splice(idx, 1);
    renderRssList();
    $("new-rss-name").focus();
  }

  function addKw() {
    const name = $("new-kw-name").value.trim();
    const keywordsStr = $("new-kw-keywords").value.trim();
    if (!name || !keywordsStr) { toast("主题名和关键词都要填", "error"); return; }

    const keywords = keywordsStr.split(/[,，]/).map(k => k.trim()).filter(Boolean);
    if (!keywords.length) { toast("至少一个关键词", "error"); return; }

    config.manual_topics.push({ name, keywords });
    $("new-kw-name").value = "";
    $("new-kw-keywords").value = "";
    renderKwList();
    toast("已添加，点底部「保存」生效", "success");
  }

  function deleteKw(idx) {
    if (!confirm("删除这个关键词？")) return;
    config.manual_topics.splice(idx, 1);
    renderKwList();
  }

  function editKw(idx) {
    const t = config.manual_topics[idx];
    $("new-kw-name").value = t.name;
    $("new-kw-keywords").value = (t.keywords || []).join(", ");
    config.manual_topics.splice(idx, 1);
    renderKwList();
    $("new-kw-name").focus();
  }

  // ============================================================
  // 事件绑定
  // ============================================================
  document.addEventListener("DOMContentLoaded", async () => {
    await loadConfig();
    render();

    $("add-rss-btn").addEventListener("click", addRss);
    $("add-kw-btn").addEventListener("click", addKw);
    $("save-btn").addEventListener("click", saveConfig);
    $("reload-btn").addEventListener("click", async () => {
      await loadConfig(); render(); toast("已重新载入", "success");
    });
    $("reset-btn").addEventListener("click", resetConfig);

    $("rss-list").addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const idx = parseInt(btn.dataset.idx);
      if (btn.dataset.action === "del") deleteRss(idx);
      else if (btn.dataset.action === "edit") editRss(idx);
    });
    $("kw-list").addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const idx = parseInt(btn.dataset.idx);
      if (btn.dataset.action === "del-kw") deleteKw(idx);
      else if (btn.dataset.action === "edit-kw") editKw(idx);
    });

    // Enter 键提交
    $("new-rss-url").addEventListener("keydown", (e) => {
      if (e.key === "Enter") addRss();
    });
    $("new-kw-keywords").addEventListener("keydown", (e) => {
      if (e.key === "Enter") addKw();
    });
  });
})();