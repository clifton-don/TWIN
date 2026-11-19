# TWIN 的 Windows 启动脚本。平时由 TWIN.exe 无窗口调用（不闪黑框）；Open_Web.bat 是后备入口。
# 第一次运行时用 Windows 自带的 C# 编译器生成 TWIN.exe（源码 tools\launcher\TWIN.cs，图标是 logo）。
# 不打扰：
#   - Python：盘上有就用盘上的；没有但电脑上装了，先用电脑上的启动，同时在后台把官方免安装版放进盘里；
#     两边都没有，才显示下载进度（没有 Python 跑不起来）。
#   - KeePassXC：电脑上装的优先（系统目录更难被篡改）；盘上没有备用的便携版，就在后台放一份，去别的电脑时应急用。
#   - 后台下载完成后，右下角托盘弹一条通知；失败了写进 tools
untime\setup.log，下次打开再试。
#   - 不想要：在 tools\runtime 里放一个空文件 .no-python / .no-keepassxc。
# 下载都从官方地址取，核对 SHA256 后才用。tools\runtime 不进 Git、不进空白版、升级不动。
# 只有出错时才弹窗。测试用环境变量 TWIN_SETUP=yes / no：不弹窗，no 表示不下载。
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
$NoDownload = $env:TWIN_SETUP -eq 'no'
$NoBrowser = $args -contains '--no-browser'
$Port = ($args | Where-Object { $_ -match '^\d+$' } | Select-Object -First 1)
if (-not $Port) { $Port = 8765 }
$Url = "http://127.0.0.1:$Port"
$Version = ''
try { $Version = ([regex]::Match((Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'twin_web.py')), '(?m)^VERSION = "([^"]+)"')).Groups[1].Value } catch { }

$PyV = '3.14.10'
$Py = if ($Arm) { @{ Zip = "python-$PyV-embed-arm64.zip"; Sha = 'bbe116bb1248820359cbf25127ac5c7794ea161869d83686cfbc9a45203ff836'; Size = 11934283 } }
      else { @{ Zip = "python-$PyV-embed-amd64.zip"; Sha = '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'; Size = 12619664 } }
$Py.Url = "https://www.python.org/ftp/python/$PyV/$($Py.Zip)"
$KpV = '2.8.0'
$Kp = if ($Arm) { @{ Zip = "KeePassXC-$KpV-ARM64.zip"; Sha = '408a44bc121d089ec7c63945fce0774044aea82316a4094033a9524493ab512e'; Size = 59703797 } }
      else { @{ Zip = "KeePassXC-$KpV-x64.zip"; Sha = '48ff4f088e9ce70e241da1270e5081528dba77c38b17dae4aa6690ffc50fc828'; Size = 70348471 } }
$Kp.Url = "https://github.com/keepassxreboot/keepassxc/releases/download/$KpV/$($Kp.Zip)"

function Say($title, $message, [switch]$Warn) {
    if ($Quiet) { Write-Output "$title`n$message"; return }
    Show-TwinDialog $title $message @('知道了') -Warn:$Warn | Out-Null
}

# 下载 $url，核对 SHA256，解压到 $dest（zip 里只有一个文件夹时取它里面的内容）。临时文件按目标分开，可以同时下几个
$FetchWork = {
    param($url, $sha, $dest)
    $ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = 'Tls12'
    $zip = "$dest.download.zip"
    $tmp = "$dest.unpack"
    New-Item -ItemType Directory -Force (Split-Path -Parent $dest) | Out-Null
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

# 免安装版 Python 只认 ._pth 里列的路径：把 tools 加进去，TWIN 的模块才能 import
function Fix-Pth {
    $pth = Get-ChildItem (Join-Path $RT 'python') -Filter 'python*._pth' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pth -and -not (Select-String -Path $pth.FullName -SimpleMatch '..\..' -Quiet)) { Add-Content -Encoding ascii $pth.FullName '..\..' }
}

# ---------- 已经在运行：只打开网页 ----------
$created = $false
$mutex = New-Object System.Threading.Mutex($true, "Local\TWIN-web-$Port", [ref]$created)
if (-not $created) {
    if (-not $NoBrowser) { Start-Process $Url }
    exit 0
}

