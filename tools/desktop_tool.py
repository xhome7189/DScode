"""
桌面自动化工具 - 鼠标、键盘、窗口操作
支持 GUI 自动化：打开应用、点击、输入、截图、找图
"""

import time
import os
import subprocess
import re
import json
from pathlib import Path
from datetime import datetime

from tools.base import Tool

HAS_PYAUTOGUI = False
try:
    import pyautogui
    HAS_PYAUTOGUI = True
except Exception:
    HAS_PYAUTOGUI = False

# OCR 支持
HAS_PYTESSERACT = False
try:
    import pytesseract
    # 测试 Tesseract 是否可用
    pytesseract.get_tesseract_version()
    HAS_PYTESSERACT = True
except Exception:
    HAS_PYTESSERACT = False


class MouseClickTool(Tool):
    """鼠标点击指定坐标"""

    name = "mouse_click"
    description = "Click at specified screen coordinates (x, y). Use for clicking buttons, links, and UI elements."

    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate on screen"},
            "y": {"type": "integer", "description": "Y coordinate on screen"},
            "button": {
                "type": "string",
                "enum": ["left", "right", "middle"],
                "description": "Mouse button to click (default: left)"
            },
            "clicks": {
                "type": "integer",
                "description": "Number of clicks (1=single, 2=double, default: 1)"
            }
        },
        "required": ["x", "y"]
    }

    def execute(self, x: int, y: int, button: str = "left", clicks: int = 1) -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed. Run: pip install pyautogui"
        try:
            pyautogui.click(x, y, button=button, clicks=clicks, duration=0.3)
            return f"Clicked at ({x}, {y}) with {button} button, {clicks} click(s)"
        except Exception as e:
            return f"Error clicking: {str(e)}"


class MouseMoveTool(Tool):
    """移动鼠标到指定坐标"""

    name = "mouse_move"
    description = "Move mouse to specified screen coordinates."

    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate"},
            "y": {"type": "integer", "description": "Y coordinate"},
            "duration": {"type": "number", "description": "Movement duration in seconds (default: 0.5)"}
        },
        "required": ["x", "y"]
    }

    def execute(self, x: int, y: int, duration: float = 0.5) -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed"
        try:
            pyautogui.moveTo(x, y, duration=duration)
            return f"Moved mouse to ({x}, {y})"
        except Exception as e:
            return f"Error moving mouse: {str(e)}"


class TypeTextTool(Tool):
    """键盘输入文字"""

    name = "type_text"
    description = "Type text using the keyboard. Supports Chinese characters via clipboard paste."

    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to type"},
            "interval": {
                "type": "number",
                "description": "Interval between keystrokes in seconds (default: 0.05)"
            }
        },
        "required": ["text"]
    }

    def execute(self, text: str, interval: float = 0.05) -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed"
        try:
            # 对于中文字符，使用剪贴板粘贴
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
            if has_chinese:
                import pyperclip
                pyperclip.copy(text)
                time.sleep(0.2)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.2)
            else:
                pyautogui.typewrite(text, interval=interval)
            return f"Typed text: {text[:50]}{'...' if len(text) > 50 else ''}"
        except ImportError:
            # 没有 pyperclip 就用逐字输入
            try:
                pyautogui.typewrite(text, interval=interval)
                return f"Typed text: {text[:50]}"
            except Exception as e:
                return f"Error typing: {str(e)}"
        except Exception as e:
            return f"Error typing: {str(e)}"


class PressKeyTool(Tool):
    """按下键盘按键"""

    name = "press_key"
    description = """Press a keyboard key or hotkey combination.
    Examples: 'enter', 'tab', 'ctrl+c', 'alt+f4', 'win', 'esc'"""

    parameters = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Key or combination to press (e.g., 'enter', 'ctrl+c', 'alt+tab')"}
        },
        "required": ["key"]
    }

    def execute(self, key: str) -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed"
        try:
            # 支持组合键如 ctrl+c, alt+tab
            parts = key.lower().split('+')
            if len(parts) > 1:
                pyautogui.hotkey(*parts)
            else:
                pyautogui.press(key)
            return f"Pressed key: {key}"
        except Exception as e:
            return f"Error pressing key: {str(e)}"


