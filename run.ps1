<#
.SYNOPSIS
    OpsPortal launcher for Windows PowerShell.

.DESCRIPTION
    One command to start, stop and manage the stack without needing `make`.

.EXAMPLE
    .\run.ps1              # build + start everything (default)
.EXAMPLE
    .\run.ps1 logs         # tail the logs
.EXAMPLE
    .\run.ps1 reseed       # wipe and re-seed the demo data
#>
[CmdletBinding()]
param(
    [ValidateSet('up', 'down', 'restart', 'logs', 'ps', 'build', 'rebuild',
                 'shell', 'dbshell', 'test', 'seed', 'reseed', 'superuser',
                 'migrate', 'nuke', 'help')]
    [string]$Command = 'up'
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Assert-Docker {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($null -eq $docker) {
        Write-Host "Docker was not found on PATH." -ForegroundColor Red
        Write-Host "Install Docker Desktop and make sure the WSL 2 backend is enabled."
        exit 1
    }
    try { docker info | Out-Null } catch {
        Write-Host "Docker is installed but not running. Start Docker Desktop and try again." -ForegroundColor Red
        exit 1
    }
}

function Show-Banner {
    Write-Host ""
    Write-Host "  OpsPortal - Mini ERP + CRM Operations Portal" -ForegroundColor Cyan
    Write-Host "  --------------------------------------------"
    Write-Host "  App .............. http://localhost:8080"
    Write-Host "  Django auth ...... http://localhost:8080/accounts/login/"
    Write-Host "  Django admin ..... http://localhost:8080/admin/"
    Write-Host "  API docs ......... http://localhost:8080/api/docs/"
    Write-Host ""
    Write-Host "  Logins:  admin / Admin@12345          (Admin)"
    Write-Host "           sales / Sales@12345          (Sales)"
    Write-Host "           warehouse / Warehouse@12345  (Warehouse)"
    Write-Host "           accounts / Accounts@12345    (Accounts)"
    Write-Host ""
}

switch ($Command) {
    'help' {
        Write-Host "Usage: .\run.ps1 [command]"
        Write-Host ""
        Write-Host "  up         Build and start the whole stack (default)"
        Write-Host "  down       Stop the stack, keeping the database"
        Write-Host "  restart    Restart every service"
        Write-Host "  logs       Tail the logs"
        Write-Host "  ps         Show container status"
        Write-Host "  build      Build the images"
        Write-Host "  rebuild    Rebuild ignoring the cache"
        Write-Host "  shell      Shell into the backend container"
        Write-Host "  dbshell    psql into the database"
        Write-Host "  migrate    Apply migrations"
        Write-Host "  seed       Seed demo data"
        Write-Host "  reseed     Wipe and re-seed demo data"
        Write-Host "  superuser  Create a Django superuser"
        Write-Host "  test       Run the backend test suite"
        Write-Host "  nuke       Stop and DELETE the database volume"
        break
    }
    'up' {
        Assert-Docker
        Show-Banner
        Write-Host "Building and starting... (first run pulls images, give it a few minutes)" -ForegroundColor Yellow
        docker compose up --build
        break
    }
    'down'      { Assert-Docker; docker compose down; break }
    'restart'   { Assert-Docker; docker compose restart; break }
    'logs'      { Assert-Docker; docker compose logs -f; break }
    'ps'        { Assert-Docker; docker compose ps; break }
    'build'     { Assert-Docker; docker compose build; break }
    'rebuild'   { Assert-Docker; docker compose build --no-cache; break }
    'shell'     { Assert-Docker; docker compose exec backend /bin/sh; break }
    'dbshell'   { Assert-Docker; docker compose exec db psql -U opsportal -d opsportal; break }
    'migrate'   { Assert-Docker; docker compose exec backend python manage.py migrate; break }
    'seed'      { Assert-Docker; docker compose exec backend python manage.py seed_demo; break }
    'reseed'    { Assert-Docker; docker compose exec backend python manage.py seed_demo --reset; break }
    'superuser' { Assert-Docker; docker compose exec backend python manage.py createsuperuser; break }
    'test'      { Assert-Docker; docker compose exec backend python manage.py test; break }
    'nuke' {
        Assert-Docker
        Write-Host "This deletes the database volume and all data in it." -ForegroundColor Yellow
        docker compose down -v
        break
    }
}
