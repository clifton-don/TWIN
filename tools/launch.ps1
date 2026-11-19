﻿# TWIN 的 Windows 启动脚本，由 Open_Web.bat 隐藏窗口调用（bat 只能放英文，中文提示都在这里）。
# 不开黑框：提示用 TWIN 自己的弹窗（launch_ui.ps1），TWIN 在后台跑，右下角托盘图标右键是菜单。
# 1. Python：优先用这块盘上自带的（tools\runtime\python），没有就问一次要不要下载官方免安装版；再不行用电脑上装的。
# 2. KeePassXC：优先用电脑上装的（Program Files 要管理员才能改，比盘上的更难被人换掉）；
#    盘上没有备用的便携版就问一次要不要放一份，去别的电脑时应急用。没在运行就顺手打开。
# 下载都从官方地址取，核对 SHA256 后才用。tools\runtime 不进 Git、不进空白版、升级不动。
# 自动回答（脚本或测试用）：环境变量 TWIN_SETUP=yes 或 no，这时不弹窗。
# 注意：这个文件里的中文提示别用弯引号（PowerShell 会把它当成字符串的引号）。
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'  # 不画进度条，下载快很多
[Net.ServicePointManager]::SecurityProtocol = 'Tls12'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
. (Join-Path $PSScriptRoot 'launch_ui.ps1')

$Root = Split-Path -Parent $PSScriptRoot
$RT = Join-Path $PSScriptRoot 'runtime'
$Arm = $env:PROCESSOR_ARCHITECTURE -eq 'ARM64'
$Quiet = $env:TWIN_SETUP -in @('yes', 'no')
$NoBrowser = $args -contains '--no-browser'
$Port = ($args | Where-Object { $_ -match '^\d+$' } | Select-Object -First 1)
if (-not $Port) { $Port = 8765 }
$Url = "http://127.0.0.1:$Port"
$Version = ''
try { $Version = ([regex]::Match((Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'twin_web.py')), '(?m)^VERSION = "([^"]+)"')).Groups[1].Value } catch { }

$PyV = '3.14.10'
$Py = if ($Arm) { @{ Zip = "python-$PyV-embed-arm64.zip"; Sha = 'bbe116bb1248820359cbf25127ac5c7794ea161869d83686cfbc9a45203ff836'; Size = 11934283 } }
      else { @{ Zip = "python-$PyV-embed-amd64.zip"; Sha = '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'; Size = 12619664 } }
$KpV = '2.8.0'
$Kp = if ($Arm) { @{ Zip = "KeePassXC-$KpV-ARM64.zip"; Sha = '408a44bc121d089ec7c63945fce0774044aea82316a4094033a9524493ab512e'; Size = 59703797 } }
      else { @{ Zip = "KeePassXC-$KpV-x64.zip"; Sha = '48ff4f088e9ce70e241da1270e5081528dba77c38b17dae4aa6690ffc50fc828'; Size = 70348471 } }

function Ask($title, $message, $yes, $no) {
    if ($env:TWIN_SETUP -eq 'yes') { return $true }
    if ($env:TWIN_SETUP -eq 'no') { return $false }
    return (Show-TwinDialog $title $message @($yes, $no)) -eq 0
}

function Say($title, $message, [switch]$Warn) {
    if ($Quiet) { Write-Output "$title`n$message"; return }
    Show-TwinDialog $title $message @('知道了') -Warn:$Warn | Out-Null
}

function Remember-No($name) {
    New-Item -ItemType Directory -Force $RT | Out-Null
    New-Item -ItemType File -Force (Join-Path $RT $name) | Out-Null
}

# 后台下载 $url，核对 SHA256，解压到 $dest（zip 里只有一个文件夹时取它里面的内容）。前台显示进度
$FetchWork = {
    param($url, $sha, $dest, $rt)
    $ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = 'Tls12'
    New-Item -ItemType Directory -Force $rt | Out-Null
    $zip = Join-Path $rt '_download.zip'
    $tmp = Join-Path $rt '_unpack'
    if (Test-Path $zip) { Remove-Item $zip }
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne $sha) {
        Remove-Item $zip
        throw '校验值对不上，文件可能被改过，已删除，没有使用。'
    }
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive -Force $zip $tmp
    Remove-Item $zip
    $in = @(Get-ChildItem $tmp)
    $src = if ($in.Count -eq 1 -and $in[0].PSIsContainer) { $in[0].FullName } else { $tmp }
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Move-Item $src $dest
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    'ok'
}

