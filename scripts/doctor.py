#!/usr/bin/env python3
"""deal-hunter 环境自检：开扫之前先确认"这台机器到底能不能跑"。

为什么必须先自检：这个技能的 A 段靠直连脚本，B 段（X / LINUX DO / 券）
和大部分站点的时效核验**全靠真浏览器 + 登录态**。浏览器这一环断了，
技能不会报错，只会安静地少推几条 —— 用户以为在盯，其实半瞎。

检查七项：
  1. 系统与 Python
  2. 外置浏览器（必须是 Chromium 内核，Safari 不行）
  3. 浏览器控制通道（CDP 启动器 + node）
  4. 代理（境外站要用，国内站要绕开）
  5. 网络（只轻量探国内主源，不刷接口）
  6. 数据目录与台账
  7. 登录态（cookie 有没有存过）

用法：
  python3 scripts/doctor.py            # 人读报告
  python3 scripts/doctor.py --json     # 机器可读
  python3 scripts/doctor.py --no-net   # 跳过网络探测（不想发任何请求时）

退出码：0=可以跑（可能带警告）  1=有条件阻塞（缺浏览器/缺通道）  2=致命（Python 版本过低）
"""
import argparse, json, os, platform, shutil, socket, subprocess, sys
import urllib.request

OK, WARN, FAIL = "ok", "warn", "fail"
ICON = {OK: "✓", WARN: "!", FAIL: "×"}
MIN_PY = (3, 8)


# ---------------------------------------------------------------- 1. 系统
def check_system():
    v = sys.version_info
    ok = v[:2] >= MIN_PY
    return {
        "key": "system", "status": OK if ok else FAIL,
        "title": "系统与运行时",
        "detail": f"{platform.system()} {platform.release()}（{platform.machine()}）· Python {v.major}.{v.minor}.{v.micro}",
        "advice": "" if ok else f"Python 版本过低，需要 ≥ {MIN_PY[0]}.{MIN_PY[1]}",
    }


