#!/usr/bin/env python3
"""直连抓取 smzdm 好价列表并结构化（无需浏览器，不走代理）。

用法：
  smzdm_feed.py [URL] [--save PATH]      默认 https://www.smzdm.com/jingxuan/
  smzdm_feed.py --detail <文章URL>       读详情页，输出时效标记（已过期/售罄等）

注意：search.smzdm.com 搜索页有 JS 挑战（返回 202 + probe.js），本脚本抓不到，
搜索必须走真实浏览器。首页/好价频道/详情页可直连。
"""
import argparse, html, json, re, sys, urllib.request
from datetime import datetime

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 国内站强制直连
# 实测：过期帖正文含 class="card-bottom-overdue" 与文案"来晚了~优惠已错过"。
# "无货或下架"是页面隐藏报错模板（所有帖都有），不能当过期依据。
EXPIRED_MARKERS = ["card-bottom-overdue", "来晚了~优惠已错过", "优惠已错过"]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    with OPENER.open(req, timeout=20) as r:
        return r.read().decode("utf-8", "ignore")


def parse_feed(h: str):
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
        zhi = g(r'data-zhi-type="1".*?<span>(\d+)</span>')
        buzhi = g(r'data-zhi-type="-1".*?<span>(\d+)</span>')
        cmt = g(r'icon-comment[^>]*></i>\s*(?:<span[^>]*>)?\s*(\d+)')
        items.append({
            "id": aid, "title": title, "price": price, "desc": desc[:200],
            "mall": g(r"'mall_name':'(.*?)'"), "brand": g(r"'brand':'(.*?)'"),
            "cate": g(r"'cate_level1':'(.*?)'"), "zhi": zhi, "buzhi": buzhi, "comments": cmt, "channel": g(r"'channel':'(.*?)'"),
            "link": f"https://www.smzdm.com/p/{aid}/",
        })
    return items


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
    h = fetch(url)
    hits = [k for k in EXPIRED_MARKERS if k in h]
    title = html.unescape((re.search(r"<title>(.*?)</title>", h, re.S) or [None, ""])[1]).strip()
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
    ap.add_argument("url", nargs="?", default="https://www.smzdm.com/jingxuan/")
    ap.add_argument("--save"); ap.add_argument("--detail")
    a = ap.parse_args()
    if a.detail:
        print(json.dumps(detail(a.detail), ensure_ascii=False, indent=2)); return
    h = fetch(a.url)
    items = parse_feed(h)
    if a.save:
        open(a.save, "w", encoding="utf-8").write(json.dumps(items, ensure_ascii=False, indent=1))
    print(json.dumps(items, ensure_ascii=False, indent=1))
    print(f"# {len(items)} 条", file=sys.stderr)


if __name__ == "__main__":
    main()
