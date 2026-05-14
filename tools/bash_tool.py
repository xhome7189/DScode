"""
Bash/Shell 命令执行工具 - 基于 DScode 的 BashTool
"""

import subprocess
import os
import signal
import threading
from pathlib import Path

from tools.base import Tool
from config import BASH_TIMEOUT, MAX_BASH_OUTPUT

# 全局停止信号（由 QueryEngine.stop() 设置）
_stop_event = threading.Event()


def signal_stop():
    """通知所有 BashTool 停止"""
    _stop_event.set()


def clear_stop():
    """清除停止信号"""
    _stop_event.clear()


class BashTool(Tool):
    """Shell 命令执行"""

    name = "bash"
    description = """Execute a shell command. Use this to run commands, build projects, 
    manage files, install packages, etc. Returns stdout and stderr output."""

    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute"
            },
            "description": {
                "type": "string",
                "description": "Brief description of what this command does"
            },
            "timeout": {
                "type": "integer",
                "description": f"Timeout in milliseconds (default: {BASH_TIMEOUT})"
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for the command"
            }
        },
        "required": ["command"]
    }

    def __init__(self):
        self._process = None

    def execute(self, command: str, description: str = "",
                timeout: int = None, working_dir: str = None) -> str:
        if timeout is None:
            timeout = BASH_TIMEOUT

        cwd = working_dir or os.getcwd()

        # 检测危险命令
        dangerous_patterns = [
            "rm -rf /", "rm -rf ~", "rm -rf .",
            "mkfs.", "dd if=",
            ":(){ :|:& };:",  # fork bomb
            "shutdown", "reboot", "halt",
            "chmod 777 /",
        ]
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                return f"Error: Dangerous command detected. The pattern '{pattern}' is blocked for safety."

        try:
            # 使用 Popen 以便能终止进程
            if os.name == "nt":
                git_bash = r"C:\Program Files\Git\bin\bash.exe"
                if os.path.exists(git_bash):
                    self._process = subprocess.Popen(
                        [git_bash, "-c", command],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=cwd,
                        env={**os.environ, "HOME": os.environ.get("USERPROFILE", "")}
                    )
                else:
                    self._process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=cwd
                    )
            else:
                self._process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    executable="/bin/bash"
                )

            # 等待完成，同时检测停止信号
            try:
                stdout, stderr = self._process.communicate(timeout=timeout / 1000)
            except subprocess.TimeoutExpired:
                self._kill_process()
                return f"Error: Command timed out after {timeout}ms"
            except KeyboardInterrupt:
                self._kill_process()
                return "Error: Command cancelled"

            # 手动解码
            def safe_decode(data: bytes) -> str:
                if data is None:
                    return ""
                try:
                    return data.decode("utf-8", errors="replace")
                except UnicodeDecodeError:
                    return data.decode("gbk", errors="replace")

            stdout_str = safe_decode(stdout)[:MAX_BASH_OUTPUT]
            stderr_str = safe_decode(stderr)[:MAX_BASH_OUTPUT]

            result = []
            if stdout_str:
                result.append(f"STDOUT:\n{stdout_str}")
            if stderr_str:
                result.append(f"STDERR:\n{stderr_str}")
            if self._process.returncode != 0:
                result.append(f"\nExit code: {self._process.returncode}")
            if not result:
                result.append("Command executed successfully (no output)")

            return "\n".join(result)

        except Exception as e:
            self._kill_process()
            return f"Error executing command: {str(e)}"

    def _kill_process(self):
        """终止当前进程"""
        if self._process and self._process.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                    capture_output=True, timeout=5
                )
            else:
                self._process.kill()
            self._process = None
