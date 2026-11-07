# 依赖清单与自动补全

**核心原则：能不装就不装。** 这个技能的直连部分（smzdm / V2EX / 爱Q）只要 Python；浏览器部分要一个 Chromium 内核浏览器。**没有第三方 Python 包，没有 node，没有外部技能。**

## 一、依赖全景

| 依赖 | 必需性 | 用在哪 | 缺了会怎样 |
|---|---|---|---|
| Python ≥ 3.8 | **必需** | 全部脚本 | 什么都跑不了 |
| Chromium 内核浏览器 | **浏览器功能必需** | X / LINUX DO / 搜索页 / 详情核验 / 登录 | 只能跑 A 段直连，B 段和核验全废 |
| 代理软件 | 可选 | 境外源（X / Slickdeals / DealMoon / OpenRouter） | 境外源拉不到，国内源不受影响 |
| 登录态 cookie | 可选 | X / LINUX DO / 券 | 那几站的正文看不到，别的照常 |
| Node.js | **不需要** | —— | CDP 控制器是纯 Python 实现的，不用 node |
| websocket-client 等第三方包 | **不需要** | —— | WebSocket 客户端写在 `scripts/browser.py` 里了 |

> 早期版本依赖 `browser-cdp-control` 技能和 node。现在 `scripts/browser.py` 自带跨平台 CDP 控制器，
> 这部分依赖已经去掉。旧技能还装着不影响，但不再是必需的。

## 二、按平台装

### macOS

```bash
# 浏览器（二选一）
brew install --cask google-chrome          # 首选
# 或去腾讯官网下 QQ 浏览器 dmg（国内站体验好，Chromium 内核）
```

没装 Homebrew 就去 google.com/chrome 下 dmg 手动装。**Safari 不行**——它走 WebDriver，不支持 CDP。

### Windows

```powershell
# 首选：直接用系统自带的 Microsoft Edge，什么都不用装
# 想用 Chrome：
winget install --id Google.Chrome -e --accept-source-agreements --accept-package-agreements
```

装完把 Chrome 加到 PATH 不是必须的，`browser.py` 会去 `Program Files` / `Program Files (x86)` / `LOCALAPPDATA` 三个位置找。

Windows 上的额外注意（细节见 `windows.md`）：
- 命令用 `python`，不是 `python3`
- 路径有空格要加引号
- `.ps1` 要存成 UTF-8 BOM

### Linux

```bash
sudo apt update && sudo apt install -y chromium        # Debian / Ubuntu
sudo dnf install -y chromium                           # Fedora
sudo pacman -S chromium                                # Arch
```

无桌面环境的服务器跑不了有头浏览器，只能 `--headless`，而且登录态需要图形界面扫码——这种情况老实告诉用户「这台机器做不了需要登录的源」。

## 三、Agent 怎么自己把依赖补全（标准动作）

不要问用户"你装了什么"，先查，再补，再复检。三步：

### 第 1 步：查

```bash
python3 scripts/doctor.py --plan
```

输出是 JSON，`steps` 里每一项都带 `kind`：

| kind | 含义 | Agent 该怎么做 |
|---|---|---|
| `auto` | 安全、可逆、只动本技能自己的数据目录 | **直接执行** `cmd`，不用问 |
| `install` | 要装软件（浏览器等） | **先问用户一句**，同意后执行 `install` 里的命令 |
| `manual` | 做不了或不该自动做（代理、登录、换 Python 版本） | 转告用户，给出具体步骤 |

### 第 2 步：补

```bash
python3 scripts/doctor.py --fix      # 只执行 auto 类，不装任何软件
```

装软件单独来。按平台取命令：

| 平台 | 命令 |
|---|---|
| macOS（有 brew） | `brew install --cask google-chrome` |
| macOS（无 brew） | 让用户去 google.com/chrome 下 dmg |
| Windows | `winget install --id Google.Chrome -e --accept-source-agreements --accept-package-agreements`；或直接用自带 Edge |
| Debian/Ubuntu | `sudo apt update && sudo apt install -y chromium` |
| Fedora | `sudo dnf install -y chromium` |

**装完必须复检**，不要假设装成功：

```bash
python3 scripts/doctor.py
```

