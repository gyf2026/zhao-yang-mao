<div align="center">

# 找羊毛

**让你想买的东西，拿到此刻最好的价。**

`通用 Agent 技能` · `WorkBuddy / Claude Code / 任意客户端` · 全程只读 · 同款只推一次

</div>

---

## 它是干什么的

一句话：**你想买什么，它就去把这东西当下的最佳优惠找出来；你想白拿什么，它就去把能领的都翻一遍。**

注意「最佳优惠」这四个字。**这件事的核心不是抓错价**——错价一年遇不上几回，遇上还常被砍单。真正天天有用的是：同一款东西，今天是不是比上个月便宜、是不是全网最低、券叠完还能不能再低一点。**正常商品 + 真优惠，才是绝大多数好价的样子。**

传统比价是「你搜一次，它答一次」，搜完就完了。这个技能不一样：它记住你的关注清单（动态血糖仪、某款奶粉、某档显卡），反复扫、自动去重、只挑真正划算的送上来——**推过的同一个东西不会再推第二遍，除非这次真的更便宜**。

### 主要作用

| 作用 | 具体做什么 | 典型例子 |
|---|---|---|
| **找最佳优惠** | 全网比价、核对历史价格、算清券后到手价，确认"这一单是不是此刻最优" | 你看中的扫地机器人，比上个月低 620，是这个型号近半年最低 |
| **薅羊毛** | 银行立减金、话费充值、红包抽奖、免费领 | 建行每周三 60-20 银联券、2.8 元充 10 元话费 |
| **盯 AI 免费额度** | 各家 API 试用额度、免费模型、学生优惠 | 某家新模型送 5 亿 token、Gemini 学生套餐免费一年 |
| **定点守候** | 按你的关注清单逐品类搜，到价就报 | 你只想盯动态血糖仪，它就只报这个 |

**错价当然也抓**（标价少一位数、原价现价严重脱节那种），但它只是"最佳优惠"里最罕见的一种，不是这技能的卖点。把错价当核心去找，结果就是天天翻垃圾、错过真正该下手的那一单。

覆盖的站点：什么值得买（全部好价 / 精选 / 白菜 / 优惠券 / 海淘 / 站内搜索）、慢慢买、爱Q生活网、V2EX 优惠节点、赚客吧、0818 团、LINUX DO 福利板块、X（Twitter）、Slickdeals、DealMoon、CamelCamelCamel。

### 它不会做的事

**全程只读。** 不下单、不领券、不加购、不发帖、不填任何表单——只把链接和结论给你，动手的是你自己。

**不碰你的账号密码。** 需要登录的站点（X、LINUX DO）由你在浏览器窗口里自己扫码或输验证码，技能只在登录成功后留一份 cookie 用于下次免登，密码从头到尾不经手。

**不刷屏。** 什么值得买一页 20 条，全推等于没推。技能里写死了五道闸——门槛 → 新鲜度（超 12 小时不推）→ 同款合并 → 打分排序 → 限额（一轮最多 3 条、单品类最多 2 条）。顺序和权重都固定，同样的输入必得同样的输出。

**不吹牛。** 抓到的是被验证码拦了、还是真没货，它会分开报。**绝不把"没抓到"说成"今天没有好价"**。

---

## 名字是怎么来的

仓库名只能是 ASCII，所以英文标识用 `zhao-yang-mao`（就是「找羊毛」的拼音），页面标题和文档里一律叫**找羊毛**。

---

## 三种用法

| 模式 | 怎么触发 | 它会做什么 |
|---|---|---|
| **一次性找最佳优惠** | 直接说"帮我找 XX 的好价 / 看看 XX 现在买划不划算" | 多站搜索 + 历史价核对 + 券后到手价，给带链接的结论 |
| **关注清单巡查** | 说"扫一轮" | 读 `watchlist.md`，逐品类搜，命中即报 |
| **定时巡检** | 挂个定时任务 | 走完整流程，只输出推送正文；没货就一个字不发 |

**门槛是硬的**，判的不是"便不便宜"，而是**"这一单对这个商品而言，是不是此刻的最优解"**：

- **关注清单命中且价格到位**：到你的目标价，或不高于历史最低价
- **历史最优**：明确标注"历史低价 / 绝对值 / 新低"且省得够（省 ≥50% 或单件 ≥100 元），或核对过历史价格曲线确认是最低
- **大幅让利**：券后比常卖价省 ≥50%，且不靠凑单、拉人、开会员才成立
- **错价 / bug 价**：标价与商品明显不符——罕见，但遇到必抓

凑单才省几十块的、纸巾零食小额捡漏的、券后 1–10 元的、票数 <20 的新爆料——**一律不推**。

