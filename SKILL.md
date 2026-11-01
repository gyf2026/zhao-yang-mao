---
name: deal-hunter
description: 在什么值得买、慢慢买、赚客吧、V2EX 优惠区、X(Twitter) 等网站巡查"羊毛"与低价好价：错价/bug 价、历史新低、大额优惠券、免费试用、AI 免费额度，也可按用户关注清单（如动态血糖仪）盯指定品类的好价。优先用浏览器登录态访问网页，只读不下单。适用于一次性找好价、按关键词比价找最低价，以及定时自动巡检推送。触发词：找羊毛、薅羊毛、好价、低价、什么值得买、smzdm、值得买、历史低价、错价、bug价、优惠券、免费领、免费试用、AI免费额度、帮我盯着、关注清单、巡检好价、扫一轮好价。
agent_created: true
---

# deal-hunter：羊毛与好价巡查

## 红线（任何模式都适用）

- **全程只读**：禁止下单、领券、加购、发帖、点赞、关注、私信、提交表单、输入个人信息或凭据。发现好价只报告，由用户自己去领。
- **登录由用户完成**：需要登录态时，让用户在浏览器窗口里自己登录（扫码/验证码），绝不索要或输入账号密码，不切换账号。
- **时效核验是硬门槛**：没核验过的条目不推。宁可少推，不推死链接。
- **不虚构**：抓不到就写抓不到，禁止凭印象补价格、补"历史低价"。

## 动手前先问清方向（第一次用 / 需求模糊时）

**不要一上来就全站扫。** 用户说"帮我找找羊毛"，直接甩 20 条链接等于没帮上忙。

用 `AskUserQuestion` 给选项（别开放式提问），问三件事：

1. **方向**：特定商品/型号比价？某品类（如血糖仪、显卡）？日用快消？纯羊毛（券/试用/AI 额度）？
2. **预算/目标价**：有明确目标价？越低越好只看新低？不设限只看大额优惠？
3. **范围**：只国内？含海淘？含 X / AI 额度？

拿到答案先写进 `watchlist.md`，下一轮不再问。

**可以直接开扫的例外**：关注清单里已有配置、用户给了明确商品名/链接、定时巡检任务。

## 数据目录

`~/.workbuddy/deal-hunter/`（首次运行 `python3 scripts/ledger.py init` 创建，路径相对本 skill 目录）

| 文件 | 用途 |
|---|---|
| `watchlist.md` | 用户关注清单（品类、关键词、目标价、排除词）。**先读它**，没有就从 `assets/watchlist.example.md` 初始化并问用户要盯什么 |
| `pushed.jsonl` / `pushed-wool.jsonl` | 已推送台账（好价 / 羊毛），用于去重 |
| `raw/日期/` | 原始抓取快照，时间戳命名 |
| `skipped.log` | 被跳过的轮次 |

## 三种使用模式

先判断用户要哪种，不明确就按"找好价"处理。

1. **找好价（一次性）**：用户说"帮我找某某的好价/最低价"。→ 对关键词在多个站点搜索，给出带链接的比价结论，直接在对话里回答完整报告。
2. **关注清单巡查**：用户说"扫一轮""看看我关注的有没有好价"。→ 读 `watchlist.md`，逐品类搜索，命中即报。
3. **定时巡检（自动化）**：由定时任务触发。→ 走完整流程，**最终回复 = 推送正文本身**，无内容则回复空字符串。提示词模板见 `references/automation-prompt.md`。

### 定时巡检：开启前必须先提醒用户这几件

定时任务不是"配好就忘"。它依赖电脑开着、网络通着、登录态有效，任何一条断了都会**静默失败**——用户以为还在盯，其实早就停了。所以建任务前，必须把下面三条讲清楚：

1. **电脑不能关机、不能睡眠。**
   - macOS：插电源、开盖、别手动点睡眠；需要长时间守候可挂 `caffeinate -dimsu`。**笔记本合盖默认必睡**，合盖就停。
   - Windows：电源计划里"接通电源时进入睡眠"设为**从不**；"关闭盖子时"设为**不采取任何操作**；网卡电源管理取消"允许关闭此设备以节约电源"。
2. **代理软件要保持运行**（Clash / v2rayN 等），否则 X、Slickdeals、DealMoon 全部拉不到；建议设开机自启。
3. **登录态会过期。** 首次登录成功后立刻 `dumpcookie` 落盘；识别到登录墙就跳过本轮、不推半成品，并在下次成功运行时提醒用户重新登录。

**排班建议**：每 2 小时一轮、只跑 08:00–23:00。好价通常几小时就被抢完，过密只是徒增风控风险；夜间没有新爆料。大促日可临时调到 1 小时。

用 `AskUserQuestion` 先问频率/时间窗/范围，确认后再用 `automation_update` 创建，**不要擅自开**。详见 `references/automation-prompt.md`。


## 通道选择（先走便宜的，再升级）

