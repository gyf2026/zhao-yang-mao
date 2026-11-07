#!/usr/bin/env python3
"""数据目录解析 —— 不绑定任何具体的 Agent 宿主。

本技能可以被任何支持"技能/skill"机制的 Agent 使用（WorkBuddy、Claude Code、Codex、
Cursor、自建 Agent……）。脚本自己不假设宿主是谁，只按下述顺序找地方存数据：

  1. 环境变量 `DEAL_HUNTER_HOME`  —— 显式指定，优先级最高
  2. 宿主配置目录 —— 技能装在 `<宿主>/skills/deal-hunter` 时，数据放 `<宿主>/deal-hunter`
     例：~/.workbuddy/skills/deal-hunter  → ~/.workbuddy/deal-hunter
         ~/.claude/skills/deal-hunter     → ~/.claude/deal-hunter
     （只在宿主目录位于家目录内时采用，避免把数据写进别人的代码仓库）
  3. 兜底 `~/.deal-hunter`

旧版本把路径写死成 `~/.workbuddy/deal-hunter`。为了不丢历史台账：
**算出来的目录不存在、而旧目录里有东西时，沿用旧目录**。想搬家直接 `mv`，
脚本下次自动跟到新位置。

调试：`python3 scripts/_paths.py` 打印最终解析结果和判定依据。
"""
import os
import sys

HOME = os.path.expanduser("~")
# scripts/ 的上一级就是技能根目录
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEGACY_DATA = os.path.join(HOME, ".workbuddy", "deal-hunter")
LEGACY_PROFILES = os.path.join(HOME, ".workbuddy", "browser-profiles")

_cache = {}


def _has_entries(p):
    """目录存在且非空。空目录视为"没有数据"，不值得为它保留旧路径。"""
    try:
        return os.path.isdir(p) and bool(os.listdir(p))
    except OSError:
        return False


def _under_home(p):
    try:
        h = os.path.normcase(os.path.realpath(HOME))
        q = os.path.normcase(os.path.realpath(p))
        return q == h or q.startswith(h + os.sep)
    except OSError:
        return False


def _host_root():
    """技能装在 `<宿主>/skills/<技能名>` 时返回 `<宿主>`，否则 None。

    这是唯一可靠的宿主线索：不需要认识具体是哪个客户端，只要是
    "配置目录/skills/技能名" 这种通行结构就成立。
    """
    parent = os.path.dirname(SKILL_DIR)
    if os.path.basename(parent).lower() in ("skills", "skill"):
        root = os.path.dirname(parent)
        if root and root != os.sep and _under_home(root):
            return root
    return None


def data_home():
    """数据目录（台账、cookie、快照、浏览器 profile 都在这下面）。"""
    if "data" in _cache:
        return _cache["data"]

    env = os.environ.get("DEAL_HUNTER_HOME", "").strip()
    if env:
        path, src = os.path.abspath(os.path.expanduser(env)), "env"
    else:
        host = _host_root()
        if host:
            path, src = os.path.join(host, "deal-hunter"), "host"
        else:
            path, src = os.path.join(HOME, ".deal-hunter"), "default"
        # 只有"没装在任何宿主目录里"时才沿用旧位置。
        # 认出了宿主就按宿主自己的目录走 —— 换了客户端还往 .workbuddy 里写，才是怪事；
        # 想让两个宿主共用一份台账，显式设 DEAL_HUNTER_HOME 即可。
        if src == "default" and not os.path.isdir(path) and _has_entries(LEGACY_DATA):
            path, src = LEGACY_DATA, "legacy"

    _cache["data"] = path
    _cache["data_src"] = src
    return path


def data_source():
    """上面那个目录是怎么定下来的：env / host / default / legacy。"""
    data_home()
    return _cache.get("data_src", "default")


def profile_root():
    """浏览器 profile 根目录。放在数据目录里，跟着数据一起走。"""
    if "profile" in _cache:
        return _cache["profile"]

    env = os.environ.get("DEAL_HUNTER_PROFILE_ROOT", "").strip()
    if env:
        path = os.path.abspath(os.path.expanduser(env))
    else:
        path = os.path.join(data_home(), "browser-profiles")
        # 旧版把 profile 放在 `~/.workbuddy/browser-profiles`（数据目录的同级）。
        # 只有在"数据目录本来就在那个宿主根下"时才沿用它，别把别人的浏览器身份搬过来。
        same_root = os.path.normcase(os.path.dirname(LEGACY_PROFILES)) == \
            os.path.normcase(os.path.dirname(data_home()))
        if same_root and not os.path.isdir(path) and _has_entries(LEGACY_PROFILES):
            path = LEGACY_PROFILES
    _cache["profile"] = path
    return path


def cookies_dir():
    return os.path.join(data_home(), "cookies")


def describe():
    """给自检和文档用的一行说明。"""
    src = {"env": "环境变量 DEAL_HUNTER_HOME",
           "host": "宿主配置目录",
           "default": "通用默认位置",
           "legacy": "沿用旧版目录（数据没搬）"}.get(data_source(), data_source())
    return {"data": data_home(), "source": data_source(), "why": src,
            "profiles": profile_root(), "cookies": cookies_dir()}


if __name__ == "__main__":
    for k, v in describe().items():
        print(f"{k:<10} {v}")

if sys.version_info < (3, 8):      # 本文件会被其它脚本 import，早失败早报错
    raise SystemExit("需要 Python 3.8+")
