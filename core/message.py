"""
消息类型定义 - 适配 DeepSeek (OpenAI) 格式
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import json


@dataclass
class ContentBlock:
    """API 内容块，仅用于内部存储（text / tool_use / tool_result）"""
    type: str  # text, tool_use, tool_result
    text: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_id: Optional[str] = None
    tool_result: Optional[str] = None
    is_error: Optional[bool] = None


@dataclass
class Message:
    """对话消息，支持转为 DeepSeek (OpenAI) 兼容 API 格式"""
    role: str          # user, assistant, system, tool
    content: list[ContentBlock] = field(default_factory=list)
    id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_api_format(self) -> dict:
        """转换为 DeepSeek (OpenAI) 兼容的 API 格式"""
        text_parts = []
        tool_calls = []
        tool_result_id = None
        tool_result_content = ""

        for block in self.content:
            if block.type == "text":
                if block.text:
                    text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.tool_id or "",
                    "type": "function",
                    "function": {
                        "name": block.tool_name or "",
                        "arguments": json.dumps(block.tool_input or {}, ensure_ascii=False)
                    }
                })
            elif block.type == "tool_result":
                tool_result_id = block.tool_id
                tool_result_content = block.tool_result or ""

        # 1. 工具结果消息：role = "tool"
        if self.role == "user" and tool_result_id is not None:
            return {
                "role": "tool",
                "tool_call_id": tool_result_id,
                "content": tool_result_content
            }

        # 2. 包含工具调用的助手消息
        if self.role == "assistant" and tool_calls:
            return {
                "role": "assistant",
                "content": "\n".join(text_parts) if text_parts else None,
                "tool_calls": tool_calls
            }

        # 3. 普通文本消息（user / assistant / system）
        combined_text = "\n".join(text_parts) if text_parts else ""
        return {
            "role": self.role,
            "content": combined_text
        }

    # ---- 工厂方法 ----

    @classmethod
    def user_message(cls, text: str) -> "Message":
        """创建用户消息"""
        return cls(role="user", content=[ContentBlock(type="text", text=text)])

    @classmethod
    def assistant_message(cls, text: str) -> "Message":
        """创建纯文本助手消息"""
        return cls(role="assistant", content=[ContentBlock(type="text", text=text)])

    @classmethod
    def system_message(cls, text: str) -> "Message":
        """创建系统消息"""
        return cls(role="system", content=[ContentBlock(type="text", text=text)])

    @classmethod
    def tool_result(cls, tool_id: str, result: str, is_error: bool = False) -> "Message":
        """创建工具结果消息。内部 role='user' 但 to_api_format() 会转为 'tool'。"""
        return cls(
            role="user",
            content=[ContentBlock(
                type="tool_result",
                tool_id=tool_id,
                tool_result=result,
                is_error=is_error
            )]
        )

    @classmethod
    def tool_use_message(cls, tool_name: str, tool_input: dict, tool_id: str, text: str = "") -> "Message":
        """创建包含工具调用的助手消息"""
        blocks = []
        if text:
            blocks.append(ContentBlock(type="text", text=text))
        blocks.append(ContentBlock(
            type="tool_use",
            tool_name=tool_name,
            tool_input=tool_input,
            tool_id=tool_id
        ))
        return cls(role="assistant", content=blocks)
