# TWIN 启动器的界面：圆角弹窗、下载进度窗、托盘右键菜单（WPF，Windows 自带，不用装东西）。
# 由 launch.ps1 点进来（dot-source）。跟随 Windows 的深色 / 浅色模式。
# 注意：这个文件里的中文提示别用弯引号（PowerShell 会把它当成字符串的引号）。
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Xaml

$script:UiDir = $PSScriptRoot
$script:Dark = $true
try {
    $v = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize' -ErrorAction Stop).AppsUseLightTheme
    $script:Dark = ($v -eq 0)
} catch { }

$script:Theme = if ($script:Dark) {
    @{ Bg = '#2B2A33'; Fg = '#F2F1F7'; Sub = '#B4B1C4'; Line = '#3E3C4A'; Hover = '#3A3846'; Btn2 = '#3A3846'; Btn2Fg = '#F2F1F7'; Track = '#3E3C4A' }
} else {
    @{ Bg = '#FFFFFF'; Fg = '#1F1D2B'; Sub = '#6B6880'; Line = '#E7E5EF'; Hover = '#F1EFF8'; Btn2 = '#F1EFF8'; Btn2Fg = '#1F1D2B'; Track = '#E7E5EF' }
}
$script:Accent = '#7F6FE0'

function script:Xaml($text) {
    $t = $script:Theme
    foreach ($k in $t.Keys) { $text = $text.Replace("{{$k}}", $t[$k]) }
    $text = $text.Replace('{{Accent}}', $script:Accent)
    return [Windows.Markup.XamlReader]::Parse($text)
}

function script:LogoSource {
    $png = Join-Path $script:UiDir 'web\logo-64.png'
    if (Test-Path $png) {
        $img = New-Object System.Windows.Media.Imaging.BitmapImage
        $img.BeginInit(); $img.UriSource = New-Object Uri $png; $img.CacheOption = 'OnLoad'; $img.EndInit()
        return $img
    }
    return $null
}

# 卡片外框：圆角、阴影、可拖动
$script:CardHead = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        WindowStyle="None" AllowsTransparency="True" Background="Transparent" ResizeMode="NoResize"
        SizeToContent="WidthAndHeight" WindowStartupLocation="CenterScreen" Topmost="True" ShowInTaskbar="True"
        Title="TWIN" FontFamily="Microsoft YaHei UI, Segoe UI" FontSize="14">
  <Window.Resources>
    <Style x:Key="Btn" TargetType="Button">
      <Setter Property="Foreground" Value="{{Btn2Fg}}"/>
      <Setter Property="Background" Value="{{Btn2}}"/>
      <Setter Property="Padding" Value="18,8"/>
      <Setter Property="Margin" Value="8,0,0,0"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" Background="{TemplateBinding Background}" CornerRadius="8" Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Opacity" Value="0.85"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
  </Window.Resources>
  <Border Margin="16" Background="{{Bg}}" CornerRadius="14" BorderBrush="{{Line}}" BorderThickness="1">
    <Border.Effect><DropShadowEffect BlurRadius="24" ShadowDepth="4" Opacity="0.35" Color="#000000"/></Border.Effect>
'@

# 弹窗：$buttons 是按钮文字数组，第一个是主按钮。返回点了第几个（0 开始），Esc 或关闭返回最后一个
function Show-TwinDialog($title, $message, [string[]]$buttons = @('好的'), [switch]$Warn) {
    $icon = if ($Warn) { '&#xE7BA;' } else { '' }
    $xaml = $script:CardHead + @'
    <StackPanel Margin="24,22,24,20" Width="400">
      <StackPanel Orientation="Horizontal" Margin="0,0,0,12">
        <Image x:Name="Logo" Width="28" Height="28" Margin="0,0,10,0" VerticalAlignment="Center"/>
        <TextBlock x:Name="Warn" FontFamily="Segoe MDL2 Assets" FontSize="18" Foreground="#E0A030" VerticalAlignment="Center" Margin="0,0,8,0"/>
        <TextBlock x:Name="Head" FontSize="17" FontWeight="SemiBold" Foreground="{{Fg}}" VerticalAlignment="Center" TextWrapping="Wrap" MaxWidth="340"/>
      </StackPanel>
      <TextBlock x:Name="Body" Foreground="{{Sub}}" TextWrapping="Wrap" LineHeight="22"/>
      <StackPanel x:Name="Btns" Orientation="Horizontal" HorizontalAlignment="Right" Margin="0,20,0,0"/>
    </StackPanel>
  </Border>
</Window>
'@
    $w = Xaml $xaml
    $logo = LogoSource
    $w.FindName('Logo').Source = $logo
    if (-not $logo) { $w.FindName('Logo').Visibility = 'Collapsed' }
    $w.FindName('Warn').Text = [System.Net.WebUtility]::HtmlDecode($icon)
    $w.FindName('Head').Text = $title
    $w.FindName('Body').Text = $message
    $state = @{ choice = $buttons.Count - 1 }  # 闭包里改哈希表的内容，外面才看得到
    $panel = $w.FindName('Btns')
    # 主按钮放最右边
    for ($i = $buttons.Count - 1; $i -ge 0; $i--) {
        $b = New-Object System.Windows.Controls.Button
        $b.Content = $buttons[$i]
        $b.Style = $w.FindResource('Btn')
        $b.Tag = $i
        if ($i -eq 0) {
            $b.Background = (New-Object System.Windows.Media.BrushConverter).ConvertFromString($script:Accent)
            $b.Foreground = [System.Windows.Media.Brushes]::White
            $b.IsDefault = $true
        }
        if ($i -eq $buttons.Count - 1 -and $buttons.Count -gt 1) { $b.IsCancel = $true }
        $b.Add_Click({ param($s) $state.choice = [int]$s.Tag; [System.Windows.Window]::GetWindow($s).Close() }.GetNewClosure())
        $panel.Children.Add($b) | Out-Null
    }
    $w.Add_MouseLeftButtonDown({ try { $this.DragMove() } catch { } })
    $w.Add_KeyDown({ param($s, $e) if ($e.Key -eq 'Escape') { $s.Close() } })
    $w.ShowDialog() | Out-Null
    return $state.choice
}

