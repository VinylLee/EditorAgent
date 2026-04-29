# 项目路线图 / Project Roadmap

> 最后更新: 2026-04-29

---

## 当前进度总览

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1 — 核心管线 | ✅ 完成 | 文章写作、事实抽取、标题生成、审核、润色、封面提示词 |
| Phase 1.1 — Prompt & 审核逻辑优化 | ✅ 完成 | 事实边界强化、幻觉检测修复、分数阈值调整 |
| Phase 2 — 联网搜索 | ✅ 完成 | DashScope + Tavily + DuckDuckGo URL 回填 + 多源聚合 |
| Phase 3 — 新闻查重 & URL 增强 | 🔄 进行中 | 正文内嵌来源链接（完成）、新闻去重（规划中） |
| Phase 4 — 多模型路由 | 🔲 规划中 | 不同 Agent 使用不同模型 |
| Phase 5 — 工程化 & 部署 | 🔲 规划中 | 测试、Docker、CI |
| Phase 6 — 多模态封面 | 🔲 未开始 | AI 生成封面图 |
| Phase 7 — 产品化 | 🔲 未开始 | 定时运行、Web UI、订阅推送 |

---

## Phase 1 — 核心管线 ✅

**已完成。** 11 步自动化内容生产管线：

```
搜索 → 新闻选择 → 事实抽取 → 文章写作 → 标题生成 → 标题风控
→ 标题终选 → 审核(含重写循环) → 最终润色 → 封面提示词 → 输出
```

关键文件：[agents/workflow.py](agents/workflow.py)、[llm/prompts.py](llm/prompts.py)、[models/schemas.py](models/schemas.py)

---

## Phase 1.1 — Prompt & 审核逻辑优化 ✅

**已完成。** 修复了 review score 72 / passed=False 的问题（见 `silly-tickling-abelson` 计划）。

变更摘要：
- **prompts.py**: 删除 `【事实】/【推断】` 标记要求；新增"事实边界"段落；Review prompt 区分"事实断言 vs 观点分析"
- **review_agent.py**: `unsupported_claims` 从硬失败改为软警告；`<70` 硬失败，`70-84` 软重写；`human_check_required` 移除对 `unsupported_claims` 的引用

---

## Phase 2 — 联网搜索 ✅

**已完成。** 不再依赖手动输入新闻。

| 组件 | 文件 | 功能 |
|------|------|------|
| DashScope Provider | [search/dashscope_search.py](search/dashscope_search.py) | 阿里云 DashScope `enable_search=True`，DuckDuckGo URL 回填 |
| Tavily Provider | [search/tavily_search.py](search/tavily_search.py) | Tavily Search API（需 API key） |
| Aggregator | [search/aggregator.py](search/aggregator.py) | 多源聚合、标题去重、跨源 URL 互填、过期新闻过滤 |
| 工厂函数 | [main.py](main.py) | `--search-provider` 支持 manual/dashscope/tavily/auto |

已知限制：DashScope 自身不返回来源 URL，通过 DuckDuckGo Lite（免费、无 API key）按标题反查补全。

---

## Phase 3 — 新闻查重 & URL 增强 🔜

### 3.1 正文内嵌参考来源链接 ✅

**状态：已完成。** 文章正文现支持内嵌来源媒体名称标记，文末汇总列出所有新闻来源 URL。

**改动摘要：**
- `ArticleWriter.write()` 新增 `source_list` 参数，将所有新闻来源（含媒体名称 + URL）注入 prompt
- `ARTICLE_WRITE_PROMPT` 强化要求：正文第 1 段用《》标注来源媒体名称，如 `据《中国青年报》报道……`
- `Workflow._append_source_url()` 重写：遍历所有新闻项，去重后列出完整参考来源列表（`---` + `**参考来源：**`）
- 涉及文件：`agent/article_writer.py`、`llm/prompts.py`、`agent/workflow.py`

### 3.2 新闻查重系统

**问题：** 每次运行都会重新搜索新闻。如果连续运行（如每天自动生成），可能搜索到同一则新闻，导致内容重复。

**方案设计：**

#### 方案 A：轻量级（推荐先行）

```
本地存储：outputs/search_history.jsonl
每条记录：{title, url, source, published_at, searched_at, content_hash}
```

- **精确去重**：URL 完全相同 → 直接跳过
- **标题相似度去重**：复用 `SearchAggregator._titles_match()` 的字符+birgram 算法，相似度 > 0.8 → 视为重复
- **时间衰减**：超过 14 天的新闻即使未完全重复，也降低其"重复"判定阈值
- 每次搜索后，将本次结果 append 到 search_history.jsonl
- 在 `SearchAggregator._merge_and_dedup()` 或一个新的 `DedupFilter` 类中执行

#### 方案 B：RAG / 向量化（后续升级）

```
使用 embedding 模型（如 DashScope text-embedding-v3 或本地 bge-small-zh）
将历史新闻 title+summary 编码为向量存入本地向量库（ChromaDB / FAISS）
新搜索到的新闻同样编码，做相似度检索，阈值 > 0.85 视为重复
```

**优缺点对比：**

