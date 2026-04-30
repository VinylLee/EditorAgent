# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for WeChat Education Agent GUI
生成独立EXE：python -m PyInstaller wechat_edu_agent.spec
"""

import sys
import os
from pathlib import Path

block_cipher = None

# 获取项目根目录
project_root = Path(os.getcwd())

# 隐藏导入（这些模块动态导入，PyInstaller可能检测不到）
hiddenimports = [
    'wechat_edu_agent',
    'wechat_edu_agent.agents',
    'wechat_edu_agent.agents.workflow',
    'wechat_edu_agent.agents.news_selector',
    'wechat_edu_agent.agents.fact_extract_agent',
    'wechat_edu_agent.agents.article_writer',
    'wechat_edu_agent.agents.title_optimizer',
    'wechat_edu_agent.agents.title_risk_agent',
    'wechat_edu_agent.agents.review_agent',
    'wechat_edu_agent.agents.polish_agent',
    'wechat_edu_agent.agents.cover_prompt_generator',
    'wechat_edu_agent.agents.formatter',
    'wechat_edu_agent.llm',
    'wechat_edu_agent.llm.client',
    'wechat_edu_agent.llm.prompts',
    'wechat_edu_agent.llm.json_schemas',
    'wechat_edu_agent.models',
    'wechat_edu_agent.models.schemas',
    'wechat_edu_agent.search',
    'wechat_edu_agent.search.base',
    'wechat_edu_agent.search.manual_input',
    'wechat_edu_agent.search.dashscope_search',
    'wechat_edu_agent.search.tavily_search',
    'wechat_edu_agent.search.aggregator',
    'wechat_edu_agent.utils',
    'wechat_edu_agent.utils.json_utils',
    'wechat_edu_agent.utils.text_utils',
    'wechat_edu_agent.utils.file_utils',
    'wechat_edu_agent.utils.logger',
    'openai',
    'pydantic',
    'dotenv',
    'dashscope',
]

a = Analysis(
    # 入口脚本：运行 GUI 模式
    [str(project_root / 'wechat_edu_agent' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # 包含整个 wechat_edu_agent 包（包括所有Python文件）
        (str(project_root / 'wechat_edu_agent'), 'wechat_edu_agent'),
        # 如果有.env.example，也包含进去
        # (str(project_root / '.env.example'), '.'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='微信教育代理',  # 生成的EXE名称
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # False=无控制台窗口，True=保留控制台
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
