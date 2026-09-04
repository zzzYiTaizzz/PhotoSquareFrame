# Builds the Windows distribution of PhotoSquareFrame.
#
# Produces dist\PhotoSquareFrame\ and a versioned zipped release archive,
# then copies the zip to the Desktop.
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
$AppVersion = (& $Python -c "from version import APP_VERSION; print(APP_VERSION)").Trim()

# Remove stale outputs so the bundle never inherits leftover files.
foreach ($Dir in @("build", "dist")) {
    $Path = Join-Path $PSScriptRoot $Dir
    if (Test-Path $Path) { Remove-Item -Recurse -Force $Path }
}

$GeneratedVersionFile = Join-Path $PSScriptRoot "build\version_info.generated.txt"
$VersionTemplate = Get-Content (Join-Path $PSScriptRoot "assets\version_info.txt") -Raw
$VersionParts = $AppVersion.Split('.')
while ($VersionParts.Count -lt 4) { $VersionParts += "0" }
$FileVersion = "({0})" -f ($VersionParts[0..3] -join ', ')
$VersionTemplate.Replace("__VERSION__", $AppVersion).Replace("__FILE_VERSION__", $FileVersion) |
    Set-Content -Path $GeneratedVersionFile -Encoding utf8

# 1) Bundle with PyInstaller (onedir, windowed). Flags mirror build_dmg.sh.
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name PhotoSquareFrame `
    --icon (Join-Path $PSScriptRoot "assets\app_icon.ico") `
    --version-file $GeneratedVersionFile `
    main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 2) Include license notices in the distributable bundle.
$Bundle = Join-Path $PSScriptRoot "dist\PhotoSquareFrame"
Copy-Item (Join-Path $PSScriptRoot "LICENSE") (Join-Path $Bundle "LICENSE.txt")
Copy-Item (Join-Path $PSScriptRoot "THIRD_PARTY_LICENSES.md") (Join-Path $Bundle "THIRD_PARTY_LICENSES.txt")
Copy-Item -Recurse (Join-Path $PSScriptRoot "licenses") (Join-Path $Bundle "licenses")

# 3) Zip the bundle into a distributable archive.
& $Python -c "import shutil; shutil.make_archive(r'$PSScriptRoot\dist\PhotoSquareFrame-Windows-x64-v$AppVersion', 'zip', r'$PSScriptRoot\dist', 'PhotoSquareFrame')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 4) Copy the zip to the Desktop for convenience.
$Zip = Join-Path $PSScriptRoot "dist\PhotoSquareFrame-Windows-x64-v$AppVersion.zip"
$Desktop = [Environment]::GetFolderPath("Desktop")
$DesktopZip = Join-Path $Desktop "PhotoSquareFrame-Windows-x64-v$AppVersion.zip"
Copy-Item -Force $Zip $DesktopZip

Write-Host ""
Write-Host "Created:  $Zip"
Write-Host "Desktop:  $DesktopZip"
