# CodePilot —— 代码助手 Agent

一个基于 **ReAct（Reasoning + Acting）模式** 的命令行代码助手 Agent。它能理解你的自然语言需求，**自己决定是否调用工具**，实际运行代码 / 读取文件 / 搜索代码库，并基于真实观察结果给出最终答案，而不是凭空编造。

本项目用于掌握 Agent 开发基础：LLM 调用、Prompt 设计、工具集成、上下文记忆、错误重试。

---

## 1. 功能特性

| 能力 | 说明 |
|------|------|
| **Agent 主循环** | 输入 → 推理(Thought) → 行动(Action/工具调用) → 观察(Observation) → … → 最终答案 |
| **工具调用** | 内置 3 个工具：执行 Python、读取文件、搜索代码库 |
| **上下文记忆** | 滑动窗口保存多轮对话，支持 `:clear` 清空 |
| **错误处理与重试** | LLM 调用指数退避重试；工具异常/格式错误回传给模型自我修正；最大轮次兜底 |
| **离线演示** | `--demo` 模式内置 MockLLM，**无需 API Key** 即可跑通完整循环 |
| **多模型兼容** | OpenAI / DeepSeek / Kimi(Moonshot) / 通义千问 等任何 OpenAI 兼容接口 |
| **安全边界** | 文件读取限制在工作目录内，代码执行带超时与路径隔离 |

---

## 2. 项目结构

```
01CodeReviewAgent/
├── run.py                  # CLI 入口（REPL + --once + --demo）
├── requirements.txt
├── .env.example            # 环境变量模板
├── code_agent/             # Agent 核心
│   ├── config.py          #   配置加载（.env / 环境变量）
│   ├── llm.py             #   LLM 抽象 + OpenAI 客户端(重试) + MockLLM
│   ├── prompts.py         #   System Prompt + ReAct 协议 + Few-shot
│   ├── memory.py          #   滑动窗口对话记忆
│   └── agent.py            #   ReAct 主循环（解析/调度/兜底）
├── tools/                  # 工具层
│   ├── base.py            #   Tool 抽象基类
│   ├── python_runner.py   #   工具1：子进程执行 Python（超时保护）
│   ├── file_reader.py     #   工具2：安全读取工作区文件（防路径逃逸）
│   └── code_search.py     #   工具3：正则搜索代码
├── sandbox/               # 工具执行的工作目录
│   └── demo_math.py       #   示例文件（供 read_file/search_code 演示）
└── tests/
    └── test_smoke.py      # 冒烟测试（不依赖网络/Key）
```

---

## 3. 快速开始

### 3.1 环境准备

```powershell
# Python 3.10+
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3.2 离线演示（无需 Key，先看效果）

```powershell
python run.py --demo
```

或单次提问：

```powershell
python run.py --demo --once "帮我写一个两数相加函数并运行验证"
```

会看到完整的 ReAct 推理过程：

```
===== 推理轮次 1 =====
Thought: 用户需要验证代码，我先用 run_python 工具实际运行一下。
Action: run_python
Action Input: {"code": "print('hello from MockLLM'); print(2 + 3)"}
  -> Observation:
     [stdout] hello from MockLLM
     5

===== 推理轮次 2 =====
Thought: 代码已成功运行，可以给出最终答案。
Final Answer: ...
```

### 3.3 接入真实模型

```powershell
copy .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY，按需修改 BASE_URL / MODEL_NAME
python run.py
```

国内常用配置示例（见 `.env.example` 注释）：

| 服务商 | BASE_URL | MODEL_NAME |
|--------|----------|------------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |

### 3.4 交互命令

REPL 中：
- 直接输入问题回车 → 交给 Agent
- `:history` → 查看记忆条数
- `:clear` → 清空记忆
- `:exit` / `:quit` → 退出

---

## 4. 工作原理（ReAct 架构）

```
用户输入
   │
   ▼
