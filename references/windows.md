# Windows 适配：会出什么问题、怎么解决

> 本技能主体脚本是 zsh + Python。**Python 部分跨平台直接能用**，shell 脚本部分必须换成等价的 PowerShell。
> 这一节把 Windows 上必然遇到的差异逐条列清楚，照着改就行。

---

## 一、目录与路径

| macOS / Linux | Windows |
|---|---|
| `~/.workbuddy/skills/deal-hunter` | `%USERPROFILE%\.workbuddy\skills\deal-hunter` |
| `~/.workbuddy/deal-hunter`（数据目录） | `%USERPROFILE%\.workbuddy\deal-hunter` |

**坑**：
- PowerShell 里 `~` 能用，但 `.bat` 里不能，且 `cd ~` 不会展开。统一用 `$env:USERPROFILE`。
- **路径带中文或空格时必须加引号**。本机 `%USERPROFILE%` 若是中文名（如 `C:\Users\张三`），会连带影响所有路径。
- 不要在 `.bat` / `.cmd` 里写中文路径 —— 控制台代码页不是 UTF-8，会变成乱码导致文件找不到。要写中文，用 `.ps1` 并存成 **UTF-8 with BOM**。

环境变量（PowerShell，只在当前会话生效）：

```powershell
$env:DEAL_HUNTER_HOME = "$env:USERPROFILE\.workbuddy\deal-hunter"
```

---

## 二、Python 相关（这部分可直接用）

- Windows 上命令是 **`python`**，不是 `python3`。脚本内部没有硬编码解释器名，直接 `python scripts\smzdm_feed.py` 即可。
- 脚本里的文件读写全部显式 `encoding="utf-8"`，中文不会乱码。
- 控制台输出中文乱码时先执行 `chcp 65001`，或改用 Windows Terminal。
- `scripts/smzdm_feed.py` 用 `urllib` 并显式清空代理（`ProxyHandler({})`），Windows 系统代理也不会污染国内站抓取。
- 定时任务里的随机延迟：`python scripts\ledger.py jitter`（60–540 秒），跨平台一致。

---

## 三、Chrome 的启动（最容易翻车的一块）

### 1. Chrome 路径

```powershell
# 常见位置，二选一
"C:\Program Files\Google\Chrome\Application\chrome.exe"
"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
```

先确认存在，再写脚本，别硬编码死：

```powershell
$chrome = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
```

### 2. 必须用独立 user-data-dir

**Windows 上 Chrome 是单实例的**：如果用户已经开着日常 Chrome，你再启动一个带 `--remote-debugging-port` 的实例，参数会被**静默忽略** —— 表现为"命令执行成功，但 9222 连不上"。

必须给一个**全新的、独立的**目录：

```powershell
$profile = "$env:USERPROFILE\.workbuddy\browser-profiles\deal-hunter"
New-Item -ItemType Directory -Force -Path $profile | Out-Null
```

### 3. 启动命令

```powershell
Start-Process -FilePath $chrome -ArgumentList @(
  "--remote-debugging-port=9315",
  "--user-data-dir=$profile",
  "--no-first-run",
  "--no-default-browser-check",
  "--proxy-server=http://127.0.0.1:7890",          # 仅境外站需要，国内站不要加
  "--proxy-bypass-list=*.smzdm.com;*.manmanbuy.com;*.zuanke8.com;*.0818tuan.com;*.v2ex.com;<local>",
  "https://www.smzdm.com/"
)
```

要点：

- `Start-Process` 启动的进程**不挂在你这个 shell 下**，天然满足"活过单次调用"，不需要 double-fork。
- `--proxy-bypass-list` 用**分号**分隔，不是逗号。`<local>` 表示本地地址直连。
- Chrome 111+ 若用 WebSocket 连 CDP 报 403，加 `--remote-allow-origins=*`。
- 参数里**不要**加 `--headless` —— 要用户登录就必须看得见窗口。

### 4. 探活

```powershell
try {
  $r = Invoke-RestMethod -Uri "http://127.0.0.1:9315/json/version" -TimeoutSec 5
  if ($r.Browser) { "✓ CDP 就绪: $($r.Browser)" }
} catch { "✗ 未就绪，查端口或看 Chrome 是否真的起来了" }
```

**坑**：Windows 系统代理会拦截 `127.0.0.1` 的请求，导致拿不到 JSON。给 `Invoke-RestMethod` 加 `-NoProxy`，或先 `$env:NO_PROXY="127.0.0.1,localhost"`。

