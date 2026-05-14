"""
文件操作工具 - FileRead, FileWrite, FileEdit
基于 DScode 的 FileReadTool, FileWriteTool, FileEditTool
"""

import os
import re
from pathlib import Path
from typing import Optional

from tools.base import Tool


class FileReadTool(Tool):
    """读取文件内容"""

    name = "read_file"
    description = "Read the contents of a file. Can read text files, code files, and display line numbers."

    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to read"
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-indexed)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read"
            }
        },
        "required": ["file_path"]
    }

    def execute(self, file_path: str, offset: int = 1, limit: int = 200) -> str:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}"
        if not path.is_file():
            return f"Error: Path is not a file: {file_path}"

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            start = max(0, offset - 1)
            end = min(total_lines, start + limit) if limit else total_lines
            selected = lines[start:end]

            result = []
            result.append(f"=== {file_path} (lines {start+1}-{end} of {total_lines}) ===\n")

            for i, line in enumerate(selected, start=start + 1):
                result.append(f"{i:6d}|{line.rstrip()}")

            return "\n".join(result)

        except Exception as e:
            return f"Error reading file: {str(e)}"


class FileWriteTool(Tool):
    """创建/覆盖文件"""

    name = "write_file"
    description = "Write content to a file. Creates the file if it doesn't exist, overwrites if it does."

    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to write"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            }
        },
        "required": ["file_path", "content"]
    }

    def execute(self, file_path: str, content: str) -> str:
        path = Path(file_path)

        try:
            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            size = len(content)
            return f"File written successfully: {file_path} ({size} bytes)"

        except Exception as e:
            return f"Error writing file: {str(e)}"


class FileEditTool(Tool):
    """文件局部修改（字符串替换）"""

    name = "edit_file"
    description = """Edit a file by replacing a specific string with a new string.
    Provide the exact old_string to replace and the new_string.
    The old_string must match exactly (including whitespace) in the file."""

    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to edit"
            },
            "old_string": {
                "type": "string",
                "description": "The exact text to replace"
            },
            "new_string": {
                "type": "string",
                "description": "The new text to replace it with"
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: false)"
            }
        },
        "required": ["file_path", "old_string", "new_string"]
    }

    def execute(self, file_path: str, old_string: str, new_string: str,
                replace_all: bool = False) -> str:
        path = Path(file_path)

        if not path.exists():
            return f"Error: File not found: {file_path}"

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            if old_string not in content:
                return f"Error: old_string not found in file. Make sure it matches exactly (including whitespace).\nFile: {file_path}"

            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"File edited successfully: {file_path}\nReplaced {count} occurrence(s)"

        except Exception as e:
            return f"Error editing file: {str(e)}"


class GlobTool(Tool):
    """文件模式匹配搜索"""

    name = "glob"
    description = "Search for files matching a glob pattern (e.g., '**/*.py', 'src/*.ts')"

    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match files"
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory)"
            }
        },
        "required": ["pattern"]
    }

    def execute(self, pattern: str, path: str = ".") -> str:
        base = Path(path)
        if not base.exists():
            return f"Error: Directory not found: {path}"

        try:
            matches = sorted(base.glob(pattern))
            if not matches:
                return f"No files matched pattern: {pattern}"

            # 限制结果数量
            max_results = 200
            results = []
            for m in matches[:max_results]:
                results.append(str(m))

            output = f"Found {len(matches)} file(s):\n" + "\n".join(results)
            if len(matches) > max_results:
                output += f"\n... and {len(matches) - max_results} more"

            return output

        except Exception as e:
            return f"Error searching files: {str(e)}"


class GrepTool(Tool):
    """内容搜索（基于正则）"""

    name = "grep"
    description = "Search for a regex pattern in files"

    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regular expression pattern to search for"
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory)"
            },
            "include": {
                "type": "string",
                "description": "File pattern to include (e.g., '*.py')"
            }
        },
        "required": ["pattern"]
    }

    def execute(self, pattern: str, path: str = ".", include: str = "*") -> str:
        base = Path(path)
        if not base.exists():
            return f"Error: Directory not found: {path}"

        try:
            results = []
            matched_files = 0
            max_files = 50

            for filepath in base.rglob(include):
                if not filepath.is_file():
                    continue
                if matched_files >= max_files:
                    break

                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if re.search(pattern, line):
                                results.append(f"{filepath}:{i}: {line.rstrip()}")
                                if len(results) >= 200:
                                    break
                except Exception:
                    continue

                if results:
                    matched_files += 1

            if not results:
                return f"No matches found for pattern: {pattern}"

            return f"Found {len(results)} match(es):\n" + "\n".join(results[:200])

        except Exception as e:
            return f"Error searching content: {str(e)}"
