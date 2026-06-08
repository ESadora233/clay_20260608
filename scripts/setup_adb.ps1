# 下载 Android Platform Tools 到 tools/platform-tools/
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root "tools\platform-tools"
$zip = Join-Path $env:TEMP "platform-tools-latest-windows.zip"
$url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"

Write-Host "下载 Platform Tools..."
Invoke-WebRequest -Uri $url -OutFile $zip

Write-Host "解压到 $dest ..."
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
Expand-Archive -Path $zip -DestinationPath (Join-Path $root "tools") -Force
Remove-Item $zip -Force

$adb = Join-Path $dest "adb.exe"
if (-not (Test-Path $adb)) {
    throw "解压失败，未找到 adb.exe"
}

Write-Host "完成: $adb"
Write-Host "可执行: python main.py doctor"