function Fetch($url, $sha, $dest, $what, $size) {
    try {
        if ($Quiet) { & $FetchWork $url $sha $dest $RT | Out-Null }
        else { Invoke-TwinProgress "正在下载 $what" $FetchWork @($url, $sha, $dest, $RT) (Join-Path $RT '_download.zip') $size | Out-Null }
        return $true
    } catch {
        Say "下载 $what 没成功" "$($_.Exception.Message)`n`n下次打开 TWIN 会再问。" -Warn
        return $false
    }
}

# ---------- 已经在运行：只打开网页 ----------
$created = $false
$mutex = New-Object System.Threading.Mutex($true, "Local\TWIN-web-$Port", [ref]$created)
if (-not $created) {
    if (-not $NoBrowser) { Start-Process $Url }
    exit 0
}

# ---------- Python ----------
$PyExe = Join-Path $RT 'python\python.exe'
if (-not (Test-Path $PyExe) -and -not (Test-Path (Join-Path $RT '.no-python'))) {
    $msg = "把官方免安装版 Python $PyV（约 12 MB）放进这块盘，以后插到别的 Windows 电脑也能直接打开 TWIN，" +
           "不用另装 Python，也不在那台电脑上留东西。`n`n选 [不用了] 就用这台电脑上装的 Python，以后不再问。"
    if (Ask '把 Python 放进这块盘？' $msg '放进这块盘' '不用了') {
        if (Fetch "https://www.python.org/ftp/python/$PyV/$($Py.Zip)" $Py.Sha (Join-Path $RT 'python') 'Python' $Py.Size) {
            # 免安装版只认 ._pth 里列的路径：把 tools 加进去，TWIN 的模块才能 import
            $pth = Get-ChildItem (Join-Path $RT 'python') -Filter 'python*._pth' | Select-Object -First 1
            if ($pth) { Add-Content -Encoding ascii $pth.FullName '..\..' }
        }
    } else { Remember-No '.no-python' }
}

$PyCmd = $null; $PyArgs = @()
if (Test-Path $PyExe) { $PyCmd = $PyExe }
elseif (Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch 'WindowsApps' }) { $PyCmd = 'python' }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $PyCmd = 'py'; $PyArgs = @('-3') }

if (-not $PyCmd) {
    Say '没找到 Python' ("TWIN 需要 Python 才能运行。`n`n最省事：删掉 tools\runtime 里的 .no-python，重新双击 Open_Web.bat，选 [放进这块盘]。`n`n" +
        "或者自己安装：python.org 下载页点最上面黄色的 Download Python，安装第一页先勾上 Add python.exe to PATH。") -Warn
    Start-Process 'https://www.python.org/downloads/'
    exit 1
}

# ---------- KeePassXC（密码库，首页点网站时自动填密码用）----------
# 用字符串拼路径：Join-Path 遇到不存在的盘符会直接报错
$KpPortable = "$RT\KeePassXC\KeePassXC.exe"
$KpLocal = @("$env:ProgramFiles\KeePassXC\KeePassXC.exe", "$env:LOCALAPPDATA\Programs\KeePassXC\KeePassXC.exe") |
    Where-Object { $_ -notmatch '^\\' -and (Test-Path -LiteralPath $_ -ErrorAction SilentlyContinue) } | Select-Object -First 1
if (-not (Test-Path $KpPortable) -and -not (Test-Path (Join-Path $RT '.no-keepassxc'))) {
    if ($KpLocal) {
        $title = '在盘里备一份 KeePassXC？'
        $msg = "这台电脑装了 KeePassXC，平时还是用电脑上这份。在盘里再备一份便携版（约 70 MB），去别的电脑时应急用。`n`n" +
               "提醒：别在网吧、公用电脑上输入主密码。选 [不用了] 以后不再问。"
    } else {
        $title = '把 KeePassXC 放进这块盘？'
        $msg = "KeePassXC 是本地加密的密码库，首页点网站时能自动填密码。官方便携版 $KpV（约 70 MB）不用安装，插到别的电脑也能用。`n`n" +
               "密码库文件请放在 TWIN 外面、同级的 VAULT 文件夹里。选 [不用了] 以后不再问。"
    }
    if (Ask $title $msg '放进这块盘' '不用了') {
        Fetch "https://github.com/keepassxreboot/keepassxc/releases/download/$KpV/$($Kp.Zip)" $Kp.Sha (Join-Path $RT 'KeePassXC') 'KeePassXC' $Kp.Size | Out-Null
    } else { Remember-No '.no-keepassxc' }
}
# 优先用电脑上装的；没装才用盘上的。没在运行就顺手打开：解锁后，首页点网站图标才能自动填密码
$KpExe = if ($KpLocal) { $KpLocal } elseif (Test-Path $KpPortable) { $KpPortable } else { $null }
if ($KpExe -and -not $Quiet -and -not (Get-Process KeePassXC -ErrorAction SilentlyContinue)) {
    Start-Process $KpExe
}

