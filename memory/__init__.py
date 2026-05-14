"""
记忆管理器 - 基于 DScode 的 memory 系统
实现对话历史的持久化存储和加载
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import MEMORY_DIR, BASE_DIR
from core.message import Message, ContentBlock


class MemoryManager:
    """会话记忆管理器"""

    def __init__(self, memory_dir: Path = None):
        self.memory_dir = memory_dir or MEMORY_DIR
        self.memory_dir.mkdir(exist_ok=True)

    def save_session(self, session_id: str, messages: list[Message],
                     metadata: dict = None) -> str:
        """保存会话"""
        data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
            "messages": []
        }

        for msg in messages:
            msg_data = {
                "role": msg.role,
                "id": msg.id,
                "timestamp": msg.timestamp,
                "content": []
            }
            for block in msg.content:
                msg_data["content"].append({
                    "type": block.type,
                    "text": block.text,
                    "tool_name": block.tool_name,
                    "tool_input": block.tool_input,
                    "tool_id": block.tool_id,
                    "tool_result": block.tool_result,
                    "is_error": block.is_error,
                })
            data["messages"].append(msg_data)

        filepath = self.memory_dir / f"{session_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return str(filepath)

    def load_session(self, session_id: str) -> Optional[tuple[list[Message], dict]]:
        """加载会话"""
        filepath = self.memory_dir / f"{session_id}.json"

        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = []
        for msg_data in data.get("messages", []):
            content = []
            for block_data in msg_data.get("content", []):
                content.append(ContentBlock(
                    type=block_data["type"],
                    text=block_data.get("text"),
                    tool_name=block_data.get("tool_name"),
                    tool_input=block_data.get("tool_input"),
                    tool_id=block_data.get("tool_id"),
                    tool_result=block_data.get("tool_result"),
                    is_error=block_data.get("is_error"),
                ))
            messages.append(Message(
                role=msg_data["role"],
                content=content,
                id=msg_data.get("id", ""),
                timestamp=msg_data.get("timestamp", ""),
            ))

        return messages, data.get("metadata", {})

    def list_sessions(self) -> list[dict]:
        """列出所有会话，按 timestamp 降序排列（最新的在前）"""
        sessions = []
        for filepath in self.memory_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ts = data.get("timestamp", "")
                sessions.append({
                    "session_id": data["session_id"],
                    "timestamp": ts,
                    "message_count": len(data.get("messages", [])),
                    "metadata": data.get("metadata", {}),
                })
            except Exception:
                pass
        # 按 timestamp 降序，timestamp 为空或解析失败的排最后
        def sort_key(s):
            try:
                return datetime.fromisoformat(s["timestamp"])
            except Exception:
                return datetime.min
        sessions.sort(key=sort_key, reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        filepath = self.memory_dir / f"{session_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False
