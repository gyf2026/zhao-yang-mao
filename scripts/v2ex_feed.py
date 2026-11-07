#!/usr/bin/env python3
"""直连抓 V2EX 节点主题（默认 deals 优惠信息），无需浏览器、不走代理。

为什么单独写一个：V2EX 是**领取类羊毛**的主来源（话费、会员、AI 额度、免费主机），
跟什么值得买的"商品降价"完全不重叠，是互补的 B 段。而且它有官方 JSON 接口，
实测直连 200，比浏览器稳定得多。

实测（2026-11-07）：
  /api/topics/show.json?node_name=deals   10 条，覆盖约 27 天 —— 更新很慢，一天扫一次足够
  /api/replies/show.json?topic_id=<id>    回复里常有人补"已失效/领完了"，比正文更能判时效

频率注意：V2EX API 有速率限制（非官方约 120 次/小时），别拿它做高频轮询。
本工具一次调用只发 1 个请求（detail 模式 2 个），日常扫一轮远低于上限。

用法：
  v2ex_feed.py                          # deals 节点，最新 10 条
  v2ex_feed.py --node deals --save raw/v2ex.json
  v2ex_feed.py --detail 1234567         # 主题正文 + 前 20 条回复 + 失效判定
  v2ex_feed.py --nodes                  # 常用节点清单
"""
import argparse, html, json, re, sys, urllib.error, urllib.request
from datetime import datetime
from _compat import fix_stdio

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 国内站强制直连
API = "https://www.v2ex.com/api"

# 羊毛相关节点。deals 是主力，其余按需。
NODES = {
    "deals": "优惠信息（主力，领取类羊毛）",
    "programmer": "程序员（偶有 AI 额度、云服务优惠）",
    "share": "分享创造（新工具免费额度常发这里）",
    "qna": "问与答（偶有优惠问答）",
}

# 回复里出现这些，基本可以断定已经领不到了。
DEAD_MARKERS = ["已失效", "失效了", "领完", "没了", "已结束", "过期了", "不能用", "已修复",
                "下架", "名额已满", "来晚了", "已经结束", "试了不行", "打不开"]


class Blocked(Exception):
    """被限流/风控拦截。调用方必须停手，不能当成"本轮没有羊毛"。"""


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    try:
        with OPENER.open(req, timeout=20) as r:
            body = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        # 403 = 被限流或 UA 被拒；429 = 明确限流。都属"明确失败"，不许静默返回空。
        raise Blocked(f"HTTP {e.code}（{'限流' if e.code in (403, 429) else '被拒'}）：{url}")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise Blocked(f"返回不是 JSON（可能被拦截页替换）：{url}")


def strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def age_hours(ts: int):
    if not ts:
        return None
    return round((datetime.now().timestamp() - ts) / 3600, 1)


def brief(content: str, n=200) -> str:
    return re.sub(r"\s+", " ", strip_html(content))[:n]


def list_node(node="deals"):
    data = fetch_json(f"{API}/topics/show.json?node_name={node}")
    if not isinstance(data, list):
        raise Blocked(f"节点 {node} 返回结构异常（可能节点名错了或已被限流）")
    items = []
    for t in data:
        member = t.get("member") or {}
        items.append({
            "id": str(t.get("id")),
            "title": t.get("title", ""),
            "url": t.get("url", ""),
            "node": (t.get("node") or {}).get("name", node),
            "author": member.get("username", ""),   # 注意是 username，不是 name
            "replies": t.get("replies", 0),
            "created": datetime.fromtimestamp(t["created"]).strftime("%Y-%m-%d %H:%M") if t.get("created") else None,
            "age_hours": age_hours(t.get("created")),
            "last_touched": datetime.fromtimestamp(t["last_touched"]).strftime("%Y-%m-%d %H:%M") if t.get("last_touched") else None,
            "content": brief(t.get("content", "")),
            "channel": "v2ex",
        })
    return items


def detail(topic_id: str, max_replies=20):
    """主题正文 + 回复。回复里的"已失效"是判时效最可靠的依据。"""
    t = fetch_json(f"{API}/topics/show.json?id={topic_id}")
    if isinstance(t, list):
        if not t:
            raise SystemExit(f"主题 {topic_id} 不存在")
        t = t[0]
    try:
        reps = fetch_json(f"{API}/replies/show.json?topic_id={topic_id}")
    except Blocked:
        reps = []          # 回复拿不到不影响正文结论，但要在结果里标出来
    reps = (reps or [])[:max_replies]
    texts = [strip_html(r.get("content", "")) for r in reps]
    hits = [k for k in DEAD_MARKERS if any(k in x for x in texts)]
    return {
        "id": str(t.get("id")), "title": t.get("title", ""), "url": t.get("url", ""),
        "author": (t.get("member") or {}).get("username", ""),
        "created": datetime.fromtimestamp(t["created"]).strftime("%Y-%m-%d %H:%M") if t.get("created") else None,
        "age_hours": age_hours(t.get("created")),
        "replies_total": t.get("replies", 0),
        "content": strip_html(t.get("content", ""))[:1500],
        "reply_samples": texts[:6],
        "dead_markers": hits,
        "likely_dead": bool(hits),
        "note": "likely_dead 只是旁证（回复里有人报失效），仍须点原链接核验；无标记≠有效，也可能只是没人回",
    }


def main():
    fix_stdio()
    ap = argparse.ArgumentParser(description="抓 V2EX 羊毛节点（直连 API）")
    ap.add_argument("--node", default="deals", help="节点名，默认 deals")
    ap.add_argument("--detail", help="主题 ID，拉正文与回复做失效判定")
    ap.add_argument("--save", help="把结果存成 JSON 文件（同时打印）")
    ap.add_argument("--nodes", action="store_true", help="列出常用节点")
    a = ap.parse_args()

    if a.nodes:
        print(json.dumps(NODES, ensure_ascii=False, indent=1))
        return
    try:
        if a.detail:
            out = detail(a.detail)
            if a.save:
                open(a.save, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return
        items = list_node(a.node)
        if a.save:
            open(a.save, "w", encoding="utf-8").write(json.dumps(items, ensure_ascii=False, indent=1))
        print(json.dumps(items, ensure_ascii=False, indent=1))
        newest = min((i["age_hours"] for i in items if i["age_hours"] is not None), default=None)
        print(f"# {len(items)} 条（v2ex/{a.node}）最新一条 {newest}h 前" if newest is not None
              else f"# {len(items)} 条（v2ex/{a.node}）", file=sys.stderr)
    except Blocked as e:
        # 明确失败，绝不返回空列表冒充"本轮没有羊毛"
        print(json.dumps({"blocked": True, "error": str(e),
                          "hint": "V2EX 有限流，隔几分钟再试；连续被拒就跳过本轮并记 skipped.log"},
                         ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
