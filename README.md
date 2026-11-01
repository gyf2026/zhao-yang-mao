# 找羊毛

> 一个给 WorkBuddy / Claude Code 用的技能（Skill）：在什么值得买、慢慢买、赚客吧、V2EX、LINUX DO、X（Twitter）等站点巡查**好价与羊毛**——错价、历史新低、大额券、免费试用、AI 免费额度，也可以只盯你关心的那个品类。

**全程只读**：只报告，不下单、不领券、不加购、不发帖。登录由你自己在浏览器里完成 —— **技能不保存你的账号密码**，只在登录成功后存一份 cookie 用于下次免登。

**同款只推一次**：同一个商品（换店铺、换链接、换标题都算）推过就不再推，除非这次价格真的更低。扫到的全部候选都会记进台账，你以后问"上次那个多少钱"随时能查回来。

---

## 它能干什么

| 模式 | 触发方式 | 行为 |
|---|---|---|
| 找好价（一次性） | "帮我找 XX 的好价" | 多站搜索 + 比价，给带链接的结论 |
| 关注清单巡查 | "扫一轮" | 读 `watchlist.md`，逐品类搜，命中即报 |
| 定时巡检 | 定时任务 | 走完整流程，只输出推送正文；没货就静默 |

**门槛是硬的**，不是"看到便宜就报"：

- 错价 / bug 价
- 页面明确标注"历史低价 / 绝对值 / 新低"，且省额 ≥50% 或单件省 ≥100 元
- 值率 ≥80% 且票数 ≥20，且标注历史低价
- 关注清单命中目标价

凑单才省几十块的、纸巾零食小额捡漏的、券后 1–10 元的、票数 <20 的新爆料——**一律不推**。

---

## 定时巡检前，先满足这三个条件

开着定时任务却什么都没收到？九成是下面三条里断了一条。**任务不会报错，它会静默跳过。**

**1. 电脑不能关机、不能睡眠**

**一旦休眠，这一轮扫描就不会执行**——睡眠时进程冻结、网络断开，浏览器和脚本都起不来，而且**不会醒来补跑**，只是白白错过这一轮。不是"晚点再扫"，是这一轮直接没了。

| 系统 | 必做设置 |
|---|---|
| macOS | 插电源、别合盖（**笔记本合盖默认必睡**）；需要长时间守候可挂 `caffeinate -dimsu` |
| Windows | 电源计划「接通电源时进入睡眠」设为**从不**；「关闭盖子时」设为**不采取任何操作**；网卡电源管理里取消「允许计算机关闭此设备以节约电源」 |

**2. 代理软件要保持运行**（Clash / v2rayN 等），否则 X、Slickdeals、DealMoon 全部拉不到；建议设开机自启。

**3. 登录态会过期，但你的密码不经手**。登录是你在浏览器窗口里自己扫码/输验证码完成的；技能只在登录成功后导出 cookie 存在本机，下次用 cookie 免登。识别到登录墙会跳过本轮、不推半成品，并在下次成功运行时提醒你重新登录。

**排班建议**：每 2 小时一轮、只跑 08:00–23:00。好价通常几小时就被抢完，过密只增加风控风险；夜间没有新爆料。大促日可临时调到 1 小时。

连续 3 轮以上被跳过，说明是系统性问题（登录过期 / 代理挂了 / 浏览器被占），技能会主动提醒你，不会一直装死。


---

## 安装

把整个目录放到你的技能目录：

```bash
# macOS / Linux
git clone https://github.com/gyf2026/zhao-yang-mao.git ~/.workbuddy/skills/deal-hunter

# Windows
git clone https://github.com/gyf2026/zhao-yang-mao.git "%USERPROFILE%\.workbuddy\skills\deal-hunter"
```

首次运行初始化数据目录：

```bash
python3 scripts/ledger.py init      # Windows 用 python
```

会在 `~/.workbuddy/deal-hunter/` 下建 `watchlist.md`、`pushed.jsonl`、`pushed-wool.jsonl`、`scan.jsonl`、`raw/`。

---

## 台账：同款只推一次，历史随时能查

两个台账文件，各管一件事：

| 文件 | 记什么 | 干什么用 |
|---|---|---|
| `pushed.jsonl` / `pushed-wool.jsonl` | 推过的商品 + 商品键 + 价格 | 判"同款推过没有、这次是不是真更便宜" |
| `scan.jsonl` | **扫到的全部候选**，含没推的、剔除原因 | 你以后问"上次那个多少钱""怎么没推"时查回来 |

```bash
# 判能不能推（退出码 1 = 同款推过且不更便宜，不推）
python3 scripts/ledger.py check --title "雅培瞬感3代 动态血糖仪" --product "雅培瞬感3代" --price 499

# 记账：推了的写 add，没推的写 scan（带原因）
python3 scripts/ledger.py add  --type 好价 --title "…" --product "…" --price 499 --url "…" --site smzdm
python3 scripts/ledger.py scan --site smzdm --keyword 动态血糖仪 --title "…" --price 899 \
        --label "365天新低" --status rejected --reason "需凑单2件才优惠" --url "…"

# 你回问的时候查
python3 scripts/ledger.py query "血糖仪"        # 命中记录 + 历史最低价
python3 scripts/ledger.py history "雅培瞬感3代"  # 单品价格变化史
```

