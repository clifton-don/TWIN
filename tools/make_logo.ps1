# 生成 TWIN 的 logo 图片（开发用，改了 logo 才需要跑一次）：
#   powershell -ExecutionPolicy Bypass -File tools\make_logo.ps1
# 用 WPF 按和 docs\logo.svg 一样的路径画，输出 tools\web\logo-{尺寸}.png 和手机主屏用的 apple-touch-icon.png，再由 tools\make_ico.py 拼成 logo.ico。
# 24 像素以下 T 用加粗版，托盘里才看得清。
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
$out = Join-Path $PSScriptRoot 'web'

function Brush($hex) { (New-Object System.Windows.Media.BrushConverter).ConvertFromString($hex) }

function Render($size, $small, $name) {
    $dv = New-Object System.Windows.Media.DrawingVisual
    $dc = $dv.RenderOpen()
    $k = $size / 64.0
    # 手机主屏图标（apple-touch-icon）：系统自己裁圆角，透明处会变黑，所以铺白底，图案缩小一点留边
    if ($name) {
        $dc.DrawRectangle((Brush '#FFFFFF'), $null, (New-Object System.Windows.Rect 0, 0, $size, $size))
        $dc.PushTransform((New-Object System.Windows.Media.TranslateTransform ($size * 0.1), ($size * 0.1)))
        $k = $k * 0.8
    }
    $dc.PushTransform((New-Object System.Windows.Media.ScaleTransform $k, $k))
    # 原件与副本：后面青色的卡是副本，前面紫色的卡是你，叠在一起的地方颜色更深，中间一个 T
    $back = New-Object System.Windows.Media.RectangleGeometry (New-Object System.Windows.Rect 18, 8, 36, 42), 9, 9
    $front = New-Object System.Windows.Media.RectangleGeometry (New-Object System.Windows.Rect 10, 16, 36, 42), 9, 9
    $overlap = New-Object System.Windows.Media.CombinedGeometry ([System.Windows.Media.GeometryCombineMode]::Intersect), $back, $front
    $dc.DrawGeometry((Brush '#55C2B8'), $null, $back)
    $dc.DrawGeometry((Brush '#7F6FE0'), $null, $front)
    $dc.DrawGeometry((Brush '#5B4CC4'), $null, $overlap)
    # 24 像素以下 T 加粗，托盘里才看得清
    $t = if ($small) { 'M16 25h24v8h-8v17h-8V33h-8z' } else { 'M18 26h20v6h-7v18h-6V32h-7z' }
    $dc.DrawGeometry((Brush '#FFFFFF'), $null, [System.Windows.Media.Geometry]::Parse($t))
    $dc.Pop(); if ($name) { $dc.Pop() }; $dc.Close()
    $bmp = New-Object System.Windows.Media.Imaging.RenderTargetBitmap $size, $size, 96, 96, ([System.Windows.Media.PixelFormats]::Pbgra32)
    $bmp.Render($dv)
    $enc = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
    $enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($bmp))
    $f = [System.IO.File]::Create((Join-Path $out $(if ($name) { $name } else { "logo-$size.png" })))
    $enc.Save($f); $f.Close()
}

foreach ($s in 16, 20, 24) { Render $s $true }
foreach ($s in 32, 40, 48, 64, 128, 256, 512) { Render $s $false }
Render 180 $false 'apple-touch-icon.png'
Write-Output "已生成 $out\logo-*.png"
