"""工具：安全读取工作目录内的文件。

限制路径必须位于 workspace 之内，防止通过 ../ 读到系统敏感文件。
"""
from __future__ import annotations

from pathlib import Path

from .base import Tool

MAX_BYTES = 64 * 1024  # 单次最多读 64KB，防止读入巨型文件


class FileReader(Tool):
    name = "read_file"
    description = (
        "读取工作目录中的文本文件内容。"
        "参数: path (str, 必填) 相对工作区的文件路径。"
    )

    def __init__(self, workspace: Path | None = None):
        self._workspace = (workspace or Path(".")).resolve()

    def run(self, args: dict) -> str:
        rel = args.get("path")
        if not rel or not isinstance(rel, str):
            return "Error: 缺少参数 path。"
        target = (self._workspace / rel).resolve()
        # 路径逃逸校验
        try:
            target.relative_to(self._workspace)
        except ValueError:
            return f"Error: 禁止访问工作目录之外的路径: {rel}"
        if not target.exists():
            return f"Error: 文件不存在: {rel}"
        if target.is_dir():
            return f"Error: {rel} 是目录，请用 search_code 浏览。"
        try:
            data = target.read_bytes()[:MAX_BYTES]
            text = data.decode("utf-8", errors="replace")
        except Exception as e:
            return f"Error: 读取失败: {e}"
        return f"[文件 {rel}，{len(data)} 字节]\n{text}"
