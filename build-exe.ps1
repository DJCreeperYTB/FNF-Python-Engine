$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectDirectory

if (-not (Test-Path -LiteralPath ".\fnf_assets\data\songs")) {
  throw "Le dossier fnf_assets est absent. Les assets FNF doivent être extraits avant la compilation."
}

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name "FNF Python" `
  --add-data "fnf_assets;fnf_assets" `
  --hidden-import av `
  main.py

# Le dossier mods/ (mod d'exemple + guide PDF) se trouve à côté de l'exe.
$distMods = ".\dist\FNF Python\mods"
New-Item -ItemType Directory -Force -Path $distMods | Out-Null
Copy-Item -LiteralPath ".\mods\ExampleMod.zip" -Destination $distMods -Force
Copy-Item -LiteralPath ".\mods\Guide de modding - Python Engine.pdf" -Destination $distMods -Force
Copy-Item -LiteralPath ".\mods\Modding Guide - Python Engine.pdf" -Destination $distMods -Force
Copy-Item -LiteralPath ".\mods\guide_pages_fr.json", ".\mods\guide_pages_en.json" -Destination $distMods -Force

Write-Host ""
Write-Host "Build Python créé : dist\FNF Python\FNF Python.exe" -ForegroundColor Green
