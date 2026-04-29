你是一名资深 Python 全栈工程师和 AI Agent 架构师。请帮我生成一个完整的自动化内容生产 Agent 项目，项目目标是：为微信公众号“教育最前沿”自动完成教育新闻选题、新闻抓取、事实整理、观点生成、公众号文章撰写、标题优化、封面图提示词生成和 Markdown 排版。

一、项目背景

公众号名称：教育最前沿

公众号定位：
拆解“减负”与“内卷”背后的残酷规则。
拒绝空话，只提供理性、可执行的升学决策。
在这里，看懂教育竞争的真实牌局。
别让你的信息差，成为孩子人生的天花板。

核心主题：
高考竞争 + 教育内卷，尤其关注“减负 vs 内卷”的冲突。

目标读者：
一线城市中产家长，孩子年龄 6-18 岁。
文章要能触发家长焦虑、共鸣和思考，但不要制造无意义恐慌。

内容风格：
1. 理性但有冲击力。
2. 不空话。
3. 有明确观点。
4. 能给家长提供实际、可执行的教育决策建议。
5. 不要鸡汤，不要泛泛而谈。
6. 文章适合微信公众号发布。

文章字数：
1200-1800 中文字。

二、核心工作流

请实现如下自动化流程：

新闻抓取与选题判断 → 新闻事实整理 → 观点生成 → 文章写作 → 标题生成 → 标题选择与优化 → 公众号排版 → 封面图提示词生成 → 输出最终文件

具体流程如下：

1. 新闻抓取与选题判断

Agent 需要从以下三类新闻中随机选择一个类型进行新闻检索：

A. 教育部政策
B. 学校案例
C. 社会事件，例如家长冲突、补课、升学焦虑、校园管理事件等

筛选新闻的标准：
1. 新闻必须与教育、升学、高考竞争、减负、内卷、家庭教育、学生压力、补课、学校管理等主题相关。
2. 新闻必须能够产生家长情绪共鸣，引发家长焦虑或思考。
3. 新闻必须和高考竞争、教育内卷、减负政策或升学路径有关。
4. 优先选择最近 7 天内的中文新闻。
5. 优先选择权威来源，例如教育部、地方教育局、新华社、人民网、中国教育在线、澎湃新闻、央视新闻、地方官方媒体等。
6. 如果搜不到最近 7 天合适新闻，可以放宽到最近 30 天，但必须在输出中说明。

新闻检索接口设计：
请将新闻检索做成可替换模块，支持以下 provider：
1. DashScope / 通义千问联网搜索，调用时支持 enable_search=True。
2. Gemini Grounding with Google Search，可选。
3. 自定义搜索 API，例如 Search1API、Tavily、SerpAPI 或其他搜索接口。
4. 如果没有配置联网 API，则允许用户手动输入新闻素材。

请不要把搜索逻辑写死在主流程中，要设计成 SearchProvider 抽象类或统一接口。

新闻抓取结果需要包含：
- news_type：新闻类型，三选一
- title：新闻标题
- source：新闻来源
- published_at：发布时间
- url：新闻链接
- summary：100-300 字摘要
- core_facts：核心事实列表
- parent_emotion_points：家长焦虑点列表
- relevance_score：与公众号定位的相关度，0-100
- virality_score：适合公众号传播的潜力，0-100
- reason：为什么选择这条新闻

2. 选题判断

请让 Agent 对候选新闻做评分，评分维度包括：
- 与高考竞争/内卷相关度
- 是否能引发家长共鸣
- 是否有冲突感
- 是否能引出深层教育逻辑
- 是否能给出可执行建议
- 是否适合写成公众号文章

最后选出一条新闻作为本期文章主题。

3. 观点生成与文章写作

文章必须严格采用以下结构：

标题：
由后续标题模块生成，文章模块先可使用临时标题。

正文结构：

第一部分：新闻事件，约 100 字
要求：
简洁交代新闻发生了什么。
包括新闻来源、时间、地点、核心事实。
不要加入过多评论。

第二部分：引出一个反常识问题
要求：
不要只是说“家长很焦虑”。
要提出一个有冲击力的问题。
例如：
“为什么学校减负了，家长反而更焦虑？”
“为什么孩子少上了晚自习，家长却不敢松一口气？”
“为什么越强调公平，家长越害怕掉队？”

