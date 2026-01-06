# 🔐 Auth & Azure-Ready Test Suite

This document outlines the manual `curl` tests to verify the **Authentication**, **Azure Readiness**, and **Basic Functionality** of the DocTalk API.

---

## ⚙️ Prerequisites

* **Docker:** Ensure the container is running (`docker-compose up`).
    * *Port Note:* Docker maps `9090` -> `8000`. We use port **9090** for these tests.
* **Local (Alternative):** If running with `poetry run uvicorn...`, change the port in commands below to **8000**.
* **Windows PowerShell Users:** Use `curl.exe` instead of `curl` and escape inner JSON quotes (e.g., `\"message\"`).

---

## 🧪 Scenario 1: Development Mode (Auth Bypass)

**Goal:** Verify that the API allows requests *without* a token when running locally.

### 1. Setup
Ensure your `.env.local` file has:
```properties
APP_ENV=development
```

Restart container: `docker-compose restart api`

### 2. Test Commands

#### A. Health Check (Public)
```bash
curl -X GET "http://localhost:9090/health"
# Expected: {"status":"ok","service":"doctalk-api"}
```

#### B. Chat Endpoint (Protected -> Bypassed)
This endpoint normally requires a token, but in development it should accept a simple X-User-ID.
```bash
curl -X POST "http://localhost:9090/chat" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: dev-session-01" \
  -H "X-User-ID: developer-mike" \
  -d '{"message": "Hello? Is anyone there?"}'
```

* **Expected Response:** `200 OK` (JSON response) or `500` (if no documents uploaded yet), but NOT `401 Unauthorized`.
* **Check Logs:** You should see a log entry: `debug "auth_bypassed" env="development" user="developer-mike"`.

---

## 🔒 Scenario 2: Production Mode (Auth Enforced)

**Goal:** Verify that the API rejects unauthorized requests when deployed (simulated).

### 1. Setup
Update your `.env.local` to simulate production:
```properties
APP_ENV=production
```

Restart container: `docker-compose restart api`

### 2. Test Commands

#### A. Fail Case: Missing Header
Attempt to access without any authorization.
```bash
curl -X POST "http://localhost:9090/chat" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: prod-session-01" \
  -d '{"message": "Let me in!"}'
```

* **Expected Response:** `401 Unauthorized`
* **Body:** `{"detail":"Invalid or missing Authorization header"}`

#### B. Fail Case: Bad Token
Attempt to access with an invalid token.
```bash
curl -X POST "http://localhost:9090/chat" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: prod-session-01" \
  -H "Authorization: Bearer invalid-token" \
  -d '{"message": "I am a hacker"}'
```

* **Expected Response:** `401 Unauthorized`
* **Body:** `{"detail":"Token rejected"}`

#### C. Success Case: Valid Token
Provide a valid Mock JWT (any string other than "invalid-token").
```bash
curl -X POST "http://localhost:9090/chat" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: prod-session-01" \
  -H "Authorization: Bearer azure-valid-jwt-token" \
  -d '{"message": "Hello Secure World"}'
```

* **Expected Response:** `200 OK` (or normal application response).
* **Check Logs:** You should see a log entry confirming the user is authenticated as `"azure-prod-user"`.

---

## ⚡ Windows PowerShell Quick Reference

If using PowerShell, copy-paste these one-liners:

### Dev Mode:
```powershell
curl.exe -X POST "http://localhost:9090/chat" -H "Content-Type: application/json" -H "X-Session-ID: dev-test" -d "{\"message\": \"Hello Dev\"}"
```

### Prod Mode (Success):
```powershell
curl.exe -X POST "http://localhost:9090/chat" -H "Content-Type: application/json" -H "X-Session-ID: prod-test" -H "Authorization: Bearer my-token" -d "{\"message\": \"Hello Prod\"}"
```
