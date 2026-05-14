"""
工具基类 - 基于 DScode 的 Tool.ts
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional


class Tool(ABC):
    """工具基类"""

    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """执行工具"""
        pass

    def get_definition(self) -> dict:
        """获取 OpenAI/DeepSeek 工具定义格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def can_use(self) -> bool:
        """检查工具是否可用"""
        return True


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._hooks: dict[str, list[Callable]] = {
            "before_execute": [],
            "after_execute": [],
        }

    def register(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool

    def unregister(self, name: str):
        """注销工具"""
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def get_tool_definitions(self) -> list[dict]:
        """获取所有可用工具的定义"""
        return [tool.get_definition() for tool in self._tools.values() if tool.can_use()]

    def execute(self, name: str, arguments: dict) -> str:
        """执行工具"""
        tool = self.get(name)
        if not tool:
            return f"Tool '{name}' not found. Available tools: {list(self._tools.keys())}"

        if not tool.can_use():
            return f"Tool '{name}' is not available"

        # 执行前钩子
        for hook in self._hooks["before_execute"]:
            hook(name, arguments)

        try:
            result = tool.execute(**arguments)
        except TypeError as e:
            return f"Tool '{name}' parameter error: {str(e)}. Expected: {tool.parameters}"
        except Exception as e:
            return f"Tool '{name}' execution failed: {str(e)}"

        # 执行后钩子
        for hook in self._hooks["after_execute"]:
            hook(name, result)

        return result

    def add_hook(self, event: str, callback: Callable):
        """添加钩子"""
        if event in self._hooks:
            self._hooks[event].append(callback)

    def list_tools(self) -> list[str]:
        """列出所有工具名"""
        return list(self._tools.keys())
