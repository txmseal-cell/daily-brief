--- /tmp/gh_fetch.py	2026-10-03 18:12:54.277792230 +0800
+++ /workspace/daily-brief/fetch.py	2026-10-03 11:22:19.433044940 +0800
@@ -66,6 +66,69 @@
         return yaml.safe_load(f)
 
 
+def load_user_config_from_kv() -> dict:
+    """从 Cloudflare KV 读用户在 admin.html 上编辑的自定义配置
+    需要环境变量：
+      - CLOUDFLARE_API_TOKEN
+      - CLOUDFLARE_ACCOUNT_ID
+      - CLOUDFLARE_KV_NAMESPACE_ID
+    没有这些 env vars 就静默返回空（用 yaml 默认）
+    """
+    api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
+    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
+    namespace_id = os.environ.get("CLOUDFLARE_KV_NAMESPACE_ID")
+
+    if not all([api_token, account_id, namespace_id]):
+        log.info("KV env vars 未配置，使用 yaml 默认")
+        return {}
+
+    try:
+        url = (
+            f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
+            f"/storage/kv/namespaces/{namespace_id}/values/custom_config"
+        )
+        headers = {"Authorization": f"Bearer {api_token}"}
+        resp = requests.get(url, headers=headers, timeout=10)
+        if resp.status_code == 404:
+            log.info("KV 中无 custom_config，使用 yaml 默认")
+            return {}
+        resp.raise_for_status()
+        data = resp.json()
+        log.info(f"已从 KV 加载用户配置（{len(data.get('sources', []))} 个 RSS，{len(data.get('manual_topics', []))} 个关键词）")
+        return data
+    except Exception as e:
+        log.warning(f"从 KV 读配置失败：{e}")
+        return {}
+
+
+def merge_configs(default_cfg: dict, user_cfg: dict) -> dict:
+    """合并配置，KV 用户源覆盖默认源（按 name）
+    - sources: 按 name 覆盖 / 新增
+    - manual_topics: 按 name 覆盖 / 新增
+    - 其他字段保留默认
+    """
+    if not user_cfg:
+        return default_cfg
+
+    # 合并 sources
+    default_sources = {s["name"]: s for s in default_cfg.get("sources", [])}
+    for us in user_cfg.get("sources", []):
+        default_sources[us["name"]] = us
+    merged_sources = list(default_sources.values())
+
+    # 合并 manual_topics
+    default_topics = {t["name"]: t for t in default_cfg.get("manual_topics", [])}
+    for ut in user_cfg.get("manual_topics", []):
+        default_topics[ut["name"]] = ut
+    merged_topics = list(default_topics.values())
+
+    out = dict(default_cfg)
+    out["sources"] = merged_sources
+    out["manual_topics"] = merged_topics
+    log.info(f"合并后：{len(merged_sources)} 个 RSS，{len(merged_topics)} 个关键词")
+    return out
+
+
 # ============================================================
 # 2. RSS 抓取 + 图片提取
 # ============================================================
@@ -550,6 +613,11 @@
 
     config = load_config(args.config)
 
+    # v4: 尝试从 Cloudflare KV 加载用户在 admin.html 上的自定义配置（覆盖默认）
+    user_cfg = load_user_config_from_kv()
+    if user_cfg:
+        config = merge_configs(config, user_cfg)
+
     if args.monthly:
         run_monthly(config, args)
         return
