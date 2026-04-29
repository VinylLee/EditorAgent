# wechat_edu_agent — 教育最前沿 · AI 公众号内容生产系统

自动化的微信公众号内容生产 Agent，专为教育类公众号 **「教育最前沿」** 设计。

支持**联网搜索**（DashScope / Tavily）和**手动输入**两种方式获取新闻素材，通过 LLM 流水线自动完成选题判断、事实提取、文章撰写、标题优化、风险审查、质量审核与封面图提示词生成。

## 项目结构

```
main.py                    # CLI 入口，参数解析，Provider 工厂
config.py                  # .env → AppConfig 配置加载
agents/
  workflow.py              # 流水线编排器（核心）
  news_selector.py         # LLM 选题评分
  fact_extract_agent.py    # 事实提取
  article_writer.py        # 文章撰写
  title_optimizer.py       # 标题生成与选择
  title_risk_agent.py      # 标题风控
  review_agent.py          # 质量审核与重写
  polish_agent.py          # 最终润色
  cover_prompt_generator.py# 封面图提示词
  formatter.py             # Markdown 格式化
llm/
  client.py                # OpenAI 兼容客户端（支持 JSON 模式与 LLM 追踪）
  prompts.py               # 全部系统提示词
  json_schemas.py          # JSON schema 定义
models/
  schemas.py               # Pydantic 数据模型
search/
  base.py                  # SearchProvider 抽象基类
  manual_input.py          # 手动新闻输入
  dashscope_search.py      # DashScope 联网搜索（通义千问 enable_search）
  tavily_search.py         # Tavily Search API 搜索
  aggregator.py            # 多源聚合、去重、降级
utils/
  json_utils.py            # JSON 容错解析与修复
  text_utils.py            # 中文字数统计、slugify
  file_utils.py            # 输出目录与文件写入
  logger.py                # 日志记录器
outputs/                   # 运行输出（按时间戳分目录）
```

## 环境要求

- **Python 3.11+**
- **LLM API**：任意 OpenAI-compatible 接口（已测试：DeepSeek、DashScope）
- **搜索 API（可选）**：DashScope API Key（联网搜索）/ Tavily API Key（搜索 API）
- 依赖包：`openai`、`python-dotenv`、`pydantic`（Tavily 需额外安装 `requests`）

## 快速开始

### 1. 创建环境

```bash
conda create -n agent311 python=3.11
conda activate agent311
pip install openai python-dotenv pydantic
```

### 2. 配置 .env

```bash
cp .env.example .env
```

编辑 `.env`，最少需要配置 LLM：

```ini
# 必填：LLM API
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-your_key_here
LLM_MODEL=deepseek-chat

# 可选：搜索（不配则只能手动输入新闻）
SEARCH_PROVIDER=auto
DASHSCOPE_API_KEY=sk-your_dashscope_key
# TAVILY_API_KEY=tvly-your_tavily_key

# 可选
OUTPUT_DIR=outputs
LLM_TEMPERATURE=0.7
```

### 3. 运行

```bash
# 联网搜索模式（需配好搜索 API Key）
python main.py run --search-provider auto --topic "教育内卷"

# 手动输入模式（无需搜索 API）
python main.py run --manual-news ./news/sample_news.txt
```

## CLI 参数详解

```
python main.py run [OPTIONS]
```

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--manual-news` | 否 | — | 手动新闻文件路径，传入后忽略 `--search-provider` |
| `--search-provider` | 否 | `.env` 中的 `SEARCH_PROVIDER` | `manual` / `dashscope` / `tavily` / `auto` |
| `--topic` | 否 | `教育内卷` | 搜索关键词，同时用作输出目录名 |
| `--news-type` | 否 | `社会事件` | `教育部政策` / `学校案例` / `社会事件` |

**默认行为**：如果不传任何参数，程序使用 `.env` 中 `SEARCH_PROVIDER=manual`，报错提示你提供 `--manual-news` 文件。要启用联网搜索，将 `SEARCH_PROVIDER` 设为 `auto` / `dashscope` / `tavily` 并配好对应 API Key。

## 运行示例

### 联网搜索

```bash
# DashScope 联网搜索（通义千问自动搜索网页并整合新闻）
python main.py run --search-provider dashscope --topic "高考改革"

