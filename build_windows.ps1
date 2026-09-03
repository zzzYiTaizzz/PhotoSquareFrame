# Builds the Windows distribution of PhotoSquareFrame.
#
# Produces dist\PhotoSquareFrame\ and a zipped release archive at
# dist\PhotoSquareFrame-Windows-x64.zip, then copies the zip to the Desktop.
#
# Usage (from PowerShell, repository root):
#   .\build_windows.ps1
#
# First-time bootstrap:
#   py -m venv .venv
#   .\.venv\Scripts\python.exe -m pip install -r requirements.txt

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Locate the venv interpreter (mirrors the macOS build script, which uses .venv).
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Virtual environment not found. Run the bootstrap commands:" -ForegroundColor Yellow
    Write-Host "  py -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

# Verify the venv has the runtime/build packages.
& $Python -c "import PIL, PySide6, PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dependencies missing. Install with:" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

# Remove stale outputs so the bundle never inherits leftover files.
foreach ($Dir in @("build", "dist")) {
    $Path = Join-Path $PSScriptRoot $Dir
    if (Test-Path $Path) { Remove-Item -Recurse -Force $Path }
}

# 1) Bundle with PyInstaller (onedir, windowed). Flags mirror build_dmg.sh.
& $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name PhotoSquareFrame main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 2) Zip the bundle into a distributable archive.
& $Python -c "import shutil; shutil.make_archive(r'$PSScriptRoot\dist\PhotoSquareFrame-Windows-x64', 'zip', r'$PSScriptRoot\dist', 'PhotoSquareFrame')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 3) Copy the zip to the Desktop for convenience.
$Zip = Join-Path $PSScriptRoot "dist\PhotoSquareFrame-Windows-x64.zip"
$Desktop = [Environment]::GetFolderPath("Desktop")
Copy-Item -Force $Zip (Join-Path $Desktop "PhotoSquareFrame-Windows-x64.zip")

Write-Host ""
Write-Host "Created:  $Zip"
Write-Host "Desktop:  $(Join-Path $Desktop 'PhotoSquareFrame-Windows-x64.zip')"