# ---------- TWIN.exe：没有或源码、图标更新了就重新编译 ----------
$Exe = Join-Path $Root 'TWIN.exe'
$Cs = Join-Path $PSScriptRoot 'launcher\TWIN.cs'
$Ico = Join-Path $PSScriptRoot 'web\logo.ico'
$Csc = @("$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe", "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
$NewExe = $false
if ($Csc -and (Test-Path $Cs)) {
    $exeTime = if (Test-Path $Exe) { (Get-Item $Exe).LastWriteTime } else { [datetime]::MinValue }
    $icoTime = if (Test-Path $Ico) { (Get-Item $Ico).LastWriteTime } else { [datetime]::MinValue }
    $srcTime = @((Get-Item $Cs).LastWriteTime, $icoTime) | Sort-Object | Select-Object -Last 1
    if ($srcTime -gt $exeTime) {
        $had = Test-Path $Exe
        # 注意：if 表达式返回只有一项的数组会被拆成字符串，@ 展开时就成了一个个字符，所以这里分开赋值
        $icoArg = @()
        if (Test-Path $Ico) { $icoArg = @("-win32icon:$Ico") }
        try {
            $cscOut = & $Csc -nologo -target:winexe @icoArg "-out:$Exe" $Cs 2>&1
            if ($LASTEXITCODE -ne 0) { New-Item -ItemType Directory -Force $RT | Out-Null; Add-Content -Encoding UTF8 (Join-Path $RT 'setup.log') "[$(Get-Date -Format s)] 编译 TWIN.exe 没成功：$($cscOut -join ' ')" }
            $NewExe = (-not $had) -and (Test-Path $Exe)
        } catch { }
    }
}

# ---------- Python ----------
$PyExe = Join-Path $RT 'python\python.exe'
$WantPy = -not (Test-Path $PyExe) -and -not (Test-Path (Join-Path $RT '.no-python')) -and -not $NoDownload
$PyCmd = $null; $PyArgs = @()
if (Test-Path $PyExe) { $PyCmd = $PyExe }
elseif (Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch 'WindowsApps' }) { $PyCmd = 'python' }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $PyCmd = 'py'; $PyArgs = @('-3') }

# 电脑上没有 Python：只能先下好再启动（这时才显示进度）
if (-not $PyCmd -and $WantPy) {
    try {
        if ($Quiet) { & $FetchWork $Py.Url $Py.Sha (Join-Path $RT 'python') | Out-Null }
        else { Invoke-TwinProgress '第一次运行：正在把 Python 放进这块盘' $FetchWork @($Py.Url, $Py.Sha, (Join-Path $RT 'python')) (Join-Path $RT 'python.download.zip') $Py.Size | Out-Null }
        Fix-Pth
        $PyCmd = $PyExe; $WantPy = $false
    } catch { }
}
if (-not $PyCmd) {
    Say '没找到 Python' ("TWIN 需要 Python 才能运行，刚才也没能下载（可能没联网）。`n`n" +
        "联网后重新打开 TWIN 会再试；或者自己安装：python.org 下载页点最上面黄色的 Download Python，安装第一页先勾上 Add python.exe to PATH。") -Warn
    Start-Process 'https://www.python.org/downloads/'
    exit 1
}

# ---------- KeePassXC（密码库，首页点网站时自动填密码用）----------
# 用字符串拼路径：Join-Path 遇到不存在的盘符会直接报错
$KpPortable = "$RT\KeePassXC\KeePassXC.exe"
$KpLocal = @("$env:ProgramFiles\KeePassXC\KeePassXC.exe", "$env:LOCALAPPDATA\Programs\KeePassXC\KeePassXC.exe") |
    Where-Object { $_ -notmatch '^\\' -and (Test-Path -LiteralPath $_ -ErrorAction SilentlyContinue) } | Select-Object -First 1
$WantKp = -not (Test-Path $KpPortable) -and -not (Test-Path (Join-Path $RT '.no-keepassxc')) -and -not $NoDownload
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
$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Icon = if (Test-Path $Ico) { New-Object System.Drawing.Icon $Ico, 16, 16 } else { [System.Drawing.SystemIcons]::Application }
$tray.Text = "TWIN 正在运行（$Url）"
$state = @{ quitting = $false }
$disp = [System.Windows.Threading.Dispatcher]::CurrentDispatcher

