"""CodePilot Agent：ReAct 主循环。

流程（输入 → 推理 → 工具调用 → 输出）：
  1. 组装 system prompt（含工具说明 + Few-shot）+ 记忆中的历史 + 用户输入
  2. 调用 LLM 得到一段文本
  3. 解析文本：
       - 命中 Final Answer  -> 返回给用户，写入记忆，结束本轮
       - 命中 Action/Action Input -> 找到对应工具执行，把 Observation 追加进上下文，回到 2
       - 解析失败          -> 构造一条纠错消息，让模型重试（计入轮次）
  4. 达到 max_iterations 仍未出 Final Answer -> 兜底返回最后一段文本
"""
from __future__ import annotations

import json
import re
from typing import List, Dict

from .config import AgentConfig
from .llm import BaseLLM
from .memory import ConversationMemory
from .prompts import SYSTEM_TEMPLATE, FEWSHOT_EXAMPLE
from tools.base import Tool

Message = Dict[str, str]

# 解析 Action Input：冒号后到行尾/下一个标签前的 JSON
_ACTION_RE = re.compile(r"Action:\s*([a-zA-Z_][\w]*)")
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.+?)(?=\n\s*(?:Thought|Action|Final Answer):|$)", re.S)
_FINAL_RE = re.compile(r"Final Answer:\s*(.+)", re.S)


class CodeAgent:
    def __init__(self, llm: BaseLLM, tools: List[Tool], config: AgentConfig):
        self._llm = llm
        self._tools = {t.name: t for t in tools}
        self._cfg = config
        self._memory = ConversationMemory(window=config.memory_window)

    # ---------- prompt 组装 ----------
    def _system_prompt(self) -> str:
        tools_desc = "\n".join(t.describe() for t in self._tools.values())
        return SYSTEM_TEMPLATE.format(tools_desc=tools_desc) + FEWSHOT_EXAMPLE

    # ---------- 解析 ----------
    @staticmethod
    def _parse(text: str) -> dict:
        """把模型输出解析成 {type: final/action/error, ...}。"""
        final = _FINAL_RE.search(text)
        if final:
            return {"type": "final", "answer": final.group(1).strip()}

        action = _ACTION_RE.search(text)
        if action:
            name = action.group(1).strip()
            m = _ACTION_INPUT_RE.search(text)
            args: dict = {}
            if m:
                raw = m.group(1).strip()
                try:
                    args = json.loads(raw)
                except json.JSONDecodeError:
                    return {"type": "parse_error", "raw": raw,
                            "message": f"Action Input 不是合法 JSON: {raw[:200]}"}
            return {"type": "action", "name": name, "args": args}

        return {"type": "error", "message": "无法识别输出格式，请严格使用 Thought/Action/Final Answer 格式。"}

    # ---------- 主循环 ----------
    def run(self, user_input: str, verbose: bool = True) -> str:
        self._memory.add_user(user_input)

        # 每轮临时上下文：system + 历史 + 本轮逐步产生的 Thought/Action/Observation
        messages: List[Message] = [
            {"role": "system", "content": self._system_prompt()},
        ]
        messages.extend(self._memory.messages())
        # 注意：上面 add_user 已把本轮 user 加进记忆，messages 里已含。

        for step in range(1, self._cfg.max_iterations + 1):
            try:
                raw = self._llm.chat(messages)
            except Exception as e:
                return f"[错误] LLM 调用失败: {e}"

            if verbose:
                self._print_step(step, raw)

            parsed = self._parse(raw)

            if parsed["type"] == "final":
                answer = parsed["answer"]
                self._memory.add_assistant(raw)  # 存完整 ReAct 轨迹的最后一条
                return answer

            if parsed["type"] == "action":
                tool = self._tools.get(parsed["name"])
                if tool is None:
                    obs = f"Error: 未知工具 '{parsed['name']}'，可用工具: {list(self._tools)}"
                else:
                    obs = tool.run(parsed["args"])
                if verbose:
                    print(f"  -> Observation:\n{self._indent(obs)}\n")
                # 把本轮 ReAct 文本与观察作为一条 user 消息追加（模型按 ReAct 文本续写）
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": f"Observation: {obs}"})
                continue

            # parse_error / 格式错误：把纠错提示发给模型重试
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user",
                             "content": f"格式错误：{parsed['message']}。请按规定格式重新输出。"})

        # 兜底：超过最大轮次
        return "（已达到最大推理轮次，未得出最终答案。请尝试更具体的问题或调大 MAX_ITERATIONS）"

    def clear_memory(self) -> None:
        self._memory.clear()

    @property
    def memory(self) -> ConversationMemory:
        return self._memory

    # ---------- 打印辅助 ----------
    @staticmethod
    def _indent(text: str, prefix: "str | None" = None) -> str:
        return "\n".join("     " + line for line in text.splitlines())

    @staticmethod
    def _print_step(step: int, raw: str) -> None:
        print(f"\n===== 推理轮次 {step} =====")
        print(raw)
