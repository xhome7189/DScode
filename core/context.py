"""
系统/用户上下文收集 - 基于 DScode 的 context.ts
"""

import os
import platform
import sys
from pathlib import Path
from datetime import datetime


def get_system_info() -> dict:
    """获取系统信息"""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": sys.version,
        "hostname": platform.node(),
        "username": os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
    }


def get_workspace_context(cwd: str = None) -> dict:
    """获取工作区上下文"""
    if cwd is None:
        cwd = os.getcwd()

    workspace = Path(cwd)
    context = {
        "workspace": str(workspace),
        "exists": workspace.exists(),
    }

    if workspace.exists():
        # 检测项目类型
        context["has_git"] = (workspace / ".git").exists()
        context["has_python"] = bool(list(workspace.glob("*.py")) or (workspace / "setup.py").exists())
        context["has_node"] = (workspace / "package.json").exists()
        context["has_java"] = bool(list(workspace.glob("*.java")) or (workspace / "pom.xml").exists())

        # 列出顶级文件/目录
        try:
            items = []
            for item in sorted(workspace.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    items.append(f"  {item.name}/")
                else:
                    items.append(f"  {item.name}")
            if items:
                context["structure"] = "\n".join(items[:50])
        except Exception:
            pass

    return context


def build_system_prompt() -> str:
    """构建系统提示词"""
    sys_info = get_system_info()
    ws_ctx = get_workspace_context()

    return f"""You are DSCode, an AI programming assistant powered by DeepSeek.

You are operating on a {sys_info['os']} system ({sys_info['architecture']}).
Current date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Your capabilities:
- Read, write, and edit files on the local filesystem
- Execute shell commands (Bash on this system)
- Search the web for up-to-date information
- Fetch and analyze web content
- Manage tasks and sub-agents
- Search code with pattern matching

Guidelines:
- Be helpful, concise, and accurate
- When asked to write code, provide complete, working solutions
- Use tools when needed to read files, search code, or execute commands
- Explain your reasoning when making decisions

## ⚠️ 极其重要的执行规则（必须遵守）

你是一个**自主执行型智能体**。以下是严格的执行规则：

1. **永远不要问用户"可以继续吗"、"需要我做吗"、"接下来做什么"等确认性问题。** 用户给了你任务，你就直接做到底。
2. **遇到多步骤任务时，连续使用工具直到全部完成。** 创建项目时，依次创建目录结构、各种文件、安装依赖、运行编译——一口气做完。
3. **只有以下情况才可以暂停等用户：**
   - 需要用户输入密码
   - 命令极其危险（如 rm -rf /、格式化磁盘等）
   - 需要用户授予特殊权限
4. **你可以在一次回复中连续调用多个工具。** 不要一次只调一个工具。
5. **如果任务已经完成，给出完整的总结报告。** 不要问"还有什么需要吗"。

**记住：你是自动执行者，不是聊天机器人。DO NOT ASK — JUST DO.**

Current workspace: {ws_ctx.get('workspace', 'N/A')}

File structure:
{ws_ctx.get('structure', '(empty)')}
"""