# ---------------------------------------------------------- 2. 外置浏览器
# 只有 Chromium 内核能用 CDP。Safari 走 WebDriver、Firefox 协议不兼容，都不列。
_MAC_ROOTS = ["/Applications", os.path.expanduser("~/Applications")]
_MAC = [
    ("Chrome", "Google Chrome.app/Contents/MacOS/Google Chrome", "首选，CDP 支持最完整"),
    ("Edge", "Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "Windows/macOS 通用，Chromium 内核"),
    ("QQ浏览器", "QQBrowser.app/Contents/MacOS/QQBrowser", "国产 Chromium，WorkBuddy 环境配合较好"),
    ("Brave", "Brave Browser.app/Contents/MacOS/Brave Browser", "Chromium 内核"),
    ("Chromium", "Chromium.app/Contents/MacOS/Chromium", "开源原版"),
    ("360极速浏览器", "360Chrome.app/Contents/MacOS/360Chrome", "国产 Chromium"),
]
_WIN = [
    ("Chrome", r"Google\Chrome\Application\chrome.exe", "首选，CDP 支持最完整"),
    ("Edge", r"Microsoft\Edge\Application\msedge.exe", "Windows 自带，无需另装"),
    ("QQ浏览器", r"Tencent\QQBrowser\QQBrowser.exe", "国产 Chromium，WorkBuddy 环境配合较好"),
    ("360极速浏览器", r"360Chrome\Chrome\Application\360chrome.exe", "国产 Chromium"),
    ("Brave", r"BraveSoftware\Brave-Browser\Application\brave.exe", "Chromium 内核"),
]
_WIN_ROOTS = [os.environ.get("ProgramFiles", r"C:\Program Files"),
              os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
              os.path.expandvars(r"%LOCALAPPDATA%")]
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
    sysname = platform.system()
    if sysname == "Darwin":
        for name, rel, note in _MAC:
            for root in _MAC_ROOTS:
                p = os.path.join(root, rel)
                if os.path.exists(p) and p not in seen:
                    seen.add(p)
                    found.append({"name": name, "path": p, "note": note, "version": _version_of(p)})
    elif sysname == "Windows":
        for name, rel, note in _WIN:
            for root in _WIN_ROOTS:
                if not root:
                    continue
                p = os.path.join(root, rel)
                if os.path.exists(p) and p not in seen:
                    seen.add(p)
                    found.append({"name": name, "path": p, "note": note, "version": _version_of(p)})
    else:
        for name, cmd in _LINUX_CMDS:
            p = shutil.which(cmd)
            if p and p not in seen:
                seen.add(p)
                found.append({"name": name, "path": p, "note": "Linux Chromium 系",
                              "version": _version_of(p)})
    return found


def check_browser(browsers):
    if not browsers:
        tip = {
            "Darwin": "装 Google Chrome（官网 dmg）或腾讯 QQ 浏览器；Safari 不支持 CDP，不能用于本技能",
            "Windows": "装 Google Chrome，或直接用系统自带的 Microsoft Edge（Chromium 内核，同样能用）",
            "Linux": "apt/dnf 安装 google-chrome 或 chromium",
        }.get(platform.system(), "装一个 Chromium 内核浏览器")
        return {"key": "browser", "status": FAIL, "title": "外置浏览器",
                "detail": "没找到任何 Chromium 内核浏览器", "advice": tip}
    top = browsers[0]
    names = [b["name"] for b in browsers]
    warn = ""
    # Chrome 单独挑出来说：它不是"随便一个能开的浏览器"，而是登录态容器
    if top["name"] not in ("Chrome", "Edge"):
        warn = "当前首选不是 Chrome/Edge，能用但 CDP 兼容性问题更多；出怪问题时优先换 Chrome 试"
    elif "QQ浏览器" in names:
        warn = "Chrome 是首选；若 WorkBuddy 环境下 Chrome 出现窗口收不到指令之类的怪问题，可换 QQ 浏览器对照一下"
    return {"key": "browser", "status": OK, "title": "外置浏览器",
            "detail": f"找到 {len(browsers)} 个（{'、'.join(names)}），首选 {top['name']}"
                      + (f"（{top['version']}）" if top["version"] else ""),
            "advice": warn, "browsers": browsers}


# -------------------------------------------------- 3. 浏览器控制通道（CDP）
def check_channel():
    here = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(here)
    cands = []

    bcc = os.path.expanduser("~/.workbuddy/skills/browser-cdp-control/scripts")
    if os.path.exists(os.path.join(bcc, "browser_cdp.sh")):
        cands.append({"path": os.path.join(bcc, "browser_cdp.sh"), "how": "browser-cdp-control 技能",
                      "rank": 1, "platform": "macOS/Linux"})
    if os.path.exists(os.path.join(bcc, "browser_cdp.ps1")):
        cands.append({"path": os.path.join(bcc, "browser_cdp.ps1"), "how": "browser-cdp-control 技能",
                      "rank": 1, "platform": "Windows"})

    # 仓库自带（Windows 专用）
    own_ps1 = os.path.join(skill_dir, "scripts", "browser_cdp.ps1")
    if os.path.exists(own_ps1):
        cands.append({"path": own_ps1, "how": "本技能自带", "rank": 2, "platform": "Windows"})
    own_sh = os.path.join(skill_dir, "scripts", "browser_cdp.sh")
    if os.path.exists(own_sh):
        cands.append({"path": own_sh, "how": "本技能自带", "rank": 2, "platform": "macOS/Linux"})

    node = shutil.which("node")
    node_v = ""
    if node:
        try:
            node_v = subprocess.run([node, "-v"], capture_output=True, text=True, timeout=5).stdout.strip()
        except Exception:
            pass

    # 按当前平台过滤
    sysname = platform.system()
    plat = "Windows" if sysname == "Windows" else "macOS/Linux"
    usable = [c for c in cands if c["platform"] == plat]

    if usable and node:
        c = sorted(usable, key=lambda x: x["rank"])[0]
        return {"key": "channel", "status": OK, "title": "浏览器控制通道",
                "detail": f"{c['how']}（{c['path']}）· node {node_v}",
                "advice": "", "channels": usable, "node": node}
    if usable and not node:
        return {"key": "channel", "status": WARN, "title": "浏览器控制通道",
                "detail": f"有启动器但没找到 node（{usable[0]['path']}）",
                "advice": "装 Node.js ≥ 18（WorkBuddy 自带的可执行 node 也可），CDP 控制脚本依赖它",
                "channels": usable, "node": node}
    if node and not usable:
        return {"key": "channel", "status": FAIL, "title": "浏览器控制通道",
                "detail": f"有 node {node_v}，但没有找到可用的 CDP 启动器",
                "advice": "装 browser-cdp-control 技能（本技能所有浏览器操作都依赖它），"
                          "或使用本仓库 scripts/ 下对应平台的启动脚本", "node": node}
    return {"key": "channel", "status": FAIL, "title": "浏览器控制通道",
            "detail": "既没有 CDP 启动器，也没有 node",
            "advice": "先装 Node.js ≥ 18，再装 browser-cdp-control 技能", "node": node}


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
        return {"key": "proxy", "status": WARN, "title": "代理",
                "detail": "没有检测到代理环境变量",
                "advice": "X / Slickdeals / DealMoon / OpenRouter 等境外源需要代理。"
                          "Clash、v2rayN 之类开好并设开机自启；国内站则必须绕开代理（脚本已内置直连）"}
    host, port = "127.0.0.1", None
    try:
        s = v.split("//")[-1].split("@")[-1]
        host = s.split(":")[0] or "127.0.0.1"
        port = int(s.split(":")[1].split("/")[0])
    except (ValueError, IndexError):
        return {"key": "proxy", "status": WARN, "title": "代理",
                "detail": f"{k}={v} 解析不出端口", "advice": "确认代理地址格式为 http://host:port"}
    alive = _port_open(host, port)
    return {"key": "proxy", "status": OK if alive else FAIL, "title": "代理",
            "detail": f"{k}={v}（端口 {'可连接' if alive else '连不上'}）",
            "advice": "" if alive else "代理软件没开或端口变了。以 env | grep -i proxy 的实时值为准，别用记下来的旧端口",
            "proxy": v, "port": port, "alive": alive}


# --------------------------------------------------------------- 5. 网络
def check_net():
    """只探国内主源，一个请求，走直连。境外站不测：走代理是正常分流，测了也是误导。

    UA 必须写完整。实测（2026-11-07）：UA 只写 "Mozilla/5.0" 时 smzdm 直接返
    TCaptcha 验证码页（1697 字节），换成完整 Chrome UA 同一个地址返回 250KB 正常页。
    用简写 UA 自检会把自己的误报当成"被 WAF 拦"。
    """
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        "https://faxian.smzdm.com/",
        headers={"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
                 "Accept-Language": "zh-CN,zh;q=0.9"})
    try:
        with opener.open(req, timeout=10) as r:
            body = r.read()
        n = len(body)
        ok = n > 6000      # 被 WAF 拦时只有 ~1.7KB
        return {"key": "net", "status": OK if ok else WARN, "title": "网络（国内主源）",
                "detail": f"faxian.smzdm.com 返回 {n} 字节" + ("" if ok else "，疑似被验证码页拦截"),
                "advice": "" if ok else "页面过小多半被 WAF 拦了。用浏览器打开一次、拖过滑块，或者降低扫描频率"}
    except Exception as e:
        return {"key": "net", "status": WARN, "title": "网络（国内主源）",
                "detail": f"连不上：{type(e).__name__}", "advice": "检查网络；若挂着代理，国内站要绕开"}


