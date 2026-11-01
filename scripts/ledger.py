#!/usr/bin/env python3
"""deal-hunter 辅助脚本：商品级去重 / 扫描台账 / 随机延迟 / 快照路径 / 初始化。

数据目录默认 ~/.workbuddy/deal-hunter/（环境变量 DEAL_HUNTER_HOME 可覆盖）
  pushed.jsonl        已推送的好价，含商品键与价格
  pushed-wool.jsonl   已推送的羊毛
  scan.jsonl          扫描台账：每次扫到的**全部**候选（含没推的、被剔除的及原因）
  watchlist.md        用户关注清单
  raw/YYYY-MM-DD/     原始抓取快照
  skipped.log         跳过轮次

三条核心规则写在本脚本里：
  1) 同款 / 相似商品只推一次——按商品键判，不按链接判（同款换家店换个链接也算同款）。
  2) 下次价格更低才允许再推——必须低于历史推送最低价，且便宜够 1% 或 5 元，避免 0.1 元抖动。
  3) 扫到的都要记账——即使没推，也要写 scan.jsonl，用户以后问"上次那个多少钱"能查回来。
"""
import argparse, json, os, random, re, shutil, sys, time
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse

HOME = os.path.expanduser(os.environ.get("DEAL_HUNTER_HOME", "~/.workbuddy/deal-hunter"))
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 建商品键时剔除的营销噪音词（保留规格数字，如 20片 / 3代 / 128G）
NOISE = re.compile(
    r"(包邮|顺丰|京东物流|好价|爆料|券后|到手价|实付|历史低价|绝对值|新低|"
    r"需凑单|凑单|需用券|用券|领券|叠加|plus会员|plus|会员价|"
    r"京东|天猫|淘宝|拼多多|唯品会|自营|官方旗舰店|旗舰店|官方店|百亿补贴|"
    r"补贴|秒杀|预售|现货|限时|直降|折|元起|起售|整点|开抢|领券中心)",
    re.I)
# 型号区分词：这些词出现在差异部分时，不能算同款（15 和 15 Pro 是两个东西）
DIFF_TOKEN = re.compile(r"(pro|max|plus|mini|ultra|lite|se|note|air|"
                        r"标准版|青春版|增强版|升级版|尊享版|豪华版|"
                        r"[0-9一二三四五六七八九]代)", re.I)
# 中文数字转阿拉伯：只认"三代 / 两代"这种代数写法。
# 千万别全局替换——"三诺""三星""九阳"里的数字是品牌名的一部分，换了就毁。
CN_NUM = {"一": "1", "二": "2", "两": "2", "三": "3", "四": "4",
          "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
CN_NUM_RE = re.compile(r"([一二两三四五六七八九])(?=\s*代)")
# 品牌中英文写法不同，但显然是同一个东西
BRAND = {
    "apple": "苹果", "samsung": "三星", "xiaomi": "小米", "redmi": "红米",
    "huawei": "华为", "honor": "荣耀", "oppo": "oppo", "vivo": "vivo",
    "sony": "索尼", "philips": "飞利浦", "panasonic": "松下", "dyson": "戴森",
    "siemens": "西门子", "bosch": "博世", "midea": "美的", "haier": "海尔",
    "nike": "耐克", "adidas": "阿迪达斯", "logitech": "罗技", "razer": "雷蛇",
    "microsoft": "微软", "intel": "英特尔", "amd": "amd", "lenovo": "联想",
    "abbott": "雅培", "sinocare": "三诺", "yuwell": "鱼跃", "medtrum": "微泰",
}
BRAND_RE = re.compile(r"\b(" + "|".join(map(re.escape, BRAND)) + r")\b", re.I)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def ledger(kind):
    return os.path.join(HOME, "pushed-wool.jsonl" if kind == "wool" else "pushed.jsonl")


def scan_path():
    return os.path.join(HOME, "scan.jsonl")


def norm(url):
    """URL 归一化：去协议/参数/锚点/尾斜杠；smzdm 取文章 ID。"""
    u = urlparse((url or "").strip())
    host = u.netloc.lower().removeprefix("www.")
    path = u.path.rstrip("/")
    if host.endswith("smzdm.com"):
        m = re.search(r"/(?:p|post|youhui|fx)/(\d+)", path) or re.search(r"/(\d{6,})", path)
        if m:
            return f"smzdm:{m.group(1)}"
    return f"{host}{path}" if host else ""


def product_key(text):
    """商品键：小写 → 中文数字转阿拉伯 → 去营销噪音 → 标点转空格。

    保留空格和规格数字（20片 / 3代 / 128G 都是区分不同 SKU 的信息）。
    """
    s = (text or "").lower()
    s = CN_NUM_RE.sub(lambda m: CN_NUM[m.group(1)], s)
    s = BRAND_RE.sub(lambda m: BRAND.get(m.group(1).lower(), m.group(1)), s)
    s = NOISE.sub(" ", s)
    s = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s):
    """英文单词与数字片段（型号靠这些区分）。"""
    return set(re.findall(r"[a-z]+|\d+", s))


