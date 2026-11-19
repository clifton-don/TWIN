# TWIN 的 Windows 启动脚本，由 Open_Web.bat 调用（bat 只能放英文，中文提示都在这里）。
# 1. Python：优先用这块盘上自带的（tools\runtime\python），没有就问一次要不要下载官方免安装版；再不行用电脑上装的。
# 2. KeePassXC：电脑上装了或盘上带了就顺手打开；都没有就问一次要不要下载官方便携版到这块盘。
# 下载都从官方地址取，核对 SHA256 后才用。tools\runtime 不进 Git、不进空白版、升级不动。
# 自动回答（脚本或测试用）：环境变量 TWIN_SETUP=yes 或 no。
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'  # 不画进度条，下载快很多
[Console]::OutputEncoding = [Text.Encoding]::UTF8
[Net.ServicePointManager]::SecurityProtocol = 'Tls12'

$Root = Split-Path -Parent $PSScriptRoot
$RT = Join-Path $PSScriptRoot 'runtime'
$Arm = $env:PROCESSOR_ARCHITECTURE -eq 'ARM64'

$PyV = '3.14.10'
$Py = if ($Arm) { @{ Zip = "python-$PyV-embed-arm64.zip"; Sha = 'bbe116bb1248820359cbf25127ac5c7794ea161869d83686cfbc9a45203ff836' } }
      else { @{ Zip = "python-$PyV-embed-amd64.zip"; Sha = '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159' } }
$KpV = '2.8.0'
$Kp = if ($Arm) { @{ Zip = "KeePassXC-$KpV-ARM64.zip"; Sha = '408a44bc121d089ec7c63945fce0774044aea82316a4094033a9524493ab512e' } }
      else { @{ Zip = "KeePassXC-$KpV-x64.zip"; Sha = '48ff4f088e9ce70e241da1270e5081528dba77c38b17dae4aa6690ffc50fc828' } }

function Ask($question) {
    if ($env:TWIN_SETUP -eq 'yes') { return $true }
    if ($env:TWIN_SETUP -eq 'no') { return $false }
    $a = Read-Host " $question [Y/N]"
    return $a -match '^[Yy]'
}

function Remember-No($name) {
    New-Item -ItemType Directory -Force $RT | Out-Null
    New-Item -ItemType File -Force (Join-Path $RT $name) | Out-Null
}

# 下载 $url，核对 SHA256，解压到 $dest（zip 里只有一个文件夹时取它里面的内容）
function Fetch($url, $sha, $dest) {
    New-Item -ItemType Directory -Force $RT | Out-Null
    $zip = Join-Path $RT '_download.zip'
    $tmp = Join-Path $RT '_unpack'
    Write-Host "  正在下载 $(Split-Path -Leaf $url) ..."
    try { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zip }
    catch { Write-Host "  下载没成功：$($_.Exception.Message)"; return $false }
    if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne $sha) {
        Remove-Item $zip
        Write-Host '  校验值对不上，文件可能被改过，已删除，没有使用。'
        return $false
    }
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive -Force $zip $tmp
    Remove-Item $zip
    $in = @(Get-ChildItem $tmp)
    $src = if ($in.Count -eq 1 -and $in[0].PSIsContainer) { $in[0].FullName } else { $tmp }
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Move-Item $src $dest
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Write-Host '  好了，已核对校验值。'
    return $true
}

# ---------- Python ----------
$PyExe = Join-Path $RT 'python\python.exe'
if (-not (Test-Path $PyExe) -and -not (Test-Path (Join-Path $RT '.no-python'))) {
    Write-Host ''
    Write-Host " 第一次在这块盘上运行：可以把 Python $PyV（官方免安装版，约 12 MB）放进这块盘，"
    Write-Host ' 以后插到别的 Windows 电脑也能直接打开 TWIN，不用另装 Python，也不在那台电脑上留东西。'
    if (Ask '现在下载吗？') {
        if (Fetch "https://www.python.org/ftp/python/$PyV/$($Py.Zip)" $Py.Sha (Join-Path $RT 'python')) {
            # 免安装版只认 ._pth 里列的路径：把 tools 加进去，TWIN 的模块才能 import
            $pth = Get-ChildItem (Join-Path $RT 'python') -Filter 'python*._pth' | Select-Object -First 1
            if ($pth) { Add-Content -Encoding ascii $pth.FullName '..\..' }
        } else { Write-Host ' 这次先用电脑上装的 Python；下次打开会再问。' }
    } else { Remember-No '.no-python' }
}

$PyCmd = $null; $PyArgs = @()
if (Test-Path $PyExe) { $PyCmd = $PyExe }
elseif (Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch 'WindowsApps' }) { $PyCmd = 'python' }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $PyCmd = 'py'; $PyArgs = @('-3') }

if (-not $PyCmd) {
    Write-Host ''
    Write-Host ' 没找到 Python，TWIN 需要它才能运行。'
    Write-Host ' 最省事：删掉 tools\runtime 里的 .no-python，重新双击 Open_Web.bat，选 Y 把 Python 放进这块盘。'
    Write-Host ' 或者自己安装：打开 https://www.python.org/downloads/ ，点最上面黄色的 "Download Python"，'
    Write-Host ' 安装第一页先勾上最下面的 "Add python.exe to PATH"，再点 "Install Now"，装好后重新双击 Open_Web.bat。'
    Start-Process 'https://www.python.org/downloads/'
    exit 1
}

# ---------- KeePassXC（密码库，首页点网站时自动填密码用）----------
# 用字符串拼路径：Join-Path 遇到不存在的盘符会直接报错
$KpExe = @(
    "$RT\KeePassXC\KeePassXC.exe",
    "$env:ProgramFiles\KeePassXC\KeePassXC.exe",
    "$env:LOCALAPPDATA\Programs\KeePassXC\KeePassXC.exe"
) | Where-Object { $_ -notmatch '^\\' -and (Test-Path -LiteralPath $_ -ErrorAction SilentlyContinue) } | Select-Object -First 1
if (-not $KpExe -and -not (Test-Path (Join-Path $RT '.no-keepassxc'))) {
    Write-Host ''
    Write-Host " 没找到 KeePassXC（本地加密的密码库）。可以把官方便携版 $KpV（约 70 MB）放进这块盘，"
    Write-Host ' 不用安装，插到别的电脑也能用。密码库文件请放在 TWIN 外面的 VAULT 文件夹里。'
    if (Ask '现在下载吗？') {
        if (Fetch "https://github.com/keepassxreboot/keepassxc/releases/download/$KpV/$($Kp.Zip)" $Kp.Sha (Join-Path $RT 'KeePassXC')) {
            $KpExe = Join-Path $RT 'KeePassXC\KeePassXC.exe'
        } else { Write-Host ' 下次打开会再问。' }
    } else { Remember-No '.no-keepassxc' }
}
# 没在运行就顺手打开：解锁后，首页点网站图标才能自动填密码
if ($KpExe -and (Test-Path $KpExe) -and -not (Get-Process KeePassXC -ErrorAction SilentlyContinue)) {
    Start-Process $KpExe
}

# ---------- 启动 TWIN ----------
Set-Location $Root
& $PyCmd @PyArgs (Join-Path $PSScriptRoot 'twin_web.py') @args
exit $LASTEXITCODE