# ----------------------------------------------------------- 6. 数据目录
def check_data():
    base = os.path.expanduser("~/.workbuddy/deal-hunter")
    files = {
        "watchlist.md": "关注清单",
        "pushed.jsonl": "已推好价台账",
        "pushed-wool.jsonl": "已推羊毛台账",
        "scan.jsonl": "扫描台账",
    }
    state = {}
    for f, desc in files.items():
        p = os.path.join(base, f)
        state[f] = os.path.getsize(p) if os.path.exists(p) else None
    exists = os.path.isdir(base)
    missing = [f for f, s in state.items() if s is None]
    if not exists:
        return {"key": "data", "status": WARN, "title": "数据目录",
                "detail": f"{base} 还没建",
                "advice": "跑一次 python3 scripts/ledger.py init 就建好了", "files": state}
    empty = [f for f, s in state.items() if s == 0]
    if missing or empty:
        msg = "；".join(x for x in [
            f"缺 {','.join(missing)}" if missing else "",
            f"空台账 {','.join(empty)}" if empty else ""] if x)
        return {"key": "data", "status": WARN, "title": "数据目录",
                "detail": f"{base} 存在，但 {msg}",
                "advice": "空台账说明还没真正跑过一轮。首次务必手动跑通再开定时任务", "files": state}
    return {"key": "data", "status": OK, "title": "数据目录",
            "detail": f"{base} 正常", "advice": "", "files": state}


