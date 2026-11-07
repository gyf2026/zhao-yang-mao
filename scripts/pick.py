#!/usr/bin/env python3
"""deal-hunter 选品器：从一堆候选里挑出"值得推、且只推这几条"。

为什么需要它：什么值得买一页 20 条、翻两页 40 条，扫出来的候选常常有十几条，
但推送上限只有 3 条。**没有排序规则就会出现"先抓到谁推谁"**，这是最差的结果。

这里只做**确定性的取舍**——门槛判定、新鲜度、同款合并、排序、限额。
价格核验、库存核验仍然由 Agent 在浏览器里做，本脚本不联网。

输入（JSON 数组，字段除"标题"外都可缺省）：
  {标题, 价格, 品类, 标注, 值, 不值, 省额, age_hours, 关注, 目标价,
   错价, 需凑件数, 链接, 商品键, 历史最低价}

输出：{选中: [...], 剔除: [{标题, 原因}], 统计: {...}}

用法：
  python3 pick.py cand.json --max 3 --max-age 12 --max-per-cate 2
  python3 pick.py cand.json --watch "动态血糖仪,瞬感,三诺"     # 按关键词自动判"关注命中"
  cat cand.json | python3 pick.py --max 3
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import product_key, similar  # noqa: E402  复用商品键与同款判定
from _compat import fix_stdio, read_stdin  # noqa: E402

LOW_VALUE_CATES = ("食品生鲜", "日用百货", "粮油调味", "个护化妆", "生鲜")
NEWLOW_WORDS = ("历史低价", "绝对值", "历史新低", "新低", "史低")
TARGET_WORDS = ("绝对值", "历史低价", "历史新低")


def f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def is_watched(r, watch):
    if r.get("关注"):
        return True
    title = str(r.get("标题", ""))
    return any(k and k in title for k in watch)


def gate_wool(r, watch):
    """羊毛类门槛。**不能套商品那套省额标准**——羊毛没有"原价"概念，省额恒为 0，
    套商品门槛会 100% 被剔除。这里判的是"能不能真领到、值不值当推"。

    收：
      · 关注清单命中（用户点名要的）
      · 有明确金额（红包/立减金/话费，≥5 元）
      · AI 免费额度 / credits / 试用名额（不限金额）
      · 明确的免费领取（会员、免费主机这类，标题带"免费领/免费送"）
    不收：
      · 纯抽奖（大概率拿不到）、纯资讯、纯提问、已失效
    """
    title = str(r.get("标题", ""))
    if r.get("已失效") or r.get("likely_dead"):
        return False, "", "已失效（回复或页面报失效）"
    if r.get("类型") != "羊毛":
        return None, "", ""
    if is_watched(r, watch):
        return True, "w", "关注清单命中"
    worth = f(r.get("额度"), 0.0) or 0.0
    if worth >= 5:
        return True, "w", f"明确金额约 {worth:g} 元"
    if any(k in title for k in ("免费额度", "credits", "API", "token", "试用名额", "免费模型")):
        return True, "w", "AI 免费额度/试用"
    if any(k in title for k in ("免费领", "免费送", "免费试用", "0 元", "0元", "白嫖")):
        return True, "w", "免费领取"
    if "抽奖" in title:
        return False, "", "纯抽奖，命中率低，不值得推"
    return False, "", "没有明确金额或领取价值"


def gate(r, watch):
    """门槛判定，返回 (是否通过, 依据字母, 说明)。羊毛类走单独一套，见 gate_wool。"""
    w = gate_wool(r, watch)
    if w[0] is not None:
        return w
    price, save = f(r.get("价格")), f(r.get("省额"), 0.0) or 0.0
    label = str(r.get("标注") or "")
    zhi, buzhi = f(r.get("值"), 0.0) or 0.0, f(r.get("不值"), 0.0) or 0.0
    target = f(r.get("目标价"))
    hist = f(r.get("历史最低价"))
    ratio = save / (price + save) if price and (price + save) > 0 else 0.0
    has_newlow = any(w in label for w in NEWLOW_WORDS)

    if r.get("错价"):
        return True, "a", "标价与商品明显不符"
    if has_newlow and (save >= 100 or ratio >= 0.5):
        return True, "b", f"标注「{label}」且省 {save:g} 元"
    if zhi >= 20 and zhi / (zhi + buzhi or 1) >= 0.8 and has_newlow:
        return True, "c", f"值率{zhi / (zhi + buzhi):.0%}、票数{zhi:g}，且标注「{label}」"
    if is_watched(r, watch) and target is not None and price is not None and price <= target:
        return True, "d", f"关注清单命中：{price:g} 元 ≤ 目标价 {target:g} 元"
    if is_watched(r, watch) and save >= 100:
        return True, "d", f"关注清单命中且省 {save:g} 元"
    if is_watched(r, watch) and hist is not None and price is not None and price < hist:
        return True, "d", f"关注清单命中且低于历史推送价 {hist:g} 元"
    return False, "", f"未达门槛（省 {save:g} 元{'，有' if has_newlow else '，无'}新低标注）"


def score(r, basis, watch):
    age0 = f(r.get("age_hours"), 0.0) or 0.0
    if r.get("类型") == "羊毛":
        # 羊毛按"能领多少 + 多新"排，没有省额和票数可用
        s = 100 if is_watched(r, watch) else 0
        s += min(40.0, (f(r.get("额度"), 0.0) or 0.0) * 2)
        s += 15 if "AI" in str(r.get("标注") or "") else 0
        s -= age0 * 0.5
        return round(s, 1)
    price, save = f(r.get("价格")), f(r.get("省额"), 0.0) or 0.0
    label = str(r.get("标注") or "")
    zhi, buzhi = f(r.get("值"), 0.0) or 0.0, f(r.get("不值"), 0.0) or 0.0
    age = f(r.get("age_hours"), 0.0) or 0.0
    ratio = save / (price + save) if price and (price + save) > 0 else 0.0
    s = 0.0
    s += 100 if is_watched(r, watch) else 0
    s += 80 if r.get("错价") else 0
    s += min(30.0, save / 10.0)
    s += min(25.0, ratio * 50)
    if any(w in label for w in TARGET_WORDS):
        s += 15
    elif "新低" in label:
        s += 10
    s += min(12.0, zhi / 10.0)
    if zhi and zhi / (zhi + buzhi or 1) >= 0.8:
        s += 5
    if (f(r.get("需凑件数"), 0) or 0) >= 2:
        s -= 10
    s -= age * 0.5          # 越新越靠前：老帖子大概率已经被抢完
    return round(s, 1)


def main():
    fix_stdio()
    ap = argparse.ArgumentParser(description="从候选里挑出要推的那几条")
    ap.add_argument("file", nargs="?", help="候选 JSON 文件，缺省读 stdin")
    ap.add_argument("--max", type=int, default=3, help="最多推几条，默认 3")
    ap.add_argument("--max-age", type=float, default=12, help="好价发布超过多少小时不推，默认 12")
    ap.add_argument("--max-age-wool", type=float, default=72,
                    help="羊毛类新鲜度上限，默认 72。羊毛不是秒杀，会员/话费活动能挂几天到一个月，"
                         "套 12 小时会把当天以外的全砍掉")
    ap.add_argument("--max-per-cate", type=int, default=2, help="同品类最多几条，0=不限，默认 2")
    ap.add_argument("--watch", default="", help="关注关键词，逗号分隔，命中即视为关注项")
    ap.add_argument("--min-save", type=float, default=50, help="低值易耗品类的省额下限，默认 50")
    a = ap.parse_args()

    raw = open(a.file, encoding="utf-8").read() if a.file else read_stdin()
    cands = json.loads(raw)
    watch = [w.strip() for w in a.watch.split(",") if w.strip()]

    kept, dropped = [], []
    for r in cands:
        title = str(r.get("标题", ""))[:40]
        age = f(r.get("age_hours"))
        limit = a.max_age_wool if r.get("类型") == "羊毛" else a.max_age
        if age is not None and age > limit:
            dropped.append({"标题": title, "原因": f"发布 {age:g} 小时，超过 {limit:g} 小时上限"})
            continue
        if (f(r.get("需凑件数"), 0) or 0) >= 3 and (f(r.get("省额"), 0) or 0) < 100:
            dropped.append({"标题": title, "原因": f"需凑 {r.get('需凑件数')} 件才省几个钱"})
            continue
        cate = str(r.get("品类") or "")
        if cate and any(c in cate for c in LOW_VALUE_CATES) and (f(r.get("省额"), 0) or 0) < a.min_save:
            dropped.append({"标题": title, "原因": f"{cate} 小额捡漏（省 {f(r.get('省额'), 0):g} 元）"})
            continue
        ok, basis, why = gate(r, watch)
        if not ok:
            dropped.append({"标题": title, "原因": why})
            continue
        kept.append({**r, "依据": basis, "判定": why, "评分": score(r, basis, watch)})

    # 同款合并：只留评分最高的那条
    kept.sort(key=lambda r: r["评分"], reverse=True)
    uniq = []
    for r in kept:
        k = r.get("商品键") or product_key(r.get("标题", ""))
        dup = next((u for u in uniq if similar(k, u.get("商品键") or product_key(u.get("标题", "")))), None)
        if dup:
            dropped.append({"标题": str(r.get("标题", ""))[:40],
                            "原因": f"同款重复（与「{str(dup.get('标题'))[:20]}」同款）"})
            continue
        uniq.append({**r, "商品键": k})

    # 限额：总数 + 单品类
    picked, per_cate = [], {}
    for r in uniq:
        if len(picked) >= a.max:
            dropped.append({"标题": str(r.get("标题", ""))[:40], "原因": f"超出每轮 {a.max} 条上限（评分 {r['评分']}）"})
            continue
        cate = str(r.get("品类") or "未分类")
        if a.max_per_cate and per_cate.get(cate, 0) >= a.max_per_cate:
            dropped.append({"标题": str(r.get("标题", ""))[:40], "原因": f"同品类已满 {a.max_per_cate} 条"})
            continue
        per_cate[cate] = per_cate.get(cate, 0) + 1
        picked.append(r)

    out = {
        "选中": [{k: r.get(k) for k in ("标题", "价格", "省额", "标注", "依据", "判定",
                                        "评分", "品类", "age_hours", "链接", "商品键")} for r in picked],
        "剔除": dropped,
        "统计": {"候选": len(cands), "通过门槛": len(uniq), "最终推送": len(picked),
                 "参数": {"max": a.max, "max_age": a.max_age, "max_age_wool": a.max_age_wool,
                          "max_per_cate": a.max_per_cate}},
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
