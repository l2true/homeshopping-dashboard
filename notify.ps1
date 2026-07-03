Add-Type -AssemblyName System.Windows.Forms

$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Warning
$notify.Visible = $true
$notify.BalloonTipTitle = "AWS 인증 갱신 필요"
$notify.BalloonTipText = "9시 예상취급액 자동 추출이 곧 시작됩니다.`n인증 정보를 Claude에 붙여넣어 주세요!"
$notify.BalloonTipIcon = "Warning"
$notify.ShowBalloonTip(15000)

Start-Sleep -Seconds 16
$notify.Dispose()