第三部分：表面现象
要求：
解释大众看到的表层现象。
例如：
学校规范办学、减少补课、延迟上学、控制作业、取消周末补课等。
但不要停留在政策宣传层面。

第四部分：深层逻辑
要求：
从教育学、社会学、升学竞争、资源分配、家庭策略等角度分析。
必须解释为什么会这样。
要体现“减负”和“内卷”的矛盾：
学校端减负，不等于竞争端减压；
校内时间减少，可能导致校外资源竞争加剧；
真正拉开差距的可能不是学习时长，而是信息、资源、规划、家庭执行力。

第五部分：家长真正焦虑点
要求：
要写出一线城市中产家长的真实心理。
例如：
怕孩子被别人偷偷甩开；
怕自己判断错方向；
怕政策变化让原来的规划失效；
怕孩子表面轻松，实际竞争力下降；
怕自己没有资源、信息和方法。

第六部分：具体建议，必须给 3 条
要求：
建议必须通俗易懂，可执行。
不能只说“尊重孩子”“减少焦虑”“培养兴趣”。
要给实际做法。
每条建议包括：
- 建议标题
- 为什么重要
- 家长具体怎么做
- 避免什么误区

建议方向可以包括：
1. 不要只盯着学校是否补课，而要看孩子的真实学习效率。
2. 建立家庭学习评估表，定期判断孩子的短板。
3. 把补课从“跟风报班”改成“精准补短板”。
4. 提前理解中高考政策、选科、升学路径。
5. 关注孩子的睡眠、运动、情绪稳定性，因为这会影响长期竞争力。
6. 用信息差、规划能力和执行力替代无效内卷。

第七部分：结尾
要求：
有力量，有余味。
不要鸡汤。
不要煽情过度。
要让家长觉得“这篇文章说出了我不敢说的焦虑，也给了我下一步该做什么”。

4. 标题生成

请为文章生成 10 个公众号标题。

标题要求：
1. 强情绪，能体现焦虑、冲突或紧迫感。
2. 反常识。
3. 面向家长。
4. 能提高公众号点击率。
5. 不要低俗标题党。
6. 标题要围绕教育竞争、减负、内卷、家长焦虑、升学决策。

标题示例风格：
- 减负3年，为什么孩子更累了？
- 真正拉开差距的，从来不是成绩
- 学校不补课了，最慌的为什么是家长？
- 孩子少学半小时，家长却开始失眠了

标题输出格式：
- title
- score，0-100
- reason
- risk，说明是否存在夸张、误导或过度焦虑的问题

5. 标题选择与优化

从 10 个标题中选出 1 个最适合发布的标题，并进行优化。

选择标准：
1. 吸引读者。
2. 有冲突感。
3. 面向家长。
4. 不造谣、不夸大事实。
5. 与文章内容高度匹配。
6. 适合微信公众号推荐流量。

输出：
- final_title
- why_selected
- optimized_reason

6. 微信公众号排版

请生成适合微信公众号发布的 Markdown 文章。

排版规则：
1. 每 2-4 行分段。
2. 小标题清晰。
3. 重点句可以加粗。
4. 不要使用过多 emoji。
5. 不要使用复杂表格。
6. 适合手机阅读。
7. 输出 Markdown 文件。
8. 文章开头要抓人。
9. 文章结尾要有传播感。

7. 封面图提示词生成

根据最终标题和文章内容，生成公众号封面图提示词。

封面图要求：
1. 目标是吸引家长点击。
2. 风格要适合教育类公众号。
3. 可以体现家长焦虑、孩子学习、竞争、分岔路、升学压力、教室、试卷、城市中产家庭等元素。
4. 不要生成真实人物肖像。
5. 不要使用侵犯版权的风格描述。
6. 输出中文提示词和英文提示词各一版。

输出格式：
- cover_prompt_cn
- cover_prompt_en
- negative_prompt
- suggested_layout
- cover_text，建议放在封面图上的短文案，控制在 12 个中文字以内

8. 最终输出

每次运行 Agent 后，请在 outputs 目录下生成一个独立文件夹，文件夹名称格式：
YYYYMMDD_HHMM_文章主题关键词

文件夹内包括：

1. news.json
保存选中的新闻和候选新闻。

2. article.md
保存最终公众号文章。

3. titles.json
保存 10 个标题和最终标题。

4. cover_prompt.md
保存封面图提示词。