def similar(a, b):
    """两个商品键是否算同款。

    先看型号差异：英文/数字片段不一致且差的是 pro、max、容量、代数 → 判为不同商品。
    再看整体相似度 ≥0.85，最后处理"全称 vs 简称"（一方被另一方完整包含）。
    """
    if not a or not b:
        return False
    ca, cb = a.replace(" ", ""), b.replace(" ", "")
    if ca == cb:
        return True
    diff = _tokens(a) ^ _tokens(b)
    if diff and any(re.fullmatch(r"\d+", t) or DIFF_TOKEN.search(t) for t in diff):
        return False
    if SequenceMatcher(None, ca, cb).ratio() >= 0.85:
        return True
    short, long_ = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
    if len(short) >= 5 and short in long_:
        return not DIFF_TOKEN.search(long_.replace(short, "", 1))
    return False


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


def append(path, rec):
    os.makedirs(HOME, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def rec_key(r):
    return r.get("商品键") or product_key(r.get("商品") or r.get("标题") or "")


def cmd_init(a):
    os.makedirs(os.path.join(HOME, "raw"), exist_ok=True)
    wl = os.path.join(HOME, "watchlist.md")
    if not os.path.exists(wl):
        shutil.copy(os.path.join(SKILL_DIR, "assets", "watchlist.example.md"), wl)
        print(f"已创建关注清单：{wl}")
    for p in (ledger("deal"), ledger("wool"), scan_path()):
        if not os.path.exists(p):
            open(p, "a").close()
    print(f"数据目录：{HOME}")


def cmd_key(a):
    print(product_key(a.text))


def cmd_check(a):
    """判定这条能不能推。退出码 0=可推，1=不推（同款已推过且没更低价）。"""
    pkey = a.product_key or product_key(a.product or a.title or "")
    price = a.price
    hits = [r for r in load(ledger(a.kind)) if similar(pkey, rec_key(r))]
    out = {"商品键": pkey, "本次价格": price, "同款历史条数": len(hits)}
    if not hits:
        out.update(action="push", reason="全新商品，未推送过")
    else:
        prices = [r["价格"] for r in hits if isinstance(r.get("价格"), (int, float))]
        low = min(prices) if prices else None
        out["历史推送最低价"] = low
        out["上次推送时间"] = hits[-1].get("时间")
        # 必须比历史推送最低价再低 1%（且至少 1 元）才算真降，挡掉换券抖动
        gap = max(1.0, round(low * 0.01, 2)) if low else 1.0
        if price is None:
            out.update(action="skip", reason="同款已推过，本次价格未知，不重复推")
        elif low is None:
            out.update(action="skip", reason="同款已推过（历史无价格记录），不重复推")
        elif price <= low - gap:
            out.update(action="push",
                       reason=f"同款已推过，但本次 {price} 明显低于历史推送最低 {low}")
        else:
            out.update(action="skip",
                       reason=f"同款已推过（历史最低 {low}），本次 {price} 不更低")
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0 if out["action"] == "push" else 1)


def cmd_add(a):
    pkey = a.product_key or product_key(a.product or a.title)
    rec = {"时间": now(), "类型": a.type, "标题": a.title, "商品": a.product or a.title,
           "商品键": pkey, "价格": a.price, "站点": a.site, "链接": a.url}
    append(ledger(a.kind), rec)
    print(json.dumps({"已记入推送台账": ledger(a.kind), "商品键": pkey}, ensure_ascii=False))


def cmd_scan(a):
    """记录一条扫到的候选——不管推没推，都要记。"""
    pkey = a.product_key or product_key(a.product or a.title)
    rec = {"时间": now(), "站点": a.site, "关键词": a.keyword, "标题": a.title,
           "商品": a.product or a.title, "商品键": pkey, "价格": a.price,
           "原价": a.orig, "标注": a.label, "状态": a.status,
           "原因": a.reason, "链接": a.url}
    append(scan_path(), rec)
    print(json.dumps({"已记入扫描台账": scan_path(), "状态": a.status}, ensure_ascii=False))


