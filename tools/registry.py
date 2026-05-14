"""
工具注册表 - 统一注册所有工具
"""

from tools.base import ToolRegistry
from tools.file_tools import FileReadTool, FileWriteTool, FileEditTool, GlobTool, GrepTool
from tools.bash_tool import BashTool
from tools.web_tools import WebSearchTool, WebFetchTool
from tools.task_tools import TaskCreateTool, TaskUpdateTool, TaskListTool
from tools.desktop_tool import (
    MouseClickTool, MouseMoveTool, TypeTextTool, PressKeyTool,
    FindWindowTool, LaunchAppTool, ScreenshotTool, GetScreenSizeTool,
    LocateImageTool, OcrScreenshotTool, FindTextOnScreenTool,
    ScanDesktopTool, HAS_PYAUTOGUI,
)


def create_registry() -> ToolRegistry:
    """创建并注册所有工具"""
    registry = ToolRegistry()

    # 文件操作
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileEditTool())
    registry.register(GlobTool())
    registry.register(GrepTool())

    # Bash
    registry.register(BashTool())

    # Web
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())

    # 任务管理
    registry.register(TaskCreateTool())
    registry.register(TaskUpdateTool())
    registry.register(TaskListTool())

    # 桌面自动化（鼠标、键盘、窗口、OCR）
    registry.register(MouseClickTool())
    registry.register(MouseMoveTool())
    registry.register(TypeTextTool())
    registry.register(PressKeyTool())
    registry.register(FindWindowTool())
    registry.register(LaunchAppTool())
    registry.register(ScreenshotTool())
    registry.register(GetScreenSizeTool())
    registry.register(ScanDesktopTool())
    registry.register(OcrScreenshotTool())
    registry.register(FindTextOnScreenTool())
    if HAS_PYAUTOGUI:
        registry.register(LocateImageTool())

    return registry
