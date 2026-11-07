#!/usr/bin/env python3
"""跨平台兼容小工具。所有脚本共用，避免各写一份。

为什么需要：
1. **Windows 控制台默认 cp936**。脚本里 print 中文、✓、× 这类字符会抛
   UnicodeEncodeError 直接崩掉，而且崩在最后一行输出上，前面的抓取全白干。
2. **stdin 编码**。管道传入 JSON 时 Windows 按 cp936 解，遇到 UTF-8 字节就乱码。
3. 这两个问题只在 Windows 上出现，macOS/Linux 测不出来，所以必须显式处理。

用法：
    from _compat import fix_stdio, read_stdin
    fix_stdio()                 # 放在 main() 第一行
    text = read_stdin()         # 代替 sys.stdin.read()
"""
import sys


def fix_stdio():
    """把 stdout/stderr 切到 UTF-8 并容错，避免在 cp936 控制台崩掉。"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            # Python < 3.7 或已被重定向成不可配置对象，忽略即可
            pass


def read_stdin() -> str:
    """按 UTF-8 读标准输入，失败退到本地编码。管道场景比 sys.stdin.read() 可靠。"""
    try:
        data = sys.stdin.buffer.read()
    except (AttributeError, ValueError):
        return sys.stdin.read()
    for enc in ("utf-8-sig", "utf-8", sys.getdefaultencoding() or "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")