**"最佳"要经得起追问**：报的时候得说清比什么价最优（历史最低？全网最低？比常卖价低多少）、凭什么这么说（页面标注 / 历史价格曲线 / 台账里记的价）。**说不出比较基准的"便宜"，不算好价。**

即使有好几条都过了门槛，也不是全推：**一轮最多 3 条、单品类最多 2 条**，按「关注清单 > 确证最低价 > 错价 > 省额 > 新低标注 > 值率」排序，发布超过 12 小时的不进候选。这部分由 `scripts/pick.py` 执行，同输入必得同输出。

---

## 它扫的不是一个频道

很多人以为看「精选」就够了。实测不是：**精选只是全部好价的人工子集**。同一时刻对比，首页 65%、排行榜 78% 的条目在精选里根本找不到，商城页和海淘页更是 100% 不重合。

所以主力源是 `faxian.smzdm.com`（全部好价，默认最新、可翻页、可按品类筛），精选用来看值 / 不值票数做质量旁证，白菜、优惠券、海淘、商城页按需补。**盯着一个子集，等于漏掉三分之二。**

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

但**不同源更新速度差很多，别用一个频率套所有站**：什么值得买是分钟级、几小时抢光，2 小时合理；LINUX DO 是小时级，一天 2–3 次够；V2EX 优惠信息是**天级**（实测最新一条在 49 小时前），一天扫一次就行，拿 2 小时去轮纯属浪费，还白耗 API 限流额度。

连续 3 轮以上被跳过，说明是系统性问题（登录过期 / 代理挂了 / 浏览器被占），技能会主动提醒你，不会一直装死。


---

## 安装

**不绑定任何客户端。** 这个仓库就是一个「技能」目录：`SKILL.md` 是给 Agent 读的说明书，`scripts/` 是能直接跑的 Python（只用标准库）。装到哪里由你所用客户端的规范决定，下面是常见位置，不是硬规定：

| 客户端 | 建议位置 | 说明 |
|---|---|---|
| WorkBuddy | `~/.workbuddy/skills/deal-hunter` | 用户级技能目录 |
| Claude Code | `~/.claude/skills/deal-hunter` | 个人技能；项目内用 `<项目>/.claude/skills/deal-hunter` |
| Codex / Cursor / 其它 | 该客户端文档里的 skills 目录 | 结构一般也是 `<配置目录>/skills/<技能名>` |
| 没有技能机制 | 任意目录 | 直接跑 `scripts/*.py`、把 `SKILL.md` 当提示词喂给 Agent 也能用，只是不会自动触发 |

**交给 Agent 自己判断**：它知道自己是什么客户端，去看一眼现有技能装在哪，装进同级目录即可。三种常见装法：

```bash
# A. clone 到技能目录（能 git pull 更新，推荐）
git clone https://github.com/gyf2026/zhao-yang-mao.git <技能目录>/deal-hunter

# B. 多客户端共用一份代码，用软链
ln -s /path/to/zhao-yang-mao <技能目录>/deal-hunter

# C. 只当脚本库用，不注册成技能
git clone https://github.com/gyf2026/zhao-yang-mao.git ~/tools/deal-hunter
```

初始化数据目录，顺便看它落在哪：

```bash
python3 scripts/ledger.py init      # Windows 用 python
python3 scripts/_paths.py           # 打印最终路径 + 判定依据
```

**数据目录跟着宿主走，不写死**：

| 情况 | 数据落在 |
|---|---|
| 设了环境变量 `DEAL_HUNTER_HOME` | 该路径 |
| 装在 `<宿主>/skills/deal-hunter` | `<宿主>/deal-hunter`（WorkBuddy → `~/.workbuddy/deal-hunter`，Claude Code → `~/.claude/deal-hunter`） |
| 装在其它位置 | `~/.deal-hunter`，不往代码仓库里写数据 |

想让两个客户端共用同一份关注清单和台账，就都设同一个 `DEAL_HUNTER_HOME`。

---

## 第一步：环境自检（**别跳过**）

```bash
python3 scripts/doctor.py --plan   # 先看缺什么（按阻塞优先级排好）
python3 scripts/doctor.py --fix    # 自动补安全项（建目录、初始化台账）
python3 scripts/doctor.py          # 复检，退出码 0=能跑 / 1=有缺失 / 2=致命
```

**依赖只有两样：Python ≥ 3.8 + 一个 Chromium 内核浏览器。** 没有 node、没有第三方 Python 包、不需要额外装技能——CDP 控制器 `scripts/browser.py` 是自带的，连 WebSocket 都自己实现了。

