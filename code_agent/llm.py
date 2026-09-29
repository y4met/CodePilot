"""LLM 抽象层。

- BaseLLM: 统一接口 chat(messages) -> str
- OpenAILLM: 对接任意 OpenAI 兼容服务（OpenAI/DeepSeek/Kimi/通义千问...），带指数退避重试
- MockLLM: 离线演示用，无需 API Key 即可跑通完整 ReAct 循环与工具调用
"""
from __future__ import annotations

import abc
import json
import re
import time
from typing import List, Dict

from .config import AgentConfig

Message = Dict[str, str]  # {"role": "system|user|assistant|tool", "content": "..."}


class BaseLLM(abc.ABC):
    """所有 LLM 实现的统一接口。"""

    @abc.abstractmethod
    def chat(self, messages: List[Message]) -> str:
        """根据消息列表返回模型文本回复。"""


class OpenAILLM(BaseLLM):
    """OpenAI 兼容客户端，内置错误重试。"""

    def __init__(self, config: AgentConfig):
        if not config.has_llm_credentials():
            raise ValueError(
                "未检测到 OPENAI_API_KEY。"
                "可使用 --demo 参数运行离线演示模式。"
            )
        # 延迟导入，避免无 openai 包时 Mock 模式也报错
        from openai import OpenAI

        self._client = OpenAI(api_key=config.api_key, base_url=config.base_url)
        self._model = config.model_name
        self._max_retries = config.max_retries

    def chat(self, messages: List[Message]) -> str:
        last_err: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=0.2,
                )
                content = resp.choices[0].message.content or ""
                return content.strip()
            except Exception as e:  # 网络/限流/服务端错误均重试
                last_err = e
                wait = 2 ** (attempt - 1)  # 1s, 2s, 4s...
                print(f"  [LLM] 第 {attempt} 次调用失败({e.__class__.__name__})，{wait}s 后重试...")
                time.sleep(wait)
        raise RuntimeError(f"LLM 调用连续失败 {self._max_retries} 次: {last_err}")


class MockLLM(BaseLLM):
    """离线演示用 LLM。

    不调用真实模型，根据对话内容产出确定性的 ReAct 文本，
    用于在没有 API Key 的情况下验证 Agent 循环、工具解析与记忆逻辑。
    """

    def chat(self, messages: List[Message]) -> str:
        # 取最后一条用户消息
        user_msgs = [m for m in messages if m["role"] == "user"]
        last_user = user_msgs[-1]["content"] if user_msgs else ""

        # 如果上一轮已有 run_python 的观察结果，则给出最终答案
        if "Observation:" in messages[-1]["content"] if messages else False:
            return (
                "Thought: 代码已成功运行，输出符合预期，可以给出最终答案。\n"
                "Final Answer: 这是离线演示模式返回的结果。真实模式下，我会先调用工具验证代码，"
                "再基于观察结果给出最终答案。你可以配置 .env 中的 OPENAI_API_KEY 接入真实模型。"
            )

        # 包含代码/运行/测试意图时，先触发一次工具调用
        if re.search(r"(代码|运行|执行|python|函数|sort|test|计算|算)", last_user, re.I):
            payload = json.dumps(
                {"code": "print('hello from MockLLM'); print(2 + 3)"},
                ensure_ascii=False,
            )
            return (
                "Thought: 用户需要验证代码，我先用 run_python 工具实际运行一下。\n"
                f"Action: run_python\n"
                f"Action Input: {payload}"
            )

        # 默认：直接友好回复
        return (
            "Thought: 这是一个简单问候，不需要调用工具。\n"
            f"Final Answer: 你好！我是 CodePilot 代码助手（离线演示模式）。"
            f"你可以让我：用 Python 运行一段代码、读取工作目录里的文件、或在代码库中搜索内容。"
        )


def build_llm(config: AgentConfig, demo: bool = False) -> BaseLLM:
    """工厂方法：根据参数选择真实 LLM 或离线 Mock。"""
    if demo:
        return MockLLM()
    return OpenAILLM(config)
