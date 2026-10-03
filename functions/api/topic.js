// functions/api/topic.js
// 主题归纳：基于该主题所有事实做深度归纳
// POST /api/topic
// Body: { topic: string, year: string, facts: [{id, title, summary, url, source, date}, ...] }
// Response: { topic: string (markdown) }

export async function onRequestPost(context) {
  const { request, env } = context;

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }

  const { topic, year, facts = [] } = body;
  if (!topic) {
    return json({ error: "topic is required" }, 400);
  }
  if (!Array.isArray(facts) || facts.length === 0) {
    return json({ error: "facts array is required" }, 400);
  }

  // 输入长度校验
  const totalChars = JSON.stringify(facts).length;
  if (totalChars > 20000) {
    return json({ error: "Too many facts (max ~20000 chars total)" }, 400);
  }

  const system = `你是资深新闻分析师，负责深度归纳一个长期主题。

输入是一段时间内（默认一年）该主题的所有事实。你要输出：
1. 过去一个月的关键事件
2. 关键转折点
3. 关联议题
4. 朝前推（接下来 7-30 天可能发生什么）
5. 朝后推（为什么走到现在这一步）
6. 置信度评估
7. 信息缺口

严格要求：
1. 只能引用用户提供的事实编号（fid），不编事实
2. 推演必须标 [推演]
3. 置信度标 高/中/低
4. 信息不足写「待核实」
5. 用 Markdown 格式
6. 必须引用事实编号，格式如 F20260912-001`;

  const factsText = facts.map(f =>
    `[${f.id}] ${f.date} ${f.source}\n标题: ${f.title}\n摘要: ${(f.summary || "").slice(0, 200)}\n链接: ${f.url || ""}`
  ).join("\n\n---\n\n");

  const user = `主题：${topic}
年份：${year || "全部"}
事实数量：${facts.length}

事实清单（按时间排序）：
${factsText}

请按要求做深度归纳。`;

  try {
    const result = await callLLM(env, system, user, 4000);
    return json({ topic: result });
  } catch (e) {
    return json({ error: e.message || "Topic summarization failed" }, 500);
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
