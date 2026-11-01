# 找羊毛

> 一个给 WorkBuddy / Claude Code 用的技能（Skill）：在什么值得买、慢慢买、赚客吧、V2EX、LINUX DO、X（Twitter）等站点巡查**好价与羊毛**——错价、历史新低、大额券、免费试用、AI 免费额度，也可以只盯你关心的那个品类。

**全程只读**：只报告，不下单、不领券、不加购、不发帖。登录由你自己在浏览器里完成。

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

会在 `~/.workbuddy/deal-hunter/` 下建 `watchlist.md`、`pushed.jsonl`、`raw/`。

---

## 快速开始

```bash
# 1. 抓什么值得买好价列表（直连，不用浏览器）
python3 scripts/smzdm_feed.py https://www.smzdm.com/jingxuan/

# 2. 查某条爆料是不是已过期
python3 scripts/smzdm_feed.py --detail https://www.smzdm.com/p/12345678/

# 3. 随机延迟（定时巡检用，反风控）
python3 scripts/ledger.py jitter --min 60 --max 540

# 4. 去重检查（退出码 1 = 推过了）
python3 scripts/ledger.py check "https://www.smzdm.com/p/12345678/" --kind deal
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
│   ├── ledger.py                台账去重 / 随机延迟 / 快照路径（跨平台）
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
- 不索要账号密码，不代收验证码，不切换账号
- 核验过时效才推，宁可少推不推死链
- 抓不到就说抓不到，不虚构价格和历史低价

---

## License

MIT
