// functions/api/config.js
// 读写 Cloudflare KV 的配置（用户在 admin.html 上编辑的内容）
// GET  /api/config  → 读 KV 返回配置
// POST /api/config  → 写 KV 保存配置
// DELETE /api/config → 清空 KV（恢复 GitHub config.yaml）
//
// 需要的 KV namespace binding（在 Cloudflare Pages 项目设置）：
//   Variable name: CONFIG
//   KV namespace:    任意名字（建议 daily-brief-config）

export async function onRequest(context) {
  const { request, env } = context;
  const kv = env.CONFIG;

  if (!kv) {
    return json({ error: "KV namespace 'CONFIG' not bound. See project Settings → Functions → KV namespace bindings." }, 500);
  }

  try {
    if (request.method === "GET") {
      const data = await kv.get("custom_config", { type: "json" });
      return json(data || defaultConfig());
    }

    if (request.method === "POST") {
      let body;
      try {
        body = await request.json();
      } catch {
        return json({ error: "Invalid JSON body" }, 400);
      }
      // 基本校验
      if (!body || typeof body !== "object") {
        return json({ error: "Body must be JSON object" }, 400);
      }
      if (!Array.isArray(body.sources)) body.sources = [];
      if (!Array.isArray(body.manual_topics)) body.manual_topics = [];
      // 单条 source 校验
      for (const s of body.sources) {
        if (!s.name || !s.url) return json({ error: "RSS 源必须有 name 和 url" }, 400);
        if (!s.url.startsWith("http")) return json({ error: "RSS URL 必须以 http 开头" }, 400);
      }
      // 单条 keyword 校验
      for (const t of body.manual_topics) {
        if (!t.name || !Array.isArray(t.keywords) || !t.keywords.length) {
          return json({ error: "关键词主题必须有 name 和 keywords[]" }, 400);
        }
      }
      // 限制大小（防止滥用）
      if (JSON.stringify(body).length > 100000) {
        return json({ error: "配置太大（>100KB）" }, 400);
      }
      body.updated_at = new Date().toISOString();
      await kv.put("custom_config", JSON.stringify(body));
      return json({ ok: true, updated_at: body.updated_at });
    }

    if (request.method === "DELETE") {
      await kv.delete("custom_config");
      return json({ ok: true, message: "已清空" });
    }

    return json({ error: "Method not allowed" }, 405);
  } catch (e) {
    return json({ error: e.message || "Internal error" }, 500);
  }
}

function defaultConfig() {
  return {
    sources: [],
    manual_topics: [],
    failed_sources: [],
    updated_at: "",
  };
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}