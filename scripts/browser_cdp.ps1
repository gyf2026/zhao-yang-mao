<#
browser_cdp.ps1 —— Windows 版：启动 / 探活 / 关闭「带 CDP 调试端口」的独立 Chrome

为什么需要它
  1. Windows 上 Chrome 是单实例：用户已经开着 Chrome 时，再启动带 --remote-debugging-port 的
     实例，参数会被静默忽略（"命令成功，但端口连不上"）。必须给独立的 user-data-dir。
  2. 内置浏览器控制在连接失败时会静默回退到自带 Chromium，导致读到的是另一个浏览器的页面。

用法
  .\browser_cdp.ps1 start "https://www.smzdm.com/" -Session deal-hunter
  .\browser_cdp.ps1 start "https://x.com/home" -Session deal-hunter-x `
      -Proxy "http://127.0.0.1:7890" -ProxyBypass "*.smzdm.com;*.v2ex.com;<local>"
  .\browser_cdp.ps1 status -Session deal-hunter
  .\browser_cdp.ps1 list
  .\browser_cdp.ps1 stop -Session deal-hunter

注意
  - 只按「调试端口」杀进程，绝不 taskkill /IM chrome.exe（会杀掉用户日常浏览器）。
  - 本文件请保存为 UTF-8 with BOM，否则中文注释在旧版 PowerShell 下会乱码。
#>

param(
  [Parameter(Position = 0)]
  [ValidateSet('start', 'status', 'stop', 'list', 'open')]
  [string]$Command = 'start',

  [Parameter(Position = 1)]
  [string]$Url = '',

  [string]$Session = 'deal-hunter',
  [int]$Port = 0,
  [string]$Proxy = '',
  [string]$ProxyBypass = '',
  [switch]$Headless
)

$ErrorActionPreference = 'Stop'
$env:NO_PROXY = '127.0.0.1,localhost'
$env:no_proxy = '127.0.0.1,localhost'

# profile 根目录：优先环境变量，否则放在通用默认数据目录下（与 _paths.py 的兜底一致）
# 这不是给日常浏览器用的，是本脚本自己起的独立实例，不能和用户日常 profile 混用
$DataHome = if ($env:DEAL_HUNTER_HOME) { $env:DEAL_HUNTER_HOME } else { Join-Path $env:USERPROFILE '.deal-hunter' }
$ProfileRoot = if ($env:DEAL_HUNTER_PROFILE_ROOT) { $env:DEAL_HUNTER_PROFILE_ROOT } else { Join-Path $DataHome 'browser-profiles' }

function Get-Port {
  param([string]$Name, [int]$Explicit)
  if ($Explicit -gt 0) { return $Explicit }
  # 名字 hash 到 9300-9399：同名稳定、异名不撞
  $sum = 0
  foreach ($ch in $Name.ToCharArray()) { $sum = ($sum * 31 + [int]$ch) % 100000 }
  return 9300 + ($sum % 100)
}

function Find-Chrome {
  $cands = @(
    (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
    (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
  )
  foreach ($c in $cands) { if ($c -and (Test-Path $c)) { return $c } }
  throw '找不到 chrome.exe，请用 $env:CHROME_PATH 指定完整路径'
}

function Test-Cdp {
  param([int]$P)
  try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$P/json/version" -TimeoutSec 5 -NoProxy
    return [bool]$r.Browser
  } catch { return $false }
}

function Get-ListenerPid {
  param([int]$P)
  $ids = @()
  try {
    $ids = (Get-NetTCPConnection -LocalPort $P -State Listen -ErrorAction SilentlyContinue).OwningProcess
  } catch {
    $ids = netstat -ano | Select-String ":$P\s+\S+\s+LISTENING" |
           ForEach-Object { ($_ -split '\s+')[-1] }
  }
  return @($ids | Where-Object { $_ } | Select-Object -Unique)
}

$TargetPort = Get-Port -Name $Session -Explicit $Port
$Profile = Join-Path $ProfileRoot $Session

switch ($Command) {

  'start' {
    if (Test-Cdp -P $TargetPort) {
      Write-Host "✓ CDP 已在运行 :$TargetPort（若属别的窗口，换 -Session 隔离）"
      exit 0
    }

    $chrome = if ($env:CHROME_PATH) { $env:CHROME_PATH } else { Find-Chrome }
    New-Item -ItemType Directory -Force -Path $Profile | Out-Null
    $startUrl = if ($Url) { $Url } else { 'about:blank' }

    $args = @(
      "--remote-debugging-port=$TargetPort",
      "--user-data-dir=$Profile",
      '--no-first-run',
      '--no-default-browser-check',
      '--remote-allow-origins=*',
      '--window-size=1280,900'
    )
    if ($Proxy) { $args += "--proxy-server=$Proxy" }
    if ($ProxyBypass) { $args += "--proxy-bypass-list=$ProxyBypass" }
    if ($Headless) { $args += '--headless=new' }
    $args += $startUrl

    # Start-Process 启动的进程不挂在本 shell 下，天然满足"活过本次调用"
    Start-Process -FilePath $chrome -ArgumentList $args

    for ($i = 0; $i -lt 20; $i++) {
      Start-Sleep -Seconds 1
      if (Test-Cdp -P $TargetPort) {
        Write-Host "✓ CDP 就绪 :$TargetPort"
        Write-Host "  profile = $Profile"
        Write-Host "  下一步: `$env:CDP_PORT=$TargetPort; node scripts\cdp.js list"
        exit 0
      }
    }
    Write-Host "✗ 启动失败 :$TargetPort"
    Write-Host "  排查：1) 是否已有同 profile 的 Chrome 在跑 2) 杀软是否拦截 3) 换 -Port 试"
    exit 1
  }

  'open' {
    if (-not (Test-Cdp -P $TargetPort)) {
      & $PSCommandPath start $Url -Session $Session -Port $TargetPort -Proxy $Proxy -ProxyBypass $ProxyBypass
    }
    $env:CDP_PORT = $TargetPort
    node (Join-Path $PSScriptRoot 'cdp.js') newtab $Url
  }

  'status' {
    if (Test-Cdp -P $TargetPort) {
      $v = Invoke-RestMethod -Uri "http://127.0.0.1:$TargetPort/json/version" -TimeoutSec 5 -NoProxy
      Write-Host "✓ :$TargetPort  $($v.Browser)"
      $tabs = Invoke-RestMethod -Uri "http://127.0.0.1:$TargetPort/json/list" -TimeoutSec 5 -NoProxy
      Write-Host "  标签页 $($tabs.Count) 个"
    } else {
      Write-Host "✗ :$TargetPort 未运行"
    }
  }

  'stop' {
    $pids = Get-ListenerPid -P $TargetPort
    if (-not $pids) { Write-Host "· :$TargetPort 本来就没在跑"; exit 0 }
    foreach ($id in $pids) {
      try { Stop-Process -Id $id -Force; Write-Host "✓ 已关闭 :$TargetPort (PID $id)" }
      catch { Write-Host "✗ 关闭失败 PID $id : $($_.Exception.Message)" }
    }
  }

  'list' {
    Write-Host '采集用 Chrome（端口 9300-9399 / 9222）...'
    $found = $false
    foreach ($p in (9222..9222) + (9300..9399)) {
      if (Test-Cdp -P $p) {
        $found = $true
        $tabs = Invoke-RestMethod -Uri "http://127.0.0.1:$p/json/list" -TimeoutSec 3 -NoProxy
        $first = ($tabs | Where-Object { $_.type -eq 'page' } | Select-Object -First 1).title
        Write-Host ("  :{0}  标签页 {1}  首个: {2}" -f $p, $tabs.Count, $first)
      }
    }
    if (-not $found) { Write-Host '  （没有在跑的实例）' }
  }
}