┌─────────────────────────────────────────────┐
│ 组装 Prompt:                                 │
│  system(工具说明+ReAct协议+Few-shot)         │
│  + 记忆历史 + 用户输入                        │
└─────────────────────────────────────────────┘
   │
   ▼
 LLM.chat()  ──失败(指数退避, 最多 MAX_RETRIES 次)──▶ 报错返回
   │
   ▼
 解析模型输出
   │
   ├── Final Answer ──▶ 返回用户，写入记忆，结束
   │
   ├── Action + Action Input(JSON)
   │       │
   │       ▼
   │   查找工具 → tool.run(args)
   │       │  (异常/超时/错误一律转成字符串 Observation)
   │       ▼
   │   追加 Observation 到上下文 → 回到 LLM.chat()
   │
   └── 格式错误 → 纠错消息回传模型重试
            │
            └─ 超过 MAX_ITERATIONS → 兜底返回
```

**关键设计：**
- **工具结果永远回传给模型**，包括错误。这样模型能像人看报错一样自我修正，而不是整个 Agent 崩溃。
- **Action Input 强制 JSON**，解析失败时不崩溃，而是把错误描述发回模型重写。
- **Few-shot 示例**直接写进 system prompt，让模型第一次就对齐输出格式。

---

## 5. 内置工具

| 工具 | 参数 | 作用 | 安全措施 |
|------|------|------|----------|
| `run_python` | `code: str` | 独立子进程执行 Python | `-I` 隔离模式、`CODE_TIMEOUT` 超时、cwd 限定工作区 |
| `read_file` | `path: str` | 读取工作区内文本文件 | 路径 resolve 后校验必须位于 workspace 内，防 `../` 逃逸 |
| `search_code` | `query: str`, `file_ext?: str` | 正则/子串搜索代码 | 忽略 `.git/__pycache__` 等目录，结果上限 30 条 |

> ⚠️ `run_python` 使用子进程隔离，适合课程/演示；生产环境应换 Docker / Firecracker 等强沙箱。

---

## 6. 配置项（.env）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | （空） | API 密钥 |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 兼容接口地址 |
| `MODEL_NAME` | `gpt-4o-mini` | 模型名 |
| `MAX_ITERATIONS` | `8` | 单轮对话最大推理次数（防死循环） |
| `MAX_RETRIES` | `3` | LLM 调用失败重试次数 |
| `CODE_TIMEOUT` | `10` | 代码执行超时秒数 |
| `MEMORY_WINDOW` | `10` | 记忆保留最近 N 条消息 |
| `WORKSPACE` | `./sandbox` | 文件工具/代码执行根目录 |

---

## 7. 测试

不依赖网络和 Key：

```powershell
python tests/test_smoke.py
```

覆盖：Python 执行正常/报错/超时、文件读取与路径逃逸拦截、代码搜索、记忆滑动窗口、ReAct 文本解析、完整端到端循环。

---

## 8. 如何扩展新工具

1. 在 `tools/` 下新建类，继承 `Tool`，实现 `name` / `description` / `run(args)`；
2. 在 `tools/__init__.py` 的 `build_default_tools()` 里注册；
3. 无需改 Agent —— 工具描述会自动拼进 system prompt，模型即学即用。

示例：

```python
from tools.base import Tool

class Calculator(Tool):
    name = "calculator"
    description = "计算算术表达式。参数: expression (str)。"
    def run(self, args: dict) -> str:
        try:
            return str(eval(args["expression"], {"__builtins__": {}}))
        except Exception as e:
            return f"Error: {e}"
```

---

## 9. 技术选型说明

- **未直接使用 LangChain**，而是手写一个精简 ReAct 循环。原因：课程目标是理解 Agent 本质（推理-行动-观察循环），手写实现能清晰看到 Prompt 协议、解析与调度逻辑；同时避免框架版本变动带来的不稳定性。LLM 层采用 OpenAI SDK，与 LangChain 的 `Tool` / `AgentExecutor` 概念一一对应，后续可平滑迁移。
- **依赖极小**（仅 `openai` + `python-dotenv`），核心逻辑零第三方框架，可读性高。
