param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsFromUser
)

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "Virtual environment not found at .venv." -ForegroundColor Red
    Write-Host "Create it first:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

& $pythonExe (Join-Path $PSScriptRoot "main.py") @ArgsFromUser
exit $LASTEXITCODE