| 维度 | 方案 A（轻量） | 方案 B（RAG） |
|------|---------------|---------------|
| 实现复杂度 | 低，1-2 个文件 | 中，需引入 embedding 依赖 |
| 运行成本 | 零 | 嵌入 API 调用费用 |
| 对同义改写新闻 | 可能漏过 | 能捕获 |
| 对完全同标题 | 100% 命中 | 100% 命中 |
| 维护负担 | 几乎为零 | 需管向量库文件 |

**推荐路径：先实现方案 A，验证效果后再升级方案 B。**

### 3.3 实现任务清单

- [ ] **3.3.1** 新建 `search/dedup.py` — `SearchHistory` 类：读取/写入 `search_history.jsonl`，提供 `is_duplicate(news_item) -> bool`
- [ ] **3.3.2** 在 `SearchAggregator` 或 `Workflow.run()` 中调用去重，过滤已见过的新闻
- [x] **3.3.3** 在 `ArticleWriter` prompt 中强化来源标注要求（正文内嵌媒体名称）
- [x] **3.3.4** 在 `Workflow._append_source_url()` 中支持多条参考来源

---

## Phase 4 — 多模型路由 🔜

**目标：** 不同 Agent 使用不同 LLM 模型，优化成本与质量。

| Agent | 推荐模型 | 理由 |
|-------|---------|------|
| NewsSelector | qwen-max / claude-sonnet | 需要强理解力做新闻筛选 |
| FactExtractAgent | qwen-plus / deepseek-v3 | 结构化抽取，中等模型即可 |
| ArticleWriter | claude-sonnet / qwen-max | 核心创作环节，需要最强模型 |
| TitleOptimizer | qwen-plus | 标题生成为主，成本敏感 |
| TitleRiskAgent | qwen-plus | 规则性检查 |
| ReviewAgent | claude-sonnet / qwen-max | 审核需要准确判断 |
| PolishAgent | qwen-plus | 轻量润色 |
| CoverPromptGenerator | qwen-plus | 提示词生成 |

**实现方式：**
- `AppConfig` 增加 `writer_model`、`reviewer_model`、`default_model` 等字段
- `LLMClient` 支持 per-call model override
- 各 Agent 初始化时指定使用的 model name

---

## Phase 5 — 工程化 🔜

- [ ] **5.1** 单元测试覆盖核心 Agent（mock LLM 输出）
- [ ] **5.2** 集成测试：端到端用 sample_news 跑全管线
- [ ] **5.3** Docker 化：`Dockerfile` + `docker-compose.yml`
- [ ] **5.4** 配置校验：启动时检查必需 env var，给出明确错误信息
- [ ] **5.5** 日志完善：结构化日志、运行耗时统计

---

## Phase 6 — 多模态封面 🔜

- [ ] **6.1** 接入图片生成 API（DashScope 万相 / DALL-E / Stable Diffusion）
- [ ] **6.2** 根据封面提示词自动生成封面图
- [ ] **6.3** 图文混排：封面图 + 文章正文输出为公众号可发布格式

---

## Phase 7 — 产品化 🔜

- [ ] **7.1** 定时任务：每天/每周自动运行，生成最新教育新闻文章
- [ ] **7.2** Web UI：简单的管理界面，查看历史文章、手动触发生成
- [ ] **7.3** 人工审核界面：在发布前预览、编辑、确认文章
- [ ] **7.4** 微信公众号 API 对接：自动发布（需公众号认证）
- [ ] **7.5** 订阅推送：通过模板消息或客服消息通知订阅者

---

## 附录：当前项目结构

```
wechat_edu_agent/
├── main.py                 # CLI 入口
├── config.py               # 配置 dataclass + .env 加载
├── agents/
│   ├── workflow.py         # 11 步管线编排
│   ├── article_writer.py   # 文章写作 Agent
│   ├── fact_extract_agent.py  # 事实抽取 Agent
│   ├── news_selector.py    # 新闻选择 Agent
│   ├── title_optimizer.py  # 标题生成 + 终选 Agent
│   ├── title_risk_agent.py # 标题风控 Agent
│   ├── review_agent.py     # 审核 + 重写 Agent
│   ├── polish_agent.py     # 最终润色 Agent
│   ├── cover_prompt_generator.py  # 封面提示词 Agent
│   └── formatter.py        # Markdown 格式化工具
├── llm/
│   ├── client.py           # OpenAI 兼容客户端 + JSON 模式 + trace
│   ├── prompts.py          # 所有 System/User Prompt（中文）
│   └── json_schemas.py     # JSON Schema 定义
├── models/
│   └── schemas.py          # Pydantic 数据模型
├── search/
│   ├── base.py             # SearchProvider ABC
│   ├── manual_input.py     # 手动输入 Provider
│   ├── dashscope_search.py # DashScope + DuckDuckGo URL 回填
│   ├── tavily_search.py    # Tavily API Provider
│   └── aggregator.py       # 多源聚合 + 去重
├── utils/
│   ├── json_utils.py       # JSON 提取/修复
│   ├── text_utils.py       # CJK 字数统计、slugify
│   ├── file_utils.py       # 输出目录、文件写入
│   └── logger.py           # 日志
└── outputs/                # 运行输出目录
```

---

## 下一步行动（按优先级）

1. **Phase 3.2** — 新闻查重（轻量方案 A），防止重复内容
2. **Phase 4** — 多模型路由，降低 API 成本
3. **Phase 5** — 测试 + Docker，提升工程可靠性
