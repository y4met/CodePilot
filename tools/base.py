"""工具抽象基类。

每个工具需要：
- name:         ReAct 协议中使用的名字
- description:  给模型看的说明（含参数）
- run(args):    执行，返回字符串结果（错误也转成字符串返回给模型，让它自我修正）
"""
from __future__ import annotations

import abc


class Tool(abc.ABC):
    name: str = "tool"
    description: str = ""

    @abc.abstractmethod
    def run(self, args: dict) -> str:
        """执行工具，args 为模型给出的 JSON 解析结果。"""

    def describe(self) -> str:
        return f"- {self.name}: {self.description}"