# Tavily 搜索 API
python main.py run --search-provider tavily --topic "减负政策"

# 自动模式（DashScope + Tavily 串联，任一成功即可）
python main.py run --search-provider auto --topic "教育内卷"

# 指定新闻类型偏好
python main.py run --search-provider auto --topic "教育内卷" --news-type "学校案例"
```

### 手动输入

```bash
# 最简单用法
python main.py run --manual-news ./news/sample_news.txt

# 指定主题和类型
python main.py run --manual-news ./news/sample_news.txt \
    --topic "减负 内卷" \
    --news-type "社会事件"
```

### 降级策略

```
--manual-news 传入？
  ├─ 是 → 使用 ManualNewsProvider（本地文件）
  └─ 否 → 检查 --search-provider：
           ├─ dashscope → DashScope 联网搜索
           ├─ tavily    → Tavily Search API
           ├─ auto      → DashScope → Tavily 依次尝试
           └─ manual    → 报错：请提供 --manual-news 或切换 Provider
```

## 工作流详解（11 步）

整个流水线由 [agents/workflow.py](agents/workflow.py) 中的 `Workflow.run()` 编排。每一步的输出都是下一步的输入。

### 步骤 1：搜索 — 获取新闻素材

```
provider.search(topic, news_type, limit=5) → SearchResult
```

根据 `--search-provider` 调用对应的 Provider：

| Provider | 数据来源 | 返回内容 |
|----------|---------|---------|
| ManualNewsProvider | 本地 .txt 文件 | 文件全文 → 1 个 NewsItem |
| DashScopeSearchProvider | 通义千问联网搜索 | LLM 整合的新闻 → 1~5 个 NewsItem |
| TavilySearchProvider | Tavily Search API | 结构化搜索结果 → 若干 NewsItem |
| SearchAggregator | 多 Provider 串联 | 去重合并后的结果 |

返回 `SearchResult`，包含 `items`（NewsItem 列表）和 `raw_text`（新闻全文）。
结果保存到 `search_result.json`。

### 步骤 2：选题判断 — 选择最佳新闻

```
NewsSelector.select(search_result.items) → NewsSelectionResult
```

LLM 从候选新闻中选择最适合写成公众号文章的一条，同时生成：

- `selected_news`：选中的 NewsItem
- `suggested_article_angle`：文章切入角度（如"减负背后的资源不平等"）
- `parent_emotion_points`：家长情绪触点（如"焦虑""失控感"）
- `deep_logic_angles`：深层逻辑角度

### 步骤 3：事实提取 — 拆解可验证信息

```
FactExtractAgent.extract(search_result.raw_text) → FactExtractResult
```

LLM 从 `raw_text` 中抽取：

- `verified_facts`：可验证的具体事实（含 evidence 原文出处）
- `verified_numbers`：数字类信息（时间、比例、人数等）
- `verified_quotes`：直接引语（含说话人）
- `allowed_inferences`：基于事实的合理推断
- `forbidden_claims`：禁止后续写作中编造的内容

**这份结果是后续写作和审核的唯一事实来源。**值得注意的是，LLM编写文章并非只基于选中的NewsItem，而是从其出发，涉及所有NewsItem

### 步骤 4：文章撰写 — 生成草稿

```
ArticleWriter.write(selected, raw_text, fact_extract, article_angle) → 文章 Markdown
```

LLM 基于以下输入撰写 1200-1800 字文章：

| 输入 | 作用 |
|------|------|
| `selected` (NewsItem JSON) | 选题聚焦——写哪条新闻 |
| `fact_extract` (FactExtractResult JSON) | 事实边界——只能用这些事实 |
| `article_angle` | 叙事角度——从什么视角切入 |
| `raw_text` | 背景素材——补充上下文 |

文章结构：新闻事件（约 100 字，含来源和日期）→ 反常识问题 → 表面现象 → 深层逻辑（教育学/社会学/升学竞争/家庭资源）→ 家长焦虑点 → 3 条具体建议 → 有力结尾。

### 步骤 5：标题生成 — 生成 10 个候选

```
TitleOptimizer.generate_titles(article) → List[TitleCandidate]
```

LLM 生成 10 个标题，每个标题附带 score（0-100）、reason 和 risk 评估。
要求：强情绪、反常识、面向家长、不低俗不造谣。

### 步骤 6：标题风控 — 安全分类

```
TitleRiskAgent.assess(titles, article, fact_extract) → TitleRiskResult
```

LLM 对标题进行风险评估，分为：
- `safe_titles`：未命中高风险规则的标题
- `risky_titles`：命中高风险规则的标题（含 risk_level 和 suggested_fix）
- `recommended_title`：从 safe 中推荐的最佳标题

高风险规则：含未证实数字、绝对化结论、推断写成事实、制造恐慌、编造场景。

### 步骤 7：标题选择 — 确定最终标题

```
TitleOptimizer.select_title(safe_titles, article) → TitleSelection
```

LLM 从安全标题中选出最适合发布的一个，给出选择理由和优化说明。

### 步骤 8：审核 ↔ 重写循环（最多 3 轮）

```
while review_round <= 3:
    ReviewAgent.review(article, fact_extract, title_risk, raw_text) → ReviewResult
    if not rewrite_required: break
    ReviewAgent.rewrite(article, review, fact_extract, raw_text) → 修正后文章
