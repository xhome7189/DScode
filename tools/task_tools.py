"""
任务管理工具 - TaskCreate, TaskUpdate, TaskList
基于 DScode 的 TaskCreateTool, TaskUpdateTool
"""

import json
from datetime import datetime
from typing import Optional

from tools.base import Tool


# 全局任务存储（进程内）
_tasks_store: list[dict] = []


def get_task_store():
    return _tasks_store


def reset_tasks():
    _tasks_store.clear()


class TaskCreateTool(Tool):
    """创建任务"""

    name = "task_create"
    description = """Create a task to track work progress. Use this for breaking down 
    complex tasks into manageable steps."""

    parameters = {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "A brief title for the task"
            },
            "description": {
                "type": "string",
                "description": "Detailed description of what needs to be done"
            },
            "active_form": {
                "type": "string",
                "description": "Present continuous form shown during execution"
            }
        },
        "required": ["subject", "description"]
    }

    def execute(self, subject: str, description: str, active_form: str = "") -> str:
        task = {
            "id": str(len(_tasks_store) + 1),
            "subject": subject,
            "description": description,
            "active_form": active_form or subject,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        _tasks_store.append(task)
        return f"Task created: [{task['id']}] {subject}"


class TaskUpdateTool(Tool):
    """更新任务"""

    name = "task_update"
    description = """Update task status or details. Use to mark tasks as 
    in_progress, completed, or deleted."""

    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The ID of the task to update"
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed", "deleted"],
                "description": "New status for the task"
            },
            "subject": {
                "type": "string",
                "description": "New subject for the task"
            }
        },
        "required": ["task_id", "status"]
    }

    def execute(self, task_id: str, status: str, subject: str = "") -> str:
        for task in _tasks_store:
            if task["id"] == task_id:
                task["status"] = status
                if subject:
                    task["subject"] = subject
                return f"Task [{task_id}] updated: status={status}"
        return f"Task [{task_id}] not found"


class TaskListTool(Tool):
    """列出任务"""

    name = "task_list"
    description = "List all tasks in the current session"

    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    def execute(self) -> str:
        if not _tasks_store:
            return "No tasks created yet."

        result = []
        for task in _tasks_store:
            status_icon = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "deleted": "❌"
            }.get(task["status"], "❓")

            result.append(f"[{task['id']}] {status_icon} {task['subject']} ({task['status']})")
            result.append(f"    {task['description']}")

        return "\n".join(result)