`--plan` 输出的每一项都带 `kind`，Agent 按它行事：

| kind | 含义 | 该怎么做 |
|---|---|---|
| `auto` | 只动本技能自己的数据目录 | 直接执行，不用问 |
| `install` | 要装软件 | 问一句，同意后执行，**装完必须复检** |
| `manual` | 代理 / 登录 / 换 Python 版本 | 转告用户，给具体步骤 |

完整依赖清单和各平台安装命令见 `references/dependencies.md`。

**为什么必须查**：A 段靠直连脚本，但 B 段（X / LINUX DO / 券）和大部分时效核验**全靠真浏览器 + 登录态**。这一环断了，技能不会报错，只会安静地少推几条——你以为在盯，其实半瞎。

### 你的 Agent 有浏览器能力吗？四个判断

脚本查不出这个，得 Agent 自己回答：

1. 有没有能开浏览器的工具（browser / playwright / CDP）？
2. 开出来是真的窗口、你能看见并自己操作吗？只拿到 HTML 字符串**不算**。
3. 有固定 profile、关掉再开还是登录态吗？每次都是干净临时目录**等于没有**。
4. 能拿到 cookie 并复用吗？拿不到**对 X / LINUX DO 等于零**。

| 客户端（举例） | 浏览器现状 | 建议 |
|---|---|---|
| WorkBuddy | 内置浏览器控制连接失败时会**静默回退到自带 Chromium**：窗口收不到指令却回「✓ Done」，数据错位；而且活不过一次命令调用 | **用外置浏览器 + CDP**，别用内置那套 |
| Hermes / OpenClaw / ChatGPT（含 Computer Use） | 一般有内置浏览器，能点能读 | **仍建议改用外置**：内置 profile 多是临时的，登录态存不住，而登录是 X、LINUX DO 的命门 |
| 其它带浏览器工具的客户端 | 按上面四条自己判 | 有真窗口 + 固定 profile 就能用；只有 HTML 就等于没有 |
| 纯 CLI Agent | 没有 | 只能跑直连部分，**如实告知用户**，别假装扫了 |

### 装哪个浏览器

**只有 Chromium 内核支持 CDP 调试协议**，这不是偏好问题：

| 浏览器 | macOS | Windows | Linux | 评价 |
|---|---|---|---|---|
| **Google Chrome** | ✓ | ✓ | ✓ | **首选**，CDP 最完整 |
| **Microsoft Edge** | ✓ | ✓ 系统自带 | ✓ | Windows 免装，等同 Chrome |
| **QQ 浏览器** | ✓ | ✓ | — | 国产 Chromium，国内站顺手 |
| Brave / Chromium | ✓ | ✓ | ✓ | 备选 |
| Safari | ✓ | — | — | **不能用**，走 WebDriver |
| Firefox | ✓ | ✓ | ✓ | **不推荐**，CDP 不兼容 |

装好后**登录就在这个浏览器里做**，cookie 才存得住；换浏览器等于重新登。

### 自检过了，再问用户要什么

方向（比价 / 品类 / 日用品 / 纯羊毛 / AI 额度）、频率、范围——用选项问，别开放式提问。完整剧本见 `references/onboarding.md`。

**顺序不能反**：先确认能跑，再问需求，最后排班。反过来会出现"计划建好了、每天准点空跑"。

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
# 1. 抓什么值得买「全部好价」（主力源，直连，不用浏览器）
python3 scripts/smzdm_feed.py --channel all --page 1
python3 scripts/smzdm_feed.py --channel all --cat 电脑数码      # 按品类
python3 scripts/smzdm_feed.py --channel jingxuan                # 精选（带值/不值票数）
python3 scripts/smzdm_feed.py --channels                        # 列出频道与品类 ID

# 2. 查某条爆料是不是已过期
python3 scripts/smzdm_feed.py --detail https://www.smzdm.com/p/12345678/

# 3. 领取类羊毛（两个直连源，都不用浏览器）
python3 scripts/v2ex_feed.py                    # V2EX 优惠信息（话费/会员/AI 额度）
python3 scripts/v2ex_feed.py --detail 1254773   # 拉回复判"已失效"
python3 scripts/iqnew_feed.py                   # 爱Q生活网（银行立减金/话费/红包）

# 4. 串成一条链：feed → 转换 → 选品（A/B 段都走这条，别手工拼 JSON）
python3 scripts/assemble.py v2ex.json iqnew.json --watch "血糖仪,话费" \
  | python3 scripts/pick.py --max 3 --max-per-cate 2

# 5. 随机延迟（定时巡检用，反风控）
python3 scripts/ledger.py jitter --min 60 --max 540