function Notify($text) {
    if ($Quiet) { Write-Output $text; return }
    $tray.ShowBalloonTip(6000, 'TWIN', $text, [System.Windows.Forms.ToolTipIcon]::Info)
}

$menuItems = @(
    @{ Icon = 'E8A7'; Text = '打开 TWIN'; Do = { Start-Process $Url } },
    @{ Icon = 'E72E'; Text = '打开 KeePassXC'; Do = {
        $k = if ($KpLocal) { $KpLocal } elseif (Test-Path $KpPortable) { $KpPortable } else { $null }
        if ($k) { Start-Process $k } else { Say '还没有 KeePassXC' '盘上的便携版还在后台下载，或者被关掉了（删掉 tools\runtime 里的 .no-keepassxc 就会再下）。' }
    } },
    @{ Icon = 'E8A5'; Text = '运行记录（手机地址、报错）'; Do = { Start-Process notepad.exe -ArgumentList "`"$Log`"" } },
    @{ Icon = 'E838'; Text = '打开 TWIN 文件夹'; Do = { Start-Process explorer.exe -ArgumentList "`"$Root`"" } },
    '-',
    @{ Icon = 'E7E8'; Text = '退出 TWIN'; Danger = $true; Do = { $state.quitting = $true; $disp.InvokeShutdown() } }
)
$sub = if ($Version) { "v$($Version -replace '-beta$', ' beta') · 端口 $Port" } else { "端口 $Port" }
# 不用闭包：闭包里找不到本脚本定义的函数
$tray.add_MouseUp({ param($s, $e) if ($e.Button -eq 'Right') { Show-TwinMenu 'TWIN 正在运行' $sub $menuItems } })
$tray.add_MouseDoubleClick({ Start-Process $Url })
$tray.Visible = $true
if ($NewExe) { Notify '以后双击 TWIN 文件夹里的 TWIN.exe 打开，不会再闪窗口。' }

# ---------- 后台下载（不弹窗，完成后托盘通知）----------
$jobs = New-Object System.Collections.ArrayList
function Start-Bg($item, $dest, $what, $after) {
    $ps = [powershell]::Create()
    $null = $ps.AddScript($FetchWork).AddArgument($item.Url).AddArgument($item.Sha).AddArgument($dest)
    [void]$jobs.Add(@{ ps = $ps; h = $ps.BeginInvoke(); what = $what; after = $after })
}
if ($WantPy) { Start-Bg $Py (Join-Path $RT 'python') 'Python' { Fix-Pth; Notify '已把 Python 放进这块盘：插到别的 Windows 电脑也能直接打开 TWIN。' } }
if ($WantKp) { Start-Bg $Kp (Join-Path $RT 'KeePassXC') 'KeePassXC' { Notify '已在盘里备好 KeePassXC 便携版，去别的电脑时应急用。' } }

$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromSeconds(2)
$timer.Add_Tick({
    if ($proc.HasExited) { $timer.Stop(); $disp.InvokeShutdown(); return }
    foreach ($j in @($jobs)) {
        if (-not $j.h.IsCompleted) { continue }
        $jobs.Remove($j)
        try {
            $j.ps.EndInvoke($j.h) | Out-Null
            if ($j.ps.Streams.Error.Count) { throw $j.ps.Streams.Error[0].Exception }
            & $j.after
        } catch {
            Add-Content -Encoding UTF8 (Join-Path $RT 'setup.log') "[$(Get-Date -Format s)] 后台下载 $($j.what) 没成功，下次打开再试：$($_.Exception.Message)"
        } finally { $j.ps.Dispose() }
    }
})
$timer.Start()

try { [System.Windows.Threading.Dispatcher]::Run() }
finally {
    $timer.Stop()
    foreach ($j in @($jobs)) { try { $j.ps.Stop(); $j.ps.Dispose() } catch { } }
    $tray.Visible = $false
    $tray.Dispose()
    if ($state.quitting) { Stop-Twin } elseif ($proc.HasExited -and $proc.ExitCode -ne 0) { Show-Crash }
    $mutex.ReleaseMutex()
}
