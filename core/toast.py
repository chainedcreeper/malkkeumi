"""윈도우 토스트 알림 — 자동 청소가 끝났을 때 "말끔이가 1.2GB 비웠어요" 같은 알림.

외부 모듈 없이 PowerShell 의 WinRT 토스트를 빌려 쓴다(Win10/11 기본 탑재).
알림은 부가 기능이라 어떤 이유로든 실패하면 조용히 넘어간다 — 청소를 막으면 안 된다.
"""
import subprocess

_PS = r'''
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml(@"
<toast><visual><binding template="ToastGeneric">
<text>{title}</text><text>{body}</text>
</binding></visual></toast>
"@)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("말끔이").Show(
  (New-Object Windows.UI.Notifications.ToastNotification $x))
'''


def notify(title, body):
    """토스트 띄우기 — XML 특수문자만 피해서 넣는다"""
    def esc(s):
        return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                .replace('"', '&quot;').replace('$', '`$'))
    script = _PS.replace('{title}', esc(title)).replace('{body}', esc(body))
    try:
        subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                       capture_output=True, timeout=20,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return True
    except (OSError, subprocess.SubprocessError):
        return False