# ------------------------------------------------------------- 7. 登录态
def check_login():
    d = os.path.expanduser("~/.workbuddy/deal-hunter/cookies")
    if not os.path.isdir(d):
        return {"key": "login", "status": WARN, "title": "登录态",
                "detail": "还没有保存过任何站点的 cookie",
                "advice": "X / LINUX DO 需要登录。让用户在自己的浏览器窗口里完成登录（扫码/验证码），"
                          "Agent 全程不碰账号密码，登录成功后导出 cookie 免下次再登"}
    n = len([f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))])
    return {"key": "login", "status": OK if n else WARN, "title": "登录态",
            "detail": f"已存 {n} 份 cookie" if n else "cookies 目录存在但没有文件",
            "advice": "" if n else "登录后记得 dumpcookie，session cookie 关窗就没了"}


# ------------------------------------------------------------------ 汇总
def main():
    ap = argparse.ArgumentParser(description="deal-hunter 环境自检")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-net", action="store_true", help="跳过网络探测")
    a = ap.parse_args()

    checks = [check_system(), check_browser(find_browsers()), check_channel(),
              check_proxy(), check_data(), check_login()]
    if not a.no_net:
        checks.append(check_net())

    fails = [c for c in checks if c["status"] == FAIL]
    warns = [c for c in checks if c["status"] == WARN]
    verdict = "blocked" if fails else ("usable-with-warnings" if warns else "ready")

    if a.json:
        print(json.dumps({"verdict": verdict,
                          "can_run_script_only": not any(c["key"] in ("system",) and c["status"] == FAIL
                                                          for c in checks),
                          "checks": checks}, ensure_ascii=False, indent=1))
        sys.exit(2 if any(c["key"] == "system" and c["status"] == FAIL for c in checks)
                 else (1 if fails else 0))

    print("deal-hunter 环境自检\n")
    for c in checks:
        print(f"  {ICON[c['status']]} {c['title']:<14} {c['detail']}")
        if c["advice"]:
            print(f"      → {c['advice']}")
    if checks and checks[1].get("browsers"):
        print("\n  可用浏览器：")
        for b in checks[1]["browsers"]:
            print(f"    · {b['name']:<12} {b['version'][:40] or '版本未知'}")
            print(f"      {b['path']}")

    print()
    if verdict == "ready":
        print("结论：可以开扫。")
    elif verdict == "usable-with-warnings":
        print(f"结论：能跑，但有 {len(warns)} 项要注意（上面标 ! 的）。"
              "纯脚本的部分（smzdm / V2EX）不受影响，浏览器相关的会打折。")
    else:
        print(f"结论：有 {len(fails)} 项阻塞，浏览器相关能力不可用。"
              "建议先修上面的 × 项，否则只能跑 A 段直连部分。")
        print("      注意：内部没有真浏览器时，Agent 的浏览器类工具会静默回退到自带 Chromium，"
              "表现为「报成功但屏幕上的窗口收不到指令」，这不是能用。")
    print()
    sys.exit(2 if any(c["key"] == "system" and c["status"] == FAIL for c in checks)
             else (1 if fails else 0))


if __name__ == "__main__":
    main()
