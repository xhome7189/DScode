"""
DeepSeek API 查询引擎 - 基于 DScode 的 QueryEngine.ts
处理流式响应、工具调用循环、对话管理
"""

import json
import time
import uuid
import sys
import threading
import traceback
from typing import Callable, Optional, Generator

import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from core.message import Message, ContentBlock
from core.context import build_system_prompt
from tools.bash_tool import signal_stop, clear_stop

# 提高递归限制，防止深度流式响应处理时超限
sys.setrecursionlimit(5000)


class QueryEngine:
    """DeepSeek API 查询引擎"""

    def __init__(self, tools_registry=None, max_retries: int = 3, retry_delay: float = 2.0):
        self.api_key = DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL
        self.model = DEEPSEEK_MODEL
        self.tools_registry = tools_registry
        self.messages: list[Message] = []
        self.total_tokens = {"prompt": 0, "completion": 0}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._stop_event = threading.Event()
        self._current_api_response = None  # 当前 API 响应用来关闭连接

    def _build_system_message(self) -> dict:
        """构建系统消息"""
        return {"role": "system", "content": build_system_prompt()}

    def _get_tool_definitions(self) -> list[dict]:
        """获取工具定义列表"""
        if not self.tools_registry:
            return []
        return self.tools_registry.get_tool_definitions()

    def _is_retryable_error(self, status_code: int) -> bool:
        """判断是否为可重试的 HTTP 状态码"""
        return status_code in [429, 500, 502, 503, 504]

    def _make_api_request(self, messages: list[dict], stream: bool = True,
                          callback: Callable = None) -> str:
        """向 DeepSeek API 发送请求（支持自动重试）"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.7,
            "max_tokens": 8192,
        }

        tools = self._get_tool_definitions()
        if tools:
            payload["tools"] = tools

        self._current_api_response = None
        last_exception = None
        for attempt in range(self.max_retries + 1):
            if self._is_stopped():
                raise Exception("已停止")
            try:
                response = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    stream=stream,
                    timeout=120
                )
                self._current_api_response = response

                if response.ok:
                    if stream:
                        return self._handle_stream(response, callback)
                    else:
                        return self._handle_non_stream(response)

                # 处理非 2xx 响应
                status_code = response.status_code
                error_text = response.text[:500]

                # 503/429/5xx 临时错误自动重试
                if self._is_retryable_error(status_code) and attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    if callback:
                        callback("retry", {
                            "attempt": attempt + 1,
                            "status_code": status_code,
                            "wait": wait_time,
                            "message": f"API 繁忙 ({status_code})，{wait_time:.1f}秒后重试..."
                        })
                    time.sleep(wait_time)
                    if self._is_stopped():
                        raise Exception("已停止")
                    last_exception = Exception(f"API 请求失败: {status_code} - {error_text}")
                    continue

                # 不可重试的错误直接抛出
                raise Exception(f"API 请求失败: {status_code} - {error_text}")

            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    if callback:
                        callback("retry", {
                            "attempt": attempt + 1,
                            "status_code": "timeout",
                            "wait": wait_time,
                            "message": f"请求超时，{wait_time:.1f}秒后重试..."
                        })
                    time.sleep(wait_time)
                    if self._is_stopped():
                        raise Exception("已停止")
                    last_exception = Exception("请求超时")
                    continue
                raise Exception("请求超时，多次重试后仍然失败")

            except requests.exceptions.ConnectionError as e:
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    if callback:
                        callback("retry", {
                            "attempt": attempt + 1,
                            "status_code": "connection_error",
                            "wait": wait_time,
                            "message": f"连接错误，{wait_time:.1f}秒后重试..."
                        })
                    time.sleep(wait_time)
                    if self._is_stopped():
                        raise Exception("已停止")
                    last_exception = e
                    continue
                raise Exception(f"连接错误，多次重试后仍然失败: {e}")

        # 所有重试都用完了
        if last_exception:
            raise Exception(f"达到最大重试次数 ({self.max_retries})，请稍后重试或检查 API 状态")
        raise Exception("未知错误")

    def _handle_stream(self, response, callback: Callable = None) -> str:
        """处理流式响应"""
        full_text = ""
        tool_calls = []

        try:
            for line in response.iter_lines(decode_unicode=True):
                if self._is_stopped():
                    break
                if not line or not line.startswith("data: "):
                    continue
                # ... rest of streaming handler ...
                data_str = line[6:]
                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                choices = data.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})

                if "content" in delta and delta["content"]:
                    text_chunk = delta["content"]
                    full_text += text_chunk
                    if callback:
                        callback("text", text_chunk)

                if "tool_calls" in delta:
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        tc_id = tc.get("id", "")
                        tc_func = tc.get("function", {})

                        while len(tool_calls) <= idx:
                            tool_calls.append({
                                "id": "",
                                "name": "",
                                "arguments": ""
                            })

                        if tc_id:
                            tool_calls[idx]["id"] = tc_id
                        if tc_func.get("name"):
                            tool_calls[idx]["name"] = tc_func["name"]
                        if tc_func.get("arguments"):
                            tool_calls[idx]["arguments"] += tc_func["arguments"]

                if "usage" in data:
                    self.total_tokens["prompt"] += data["usage"].get("prompt_tokens", 0)
                    self.total_tokens["completion"] += data["usage"].get("completion_tokens", 0)
        except (AttributeError, requests.exceptions.ConnectionError):
            # 连接被主动关闭（停止操作）时忽略异常
            pass
        except Exception:
            # 其他流式处理异常忽略
            pass

        if tool_calls and callback:
            callback("tool_calls", tool_calls)

        return full_text, tool_calls

    def _handle_non_stream(self, response) -> str:
        """处理非流式响应"""
        data = response.json()
        choice = data["choices"][0]
        message = choice.get("message", {})

        text = message.get("content", "")
        tool_calls = message.get("tool_calls", [])

        if "usage" in data:
            self.total_tokens["prompt"] += data["usage"].get("prompt_tokens", 0)
            self.total_tokens["completion"] += data["usage"].get("completion_tokens", 0)

        return text, tool_calls

    def chat(self, user_message: str, callback: Callable = None,
             max_tool_rounds: int = 50) -> str:
        """发起对话，支持自动工具调用循环"""
        self._stop_event.clear()
        clear_stop()

        user_msg = Message.user_message(user_message)
        self.messages.append(user_msg)

        api_messages = [self._build_system_message()]
        for msg in self.messages:
            api_messages.append(msg.to_api_format())

        full_response = ""
        auto_continue_count = 0

        for round_num in range(max_tool_rounds):
            if self._is_stopped():
                break
            if callback:
                callback("thinking", None)

            text, tool_calls = self._make_api_request(api_messages, stream=True, callback=callback)

            # ---- 模型返回无工具调用：检测是否在"问确认"----
            if not tool_calls:
                if text and auto_continue_count < 3 and self._is_asking_confirmation(text):
                    # 问确认 → 不把确认文本加入最终回复，注入继续指令
                    auto_continue_count += 1
                    auto_msg = Message.user_message("CONTINUE executing the task. Do NOT ask questions. Just finish everything.")
                    self.messages.append(auto_msg)
                    api_messages.append(auto_msg.to_api_format())
                    continue  # 继续下一轮
                # 不是确认性问题 → 真做完了，把文本加入最终回复
                if text:
                    full_response += text
                break

            # 有工具调用，累积文本
            if text:
                full_response += text

            # ---- 构造工具调用 + 执行工具（合并为单循环，确保 tool_id 一致）----
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                arguments = self._safe_parse_json(tc.get("arguments", "{}"))
                tool_id = tc.get("id", str(uuid.uuid4()))

                # 1. 助手消息（包含工具调用）
                assistant_msg = Message.tool_use_message(
                    tool_name=tool_name,
                    tool_input=arguments,
                    tool_id=tool_id,
                    text=""
                )
                self.messages.append(assistant_msg)
                api_messages.append(assistant_msg.to_api_format())

                # 2. 执行工具
                if callback:
                    callback("tool_start", {"name": tool_name, "input": arguments, "id": tool_id})

                try:
                    if self.tools_registry:
                        result_text = self.tools_registry.execute(tool_name, arguments)
                    else:
                        result_text = f"Tool '{tool_name}' not available"
                    is_error = False
                except Exception as e:
                    result_text = f"Error: {str(e)}"
                    is_error = True

                if callback:
                    callback("tool_end", {"name": tool_name, "result": result_text[:500], "id": tool_id})

                # 3. 工具结果（role: tool, tool_call_id 与上面 tool_id 一致）
                result_msg = Message.tool_result(tool_id, result_text[:5000], is_error)
                self.messages.append(result_msg)
                api_messages.append(result_msg.to_api_format())

            # 不在每轮注入继续指令，避免无限循环。
            # 仅在模型主动停顿时（上面 not tool_calls 分支）注入一次。

        if full_response:
            self.messages.append(Message.assistant_message(full_response))

        return full_response

    def _safe_parse_json(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    def reset(self):
        self.messages = []
        self.total_tokens = {"prompt": 0, "completion": 0}
        self._stop_event.clear()
        clear_stop()

    def get_cost(self) -> dict:
        input_price = 0.14
        output_price = 0.28
        input_cost = (self.total_tokens["prompt"] / 1_000_000) * input_price
        output_cost = (self.total_tokens["completion"] / 1_000_000) * output_price
        return {
            "total_tokens": self.total_tokens,
            "total_cost_usd": input_cost + output_cost,
            "total_cost_cny": (input_cost + output_cost) * 7.2
        }

    def stop(self):
        """停止当前执行"""
        self._stop_event.set()
        signal_stop()  # 同时通知 BashTool 终止进程
        if self._current_api_response:
            try:
                self._current_api_response.close()
            except Exception:
                pass

    def _is_stopped(self) -> bool:
        return self._stop_event.is_set()

    @staticmethod
    def _is_asking_confirmation(text: str) -> bool:
        """检测模型回复是否在问确认（而非真做完）"""
        if not text:
            return False
        t = text.strip().lower()

        # 问句特征（以问号结尾）
        if t.endswith("?"):
            return True

        # 中文确认特征
        confirm_phrases = [
            "是否可以", "可以继续", "需要我", "要我继续",
            "是否继续", "要不要", "你觉得", "你认为",
            "请确认", "请问", "应该继续", "接下来",
            "下一步", "还需", "还要", "有什么需要",
            "还有什么", "吗？", "么？",
        ]
        for phrase in confirm_phrases:
            if phrase in t:
                return True

        # 英文确认特征
        eng_phrases = [
            "should i", "would you like", "do you want",
            "shall i", "can i", "may i", "continue?",
            "proceed", "next step", "what's next",
            "need me to", "shall we",
        ]
        for phrase in eng_phrases:
            if phrase in t:
                return True

        # 短文本 + 包含继续性词汇（且不是明显的完成信号）
        if len(t) < 60:
            complete_words = ["全部完成", "已完成", "已创建完成", "构建成功", "部署成功", "all done", "completed"]
            if any(w in t for w in complete_words):
                return False
            if any(w in t for w in ["继续", "下一步"]):
                return True

        return False