5. report.md
保存本次运行报告，包括：
- 使用了哪个搜索 provider
- 使用了哪个写作模型
- 搜到了多少条新闻
- 为什么选中当前新闻
- 文章字数
- 最终标题
- 是否存在事实不确定点
- 建议人工复核的地方

三、模型调用设计

请把模型调用做成可配置。

支持至少两类模型：

1. 本地 LM Studio
兼容 OpenAI API。
默认 base_url:
http://localhost:1234/v1

2. 国内或商业大模型 API
兼容 OpenAI API。
例如：
- DashScope / 通义千问
- DeepSeek
- Kimi / Moonshot
- 智谱 GLM
- 腾讯混元

请设计统一的 LLMClient，不要让业务逻辑直接依赖某一个模型。

.env 示例：

LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_API_KEY=lm-studio
LMSTUDIO_MODEL=qwen3.5-9b

DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-plus

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

MOONSHOT_API_KEY=
MOONSHOT_BASE_URL=https://api.moonshot.ai/v1
MOONSHOT_MODEL=kimi-k2

ZHIPU_API_KEY=
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ZHIPU_MODEL=glm-4.5

DEFAULT_SEARCH_PROVIDER=dashscope
DEFAULT_DRAFT_PROVIDER=deepseek
DEFAULT_POLISH_PROVIDER=deepseek

模型分工建议：
1. 新闻检索：优先 DashScope / 通义千问联网搜索。
2. 文章生成：优先 DeepSeek。
3. 备用：GLM 或 Kimi。
4. 本地备用：LM Studio 中的 Qwen3.5-9B 或 Qwen3-14B。

四、程序结构

请生成一个清晰的 Python 项目，建议结构如下：

wechat_edu_agent/
  README.md
  requirements.txt
  .env.example
  main.py
  config.py

  agents/
    __init__.py
    workflow.py
    news_selector.py
    article_writer.py
    title_optimizer.py
    formatter.py
    cover_prompt_generator.py

  llm/
    __init__.py
    client.py
    prompts.py

  search/
    __init__.py
    base.py
    dashscope_search.py
    gemini_search.py
    custom_search.py
    manual_input.py

  models/
    __init__.py
    schemas.py

  utils/
    __init__.py
    json_utils.py
    text_utils.py
    file_utils.py
    logger.py

  outputs/
    .gitkeep

五、技术要求

1. 使用 Python 3.11+。
2. 使用 pydantic 定义数据结构。
3. 使用 python-dotenv 读取环境变量。
4. 使用 openai SDK 调用 OpenAI-compatible API。
5. 所有 API key 必须从 .env 读取，不要写死。
6. 所有中间结果都要保存，方便人工检查。
7. 代码要有清晰注释。
8. 要有异常处理。
9. 搜索失败时允许退回 manual_input 模式，让用户手动粘贴新闻。
10. LLM 输出 JSON 时要做容错解析。
11. 最终文章必须保存为 Markdown。
12. README 中要写清楚安装、配置和运行方法。

六、命令行使用方式

请实现 CLI。

示例：

python main.py run

可选参数：

python main.py run --topic "减负 内卷 高考竞争"
python main.py run --news-type "学校案例"
python main.py run --search-provider dashscope
python main.py run --draft-provider deepseek
python main.py run --manual-news ./sample_news.txt

如果用户指定 --manual-news，则跳过联网搜索，直接基于用户提供的新闻写文章。

七、核心 Prompt 模板

请在 llm/prompts.py 中保存以下 Prompt 模板，并在代码中调用。

1. 新闻选择 Prompt

你是一名教育内容编辑，需要为微信公众号“教育最前沿”选择一则新闻。

公众号定位：
拆解“减负”与“内卷”背后的残酷规则。
拒绝空话，只提供理性、可执行的升学决策。
在这里，看懂教育竞争的真实牌局。
别让家长的信息差，成为孩子人生的天花板。

目标读者：
一线城市中产家长，孩子年龄 6-18 岁。

请从候选新闻中选择最适合写成公众号文章的一条。

选择标准：
1. 新闻类型必须属于：教育部政策、学校案例、社会事件。
2. 新闻要能引发家长情绪共鸣。
3. 新闻必须与高考竞争、教育内卷、减负政策、升学焦虑有关。
4. 新闻要能引出深层逻辑，而不是只能写表面现象。
5. 新闻要能给家长提供实际建议。
6. 不要选择事实不清、来源不明、过度娱乐化的新闻。

