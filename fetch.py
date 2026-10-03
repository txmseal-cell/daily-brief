#!/usr/bin/env python3
"""
fetch.py — daily-brief 主脚本（v3，原文直存版）

核心原则：
  - 原文直存，不预翻译，不改写
  - 只做：抓取、分类、热度、关键词匹配、议题识别
  - AI 调用在 Cloudflare Functions（按需）
  - 用户在网页上点按钮才调 AI

流程：
  1. 读 config.yaml
  2. 抓 RSS（每个源按 max_items 数量）
  3. 提取图片（media:thumbnail / media:content / og:image）
  4. 简单分类（基于 source 自带 category）
  5. 计算 hot_score
  6. 识别候选议题
  7. 输出 Markdown + HTML（含「中文翻译」「归纳」按钮）
  8. 更新 facts.json / pending.json / index.html
"""

import os
import re
import sys
import json
import yaml
import hashlib
import logging
import argparse
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from html import unescape as html_unescape

from templates import (
    render_daily_html,
    render_index_html,
    render_topic_html,
    render_monthly_html,
    MARKDOWN_TEMPLATE,
    CATEGORY_SECTION_MD,
    FACT_MD,
    SOURCE_LIST_MD,
    PENDING_TOPIC_MD,
)

# ============================================================
# 日志
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("daily-brief")

BJT = timezone(timedelta(hours=8))

# ============================================================
# 1. 配置加载
# ============================================================
def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================
# 2. RSS 抓取 + 图片提取
# ============================================================
def fetch_rss(src: dict, max_age_hours: int, user_agent: str, timeout: int) -> list:
    """抓取单个 RSS 源，返回事实列表（原文）"""
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    max_items = src.get("max_items", 2)
    extract_image = src.get("extract_image", False)
    image_source = src.get("image_source", "rss")

    try:
        feed = feedparser.parse(src["url"], agent=user_agent)
    except Exception as e:
        log.warning(f"[{src['name']}] 抓取异常: {e}")
        return items

    if feed.bozo and not feed.entries:
        log.warning(f"[{src['name']}] 解析失败: {getattr(feed, 'bozo_exception', '未知')}")
        return items

    count = 0
    for entry in feed.entries[:max_items]:
        published = _parse_date(entry)
        if published and published < cutoff:
            continue

        image_url = ""
        if extract_image:
            image_url = _extract_image(entry, image_source, src, user_agent)

        items.append({
            "source": src["name"],
            "category": src.get("category", "新闻"),
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", "").strip(),
            "summary": _clean_html(entry.get("summary", entry.get("description", ""))),
            "image": image_url,
            "published": published.isoformat() if published else "",
            "published_display": published.astimezone(BJT).strftime("%Y-%m-%d %H:%M")
                if published else "未知",
            "fetched_at": datetime.now(BJT).isoformat(),
        })
        count += 1

    log.info(f"[{src['name']}] 抓到 {count} 条")
    return items


