# daily-brief

> 每天自动抓全球 70+ 主流信源，**原文直存**，按需 AI 翻译和归纳。
> 手机、电脑都能看，历史可搜，事实可追溯，议题可升级。

---

## 一句话总结

> 原文直存，按需翻译，按需归纳，月度总结。
> AI 只在需要时介入。系统负责发现和整理，你负责判断和决策。
> 事实可追溯，推演标清楚，议题你确认。

---

## 核心设计

| 阶段 | 谁做 | 用什么 | 何时运行 |
|---|---|---|---|
| **抓取** | GitHub Actions | feedparser | 每天 8:00 |
| **分类 / 热度 / 议题** | GitHub Actions | 规则 + 关键词 | 每天 8:00 |
| **AI 翻译** | Cloudflare Function | DeepSeek | 用户点「中文翻译」按钮 |
| **AI 归纳** | Cloudflare Function | DeepSeek | 用户点「归纳」按钮 |
| **主题归纳** | Cloudflare Function | DeepSeek | 用户点「归纳这个主题」按钮 |
| **月度总结** | GitHub Actions + Cloudflare Function | DeepSeek | 每月 1 号 + 用户点按钮 |

**关键原则：**
- 抓取阶段**不调 AI**（省成本）
- AI 只在用户**点击按钮时**才调用
- 原文是事实，AI 不碰原文，只在用户主动请求时翻译/归纳
- 每月 1 号跑月度总结，AI 生成报告归档

---

## 部署（5 步）

### 第 1 步：建 GitHub repo

- 名字：`daily-brief`
- 公开或私有都行

### 第 2 步：上传代码

把整个 `daily-brief/` 目录上传到 repo。

### 第 3 步：配 GitHub Secrets

