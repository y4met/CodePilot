"""CodePilot CLI 入口。

用法:
    python run.py                # 真实模式（读取 .env 中的 API Key）
    python run.py --demo         # 离线演示模式（无需 Key，跑通完整循环）
    python run.py --once "..."   # 单次提问后退出
"""
from __future__ import annotations

import argparse
import sys

from code_agent.agent import CodeAgent
from code_agent.config import AgentConfig
from code_agent.llm import build_llm
from tools import build_default_tools

BANNER = r"""
  代码助手 Agent  |  ReAct · 工具调用 · 上下文记忆
---------------------------------------------------
"""

HELP = """命令:
  直接输入问题并回车 -> 交给 Agent
  :clear             -> 清空对话记忆
  :history           -> 查看当前记忆条数
  :exit  / :quit     -> 退出
"""

def main() -> int:
    parser = argparse.ArgumentParser(description="CodePilot 代码助手 Agent")
    parser.add_argument("--demo", action="store_true", help="离线演示模式（无需 API Key）")
    parser.add_argument("--once", type=str, default=None, help="单次提问后退出")
    parser.add_argument("--quiet", action="store_true", help="不打印推理过程")
    args = parser.parse_args()

    config = AgentConfig.load()
    config.ensure_workspace()

    try:
        llm = build_llm(config, demo=args.demo)
    except ValueError as e:
        print(f"[配置错误] {e}")
        return 1

    tools = build_default_tools(config)
    agent = CodeAgent(llm, tools, config)

    print(BANNER)
    mode = "离线演示模式 (MockLLM)" if args.demo else f"真实模型模式 ({config.model_name})"
    print(f"模式: {mode}")
    print(f"工作目录: {config.workspace}")
    print(f"可用工具: {', '.join(t.name for t in tools)}")
    print(HELP)

    # 单次模式
    if args.once:
        answer = agent.run(args.once, verbose=not args.quiet)
        print(f"\n=== Final Answer ===\n{answer}")
        return 0

    # REPL
    while True:
        try:
            user = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user:
            continue
        if user in (":exit", ":quit"):
            print("再见！")
            break
        if user == ":clear":
            agent.clear_memory()
            print("记忆已清空。")
            continue
        if user == ":history":
            print(f"当前记忆中有 {len(agent.memory)} 条消息。")
            continue

        answer = agent.run(user, verbose=not args.quiet)
        print(f"\n=== Final Answer ===\n{answer}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