def _parse_date(entry) -> Optional[datetime]:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        v = entry.get(field)
        if v:
            try:
                return datetime(*v[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _clean_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return html_unescape(s)[:600]


def _extract_image(entry, image_source: str, src: dict, user_agent: str) -> str:
    """从 RSS 拿图：media:thumbnail > media:content > enclosure > og:image"""
    # 1. media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url", "")
    # 2. media:content
    if hasattr(entry, "media_content") and entry.media_content:
        return entry.media_content[0].get("url", "")
    # 3. enclosure
    encl = entry.get("enclosures", [])
    for e in encl:
        if e.get("type", "").startswith("image"):
            return e.get("href", e.get("url", ""))
    # 4. og:image（需要 fetch 原文，失败不影响主流程）
    if image_source == "og" and entry.get("link"):
        try:
            r = requests.get(
                entry["link"],
                headers={"User-Agent": user_agent},
                timeout=8,
                allow_redirects=True,
            )
            if r.ok:
                m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', r.text)
                if m:
                    return m.group(1)
        except Exception:
            pass
    return ""


# ============================================================
# 3. 简单关键词匹配（用于议题识别和分类调整）
# ============================================================
KEYWORD_CATEGORY_OVERRIDE = [
    # (keywords, category) — 命中时覆盖默认分类
    (["wheat", "小麦", "粮食", "玉米", "大豆", "rice", "米"], "农业"),
    (["fertilizer", "化肥", "尿素", "potash", "钾肥", "urea"], "农业"),
    (["Fed", "rate cut", "rate hike", "加息", "降息", "美联储"], "金融"),
    (["AI", "LLM", "GPT", "Claude", "agent", "智能体", "大模型"], "科技"),
    (["GPU", "NVIDIA", "TSMC", "台积电", "H100", "B200", "ASML", "半导体"], "科技"),
    (["IPO", "融资", "估值", "收购", "Series A"], "金融"),
]


def refine_category(item: dict) -> str:
    """基于标题+摘要的关键词，简单调整分类"""
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    for kws, cat in KEYWORD_CATEGORY_OVERRIDE:
        for kw in kws:
            if kw.lower() in text:
                return cat
    return item.get("category", "新闻")


# ============================================================
# 4. 热度计算
# ============================================================
def compute_hot_score(item: dict, source_weight: dict, category_weight: dict) -> int:
    """热度 = 基础分 × 来源权重 × 分类权重"""
    src_w = source_weight.get(item["source"], 5)
    cat_w = category_weight.get(item["category"], 3)
    base = 10
    score = base * src_w * cat_w / 10  # 归一化
    return int(score)


# ============================================================
# 5. 事实编号
# ============================================================
def make_fact_id(date_str: str, seq: int) -> str:
    d = date_str.replace("-", "")
    return f"F{d}-{seq:03d}"


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


# ============================================================
# 6. 议题识别（基于已有 facts.json）
# ============================================================
def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def identify_pending_topics(today_items: list, facts_index: list, config: dict) -> list:
    """
    跨来源共振 / 单来源连续 → 候选议题
    写入 pending.json
    """
    topics_cfg = config["topics"]
    cross_threshold = topics_cfg["cross_source_threshold"]
    cross_days = topics_cfg["cross_source_days"]
    single_threshold = topics_cfg["single_source_threshold"]
    single_days = topics_cfg["single_source_days"]
    manual = config.get("manual_topics", [])

    # 把 manual 关键词汇总
    manual_kws = {}  # keyword -> topic_name
    for mt in manual:
        for kw in mt.get("keywords", []):
            manual_kws[kw.lower()] = mt["name"]

    # 收集最近事实（含今日）
    all_facts = facts_index[-1000:]  # 限最近 1000 条
    today_facts_for_pending = [
        {
            "title": it.get("title", ""),
            "summary": it.get("summary", ""),
            "source": it.get("source", ""),
            "date": it.get("date", datetime.now(BJT).strftime("%Y-%m-%d")),
            "fid": it.get("fid", ""),
        }
        for it in today_items
    ]
    all_facts.extend(today_facts_for_pending)

    # 关键词聚合
    kw_to_facts = {}  # keyword -> [(source, date, fid)]
    for f in all_facts:
        text = (f.get("title", "") + " " + f.get("summary", "")).lower()
        source = f.get("source", "")
        date = f.get("date", "")
        fid = f.get("fid", "")
        for kw in manual_kws.keys():
            if kw in text:
                kw_to_facts.setdefault(kw, []).append((source, date, fid))

    # 构建候选议题
    candidates = []
    now = datetime.now(BJT)

    # 1. 手动主题：始终追踪
    for mt in manual:
        matched = []
        for kw in mt.get("keywords", []):
            matched.extend(kw_to_facts.get(kw.lower(), []))
        if matched:
            sources = set(m[0] for m in matched)
            dates = sorted(set(m[1] for m in matched), reverse=True)
            try:
                latest = datetime.strptime(dates[0], "%Y-%m-%d")
                days = (now - latest).days
            except Exception:
                days = 0
            candidates.append({
                "id": "manual-" + mt["name"],
                "topic": mt["name"],
                "keywords": mt["keywords"],
                "first_seen": dates[-1] if dates else "",
                "last_seen": dates[0] if dates else "",
                "source_count": len(sources),
                "fact_ids": list(set(m[2] for m in matched if m[2]))[:30],
                "status": "tracking",
            })

    # 2. 自动议题：跨来源共振 / 单来源连续
    # 从 facts.json 已有 fact 中按"高频"提取（先用 top 关键词扫描）
    high_freq = {}
    for f in all_facts:
        text = (f.get("title", "") + " " + f.get("summary", "")).lower()
        source = f.get("source", "")
        date = f.get("date", "")
        fid = f.get("fid", "")
        # 提取 ≥2 字的关键词
        for word in _extract_keywords(text):
            high_freq.setdefault(word, []).append((source, date, fid))

    for word, items in high_freq.items():
        if len(items) < single_threshold:
            continue
        sources = set(i[0] for i in items)
        dates = sorted(set(i[1] for i in items), reverse=True)
        try:
            latest = datetime.strptime(dates[0], "%Y-%m-%d")
            days = (now - latest).days
        except Exception:
            continue

        if (len(sources) >= cross_threshold and days <= cross_days) or \
           (len(items) >= single_threshold and days <= single_days):
            # 避免和 manual 重复
            if word in manual_kws:
                continue
            candidates.append({
                "id": "auto-" + hashlib.md5(word.encode()).hexdigest()[:10],
                "topic": word,
                "keywords": [word],
                "first_seen": dates[-1],
                "last_seen": dates[0],
                "source_count": len(sources),
                "fact_ids": list(set(i[2] for i in items if i[2]))[:30],
                "status": "pending",
            })

    # 合并到 pending.json
    pending_path = "data/pending.json"
    pending = load_json(pending_path, [])
    existing_ids = {p.get("id"): p for p in pending}

    final = []
    for c in candidates:
        if c["id"] in existing_ids:
            # 更新已有
            old = existing_ids[c["id"]]
            old["last_seen"] = c["last_seen"]
            old["source_count"] = max(old.get("source_count", 0), c["source_count"])
            old["fact_ids"] = list(set((old.get("fact_ids", []) + c["fact_ids"])))[:50]
            final.append(old)
        else:
            final.append(c)

    save_json(pending_path, final)
    log.info(f"pending.json: {len(final)} 个议题")
    return final


# 简单的关键词提取（去掉停用词 + 长度≥3）
STOPWORDS = set("""
the a an and or but if then else is are was were be been being have has had do does did
will would should could may might must can could to of in for on with at by from as this that
these those it its we our you your they them their he she his her which who what when where why how
""".split())


def _extract_keywords(text: str) -> list:
    words = re.findall(r"[a-zA-Z\u4e00-\u9fff]{3,}", text)
    return [w for w in words if w.lower() not in STOPWORDS]


# ============================================================
# 7. 归档处理
# ============================================================
def archive_old_pending(pending: list, archive_days: int) -> list:
    """超过 N 天的 pending 议题，标记为 archived"""
    now = datetime.now(BJT)
    for p in pending:
        if p.get("status") == "archived":
            continue
        try:
            last = datetime.strptime(p.get("last_seen", "1970-01-01"), "%Y-%m-%d")
            if (now - last).days > archive_days:
                p["status"] = "archived"
        except Exception:
            pass
    return pending


# ============================================================
# 8. 输出 Markdown
# ============================================================
def render_markdown(date: str, items: list, pending_topics: list, facts_index: list) -> str:
    # 1. 分类要点
    by_cat = {}
    for it in items:
        by_cat.setdefault(it.get("category", "其他"), []).append(it)

    cat_sections = []
    for cat in ["农业", "经济", "金融", "科技", "政治", "军事", "娱乐", "社会", "新闻"]:
        if cat not in by_cat:
            continue
        facts_md = []
        for it in by_cat[cat]:
            facts_md.append(FACT_MD.format(
                fid=it["fid"],
                source=it.get("source", ""),
                published=it.get("published_display", ""),
                original_title=it.get("title", ""),
                url=it.get("url", "#"),
                summary=it.get("summary", "")[:300],
                image=it.get("image", ""),
                hot=it.get("hot_score", 0),
            ))
        cat_sections.append(CATEGORY_SECTION_MD.format(
            category=cat, count=len(by_cat[cat]), facts="\n".join(facts_md)
        ))
    category_sections = "\n".join(cat_sections) if cat_sections else "_今日无分类要点_"

    # 2. 来源列表
    source_count = {}
    for it in items:
        source_count[it.get("source", "未知")] = source_count.get(it.get("source", "未知"), 0) + 1
    source_list = "\n".join(SOURCE_LIST_MD.format(source=s, count=c)
                            for s, c in sorted(source_count.items(), key=lambda x: -x[1]))

    # 3. 候选议题
    active = [t for t in pending_topics if t.get("status") != "archived"]
    pending = "\n".join(PENDING_TOPIC_MD.format(
        topic=t.get("topic", ""),
        heat=t.get("source_count", 0),
        first_seen=t.get("first_seen", ""),
        last_seen=t.get("last_seen", ""),
        source_count=t.get("source_count", 0),
        fact_count=len(t.get("fact_ids", [])),
        status=t.get("status", "pending"),
    ) for t in active[:15]) or "_今日无新候选议题_"

    return MARKDOWN_TEMPLATE.format(
        date=date,
        generated_at=datetime.now(BJT).strftime("%Y-%m-%d %H:%M"),
        fact_count=len(items),
        source_count=len(source_count),
        category_sections=category_sections,
        source_list=source_list,
        pending_topics=pending,
        active_topic_count=len(active),
    )


# ============================================================
# 9. Facts 索引维护
# ============================================================
def append_facts(path: str, items: list, date: str):
    index = load_json(path, [])
    existing_hashes = {f.get("url_hash") for f in index}
    added = 0
    for it in items:
        h = url_hash(it["url"])
        if h in existing_hashes:
            continue
        # 关联 manual_topics
        text = (it.get("title", "") + " " + it.get("summary", "")).lower()
        topics = []
        for mt in []:  # 由调用方传 config
            pass
        index.append({
            "id": it["fid"],
            "url_hash": h,
            "url": it["url"],
            "date": date,
            "source": it.get("source", ""),
            "category": it.get("category", ""),
            "title": it.get("title", ""),       # 原文标题
            "summary": it.get("summary", ""),   # 原文摘要
            "image": it.get("image", ""),
            "published": it.get("published", ""),
            "fetched": it.get("fetched_at", ""),
            "hot_score": it.get("hot_score", 0),
            "topics": it.get("topics", []),
        })
        existing_hashes.add(h)
        added += 1
    save_json(path, index)
    log.info(f"facts.json 新增 {added} 条，总计 {len(index)} 条")
    return index


def tag_topics(items: list, config: dict) -> list:
    """给每条事实打上主题标签（基于 manual_topics 关键词）"""
    manual = config.get("manual_topics", [])
    for it in items:
        text = (it.get("title", "") + " " + it.get("summary", "")).lower()
        tags = []
        for mt in manual:
            for kw in mt.get("keywords", []):
                if kw.lower() in text:
                    tags.append(mt["name"])
                    break
        it["topics"] = tags
    return items


# ============================================================
# 10. Index 维护
# ============================================================
def update_index(archive_dir: str, facts_path: str, out_path: str):
    entries = []
    for p in sorted(Path(archive_dir).glob("*.html"), reverse=True):
        entries.append((p.stem, p.stem))
    facts = load_json(facts_path, [])
    search_index = [{
        "id": f.get("id", ""),
        "title": f.get("title", ""),
        "summary": f.get("summary", ""),
        "source": f.get("source", ""),
        "category": f.get("category", ""),
        "date": f.get("date", ""),
        "url": f.get("url", ""),
    } for f in facts]
    html = render_index_html(entries, search_index)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info(f"index.html 已更新，{len(entries)} 天，{len(search_index)} 条可搜")


# ============================================================
# 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--date", default=None, help="覆盖日期（测试用）")
    parser.add_argument("--archive-dir", default="archive")
    parser.add_argument("--facts", default="data/facts.json")
    parser.add_argument("--pending", default="data/pending.json")
    parser.add_argument("--index", default="index.html")
    parser.add_argument("--limit", type=int, default=None, help="限制源数量（测试用）")
    parser.add_argument("--monthly", action="store_true", help="生成月度总结")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.monthly:
        run_monthly(config, args)
        return

    today = args.date or datetime.now(BJT).strftime("%Y-%m-%d")
    log.info(f"日期: {today}")

    # 1. 抓 RSS
    sources = config["sources"]
    if args.limit:
        sources = sources[:args.limit]
    log.info(f"开始抓取 {len(sources)} 个 RSS 源")

    all_items = []
    for src in sources:
        items = fetch_rss(
            src,
            config["fetch"]["max_age_hours"],
            config["fetch"]["user_agent"],
            config["fetch"]["timeout_seconds"],
        )
        all_items.extend(items)

    log.info(f"共抓到 {len(all_items)} 条原文事实")

    if not all_items:
        log.warning("今天没抓到任何内容")
        return

    # 2. 简单分类（关键词覆盖）+ 主题标签
    for it in all_items:
        it["category"] = refine_category(it)
    all_items = tag_topics(all_items, config)

    # 3. 编号 + 热度
    for i, it in enumerate(all_items, 1):
        it["fid"] = make_fact_id(today, i)
        it["hot_score"] = compute_hot_score(
            it,
            config["hot_rules"]["source_weight"],
            config["hot_rules"]["category_weight"],
        )

    # 4. 排序：高热度优先
    all_items.sort(key=lambda x: x.get("hot_score", 0), reverse=True)

    # 5. 议题识别
    facts_index = load_json(args.facts, [])
    pending_topics = identify_pending_topics(all_items, facts_index, config)
    pending_topics = archive_old_pending(pending_topics, config["topics"]["pending_archive_days"])
    save_json(args.pending, pending_topics)

    # 6. 追加 facts
    facts_index = append_facts(args.facts, all_items, today)

    # 7. 输出 Markdown
    os.makedirs(args.archive_dir, exist_ok=True)
    md = render_markdown(today, all_items, pending_topics, facts_index)
    md_path = os.path.join(args.archive_dir, f"{today}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    log.info(f"已生成 {md_path}")

    # 8. 输出 HTML
    by_cat = {}
    source_count = {}
    for it in all_items:
        by_cat.setdefault(it.get("category", "其他"), []).append(it)
        source_count[it.get("source", "")] = source_count.get(it.get("source", ""), 0) + 1
    source_summary = sorted(source_count.items(), key=lambda x: -x[1])

    # 7 天内其他事实链接
    recent_facts = [f for f in facts_index if f.get("date") and f.get("date") >= (datetime.now(BJT) - timedelta(days=7)).strftime("%Y-%m-%d")]

    html = render_daily_html(today, {
        "by_category": by_cat,
        "source_summary": source_summary,
        "pending_topics": [t for t in pending_topics if t.get("status") != "archived"][:15],
        "fact_count": len(all_items),
        "source_count": len(source_count),
        "date": today,
        "generated_at": datetime.now(BJT).strftime("%Y-%m-%d %H:%M"),
        "recent_facts": recent_facts[:30],
    })
    html_path = os.path.join(args.archive_dir, f"{today}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info(f"已生成 {html_path}")

    # 9. 更新 index
    update_index(args.archive_dir, args.facts, args.index)

    log.info("✅ 全部完成")


def run_monthly(config: dict, args):
    """生成月度总结（每月 1 号跑）"""
    log.info("生成月度总结")
    # TODO: 完整月度逻辑（统计 + LLM 总结）
    # 占位：先记录
    today = datetime.now(BJT)
    month_str = today.strftime("%Y-%m")
    out = f"archive/monthly/{month_str}.md"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# {month_str} 月度总结\n\n_待生成，请点击网页上「生成月度总结」按钮。_\n")
    log.info(f"已生成占位 {out}")


if __name__ == "__main__":
    main()