`外置浏览器` 那项从 `[x]` 变成 `[ok]` 才算完。

### 第 3 步：验一遍真能开

自检通过 ≠ 浏览器真能用。跑一次端到端：

```bash
python3 scripts/browser.py start "https://faxian.smzdm.com/" --session selftest
python3 scripts/browser.py eval --session selftest "document.title"
python3 scripts/browser.py stop  --session selftest
```

拿到标题就说明整条链路通了（启动 → CDP → 执行 JS → 关闭）。拿不到就按 `troubleshooting.md` 排查。

## 四、装在哪个客户端：目录约定

**代码不假设宿主是谁。** 唯一需要遵守的约定是目录结构：`<宿主配置目录>/skills/deal-hunter`。

| 客户端 | 技能目录 | 数据目录（自动推出） |
|---|---|---|
| WorkBuddy | `~/.workbuddy/skills/deal-hunter` | `~/.workbuddy/deal-hunter` |
| Claude Code | `~/.claude/skills/deal-hunter`（项目级：`<项目>/.claude/skills/…`） | `~/.claude/deal-hunter` |
| 其它客户端 | 按其文档的 skills 目录 | `<该配置目录>/deal-hunter` |
| 无技能机制 / 装在别处 | 任意位置 | `~/.deal-hunter` |

- 解析逻辑在 `scripts/_paths.py`，查一次就知道落在哪：`python3 scripts/_paths.py`。
- 宿主目录必须在**家目录内**才被认；装在别人的代码仓库里会自动退到 `~/.deal-hunter`，不会往仓库里写数据。
- 想让多个客户端共用一份关注清单和台账：设 `DEAL_HUNTER_HOME` 指向同一路径。
- 旧版本把数据写死在 `~/.workbuddy/deal-hunter`。升级后如果新位置不存在、旧位置有数据，会**自动沿用旧位置**，不会丢台账；确认无误后自己 `mv` 到新位置即可。

## 五、失败时的判断顺序

浏览器起不来，按这个顺序排，别乱试：

1. **有没有浏览器** → `browser.py find`。空的就是没装。
2. **端口有没有监听** → `browser.py status --session xxx`。`alive: false` 说明进程没起或没法起。
3. **profile 是否被占用** → 同一 `--session` 只能有一个实例。换一个 session 名试。
4. **是不是代理污染** → 国内站必须 `--no-proxy-server`（`browser.py` 默认已加）。手动加了 `--proxy` 却打不开国内站，就是这个原因。
5. **安全软件拦截** → 少见，但 Windows 上 360 之类会拦本地端口。临时关掉验证。

## 六、实测矩阵（诚实标注）

| 能力 | macOS 26/27 (Apple Silicon) | Windows | Linux |
|---|---|---|---|
| 直连脚本（smzdm / V2EX / 爱Q / ledger / pick） | ✅ 实测 | ⚠️ 代码按平台分支写的，未实机验证 | ⚠️ 同上 |
| `doctor.py` 七项自检 | ✅ 实测 | ⚠️ 未实机验证 | ⚠️ 未实机验证 |
| `browser.py` 启动 / 探活 / eval / 截图 / cookie / 关闭 | ✅ 实测（Chrome 156 + QQ 浏览器） | ⚠️ 未实机验证（用 `DETACHED_PROCESS` 脱离父进程） | ⚠️ 未实机验证 |
| 登录态保存 | ✅ 实测（profile 落盘可复用） | ⚠️ 未实机验证 | ⚠️ 未实机验证 |
| `_paths.py` 数据目录解析（宿主识别 / 环境变量 / 兜底） | ✅ 实测三种分支 | ⚠️ 未实机验证 | ⚠️ 未实机验证 |
| 宿主适配（WorkBuddy） | ✅ 实测 | ⚠️ 未实机验证 | — |
| 宿主适配（Claude Code 及其它 skills 目录结构） | ⚠️ 结构兼容，未实测 | ⚠️ 未实测 | ⚠️ 未实测 |

**没实机测过的平台，出了问题别急着怀疑代码逻辑**，先看这三处最常见的平台差异：进程脱离方式、路径分隔符与空格、控制台编码。遇到 Windows/Linux 的真问题，按实际现象改，改完把结论补进这张表。
