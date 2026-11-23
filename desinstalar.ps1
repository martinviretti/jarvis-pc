<#
.SYNOPSIS
  Quita Jarvis PC. Pregunta si conservar la configuración y el historial.
#>
$ErrorActionPreference = "Continue"
$Base = Join-Path $env:LOCALAPPDATA "JarvisPC"
$Venv = Join-Path $Base ".venv"

Write-Host "Desinstalando Jarvis..." -ForegroundColor Yellow
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*jarvis*" -and $_.ExecutablePath -like "$Venv*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

$accesos = @(
    (Join-Path ([Environment]::GetFolderPath("Startup")) "Jarvis.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Jarvis.lnk")
)
$accesos | ForEach-Object { if (Test-Path $_) { Remove-Item $_ -Force } }
$menu = Join-Path ([Environment]::GetFolderPath("Programs")) "Jarvis"
if (Test-Path $menu) { Remove-Item $menu -Recurse -Force }

$conservar = Read-Host "¿Conservar la configuración, el historial y la conexión con Google? (S/n)"
foreach ($sub in @("app", ".venv", "modelos", "instalar.ps1")) {
    $ruta = Join-Path $Base $sub
    if (Test-Path $ruta) { Remove-Item $ruta -Recurse -Force }
}
if ($conservar -match "^[nN]") {
    if (Test-Path $Base) { Remove-Item $Base -Recurse -Force }
    Write-Host "Jarvis quedó completamente borrado."
} else {
    Write-Host "Jarvis quedó desinstalado. Tus datos siguen en $Base\datos"
}
Read-Host "Apretá Enter para cerrar"
