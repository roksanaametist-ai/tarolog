#Requires -Version 5.1
<#
.SYNOPSIS
  Деплой TarGPT3 на HSHP VPS по SSH.
.EXAMPLE
  .\deploy\hshp\deploy-remote.ps1 -Host 37.46.18.192 -User root
#>
param(
    [string]$Host = "37.46.18.192",
    [string]$User = "root",
    [string]$AppDir = "/opt/targpt",
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path (Join-Path $Root $EnvFile))) {
    Write-Error "Не найден $EnvFile в $Root — нужен файл с секретами."
}

$target = "${User}@${Host}"
Write-Host "==> Копируем .env на сервер ($target)..."
scp (Join-Path $Root $EnvFile) "${target}:${AppDir}/.env"

Write-Host "==> Запуск install.sh на сервере..."
ssh $target "chmod 600 ${AppDir}/.env; sudo bash ${AppDir}/deploy/hshp/install.sh"

Write-Host "==> Проверка..."
ssh $target "curl -sf http://127.0.0.1:5000/health; systemctl is-active targpt-bot targpt-landing"

Write-Host "Готово. Откройте https://followthefrensy.ru/"
