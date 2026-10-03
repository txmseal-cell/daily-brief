// search.js — 客户端搜索（按日期、分类、关键词、来源、事实编号）
// 离线可用，不依赖外部库

(function () {
  "use strict";

  const INDEX = window.__SEARCH_INDEX__ || [];
  const input = document.getElementById("search");
  const results = document.getElementById("results");
  const list = document.querySelector(".day-list");

  if (!input || !results) return;

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function highlight(text, q) {
    if (!q) return escapeHtml(text);
    const re = new RegExp("(" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
    return escapeHtml(text).replace(re, '<mark>$1</mark>');
  }

  function scoreFact(f, q) {
    const ql = q.toLowerCase();
    let s = 0;
    if ((f.title || "").toLowerCase().includes(ql)) s += 10;
    if ((f.summary || "").toLowerCase().includes(ql)) s += 3;
    if ((f.source || "").toLowerCase().includes(ql)) s += 2;
    if ((f.category || "").toLowerCase().includes(ql)) s += 2;
    if ((f.date || "").includes(ql)) s += 5;
    if (f.id && f.id.toLowerCase().includes(ql)) s += 8;
    return s;
  }

  function renderResults(q) {
    if (!q || q.length < 2) {
      results.innerHTML = "";
      if (list) list.style.display = "";
      return;
    }
    if (list) list.style.display = "none";

    const matches = INDEX
      .map((f) => ({ f, s: scoreFact(f, q) }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 50);

    if (matches.length === 0) {
      results.innerHTML = '<div class="empty">没有匹配的结果</div>';
      return;
    }

    const html = matches
      .map(({ f }) => {
        const dateLink = f.date ? `<a href="archive/${f.date}.html">${f.date}</a> · ` : "";
        return `
          <div class="result">
            <div class="result-title">${highlight(f.title, q)}</div>
            <div class="result-meta">
              ${dateLink}
              <span>${escapeHtml(f.id || "")}</span> ·
              <span>${escapeHtml(f.source || "")}</span> ·
              <span>${escapeHtml(f.category || "")}</span>
            </div>
            <div class="result-snippet">${highlight((f.summary || "").slice(0, 240), q)}</div>
            ${f.url ? `<div class="result-meta"><a href="${escapeHtml(f.url)}" target="_blank" rel="noopener">原文 →</a></div>` : ""}
          </div>
        `;
      })
      .join("");

    results.innerHTML = `<div class="meta">${matches.length} 条匹配（最多 50）</div>` + html;
  }

  let timer;
  input.addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => renderResults(e.target.value.trim()), 150);
  });

  // URL ?q=xxx
  const params = new URLSearchParams(window.location.search);
  const initialQ = params.get("q");
  if (initialQ) {
    input.value = initialQ;
    renderResults(initialQ);
  }
})();
