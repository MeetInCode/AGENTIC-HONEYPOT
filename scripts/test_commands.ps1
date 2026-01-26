# ============================================
# Agentic Honeypot - Windows PowerShell Test Commands
# ============================================
# This script contains all commands needed to
# set up, run, and test the Agentic Honeypot.
# Run commands individually as needed.
# ============================================

Write-Host "🍯 Agentic Honeypot - Test Commands Reference" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ============================================
# 1. SETUP COMMANDS
# ============================================

Write-Host "`n📦 SETUP COMMANDS:" -ForegroundColor Yellow

# Create virtual environment
# python -m venv venv

# Activate virtual environment (Windows PowerShell)
# .\venv\Scripts\Activate.ps1

# Install dependencies
# pip install -r requirements.txt

# Download spaCy model (optional)
# python -m spacy download en_core_web_sm

# Copy environment file
# Copy-Item .env.example .env
# Then edit .env with your API keys using notepad or VS Code

# ============================================
# 2. RUN SERVER
# ============================================

Write-Host "`n🚀 RUN SERVER:" -ForegroundColor Yellow

# Start the API server
# python main.py

# Or with uvicorn
# uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# ============================================
# 3. RUN TESTS
# ============================================

Write-Host "`n🧪 RUN TESTS:" -ForegroundColor Yellow

# Run API integration tests (requires server running in another terminal)
# python tests/test_api.py

# Run unit tests with pytest
# pytest tests/test_agents.py -v

# Run all tests
# pytest tests/ -v

# ============================================
# 4. INVOKE-RESTMETHOD COMMANDS
# ============================================

Write-Host "`n📡 PowerShell API Test Commands:" -ForegroundColor Yellow
Write-Host ""

# Health check
Write-Host "# Health Check:" -ForegroundColor Green
Write-Host 'Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get'
Write-Host ""

# Test scam message analysis
Write-Host "# Analyze Scam Message:" -ForegroundColor Green
$testBody = @'
$headers = @{
    "x-api-key" = "your-secret-api-key-here"
    "Content-Type" = "application/json"
}

$body = @{
    sessionId = "ps-test-001"
    message = @{
        sender = "scammer"
        text = "Your SBI account will be blocked today. Verify immediately by sharing OTP."
        timestamp = "2024-01-26T10:00:00Z"
    }
    conversationHistory = @()
    metadata = @{
        channel = "SMS"
        language = "English"
        locale = "IN"
    }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/analyze" -Method Post -Headers $headers -Body $body
'@
Write-Host $testBody
Write-Host ""

# List sessions
Write-Host "# List Sessions:" -ForegroundColor Green
Write-Host '$headers = @{"x-api-key" = "your-secret-api-key-here"}'
Write-Host 'Invoke-RestMethod -Uri "http://localhost:8000/api/v1/sessions" -Method Get -Headers $headers'
Write-Host ""

# Get session details
Write-Host "# Get Session Details:" -ForegroundColor Green
Write-Host 'Invoke-RestMethod -Uri "http://localhost:8000/api/v1/session/ps-test-001" -Method Get -Headers $headers'
Write-Host ""

# ============================================
# 5. QUICK TEST FUNCTION
# ============================================

Write-Host "🔧 Quick Test Function:" -ForegroundColor Yellow

$quickTest = @'
function Test-Honeypot {
    param(
        [string]$Message = "Your account will be blocked. Click here to verify.",
        [string]$ApiKey = "your-secret-api-key-here",
        [string]$BaseUrl = "http://localhost:8000"
    )
    
    $headers = @{
        "x-api-key" = $ApiKey
        "Content-Type" = "application/json"
    }
    
    $body = @{
        sessionId = "quick-test-$(Get-Date -Format 'HHmmss')"
        message = @{
            sender = "scammer"
            text = $Message
            timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
        }
        conversationHistory = @()
        metadata = @{
            channel = "SMS"
            language = "English"
            locale = "IN"
        }
    } | ConvertTo-Json -Depth 5
    
    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/api/v1/analyze" -Method Post -Headers $headers -Body $body
        
        Write-Host "`nResult:" -ForegroundColor Cyan
        Write-Host "  Scam Detected: $($response.scamDetected)" -ForegroundColor $(if ($response.scamDetected) { "Red" } else { "Green" })
        
        if ($response.agentResponse) {
            Write-Host "  Agent Response: $($response.agentResponse)" -ForegroundColor Yellow
        }
        
        return $response
    }
    catch {
        Write-Host "Error: $_" -ForegroundColor Red
    }
}

# Usage:
# Test-Honeypot -Message "URGENT: Share OTP to unblock account"
# Test-Honeypot -Message "Hi, let's meet for coffee tomorrow"
'@
Write-Host $quickTest
Write-Host ""

# ============================================
# 6. SAMPLE TEST MESSAGES
# ============================================

Write-Host "`n📝 Sample Test Messages:" -ForegroundColor Yellow

$samples = @(
    @{Type="Scam"; Message="Your bank account will be blocked today. Verify immediately."},
    @{Type="Scam"; Message="URGENT: Your UPI ID suspended. Share OTP to verify."},
    @{Type="Scam"; Message="Congratulations! You won Rs 50000. Share bank details to claim."},
    @{Type="Scam"; Message="Income Tax refund pending. Click: bit.ly/itrefund"},
    @{Type="Safe"; Message="Hi, how are you doing? Let's meet tomorrow."},
    @{Type="Safe"; Message="Your Amazon order has been shipped."}
)

foreach ($sample in $samples) {
    $color = if ($sample.Type -eq "Scam") { "Red" } else { "Green" }
    Write-Host "  [$($sample.Type)] $($sample.Message)" -ForegroundColor $color
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "📖 For full documentation, see README.md" -ForegroundColor Cyan
Write-Host "📖 API docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
