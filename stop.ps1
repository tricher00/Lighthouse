# Stop Lighthouse Server
# Finds and kills the Python process running the Lighthouse server

Write-Host "Stopping Lighthouse server..." -ForegroundColor Cyan

# Load .env to get the PORT
$envFile = Join-Path $PSScriptRoot ".env"
$port = 8000  # Default port

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^PORT=(\d+)') {
            $port = [int]$matches[1]
        }
    }
}

Write-Host "Looking for processes on port $port..." -ForegroundColor Yellow

# Find the process using the port
$netstatOutput = netstat -ano | Select-String ":$port\s" | Select-String "LISTENING"

if ($netstatOutput) {
    $processIds = @()
    
    foreach ($line in $netstatOutput) {
        # Extract PID from netstat output (last column)
        if ($line -match '\s+(\d+)\s*$') {
            $processId = $matches[1]
            $processIds += $processId
        }
    }
    
    # Remove duplicates
    $processIds = $processIds | Select-Object -Unique
    
    if ($processIds.Count -gt 0) {
        Write-Host "Found $($processIds.Count) process(es) to stop:" -ForegroundColor Yellow
        
        foreach ($processId in $processIds) {
            try {
                $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Host "  - Stopping PID $processId ($($process.ProcessName))..." -ForegroundColor White
                    Stop-Process -Id $processId -Force
                    Write-Host "    ✓ Stopped" -ForegroundColor Green
                }
            }
            catch {
                Write-Host "    ✗ Failed to stop PID $processId : $_" -ForegroundColor Red
            }
        }
        
        Write-Host "`nLighthouse server stopped successfully!" -ForegroundColor Green
    }
    else {
        Write-Host "No processes found on port $port" -ForegroundColor Yellow
    }
}
else {
    Write-Host "No Lighthouse server running on port $port" -ForegroundColor Yellow
}