class FindWindowTool(Tool):
    """查找并激活窗口（找不到时尝试启动应用）"""

    name = "find_window"
    description = """Find a window by title, bring it to front.
If no window is found, try to launch the application first.
Common app names: 微信, 企业微信, 钉钉, QQ, Chrome, 记事本, 计算器, etc."""

    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Window title to search for (partial match). Common: '微信', '企业微信', '钉钉', 'QQ', 'Chrome'"},
            "activate": {
                "type": "boolean",
                "description": "Whether to activate (bring to front) the window (default: true)"
            }
        },
        "required": ["title"]
    }

    # 常见应用的启动命令映射
    APP_LAUNCH_MAP = {
        "微信": ["wechat.exe", "WeChat.exe"],
        "企业微信": ["wework.exe", "WXWork.exe"],
        "钉钉": ["dingtalk.exe", "DingTalk.exe"],
        "qq": ["qq.exe", "QQ.exe"],
        "chrome": ["chrome.exe"],
        "edge": ["msedge.exe"],
        "记事本": ["notepad.exe"],
        "计算器": ["calc.exe"],
        "画图": ["mspaint.exe", "pbrush.exe"],
    }

    def _try_launch(self, title: str) -> bool:
        """尝试启动应用"""
        import shutil
        title_lower = title.lower()

        # 1. 查映射表
        for key, exes in self.APP_LAUNCH_MAP.items():
            if key in title_lower or title_lower in key:
                for exe in exes:
                    found = shutil.which(exe)
                    if found:
                        subprocess.Popen([found], shell=True)
                        time.sleep(2)
                        return True
                    # 尝试常见安装路径
                    common_paths = [
                        os.path.expandvars(f"%ProgramFiles%\\{exe}"),
                        os.path.expandvars(f"%ProgramFiles(x86)%\\{exe}"),
                        os.path.expandvars(f"%LocalAppData%\\{exe}"),
                        f"C:\\Program Files\\{exe}",
                        f"C:\\Program Files (x86)\\{exe}",
                    ]
                    for p in common_paths:
                        if os.path.exists(p):
                            subprocess.Popen([p], shell=True)
                            time.sleep(2)
                            return True

        # 2. 直接用 start 命令尝试（Windows 自动查找）
        try:
            subprocess.run(f"start {title}", shell=True, capture_output=True, timeout=5)
            time.sleep(2)
            return True
        except Exception:
            pass

        return False

    def execute(self, title: str, activate: bool = True) -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed"
        try:
            import pygetwindow as gw
            # 先找已有窗口
            windows = gw.getWindowsWithTitle(title)
            if not windows:
                # 找不到 → 尝试启动应用
                launched = self._try_launch(title)
                if launched:
                    # 再找一次
                    time.sleep(1)
                    windows = gw.getWindowsWithTitle(title)
                if not windows:
                    return (f"No window found with title '{title}'. "
                            f"Tried to launch it but couldn't find the executable.\n"
                            f"Try using 'launch_app' tool first, then 'find_window'.")

            win = windows[0]
            if activate:
                win.activate()
                time.sleep(0.5)

            return (f"Found window: '{win.title}'\n"
                    f"Position: ({win.left}, {win.top})\n"
                    f"Size: {win.width}x{win.height}\n"
                    f"Currently active: {win.isActive}")
        except ImportError:
            return "Error: pygetwindow not installed. Run: pip install pygetwindow"
        except Exception as e:
            return f"Error finding window: {str(e)}"