def _hay(r):
    return " ".join(str(r.get(k, "")) for k in ("标题", "商品", "商品键", "关键词", "站点")).lower()


def cmd_query(a):
    """按关键词回查台账：扫过的、推过的都能查到。"""
    kw = a.keyword.lower()
    rows = []
    for r in load(scan_path()):
        if kw in _hay(r):
            rows.append({**r, "来源": "扫描台账"})
    for kind in ("deal", "wool"):
        for r in load(ledger(kind)):
            if kw in _hay(r):
                rows.append({**r, "来源": "推送台账"})
    rows.sort(key=lambda r: r.get("时间", ""))
    priced = [r for r in rows if isinstance(r.get("价格"), (int, float))]
    low = min(priced, key=lambda r: r["价格"]) if priced else None
    out = {"关键词": a.keyword, "命中": len(rows),
           "历史最低价": low["价格"] if low else None,
           "最低价记录": {k: low.get(k) for k in ("时间", "标题", "价格", "链接")} if low else None,
           "记录": rows[-(a.limit):]}
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_history(a):
    """查某个商品的价格变化史（按商品键模糊匹配）。"""
    pkey = a.product_key or product_key(a.product)
    rows = []
    for r in load(scan_path()) + load(ledger("deal")) + load(ledger("wool")):
        if similar(pkey, rec_key(r)):
            rows.append({k: r.get(k) for k in ("时间", "标题", "价格", "状态", "原因", "站点", "链接")})
    rows.sort(key=lambda r: r.get("时间", ""))
    prices = [r["价格"] for r in rows if isinstance(r.get("价格"), (int, float))]
    print(json.dumps({"商品键": pkey, "记录数": len(rows),
                      "最低价": min(prices) if prices else None,
                      "最高价": max(prices) if prices else None,
                      "记录": rows}, ensure_ascii=False, indent=1))


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
    p = argparse.ArgumentParser(description="deal-hunter 台账与去重工具")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("init").set_defaults(f=cmd_init)

    c = sp.add_parser("key", help="算商品键"); c.add_argument("text"); c.set_defaults(f=cmd_key)

    c = sp.add_parser("check", help="判能不能推（同款去重 + 更低价才推）")
    c.add_argument("url", nargs="?")
    c.add_argument("--title"); c.add_argument("--product", help="Agent 归一化后的商品名，优先用它")
    c.add_argument("--price", type=float); c.add_argument("--product-key", dest="product_key")
    c.add_argument("--kind", choices=["deal", "wool"], default="deal"); c.set_defaults(f=cmd_check)

    c = sp.add_parser("add", help="写入推送台账")
    c.add_argument("--kind", choices=["deal", "wool"], default="deal")
    c.add_argument("--type", required=True); c.add_argument("--title", required=True)
    c.add_argument("--url", required=True); c.add_argument("--product"); c.add_argument("--price", type=float)
    c.add_argument("--site"); c.add_argument("--product-key", dest="product_key"); c.set_defaults(f=cmd_add)

    c = sp.add_parser("scan", help="写入扫描台账（推没推都要记）")
    c.add_argument("--title", required=True); c.add_argument("--url"); c.add_argument("--site")
    c.add_argument("--keyword"); c.add_argument("--product"); c.add_argument("--price", type=float)
    c.add_argument("--orig", help="原价/常卖价"); c.add_argument("--label", help="页面低价标注原文")
    c.add_argument("--status", choices=["pushed", "rejected", "dup"], default="rejected")
    c.add_argument("--reason"); c.add_argument("--product-key", dest="product_key"); c.set_defaults(f=cmd_scan)

    c = sp.add_parser("query", help="按关键词回查台账")
    c.add_argument("keyword"); c.add_argument("--limit", type=int, default=20); c.set_defaults(f=cmd_query)

    c = sp.add_parser("history", help="查单个商品的价格史")
    c.add_argument("product"); c.add_argument("--product-key", dest="product_key"); c.set_defaults(f=cmd_history)

    c = sp.add_parser("jitter"); c.add_argument("--min", type=float, default=60); c.add_argument("--max", type=float, default=540); c.set_defaults(f=cmd_jitter)
    c = sp.add_parser("raw-path"); c.add_argument("site"); c.add_argument("tag"); c.add_argument("--ext", default="json"); c.set_defaults(f=cmd_raw)
    c = sp.add_parser("skip"); c.add_argument("reason"); c.set_defaults(f=cmd_skip)

    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
