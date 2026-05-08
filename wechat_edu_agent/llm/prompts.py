"""
提示词加载模块。

加载顺序（高优先级优先）：
1. PROMPTS_PATH 环境变量指向的 JSON 文件
2. 打包后 exe 同目录下的 prompts.json（独立部署，修改无需重打包）
3. 本文件同目录下的 prompts.json
4. sys._MEIPASS 下的内置 prompts.json（PyInstaller 包内兜底）
5. 内置默认值（内置字符串兜底）

支持在 prompts.json 中使用 {VARIABLE_NAME} 占位符，
变量值从 app_constants.py 中读取。

用法（与之前完全兼容）：
    from llm.prompts import SYSTEM_PROMPT, REVIEW_PROMPT
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from app_constants import (
    ARTICLE_WORD_COUNT_MIN,
    ARTICLE_WORD_COUNT_MAX,
    ARTICLE_WORD_COUNT_REVIEW_MAX,
    ARTICLE_WORD_COUNT_TARGET,
)

# 可供 prompts.json 引用的变量名 → 值映射
_PROMPT_VARS: dict[str, Any] = {
    "ARTICLE_WORD_COUNT_MIN": ARTICLE_WORD_COUNT_MIN,
    "ARTICLE_WORD_COUNT_MAX": ARTICLE_WORD_COUNT_MAX,
    "ARTICLE_WORD_COUNT_TARGET": ARTICLE_WORD_COUNT_TARGET,
    "ARTICLE_WORD_COUNT_REVIEW_MAX": ARTICLE_WORD_COUNT_REVIEW_MAX,
}


def _substitute(text: str) -> str:
    """安全替换 {VAR_NAME} 占位符，不影响已有的 {}。

    只替换 _PROMPT_VARS 中定义的变量，不认识的 {} 原样保留。
    """
    for key, value in _PROMPT_VARS.items():
        text = text.replace(f"{{{key}}}", str(value))
    return text


def _load_prompts() -> dict[str, str]:
    sources: list[Path] = []

    # 1) 环境变量指定的路径
    env_path = os.getenv("PROMPTS_PATH")
    if env_path:
        sources.append(Path(env_path))

    # 2) 打包后 exe 同目录下的 prompts.json（独立部署用，修改无需重打包）
    if getattr(sys, "frozen", False):
        sources.append(Path(sys.executable).resolve().parent / "prompts.json")

    # 3) 本文件同目录下的 prompts.json（开发模式）
    sources.append(Path(__file__).resolve().parent / "prompts.json")

    # 4) PyInstaller 打包后，数据文件可能在 sys._MEIPASS 下
    if hasattr(sys, "_MEIPASS"):
        sources.append(Path(sys._MEIPASS) / "wechat_edu_agent" / "llm" / "prompts.json")
        sources.append(Path(sys._MEIPASS) / "llm" / "prompts.json")

    for source in sources:
        try:
            with source.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # 统一格式：数组转成 \n 连接的字符串，字符串保持原样
                normalized: dict[str, str] = {}
                for key, value in data.items():
                    if isinstance(value, list):
                        normalized[key] = "\n".join(value)
                    elif isinstance(value, str):
                        normalized[key] = value
                    else:
                        continue
                    # 替换占位符变量
                    normalized[key] = _substitute(normalized[key])
                # # 记录 prompts.json 加载来源（便于验证打包后是否用了 exe 旁边的文件）
                # try:
                #     with open(Path(sys.executable if getattr(sys, "frozen", False) else __file__).parent / "_prompts_source.txt", "w") as _f:
                #         _f.write(str(source))
                # except OSError:
                #     pass
                return normalized
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue

    # 当没有有效 JSON 文件时返回空字典
    return {}


_prompts = _load_prompts()


def __getattr__(name: str) -> str:
    """支持 from llm.prompts import XXX_PROMPT 的模块级变量。"""
    if name in _prompts:
        return _prompts[name]
    raise AttributeError(f"module 'llm.prompts' has no attribute '{name}'")


def __dir__() -> list[str]:
    return list(_prompts.keys())
