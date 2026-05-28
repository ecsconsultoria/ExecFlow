# Padroniza execução dos testes do App_Orcamentos_V2.
#
# Uso:
#   .\run_tests.ps1                       # roda toda a suite
#   .\run_tests.ps1 -Cov                  # com relatório de cobertura (term + HTML)
#   .\run_tests.ps1 -File tests/test_rbac_routes.py
#   .\run_tests.ps1 -K "tenant"           # filtra por keyword (pytest -k)
#   .\run_tests.ps1 -Cov -K "security"    # combinável

param(
    [switch]$Cov,
    [string]$File = "",
    [string]$K = ""
)

$ErrorActionPreference  = "Stop"
$env:PYTHONIOENCODING   = "utf-8"
$env:PYTHONPATH         = (Get-Location).Path

$python = "c:\Users\ECS\OneDrive - ECS Consultoria\AI_Projects\venv\Scripts\python.exe"

$pyArgs = @("-m", "pytest", "-v")
if ($Cov)  { $pyArgs += @("--cov=app", "--cov-report=term-missing", "--cov-report=html") }
if ($File) { $pyArgs += $File }
if ($K)    { $pyArgs += @("-k", $K) }

& $python @pyArgs