进入 repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Name | Value | 必需 |
|---|---|---|
| `MINIMAX_API_KEY` | 你的 MiniMax Key（[获取](https://api.minimaxi.com/)） | **是** |
| `DEEPSEEK_API_KEY` | 你的 DeepSeek Key（[获取](https://platform.deepseek.com/)） | 否（备用） |

> 抓取阶段不调 AI，所以 GitHub Actions 上可以**暂时不配**任何 Key。
> 但 Cloudflare Pages 那边的 `MINIMAX_API_KEY` **必须配**，否则按钮点了没反应。

### 第 4 步：手动测试

进入 repo → **Actions** → **daily-brief-daily** → **Run workflow** → 点绿色按钮

等待 1-3 分钟，看是否成功生成 `archive/2026-09-12.md` 和 `.html`。

### 第 5 步：部署 Cloudflare Pages

1. 登录 [Cloudflare](https://dash.cloudflare.com/)
2. **Workers & Pages** → **Create** → **Pages** → **Connect to Git**
3. 选择 `daily-brief` repo
4. **Build settings**：
   - Framework preset：**None**
   - Build command：留空
   - Build output directory：**`/`**（如报错填 `.`）
5. **Save and Deploy**

部署成功后访问 `https://daily-brief.pages.dev`。

### 第 6 步：配 Cloudflare 环境变量

进入 Cloudflare Pages → 你的项目 → **Settings** → **Environment variables** → **Add**

| Variable name | Value |
|---|---|
| `MINIMAX_API_KEY` | **必需**，主用 LLM |
| `DEEPSEEK_API_KEY` | 可选，备用 LLM |
| `REPO_URL` | （可选）`https://raw.githubusercontent.com/你的用户名/daily-brief/main`，月度 Function 用 |

> **`MINIMAX_API_KEY` 必需**：配完才能用页面上的「中文翻译」「归纳」按钮。

---

## 本地运行

```bash
pip install -r requirements.txt

# 抓取（不调 AI，可选配）
export MINIMAX_API_KEY=xxx  # 主用，AI 调用时需要
export DEEPSEEK_API_KEY=sk-xxx  # 可选，备用
python fetch.py --limit 5  # 测试只跑前 5 个源
```

参数：
- `--limit N`：限制抓取源数量
- `--date YYYY-MM-DD`：覆盖日期（测试用）
- `--monthly`：生成月度总结占位（实际生成走 Function）

---

## 使用流程

### 日常看新闻

1. 打开 `https://daily-brief.pages.dev`
2. 点击今天日期进入简报
3. 默认显示**英文原文**
4. 想看中文 → 点「中文翻译」按钮（每次调用 DeepSeek）
5. 想看分析 → 点「归纳」按钮（每次调用 DeepSeek）

### 找历史新闻

- 首页搜索框：搜关键词 / 日期 / 事实编号
- 离线可用，数据在 `data/facts.json` 里

### 升级候选议题为主线主题

1. 看候选议题列表
2. 选感兴趣的（如「小麦」「化肥」）
3. 手动编辑 `config.yaml` 的 `manual_topics`
4. 下次跑抓取时自动追踪

### 升级后回填时间线

用户升级议题后，编辑 `topics/主题名-2026.md` 写一个手动维护，或等我们做下个版本的自动回填功能（v4）。

### 每月总结

- 自动：每月 1 号 GitHub Actions 跑 `monthly.yml`
- 手动：访问 `archive/monthly/YYYY-MM.html`，点「生成月度总结」按钮

---

## 项目结构

```
daily-brief/
├── .github/workflows/
│   ├── daily.yml                    # 每天 8:00 抓取
│   └── monthly.yml                  # 每月 1 号总结
├── functions/api/
│   ├── translate.js                 # 单条翻译
│   ├── summarize.js                 # 单条归纳
│   ├── topic.js                     # 主题归纳
│   └── monthly.js                   # 月度总结
├── archive/
│   ├── YYYY-MM-DD.md                # 每日 Markdown
│   ├── YYYY-MM-DD.html              # 每日 HTML
│   └── monthly/YYYY-MM.html         # 月度 HTML
├── topics/                          # 主题档案（手动维护）
├── timeline/                        # 议题时间线（手动维护）
├── data/
│   ├── facts.json                   # 事实索引
│   └── pending.json                 # 候选议题
├── config.yaml                      # 信源 + 关键词 + 议题规则
├── fetch.py                         # 抓取主脚本
├── templates.py                     # HTML 模板
├── search.js                        # 客户端搜索
├── requirements.txt
└── README.md
```

---

## 事实编号规则

每条事实：`FYYYYMMDD-NNN`，例：`F20260912-001`

`F` 前缀 + 日期 + 序号（三位数）。这是引用事实的"身份证号"。

推演示例：
```
[推演] 小麦减产可能推高面包价格。
依据：F20260912-001、F20260912-005
置信度：中
信息缺口：缺少库存数据，待核实
```

---

## 议题识别规则

**自动**：
- 跨来源共振：3 个来源 / 7 天内提到同一关键词
- 单来源连续：3 次 / 30 天内同一关键词
- 自动入 `data/pending.json`，30 天后归档

**手动**：
- 编辑 `config.yaml` 的 `manual_topics`
- 始终追踪，不会归档
- 升级后回填到 `topics/主题名-2026.md`（v4 实现自动回填）

---

## 成本估算

| 项 | 每次 | 频次 | 月费用 |
|---|---|---|---|
| 抓取（无 AI） | $0 | 每天 | $0 |
| 翻译（按点击） | ~0.001 元/次 | 用户决定 | 看点击量 |
| 归纳（按点击） | ~0.002 元/次 | 用户决定 | 看点击量 |
| 主题归纳 | ~0.05 元/次 | 用户决定 | 看点击量 |
| 月度总结 | ~0.1 元/次 | 每月 1 次 | ~0.1 元 |
| **总计** | | | **几元/月，看你用多少** |

如果你每天点 20 次翻译 + 5 次归纳，月费用约 2-3 元。

---

## 常见问题

### Actions 失败：`MINIMAX_API_KEY not set`

→ GitHub Secrets 没配 / Secrets 名字写错 / 抓取阶段不调 AI 所以可以暂时不配

### 翻译按钮没反应

→ Cloudflare Pages 的环境变量没配 `MINIMAX_API_KEY`
→ 或 Key 无效
→ 或超过 Free plan 限额（每天 10 万次请求）

### RSS 源失效

→ 编辑 `config.yaml` 删掉失效源或换 URL
→ commit 后 GitHub Actions 下次跑就用新配置

### 添加新主题

→ 编辑 `config.yaml` 的 `manual_topics`
→ 加一条 `- name: 主题名 / keywords: [关键词1, 关键词2]`

### 想要更多信源

→ 编辑 `config.yaml` 的 `sources`
→ 加一条 `- name: 显示名 / url: RSS链接 / category: 分类 / max_items: 2`

### 月度总结没数据

→ 第一次部署跑还没积累够事实
→ 至少跑 1 天 daily workflow 后再点月度总结

### 想看 Google Analytics 统计

→ 暂不支持（v4 加）

---

## 安全 & 隐私

- API Key 只存在 GitHub Secrets 和 Cloudflare 环境变量
- 代码不硬编码任何 Key
- 仓库可私有，不公开也能用
- 所有数据在 Git 历史里
- 不依赖任何第三方服务器（除 GitHub + Cloudflare + DeepSeek）

---

## 致谢

信源致谢各新闻机构。所有内容版权归原作者所有，本项目只做抓取与整理。
