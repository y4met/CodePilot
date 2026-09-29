"""上下文记忆：滑动窗口对话历史。

只保留最近 N 轮 user/assistant 消息，避免上下文无限膨胀；
系统 Prompt 与工具 Observation 不纳入窗口截断。
"""
from __future__ import annotations

from collections import deque
from typing import List, Dict

Message = Dict[str, str]


class ConversationMemory:
    def __init__(self, window: int = 10):
        # window 表示保留最近多少条 user+assistant 消息
        self._buf: deque[Message] = deque(maxlen=window)

    def add_user(self, content: str) -> None:
        self._buf.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self._buf.append({"role": "assistant", "content": content})

    def messages(self) -> List[Message]:
        """返回当前窗口内的对话历史（浅拷贝）。"""
        return list(self._buf)

    def clear(self) -> None:
        self._buf.clear()

    def __len__(self) -> int:
        return len(self._buf)
