$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigFile = Join-Path $ScriptDir "projects_config.json"
$BaseCompose = Join-Path $ScriptDir "docker-compose.yml"
$VolumesCompose = Join-Path $ScriptDir "docker-compose-volumes.yml"

# 1. Leer projects_config.json
if (Test-Path $ConfigFile) {
    $Config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
    $Projects = $Config.projects
} else {
    $Projects = @()
}

$Volumes = @()
foreach ($p in $Projects) {
    if ($p.host_path) {
        $folderName = Split-Path $p.host_path -Leaf
        $cpath = "/sources/" + $folderName
        $Volumes += "      - $($p.host_path):$($cpath):ro"
    }
}

$VolumesStr = $Volumes -join "`n"

# 2. Generar docker-compose-volumes.yml
$OverrideContent = @"
services:
  context_graph:
    volumes:
$VolumesStr
"@

Set-Content -Path $VolumesCompose -Value $OverrideContent -Encoding UTF8
Write-Host "docker-compose-volumes.yml generado dinamicamente (container_path inferido)." -ForegroundColor Green

# 3. Levantar combinando ambos archivos
docker compose -f $BaseCompose -f $VolumesCompose up -d --build
Write-Host "context_graph listo en http://localhost:8899" -ForegroundColor Cyan
