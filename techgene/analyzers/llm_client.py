"""LLM 客户端封装

统一调用 DeepSeek API（OpenAI 兼容接口）。
用于维度二的 I/O 范式分类和维度三的引用意图分类。
"""

import os
from openai import OpenAI
from loguru import logger

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _client


def classify(text: str, task: str, options: list[str]) -> str:
    """用 LLM 对文本进行分类。

    Args:
        text: 论文标题 + 摘要
        task: 分类任务描述
        options: 候选类别列表

    Returns:
        最匹配的类别
    """
    client = get_client()
    options_str = "\n".join(f"- {o}" for o in options)

    prompt = f"""{task}

文本：
{text[:2000]}

候选类别：
{options_str}

只返回最匹配的一个类别名称，不要解释。"""

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.1,
        )
        result = resp.choices[0].message.content.strip()
        # 匹配最接近的选项
        for opt in options:
            if opt.lower() in result.lower():
                return opt
        return result  # 返回原始结果，由调用方处理
    except Exception as e:
        logger.warning(f"LLM 分类失败: {e}")
        return options[0]  # 降级返回第一个选项


def analyze_citation_intent(citation_text: str) -> str:
    """判断引用意图：作为组件使用 vs 对标比较。

    Returns:
        "uses_as_component" | "compares_against" | "background_mention"
    """
    client = get_client()
    prompt = f"""分析以下论文引用句子的意图。分类为：
- component: 将该技术作为组件/模块使用（如 "we use X as backbone", "built upon X"）
- comparison: 与对该技术进行对标比较（如 "compared to X", "outperforms X"）
- background: 仅作为背景引用（如 "recently, X proposed...", "following X"）

引用句：
{citation_text[:500]}

只返回一个词：component, comparison, 或 background。"""

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.1,
        )
        result = resp.choices[0].message.content.strip().lower()
        if "component" in result:
            return "component"
        elif "comparison" in result:
            return "comparison"
        else:
            return "background"
    except Exception as e:
        logger.warning(f"引用意图分析失败: {e}")
        return "background"
