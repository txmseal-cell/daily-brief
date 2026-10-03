// functions/api/summarize.js
// 单条事实归纳：基于事实编号的事实做归纳
// POST /api/summarize
// Body: { fact: { id, title, summary, url, source, date } }
// Response: { summarize: string (markdown) }

export async function onRequestPost(context) {
  const { request, env } = context;

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }

  const { fact } = body;
  if (!fact || !fact.title) {
    return json({ error: "fact.title is required" }, 400);
  }

  const text = JSON.stringify(fact);
  if (text.length > 5000) {
    return json({ error: "Input too long (max 5000 chars)" }, 400);
  }

  const system = `你是资深新闻分析师。基于用户提供的一条事实（标题、摘要、来源、链接、日期），做归纳。

严格要求：
1. 只基于用户提供的事实，不编造
2. 必须引用事实编号（用户在 fact.id 里给了）
3. 事实层和推演层分开
4. 推演必须标 [推演]
5. 置信度标 高/中/低
6. 信息不足写「待核实」
7. 不编链接
8. 用 Markdown 格式输出

输出结构：
**[事实]** 一句话概括（依据 {fact.id}）

**[关键点]**
- 要点 1
- 要点 2
- 要点 3

**[影响领域]**
- 农业 / 经济 / 金融 / 科技 / 政治 / 军事（按事实内容选）

**[推演]** 可能的走向
- 依据：{fact.id}
- 置信度：高/中/低
- 信息缺口：待核实`;

  const user = `事实编号：${fact.id}
标题：${fact.title}
来源：${fact.source || "未知"}
日期：${fact.date || "未知"}
链接：${fact.url || "未知"}
摘要：${fact.summary || "(无)"}

请按上面结构归纳。`;

  try {
    const summarize = await callLLM(env, system, user);
    return json({ summarize });
  } catch (e) {
    return json({ error: e.message || "Summarization failed" }, 500);
  }
}

async function callLLM(env, system, userText) {
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
          max_tokens: 2000,
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
        max_tokens: 2000,
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
