#!/usr/bin/env python3
"""跨平台 CDP 浏览器启动器 —— 零第三方依赖，只用标准库。

为什么要有这个文件：本技能所有浏览器操作原本依赖 `browser-cdp-control` 技能，
那是别人机器上不一定有的东西。别人 clone 下来，Windows 还有自带的 .ps1 可用，
macOS/Linux 直接抓瞎。这个脚本把这件事收回来，只依赖「系统里装了一个
Chromium 内核浏览器」，其余全部自带。

设计原则
  · 零依赖：只用 Python 标准库，WebSocket 自己实现（约 100 行），不装 websocket-client。
  · 行为确定：直接发 CDP 指令，中间没有会自动回退的封装层。
  · 不抢用户的浏览器：每个 --session 一个独立 profile + 独立端口，跟日常浏览器互不干扰。
  · 登录态能存住：profile 落在磁盘上，关掉再开还是登录状态。

命令
  browser.py find                              # 看看本机有哪些可用浏览器
  browser.py start [URL] [--session 名字]       # 起一个带调试端口的窗口
  browser.py status [--session 名字]            # 探活
  browser.py list                              # 列出页面 target
  browser.py open URL                          # 开新标签（不抢已有页）
  browser.py eval TARGET_ID "JS 表达式"         # 在页面里执行 JS，返回结果
  browser.py cookies [--session 名字] [--save 路径]   # 导出当前 profile 全部 cookie
  browser.py stop [--session 名字]              # 关掉本脚本起的实例
  browser.py front TARGET_ID                   # 把标签切到前台（需要用户登录时用）

端口与 profile
  --session 名字经 CRC32 映射到 9300–9399，同名必得同端口、同 profile，可复现：
      ~/.workbuddy/browser-profiles/<session>

平台差异（都已在代码里处理）
  macOS/Linux  用 start_new_session 脱离父进程，否则 shell 一结束浏览器就被回收
  Windows      用 DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP，同理
  三平台都会显式清掉 HTTP(S)_PROXY 环境变量（浏览器继承 shell 代理会让国内站从海外
  机房 IP 出去，触发风控），要代理就显式 --proxy
"""
import argparse, base64, binascii, json, os, platform, shutil, socket, struct
import subprocess, sys, time, urllib.error, urllib.parse, urllib.request

HOME = os.path.expanduser("~")
PROFILE_ROOT = os.path.join(HOME, ".workbuddy", "browser-profiles")
IS_WIN = platform.system() == "Windows"