| 目标 | 通道 | 说明 |
|---|---|---|
| smzdm 首页/好价频道/详情页 | `scripts/smzdm_feed.py`（直连，不走代理） | 20 条/页，含标题、现价、商城、值/不值票数 |
| smzdm 站内搜索 `search.smzdm.com` | **必须浏览器** | 直连只返回 202 + JS 挑战页（实测） |
| 带 Cloudflare/403 的站点、X、登录后内容 | **`browser-cdp-control` 技能** | 详见下节，**不要用内置浏览器控制** |
| 站点逐一可达性与坑 | 见 `references/sites.md` | 含实测结论与 http/https 差异 |

### 浏览器一律走 `browser-cdp-control` 技能（2026-11-01 实测）

内置浏览器控制（agent-browser / browser-use）在连接失败时**静默回退到自带的 Chromium**：屏幕上那个 Chrome 收不到指令，却回「✓ Done」，读到的是另一个浏览器的页面。而且它起的 Chrome **活不过一次命令调用**，登录态存不住。所以固定用：

```bash
cd ~/.workbuddy/skills/browser-cdp-control/scripts
export NODE_PATH=/Users/fgy/.workbuddy/binaries/node/workspace/node_modules

# 国内站（直连，脚本自带 env -u 摘代理）
./browser_cdp.sh start "<URL>" --session deal-hunter --detach
# 境外站（X/Slickdeals 等，需显式给代理 + 国内域名绕过）
./browser_cdp.sh start "<URL>" --session deal-hunter-x --detach \
  --proxy "http://127.0.0.1:54835" \
  --proxy-bypass "*.smzdm.com;*.manmanbuy.com;*.zuanke8.com;*.0818tuan.com;*.v2ex.com;*.linux.do;localhost"

CDP_PORT=9315 node cdp.js list                  # 取 targetId
CDP_PORT=9315 node cdp.js newtab "<URL>"        # 开新标签（不抢已有页）
CDP_PORT=9315 node cdp.js eval <id> "表达式"     # 抓结构化数据
CDP_PORT=9315 node cdp.js front <id>            # 需要用户登录时切前台
```

- 端口由 `--session` 名字 hash 到 93xx，国内/境外各用一个 session，互不干扰。
- **代理端口会变**：每次以 `env | grep -i proxy` 的实际值为准，别用记下来的旧端口（写错会得到 `ERR_PROXY_CONNECTION_FAILED`）。
- 登录成功后立刻 `node cdp.js dumpcookie <id> /tmp/xxx.json`，session cookie 关窗就没了。
- `--proxy` / `--proxy-bypass` 是本技能新增的可选参数，不传则行为与原来完全一致。
- **Windows 用 `scripts/browser_cdp.ps1`**（参数同名）；Chrome 已有实例会吞掉调试参数，必须用独立 `user-data-dir`，详见 `references/windows.md`。
- 浏览器出任何问题（白屏 / 窗口消失 / 验证码 / 代理连不上 / Cloudflare / 登录墙），先查 `references/troubleshooting.md` 的决策树。

**国内站先排除代理污染**：本机常有 `HTTP_PROXY` 变量，会让国内站流量走海外节点而被风控。命令行抓国内站一律加 `--noproxy '*'`（脚本已内置）。详见 `cn-platform-collection` 技能第零条铁律。

## 标准流程

1. **准备**：`ledger.py init`；读 `watchlist.md`。定时模式先 `ledger.py jitter`（60–540 秒随机延迟，反风控）。
2. **A 段：好价扫描**
   - smzdm 首页 + `/jingxuan/` 翻 1–2 页：`python3 scripts/smzdm_feed.py [URL] --save $(python3 scripts/ledger.py raw-path smzdm jingxuan)`。
   - 关注清单：对每个品类的主词必搜，辅词每轮轮换 2–3 个，用浏览器开 `https://search.smzdm.com/?c=home&s=<关键词>&order=time`，每词最多 1 页，页面快照存 `raw/`。
   - 交叉比价（可选）：对候选商品到慢慢买查历史价，印证"历史低价"。
3. **B 段：羊毛与 AI 额度**（用户要求或定时模式开启时）：浏览已登录的 X 首页/关注流 1–2 屏，加 V2EX 优惠区、赚客吧等，见 `references/sites.md`。只收"领取类"与"AI 免费额度"，纯资讯讨论一律不收。
4. **按门槛筛选**（见下）。
5. **去重**：`ledger.py check <链接> --kind deal|wool`，退出码 1 即已推送过，丢弃。
6. **时效核验（逐条）**：先 `smzdm_feed.py --detail <帖子链接>`，`expired=true` 直接丢；再用浏览器打开商城原链接看库存与实际价。X 帖需看评论区高赞是否说"失效/已修复/结束"。
7. **推送并记账**：输出后 `ledger.py add --kind … --type … --title … --url …`。
8. **关标签页**：本轮打开的标签页保持到全轮结束，最后一次性关闭，不碰用户原有标签页。

## 推送门槛