# 后台跑 $work（scriptblock，参数 $argList），同时显示进度窗；$watch 文件长到 $total 字节时进度满
# 返回 $work 的输出；出错时抛出
function Invoke-TwinProgress($title, $work, $argList, $watch, $total) {
    $xaml = $script:CardHead + @'
    <StackPanel Margin="24,22,24,22" Width="380">
      <StackPanel Orientation="Horizontal" Margin="0,0,0,14">
        <Image x:Name="Logo" Width="28" Height="28" Margin="0,0,10,0" VerticalAlignment="Center"/>
        <TextBlock x:Name="Head" FontSize="16" FontWeight="SemiBold" Foreground="{{Fg}}" VerticalAlignment="Center"/>
      </StackPanel>
      <Border Height="6" CornerRadius="3" Background="{{Track}}">
        <Border x:Name="Bar" Height="6" CornerRadius="3" Background="{{Accent}}" HorizontalAlignment="Left" Width="0"/>
      </Border>
      <TextBlock x:Name="Info" Foreground="{{Sub}}" FontSize="12.5" Margin="0,10,0,0"/>
    </StackPanel>
  </Border>
</Window>
'@
    $w = Xaml $xaml
    $logo = LogoSource
    $w.FindName('Logo').Source = $logo
    if (-not $logo) { $w.FindName('Logo').Visibility = 'Collapsed' }
    $w.FindName('Head').Text = $title
    $bar = $w.FindName('Bar'); $info = $w.FindName('Info')
    $info.Text = '正在连接……'

    $ps = [powershell]::Create()
    $null = $ps.AddScript($work)
    foreach ($a in $argList) { $null = $ps.AddArgument($a) }
    $handle = $ps.BeginInvoke()
    $state = @{ result = $null; error = $null }

    $timer = New-Object System.Windows.Threading.DispatcherTimer
    $timer.Interval = [TimeSpan]::FromMilliseconds(200)
    $timer.Add_Tick({
        if ($handle.IsCompleted) {
            $timer.Stop()
            try { $state.result = $ps.EndInvoke($handle) } catch { $state.error = $_.Exception.InnerException }
            if (-not $state.error -and $ps.Streams.Error.Count) { $state.error = $ps.Streams.Error[0].Exception }
            $w.Close()
            return
        }
        if ($watch -and (Test-Path $watch)) {
            $got = (Get-Item $watch).Length
            $pct = [Math]::Min(1.0, $got / [double]$total)
            $bar.Width = 380 * $pct  # 和外面的 StackPanel 一样宽
            $info.Text = ('{0:N1} / {1:N1} MB · {2:P0}' -f ($got / 1MB), ($total / 1MB), $pct)
            if ($got -ge $total) { $info.Text = '正在核对校验值、解压……' }
        }
    }.GetNewClosure())
    $timer.Start()
    $w.Add_MouseLeftButtonDown({ try { $this.DragMove() } catch { } })
    $w.ShowDialog() | Out-Null
    $ps.Dispose()
    if ($state.error) { throw $state.error }
    return $state.result
}

