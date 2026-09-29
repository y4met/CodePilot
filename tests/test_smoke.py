"""冒烟测试：不依赖网络/API Key，验证工具、记忆、解析与完整 ReAct 循环。

运行: python -m pytest tests/ -v   或   python tests/test_smoke.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让 tests 能导入项目根
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code_agent.agent import CodeAgent
from code_agent.config import AgentConfig
from code_agent.llm import MockLLM
from code_agent.memory import ConversationMemory
from tools.python_runner import PythonRunner
from tools.file_reader import FileReader
from tools.code_search import CodeSearch


def test_python_runner_ok():
    t = PythonRunner(timeout=5)
    out = t.run({"code": "print(1+2)"})
    assert "3" in out, out
    print("[PASS] python_runner 正常执行")


def test_python_runner_error_returns_stderr():
    t = PythonRunner(timeout=5)
    out = t.run({"code": "raise ValueError('boom')"})
    assert "ValueError" in out, out
    print("[PASS] python_runner 错误被捕获并回传")


def test_python_runner_timeout():
    t = PythonRunner(timeout=2)
    out = t.run({"code": "while True: pass"})
    assert ("被终止" in out) or ("超时" in out), out
    print("[PASS] python_runner 超时保护")


def test_file_reader_path_escape():
    import tempfile
    with tempfile.TemporaryDirectory() as ws:
        Path(ws, "a.py").write_text("x=1", encoding="utf-8")
        t = FileReader(workspace=Path(ws))
        assert "x=1" in t.run({"path": "a.py"})
        assert "禁止" in t.run({"path": "../etc/passwd"})
    print("[PASS] file_reader 读取 + 路径逃逸拦截")


def test_code_search():
    import tempfile
    with tempfile.TemporaryDirectory() as ws:
        Path(ws, "b.py").write_text("def hello():\n    pass\n", encoding="utf-8")
        t = CodeSearch(workspace=Path(ws))
        out = t.run({"query": "hello"})
        assert "b.py" in out and "hello" in out, out
    print("[PASS] code_search 关键字搜索")


def test_memory_window():
    m = ConversationMemory(window=4)
    for i in range(6):
        m.add_user(f"q{i}")
        m.add_assistant(f"a{i}")
    msgs = m.messages()
    assert len(msgs) == 4, len(msgs)  # 只保留最近 4 条
    assert msgs[-1]["content"] == "a5"
    print("[PASS] memory 滑动窗口")


def test_react_parse():
    a = CodeAgent(MockLLM(), [], AgentConfig())
    # final
    p = a._parse("Thought: done\nFinal Answer: 结果是 42")
    assert p["type"] == "final" and "42" in p["answer"]
    # action
    p = a._parse('Thought: run\nAction: run_python\nAction Input: {"code": "print(1)"}')
    assert p["type"] == "action" and p["name"] == "run_python"
    assert p["args"]["code"] == "print(1)"
    # bad json
    p = a._parse("Thought: run\nAction: run_python\nAction Input: {bad json")
    assert p["type"] == "parse_error"
    print("[PASS] ReAct 解析 final/action/错误格式")


def test_full_loop_with_mock():
    cfg = AgentConfig.load()
    cfg.ensure_workspace()
    tools = [PythonRunner(timeout=5, workspace=cfg.workspace)]
    agent = CodeAgent(MockLLM(), tools, cfg)
    ans = agent.run("帮我写个两数相加函数并运行验证", verbose=False)
    assert ans, "应有最终答案"
    assert len(agent.memory) >= 2
    print("[PASS] 完整 ReAct 循环（输入->推理->工具->输出）")


if __name__ == "__main__":
    test_python_runner_ok()
    test_python_runner_error_returns_stderr()
    test_python_runner_timeout()
    test_file_reader_path_escape()
    test_code_search()
    test_memory_window()
    test_react_parse()
    test_full_loop_with_mock()
    print("\n全部冒烟测试通过")
