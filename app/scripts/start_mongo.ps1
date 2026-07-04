# Start local MongoDB via Docker (if Docker Desktop is running)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "Starting MongoDB container..."
docker compose -f docker-compose.mongo.yml up -d

Write-Host ""
Write-Host "Local URI: mongodb://127.0.0.1:27017"
Write-Host "In .env set:"
Write-Host "  MONGO_BACKEND=local"
Write-Host "  MONGO_URI=mongodb://127.0.0.1:27017"
Write-Host ""
Write-Host "Test: python -m core.mongo_connect"
