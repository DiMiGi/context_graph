$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseCompose = Join-Path $ScriptDir "docker-compose.yml"
$VolumesCompose = Join-Path $ScriptDir "docker-compose-volumes.yml"

Write-Host "Deteniendo context_graph..." -ForegroundColor Yellow

if (Test-Path $VolumesCompose) {
    docker compose -f $BaseCompose -f $VolumesCompose down
} else {
    docker compose -f $BaseCompose down
}

Write-Host "context_graph detenido correctamente." -ForegroundColor Green