# 6. 同款去重（退出码 1 = 同款推过且不更便宜，不推）
python3 scripts/ledger.py check --title "雅培瞬感3代 动态血糖仪" --product "雅培瞬感3代" --price 499
```

被验证码拦时会返回 `{"blocked": true}` 并退出（码 2）——**这是明确的失败，不是"今天没有好价"**。切浏览器取数，仍拿不到就跳过本轮，绝不把空结果当结论。

浏览器部分（搜索页、X、Cloudflare 站点、登录后才能看的内容）走自带的 CDP 控制器，**三平台同一份命令**：

```bash
python3 scripts/browser.py start "https://faxian.smzdm.com/" --session deal-hunter
python3 scripts/browser.py eval  "document.title" --session deal-hunter
python3 scripts/browser.py shot  /tmp/page.png --session deal-hunter   # 截图（最小化也能拍）
python3 scripts/browser.py cookies --session deal-hunter --save <数据目录>/cookies/x.json
python3 scripts/browser.py stop  --session deal-hunter
```

不需要 node、不需要额外技能。`browser.py find` 看本机有哪些浏览器可用。

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
│   ├── onboarding.md            首次使用：自检 → 装浏览器 → 问方向 → 定计划
│   ├── dependencies.md          依赖清单、各平台安装、补全流程、实测矩阵
│   ├── sites.md                 每个站：入口/建议操作/抓什么/坑
│   ├── troubleshooting.md       浏览器踩坑手册 + 排查决策树
│   ├── windows.md               Windows 差异与解法
│   ├── reporting.md             汇报规范（先问后查、三要素、确定性分档）
│   └── automation-prompt.md     定时任务提示词模板
├── scripts/
│   ├── doctor.py                环境自检 + 依赖补全（--plan / --fix）
│   ├── _paths.py                数据目录解析（不绑定宿主，可被 DEAL_HUNTER_HOME 覆盖）
│   ├── browser.py               跨平台 CDP 控制器（零依赖，自己实现 WebSocket）
│   ├── _compat.py               Windows 控制台编码与 stdin 兜底
│   ├── ledger.py                商品级去重 / 扫描台账 / 回查 / 随机延迟
│   ├── assemble.py              feed 输出 → pick 输入（字段转换 + 类型标注 + 自检）
│   ├── pick.py                  选品器：门槛、新鲜度、同款合并、打分排序、限额
│   ├── smzdm_feed.py            smzdm 列表与详情直连解析
│   ├── v2ex_feed.py             V2EX 优惠信息（直连 API + 回复失效判定）
│   ├── iqnew_feed.py            爱Q生活网线报（直连，GBK 编码已处理）
│   └── browser_cdp.ps1          Windows 旧版启动器（兼容保留，优先用 browser.py）
└── assets/
    └── watchlist.example.md     关注清单模板
```

---

## 覆盖站点

**国内**：什么值得买（全部好价 / 精选 / 白菜 / 优惠券 / 海淘 / 商城页 / 站内搜索 / 详情）、慢慢买（历史价印证）、**爱Q生活网（银行立减金 / 话费 / 红包，直连）**、V2EX 优惠信息、赚客吧、0818 团、LINUX DO 福利羊毛、京东/淘宝（仅核价核库存）

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

## 平台与客户端支持

**不限客户端**：只要它支持「技能」机制（`<配置目录>/skills/<技能名>`），就能直接用；装在哪由客户端决定，见上文「安装」。没有技能机制的客户端也能跑脚本，只是不会自动触发。

| 部分 | macOS / Linux | Windows |
|---|---|---|
| Python 脚本 | ✓ 实测 | ✓ 代码按平台分支写，控制台编码已兜底（未实机验证） |
| 浏览器控制 | `scripts/browser.py` ✓ 实测 | 同左，用 `DETACHED_PROCESS` 脱离父进程（未实机验证） |
| 数据目录 | 见上文「安装」，默认跟着宿主走 | 同左，Windows 下是 `%USERPROFILE%\` 下的对应目录 |
| 已知差异 | 代理变量污染 | `python` 而非 `python3`、路径带空格要引号、控制台代码页 |

Windows 细节：`python3`→`python`、`curl`→`curl.exe`、bypass 用分号、Chrome 必须独立 `user-data-dir`、杀进程按 PID、`.ps1` 存 UTF-8 BOM、中文路径加引号。详见 `references/windows.md`。

**哪些真测过**：`references/dependencies.md` 末尾有实测矩阵。macOS 全流程实测；Windows / Linux 的代码路径写了但没实机跑过，遇到问题按实际现象改，别默认是逻辑错。

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
