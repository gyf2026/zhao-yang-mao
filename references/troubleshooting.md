# 浏览器控制踩坑手册

> 每条都是实际踩过的，按「症状 → 真实原因 → 怎么处置」写。
> 排查顺序：**先看标题对不对，再看端口通不通，最后才怀疑站点。**

---

## 0. 一条铁律：不要用客户端内置的浏览器控制

很多客户端（WorkBuddy、Hermes、browser-use 这类）内置的浏览器控制在**连接失败时不报错，而是静默回退到它自带的 Chromium**。

于是会出现两个症状，而且它们会同时出现：

- 屏幕上那个真实 Chrome 窗口**完全收不到指令** —— 白屏、点不动、滚动没反应
- 它回你 `✓ Done`，但你读到的是**另一个浏览器**里的页面 —— 数据错位

**数据错位比直接报错更坏**：你会拿着 A 浏览器的页面，去下 B 站点的结论。

**判断方法**：看返回的页面标题和 URL 对不对得上。对不上，就是落到自带浏览器里了。

**正确做法**：用自带的 `scripts/browser.py` 起一个带调试端口的 Chrome，直接发 CDP 指令。中间没有中间层，行为完全确定。

```bash
python3 scripts/browser.py start "<URL>" --session deal-hunter
```

---

## 1. 浏览器下一次就没了 / 窗口反复消失

**症状**：刚启动成功，下一条命令再查端口已经不通，但屏幕上可能还留着窗口；登录永远做不完。

**真实原因**：`chrome &` 前台启动的 Chrome 是**子进程**，随调用它的 shell 一起被进程组回收。

**处置**：
- 必须加 `--detach`（脚本内置 double-fork + setsid）。
- Windows 上对应的是用 `Start-Process` 启动，不要在同一个 `cmd` 窗口里前台跑。
- 判断是否真的活着：`curl --noproxy '*' -m 5 http://127.0.0.1:<port>/json/version`，返回 `"Browser"` 才算活。

---

## 2. 国内站被要求验证码 / 提示 IP 风险（300012）

**症状**：明明是本网站，却跳出滑块、验证码、"IP 存在风险"。

**真实原因**：**代理环境污染**。命令行启动的 Chrome 会继承 shell 里的 `HTTP_PROXY` / `HTTPS_PROXY`，于是国内站流量也走了海外机房 IP。小红书、搜狗这类站对机房 IP 一律拦截。

**处置**：
- 启动 Chrome 时把代理变量摘干净（`browser.py` 已默认清空 `HTTP(S)_PROXY` 环境变量，并加 `--no-proxy-server`）。
- 只给**境外站**显式加 `--proxy`。
- 诊断出口 IP **必须用国内回显站**，别用 ipinfo.io（它走代理是正常的，会得出"整机在海外"的错误结论）：
  ```bash
  curl -s --noproxy '*' -m 12 https://myip.ipip.net
  # 期望：当前 IP：114.94.x.x  来自于：中国 上海 上海  电信
  ```

**另一个更隐蔽的原因：UA 写太简（2026-11-07 实测）**

同样是 `https://faxian.smzdm.com/`，同样直连不走代理，只改 UA：

| UA | 结果 |
|---|---|
| `Mozilla/5.0` | HTTP 200，**1697 字节，TCaptcha 验证码页** |
| 完整 Chrome UA（含 `(Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ...`） | HTTP 200，**250KB 正常页** |

所以遇到"没抓几次却被拦"，先看 UA 是不是简写的。urllib 默认 UA 是 `Python-urllib/3.x`，比简写的更容易被拦。**脚本里一律用完整 Chrome UA**，别为了省事写 `Mozilla/5.0`。

判别办法同样是看**响应字节数**：正常页 200KB+，被拦的只有 1–2KB。

---

## 3. ERR_PROXY_CONNECTION_FAILED

**症状**：页面一片灰，写着"未连接到互联网 / 代理服务器出现问题"，错误码 `ERR_PROXY_CONNECTION_FAILED`。

**真实原因**：`--proxy-server` 给的端口是错的，或者代理没启动。

**真实案例（本技能踩过）**：按旧记忆写了 `127.0.0.1:50602`，实际端口是 `54835`，那个端口根本没人监听。curl 因为读的是环境变量所以能通，Chrome 因为读的是我手写的参数所以不通 —— **两边不一致才是最难查的**。

**处置**：
- 端口一律**实时读取**，不要背：
  ```bash
  env | grep -i proxy        # macOS / Linux
  echo $env:HTTP_PROXY       # Windows PowerShell
  ```
- 先验代理本身通不通：`curl -x http://127.0.0.1:<port> -o /dev/null -w "%{http_code}" https://x.com/`，200 才继续。

---

## 4. 两个窗口互相抢页面 / 页面自己跳走

**症状**：我刚导航到 A 页，读到的却是 B 页；或者页面莫名跳回上一页。

**真实原因**：所有任务默认连同一个端口、用同一个 profile。两个任务操作同一个标签页，就是互相抢。

