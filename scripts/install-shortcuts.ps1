param([string]$Python = 'C:\AIInference\runtime\chat-venv\Scripts\pythonw.exe', [switch]$Startup)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$shortcutShell = New-Object -ComObject WScript.Shell
$folders = @([Environment]::GetFolderPath('Desktop'))
if ($Startup) { $folders += [Environment]::GetFolderPath('Startup') }
foreach ($folder in $folders) {
    $link = $shortcutShell.CreateShortcut((Join-Path $folder 'Photo Coach.lnk'))
    $link.TargetPath = $Python
    $link.Arguments = '"' + (Join-Path $repoRoot 'chat\run.py') + '"'
    $link.WorkingDirectory = $repoRoot
    $link.Description = 'Start the local AI model, chat website and relay'
    $link.Save()
}
