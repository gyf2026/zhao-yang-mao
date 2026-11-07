#!/usr/bin/env python3
"""直连抓爱Q生活网「活动分享」线报（银行立减金 / 话费 / 红包 / 会员），无需浏览器。

为什么值得接：内容全是"领取类"羊毛，跟 smzdm 的商品降价、V2EX 的会员福利互补。
更新比 V2EX 勤得多（当天就有十几条），而且页面结构比大多数线报站干净。

实测（2026-11-07）：
  https://www.iqnew.com/activity/   直连 200，列表结构 <li><a href="/activity/<id>.html"
                                    title="标题"><span class="time">2026-11-07</span>标题</a></li>
  分页：/activity/index_2.html ... index_12.html

两个坑：
1. **这站是 GBK 编码**。当 UTF-8 读全是乱码，必须先按 GBK 解，失败再退 UTF-8。
2. 首页（/）的日期只有"11-07"没有年份，且混着导航链接；**用 /activity/ 列表页**，
   日期是完整的 2026-11-07，结构也规整。

内容注意：线报站帖子质量参差，标题里的"亲测"是作者自述，不等于真到账；
部分链接带返利参数，报给用户时要说明。

用法：
  iqnew_feed.py                       # 活动分享第 1 页
  iqnew_feed.py --page 2              # 翻页
  iqnew_feed.py --pages 3             # 连抓 3 页
  iqnew_feed.py --save raw/xxx.json
"""
import argparse, html, json, re, sys, time, urllib.error, urllib.request
from datetime import datetime
from _compat import fix_stdio

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 国内站强制直连
BASE = "https://www.iqnew.com"

# 领取类关键词，仅作标记，不做过滤（筛不筛交给 pick.py）
WOOL_HINTS = ("领取", "亲测", "红包", "立减", "券", "免费", "抽奖", "免费领", "话费",
              "会员", "额度", "试用", "秒到", "返现", "积分")


class Blocked(Exception):
    """被拦截 / 页面结构变了。调用方必须停手，不能当成本轮没有羊毛。"""


def fetch(path: str, retries: int = 3) -> str:
    """带重试。实测（2026-11-07）这站有频控：连续请求会直接 reset 连接，
    裸抛 URLError 会让整轮崩掉，所以统一收成 Blocked 并退避重试。"""
    url = path if path.startswith("http") else BASE + path
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": BASE + "/",
    })
    last = None
    for i in range(max(1, retries)):
        try:
            with OPENER.open(req, timeout=20) as r:
                raw = r.read()
            break
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
            last = e
            if i < retries - 1:
                time.sleep(2 + i * 3)      # 2s, 5s 退避
    else:
        raise Blocked(f"连不上（{type(last).__name__}: {last}），重试 {retries} 次仍失败")
    # GBK 优先，这是本站的编码；退 UTF-8 兜底
    for enc in ("gbk", "gb18030", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("gbk", "ignore")


def page_path(page: int, channel="activity") -> str:
    if page <= 1:
        return f"/{channel}/"
    return f"/{channel}/index_{page}.html"


def parse(h: str):
    """列表结构：<li><a href="/activity/216597.html" title="标题">
    <span class="time">2026-11-07</span> 标题 </a></li>"""
    items = []
    for blk in re.findall(r'<li>\s*<a href="(/[^"]+?\.html)"(.*?)</a>\s*</li>', h, re.S):
        href, rest = blk
        m_title = re.search(r'title="([^"]*)"', rest)
        title = html.unescape(m_title.group(1)).strip() if m_title else ""
        if not title:
            title = html.unescape(re.sub(r"<[^>]+>", "", rest)).strip()
            title = re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", title)   # 去掉正文里的日期前缀
        m_time = re.search(r'<span class="time">\s*(\d{4}-\d{2}-\d{2})\s*</span>', rest)
        date = m_time.group(1) if m_time else None
        if not href.startswith(("/activity/", "/mall/", "/news/", "/old/")):
            continue          # 导航、QQ 群这类不是线报
        if not date:
            continue
        age = None
        try:
            age = round((datetime.now() - datetime.strptime(date, "%Y-%m-%d")).total_seconds() / 3600, 1)
            if age < 0:
                age = 0.0
        except ValueError:
            pass
        items.append({
            "id": re.search(r"(\d+)\.html", href).group(1) if re.search(r"(\d+)\.html", href) else href,
            "title": title,
            "url": BASE + href,
            "date": date,
            "age_hours": age,
            "hints": [w for w in WOOL_HINTS if w in title],
            "channel": "iqnew",
        })
    return items


def main():
    fix_stdio()
    ap = argparse.ArgumentParser(description="抓爱Q生活网活动线报（直连）")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--pages", type=int, default=1, help="连续抓几页，默认 1")
    ap.add_argument("--channel", default="activity", choices=["activity", "news", "mall"],
                    help="默认 activity（活动分享，羊毛最多）")
    ap.add_argument("--save")
    a = ap.parse_args()

    try:
        all_items, seen = [], set()
        for p in range(a.page, a.page + max(1, a.pages)):
            h = fetch(page_path(p, a.channel))
            # 页面异常小 = 被拦或改版，明确失败
            if len(h) < 3000:
                raise Blocked(f"页面只有 {len(h)} 字符，疑似被拦或改版")
            got = parse(h)
            if not got and p == a.page:
                raise Blocked("一条都没解析出来，页面结构可能变了（检查 list-item 结构）")
            for it in got:
                if it["url"] in seen:
                    continue
                seen.add(it["url"])
                all_items.append(it)
        all_items.sort(key=lambda x: x["age_hours"] if x["age_hours"] is not None else 9e9)
        if a.save:
            open(a.save, "w", encoding="utf-8").write(json.dumps(all_items, ensure_ascii=False, indent=1))
        print(json.dumps(all_items, ensure_ascii=False, indent=1))
        newest = min((i["age_hours"] for i in all_items if i["age_hours"] is not None), default=None)
        print(f"# {len(all_items)} 条（iqnew/{a.channel}）最新 {newest}h 前" if newest is not None
              else f"# {len(all_items)} 条（iqnew/{a.channel}）", file=sys.stderr)
    except Blocked as e:
        print(json.dumps({"blocked": True, "error": str(e),
                          "hint": "改走浏览器打开同页；或隔久一点再试"}, ensure_ascii=False),
              file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
