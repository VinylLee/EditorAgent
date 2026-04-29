# Run Report

- run_id: 20260429_151950
- created_at: 2026-04-29T15:19:50
- search_provider: manual
- draft_provider: deepseek-chat
- polish_provider: deepseek-chat
- selected_news_title: 新闻标题：松原多所高中推行“规范办学”：早晨推迟半小时、高三不补课，家长却陷入另一重忧虑
- final_title: 学校不补课了，别人家孩子偷偷学，你家孩子敢睡吗？
- article_word_count: 1770
- output_dir: outputs\20260429_1517_教育内卷
- fact_count: 0
- number_count: 0
- quote_count: 0
- review_score: 40
- review_passed: False
- final_review_passed: False
- title_risk_count: 10
- auto_rewrite_performed: False
- human_check_required: True
- warning: Fact extract JSON parse failed; repair attempted. Error: 2 validation errors for FactExtractResult
allowed_inferences.0
  Input should be a valid string [type=string_type, input_value={'id': 'I1', 'inference':...规范管理政策”'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
allowed_inferences.1
  Input should be a valid string [type=string_type, input_value={'id': 'I2', 'inference':...补怎么办？’”'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
- warning: Fact extract JSON repair failed; fallback used. Error: 2 validation errors for FactExtractResult
allowed_inferences.0
  Input should be a valid string [type=string_type, input_value={'id': 'I1', 'inference':...规范管理政策”'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
allowed_inferences.1
  Input should be a valid string [type=string_type, input_value={'id': 'I2', 'inference':...补怎么办？’”'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
- warning: No safe titles found; fallback to all titles.
- warning: Review JSON parse failed; repair attempted. Error: 1 validation error for ReviewResult
title_risks.0
  Input should be a valid string [type=string_type, input_value={'title': '学校不补...表述，风险低。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
- warning: Review JSON repair failed; fallback used. Error: 1 validation error for ReviewResult
title_risks.0
  Input should be a valid string [type=string_type, input_value={'title': '学校不补...表述，风险低。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
