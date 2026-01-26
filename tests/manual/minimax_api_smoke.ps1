# Minimax API Smoke Test
# Este script valida que POST /run usa Minimax real (no placeholder)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Minimax API Smoke Test - Validación Real" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Validar que estamos en la raíz del repo
if (-not (Test-Path "agentos\api\main.py")) {
    Write-Host "❌ ERROR: Debe ejecutar este script desde la raíz del repo agentos_mvp" -ForegroundColor Red
    Write-Host "   Directorio actual: $(Get-Location)" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Directorio correcto: $(Get-Location)" -ForegroundColor Green

# 2. Validar que .venv existe
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "❌ ERROR: No se encuentra .venv. Ejecute primero:" -ForegroundColor Red
    Write-Host "   python -m venv .venv" -ForegroundColor Yellow
    Write-Host "   .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "   pip install -e ." -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Virtual environment encontrado" -ForegroundColor Green

# 3. Activar .venv
Write-Host ""
Write-Host "Activando virtual environment..." -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

# 4. Validar env vars requeridas
Write-Host ""
Write-Host "Validando variables de entorno..." -ForegroundColor Cyan

$errors = @()

if ($env:AGENTOS_ORCHESTRATOR -ne "planner") {
    $errors += "AGENTOS_ORCHESTRATOR debe ser 'planner'"
}

if (($env:AGENTOS_LLM_PROVIDER -ne "minimax") -and ($env:AGENTOS_LLM -ne "minimax")) {
    $errors += "AGENTOS_LLM_PROVIDER o AGENTOS_LLM debe ser 'minimax'"
}

if (-not $env:MINIMAX_API_KEY) {
    $errors += "MINIMAX_API_KEY no está configurada"
}

if ($errors.Count -gt 0) {
    Write-Host "❌ ERROR: Variables de entorno faltantes o incorrectas:" -ForegroundColor Red
    foreach ($error in $errors) {
        Write-Host "   - $error" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "Configure las variables antes de ejecutar este script:" -ForegroundColor Yellow
    Write-Host '  $env:AGENTOS_ORCHESTRATOR = "planner"' -ForegroundColor White
    Write-Host '  $env:AGENTOS_LLM_PROVIDER = "minimax"' -ForegroundColor White
    Write-Host '  $env:MINIMAX_API_KEY = "tu-api-key-aqui"' -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "✅ AGENTOS_ORCHESTRATOR = $env:AGENTOS_ORCHESTRATOR" -ForegroundColor Green
if ($env:AGENTOS_LLM_PROVIDER) {
    Write-Host "✅ AGENTOS_LLM_PROVIDER = $env:AGENTOS_LLM_PROVIDER" -ForegroundColor Green
} else {
    Write-Host "✅ AGENTOS_LLM = $env:AGENTOS_LLM" -ForegroundColor Green
}
Write-Host "✅ MINIMAX_API_KEY = ***$(($env:MINIMAX_API_KEY).Substring([Math]::Max(0, $env:MINIMAX_API_KEY.Length - 4)))" -ForegroundColor Green

# 5. Configurar API key para autenticación (si aplica)
if (-not $env:AGENTOS_API_KEY) {
    Write-Host ""
    Write-Host "⚠️  AGENTOS_API_KEY no configurada, usando 'test-key' por defecto" -ForegroundColor Yellow
    $apiKey = "test-key"
} else {
    $apiKey = $env:AGENTOS_API_KEY
}

# 6. Instrucciones para levantar servidor
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PASO 1: Levantar servidor uvicorn" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "En una NUEVA ventana de PowerShell, ejecute:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  cd $(Get-Location)" -ForegroundColor White
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host '  $env:AGENTOS_ORCHESTRATOR = "planner"' -ForegroundColor White
Write-Host '  $env:AGENTOS_LLM_PROVIDER = "minimax"' -ForegroundColor White
Write-Host '  $env:MINIMAX_API_KEY = "' -NoNewline -ForegroundColor White
Write-Host "***" -NoNewline -ForegroundColor Red
Write-Host '"' -ForegroundColor White
Write-Host "  uvicorn agentos.api.main:app --host 127.0.0.1 --port 8080" -ForegroundColor White
Write-Host ""
Write-Host "Presione ENTER cuando el servidor esté listo (verá 'Application startup complete')..." -ForegroundColor Yellow
Read-Host

# 7. Verificar que el servidor está corriendo
Write-Host ""
Write-Host "Verificando que el servidor responde..." -ForegroundColor Cyan
try {
    $healthResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8080/healthz" -Method Get -ErrorAction Stop
    Write-Host "✅ Servidor responde en http://127.0.0.1:8080" -ForegroundColor Green
    Write-Host "   Agentes: $($healthResponse.agents -join ', ')" -ForegroundColor Gray
    Write-Host "   Tools: $($healthResponse.tools -join ', ')" -ForegroundColor Gray
} catch {
    Write-Host "❌ ERROR: El servidor no responde en http://127.0.0.1:8080" -ForegroundColor Red
    Write-Host "   Asegúrese de que uvicorn está corriendo" -ForegroundColor Yellow
    exit 1
}

# 8. Ejecutar request a POST /run
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PASO 2: Ejecutar POST /run con Minimax" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$requestBody = @{
    task = "Explica qué es Python en una frase corta"
    session_id = "smoke-test-session"
    user_id = "smoke-test-user"
} | ConvertTo-Json

Write-Host "Request:" -ForegroundColor Cyan
Write-Host $requestBody -ForegroundColor Gray
Write-Host ""
Write-Host "Enviando request a Minimax API..." -ForegroundColor Cyan

try {
    $response = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8080/run" `
        -Method Post `
        -Headers @{"X-API-Key" = $apiKey; "Content-Type" = "application/json"} `
        -Body $requestBody `
        -ErrorAction Stop
    
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "RESULTADO" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Mostrar respuesta
    Write-Host "Agent: $($response.agent)" -ForegroundColor White
    Write-Host "Success: $($response.success)" -ForegroundColor $(if ($response.success) { "Green" } else { "Red" })
    Write-Host ""
    Write-Host "Output:" -ForegroundColor Cyan
    Write-Host $response.output -ForegroundColor White
    Write-Host ""
    
    if ($response.error) {
        Write-Host "Error:" -ForegroundColor Red
        Write-Host $response.error -ForegroundColor Yellow
        Write-Host ""
    }
    
    # Validar que NO es el placeholder
    $isPlaceholder = $response.output -match "En un sistema real.*tool router"
    
    if ($isPlaceholder) {
        Write-Host "❌ FALLO: La respuesta contiene el PLACEHOLDER" -ForegroundColor Red
        Write-Host "   Minimax NO está siendo usado correctamente" -ForegroundColor Yellow
        exit 1
    } else {
        Write-Host "✅ ÉXITO: La respuesta NO contiene el placeholder" -ForegroundColor Green
        Write-Host "   Minimax está generando respuestas reales" -ForegroundColor Green
    }
    
    # Validar que es planner_executor
    if ($response.agent -eq "planner_executor") {
        Write-Host "✅ Orquestador correcto: planner_executor" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Orquestador inesperado: $($response.agent)" -ForegroundColor Yellow
    }
    
    # Mostrar metadata
    if ($response.meta) {
        Write-Host ""
        Write-Host "Metadata:" -ForegroundColor Cyan
        Write-Host "  Subtasks: $($response.meta.subtasks.Count)" -ForegroundColor Gray
        Write-Host "  Replan count: $($response.meta.replan_count)" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "✅ SMOKE TEST EXITOSO" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    
} catch {
    Write-Host ""
    Write-Host "❌ ERROR al ejecutar request:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "   Status code: $statusCode" -ForegroundColor Yellow
    }
    
    exit 1
}
