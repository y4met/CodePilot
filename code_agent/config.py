"""配置加载：从环境变量/.env 读取所有可调参数。

集中管理配置，避免在代码中散落魔法数字；启动时一次性校验关键项。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv 缺失时不阻塞，环境变量仍可从系统读取
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False


# 项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass
class AgentConfig:
    """Agent 全部配置项。"""

    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o-mini"

    max_iterations: int = 8
    max_retries: int = 3
    code_timeout: int = 10
    memory_window: int = 10
    workspace: Path = field(default_factory=lambda: ROOT_DIR / "sandbox")

    @classmethod
    def load(cls, env_file: str | Path | None = None) -> "AgentConfig":
        """加载 .env 与环境变量。"""
        env_path = Path(env_file) if env_file else ROOT_DIR / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        workspace = Path(os.getenv("WORKSPACE", str(ROOT_DIR / "sandbox")))
        if not workspace.is_absolute():
            workspace = (ROOT_DIR / workspace).resolve()

        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
            model_name=os.getenv("MODEL_NAME", "gpt-4o-mini").strip(),
            max_iterations=int(os.getenv("MAX_ITERATIONS", "8")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            code_timeout=int(os.getenv("CODE_TIMEOUT", "10")),
            memory_window=int(os.getenv("MEMORY_WINDOW", "10")),
            workspace=workspace,
        )

    def ensure_workspace(self) -> None:
        """确保工作目录存在（代码执行/文件读写的根）。"""
        self.workspace.mkdir(parents=True, exist_ok=True)

    def has_llm_credentials(self) -> bool:
        return bool(self.api_key)
