#!/usr/bin/env python3
"""deal-hunter 辅助脚本：台账去重 / 随机延迟 / 原始快照路径 / 初始化数据目录。

数据目录默认 ~/.workbuddy/deal-hunter/（可用环境变量 DEAL_HUNTER_HOME 覆盖）
  pushed.jsonl     已推送的好价（A 类）
  pushed-wool.jsonl 已推送的羊毛（B 类）
  watchlist.md     用户关注清单
  raw/YYYY-MM-DD/  原始抓取快照
  skipped.log      跳过轮次记录
"""
import argparse, json, os, random, re, shutil, sys, time
from datetime import datetime
from urllib.parse import urlparse

HOME = os.path.expanduser(os.environ.get("DEAL_HUNTER_HOME", "~/.workbuddy/deal-hunter"))
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACK = re.compile(r"^(utm_|spm|from|fromTo|ref|share|sid|zdm_)", re.I)


def norm(url: str) -> str:
    """URL 归一化：去协议/参数/锚点/尾斜杠；smzdm 取文章 ID。"""
    u = urlparse(url.strip())
    host = u.netloc.lower().removeprefix("www.")
    path = u.path.rstrip("/")
    if host.endswith("smzdm.com"):
        m = re.search(r"/(?:p|post|youhui|fx)/(\d+)", path) or re.search(r"/(\d{6,})", path)
        if m:
            return f"smzdm:{m.group(1)}"
    return f"{host}{path}"


def ledger(kind: str) -> str:
    return os.path.join(HOME, "pushed-wool.jsonl" if kind == "wool" else "pushed.jsonl")


def load(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def cmd_init(a):
    os.makedirs(os.path.join(HOME, "raw"), exist_ok=True)
    wl = os.path.join(HOME, "watchlist.md")
    if not os.path.exists(wl):
        shutil.copy(os.path.join(SKILL_DIR, "assets", "watchlist.example.md"), wl)
        print(f"已创建关注清单：{wl}")
    for k in ("deal", "wool"):
        p = ledger(k)
        if not os.path.exists(p):
            open(p, "a").close()
    print(f"数据目录：{HOME}")


def cmd_check(a):
    key = norm(a.url)
    for r in load(ledger(a.kind)):
        if norm(r.get("链接", "")) == key:
            print(json.dumps({"dup": True, "record": r}, ensure_ascii=False))
            sys.exit(1)
    print(json.dumps({"dup": False, "key": key}, ensure_ascii=False))


def cmd_add(a):
    os.makedirs(HOME, exist_ok=True)
    rec = {"时间": datetime.now().strftime("%Y-%m-%d %H:%M"), "类型": a.type,
           "标题": a.title, "链接": a.url}
    with open(ledger(a.kind), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("已追加台账")


def cmd_jitter(a):
    s = random.uniform(a.min, a.max)
    print(f"随机延迟 {s:.0f}s")
    time.sleep(s)


def cmd_raw(a):
    d = os.path.join(HOME, "raw", datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(d, exist_ok=True)
    print(os.path.join(d, f"{datetime.now().strftime('%H%M%S')}-{a.site}-{a.tag}.{a.ext}"))


def cmd_skip(a):
    os.makedirs(HOME, exist_ok=True)
    with open(os.path.join(HOME, "skipped.log"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M}\t{a.reason}\n")
    print("已记录跳过")


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("init").set_defaults(f=cmd_init)
    c = sp.add_parser("check"); c.add_argument("url"); c.add_argument("--kind", choices=["deal", "wool"], default="deal"); c.set_defaults(f=cmd_check)
    c = sp.add_parser("add"); c.add_argument("--kind", choices=["deal", "wool"], default="deal")
    c.add_argument("--type", required=True); c.add_argument("--title", required=True); c.add_argument("--url", required=True); c.set_defaults(f=cmd_add)
    c = sp.add_parser("jitter"); c.add_argument("--min", type=float, default=60); c.add_argument("--max", type=float, default=540); c.set_defaults(f=cmd_jitter)
    c = sp.add_parser("raw-path"); c.add_argument("site"); c.add_argument("tag"); c.add_argument("--ext", default="json"); c.set_defaults(f=cmd_raw)
    c = sp.add_parser("skip"); c.add_argument("reason"); c.set_defaults(f=cmd_skip)
    a = p.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