# ---------------------------------------------------------------- 控制台编码
def _fix_stdio():
    """Windows 控制台默认 cp936，print 中文/符号会抛 UnicodeEncodeError 直接崩掉。"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ---------------------------------------------------------------- 浏览器发现
_MAC_ROOTS = ["/Applications", os.path.join(HOME, "Applications")]
_MAC = [
    ("Chrome", "Google Chrome.app/Contents/MacOS/Google Chrome"),
    ("Edge", "Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ("QQ浏览器", "QQBrowser.app/Contents/MacOS/QQBrowser"),
    ("Brave", "Brave Browser.app/Contents/MacOS/Brave Browser"),
    ("Chromium", "Chromium.app/Contents/MacOS/Chromium"),
    ("360极速浏览器", "360Chrome.app/Contents/MacOS/360Chrome"),
]
_WIN = [
    ("Chrome", r"Google\Chrome\Application\chrome.exe"),
    ("Edge", r"Microsoft\Edge\Application\msedge.exe"),
    ("QQ浏览器", r"Tencent\QQBrowser\QQBrowser.exe"),
    ("360极速浏览器", r"360Chrome\Chrome\Application\360chrome.exe"),
    ("Brave", r"BraveSoftware\Brave-Browser\Application\brave.exe"),
]
_WIN_ROOTS = [os.environ.get("ProgramFiles", r"C:\Program Files"),
              os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
              os.environ.get("LOCALAPPDATA", "")]
_LINUX_CMDS = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
               "microsoft-edge", "brave-browser"]


def find_browsers():
    out, seen = [], set()
    if platform.system() == "Darwin":
        for name, rel in _MAC:
            for root in _MAC_ROOTS:
                p = os.path.join(root, rel)
                if os.path.exists(p) and p not in seen:
                    seen.add(p)
                    out.append((name, p))
    elif IS_WIN:
        for name, rel in _WIN:
            for root in _WIN_ROOTS:
                if not root:
                    continue
                p = os.path.join(root, rel)
                if os.path.exists(p) and p not in seen:
                    seen.add(p)
                    out.append((name, p))
    else:
        for cmd in _LINUX_CMDS:
            p = shutil.which(cmd)
            if p and p not in seen:
                seen.add(p)
                out.append(("Chromium" if "chrom" in cmd else cmd.split("-")[0].title(), p))
    return out


def pick_browser(explicit=None):
    if explicit:
        if not os.path.exists(explicit):
            raise SystemExit(f"指定的浏览器不存在：{explicit}")
        return explicit
    bs = find_browsers()
    if not bs:
        raise SystemExit(
            "没找到任何 Chromium 内核浏览器。装一个再来：\n"
            "  macOS        brew install --cask google-chrome    （或装腾讯 QQ 浏览器）\n"
            "  Windows      winget install Google.Chrome        （或直接用系统自带的 Edge）\n"
            "  Debian/Ubuntu  sudo apt install -y chromium\n"
            "  Fedora       sudo dnf install -y chromium\n"
            "注意：Safari 走 WebDriver、Firefox 的 CDP 协议不兼容，都不能用于本技能。")
    # 优先 Chrome / Edge，它们的 CDP 最稳
    for pref in ("Chrome", "Edge"):
        for n, p in bs:
            if n == pref:
                return p
    return bs[0][1]


# ------------------------------------------------------------- 端口与 profile
def session_port(name):
    """CRC32 而不是 hash()：Python 的 hash 有随机化，重启进程就变。"""
    return 9300 + (binascii.crc32(name.encode("utf-8")) & 0xFFFFFFFF) % 100


def session_profile(name):
    return os.path.join(PROFILE_ROOT, name)


# ------------------------------------------------------------------ HTTP 侧
def _get_json(url, timeout=3, method="GET"):
    try:
        req = urllib.request.Request(url, method=method,
                                     headers={"Host": urllib.parse.urlparse(url).netloc})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # localhost 不能走代理
        with opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None


def alive(port):
    return _get_json(f"http://127.0.0.1:{port}/json/version") is not None


def list_targets(port):
    return _get_json(f"http://127.0.0.1:{port}/json/list") or []


def version(port):
    return _get_json(f"http://127.0.0.1:{port}/json/version") or {}


# ------------------------------------------------------- WebSocket（最小实现）
class WS:
    """够 CDP 用的最小 WebSocket 客户端：握手 + 发送 masked 文本帧 + 收完整文本帧。

    只实现 CDP 需要的部分：不分片发送、不压缩扩展、收到 ping 回 pong。
    """

    def __init__(self, ws_url, timeout=25):
        u = urllib.parse.urlparse(ws_url)
        host, port = u.hostname, u.port or 80
        path = u.path or "/"
        if u.query:
            path += "?" + u.query
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
               f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        # 读到 \r\n\r\n 为止
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket 握手被对端关闭")
            buf += chunk
        head = buf.split(b"\r\n\r\n")[0].decode("latin-1")
        if " 101 " not in head.split("\r\n")[0]:
            raise ConnectionError(f"WebSocket 握手失败：{head.splitlines()[0] if head else '(空响应)'}")
        self._rest = buf.split(b"\r\n\r\n", 1)[1]

    def _read_exact(self, n):
        data = b""
        if self._rest:
            data, self._rest = self._rest[:n], self._rest[n:]
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("WebSocket 连接已断开")
            data += chunk
        return data

    def send_text(self, text):
        payload = text.encode("utf-8")
        n = len(payload)
        head = b"\x81"                     # FIN + opcode=1(text)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(head + mask + masked)

    def recv_text(self):
        chunks = []
        while True:
            b1, b2 = self._read_exact(2)
            opcode = b1 & 0x0F
            fin = b1 & 0x80
            masked = b2 & 0x80
            ln = b2 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._read_exact(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if masked else b""
            data = self._read_exact(ln) if ln else b""
            if masked and data:
                data = bytes(x ^ mask[i % 4] for i, x in enumerate(data))
            if opcode == 0x9:                       # ping → pong
                self.sock.sendall(b"\x8a" + bytes([0x80]) + os.urandom(4))
                continue
            if opcode == 0x8:                       # close
                raise ConnectionError("对端关闭了 WebSocket")
            if opcode in (0x1, 0x0):                # text / continuation
                chunks.append(data)
                if fin:
                    return b"".join(chunks).decode("utf-8", "replace")

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def cdp(ws_url, method, params=None, timeout=25):
    ws = WS(ws_url, timeout=timeout)
    try:
        ws.send_text(json.dumps({"id": 1, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = json.loads(ws.recv_text())
            if msg.get("id") == 1:
                if "error" in msg:
                    raise RuntimeError(f"{method} 失败：{msg['error']}")
                return msg.get("result", {})
        raise TimeoutError(f"{method} 超时（{timeout}s）")
    finally:
        ws.close()


# ------------------------------------------------------------------ 启动实例
def _clean_env_without_proxy():
    env = os.environ.copy()
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(k, None)
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    return env


def launch(url=None, session="collect", port=None, exe=None, proxy=None, bypass=None, headless=False):
    port = port or session_port(session)
    profile = session_profile(session)
    os.makedirs(profile, exist_ok=True)
    if alive(port):
        return {"port": port, "profile": profile, "already": True, "exe": None}

    exe = pick_browser(exe)
    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run", "--no-default-browser-check",
        "--no-sandbox", "--disable-gpu",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
    ]
    if proxy:
        args.append(f"--proxy-server={proxy}")
        args.append("--proxy-bypass-list=" + (bypass or "127.0.0.1;localhost"))
    else:
        args.append("--no-proxy-server")     # 国内站必须直连，别继承系统代理
    if headless:
        args.append("--headless=new")
    args.append(url or "about:blank")

    kw = {}
    if IS_WIN:
        kw["creationflags"] = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True                  # 脱离 shell，避免被回收
    subprocess.Popen(args, env=_clean_env_without_proxy(),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)

    for _ in range(50):          # 最多等 15 秒
        time.sleep(0.3)
        if alive(port):
            return {"port": port, "profile": profile, "already": False, "exe": exe}
    raise SystemExit(
        f"浏览器起来了但调试端口 {port} 没响应。常见原因：\n"
        f"  · 该 profile 已被另一个窗口占用（换 --session 试）\n"
        f"  · 浏览器版本太老不支持 CDP\n"
        f"  · 安全软件拦截了本地端口")


def pid_on_port(port):
    try:
        if IS_WIN:
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=15).stdout
            for line in out.splitlines():
                if f":{port}" in line and "LISTENING" in line.upper():
                    return int(line.split()[-1])
        else:
            out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                                 capture_output=True, text=True, timeout=10).stdout
            pids = [int(x) for x in out.split() if x.strip().isdigit()]
            return pids[0] if pids else None
    except Exception:
        return None
    return None


def stop(session="collect", port=None):
    port = port or session_port(session)
    pid = pid_on_port(port)
    if not pid:
        return {"port": port, "stopped": False, "reason": "端口上没有监听进程"}
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=15)
        else:
            os.kill(pid, 15)
        for _ in range(20):
            if not alive(port):
                break
            time.sleep(0.25)
        return {"port": port, "pid": pid, "stopped": not alive(port)}
    except Exception as e:
        return {"port": port, "pid": pid, "stopped": False, "reason": str(e)}


# ------------------------------------------------------------------ 页面操作
def pick_target(port, target_id=None, prefer_url=None):
    ts = [t for t in list_targets(port) if t.get("type") == "page"]
    if target_id:
        for t in ts:
            if t.get("id") == target_id:
                return t
        raise SystemExit(f"找不到 target：{target_id}")
    if prefer_url:
        for t in ts:
            if prefer_url in (t.get("url") or ""):
                return t
    if not ts:
        raise SystemExit("端口通，但没有任何 page target。先 open 一个 URL。")
    return ts[0]


def do_eval(port, target_id, js, timeout=25):
    t = pick_target(port, target_id)
    res = cdp(t["webSocketDebuggerUrl"], "Runtime.evaluate", {
        "expression": js, "returnByValue": True, "awaitPromise": True, "userGesture": True,
    }, timeout=timeout)
    if res.get("exceptionDetails"):
        d = res["exceptionDetails"]
        raise SystemExit("JS 执行出错：" + json.dumps(d.get("exception") or d, ensure_ascii=False)[:400])
    r = res.get("result", {})
    return r.get("value") if "value" in r else r


def do_open(port, url):
    """Chrome 111+ 的 /json/new 只接受 PUT，GET 会 405。"""
    r = _get_json(f"http://127.0.0.1:{port}/json/new?{urllib.parse.quote(url, safe='')}", method="PUT")
    if not r:
        raise SystemExit("开新标签失败（旧版 Chrome 用 GET，新版要 PUT；也可能是端口不对）")
    return r


def do_cookies(port):
    v = version(port)
    ws_url = v.get("webSocketDebuggerUrl")
    if not ws_url:
        raise SystemExit("拿不到 browser 级 WebSocket 地址，无法导出 cookie")
    res = cdp(ws_url, "Storage.getCookies", {})
    return res.get("cookies", [])


# ---------------------------------------------------------------------- CLI
def main():
    _fix_stdio()
    ap = argparse.ArgumentParser(description="跨平台 CDP 浏览器启动器（零依赖）")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("find", help="列出本机可用的 Chromium 内核浏览器")

    p = sub.add_parser("start", help="启动带调试端口的浏览器")
    p.add_argument("url", nargs="?")
    p.add_argument("--session", default="collect")
    p.add_argument("--port", type=int)
    p.add_argument("--exe", help="指定浏览器可执行文件")
    p.add_argument("--proxy", help="如 http://127.0.0.1:7890，只给境外站用")
    p.add_argument("--proxy-bypass", help="分号分隔的直连域名，如 *.smzdm.com;localhost")
    p.add_argument("--headless", action="store_true")

    for name in ("status", "stop", "cookies"):
        q = sub.add_parser(name)
        q.add_argument("--session", default="collect")
        q.add_argument("--port", type=int)
        if name == "cookies":
            q.add_argument("--save")

    q = sub.add_parser("list", help="列出页面 target")
    q.add_argument("--session", default="collect")
    q.add_argument("--port", type=int)

    q = sub.add_parser("open", help="开新标签")
    q.add_argument("url")
    q.add_argument("--session", default="collect")
    q.add_argument("--port", type=int)

    q = sub.add_parser("eval", help="在页面执行 JS")
    q.add_argument("js", nargs="?", help="JS 表达式；不传则从 stdin 读")
    q.add_argument("--target", help="页面 target id，默认用第一个 page")
    q.add_argument("--session", default="collect")
    q.add_argument("--port", type=int)
    q.add_argument("--timeout", type=float, default=25)

    q = sub.add_parser("front", help="把标签切到前台（要用户登录时用）")
    q.add_argument("target_id")
    q.add_argument("--session", default="collect")
    q.add_argument("--port", type=int)

    a = ap.parse_args()
    if not a.cmd:
        ap.print_help()
        return

    if a.cmd == "find":
        bs = find_browsers()
        if not bs:
            print("没有可用的 Chromium 内核浏览器。装法见 README「装哪个浏览器」。")
            sys.exit(1)
        for n, p in bs:
            print(f"{n:<14} {p}")
        print(f"\n默认使用：{pick_browser()}")
        return

    port = getattr(a, "port", None) or session_port(getattr(a, "session", "collect"))

    if a.cmd == "start":
        r = launch(a.url, a.session, a.port, a.exe, a.proxy, a.proxy_bypass, a.headless)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        if not r["already"]:
            print(f"# 下次复用同一 session 即可（端口 {r['port']}，profile {r['profile']}）", file=sys.stderr)
        return

    if a.cmd == "status":
        if alive(port):
            v = version(port)
            ts = [t for t in list_targets(port) if t.get("type") == "page"]
            print(json.dumps({"alive": True, "port": port,
                              "browser": v.get("Browser"), "pages": len(ts)}, ensure_ascii=False))
        else:
            print(json.dumps({"alive": False, "port": port}, ensure_ascii=False))
            sys.exit(1)
        return

    if a.cmd == "stop":
        print(json.dumps(stop(a.session, a.port), ensure_ascii=False))
        return

    if a.cmd == "list":
        if not alive(port):
            raise SystemExit(f"端口 {port} 没在监听，先 start")
        for t in list_targets(port):
            if t.get("type") != "page":
                continue
            print(json.dumps({"id": t.get("id"), "title": t.get("title"), "url": t.get("url")},
                             ensure_ascii=False))
        return

    if a.cmd == "open":
        if not alive(port):
            raise SystemExit(f"端口 {port} 没在监听，先 start")
        r = do_open(port, a.url)
        print(json.dumps({"id": r.get("id"), "url": r.get("url")}, ensure_ascii=False))
        return

    if a.cmd == "eval":
        js = a.js if a.js is not None else sys.stdin.read()
        if not js.strip():
            raise SystemExit("没给 JS。用法：browser.py eval \"document.title\" [--target ID]")
        print(json.dumps(do_eval(port, a.target, js, a.timeout), ensure_ascii=False))
        return

    if a.cmd == "cookies":
        cs = do_cookies(port)
        simple = [{"name": c.get("name"), "domain": c.get("domain"), "expires": c.get("expires"),
                   "value_len": len(c.get("value") or "")} for c in cs]
        if a.save:
            d = os.path.dirname(os.path.abspath(a.save))
            if d:
                os.makedirs(d, exist_ok=True)
            with open(a.save, "w", encoding="utf-8") as f:
                json.dump(cs, f, ensure_ascii=False, indent=1)
            try:
                os.chmod(a.save, 0o600)
            except Exception:
                pass
            print(json.dumps({"saved": a.save, "count": len(cs),
                              "note": "含登录凭据，只存本机，不要提交到仓库"}, ensure_ascii=False))
        else:
            print(json.dumps({"count": len(cs), "cookies": simple}, ensure_ascii=False, indent=1))
        return

    if a.cmd == "front":
        t = pick_target(port, a.target_id)
        cdp(t["webSocketDebuggerUrl"], "Page.bringToFront", {})
        print(json.dumps({"ok": True, "url": t.get("url")}, ensure_ascii=False))
        return


if __name__ == "__main__":
    main()