# 托盘右键菜单：$items 是 @(@{ Icon = 'E8A7'; Text = '打开 TWIN'; Do = { ... } }, '-', ...)
function Show-TwinMenu($title, $subtitle, $items) {
    $xaml = $script:CardHead.Replace('WindowStartupLocation="CenterScreen"', 'WindowStartupLocation="Manual"').Replace('ShowInTaskbar="True"', 'ShowInTaskbar="False"') + @'
    <StackPanel Margin="6" Width="250">
      <StackPanel Orientation="Horizontal" Margin="10,10,10,8">
        <Image x:Name="Logo" Width="30" Height="30" Margin="0,0,10,0" VerticalAlignment="Center"/>
        <StackPanel VerticalAlignment="Center">
          <TextBlock x:Name="Head" FontSize="14.5" FontWeight="SemiBold" Foreground="{{Fg}}"/>
          <TextBlock x:Name="Sub" FontSize="12" Foreground="{{Sub}}"/>
        </StackPanel>
      </StackPanel>
      <Border Height="1" Background="{{Line}}" Margin="6,2,6,4"/>
      <StackPanel x:Name="Items"/>
    </StackPanel>
  </Border>
</Window>
'@
    $w = Xaml $xaml
    $logo = LogoSource
    $w.FindName('Logo').Source = $logo
    if (-not $logo) { $w.FindName('Logo').Visibility = 'Collapsed' }
    $w.FindName('Head').Text = $title
    $w.FindName('Sub').Text = $subtitle
    $list = $w.FindName('Items')
    $conv = New-Object System.Windows.Media.BrushConverter
    # 关窗只关一次：点菜单项关窗时会触发失去焦点，再关一次 WPF 会报错、把整个托盘程序带崩
    $menu = @{ closing = $false }
    $w.Add_Closing({ $menu.closing = $true }.GetNewClosure())
    foreach ($it in $items) {
        if ($it -eq '-') {
            $sep = New-Object System.Windows.Controls.Border
            $sep.Height = 1; $sep.Margin = '6,4,6,4'; $sep.Background = $conv.ConvertFromString($script:Theme.Line)
            $list.Children.Add($sep) | Out-Null
            continue
        }
        $row = New-Object System.Windows.Controls.Border
        $row.CornerRadius = 8; $row.Padding = '10,8,10,8'; $row.Cursor = 'Hand'; $row.Background = [System.Windows.Media.Brushes]::Transparent
        $sp = New-Object System.Windows.Controls.StackPanel; $sp.Orientation = 'Horizontal'
        $ic = New-Object System.Windows.Controls.TextBlock
        $ic.FontFamily = 'Segoe MDL2 Assets'; $ic.FontSize = 15; $ic.Width = 26; $ic.VerticalAlignment = 'Center'
        $ic.Text = [string][char][Convert]::ToInt32($it.Icon, 16)
        $ic.Foreground = $conv.ConvertFromString($(if ($it.Danger) { '#E5484D' } else { $script:Theme.Sub }))
        $tx = New-Object System.Windows.Controls.TextBlock
        $tx.Text = $it.Text; $tx.VerticalAlignment = 'Center'
        $tx.Foreground = $conv.ConvertFromString($(if ($it.Danger) { '#E5484D' } else { $script:Theme.Fg }))
        $sp.Children.Add($ic) | Out-Null; $sp.Children.Add($tx) | Out-Null
        $row.Child = $sp
        $hover = $conv.ConvertFromString($script:Theme.Hover)
        $row.Add_MouseEnter({ $this.Background = $hover }.GetNewClosure())
        $row.Add_MouseLeave({ $this.Background = [System.Windows.Media.Brushes]::Transparent })
        $action = $it.Do
        $row.Add_MouseLeftButtonUp({ if (-not $menu.closing) { $w.Close() }; & $action }.GetNewClosure())
        $list.Children.Add($row) | Out-Null
    }
    $w.Add_Deactivated({ if (-not $menu.closing) { $w.Close() } }.GetNewClosure())
    $w.Add_KeyDown({ if ($_.Key -eq 'Escape' -and -not $menu.closing) { $w.Close() } }.GetNewClosure())
    # 放在鼠标左上方（托盘一般在右下角），屏幕坐标要换算成 WPF 的逻辑单位
    $w.Add_SourceInitialized({
        $m = [System.Windows.PresentationSource]::FromVisual($this).CompositionTarget.TransformFromDevice
        $p = $m.Transform((New-Object System.Windows.Point ([System.Windows.Forms.Cursor]::Position.X), ([System.Windows.Forms.Cursor]::Position.Y)))
        $wa = [System.Windows.SystemParameters]::WorkArea
        $this.Left = [Math]::Max($wa.Left, [Math]::Min($p.X - $this.ActualWidth + 16, $wa.Right - $this.ActualWidth))
        $this.Top = [Math]::Max($wa.Top, [Math]::Min($p.Y - $this.ActualHeight + 16, $wa.Bottom - $this.ActualHeight))
    })
    $w.Add_ContentRendered({
        $wa = [System.Windows.SystemParameters]::WorkArea
        $m = [System.Windows.PresentationSource]::FromVisual($this).CompositionTarget.TransformFromDevice
        $p = $m.Transform((New-Object System.Windows.Point ([System.Windows.Forms.Cursor]::Position.X), ([System.Windows.Forms.Cursor]::Position.Y)))
        $this.Left = [Math]::Max($wa.Left, [Math]::Min($p.X - $this.ActualWidth + 16, $wa.Right - $this.ActualWidth))
        $this.Top = [Math]::Max($wa.Top, [Math]::Min($p.Y - $this.ActualHeight + 16, $wa.Bottom - $this.ActualHeight))
        $this.Activate() | Out-Null
    })
    $w.Show()
}
