# Start Postgres
$dbRunning = docker ps --filter "name=mediassist-db" --format "{{.Names}}"
if ($dbRunning -ne "mediassist-db") {
    Write-Host "Starting Postgres..."
    docker run -d --name mediassist-db `
        -e POSTGRES_USER=mediassist `
        -e POSTGRES_PASSWORD=mediassist `
        -e POSTGRES_DB=mediassist `
        -p 5432:5432 `
        postgres:16-alpine
    Start-Sleep -Seconds 3
} else {
    Write-Host "Postgres already running."
}

# Start API
Write-Host "Starting API on http://localhost:8000 ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; .venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload"

# Start Streamlit
Write-Host "Starting UI on http://localhost:8501 ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; .venv\Scripts\streamlit.exe run streamlit_app.py"