判定按**商品**不按链接：同款换家店、换个链接、改个标题，照样算推过。脚本会自动去营销词、把"三代"和"3 代"归一、合并品牌中英文（Apple=苹果），但会用型号词把 `iPhone 15` 和 `15 Pro`、单套和 2 个装分开。更低价再推的门槛是**再低 1% 且至少低 1 元**，挡掉换券造成的假降价。

---

## 快速开始

```bash
# 1. 抓什么值得买好价列表（直连，不用浏览器）
python3 scripts/smzdm_feed.py https://www.smzdm.com/jingxuan/

# 2. 查某条爆料是不是已过期
python3 scripts/smzdm_feed.py --detail https://www.smzdm.com/p/12345678/

# 3. 随机延迟（定时巡检用，反风控）
python3 scripts/ledger.py jitter --min 60 --max 540

# 4. 同款去重（退出码 1 = 同款推过且不更便宜，不推）
python3 scripts/ledger.py check --title "雅培瞬感3代 动态血糖仪" --product "雅培瞬感3代" --price 499
```

浏览器部分（搜索页、X、Cloudflare 站点）需要真 Chrome + CDP 直控：

```bash
# macOS：用 browser-cdp-control 技能
~/.workbuddy/skills/browser-cdp-control/scripts/browser_cdp.sh start "<URL>" --session deal-hunter --detach
CDP_PORT=9315 node ~/.workbuddy/skills/browser-cdp-control/scripts/cdp.js list

# Windows：本仓库自带
.\scripts\browser_cdp.ps1 start "https://www.smzdm.com/" -Session deal-hunter
.\scripts\browser_cdp.ps1 status -Session deal-hunter
```

---

## 为什么不用内置浏览器控制

内置的 browser-use / agent-browser 在**连接失败时不报错，而是静默回退到它自带的 Chromium**。结果：

- 屏幕上那个真实 Chrome 收不到任何指令（白屏、点不动）
- 它回你 `✓ Done`，但你读到的是另一个浏览器里的页面——**数据错位**

另外它起的 Chrome 是子进程，**活不过一次命令调用**，登录态根本存不住。

所以本技能固定用「自己起带调试端口的 Chrome + 直接发 CDP 指令」，中间没有中间层。详见 `references/troubleshooting.md`。

---

## 文件结构

```
deal-hunter/
├── SKILL.md                     主流程、门槛、格式
├── references/
│   ├── sites.md                 每个站：入口/建议操作/抓什么/坑
│   ├── troubleshooting.md       浏览器踩坑手册 + 排查决策树
│   ├── windows.md               Windows 差异与解法
│   ├── reporting.md             汇报规范（先问后查、三要素、确定性分档）
│   └── automation-prompt.md     定时任务提示词模板
├── scripts/
│   ├── ledger.py                商品级去重 / 扫描台账 / 回查 / 随机延迟（跨平台）
│   ├── smzdm_feed.py            smzdm 列表与详情直连解析（跨平台）
│   └── browser_cdp.ps1          Windows 浏览器启动/探活/关闭
└── assets/
    └── watchlist.example.md     关注清单模板
```

---

## 覆盖站点

**国内**：什么值得买（列表/搜索/详情）、慢慢买（历史价印证）、赚客吧、0818 团、V2EX 优惠信息、LINUX DO 福利羊毛、京东/淘宝（仅核价核库存）

**海外**：Slickdeals、DealMoon、CamelCamelCamel（需代理）

**社交**：X（需登录 + 代理，建议用 List 而非首页算法流）

白菜哦（baicaio）直连和浏览器都 403，已放弃。

每个站的具体操作和坑见 `references/sites.md`。

---

## 汇报口径

这是本技能和"随便抓一堆链接"最大的区别：

1. **先问后查**——方向、预算、范围不清楚时，先给选项问，别上来就全站扫。
2. **三要素溯源**——每条结论必带：来源站点 + 抓取时间 + 价格口径（含不含券、要不要凑单）。
3. **报实付价**——省额按常卖价算，不用虚的划线价；凑单/领券条件写进括号。
4. **确定性分三档**——已核验 / 仅列表页（标"未核库存"）/ 传闻（标"未核验"）。不把未核验说成已确认。
5. **主动交代剔除了什么**——比多推两条更能建立信任。

完整规范见 `references/reporting.md`。

---

## 平台支持

| 部分 | macOS / Linux | Windows |
|---|---|---|
| Python 脚本 | ✓ | ✓（命令是 `python`） |
| 浏览器启动 | 依赖 `browser-cdp-control` 技能 | 自带 `browser_cdp.ps1` |
| 已知差异 | 代理变量污染、进程组回收 | Chrome 单实例吞参数、`.bat` 中文乱码、`curl` 是别名 |

Windows 十条必看：`python3`→`python`、`curl`→`curl.exe`、bypass 用分号、Chrome 必须独立 `user-data-dir`、杀进程按 PID、`.ps1` 存 UTF-8 BOM、本地请求加 `-NoProxy`、Node 需 ≥22、中文路径加引号、代理端口自己查。详见 `references/windows.md`。

---

## 红线

- 只读，不下单、不领券、不加购、不发帖、不点赞、不关注、不私信
- **不索要、不保存账号密码**，不代收验证码，不切换账号；只用你自己登录后留下的 cookie 免登
- 核验过时效才推，宁可少推不推死链
- 同款只推一次，除非真降价
- 扫到的都记台账，问得回来；查不到就说没扫到，不虚构价格和历史低价

---

## License

MIT
