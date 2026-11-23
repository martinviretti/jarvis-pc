<#
.SYNOPSIS
  Instala o actualiza Jarvis PC sin permisos de administrador.

.DESCRIPTION
  - Instala uv (gestor de Python) en el usuario, si no está.
  - Copia Jarvis a %LOCALAPPDATA%\JarvisPC\app y crea su propio Python 3.12 aislado.
  - Descarga los modelos (~800 MB, una sola vez).
  - Crea accesos directos: inicio de Windows, escritorio y menú Inicio.
  - La primera vez abre la configuración (micrófono, tecla, Hey Jarvis, luz y Google).

  Uso, desde internet (repo público):
    irm https://raw.githubusercontent.com/martinviretti/jarvis-pc/main/instalar.ps1 | iex

  Uso, desde una carpeta descargada (repo privado o sin internet a GitHub):
    powershell -ExecutionPolicy Bypass -File .\instalar.ps1
#>
param(
    [switch]$Actualizar,
    [switch]$Prueba,          # para desarrollo: no crea accesos directos ni arranca Jarvis
    [string]$Repo = "martinviretti/jarvis-pc",
    [string]$Rama = "main"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest es mucho más rápido sin barra

$Base    = if ($env:JARVIS_HOME) { $env:JARVIS_HOME } else { Join-Path $env:LOCALAPPDATA "JarvisPC" }
$App     = Join-Path $Base "app"
$Venv    = Join-Path $Base ".venv"
$Datos   = Join-Path $Base "datos"
$Py      = Join-Path $Venv "Scripts\python.exe"
$PyW     = Join-Path $Venv "Scripts\pythonw.exe"

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }

Write-Host "Jarvis PC - instalador" -ForegroundColor Green
New-Item -ItemType Directory -Force -Path $Base, $Datos | Out-Null

# 1. Cerrar Jarvis si está abierto (para actualizar)
Paso "Cerrando Jarvis si estaba abierto"
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*jarvis*" -and $_.ExecutablePath -like "$Venv*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# 2. uv
Paso "Preparando Python (uv)"
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
uv --version

# 3. Código: desde esta carpeta si el script se corrió desde el repo descargado, o desde GitHub
Paso "Copiando Jarvis"
$origen = $null
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "pyproject.toml")) -and ($PSScriptRoot -ne $App)) {
    $origen = $PSScriptRoot
    Write-Host "Usando la carpeta $origen"
} else {
    $tmp = Join-Path $env:TEMP ("jarvis-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    $zip = Join-Path $tmp "jarvis.zip"
    $url = "https://github.com/$Repo/archive/refs/heads/$Rama.zip"
    Write-Host "Descargando $url"
    Invoke-WebRequest $url -OutFile $zip
    Expand-Archive $zip -DestinationPath $tmp -Force
    $origen = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
}
if (Test-Path $App) { Remove-Item $App -Recurse -Force }
New-Item -ItemType Directory -Force -Path $App | Out-Null
Copy-Item -Path (Join-Path $origen "*") -Destination $App -Recurse -Force -Exclude ".venv", "_dev", ".git"
Copy-Item -Path (Join-Path $App "instalar.ps1") -Destination (Join-Path $Base "instalar.ps1") -Force

# 4. Entorno de Python propio
Paso "Instalando dependencias (la primera vez tarda unos minutos)"
if (-not (Test-Path $Py)) { uv venv --python 3.12 $Venv }
uv pip install --python $Py $App
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias." }

# 5. Modelos
Paso "Descargando modelos (voz, Hey Jarvis y Parakeet; ~800 MB la primera vez)"
& $Py -m jarvis.setup_models
if ($LASTEXITCODE -ne 0) { throw "Falló la descarga de modelos. Revisá la conexión y corré el instalador de nuevo." }

if ($Prueba) { Write-Host "Modo prueba: instalado en $Base (sin accesos directos)." -ForegroundColor Green; return }

# 6. Accesos directos
Paso "Creando accesos directos"
$shell = New-Object -ComObject WScript.Shell
function Acceso($ruta, $destino, $argumentos, $descripcion) {
    $lnk = $shell.CreateShortcut($ruta)
    $lnk.TargetPath = $destino
    $lnk.Arguments = $argumentos
    $lnk.WorkingDirectory = $Base
    $lnk.Description = $descripcion
    $lnk.Save()
}
$inicio   = [Environment]::GetFolderPath("Startup")
$escrit   = [Environment]::GetFolderPath("Desktop")
$menu     = Join-Path ([Environment]::GetFolderPath("Programs")) "Jarvis"
New-Item -ItemType Directory -Force -Path $menu | Out-Null
Acceso (Join-Path $inicio "Jarvis.lnk") $PyW "-m jarvis" "Jarvis, asistente de voz"
Acceso (Join-Path $escrit "Jarvis.lnk") $PyW "-m jarvis" "Jarvis, asistente de voz"
Acceso (Join-Path $menu "Jarvis.lnk") $PyW "-m jarvis" "Jarvis, asistente de voz"
Acceso (Join-Path $menu "Configurar Jarvis.lnk") $Py "-m jarvis.configurar" "Micrófono, tecla, luz y Google"
Acceso (Join-Path $menu "Conectar Google.lnk") $Py "-m jarvis.configurar --google" "Calendario y tareas de Google"
Acceso (Join-Path $menu "Calibrar Hey Jarvis.lnk") $Py "-m jarvis.configurar --calibrar" "Ajustar Hey Jarvis a tu voz"
Acceso (Join-Path $menu "Desinstalar Jarvis.lnk") "powershell.exe" "-NoProfile -ExecutionPolicy Bypass -File `"$App\desinstalar.ps1`"" "Quitar Jarvis"

# 7. Configuración inicial (solo la primera vez)
if (-not (Test-Path (Join-Path $Datos "config.yaml")) -and -not $Actualizar) {
    Paso "Configuración inicial"
    & $Py -m jarvis.configurar
}

# 8. Arrancar
Paso "Arrancando Jarvis"
Start-Process $PyW -ArgumentList "-m", "jarvis" -WorkingDirectory $Base
Write-Host ""
Write-Host "Listo. Jarvis quedó en la bandeja (al lado del reloj) y arranca solo con Windows." -ForegroundColor Green
Write-Host "Decí 'Hey Jarvis' o mantené apretada la tecla para hablar. Probá: 'qué podés hacer'."