class LaunchAppTool(Tool):
    """启动应用程序"""

    name = "launch_app"
    description = """Launch/start an application by name.
Examples: '微信', 'wechat', 'notepad', 'chrome', 'calc', 'mspaint'"""

    parameters = {
        "type": "object",
        "properties": {
            "app": {"type": "string", "description": "Application name or executable name to launch"},
            "args": {"type": "string", "description": "Optional command line arguments"}
        },
        "required": ["app"]
    }

    def execute(self, app: str, args: str = "") -> str:
        try:
            import shutil
            app_lower = app.lower()

            # 常见应用映射
            app_map = {
                "微信": "wechat.exe", "wechat": "wechat.exe",
                "企业微信": "wxwork.exe", "wework": "wxwork.exe",
                "钉钉": "dingtalk.exe", "dingtalk": "dingtalk.exe",
                "qq": "qq.exe", "tim": "qq.exe",
                "chrome": "chrome.exe", "谷歌": "chrome.exe",
                "edge": "msedge.exe",
                "记事本": "notepad.exe", "notepad": "notepad.exe",
                "计算器": "calc.exe", "calc": "calc.exe",
                "画图": "mspaint.exe", "mspaint": "mspaint.exe",
                "cmd": "cmd.exe", "命令提示符": "cmd.exe",
                "powershell": "powershell.exe",
                "explorer": "explorer.exe", "资源管理器": "explorer.exe",
            }

            exe = app_map.get(app_lower, app)

            # 尝试 which 查找
            found = shutil.which(exe)
            if found:
                if args:
                    subprocess.Popen([found, args], shell=True)
                else:
                    subprocess.Popen([found], shell=True)
                return f"Launched: {found}"

            # 尝试 start 命令
            cmd = f"start {exe} {' ' + args if args else ''}"
            subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            return f"Launched: {app}"

        except Exception as e:
            return f"Error launching app: {str(e)}"


