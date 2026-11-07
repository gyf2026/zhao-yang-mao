#!/usr/bin/env python3
"""deal-hunter 环境自检 + 依赖补全计划。

两件事：
  1. 查清这台机器能不能跑（七项）
  2. 缺什么、按什么顺序补、命令是什么 —— 让 Agent 能自己把环境配起来

设计前提：**能不装就不装**。浏览器控制已改为本仓库自带的 `scripts/browser.py`
（纯标准库，自己实现 WebSocket），所以不需要 node、不需要 websocket-client、
也不需要额外装别的技能。这台机器只要求两样东西：Python ≥3.8 + 一个 Chromium 内核浏览器。

用法：
  python3 scripts/doctor.py            # 人读报告（含补全建议）
  python3 scripts/doctor.py --json     # 机器可读
  python3 scripts/doctor.py --plan     # 只输出"要补什么"，按顺序给命令
  python3 scripts/doctor.py --fix      # 执行安全操作（建目录、初始化台账），不装软件
  python3 scripts/doctor.py --no-net   # 不发任何网络请求

退出码：0=ready  1=能跑但有缺失（浏览器类功能可能不可用）  2=致命
"""
import argparse, json, os, platform, shutil, socket, subprocess, sys
import urllib.request

OK, WARN, FAIL = "ok", "warn", "fail"
ICON = {OK: "[ok]", WARN: "[!]", FAIL: "[x]"}       # 不用 ✓×，Windows 控制台会乱码
MIN_PY = (3, 8)
IS_WIN = platform.system() == "Windows"
SYSNAME = platform.system()
HOME = os.path.expanduser("~")
DATA = os.path.expanduser(os.environ.get("DEAL_HUNTER_HOME", "~/.workbuddy/deal-hunter"))
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fix_stdio():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ---------------------------------------------------------------- 1. 系统
def check_system():
    v = sys.version_info
    ok = v[:2] >= MIN_PY
    return {
        "key": "system", "status": OK if ok else FAIL, "blocking": not ok,
        "title": "Python 运行时",
        "detail": f"{SYSNAME} {platform.release()}（{platform.machine()}）· Python {v.major}.{v.minor}.{v.micro}",
        "fix": [] if ok else [
            {"kind": "manual", "desc": f"Python 版本过低，需要 ≥ {MIN_PY[0]}.{MIN_PY[1]}",
             "install": {
                 "Darwin": "brew install python@3.12   # 或去 python.org 下安装包",
                 "Windows": "winget install Python.Python.3.12   # 或去 python.org 下安装包",
                 "Linux": "sudo apt install -y python3   # Debian/Ubuntu；Fedora 用 dnf",
             }},
        ],
    }


# ---------------------------------------------------------- 2. 外置浏览器
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
_LINUX_CMDS = [("Chrome", "google-chrome"), ("Chrome", "google-chrome-stable"),
               ("Chromium", "chromium"), ("Chromium", "chromium-browser"),
               ("Edge", "microsoft-edge"), ("Brave", "brave-browser")]


def _version_of(path):
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=6)
        txt = (out.stdout or out.stderr or "").strip()
        return txt.splitlines()[0][:60] if txt else ""
    except Exception:
        return ""


def find_browsers():
    found, seen = [], set()
    if SYSNAME == "Darwin":
        for name, rel in _MAC:
            for root in _MAC_ROOTS:
                p = os.path.join(root, rel)
                if os.path.exists(p) and p not in seen:
                    seen.add(p)
                    found.append({"name": name, "path": p, "version": _version_of(p)})
    elif IS_WIN:
        for name, rel in _WIN:
            for root in _WIN_ROOTS:
                if not root:
                    continue
                p = os.path.join(root, rel)
                if os.path.exists(p) and p not in seen:
                    seen.add(p)
                    found.append({"name": name, "path": p, "version": _version_of(p)})
    else:
        for name, cmd in _LINUX_CMDS:
            p = shutil.which(cmd)
            if p and p not in seen:
                seen.add(p)
                found.append({"name": name, "path": p, "version": _version_of(p)})
    return found


def _install_opts():
    """按当前平台给出可执行的安装命令；没有包管理器就退化成手动指引。"""
    if SYSNAME == "Darwin":
        if shutil.which("brew"):
            return {"brew": "brew install --cask google-chrome"}
        return {"manual": "去 google.com/chrome 下载 dmg 安装；或先装 Homebrew 再 brew install --cask google-chrome"}
    if IS_WIN:
        if shutil.which("winget"):
            return {"winget": "winget install --id Google.Chrome -e --accept-source-agreements --accept-package-agreements",
                    "note": "Windows 也可以直接用系统自带的 Microsoft Edge，不需要另装"}
        return {"manual": "去 google.com/chrome 下载安装；Windows 10/11 自带 Edge，也可以直接用"}
    if shutil.which("apt"):
        return {"apt": "sudo apt update && sudo apt install -y chromium"}
    if shutil.which("dnf"):
        return {"dnf": "sudo dnf install -y chromium"}
    return {"manual": "用发行版包管理器装 chromium（如 pacman -S chromium）"}


