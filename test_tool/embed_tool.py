"""
向量化小工具 —— 手动输入文本，调用向量化接口返回向量。

Usage:
    python embed_tool.py
    python embed_tool.py "要向量化的文本"
    python embed_tool.py "要向量化的文本" --model text-embedding-v3
"""

import argparse
import sys
import os

# 保证能导入项目内的模块
_project_root = os.path.dirname(os.path.abspath(__file__))
_pkg_dir = os.path.join(_project_root, "wechat_edu_agent")
sys.path.insert(0, _pkg_dir)

from config import load_config
from llm.client import LLMClient


def main():
    parser = argparse.ArgumentParser(description="向量化小工具")
    parser.add_argument("text", nargs="?", help="要向量化的文本（留空则交互式输入）")
    parser.add_argument("--model", help="向量化模型（覆盖 .env 中的配置）")
    args = parser.parse_args()

    config = load_config()
    client = LLMClient.from_config(config)

    # 从命令行参数或用户输入获取文本
    if args.text:
        texts = [args.text]
    else:
        print("请输入要向量化的文本（输入空行结束）：")
        lines = []
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        if not lines:
            print("未输入任何文本，退出。")
            return
        texts = ["\n".join(lines)]

    model = args.model or config.embedding_model

    print(f"\n正在调用向量化接口...")
    print(f"  API Base: {config.embedding_base_url}")
    print(f"  Model:    {model}")
    print(f"  输入文本: {texts[0][:80]}{'...' if len(texts[0]) > 80 else ''}")
    print(f"  文本长度: {len(texts[0])} 字符")
    print()

    try:
        vectors = client.embed_texts(texts, model=model)
    except Exception as e:
        print(f"向量化调用失败: {e}")
        print()
        print("提示：当前 .env 中配置的模型是 gte-rerank-v2，这是一个重排序模型。")
        print("请使用向量模型，例如 text-embedding-v3（DashScope），text-embedding-3-small（OpenAI）等。")
        print("用法: python embed_tool.py \"文本\" --model text-embedding-v3")
        sys.exit(1)

    vector = vectors[0]
    print(f"向量维度: {len(vector)}")
    print(f"前 10 维: {vector[:10]}")
    print(f"完整向量 ({len(vector)} 维):")
    print(vector)


if __name__ == "__main__":
    main()