class ScreenshotTool(Tool):
    """截取屏幕并保存"""

    name = "screenshot"
    description = "Take a screenshot of the entire screen or a region."

    parameters = {
        "type": "object",
        "properties": {
            "save_path": {
                "type": "string",
                "description": "Path to save the screenshot (default: screenshots/screenshot_YYYYMMDD_HHMMSS.png)"
            },
            "region": {
                "type": "string",
                "description": "Region to capture as 'x,y,width,height' (default: full screen)"
            }
        },
        "required": []
    }

    def execute(self, save_path: str = None, region: str = None) -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed"
        try:
            from datetime import datetime
            if not save_path:
                base_dir = Path(__file__).parent.parent / "screenshots"
                base_dir.mkdir(exist_ok=True)
                save_path = str(base_dir / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

            if region:
                parts = [int(x.strip()) for x in region.split(',')]
                if len(parts) == 4:
                    screenshot = pyautogui.screenshot(region=tuple(parts))
                else:
                    screenshot = pyautogui.screenshot()
            else:
                screenshot = pyautogui.screenshot()

            screenshot.save(save_path)
            return f"Screenshot saved to: {save_path} ({os.path.getsize(save_path)} bytes)"
        except Exception as e:
            return f"Error taking screenshot: {str(e)}"


class GetScreenSizeTool(Tool):
    """获取屏幕分辨率"""

    name = "get_screen_size"
    description = "Get the current screen resolution and mouse position."

    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    def execute(self) -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed"
        try:
            width, height = pyautogui.size()
            mx, my = pyautogui.position()
            return f"Screen: {width}x{height}\nMouse position: ({mx}, {my})"
        except Exception as e:
            return f"Error: {str(e)}"


class LocateImageTool(Tool):
    """在屏幕上查找图片位置"""

    name = "locate_image"
    description = "Find an image on the screen and return its position. Requires the image file path."

    parameters = {
        "type": "object",
        "properties": {
            "image_path": {"type": "string", "description": "Path to the image file to find on screen"},
            "confidence": {
                "type": "number",
                "description": "Match confidence 0.0-1.0 (default: 0.8)"
            }
        },
        "required": ["image_path"]
    }

    def execute(self, image_path: str, confidence: float = 0.8) -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed"
        try:
            location = pyautogui.locateOnScreen(image_path, confidence=confidence)
            if location:
                center = pyautogui.center(location)
                return (f"Image found at: ({location.left}, {location.top})\n"
                        f"Size: {location.width}x{location.height}\n"
                        f"Center: ({int(center.x)}, {int(center.y)})")
            return f"Image not found on screen: {image_path}"
        except pyautogui.ImageNotFoundException:
            return f"Image not found: {image_path}"
        except Exception as e:
            return f"Error locating image: {str(e)}"


class OcrScreenshotTool(Tool):
    """对屏幕截图进行文字识别"""

    name = "ocr_screenshot"
    description = "Take a screenshot and perform OCR (Optical Character Recognition) to extract all text from the screen."

    parameters = {
        "type": "object",
        "properties": {
            "region": {
                "type": "string",
                "description": "Region to OCR as 'x,y,width,height' (default: full screen)"
            },
            "language": {
                "type": "string",
                "description": "OCR language: 'chi_sim' for Chinese, 'eng' for English (default: chi_sim+eng)"
            }
        },
        "required": []
    }

    def execute(self, region: str = None, language: str = "chi_sim+eng") -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed"
        if not HAS_PYTESSERACT:
            return "Error: Tesseract OCR not available.\nInstall: https://github.com/UB-Mannheim/tesseract/wiki"
        try:
            # 截图
            if region:
                parts = [int(x.strip()) for x in region.split(",")]
                img = pyautogui.screenshot(region=tuple(parts) if len(parts) == 4 else None)
            else:
                img = pyautogui.screenshot()

            # OCR 识别
            text = pytesseract.image_to_string(img, lang=language)

            # 获取每个字符的详细信息（用于定位）
            data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)

            # 找出所有非空文本块及其位置
            blocks = []
            for i in range(len(data["text"])):
                txt = data["text"][i].strip()
                if txt and int(data["conf"][i]) > 30:  # 置信度 > 30
                    blocks.append({
                        "text": txt,
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "w": data["width"][i],
                        "h": data["height"][i],
                    })

            # 保存截图到临时文件
            base_dir = Path(__file__).parent.parent / "screenshots"
            base_dir.mkdir(exist_ok=True)
            screenshot_path = str(base_dir / f"ocr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            img.save(screenshot_path)

            result_text = text.strip()
            if not result_text:
                result_text = "(屏幕上未识别到文字)"

            return (f"OCR 结果:\n{result_text[:3000]}\n\n"
                    f"识别到 {len(blocks)} 个文本块\n"
                    f"截图保存在: {screenshot_path}\n\n"
                    f"如需精准定位特定文本，请使用 find_text_on_screen 工具。")
        except Exception as e:
            return f"Error OCR: {str(e)}"


class FindTextOnScreenTool(Tool):
    """在屏幕上查找指定文本的位置"""

    name = "find_text_on_screen"
    description = """Search for specific text on the screen using OCR.
Returns the coordinates where the text is found, so you can click there.
Use this to find buttons, search boxes, menu items, etc."""

    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to search for on screen"},
            "language": {
                "type": "string",
                "description": "OCR language (default: chi_sim+eng)"
            },
            "fuzzy": {
                "type": "boolean",
                "description": "Enable fuzzy/partial matching (default: true)"
            }
        },
        "required": ["text"]
    }

    def execute(self, text: str, language: str = "chi_sim+eng", fuzzy: bool = True) -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed"
        if not HAS_PYTESSERACT:
            return "Error: Tesseract OCR not available.\nInstall Tesseract from https://github.com/UB-Mannheim/tesseract/wiki"
        try:
            img = pyautogui.screenshot()
            data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)

            search_lower = text.lower()
            matches = []
            for i in range(len(data["text"])):
                txt = data["text"][i].strip()
                if not txt:
                    continue
                conf = int(data["conf"][i])
                if conf < 20:
                    continue

                if fuzzy:
                    # 模糊匹配：目标文本出现在识别文本中，或反之
                    if search_lower in txt.lower() or txt.lower() in search_lower:
                        matches.append({
                            "text": txt,
                            "x": data["left"][i],
                            "y": data["top"][i],
                            "w": data["width"][i],
                            "h": data["height"][i],
                            "conf": conf,
                        })
                else:
                    if txt.lower() == search_lower:
                        matches.append({
                            "text": txt,
                            "x": data["left"][i],
                            "y": data["top"][i],
                            "w": data["width"][i],
                            "h": data["height"][i],
                            "conf": conf,
                        })

            if not matches:
                return f"Text '{text}' not found on screen."

            # 排序：按位置从上到下，从左到右
            matches.sort(key=lambda m: (m["y"], m["x"]))

            result = f"Found '{text}' in {len(matches)} location(s):\n\n"
            for i, m in enumerate(matches[:10]):
                center_x = m["x"] + m["w"] // 2
                center_y = m["y"] + m["h"] // 2
                result += (f"  [{i+1}] '{m['text']}' (confidence: {m['conf']}%)\n"
                          f"       Position: ({m['x']}, {m['y']})\n"
                          f"       Size: {m['w']}x{m['h']}\n"
                          f"       Click at: ({center_x}, {center_y})\n\n")

            if len(matches) > 10:
                result += f"... and {len(matches) - 10} more matches\n"

            result += "Use mouse_click with the coordinates above to click on this element."
            return result

        except Exception as e:
            return f"Error finding text: {str(e)}"