def check_browser(browsers):
    if not browsers:
        return {"key": "browser", "status": FAIL, "blocking": True,
                "title": "外置浏览器", "detail": "没找到任何 Chromium 内核浏览器",
                "fix": [{"kind": "install", "desc": "装一个 Chromium 内核浏览器（Safari 和 Firefox 不能用）",
                         "install": _install_opts()}],
                "browsers": []}
    top = browsers[0]
    names = [b["name"] for b in browsers]
    advice = ""
    if top["name"] not in ("Chrome", "Edge"):
        advice = "首选不是 Chrome/Edge，能用但 CDP 兼容性问题更多，出怪问题时换 Chrome"
    elif "QQ浏览器" in names:
        advice = "Chrome 是首选；WorkBuddy 环境下 Chrome 若出现窗口收不到指令，可换 QQ 浏览器对照"
    return {"key": "browser", "status": OK, "blocking": False, "title": "外置浏览器",
            "detail": f"找到 {len(browsers)} 个（{'、'.join(names)}），首选 {top['name']}"
                      + (f"（{top['version']}）" if top["version"] else ""),
            "advice": advice, "browsers": browsers, "fix": []}


# ------------------------------------------------- 3. 浏览器控制通道（自带）
def check_channel():
    own = os.path.join(SKILL_DIR, "scripts", "browser.py")
    if os.path.exists(own):
        # 真跑一次 find，确认它能执行（不是只有个文件）
        try:
            r = subprocess.run([sys.executable, own, "find"],
                               capture_output=True, text=True, timeout=20)
            ok = r.returncode == 0
            body = (r.stdout or "").split("默认使用")[0]      # 别把尾部提示当成浏览器计数
            n_browser = len([x for x in body.splitlines() if x.strip()])
            detail = "自带 scripts/browser.py（零依赖 CDP 控制器）" + (
                f"，可驱动 {n_browser} 个浏览器" if ok and n_browser else "")
        except Exception as e:
            ok, detail = False, f"scripts/browser.py 执行失败：{type(e).__name__}"
        if ok:
            return {"key": "channel", "status": OK, "blocking": False,
                    "title": "浏览器控制", "detail": detail, "fix": []}
        return {"key": "channel", "status": FAIL, "blocking": True,
                "title": "浏览器控制", "detail": detail,
                "fix": [{"kind": "manual", "desc": "自带控制器跑不起来，先确认 Python 环境完整，"
                                                  "或用外置方案：装 browser-cdp-control 技能"}]}

    # 没有自带脚本时，看有没有外部技能可用（兼容旧环境）
    bcc = os.path.join(HOME, ".workbuddy", "skills", "browser-cdp-control", "scripts")
    sh_ = os.path.join(bcc, "browser_cdp.sh")
    ps1 = os.path.join(bcc, "browser_cdp.ps1")
    if os.path.exists(sh_) or os.path.exists(ps1):
        return {"key": "channel", "status": WARN, "blocking": False,
                "title": "浏览器控制",
                "detail": "缺少自带 scripts/browser.py，但检测到 browser-cdp-control 技能，可临时用",
                "fix": [{"kind": "manual", "desc": "重新拉取本仓库，scripts/browser.py 是自带的跨平台控制器"}]}
    return {"key": "channel", "status": FAIL, "blocking": True, "title": "浏览器控制",
            "detail": "既没有 scripts/browser.py，也没有 browser-cdp-control 技能",
            "fix": [{"kind": "manual", "desc": "重新 clone 本仓库；scripts/browser.py 应该随仓库一起下发"}]}


# --------------------------------------------------------------- 4. 代理
def _env_proxy():
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        v = os.environ.get(k)
        if v:
            return k, v
    return None, None


