"""
DSCode - CustomTkinter 纯 Windows 桌面版
主要聊天窗口界面
"""

import threading
import uuid
import re
import queue
import os
import sys
import traceback
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import customtkinter as ctk

# 设置 CustomTkinter 外观（白色主题）
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

from core.query_engine import QueryEngine
from core.message import Message
from tools.registry import create_registry
from memory import MemoryManager
from config import BASE_DIR

# 报告保存目录
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# 错误日志目录
ERROR_LOG_DIR = BASE_DIR / "logs"
ERROR_LOG_DIR.mkdir(exist_ok=True)


def _log_error(context: str):
    """记录错误到日志文件（except 块中的吞掉错误也记录）"""
    try:
        log_path = ERROR_LOG_DIR / f"error_{datetime.now().strftime('%Y%m%d')}.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] [{context}]\n")
            traceback.print_exc(file=f)
            f.write("\n")
    except Exception:
        pass

# ── 颜色常量（白色主题）──
COLOR_BG = "#f5f5f5"
COLOR_SIDEBAR = "#ffffff"
COLOR_HEADER = "#fafafa"
COLOR_INPUT = "#ffffff"
COLOR_CODE_BG = "#f0f0f0"
COLOR_BORDER = "#e0e0e0"
COLOR_ACCENT = "#6366f1"
COLOR_ACCENT_HOVER = "#818cf8"
COLOR_TEXT = "#1f2937"
COLOR_TEXT_SECONDARY = "#6b7280"
COLOR_TEXT_MUTED = "#9ca3af"
COLOR_USER_BUBBLE = "#e8eaff"
COLOR_SUCCESS = "#059669"
COLOR_ERROR = "#dc2626"
COLOR_WARNING = "#d97706"
COLOR_TOOL = "#6366f1"


