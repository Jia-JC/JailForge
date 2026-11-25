# Build the JailForge Windows EXE and portable zip.
# Usage (from the project root):
#   powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$python = Join-Path $Root ".venv\Scripts\python.exe"
$pyinstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $python)) { throw "找不到 .venv，请先创建虚拟环境并安装依赖。" }
if (-not (Test-Path $pyinstaller)) { throw "找不到 PyInstaller，请先运行 pip install pyinstaller。" }

$env:PYINSTALLER_CONFIG_DIR = Join-Path $Root ".pyinstaller"
New-Item -ItemType Directory -Force $env:PYINSTALLER_CONFIG_DIR | Out-Null

$web = (Resolve-Path "web").Path
$configs = (Resolve-Path "configs").Path
$data = (Resolve-Path "jailforge\data").Path
$icon = (Resolve-Path "assets\icon.ico").Path
$versionFile = (Resolve-Path "assets\version_info.txt").Path
$entry = (Resolve-Path "launcher.py").Path

$common = @(
    "--noconfirm", "--clean", "--windowed", "--name", "JailForge",
    "--icon", $icon, "--version-file", $versionFile,
    "--add-data", "$web;web",
    "--add-data", "$configs;configs",
    "--add-data", "$data;jailforge/data",
    "--collect-submodules", "jailforge",
    "--hidden-import", "jailforge.judge.llm_judge",
    "--collect-all", "certifi",
    "--collect-submodules", "charset_normalizer",
    "--exclude-module", "gradio",
    "--exclude-module", "pandas",
    "--exclude-module", "matplotlib",
    "--log-level", "WARN",
    $entry
)

Write-Host "[1/4] Building one-file EXE..."
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
& $pyinstaller @common --onefile --distpath "dist" --workpath "build" --specpath "build"
if (-not (Test-Path "dist\JailForge.exe")) { throw "单文件 EXE 构建失败。" }

Write-Host "[2/4] Building portable folder..."
if (Test-Path "dist-portable") { Remove-Item "dist-portable" -Recurse -Force }
if (Test-Path "build-portable") { Remove-Item "build-portable" -Recurse -Force }
& $pyinstaller @common --onedir --distpath "dist-portable" --workpath "build-portable" --specpath "build-portable"

Write-Host "[3/4] Packing release assets..."
New-Item -ItemType Directory -Force "release" | Out-Null
Copy-Item "dist\JailForge.exe" "release\JailForge.exe" -Force
Copy-Item "LICENSE" "dist-portable\JailForge\LICENSE.txt" -Force
Copy-Item (Join-Path $Root "assets\使用说明.txt") "dist-portable\JailForge\使用说明.txt" -Force
if (Test-Path "dist-portable\JailForge\results") { Remove-Item "dist-portable\JailForge\results" -Recurse -Force }
Compress-Archive -Path "dist-portable\JailForge\*" -DestinationPath "release\JailForge-portable-win64.zip" -Force

Write-Host "[4/4] Writing SHA256..."
$hashes = Get-FileHash "release\JailForge.exe", "release\JailForge-portable-win64.zip" -Algorithm SHA256 |
    ForEach-Object { "$($_.Hash.ToLower())  $([System.IO.Path]::GetFileName($_.Path))" }
$hashes | Set-Content "release\SHA256SUMS.txt" -Encoding ascii

Get-ChildItem "release" | Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 2) } }
Write-Host "完成。发布资产在 release/ 目录。"