# ---------- 后台启动 TWIN（不开黑框，输出写进运行记录）----------
New-Item -ItemType Directory -Force $RT | Out-Null
# 默认端口叫 twin.log；同时开几个端口时各写各的，免得互相覆盖
$tag = if ($Port -eq 8765) { '' } else { "-$Port" }
$Log = Join-Path $RT "twin$tag.log"
$ErrLog = Join-Path $RT "twin$tag-error.log"
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONIOENCODING = 'utf-8'
$Web = Join-Path $PSScriptRoot 'twin_web.py'
$argList = @($PyArgs) + @("`"$Web`"") + @($args | ForEach-Object { "`"$_`"" })
$proc = Start-Process -FilePath $PyCmd -ArgumentList $argList -WorkingDirectory $Root -WindowStyle Hidden `
    -RedirectStandardOutput $Log -RedirectStandardError $ErrLog -PassThru
$null = $proc.Handle  # 先拿住句柄，进程结束后才读得到退出码

function Stop-Twin {
    if (-not $proc.HasExited) { & taskkill.exe /PID $proc.Id /T /F | Out-Null }  # /T：连 py 启动器带出来的 python 一起停
}

function Show-Crash {
    $tail = if (Test-Path $ErrLog) { (Get-Content -Tail 8 -Encoding UTF8 $ErrLog) -join "`n" } else { '' }
    Say 'TWIN 没能启动或意外停止了' "$tail`n`n完整记录在：$ErrLog" -Warn
}

Start-Sleep -Seconds 2
if ($proc.HasExited) { Show-Crash; exit 1 }

# ---------- 托盘图标 ----------
$icoPath = Join-Path $PSScriptRoot 'web\logo.ico'
$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Icon = if (Test-Path $icoPath) { New-Object System.Drawing.Icon $icoPath, 16, 16 } else { [System.Drawing.SystemIcons]::Application }
$tray.Text = "TWIN 正在运行（$Url）"
$state = @{ quitting = $false }
$disp = [System.Windows.Threading.Dispatcher]::CurrentDispatcher

$menuItems = @(
    @{ Icon = 'E8A7'; Text = '打开 TWIN'; Do = { Start-Process $Url } },
    @{ Icon = 'E72E'; Text = '打开 KeePassXC'; Do = {
        $k = if ($KpLocal) { $KpLocal } elseif (Test-Path $KpPortable) { $KpPortable } else { $null }
        if ($k) { Start-Process $k } else { Say '没有 KeePassXC' '删掉 tools\runtime 里的 .no-keepassxc，重新打开 TWIN 就会再问要不要放进这块盘。' }
    } },
    @{ Icon = 'E8A5'; Text = '运行记录（手机地址、报错）'; Do = { Start-Process notepad.exe -ArgumentList "`"$Log`"" } },
    @{ Icon = 'E838'; Text = '打开 TWIN 文件夹'; Do = { Start-Process explorer.exe -ArgumentList "`"$Root`"" } },
    '-',
    @{ Icon = 'E7E8'; Text = '退出 TWIN'; Danger = $true; Do = { $state.quitting = $true; $disp.InvokeShutdown() } }
)
$sub = if ($Version) { "v$($Version -replace '-beta$', ' beta') · 端口 $Port" } else { "端口 $Port" }
$tray.add_MouseUp({
    param($s, $e)
    if ($e.Button -eq 'Right') { Show-TwinMenu 'TWIN 正在运行' $sub $menuItems }
})  # 不用闭包：闭包里找不到本脚本定义的函数
$tray.add_MouseDoubleClick({ Start-Process $Url })
$tray.Visible = $true

$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromSeconds(2)
$timer.Add_Tick({ if ($proc.HasExited) { $timer.Stop(); $disp.InvokeShutdown() } })
$timer.Start()

try { [System.Windows.Threading.Dispatcher]::Run() }
finally {
    $timer.Stop()
    $tray.Visible = $false
    $tray.Dispose()
    if ($state.quitting) { Stop-Twin } elseif ($proc.HasExited -and $proc.ExitCode -ne 0) { Show-Crash }
    $mutex.ReleaseMutex()
}