class ScanDesktopTool(Tool):
    """扫描桌面情况：截图 + OCR + 窗口列表"""

    name = "scan_desktop"
    description = """Comprehensive desktop scan.
Takes a screenshot, lists all open windows, performs OCR on the screen,
and returns a complete picture of what's on the desktop.
Use this to understand the current screen state before performing mouse operations."""

    parameters = {
        "type": "object",
        "properties": {
            "ocr": {
                "type": "boolean",
                "description": "Whether to perform OCR (default: true)"
            },
            "language": {
                "type": "string",
                "description": "OCR language (default: chi_sim+eng)"
            }
        },
        "required": []
    }

    def execute(self, ocr: bool = True, language: str = "chi_sim+eng") -> str:
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not installed"
        try:
            result_parts = []
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result_parts.append(f"=== 桌面扫描报告 ({now}) ===")

            # 1. 屏幕信息
            width, height = pyautogui.size()
            mx, my = pyautogui.position()
            result_parts.append(f"\n📺 屏幕: {width}x{height}  鼠标: ({mx}, {my})")

            # 2. 截图
            img = pyautogui.screenshot()
            base_dir = Path(__file__).parent.parent / "screenshots"
            base_dir.mkdir(exist_ok=True)
            screenshot_path = str(base_dir / f"desktop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            img.save(screenshot_path)
            result_parts.append(f"\n📸 截图: {screenshot_path}")

            # 3. 窗口列表
            try:
                import pygetwindow as gw
                all_windows = gw.getAllWindows()
                visible = [w for w in all_windows if w.visible and w.title.strip()]
                result_parts.append(f"\n🪟 可见窗口 ({len(visible)} 个):")
                for w in visible[:20]:
                    result_parts.append(f"  - '{w.title}'  ({w.left},{w.top}) {w.width}x{w.height}")
                if len(visible) > 20:
                    result_parts.append(f"  ... 还有 {len(visible)-20} 个窗口")
            except ImportError:
                result_parts.append("\n🪟 窗口列表: pygetwindow 未安装")

            # 4. OCR 识别
            if ocr and HAS_PYTESSERACT:
                text = pytesseract.image_to_string(img, lang=language).strip()
                if text:
                    # 只取前 1500 字符
                    if len(text) > 1500:
                        text = text[:1500] + "\n... (截断)"
                    result_parts.append(f"\n🔍 屏幕文字识别:\n{text}")
                else:
                    result_parts.append("\n🔍 屏幕文字识别: (无)")
            elif ocr and not HAS_PYTESSERACT:
                result_parts.append("\n🔍 OCR: Tesseract 未安装，跳过")
            else:
                result_parts.append("\n🔍 OCR: 已跳过")

            result_parts.append(f"\n{'='*30}")
            result_parts.append("提示: 使用 find_text_on_screen 可精准定位文字位置")
            result_parts.append("提示: 使用 mouse_click(x,y) 可点击找到的元素")

            return "\n".join(result_parts)

        except Exception as e:
            return f"Error scanning desktop: {str(e)}"