def _port_open(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_proxy():
    k, v = _env_proxy()
    if not v:
        return {"key": "proxy", "status": WARN, "blocking": False, "title": "代理",
                "detail": "没有代理环境变量（只影响境外源）",
                "advice": "X / Slickdeals / DealMoon / OpenRouter 需要代理；国内源不需要，脚本已强制直连",
                "fix": []}
    host, port = "127.0.0.1", None
    try:
        s = v.split("//")[-1].split("@")[-1]
        host = s.split(":")[0] or "127.0.0.1"
        port = int(s.split(":")[1].split("/")[0])
    except (ValueError, IndexError):
        return {"key": "proxy", "status": WARN, "blocking": False, "title": "代理",
                "detail": f"{k}={v} 解析不出端口", "advice": "代理地址应为 http://host:port", "fix": []}
    alive = _port_open(host, port)
    return {"key": "proxy", "status": OK if alive else FAIL,
            "blocking": False, "title": "代理",
            "detail": f"{k}={v}（端口 {'可连接' if alive else '连不上'}）",
            "advice": "" if alive else "代理软件没开或端口变了；以 env | grep -i proxy 的实时值为准",
            "fix": [] if alive else [
                {"kind": "manual", "desc": "启动代理软件（Clash / v2rayN 等），建议设开机自启",
                 "note": "只在需要境外源时才必须；国内源不依赖它"}]}


# --------------------------------------------------------------- 5. 网络
def check_net():
    """只探国内主源，直连。UA 必须完整——实测简写 UA 会被直接判定机器人。
    （2026-11-07：UA 写 "Mozilla/5.0" → 1697 字节 TCaptcha 页；完整 UA → 250KB 正常页。）"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        "https://faxian.smzdm.com/",
        headers={"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
                 "Accept-Language": "zh-CN,zh;q=0.9"})
    try:
        with opener.open(req, timeout=10) as r:
            n = len(r.read())
        ok = n > 6000
        return {"key": "net", "status": OK if ok else WARN, "blocking": False,
                "title": "网络（国内主源）",
                "detail": f"faxian.smzdm.com 返回 {n} 字节" + ("" if ok else "，疑似验证码页"),
                "advice": "" if ok else "用浏览器打开一次拖过滑块，或降低扫描频率",
                "fix": [] if ok else [
                    {"kind": "manual", "desc": "浏览器打开 https://faxian.smzdm.com/ 手动过一次验证码"}]}
    except Exception as e:
        return {"key": "net", "status": WARN, "blocking": False, "title": "网络（国内主源）",
                "detail": f"连不上：{type(e).__name__}", "advice": "检查网络；挂着代理时国内站要绕开",
                "fix": []}


# ----------------------------------------------------------- 6. 数据目录
def check_data():
    files = {"watchlist.md": "关注清单", "pushed.jsonl": "好价台账",
             "pushed-wool.jsonl": "羊毛台账", "scan.jsonl": "扫描台账"}
    exists = os.path.isdir(DATA)
    state = {f: (os.path.getsize(os.path.join(DATA, f)) if os.path.exists(os.path.join(DATA, f)) else None)
             for f in files}
    init_fix = [{"kind": "auto", "desc": "初始化数据目录与台账",
                 "cmd": [sys.executable, os.path.join(SKILL_DIR, "scripts", "ledger.py"), "init"]}]
    if not exists:
        return {"key": "data", "status": WARN, "blocking": False, "title": "数据目录",
                "detail": f"{DATA} 还没建", "fix": init_fix, "files": state}
    missing = [f for f, s in state.items() if s is None]
    empty = [f for f, s in state.items() if s == 0]
    if missing:
        return {"key": "data", "status": WARN, "blocking": False, "title": "数据目录",
                "detail": f"缺 {','.join(missing)}",
                "advice": "关注清单缺了会问不出方向，台账缺了就没法去重和回查",
                "fix": init_fix, "files": state}
    if empty:
        # 只有"一份记录都没有"才算没跑过。单看 pushed.jsonl 会误判：
        # 只跑羊毛那一段时好价台账本来就是空的（2026-11-07 实测踩到）。
        ledgers = ("pushed.jsonl", "pushed-wool.jsonl", "scan.jsonl")
        ran = any(state.get(f) for f in ledgers)
        if not ran:
            return {"key": "data", "status": WARN, "blocking": False, "title": "数据目录",
                    "detail": f"存在，但台账全是空的（{','.join(empty)}）",
                    "advice": "空台账 = 从没真跑过一轮。先手动跑通再开定时任务",
                    "fix": [], "files": state}
        return {"key": "data", "status": OK, "blocking": False, "title": "数据目录",
                "detail": f"{DATA} 正常，已跑过（空的是 {','.join(empty)}）",
                "fix": [], "files": state}
    return {"key": "data", "status": OK, "blocking": False, "title": "数据目录",
            "detail": f"{DATA} 正常", "fix": [], "files": state}


# ------------------------------------------------------------- 7. 登录态
def check_login():
    d = os.path.join(DATA, "cookies")
    if not os.path.isdir(d):
        return {"key": "login", "status": WARN, "blocking": False, "title": "登录态",
                "detail": "还没保存过 cookie（只影响 X / LINUX DO 这类要登录的源）",
                "advice": "让用户在浏览器窗口里自己登录，之后 browser.py cookies --save 导出",
                "fix": []}
    n = len([f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))])
    return {"key": "login", "status": OK if n else WARN, "blocking": False, "title": "登录态",
            "detail": f"已存 {n} 份 cookie" if n else "cookies 目录空",
            "advice": "" if n else "登录后要导出，session cookie 关窗就没了", "fix": []}


# ------------------------------------------------------------------ 汇总
def main():
    _fix_stdio()
    ap = argparse.ArgumentParser(description="deal-hunter 环境自检")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--plan", action="store_true", help="只输出补全计划")
    ap.add_argument("--fix", action="store_true", help="执行安全的自动补全（建目录/初始化台账），不装软件")
    ap.add_argument("--no-net", action="store_true")
    a = ap.parse_args()

    checks = [check_system(), check_browser(find_browsers()), check_channel(),
              check_proxy(), check_data(), check_login()]
    if not a.no_net and not a.plan:
        checks.append(check_net())

    fails = [c for c in checks if c["status"] == FAIL]
    warns = [c for c in checks if c["status"] == WARN]
    blocking = [c for c in fails if c.get("blocking")]
    verdict = "blocked" if blocking else ("usable-with-warnings" if (fails or warns) else "ready")

    # ---- --plan：只列要补的东西，按阻塞优先级排序
    if a.plan:
        plan = []
        for c in sorted(checks, key=lambda x: (not x.get("blocking"), x["status"] != FAIL)):
            for f in c.get("fix", []):
                plan.append({"for": c["title"], "status": c["status"], **f})
        print(json.dumps({"verdict": verdict, "steps": plan}, ensure_ascii=False, indent=1))
        sys.exit(2 if blocking else (1 if (fails or warns) else 0))

    # ---- --fix：只做安全操作
    if a.fix:
        done = []
        for c in checks:
            for f in c.get("fix", []):
                if f.get("kind") == "auto" and f.get("cmd"):
                    try:
                        r = subprocess.run(f["cmd"], capture_output=True, text=True, timeout=60)
                        done.append({"step": f["desc"], "ok": r.returncode == 0,
                                     "out": (r.stdout or r.stderr or "").strip()[:300]})
                    except Exception as e:
                        done.append({"step": f["desc"], "ok": False, "out": str(e)})
        checks = [check_system(), check_browser(find_browsers()), check_channel(),
                  check_proxy(), check_data(), check_login()]
        fails = [c for c in checks if c["status"] == FAIL]
        warns = [c for c in checks if c["status"] == WARN]
        blocking = [c for c in fails if c.get("blocking")]
        verdict = "blocked" if blocking else ("usable-with-warnings" if (fails or warns) else "ready")
        print(json.dumps({"fixed": done, "verdict_now": verdict}, ensure_ascii=False, indent=1))
        sys.exit(2 if blocking else (1 if (fails or warns) else 0))

    if a.json:
        print(json.dumps({"verdict": verdict, "data_dir": DATA,
                          "checks": checks}, ensure_ascii=False, indent=1))
        sys.exit(2 if blocking else (1 if (fails or warns) else 0))

    print("deal-hunter 环境自检\n")
    for c in checks:
        print(f"  {ICON[c['status']]} {c['title']:<16} {c['detail']}")
        if c.get("advice"):
            print(f"       → {c['advice']}")
    if checks[1].get("browsers"):
        print("\n  可用浏览器：")
        for b in checks[1]["browsers"]:
            print(f"    · {b['name']:<12} {(b['version'] or '版本未知')[:38]}")
            print(f"      {b['path']}")

    todo = [f for c in checks for f in c.get("fix", [])]
    if todo:
        print("\n  待补全：")
        for f in todo:
            print(f"    · {f['desc']}")
            if f.get("cmd"):
                print(f"      $ {' '.join(f['cmd'])}")
            for k, v in (f.get("install") or {}).items():
                print(f"      {k}: {v}")
            if f.get("note"):
                print(f"      注：{f['note']}")

    print()
    if verdict == "ready":
        print("结论：可以开扫。")
    elif verdict == "usable-with-warnings":
        print(f"结论：能跑，{len(fails) + len(warns)} 项待补（见上）。"
              "直连源不受影响；浏览器类问题会打折。")
    else:
        print(f"结论：{len(blocking)} 项阻塞，浏览器类能力不可用，只能跑 A 段直连。")
    sys.exit(2 if blocking else (1 if (fails or warns) else 0))


if __name__ == "__main__":
    main()