**A 节（好价）满足任一条才收：**
- a) 错价/bug 价：标价与商品明显不符（如少一位数）、原价现价严重脱节，或大量值友标记异常。
- b) 页面明确标注"历史低价/绝对值/新低"，且省额比例 ≥50% 或单件/单套省额 ≥100 元。
- c) 值率 ≥80% 且票数 ≥20，且页面标注历史低价。
- d) **关注清单命中**：价格低于清单里的"目标价"；未设目标价时按 b) 的 100 元线。

**不收：** 凑 3 件以上或复杂叠券才省几十元；纸巾零食日用小额捡漏；券后 1–10 元极限价；仅"低于常卖价"而无新低标注；票数 <20 的新爆料。A 节最多 3 条。

**时效硬规则：** 页面出现过期/售罄/缺货/活动结束，或名额已满，一律不推。注意 smzdm 详情页里的"无货或下架"是隐藏的报错模板，每个帖子都有，**不能当过期依据**；真正的过期标记是 `card-bottom-overdue` / "来晚了~优惠已错过"（脚本已处理）。

**B 节（羊毛）：** 领取类（免费领、限量领、折扣码、免费试用、抽奖、会员权益）与 AI 免费额度（credits、API 免费额度、试用名额）。最多 3 条，新的才收。

## 输出格式

**条目字段**
- A 节：商品、现价与省额/降幅、判定依据（a/b/c/d）、是否需凑单或领券、历史低价标注原文、链接。
- B 节及 A 节内的券/试用类：是什么、怎么领、额度/价值、截止时间（未标注写"未标注"）、限制条件、来源链接。

**定时模式的合并投递**
- 两节都有：首行`【好价】`，空一行列条目；一行分隔线`／`；再首行`【羊毛】`，空一行列条目。标记只在首行出现一次。
- 只有一节：只发该节，不加分隔线。
- 都没有：最终回复为空字符串，一个字都不输出。
- `羊毛`字样只用于 B 节标记，A 节全文不得出现。

**对话模式**：结论先行，表格列候选、依据和链接，并交代剔除了什么、为什么。完整口径见 `references/reporting.md`。

**汇报三条硬要求**（详情见 `references/reporting.md`）：
1. 每条结论必须带 **来源站点 + 抓取时间 + 价格口径**（含不含券、要不要凑单、是不是会员价）。
2. 报**实付价**，省额按常卖价算，不用虚的划线价；凑单/领券条件写进括号。
3. 区分三档确定性：**已核验**（打开过原页）/ **仅列表页**（标"未核库存"）/ **传闻**（标"未核验"）。禁止把未核验说成已确认，禁止用"据说/可能/大概率"支撑结论。


## 落盘与超时

- 每个扫描页面都要在 `raw/` 留快照或结构化提取文件；定时模式下无落盘视为未完成，不推送。
- 整轮控制在 45 分钟内，超时或中途出错按未完成处理，`ledger.py skip "<原因>"` 后静默结束，**绝不产生半成品推送**。
- 浏览器被占用时：等 2–3 分钟复查，累计 15 分钟仍占用则跳过本轮，不抢占。

## 平台差异（macOS / Linux / Windows）

脚本分两类，跨平台能力不同：

| 部分 | macOS / Linux | Windows |
|---|---|---|
| `ledger.py`、`smzdm_feed.py` | ✓ | ✓ 直接用（命令是 `python` 不是 `python3`） |
| `smzdm_feed.py`（抓取） | ✓ | ✓ urllib 已显式清代理，系统代理不影响 |
| 浏览器启动 | `browser_cdp.sh`（zsh，需 `--detach` 防回收） | `browser_cdp.ps1`（PowerShell，`Start-Process` 天然脱离） |
| 必踩差异 | 代理变量污染、进程组回收 | Chrome 单实例吞参数、`curl` 是别名、`.bat` 中文乱码 |

**Windows 上十条必看**（完整版 `references/windows.md`）：`python3`→`python`、`curl`→`curl.exe`、bypass 用分号、Chrome 必须独立 `user-data-dir`、杀进程按 PID 不按镜像名、`.ps1` 存 UTF-8 BOM、本地请求加 `-NoProxy`、Node 需 ≥22、中文路径全部加引号、代理端口自己查别照抄。

## 参考文件

- `references/sites.md`：**每个站点的入口、建议操作、抓什么、坑在哪**。动手前先看对应站点那一节。
- `references/troubleshooting.md`：**浏览器控制的踩坑手册**（白屏、窗口消失、验证码、代理连不上、Cloudflare、登录墙、关不掉）。出问题先查它。
- `references/windows.md`：Windows 上的路径、Chrome 启动、端口、编码、权限差异与解法。
- `references/reporting.md`：**汇报规范**（先问后查、三要素溯源、确定性分档、报告结构、自检清单）。
- `references/automation-prompt.md`：定时任务提示词模板与排班建议。
- `scripts/browser_cdp.ps1`：Windows 版浏览器启动/探活/关闭。
- `scripts/ledger.py`、`scripts/smzdm_feed.py`：跨平台 Python 工具。