**处置**：
- 一个任务一个 session：`--session deal-hunter` / `--session deal-hunter-x`，端口自动 hash 到 93xx，profile 各自独立。
- **同名 session 仍然是共享**，并行时名字必须不同。
- 拿到了 `targetId` 就只操作这个 target，不要用"当前标签页"这种隐式指代。

---

## 5. 端口通，但标题不对 / 内容是空的

**症状**：CDP 返回 200，`list` 也有内容，但标题是 `about:blank` 或上一次的页面。

**真实原因**：页面还在跳转；或者 targetId 取错了（取到了旧的、已销毁的 target）。

**处置**：
- 加等待：`sleep 3` 或轮询标题非空再读。
- 重新 `python3 scripts/browser.py list --session <名字>` 拿新 id；**target id 是十六进制长串，别截断**（截成 8 位会报"target 不存在"）。
- 静态页直接读 `document.title + body.innerText.length` 两个值一起看，比标题单独可靠。

---

## 6. Cloudflare "Just a moment…" / "请稍候…"

**症状**：正文只有几十个字，标题是 "Just a moment..." 或 "请稍候…"。

**真实原因**：Cloudflare 人机校验还没过。裸 HTTP 请求必被拦，真浏览器一般 3–5 秒自动过。

**处置**：
- 等 5 秒再读；还不过就把窗口 `front` 给用户，让他点一下。
- 过不去就记录跳过，别硬刷（刷多了会被拉黑更久）。
- 常见于：LINUX DO、CamelCamelCamel、DealMoon。

---

## 7. 登录墙

**症状**：跳转到 `x.com/i/jf/onboarding/...`、`/login`，正文一百来字。

**真实原因**：这个 profile 没登录过。

**处置**：
- `python3 scripts/browser.py front <targetId> --session deal-hunter` 把窗口切到前台，让用户自己扫码/输密码。
- **绝不代输账号密码、不代收验证码。**
- 登录成功后**立刻**备份 cookie（session cookie 关窗即失效）：
  ```bash
  python3 scripts/browser.py cookies --session deal-hunter-x --save <数据目录>/cookies/x.json
  ```
- 平时不用手动"注回" cookie：登录态主要在 profile 目录里，关掉重开仍在。cookie 备份是给 profile 被清掉、或换机器时兜底用的。

---

## 8. `stop` 说关了，端口还占着

**症状**：关闭命令回"已关闭"，但下次启动报端口被占用。

**真实原因（真实 bug）**：zsh **默认不做 word splitting**。`for p in $PIDS; do kill "$p"; done` 里 `PIDS` 是 `"76042 "`（带尾空格），整串被当成一个参数传给 `kill`，静默失败。原脚本一直靠后面的 `pkill -f browser-profiles/collect` 兜底才看起来能用 —— 一旦 profile 名不同就彻底关不掉。

**处置**：
- 按行读 PID，或直接用 `lsof` 按端口取 PID：
  ```bash
  lsof -nP -iTCP:9315 -sTCP:LISTEN
  kill -9 <PID>
  ```
- **绝不 `pkill -f "Google Chrome"` / `killall Chrome`** —— 会连用户日常用的 Chrome 一起杀掉。
- 只按**调试端口**杀。

---

## 9. 截图是黑的 / 只有一半

**症状**：截出来的图空白、或者只有一半。

**真实原因**：用系统截图（`screencapture` / 系统截屏）时，窗口最小化或被遮挡就拍不到内容。

**处置**：
- 用 CDP 截图，跟窗口状态无关：
  ```bash
  python3 scripts/browser.py shot /tmp/page.png --session deal-hunter        # 可视区域
  python3 scripts/browser.py shot /tmp/page.png --session deal-hunter --full # 整页长图
  ```
- 系统截图只用于诊断"窗口到底在不在屏幕上"，不用于取内容。

---

## 10. 需要窗口在前台（要用户操作）

- `python3 scripts/browser.py front <targetId> --session <名字>`：把指定标签切到前台。
- 窗口被最小化时，先 `Browser.setWindowBounds` 置 `windowState: normal`，再 `Target.activateTarget`。
- macOS 上 `osascript -e 'tell application "Google Chrome" to activate'` 只能激活应用，**不一定能还原最小化窗口**，别指望它。

---

## 11. 抓不到就说抓不到

- 不要拿残留 DOM（页面上一次渲染的内容）当结果。
- 不要用"上次看到的价格"补今天的推送。
- 不要因为抓不到就降门槛凑数 —— 少推一条比推错一条代价小得多。

---

## 排查决策树

```
页面没内容？
├─ 标题对不对？ ── 不对 → 可能落到自带浏览器（用 CDP 直控）/ target 取错
├─ 正文只有几十字？
│   ├─ 标题含 "Just a moment" → Cloudflare，等 5 秒或让用户点
│   ├─ URL 含 /login 或 onboarding → 登录墙，front 给用户
│   └─ 含 ERR_PROXY_CONNECTION_FAILED → 代理端口错
└─ 端口通但内容空 → 页面没加载完，sleep 后重读
```
