param([string]$Python = 'C:\AIInference\runtime\chat-venv\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
& $Python (Join-Path $repoRoot 'chat\setup.py')
if ($LASTEXITCODE -ne 0) { throw 'Settings initialization failed' }
$pythonWindowless = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
Start-Process -FilePath $pythonWindowless -ArgumentList @('"' + (Join-Path $repoRoot 'chat\run.py') + '"') -WindowStyle Hidden