请输出 JSON：
{
  "selected_news": {},
  "reason": "",
  "parent_emotion_points": [],
  "deep_logic_angles": [],
  "suggested_article_angle": "",
  "risk_notes": []
}

2. 文章写作 Prompt

你是一个教育类微信公众号作者，擅长根据热点新闻创作有传播力的深度教育文章。

公众号主题：
高考竞争 + 教育内卷，尤其关注“减负 vs 内卷”。

目标读者：
一线城市中产家长，孩子年龄 6-18 岁。

请基于以下新闻写一篇公众号文章。

文章结构：
1. 新闻事件，约 100 字。
2. 引出一个反常识问题。
3. 表面现象。
4. 深层逻辑，从教育学、社会学、升学竞争、家庭资源和教育决策角度分析。
5. 家长真正焦虑点，引发情感共鸣。
6. 给家长的 3 条具体建议，每条都要通俗、可执行。
7. 有力量的结尾，不要鸡汤。

风格要求：
- 理性但有冲击力。
- 不空话。
- 有观点。
- 不制造无意义恐慌。
- 不要像政策宣传稿。
- 不要像 AI 套话。
- 字数 1200-1800 中文字。
- 适合微信公众号发布。
- 多用短段落。
- 重点句可以加粗。

请输出 Markdown 正文。

3. 标题生成 Prompt

你是教育类微信公众号标题专家。
请为以下文章生成 10 个标题。

标题要求：
1. 强情绪，体现焦虑、冲突或紧迫感。
2. 反常识。
3. 面向家长。
4. 吸引读者点击。
5. 不低俗，不造谣，不恶意夸大。
6. 适合微信公众号推荐流量。

请输出 JSON 数组，每个标题包含：
{
  "title": "",
  "score": 0,
  "reason": "",
  "risk": ""
}

4. 标题选择 Prompt

你是教育类微信公众号主编。
请从以下 10 个标题中选择最适合发布的一个，并进一步优化。

选择标准：
1. 点击吸引力强。
2. 有冲突感。
3. 面向家长。
4. 不夸大事实。
5. 与文章内容高度匹配。
6. 适合公众号传播。

请输出 JSON：
{
  "final_title": "",
  "why_selected": "",
  "optimized_reason": ""
}

5. 封面图 Prompt 生成 Prompt

你是公众号封面策划。
请根据文章标题和内容，生成一套封面图提示词。

要求：
1. 面向一线城市中产家长。
2. 体现教育竞争、减负、内卷、孩子学习压力或家长焦虑。
3. 画面有冲突感，但不要恐怖、低俗或夸张。
4. 不要出现真实名人、真实学校 logo、真实机构 logo。
5. 不要使用侵权风格词。
6. 适合微信公众号封面。

请输出 JSON：
{
  "cover_prompt_cn": "",
  "cover_prompt_en": "",
  "negative_prompt": "",
  "suggested_layout": "",
  "cover_text": ""
}

八、数据结构

请使用 pydantic 定义以下模型：

NewsItem
- news_type
- title
- source
- published_at
- url
- summary
- core_facts
- parent_emotion_points
- relevance_score
- virality_score
- reason

ArticleResult
- final_title
- article_markdown
- word_count
- news
- titles
- cover_prompt
- risk_notes

RunReport
- run_id
- created_at
- search_provider
- draft_provider
- polish_provider
- selected_news_title
- final_title
- article_word_count
- output_dir
- warnings

九、质量控制

在最终输出前，请增加一个 review 步骤，检查：

1. 文章是否围绕新闻事实展开。
2. 是否存在编造新闻事实。
3. 是否符合 1200-1800 字。
4. 是否有 3 条具体建议。
5. 是否体现“减负 vs 内卷”的冲突。
6. 是否面向一线城市中产家长。
7. 标题是否夸张过度。
8. 是否需要人工复核事实。

如果发现问题，自动修正一次。

十、请先输出完整项目代码

请按照上述需求，生成完整项目代码。
要求：
1. 不要只给伪代码。
2. 每个文件都要给出完整内容。
3. README 要包含安装、配置、运行示例。
4. 如果某些搜索 API 的真实 SDK 不确定，请先写成可替换接口，并提供 TODO 标记。
5. 代码要能在没有联网搜索 API 的情况下，通过 --manual-news 跑通完整流程。
