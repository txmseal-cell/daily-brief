// functions/api/translate.js
// 单条新闻翻译：英文 → 中文
// POST /api/translate
// Body: { title: string, summary: string, url?: string }
// Response: { translation: string }

export async function onRequestPost(context) {
  const { request, env } = context;

  // 1. 解析 body
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }

  const { title = "", summary = "" } = body;
  const text = (title + "\n\n" + summary).trim();

  // 2. 输入校验
  if (!text) {
    return json({ error: "title and summary are required" }, 400);
  }
  if (text.length > 5000) {
    return json({ error: "Input too long (max 5000 chars)" }, 400);
  }

  // 3. 调用 LLM（MiniMax 主用，DeepSeek 备用）
  const system = "你是专业的中英双语新闻翻译。把用户提供的英文新闻翻译成中文，只输出译文本身，不要任何解释、标题、Markdown 标记。专有名词（人名、公司、产品）保留原文。";

  try {
    const translation = await callLLM(env, system, text);
    return json({ translation });
  } catch (e) {
    return json({ error: e.message || "Translation failed" }, 500);
  }
}

// ============================================================
// LLM 调用：MiniMax 主用，DeepSeek 备用
// ============================================================
async function callLLM(env, system, userText) {
  const primaryKey = env.MINIMAX_API_KEY;
  const fallbackKey = env.DEEPSEEK_API_KEY;

  if (!primaryKey && !fallbackKey) {
    throw new Error("No LLM API key configured (DEEPSEEK_API_KEY or MINIMAX_API_KEY)");
  }

  // 1. 试 DeepSeek
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
          temperature: 0.3,
          max_tokens: 1500,
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

  // 2. 试 MiniMax
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
        temperature: 0.3,
        max_tokens: 1500,
      }),
    });
    if (!r.ok) throw new Error("DeepSeek: " + r.status);
    const data = await r.json();
    const text = data.choices?.[0]?.message?.content;
    if (!text) throw new Error("MiniMax returned empty content");
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
