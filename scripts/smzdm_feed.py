#!/usr/bin/env python3
"""直连抓取什么值得买各好价频道并结构化（无需浏览器，不走代理）。

频道（实测 2026-11-01）：
  all        https://faxian.smzdm.com/            全部好价，默认「最新」排序，量大、翻页稳 —— 主力
  jingxuan   https://www.smzdm.com/jingxuan/      精选好价，人工挑选的子集，只是全部好价的一部分
  baicai     https://faxian.smzdm.com/9kuai9/     白菜 9.9 包邮（按门槛一般不推，除非用户点名要）

用法：
  smzdm_feed.py --channel all --page 1 [--cat 163] [--save PATH]
  smzdm_feed.py https://faxian.smzdm.com/h1s0t0f163c0p2/     直接给地址也行
  smzdm_feed.py --detail https://www.smzdm.com/p/185236762/  详情页时效核验
  smzdm_feed.py --channels                                   列出频道与品类 ID

两个必须知道的坑（都实测踩过）：
1. 被 WAF 拦时返回 ~1.7KB 的腾讯验证码页（TCaptcha），HTTP 200，看起来"成功"。
   必须判 blocked=True 并停手，否则会把空页当成"没有好价"。
2. 详情页被同样拦时 <title> 为空。此时绝不能返回 expired=false 让它过关。

搜索（search.smzdm.com）拿不到：返回 202 + JS 挑战，必须用真实浏览器。
"""
import argparse, html, json, re, sys, urllib.request
from datetime import datetime

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 国内站强制直连

# 实测：过期帖正文含 class="card-bottom-overdue" 与文案"来晚了~优惠已错过"。
# "无货或下架"是页面隐藏报错模板（所有帖都有），不能当过期依据。
EXPIRED_MARKERS = ["card-bottom-overdue", "来晚了~优惠已错过", "优惠已错过"]
WAF_MARKERS = ["TCaptcha", "captcha.qq.com", "WafCaptcha", "slidercaptcha"]

CHANNELS = {
    "all": "https://faxian.smzdm.com/",
    "jingxuan": "https://www.smzdm.com/jingxuan/",
    "baicai": "https://faxian.smzdm.com/9kuai9/",
}
# 品类 ID 来自页面筛选链接 h1s0t0f<ID>c0p<页码>
CATS = {
    "电脑数码": 163, "家用电器": 27, "运动户外": 191, "食品生鲜": 95, "家居家装": 37,
    "服饰鞋包": 57, "手机": 165, "蓝牙耳机": 5409, "母婴用品": 75, "个护化妆": 113,
    "日用百货": 1515, "电视": 1255, "摄影": 169, "图书音像": 7, "办公设备": 177,
    "玩模乐器": 93, "汽车消费": 147, "旅游出行": 5337,
}


class Blocked(Exception):
    """被 WAF / 验证码拦截。调用方必须停手并改走浏览器，不能当成"没数据"。"""


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    with OPENER.open(req, timeout=20) as r:
        h = r.read().decode("utf-8", "ignore")
    hit = [m for m in WAF_MARKERS if m in h]
    # 被拦时整页只有验证码脚本（1-2KB），正常页 200KB+。两个条件任一命中就判拦截。
    if hit or len(h) < 6000:
        raise Blocked(f"被拦截（{','.join(hit) or f'页面仅 {len(h)} 字节'}）：{url}")
    return h


def channel_url(channel="all", page=1, cat=None):
    if channel not in CHANNELS:
        raise SystemExit(f"未知频道 {channel}，可选：{','.join(CHANNELS)}")
    if cat:
        cid = CATS.get(cat, cat) if not str(cat).isdigit() else cat
        return f"https://faxian.smzdm.com/h1s0t0f{cid}c0p{page}/"
    if channel == "all":
        return CHANNELS["all"] if page == 1 else f"https://faxian.smzdm.com/p{page}/"
    return CHANNELS[channel] if page == 1 else f"{CHANNELS[channel]}p{page}/"


def parse_feed(h: str):
    """精选好价结构：<div class="feed-block z-hor-feed">，字段在内嵌 sensors 调用里。"""
    items = []
    for blk in re.split(r'<div class="feed-block z-hor-feed"', h)[1:]:
        blk = blk[:6000]
        g = lambda p: (re.search(p, blk, re.S) or [None, ""])[1]
        aid = g(r"'article_id':(\d+)")
        if not aid:
            continue
        title = html.unescape(g(r"'article_title':'(.*?)'"))
        price = html.unescape(re.sub(r"\s+", " ", g(r'class="z-highlight"[^>]*>(.*?)</a>')).strip())
        desc = html.unescape(re.sub(r"<[^>]+>|\s+", " ", g(r'class="feed-block-descripe">(.*?)<a ')).strip())
        items.append({
            "id": aid, "title": title, "price": price, "desc": desc[:200],
            "mall": g(r"'mall_name':'(.*?)'"), "brand": g(r"'brand':'(.*?)'"),
            "cate": g(r"'cate_level1':'(.*?)'"),
            "zhi": g(r'data-zhi-type="1".*?<span>(\d+)</span>'),
            "buzhi": g(r'data-zhi-type="-1".*?<span>(\d+)</span>'),
            "comments": g(r'icon-comment[^>]*></i>\s*(?:<span[^>]*>)?\s*(\d+)'),
            "channel": g(r"'channel':'(.*?)'"), "badge": "",
            "link": f"https://www.smzdm.com/p/{aid}/",
        })
    return items