class ChatWindow(ctk.CTk):
    """主聊天窗口"""

    def __init__(self):
        super().__init__()

        self.title("DSCode")
        self.geometry("1200x800")
        self.minsize(900, 600)

        # 核心组件
        self.registry = create_registry()
        self.engine = QueryEngine(tools_registry=self.registry, max_retries=3, retry_delay=2.0)
        self.memory_manager = MemoryManager()

        # 状态
        self.is_sending = False
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._streaming_active = False
        self.api_thread = None
        self.stop_streaming = False
        self._active_session_id = None

        # 构建 UI
        self._build_ui()

        # 绑定关闭事件
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ═══════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════

    def _build_ui(self):
        """构建完整 UI"""
        # Grid 布局
        self.grid_columnconfigure(0, weight=0)  # sidebar
        self.grid_columnconfigure(1, weight=1)  # main
        self.grid_rowconfigure(0, weight=1)

        # ── 侧边栏 ──
        self.sidebar = ctk.CTkFrame(self, width=260, fg_color=COLOR_SIDEBAR, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self._build_sidebar()

        # ── 主区域 ──
        self.main_area = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(1, weight=1)  # 聊天区可拉伸

        self._build_header()
        self._build_chat_display()
        self._build_input_area()

    def _build_sidebar(self):
        """构建侧边栏"""
        # ── 标题 ──
        title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_frame.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(
            title_frame, text="🔮 DSCode",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_ACCENT_HOVER
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame, text="v1.0.0",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w")

        # ── 按钮 ──
        btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=8)

        btn_style = {
            "height": 32, "corner_radius": 6,
            "fg_color": COLOR_INPUT, "text_color": COLOR_TEXT,
            "hover_color": COLOR_HEADER, "border_width": 1,
            "border_color": COLOR_BORDER, "font": ctk.CTkFont(size=12)
        }

        self.btn_new = ctk.CTkButton(btn_frame, text="＋ 新会话", command=self._new_session, **btn_style)
        self.btn_new.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_save = ctk.CTkButton(btn_frame, text="💾 保存", command=self._save_session, **btn_style)
        self.btn_save.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # ── 会话列表 ──
        ctk.CTkLabel(
            self.sidebar, text="会话历史",
            font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=16, pady=(4, 4))

        self.session_frame = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent",
            corner_radius=0
        )
        self.session_frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self._refresh_session_list()

        # ── 底部统计 ──
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=80)
        footer.pack(fill="x", padx=16, pady=8)
        footer.pack_propagate(False)

        stats = [
            ("Token:", "0", "stat_tokens"),
            ("费用:", "¥0", "stat_cost"),
            ("模型:", "deepseek-chat", "stat_model"),
            ("工具:", f"{len(self.registry.list_tools())} 个", "stat_tools"),
        ]
        for label, value, attr_name in stats:
            row = ctk.CTkFrame(footer, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=11),
                         text_color=COLOR_TEXT_MUTED).pack(side="left")
            lbl = ctk.CTkLabel(row, text=value, font=ctk.CTkFont(size=11, weight="bold"),
                               text_color=COLOR_TEXT_SECONDARY)
            lbl.pack(side="right")
            setattr(self, attr_name, lbl)

    def _build_header(self):
        """构建顶部栏"""
        header = ctk.CTkFrame(self.main_area, fg_color=COLOR_HEADER, height=44, corner_radius=0)
        header.grid(row=0, column=0, sticky="new")
        header.grid_propagate(False)

        # Badge
        badge = ctk.CTkLabel(
            header, text="  DeepSeek Chat  ",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_ACCENT_HOVER,
            fg_color=COLOR_SIDEBAR, corner_radius=8
        )
        badge.pack(side="left", padx=16, pady=8)

        # 工具数
        self.header_tool_count = ctk.CTkLabel(
            header, text=f"{len(self.registry.list_tools())} 个工具可用",
            font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED
        )
        self.header_tool_count.pack(side="left", padx=8)

        # 右侧按钮
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right", padx=12)

        btn_s = {"height": 28, "font": ctk.CTkFont(size=12),
                 "fg_color": "transparent", "text_color": COLOR_TEXT_SECONDARY,
                 "hover_color": COLOR_INPUT, "border_width": 1, "border_color": COLOR_BORDER,
                 "corner_radius": 6}

        ctk.CTkButton(btn_frame, text="🔄 重置", command=self._reset_chat, **btn_s).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="📂 加载", command=self._refresh_session_list, **btn_s).pack(side="left", padx=2)

    def _build_chat_display(self):
        """构建消息显示区"""
        # 使用 CTkTextbox 作为聊天显示
        self.chat_display = ctk.CTkTextbox(
            self.main_area,
            fg_color=COLOR_BG,
            text_color=COLOR_TEXT,
            font=ctk.CTkFont(size=14),
            wrap="word",
            corner_radius=0,
            border_width=0
        )
        self.chat_display.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        # 配置 tag 样式
        self._configure_tags()

        # 欢迎消息
        self._insert_welcome_message()

    def _configure_tags(self):
        """配置 Text widget 的 tag 样式"""
        text_widget = self.chat_display._textbox

        # 标题 tag
        text_widget.tag_configure("title",
            font=ctk.CTkFont(size=18, weight="bold"),
            foreground=COLOR_ACCENT_HOVER,
            spacing3=8)

        # 用户消息
        text_widget.tag_configure("user_label",
            font=ctk.CTkFont(size=12, weight="bold"),
            foreground="#6366f1",
            spacing1=12, spacing3=2,
            lmargin1=20, lmargin2=20)

        text_widget.tag_configure("user_content",
            font=ctk.CTkFont(size=14),
            foreground=COLOR_TEXT,
            spacing1=2, spacing3=8,
            lmargin1=20, lmargin2=20)

        # 助手消息
        text_widget.tag_configure("assistant_label",
            font=ctk.CTkFont(size=12, weight="bold"),
            foreground=COLOR_SUCCESS,
            spacing1=12, spacing3=2,
            lmargin1=20, lmargin2=20)

        text_widget.tag_configure("assistant_content",
            font=ctk.CTkFont(size=14),
            foreground=COLOR_TEXT,
            spacing1=2, spacing3=8,
            lmargin1=20, lmargin2=20)

        text_widget.tag_configure("streaming",
            font=ctk.CTkFont(size=14),
            foreground=COLOR_TEXT,
            spacing1=2, spacing3=8,
            lmargin1=20, lmargin2=20)

        # 代码块
        text_widget.tag_configure("code_block",
            font=ctk.CTkFont(family="Consolas", size=13),
            foreground=COLOR_TEXT,
            background=COLOR_CODE_BG,
            spacing1=6, spacing3=6,
            lmargin1=24, lmargin2=24,
            rmargin=24)

        text_widget.tag_configure("code_inline",
            font=ctk.CTkFont(family="Consolas", size=13),
            foreground="#f472b6",
            background=COLOR_CODE_BG)

        # 工具指示器
        text_widget.tag_configure("tool_call",
            font=ctk.CTkFont(size=12),
            foreground=COLOR_TOOL,
            spacing1=4, spacing3=2,
            lmargin1=20, lmargin2=20)

        text_widget.tag_configure("tool_done",
            font=ctk.CTkFont(size=12),
            foreground=COLOR_SUCCESS,
            spacing1=2, spacing3=4,
            lmargin1=20, lmargin2=20)

        text_widget.tag_configure("tool_error",
            font=ctk.CTkFont(size=12),
            foreground=COLOR_ERROR,
            spacing1=2, spacing3=4,
            lmargin1=20, lmargin2=20)

        # 错误消息
        text_widget.tag_configure("error_msg",
            font=ctk.CTkFont(size=13),
            foreground=COLOR_ERROR,
            spacing1=4, spacing3=6,
            lmargin1=20, lmargin2=20)

        # 重试信息
        text_widget.tag_configure("retry_msg",
            font=ctk.CTkFont(size=12),
            foreground=COLOR_WARNING,
            spacing1=2, spacing3=2,
            lmargin1=20, lmargin2=20)

        # 单独
        text_widget.tag_configure("separator",
            foreground=COLOR_BORDER,
            spacing1=4, spacing3=4,
            lmargin1=10, lmargin2=10)

        # 时间戳
        text_widget.tag_configure("timestamp",
            font=ctk.CTkFont(size=10),
            foreground=COLOR_TEXT_MUTED,
            spacing1=2, spacing3=0,
            lmargin1=24, lmargin2=24)

        # 系统消息
        text_widget.tag_configure("system_msg",
            font=ctk.CTkFont(size=12, slant="italic"),
            foreground=COLOR_TEXT_MUTED,
            spacing1=6, spacing3=6)

        # 可点击文件链接
        text_widget.tag_configure("filelink",
            font=ctk.CTkFont(size=12, underline=True),
            foreground=COLOR_ACCENT_HOVER,
            spacing1=4, spacing3=4)

    def _insert_welcome_message(self):
        """插入欢迎消息"""
        tw = self.chat_display._textbox
        tw.configure(state="normal")

        tw.insert("end", "\n", "separator")
        tw.insert("end", "🔮  DSCode\n", "title")
        tw.insert("end", "你好！我是 DSCode，你的 AI 编程助手。\n\n", "assistant_content")
        tw.insert("end", "我可以帮你：\n", "assistant_content")
        tw.insert("end", "  📝 读写和编辑文件\n", "assistant_content")
        tw.insert("end", "  💻 执行命令和脚本\n", "assistant_content")
        tw.insert("end", "  🔍 搜索代码和文件\n", "assistant_content")
        tw.insert("end", "  🌐 网络搜索和内容抓取\n", "assistant_content")
        tw.insert("end", "  📋 任务管理和追踪\n\n", "assistant_content")

        tw.configure(state="disabled")
        # 滚动到底部
        tw.see("end")

    def _build_input_area(self):
        """构建输入区域"""
        input_frame = ctk.CTkFrame(self.main_area, fg_color=COLOR_SIDEBAR, height=160, corner_radius=0)
        input_frame.grid(row=2, column=0, sticky="sew")
        input_frame.grid_propagate(False)
        input_frame.grid_columnconfigure(0, weight=1)

        # 输入框容器
        inner = ctk.CTkFrame(input_frame, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 20))
        inner.grid_columnconfigure(0, weight=1)

        # 输入框
        self.input_text = ctk.CTkTextbox(
            inner, height=88, fg_color=COLOR_INPUT,
            text_color=COLOR_TEXT, font=ctk.CTkFont(size=14),
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=8, wrap="word"
        )
        self.input_text.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.input_text._textbox.configure(relief="flat", highlightthickness=0)
        self.input_text.bind("<KeyRelease>", self._auto_resize_input)

        # 发送按钮
        self.send_btn = ctk.CTkButton(
            inner, text="➤", width=44, height=88,
            font=ctk.CTkFont(size=18),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="white", corner_radius=22,
            command=self._send_message
        )
        self.send_btn.grid(row=0, column=1, sticky="e")

        # 绑定快捷键：输入框按 Enter 发送，Shift+Enter 换行
        self.input_text.bind("<Return>", lambda e: self._on_enter(e))

    def _auto_resize_input(self, event=None):
        """自动调整输入框高度"""
        # 由 grid_propagate 控制，简单起见固定高度
        pass

    def _on_enter(self, event):
        """Enter 发送，Shift+Enter 换行"""
        try:
            if not event.state & 0x1:  # 没有按 Shift
                self._send_message()
                return "break"
        except Exception:
            _log_error("handler")

    # ═══════════════════════════════════════════
    #  消息发送 / 接收
    # ═══════════════════════════════════════════

    def _send_message(self):
        """发送消息 - 发送中点击则停止"""
        try:
            if self.is_sending:
                # 点击停止按钮
                self.stop_streaming = True
                self.engine.stop()
                self.is_sending = False
                self.send_btn.configure(text="➤", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
                return

            text = self.input_text.get("1.0", "end-1c").strip()
            if not text:
                return

            self.input_text.delete("1.0", "end")
            self.is_sending = True
            self._streaming_active = False
            self.send_btn.configure(text="■", fg_color=COLOR_ERROR, hover_color="#dc2626")

            # 显示用户消息
            self._display_user_message(text)

            # 创建流式容器
            self._create_streaming_container()

            # 后台线程调用 API
            self.stop_streaming = False
            self.api_thread = threading.Thread(
                target=self._api_call_thread,
                args=(text,),
                daemon=True
            )
            self.api_thread.start()
        except Exception:
            _log_error("_send_message")

    def _api_call_thread(self, user_message: str):
        """API 调用线程（后台）"""
        try:
            self.engine.chat(user_message, callback=self._handle_api_event)
        except Exception as e:
            err_msg = str(e) or "API 响应异常（返回空结果）"
            if "已停止" in err_msg:
                err_msg = "⏹ 已停止"
            self._schedule_ui_update(lambda m=err_msg: self._display_error(m))
        finally:
            self._schedule_ui_update(self._on_api_done)

    def _handle_api_event(self, event_type: str, data):
        """处理 API 事件回调（在后台线程中调用）"""
        try:
            if event_type == "text" and data:
                self._schedule_ui_update(lambda d=data: self._append_stream_text(d))

            elif event_type == "tool_start":
                name = data.get("name", "")
                self._schedule_ui_update(lambda n=name: self._show_tool_start(n))

            elif event_type == "tool_end":
                name = data.get("name", "")
                self._schedule_ui_update(lambda n=name: self._show_tool_end(n))

            elif event_type == "retry":
                msg = data.get("message", "")
                self._schedule_ui_update(lambda m=msg: self._show_retry(m))

            elif event_type == "error":
                msg = data.get("content", str(data)) if data else "API 响应异常"
                self._schedule_ui_update(lambda m=msg: self._display_error(m))

            # tool_calls 事件是内部事件，不需要前端展示
        except Exception as e:
            _log_error("_handle_api_event")
            pass  # 回调异常不影响引擎继续执行

    def _schedule_ui_update(self, callback):
        """调度 UI 更新到主线程（安全执行，异常不崩溃窗口）"""
        if self.stop_streaming:
            return
        # 包装回调，防止任何异常导致 tkinter 主循环崩溃
        def safe_wrapper():
            try:
                callback()
            except Exception:
                _log_error("safe_wrapper")
        try:
            self.after(0, safe_wrapper)
        except Exception:
            _log_error("schedule_ui_update_after")

    def _on_api_done(self):
        """API 调用完成后的 UI 恢复"""
        self.is_sending = False
        self._streaming_active = False
        self.send_btn.configure(text="➤", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self._update_stats()
        # 自动保存会话
        self._auto_save()
        # 自动生成工作报告
        self._generate_report()

    def _auto_save(self):
        """即时保存当前会话到本地并刷新列表"""
        if not self.engine.messages:
            return
        try:
            name = f"auto_{self.current_session_id}"
            self.memory_manager.save_session(
                name, self.engine.messages,
                metadata={"timestamp": datetime.now().isoformat(), "auto": True}
            )
            # 即时刷新侧边栏会话列表（耗时很少）
            self._refresh_session_list()
        except Exception:
            _log_error("_auto_save")

    def _generate_report(self):
        """工作结束后自动生成工作报告 .md 并显示可点击链接"""
        if not self.engine.messages:
            return
        try:
            msgs = self.engine.messages
            now = datetime.now()

            # 提取信息
            user_count = sum(1 for m in msgs if m.role == "user" and any(b.type == "text" and b.text for b in m.content))
            assistant_last = ""
            for m in reversed(msgs):
                if m.role == "assistant":
                    texts = [b.text for b in m.content if b.type == "text" and b.text]
                    if texts:
                        assistant_last = texts[0][:300]
                        break
            tool_count = sum(1 for m in msgs for b in m.content if b.type == "tool_use")

            # 生成文件名：工作报告_年月日_时分.md
            filename = f"工作报告_{now.strftime('%Y%m%d_%H%M')}.md"
            filepath = REPORT_DIR / filename

            content = f"""# 工作报告

> **生成时间：** {now.strftime('%Y-%m-%d %H:%M:%S')}
> **会话 ID：** {self.current_session_id}

---

## 会话摘要

| 项目 | 数值 |
|------|------|
| 用户消息 | {user_count} 条 |
| 助手回复 | {sum(1 for m in msgs if m.role == 'assistant'):d} 条 |
| 工具调用 | {tool_count} 次 |

## 最后回复摘要

{assistant_last if assistant_last else '(空)'}

---

*由 DSCode 自动生成*
"""
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            # 在聊天框显示可点击链接
            self._show_file_link(filepath)

        except Exception:
            _log_error("handler")  # 报告生成失败不影响使用

    def _show_file_link(self, filepath: Path):
        """在聊天框显示可点击的文件链接"""
        tw = self.chat_display._textbox
        tw.configure(state="normal")

        folder = str(filepath.parent)
        tw.insert("end", f"\n  📄 已保存工作报告\n", "system_msg")

        # 用 filelink tag 标记可点击文本
        link_text = f"    📁 {folder}\\"
        idx_start = tw.index("end-1c")
        tw.insert("end", link_text, "filelink")
        idx_end = tw.index("end-1c")

        # 存储路径信息到 tag
        tw.tag_add("filelink", idx_start, idx_end)
        tw.tag_bind("filelink", "<Button-1>",
                     lambda e, p=folder: self._open_folder(p))
        tw.insert("end", "\n", "system_msg")

        tw.configure(state="disabled")
        tw.see("end")

    def _open_folder(self, folder: str):
        """在文件管理器中打开文件夹"""
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", folder], shell=True)
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            _log_error("handler")

    # ═══════════════════════════════════════════
    #  消息显示
    # ═══════════════════════════════════════════

    def _display_user_message(self, text: str):
        """显示用户消息"""
        tw = self.chat_display._textbox
        tw.configure(state="normal")

        now = datetime.now().strftime("%H:%M:%S")
        tw.insert("end", "\n", "separator")
        tw.insert("end", f"  ── {now} ──\n", "timestamp")
        tw.insert("end", f"👤 你\n", "user_label")
        tw.insert("end", f"{text}\n", "user_content")

        tw.configure(state="disabled")
        tw.see("end")

    def _create_streaming_container(self):
        """创建流式输出的容器"""
        tw = self.chat_display._textbox
        tw.configure(state="normal")

        now = datetime.now().strftime("%H:%M:%S")
        tw.insert("end", f"\n  ── {now} ──\n", "timestamp")
        tw.insert("end", f"🔮 DSCode\n", "assistant_label")

        # 标记开始流式输出
        self._streaming_active = True

        tw.configure(state="disabled")
        tw.see("end")

    def _append_stream_text(self, text: str):
        """追加流式文本（始终插到末尾，保证顺序）"""
        if not self._streaming_active:
            return
        tw = self.chat_display._textbox
        tw.configure(state="normal")

        # 直接插到末尾
        tw.insert("end", text, "streaming")

        tw.configure(state="disabled")
        tw.see("end")

        tw.configure(state="disabled")
        tw.see("end")

    def _show_tool_start(self, name: str):
        """显示工具开始调用"""
        tw = self.chat_display._textbox
        tw.configure(state="normal")

        tw.insert("end", f"  ⏳ 执行工具: {name}\n", "tool_call")

        tw.configure(state="disabled")
        tw.see("end")

    def _show_tool_end(self, name: str):
        """显示工具调用完成"""
        tw = self.chat_display._textbox
        tw.configure(state="normal")

        tw.insert("end", f"  ✅ 工具完成: {name}\n", "tool_done")

        tw.configure(state="disabled")
        tw.see("end")

    def _show_retry(self, message: str):
        """显示重试信息"""
        tw = self.chat_display._textbox
        tw.configure(state="normal")

        tw.insert("end", f"  ⚠️ {message}\n", "retry_msg")

        tw.configure(state="disabled")
        tw.see("end")

    def _display_error(self, error: str):
        """显示错误"""
        tw = self.chat_display._textbox
        tw.configure(state="normal")

        tw.insert("end", f"\n  ❌ {error}\n", "error_msg")

        tw.configure(state="disabled")
        tw.see("end")

    # ═══════════════════════════════════════════
    #  侧边栏操作
    # ═══════════════════════════════════════════

    def _new_session(self):
        """新建会话"""
        self.engine.reset()
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        tw = self.chat_display._textbox
        tw.configure(state="normal")
        tw.delete("1.0", "end")
        tw.configure(state="disabled")

        self._insert_welcome_message()
        self._update_stats()

    def _save_session(self):
        """保存会话"""
        name = f"会话_{datetime.now().strftime('%m%d_%H%M')}"
        filepath = self.memory_manager.save_session(name, self.engine.messages,
                                                     metadata={"timestamp": datetime.now().isoformat()})
        self._refresh_session_list()
        self._show_system_message(f"✅ 会话已保存: {name}")

    def _reset_chat(self):
        """重置对话"""
        self.engine.reset()
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        tw = self.chat_display._textbox
        tw.configure(state="normal")
        tw.delete("1.0", "end")
        tw.configure(state="disabled")

        self._insert_welcome_message()
        self._update_stats()
        self._show_system_message("🔄 对话已重置")

    def _show_system_message(self, text: str):
        """在聊天框显示系统消息"""
        tw = self.chat_display._textbox
        tw.configure(state="normal")
        tw.insert("end", f"\n  📌 {text}\n", "system_msg")
        tw.configure(state="disabled")
        tw.see("end")

    def _refresh_session_list(self):
        """刷新会话列表"""
        for widget in self.session_frame.winfo_children():
            widget.destroy()

        self._active_session_id = None  # 当前选中的会话 ID
        sessions = self.memory_manager.list_sessions()
        if not sessions:
            item = ctk.CTkFrame(self.session_frame, fg_color=COLOR_HEADER, corner_radius=6)
            item.pack(fill="x", pady=2)
            ctk.CTkLabel(item, text="当前会话", font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=COLOR_TEXT).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(item, text="活跃中", font=ctk.CTkFont(size=11),
                         text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=10, pady=(0, 8))
            return

        for s in sessions[:20]:
            sid = s.get("session_id", "未知")
            is_active = (sid == self._active_session_id)
            fg = COLOR_HEADER if is_active else "transparent"

            item = ctk.CTkFrame(self.session_frame, fg_color=fg, corner_radius=6)
            item.pack(fill="x", pady=1)

            name = sid
            meta = f"{s.get('message_count', 0)} 条 · {s.get('timestamp', '')[:10]}"

            lbl_title = ctk.CTkLabel(item, text=name, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=COLOR_TEXT)
            lbl_title.pack(anchor="w", padx=10, pady=(6, 0))

            lbl_meta = ctk.CTkLabel(item, text=meta, font=ctk.CTkFont(size=10),
                         text_color=COLOR_TEXT_MUTED)
            lbl_meta.pack(anchor="w", padx=10, pady=(0, 6))

            # 绑定点击事件到框架和所有标签（点击标签事件不自动传到父框架）
            def make_click_handler(session_id):
                def handler(event=None):
                    try:
                        self._load_session(session_id)
                    except Exception:
                        _log_error("session_click_handler")
                return handler

            click_fn = make_click_handler(sid)
            for widget in (item, lbl_title, lbl_meta):
                widget.bind("<Button-1>", click_fn)
                widget.configure(cursor="hand2")

    def _load_session(self, session_id: str):
        """加载会话（批量插入，避免卡顿）"""
        try:
            result = self.memory_manager.load_session(session_id)
            if result is None:
                self._show_system_message("❌ 会话加载失败")
                return
        except Exception as e:
            self._show_system_message(f"❌ 会话加载失败: {e}")
            return

        messages, metadata = result
        self.engine.messages = messages

        # 高亮当前选中的会话
        self._active_session_id = session_id
        self._refresh_session_list()

        # 批量重绘聊天框
        tw = self.chat_display._textbox
        tw.configure(state="normal")
        tw.delete("1.0", "end")

        for msg in messages:
            text_blocks = [b.text for b in msg.content if b.type == "text" and b.text]
            combined = "\n".join(text_blocks).strip()
            if not combined:
                continue

            now = " "
            if msg.role == "user":
                tw.insert("end", "\n", "separator")
                tw.insert("end", f"  ── {now} ──\n", "timestamp")
                tw.insert("end", "👤 你\n", "user_label")
                tw.insert("end", f"{combined}\n", "user_content")
            elif msg.role == "assistant":
                tw.insert("end", "\n", "separator")
                tw.insert("end", f"  ── {now} ──\n", "timestamp")
                tw.insert("end", "🔮 DSCode\n", "assistant_label")
                tw.insert("end", f"{combined}\n", "assistant_content")

        tw.configure(state="disabled")
        tw.see("end")
        self._update_stats()

    def _display_assistant_message(self, text: str):
        """显示助手消息（加载历史时使用）"""
        tw = self.chat_display._textbox
        tw.configure(state="normal")

        tw.insert("end", "\n", "separator")
        tw.insert("end", "🔮 DSCode\n", "assistant_label")
        tw.insert("end", f"{text}\n", "assistant_content")

        tw.configure(state="disabled")
        tw.see("end")

    def _update_stats(self):
        """更新底部统计"""
        cost = self.engine.get_cost()
        total = cost["total_tokens"]["prompt"] + cost["total_tokens"]["completion"]

        self.stat_tokens.configure(text=str(total))
        self.stat_cost.configure(text=f"¥{cost['total_cost_cny']:.4f}")
        self.header_tool_count.configure(text=f"{len(self.registry.list_tools())} 个工具可用")

    def _on_close(self):
        """关闭窗口"""
        self.stop_streaming = True
        self.destroy()
