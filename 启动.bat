@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 临时清除代理环境变量，避免Lingma等AI代理干扰网络请求
set http_proxy=
set https_proxy=
set HTTP_PROXY=
set HTTPS_PROXY=
set NO_PROXY=
set no_proxy=
set all_proxy=
set ALL_PROXY=

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python
    pause
    exit /b 1
)

:: 安装依赖
python -c "import customtkinter" 2>nul || pip install customtkinter -q
python -c "import requests" 2>nul || pip install requests -q

:: 启动应用
echo 启动 DSCode...
echo 提示：如果窗口一闪消失，请查看 logs\ 目录下的日志文件
echo.
python main.py

:: 无论成功还是失败都暂停，让用户看到退出信息
echo.
echo 应用已退出 (exit code: %errorlevel%)
echo 请查看 logs\ 目录下的日志了解详情
pause
