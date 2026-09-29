"""工具集合：Agent 可调用的能力。"""
from .base import Tool
from .python_runner import PythonRunner
from .file_reader import FileReader
from .code_search import CodeSearch

__all__ = ["Tool", "PythonRunner", "FileReader", "CodeSearch", "build_default_tools"]


def build_default_tools(config) -> list[Tool]:
    """根据配置构建默认工具集。"""
    return [
        PythonRunner(timeout=config.code_timeout, workspace=config.workspace),
        FileReader(workspace=config.workspace),
        CodeSearch(workspace=config.workspace),
    ]
