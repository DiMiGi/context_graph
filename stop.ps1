$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseCompose = Join-Path $ScriptDir "docker-compose.yml"
$VolumesCompose = Join-Path $ScriptDir "docker-compose-volumes.yml"

Write-Host "Deteniendo local_graphs..." -ForegroundColor Yellow

if (Test-Path $VolumesCompose) {
    docker compose -f $BaseCompose -f $VolumesCompose down
} else {
    docker compose -f $BaseCompose down
}

Write-Host "local_graphs detenido correctamente." -ForegroundColor Green
