# 生成 TWIN 的 logo 图片（开发用，改了 logo 才需要跑一次）：
#   powershell -ExecutionPolicy Bypass -File tools\make_logo.ps1
# 用 WPF 按和 docs\logo.svg 一样的路径画，输出 tools\web\logo-{尺寸}.png，再由 tools\make_ico.py 拼成 logo.ico。
# 24 像素以下用简化版：去掉细横线、加粗笔画，托盘里才看得清。
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
$out = Join-Path $PSScriptRoot 'web'

function Brush($hex) { (New-Object System.Windows.Media.BrushConverter).ConvertFromString($hex) }

function Render($size, $small) {
    $dv = New-Object System.Windows.Media.DrawingVisual
    $dc = $dv.RenderOpen()
    $k = $size / 64.0
    $dc.PushTransform((New-Object System.Windows.Media.ScaleTransform $k, $k))
    $r = if ($small) { 12 } else { 14 }
    $dc.DrawRoundedRectangle((Brush '#26215C'), $null, (New-Object System.Windows.Rect 0, 0, 64, 64), $r, $r)
    if ($small) {
        # 简化版：T 和倒影都加粗，中间留一条缝代替水面线
        $dc.DrawGeometry((Brush '#FFFFFF'), $null, [System.Windows.Media.Geometry]::Parse('M12 8h40v9H37v11h-10V17H12z'))
        $dc.DrawGeometry((Brush '#55C2B8'), $null, [System.Windows.Media.Geometry]::Parse('M12 56h40v-9H37V36h-10v11H12z'))
    } else {
        $dc.DrawGeometry((Brush '#FFFFFF'), $null, [System.Windows.Media.Geometry]::Parse('M16 10h32v6H35v15h-6V16H16z'))
        $dc.DrawRoundedRectangle((Brush '#7F6FE0'), $null, (New-Object System.Windows.Rect 12, 33, 40, 2), 1, 1)
        $dc.DrawGeometry((Brush '#55C2B8'), $null, [System.Windows.Media.Geometry]::Parse('M16 54h32v-6H35V37h-6v11H16z'))
    }
    $dc.Pop(); $dc.Close()
    $bmp = New-Object System.Windows.Media.Imaging.RenderTargetBitmap $size, $size, 96, 96, ([System.Windows.Media.PixelFormats]::Pbgra32)
    $bmp.Render($dv)
    $enc = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
    $enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($bmp))
    $f = [System.IO.File]::Create((Join-Path $out "logo-$size.png"))
    $enc.Save($f); $f.Close()
}

foreach ($s in 16, 20, 24) { Render $s $true }
foreach ($s in 32, 40, 48, 64, 128, 256, 512) { Render $s $false }
Write-Output "已生成 $out\logo-*.png"
