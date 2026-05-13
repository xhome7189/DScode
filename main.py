"""
DSCode - 启动入口
CustomTkinter 纯 Windows 桌面版
"""
import sys
import os
import traceback
from datetime import datetime

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ===== 启动追踪日志（记录到启动阶段每一行） =====
BOOT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "boot_trace.log")
os.makedirs(os.path.dirname(BOOT_LOG), exist_ok=True)
def boot_log(msg):
    try:
        with open(BOOT_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

boot_log("=== 启动开始 ===")

# 清除代理环境变量，避免Lingma等AI代理干扰
boot_log("step 1: fix_proxy")
from fix_proxy import apply as fix_proxy
fix_proxy()
boot_log("step 1 done")

boot_log("step 2: import ChatWindow")
from gui.chat_window import ChatWindow
boot_log("step 2 done")


def main():
    """启动桌面应用"""
    print("╔══════════════════════════════════════════════╗")
    print("║               DSCode v1.0.0                ║")
    print("║        CustomTkinter 纯 Windows 桌面版       ║")
    print("╠══════════════════════════════════════════════╣")
    print("║  模型: DeepSeek Chat                       ║")
    print("║  引擎: QueryEngine + ToolSystem            ║")
    print("╚══════════════════════════════════════════════╝")

    boot_log("step 3: ChatWindow()")
    app = ChatWindow()
    boot_log("step 4: mainloop()")
    app.mainloop()
    boot_log("=== 正常退出 ===")


if __name__ == "__main__":
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    boot_log("step 5: mainloop start")

    # 全局异常钩子（捕获 tkinter 主循环内部异常）
    def global_excepthook(exc_type, exc_value, exc_tb):
        boot_log(f"异常钩子触发: {exc_type.__name__}: {exc_value}")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"=== 全局未处理异常 ===\n")
            f.write(f"类型: {exc_type.__name__}\n")
            f.write(f"信息: {exc_value}\n\n")
            traceback.print_tb(exc_tb, file=f)
        print(f"\n❌ 程序异常: {exc_type.__name__}: {exc_value}")
        print(f"   详情请查看: {log_path}")
        # 调用原始钩子（默认会退出）
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = global_excepthook

    try:
        main()
    except SystemExit:
        boot_log("SystemExit 退出")
    except Exception:
        boot_log("try/except 捕获异常")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"=== DSCode 崩溃日志 ===\n")
            f.write(f"时间: {datetime.now().isoformat()}\n")
            f.write(f"系统: {sys.platform}\n")
            f.write(f"Python: {sys.version}\n\n")
            traceback.print_exc(file=f)
        print(f"\n❌ 程序崩溃，详情请查看: {log_path}")
        traceback.print_exc()
    finally:
        boot_log("=== main 结束 ===")
