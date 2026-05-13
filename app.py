"""
DeepSeek Code - 应用主入口
Flask 后端 + Web 前端 GUI
"""

import json
import os
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

from config import GUI_HOST, GUI_PORT, BASE_DIR
from core.query_engine import QueryEngine
from core.message import Message
from tools.registry import create_registry
from memory import MemoryManager
from tools.task_tools import reset_tasks

# 初始化 Flask
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
CORS(app)

# 创建核心组件
registry = create_registry()
engine = QueryEngine(tools_registry=registry)
memory_manager = MemoryManager()

# 当前会话 ID
current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")


@app.route("/")
def index():
    """主页面"""
    return send_from_directory(str(BASE_DIR), "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """聊天接口 - 流式响应"""
    data = request.json
    user_message = data.get("message", "")
    session_id = data.get("session_id", current_session_id)

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    def generate():
        """生成流式响应"""
        full_text = ""

        def callback(event_type, data):
            nonlocal full_text
            if event_type == "text":
                full_text += data
                yield f"data: {json.dumps({'type': 'text', 'content': data}, ensure_ascii=False)}\n\n"
            elif event_type == "tool_start":
                yield f"data: {json.dumps({'type': 'tool_start', 'content': data}, ensure_ascii=False)}\n\n"
            elif event_type == "tool_end":
                yield f"data: {json.dumps({'type': 'tool_end', 'content': data}, ensure_ascii=False)}\n\n"
            elif event_type == "thinking":
                yield f"data: {json.dumps({'type': 'thinking', 'content': 'Thinking...'}, ensure_ascii=False)}\n\n"

        try:
            engine.chat(user_message, callback=callback)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@app.route("/api/history", methods=["GET"])
def get_history():
    """获取对话历史"""
    messages_data = []
    for msg in engine.messages:
        msg_data = {
            "role": msg.role,
            "timestamp": msg.timestamp,
            "content": []
        }
        for block in msg.content:
            msg_data["content"].append({
                "type": block.type,
                "text": block.text,
                "tool_name": block.tool_name,
                "tool_input": block.tool_input,
                "tool_result": block.tool_result,
                "is_error": block.is_error,
            })
        messages_data.append(msg_data)

    return jsonify({"messages": messages_data, "session_id": current_session_id})


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    """列出保存的会话"""
    sessions = memory_manager.list_sessions()
    return jsonify({"sessions": sessions})


@app.route("/api/sessions/save", methods=["POST"])
def save_session():
    """保存当前会话"""
    name = request.json.get("name", current_session_id)
    filepath = memory_manager.save_session(name, engine.messages)
    return jsonify({"status": "ok", "path": filepath})


@app.route("/api/sessions/load", methods=["POST"])
def load_session():
    """加载会话"""
    session_id = request.json.get("session_id", "")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    result = memory_manager.load_session(session_id)
    if result is None:
        return jsonify({"error": "Session not found"}), 404

    messages, metadata = result
    engine.messages = messages
    return jsonify({"status": "ok", "message_count": len(messages)})


@app.route("/api/reset", methods=["POST"])
def reset_chat():
    """重置对话"""
    engine.reset()
    reset_tasks()
    return jsonify({"status": "ok"})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """获取使用统计"""
    cost = engine.get_cost()
    return jsonify({
        "total_tokens": cost["total_tokens"],
        "total_cost_usd": round(cost["total_cost_usd"], 6),
        "total_cost_cny": round(cost["total_cost_cny"], 4),
        "message_count": len(engine.messages),
        "tools_available": registry.list_tools(),
    })


def main():
    """启动应用"""
    print(f"╔══════════════════════════════════════════════╗")
    print(f"║          DeepSeek Code v1.0.0              ║")
    print(f"║     基于 DScode 架构的 Python 重写     ║")
    print(f"╠══════════════════════════════════════════════╣")
    print(f"║  模型: DeepSeek Chat                       ║")
    print(f"║  地址: http://{GUI_HOST}:{GUI_PORT}              ║")
    print(f"║  工具: {len(registry.list_tools())} 个已注册                    ║")
    print(f"╚══════════════════════════════════════════════╝")
    print(f"\n正在打开浏览器...")

    # 自动打开浏览器
    webbrowser.open(f"http://{GUI_HOST}:{GUI_PORT}")

    # 启动服务
    app.run(
        host=GUI_HOST,
        port=GUI_PORT,
        debug=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
