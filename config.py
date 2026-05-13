"""
DSCode - Configuration
"""

import os
from pathlib import Path

# === DeepSeek API 配置 ===
DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"  # deepseek-chat 或 deepseek-reasoner

# === 应用配置 ===
APP_NAME = "DSCode"
APP_VERSION = "1.0.0"
BASE_DIR = Path(__file__).parent

# === 工具配置 ===
MAX_BASH_OUTPUT = 50000  # Bash 输出最大字符数
BASH_TIMEOUT = 120000     # Bash 超时 (ms)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 最大文件读取大小 10MB

# === 记忆系统配置 ===
MEMORY_DIR = BASE_DIR / ".memory"
MEMORY_DIR.mkdir(exist_ok=True)

# === 日志配置 ===
LOG_DIR = BASE_DIR / ".logs"
LOG_DIR.mkdir(exist_ok=True)

# === GUI 配置 ===
GUI_HOST = "127.0.0.1"
GUI_PORT = 8899
BROWSER_WIDTH = 1200
BROWSER_HEIGHT = 800