def parse_faxian(h: str):
    """全部好价结构：<div class="feed-block-ver ">，标题在 h5.feed-ver-title，价格在 .z-highlight。

    与精选的区别：没有值/不值票数，但有 data-tab（默认「最新」）和 tag-top-left 角标
    （优惠精选 / 小值爆料 / 百亿补贴 等），角标可当作来源强度的旁证。
    """
    items = []
    for blk in re.split(r'<div class="feed-block-ver', h)[1:]:
        blk = blk[:5000]
        g = lambda p: (re.search(p, blk, re.S) or [None, ""])[1]
        aid = re.search(r'smzdm\.com/p/(\d+)/', blk)
        if not aid:
            continue
        txt = lambda s: html.unescape(re.sub(r"<[^>]+>|\s+", " ", s or "")).strip()
        items.append({
            "id": aid.group(1), "title": txt(g(r'feed-ver-title[^>]*>\s*<a[^>]*>(.*?)</a>')),
            "price": txt(g(r'class="z-highlight[^"]*"[^>]*>(.*?)</div>')),
            "desc": txt(g(r'feed-ver-desc[^>]*>(.*?)</div>'))[:200],
            "mall": txt(g(r'class="tag-bottom-right"[^>]*>(.*?)</a>')),
            "brand": "", "cate": txt(g(r'feed-ver-cate[^>]*>(.*?)</a>')),
            "zhi": None, "buzhi": None, "comments": None,
            "badge": txt(g(r'class="tag-top-left[^"]*"[^>]*>(.*?)</span>')),
            "tab": (re.search(r'data-tab="([^"]*)"', blk) or [None, ""])[1],
            "channel": "faxian",
            "link": f"https://www.smzdm.com/p/{aid.group(1)}/",
        })
    return items


def parse_any(h: str):
    """按页面结构自动选解析器，返回 (items, kind)。"""
    if "feed-block-ver" in h:
        return parse_faxian(h), "faxian"
    return parse_feed(h), "jingxuan"


def _meta_time(h: str, key: str):
    """抓 meta 里的时间戳，如 name="weibo:webpage:create_at" content="2026-11-01 23:08:28 +0800"。"""
    m = re.search(rf'name="weibo:webpage:{key}"\s+content="([^"]+)"', h)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def detail(url: str):
    h = fetch(url)  # 被拦会抛 Blocked，不会静默返回空结果
    title = html.unescape((re.search(r"<title>(.*?)</title>", h, re.S) or [None, ""])[1]).strip()
    # 二次保险：即使没命中 WAF 关键词，标题为空也说明拿到的不是正常详情页
    if not title:
        raise Blocked(f"详情页标题为空，内容不可信：{url}")
    hits = [k for k in EXPIRED_MARKERS if k in h]
    worth = re.search(r'id="rating_worthy_num"[^>]*>(\d+)', h)
    unw = re.search(r'id="rating_unworthy_num"[^>]*>(\d+)', h)
    created, updated = _meta_time(h, "create_at"), _meta_time(h, "update_at")
    # 列表页没有发布时间，只能靠详情页 meta；年龄用于"太旧的不推"
    age = round((datetime.now() - created).total_seconds() / 3600, 1) if created else None
    # 详情页标题带"【省850元】"，这是站内自算的省额，最适合当门槛依据
    sav = re.search(r"【省(\d+(?:\.\d+)?)元】", title)
    return {"url": url, "title": title, "expired": bool(hits), "markers": hits,
            "zhi": worth.group(1) if worth else None, "buzhi": unw.group(1) if unw else None,
            "savings": float(sav.group(1)) if sav else None,
            "created": created.strftime("%Y-%m-%d %H:%M") if created else None,
            "updated": updated.strftime("%Y-%m-%d %H:%M") if updated else None,
            "age_hours": age,
            "note": "expired=true 不得推送；savings 为站内自算省额；age_hours 超阈值视为太旧不推；false 仅表示站内未标过期，商城库存仍需浏览器核对"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--channel", default="all", choices=list(CHANNELS))
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--cat", help="品类中文名或 ID，如 电脑数码 / 163")
    ap.add_argument("--save")
    ap.add_argument("--detail")
    ap.add_argument("--channels", action="store_true", help="列出频道与品类 ID")
    a = ap.parse_args()

    if a.channels:
        print(json.dumps({"频道": CHANNELS, "品类": CATS}, ensure_ascii=False, indent=1))
        return
    try:
        if a.detail:
            print(json.dumps(detail(a.detail), ensure_ascii=False, indent=2))
            return
        url = a.url or channel_url(a.channel, a.page, a.cat)
        h = fetch(url)
        items, kind = parse_any(h)
        if a.save:
            open(a.save, "w", encoding="utf-8").write(json.dumps(items, ensure_ascii=False, indent=1))
        print(json.dumps(items, ensure_ascii=False, indent=1))
        print(f"# {len(items)} 条（{kind}）{url}", file=sys.stderr)
    except Blocked as e:
        # 明确失败，绝不返回空列表冒充"本轮没有好价"
        print(json.dumps({"blocked": True, "error": str(e),
                          "hint": "改走浏览器（browser-cdp-control），或降低频率后再试"},
                         ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
