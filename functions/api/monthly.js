// functions/api/monthly.js
// 月度总结：拉取某月所有事实，AI 生成月度报告
// POST /api/monthly
// Body: { month: "2026-09" }
// Response: { summary: string (markdown) }

export async function onRequestPost(context) {
  const { request, env } = context;

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }

  const { month } = body;  // "2026-09"
  if (!month || !/^\d{4}-\d{2}$/.test(month)) {
    return json({ error: "month must be in YYYY-MM format" }, 400);
  }

  // 1. 读 data/facts.json
  // 部署后，data/ 目录会随 repo 一起部署，可以通过 KV/R2 存
  // 这里用 GitHub raw URL 兜底（如果 Cloudflare Pages 的 functions 没法直接读 repo 文件）
  let allFacts = [];
  try {
    // Cloudflare Pages 的 Functions 可以用 fetch 访问静态资源
    // 但 data/facts.json 不一定被部署为静态资源
    // 安全做法：从 GitHub raw 拉
    const repoUrl = env.REPO_URL || "";  // 用户可配
    if (repoUrl) {
      const r = await fetch(`${repoUrl}/data/facts.json`);
      if (r.ok) allFacts = await r.json();
    }
  } catch (e) {
    console.error("fetch facts.json failed:", e.message);
  }

  // 过滤该月事实
  const monthFacts = allFacts.filter(f => f.date && f.date.startsWith(month));
  if (monthFacts.length === 0) {
    return json({ summary: `本月 (${month}) 暂无数据。请确认已运行 daily workflow 至少 1 天。` });
  }

  // 限制输入大小（按 hot_score 排序取 top）
  monthFacts.sort((a, b) => (b.hot_score || 0) - (a.hot_score || 0));
  const topFacts = monthFacts.slice(0, 100);

  const system = `你是资深新闻分析师，负责生成月度总结报告。

输入是一个月内最重要的 top 100 条事实（按热度排序）。你要输出：
1. 本月主线（3-5 条最关键的世界走向）
2. 分类要点（农业/经济金融/科技/政治军事 各领域的核心动态）
3. 关键议题与转折
4. 朝前推（下个月值得关注的走向）
5. 信息缺口

严格要求：
1. 只能引用用户提供的事实编号（FYYYYMMDD-NNN），不编事实
2. 推演必须标 [推演]
3. 置信度标 高/中/低
4. 信息不足写「待核实」
5. 用 Markdown 格式`;

  const factsText = topFacts.map(f =>
    `[${f.id}] ${f.date} ${f.source} (🔥${f.hot_score || 0})\n${f.title}\n${(f.summary || "").slice(0, 200)}`
  ).join("\n\n");

  const user = `月份：${month}
事实数量：${monthFacts.length}（取 top ${topFacts.length} 做归纳）

事实清单：
${factsText}

请生成该月的总结报告。`;

  try {
    const summary = await callLLM(env, system, user, 4000);
    return json({ summary });
  } catch (e) {
    return json({ error: e.message || "Monthly summary failed" }, 500);
  }
}

async function callLLM(env, system, userText, maxTokens = 4000) {
  const primaryKey = env.MINIMAX_API_KEY;
  const fallbackKey = env.DEEPSEEK_API_KEY;

  if (!primaryKey && !fallbackKey) {
    throw new Error("No LLM API key configured");
  }

  if (primaryKey) {
    try {
      const r = await fetch("https://api.minimaxi.com/v1/chat/completions", {
        method: "POST",
        headers: {
          "Authorization": "Bearer " + primaryKey,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "MiniMax-Text-01",
          messages: [
            { role: "system", content: system },
            { role: "user", content: userText },
          ],
          temperature: 0.4,
          max_tokens: maxTokens,
        }),
      });
      if (r.ok) {
        const data = await r.json();
        const text = data.choices?.[0]?.message?.content;
        if (text) return text.trim();
      }
      throw new Error("DeepSeek: " + r.status);
    } catch (e) {
      console.error("DeepSeek failed:", e.message);
      if (!fallbackKey) throw e;
    }
  }

  if (fallbackKey) {
    const r = await fetch("https://api.deepseek.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + fallbackKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "deepseek-chat",
        messages: [
          { role: "system", content: system },
          { role: "user", content: userText },
        ],
        temperature: 0.4,
        max_tokens: maxTokens,
      }),
    });
    if (!r.ok) throw new Error("DeepSeek: " + r.status);
    const data = await r.json();
    const text = data.choices?.[0]?.message?.content;
    if (!text) throw new Error("MiniMax returned empty");
    return text.trim();
  }

  throw new Error("All LLM providers failed");
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