```

每轮审核检查：
- 是否存在事实编造（hallucination_risks）
- 是否有无法验证的事实断言（unsupported_claims）
- 标题风险、字数是否合格、结构是否完整
- 是否像空话/鸡汤/政策宣传腔

审核规则：
- 存在 hallucination_risks → `passed=False`（硬失败）
- 分数 <70 → 硬失败
- 分数 70-84 → `rewrite_required=True`（软重写）
- 分数 ≥85 → 通过

### 步骤 9：最终润色 — 去标记、优化节奏

```
PolishAgent.polish(title, article, fact_extract) → 润色后文章
```

- 去除残存格式标记和提示词痕迹
- 优化语句节奏，适配手机阅读
- 不新增任何事实、数字、人物、引语

### 步骤 10：封面提示词 — 生成封面图 prompt

```
CoverPromptGenerator.generate(title, article) → CoverPrompt
```

生成中英文封面图提示词，含负向提示词和布局建议。

### 步骤 11：输出 — 写入文件

文章末尾自动附加所有新闻来源 URL（去重后汇总列出）。正文第 1 段要求用《》标注来源媒体名称。所有输出写入 `outputs/YYYYMMDD_HHMM_<topic>/`：

| 文件 | 内容 |
|------|------|
| `search_result.json` | 搜索到的原始新闻（NewsItem 列表 + 全文） |
| `article.md` | 审核前的原始草稿 |
| `final_article.md` | 润色后的最终文章（含来源 URL） |
| `fact_extract.json` | 事实提取结果（验证事实/数字/引语/推断） |
| `titles.json` | 10 个候选标题 + 最终选择 |
| `title_risk.json` | 标题风险评估（安全/风险分类） |
| `review.json` | 质量审核报告（评分/幻觉风险/问题列表） |
| `cover_prompt.md` | 封面图提示词（中英文） |
| `report.md` | 运行报告（含评分、字数、标题风险数等） |
| `llm_trace.jsonl` | 所有 LLM 调用追踪（含 prompt/response/timestamp） |

## 关键设计决策

- **搜索可插拔**：`SearchProvider` ABC，已实现 DashScope / Tavily / Manual 三种 Provider，支持 auto 多源聚合
- **事实锚定**：事实提取结果是写作和审核的单一事实来源（Single Source of Truth），Review 区分"事实断言"与"观点分析"，防止误报
- **审核分级**：<70 硬失败 → 70-84 软重写 → ≥85 通过；仅 hallucination_risks（具体事实编造）触发硬失败，unsupported_claims 降级为软警告
- **来源追溯**：正文第 1 段要求标注来源媒体名称（用《》标出），文末汇总列出所有新闻来源 URL，确保可溯源和多源透明
- **JSON 容错**：每轮 LLM JSON 输出均有多层回退：解析 → 修复 → 默认值
- **LLM 追踪**：所有调用记录到 `llm_trace.jsonl`，包含完整 prompt/response/timestamp，便于调试和成本分析
