#!/usr/bin/env python3
"""把各源 feed 的输出，转成 pick.py 能吃的格式。

为什么需要它：feed 脚本输出的是英文键（title / url / age_hours），
`pick.py` 吃的是中文键（标题 / 链接 / age_hours）。中间原本靠 Agent 手工翻译，
一旦少写一个字段，pick 会把所有条目标成"未达门槛"，输出 `"选中": []`——
**和"本轮真的没有好价"长得一模一样**。这是整条流水线最脆的地方，所以单独做成脚本。

另外两件它负责的事：
  · 给条目打上 `类型`（好价 / 羊毛），pick 用两套不同的门槛
  · 从标题里抽 `额度`（红包、立减金、话费这类没有"原价"，只能用金额衡量）

用法：
  python3 scripts/assemble.py raw/v2ex-deals.json raw/iqnew-activity.json \\
      --watch "血糖仪,瞬感,微泰" > candidates.json
  python3 scripts/pick.py candidates.json --watch "血糖仪,瞬感,微泰"

  python3 scripts/assemble.py - < dump.json          # 从 stdin 读
  python3 scripts/assemble.py --stats < a.json       # 只看识别结果，不输出全部
"""
import argparse, json, os, re, sys
from _compat import fix_stdio, read_stdin

# "6x6元" 这类要相乘，"1-9 元话费" 取上限，其余取最大数字
MUL = re.compile(r"(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+(?:\.\d+)?)\s*元")
RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*[-~—]\s*(\d+(?:\.\d+)?)\s*元")
MONEY = re.compile(r"(\d+(?:\.\d+)?)\s*(?:元|块)")


def extract_amount(title: str) -> float:
    """从标题里估个"能拿多少"。估不准不算错——它只用来排序和过门槛。"""
    m = MUL.search(title)
    if m:
        return round(float(m.group(1)) * float(m.group(2)), 2)
    m = RANGE.search(title)
    if m:
        return float(m.group(2))
    vals = [float(x) for x in MONEY.findall(title)]
    return max(vals) if vals else 0.0


def guess_source(item: dict) -> str:
    """靠字段特征判断来源，不要求用户先标好。"""
    ch = str(item.get("channel") or "")
    if ch == "v2ex":
        return "v2ex"
    if ch == "iqnew":
        return "iqnew"
    if ch in ("faxian", "jingxuan", "baicai"):
        return "smzdm"
    if "savings" in item or "expired" in item:
        return "smzdm_detail"
    if "price" in item and "mall" in item:
        return "smzdm"
    if "replies" in item and "node" in item:
        return "v2ex"
    if "hints" in item:
        return "iqnew"
    return "unknown"


def convert(item: dict, source: str):
    title = str(item.get("title") or item.get("标题") or "").strip()
    if not title:
        return None
    url = item.get("url") or item.get("link") or item.get("链接") or ""
    age = item.get("age_hours")
    out = {"标题": title, "链接": url, "age_hours": age}

    if source in ("v2ex", "iqnew"):
        out["类型"] = "羊毛"
        out["品类"] = "羊毛"
        out["额度"] = extract_amount(title)
        out["标注"] = "V2EX" if source == "v2ex" else "爱Q"
        if item.get("likely_dead"):
            out["已失效"] = True
        if item.get("replies") is not None:
            out["回复数"] = item["replies"]
        # 羊毛没有原价，省额留空，别用 0 冒充
        out.pop("省额", None)
        return out

    if source == "smzdm_detail":
        out["类型"] = "好价"
        out["省额"] = item.get("savings")
        out["标注"] = title[:0] or ""
        if item.get("expired"):
            out["已失效"] = True
        return out

    # smzdm 列表 / 未知来源，按好价处理，能带的字段都带上
    out["类型"] = "好价"
    price = item.get("price") or item.get("价格")
    if isinstance(price, str):
        m = MONEY.search(price)
        price = float(m.group(1)) if m else None
    out["价格"] = price
    out["品类"] = item.get("cate") or item.get("品类") or ""
    out["标注"] = item.get("badge") or ""
    for src, dst in (("zhi", "值"), ("buzhi", "不值"), ("savings", "省额"), ("comments", "评论数")):
        if item.get(src) is not None:
            out[dst] = item[src]
    return out


def main():
    fix_stdio()
    ap = argparse.ArgumentParser(description="feed 输出 → pick 输入")
    ap.add_argument("files", nargs="*", help="JSON 文件，可多个；- 表示 stdin")
    ap.add_argument("--watch", default="", help="关注关键词，逗号分隔（命中即标记）")
    ap.add_argument("--stats", action="store_true", help="只打印识别统计")
    ap.add_argument("--strict", action="store_true",
                    help="关键字段缺失率过高时报错退出（默认开启，用 --no-strict 关闭）")
    ap.add_argument("--no-strict", dest="strict", action="store_false")
    ap.set_defaults(strict=True)
    a = ap.parse_args()

    raw_items, sources = [], {}
    files = a.files or ["-"]
    for f in files:
        try:
            text = read_stdin() if f == "-" else open(f, encoding="utf-8").read()
            data = json.loads(text[text.index("["):text.rindex("]") + 1] if "[" in text else text)
        except (OSError, ValueError) as e:
            print(json.dumps({"error": f"读不了 {f}：{e}"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(2)
        if isinstance(data, dict):
            data = [data]
        for it in data:
            s = guess_source(it)
            sources[s] = sources.get(s, 0) + 1
            raw_items.append((it, s))

    watch = [w.strip() for w in a.watch.split(",") if w.strip()]
    out, dropped = [], 0
    for it, s in raw_items:
        c = convert(it, s)
        if not c:
            dropped += 1
            continue
        if watch and any(w in c["标题"] for w in watch):
            c["关注"] = True
        out.append(c)

    # 自检：全空的标题说明字段没对上，这时候吐空列表等于谎报"没货"
    empty_ratio = (dropped / len(raw_items)) if raw_items else 1.0
    stats = {"总数": len(raw_items), "可用": len(out), "丢弃": dropped,
             "来源": sources, "空标题率": round(empty_ratio, 2)}
    if a.strict and raw_items and empty_ratio > 0.3:
        print(json.dumps({"error": "字段没对上：超过 30% 的条目拿不到标题",
                          "hint": "确认输入是 feed 脚本的输出（--save 存的文件），"
                                  "或先用 --stats 看识别结果",
                          "stats": stats}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)

    if a.stats:
        print(json.dumps(stats, ensure_ascii=False, indent=1))
        return
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"# {len(out)} 条可用（丢弃 {dropped}），来源 {sources}", file=sys.stderr)


if __name__ == "__main__":
    main()