### 5. 关闭：只能按端口杀

```powershell
# 查占用端口的 PID
$pids = (Get-NetTCPConnection -LocalPort 9315 -State Listen -ErrorAction SilentlyContinue).OwningProcess
$pids | ForEach-Object { Stop-Process -Id $_ -Force }
```

**绝对不要** `taskkill /IM chrome.exe /F` —— 会把用户正在用的 Chrome 连同所有标签页一起强杀。

**坑**：`Get-NetTCPConnection` 在部分精简版系统上不可用，退化用：

```powershell
netstat -ano | Select-String ":9315\s.*LISTENING"
```

---

## 四、代理（Windows 上差异最大）

| 项 | 说明 |
|---|---|
| 端口 | Clash 常见 7890，v2rayN 常见 10808/10809，**每家不同，必须自己确认**，不要照抄 |
| 系统代理 | Chrome 默认跟随系统代理；但命令行启动的 Chrome 不一定继承，**显式给 `--proxy-server` 最稳** |
| 环境变量 | `$env:HTTP_PROXY` 可能不存在，也可能是 `http://127.0.0.1:7890` |
| 国内站 | 必须直连。要么不加 `--proxy-server`，要么把国内域名写进 bypass |

确认代理通不通：

```powershell
curl.exe -x http://127.0.0.1:7890 -o NUL -w "%{http_code}" https://x.com/
```

（PowerShell 里 `curl` 是 `Invoke-WebRequest` 的别名，要写 `curl.exe`。）

---

## 五、Node（跑 cdp.js 需要）

- WorkBuddy 自带 Node 在 `%USERPROFILE%\.workbuddy\binaries\node\versions\<ver>\node.exe`。
- 若 `node -v` 报错，直接用绝对路径调用；或 `winget install OpenJS.NodeJS.LTS`。
- `cdp.js` 依赖 Node 内置 `WebSocket`（Node ≥ 22）。**Node 18/20 没有全局 WebSocket，会静默失败**（报 `WebSocket is not defined` 或被 catch 掉）。
- `NODE_PATH` 在 Windows 用分号分隔，若脚本需要：`$env:NODE_PATH = "$env:USERPROFILE\.workbuddy\binaries\node\workspace\node_modules"`。

---

## 六、编码与换行

| 问题 | 解决 |
|---|---|
| 控制台中文乱码 | `chcp 65001` 或换 Windows Terminal |
| `.ps1` 里中文变乱码 | 存成 **UTF-8 with BOM**（VS Code 右下角切编码） |
| `.bat` 里中文路径失效 | 不要在 .bat 写中文，改用 .ps1 或 Python |
| git 提交后全体文件显示改动 | `git config core.autocrlf true`（Windows 侧） |
| 脚本输出存文件后中文乱 | `Out-File -Encoding utf8` |

---

## 七、权限与安全软件

- **UAC**：无需管理员权限即可启动 Chrome 并开调试端口（端口 > 1024）。
- **防火墙弹窗**：首次监听本地端口可能弹窗，选"允许专用网络"即可；不开公网。
- **杀毒/EDR**：部分企业管控软件会拦截"带远程调试端口的浏览器"，表现为 Chrome 启动即退出。看 `chrome_debug.log` 或临时换 `chrome.exe --remote-debugging-port=0`（随机端口）验证。
- **企业策略**：`--remote-debugging-port` 可能被组策略禁用，这种情况只能改用普通浏览器 + 人工，无解。

---

## 八、定时巡检

- WorkBuddy 的定时任务（automation）跨平台一致，直接用。
- 若改用 **Windows 计划任务**，注意：
  - "只在用户登录时运行"才看得到浏览器窗口（登录类任务必须这样）。
  - 起始目录要显式设置，否则相对路径找不到脚本。
  - 用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<绝对路径>.ps1"`。

---

## 九、Windows 专属避坑清单（速查）

1. `python3` → **`python`**
2. `curl` → **`curl.exe`**（否则走 PowerShell 别名）
3. 分号分隔 bypass，**不是逗号**
4. Chrome 已有实例 → 必须**独立 user-data-dir**，否则调试参数被忽略
5. 杀进程按 **PID/端口**，绝不按镜像名
6. `.ps1` 存 **UTF-8 BOM**，`.bat` 不写中文
7. `127.0.0.1` 的请求要 **`-NoProxy`**
8. Node **≥ 22**，否则 `WebSocket is not defined`
9. 中文用户名路径**全部加引号**
10. 代理端口**自己查**，别照抄本文档的 7890
