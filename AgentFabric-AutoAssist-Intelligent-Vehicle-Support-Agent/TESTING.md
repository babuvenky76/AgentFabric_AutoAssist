# AutoAssist UI Testing Guide

## Overview
This guide provides complete instructions for testing the AutoAssist UI locally on your laptop.

---

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Local Testing Setup](#local-testing-setup)
4. [Manual UI Testing](#manual-ui-testing)
5. [Automated Testing](#automated-testing)
6. [Troubleshooting](#troubleshooting)
7. [Test Scenarios](#test-scenarios)

---

## Prerequisites

### System Requirements
- **OS**: macOS, Linux, or Windows
- **Node.js**: v14 or higher (for frontend server)
- **Python**: 3.10+ (for backend API)
- **Docker**: Optional (for containerized testing)

### Installation

#### 1. Install Node.js
```bash
# macOS (using brew)
brew install node

# Verify installation
node --version
npm --version
```

#### 2. Install Python Dependencies
```bash
# Navigate to project root
cd AgentFabric-AutoAssist-Intelligent-Vehicle-Support-Agent

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Quick Start

### Option 1: Simple Local Testing (No Docker)

#### Step 1: Start the Backend API
```bash
# From project root, in terminal 1
source venv/bin/activate
python -m app.main
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

#### Step 2: Start the Frontend Server
```bash
# From project root, in terminal 2
cd frontend
node server.js
```

Expected output:
```
AutoAssist Frontend server running on http://localhost:3000
Serving files from: /path/to/frontend
```

#### Step 3: Open in Browser
```bash
# Open browser and navigate to:
http://localhost:3000
```

✅ You should see the AutoAssist chat interface!

---

### Option 2: Docker Compose Testing

#### Step 1: Build and Start Services
```bash
# From project root
docker-compose up --build
```

This starts:
- Frontend (http://localhost:3000)
- API Backend (http://localhost:8000)
- Prometheus (http://localhost:9090)
- Grafana (http://localhost:3000) - separate instance

#### Step 2: Access the UI
```
http://localhost:3000
```

#### Step 3: Stop Services
```bash
docker-compose down
```

---

## Local Testing Setup

### Configuration

#### 1. Update .env File
```bash
# Create .env from example
cp .env.example .env

# Edit .env with your settings
nano .env
```

#### 2. Key Configuration Variables
```env
# API Backend
API_ENDPOINT=http://localhost:8000

# LLM Configuration
MODEL_PROVIDER=local          # or "api"
MODEL_NAME=mistral            # LLM model name
TEMPERATURE=0.7              # Response randomness (0-1)
MAX_TOKENS=1024              # Max response length
TIMEOUT_SECONDS=30           # Request timeout
```

#### 3. Configure Frontend API Endpoint
In the UI, navigate to the "Configuration" section on the right sidebar:
- Update "API Endpoint" to your backend URL
- Click "Save Settings"

The endpoint is persisted in browser's localStorage.

---

## Manual UI Testing

### Test 1: Basic Chat Functionality

**Steps:**
1. Open http://localhost:3000
2. In the chat input field, type: "How do I check my tire pressure?"
3. Click "Send" or press Enter
4. Wait for response

**Expected Results:**
- ✅ User message appears on the right (blue)
- ✅ Agent response appears on the left (gray)
- ✅ Response is automotive-related
- ✅ Timestamp shows for each message
- ✅ Chat automatically scrolls to latest message

**Screenshot Checkpoints:**
- [ ] Chat interface loads correctly
- [ ] Messages display with proper formatting
- [ ] Scroll works smoothly
- [ ] Send button is clickable

---

### Test 2: Input Validation

**Test 2a: Empty Input**
1. Leave chat input blank
2. Click "Send"

**Expected:** Toast notification: "Please enter a question"

**Test 2b: Maximum Length Exceeded**
1. Paste a message with 1001+ characters
2. Click "Send"

**Expected:** Toast notification: "Question too long (max 1000 characters)"

**Test 2c: Character Count Display**
1. Type in the chat input
2. Observe character count in bottom-right

**Expected:** Character count updates in real-time (e.g., "42/1000")

---

### Test 3: Health Check

**Steps:**
1. Ensure backend API is running
2. Look at header status badge

**Expected Results:**
- ✅ Status badge shows "Service Healthy" (green indicator)
- ✅ Status updates automatically every 10 seconds
- ✅ If backend is down, shows "Service Unhealthy" (red indicator)

**Test Backend Down Scenario:**
1. Stop the backend API service
2. Observe status badge changes to red
3. Try sending a message
4. Expected: Error toast notification

---

### Test 4: Metrics Display

**Steps:**
1. Send 3-5 chat messages
2. Look at the "Agent Metrics" panel on the right

**Expected Results:**
- ✅ Total Requests increments correctly
- ✅ Success Rate updates
- ✅ Average Latency displays in milliseconds
- ✅ Metrics refresh every 5 seconds

**Test Manual Refresh:**
1. Click the 🔄 refresh button in metrics header
2. Observe metrics update immediately

---

### Test 5: Configuration

**Steps:**
1. Change API Endpoint in Configuration panel
2. Click "Save Settings"
3. Verify toast confirmation

**Expected Results:**
- ✅ Toast shows "Settings saved successfully"
- ✅ New endpoint persists in browser (localStorage)
- ✅ Health check uses new endpoint
- ✅ Chat requests use new endpoint

---

### Test 6: Keyboard Shortcuts

**Test 6a: Send with Ctrl+Enter**
1. Type a message
2. Press Ctrl+Enter (Cmd+Enter on Mac)
3. Expected: Message sends without clicking button

**Test 6b: Clear with Escape**
1. Type a message
2. Press Escape
3. Expected: Input clears, character count resets to 0

---

### Test 7: Loading Spinner

**Steps:**
1. Send a chat message
2. Observe loading spinner overlay

**Expected Results:**
- ✅ Semi-transparent overlay appears
- ✅ Spinning animation in center
- ✅ "Processing..." text displays
- ✅ Spinner disappears when response arrives

---

### Test 8: Error Handling

**Test 8a: Network Error**
1. Disconnect from internet or stop API
2. Try sending a message
3. Expected: Error message in chat + error toast

**Test 8b: API Error**
1. Send a very long query (exactly at 1000 characters)
2. Expected: Either success or error response from API

**Test 8c: Timeout**
1. If backend is slow, wait for timeout
2. Expected: "Request timeout" error message

---

### Test 9: Responsive Design

#### Desktop (1280px+)
```bash
# Open in full browser window
http://localhost:3000
```
**Expected:** 2-column layout (chat + metrics sidebar)

#### Tablet (768px-1024px)
```bash
# Resize browser window or use DevTools: Ctrl+Shift+M
```
**Expected:** 
- Single column layout
- Metrics displayed below chat
- Buttons responsive

#### Mobile (< 768px)
```bash
# Resize to ~375px width or use mobile DevTools
```
**Expected:**
- All elements stack vertically
- Touch-friendly button sizes
- No horizontal scroll
- Header adapts to small screen

---

### Test 10: Dark Mode

**Steps:**
1. (OS Level) Set system to Dark Mode
2. Reload the page

**Expected Results:**
- ✅ UI colors adapt to dark theme
- ✅ Text remains readable
- ✅ Contrast meets accessibility standards

---

## Automated Testing

### cURL Testing

#### Test Health Endpoint
```bash
curl -X GET http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "AutoAssist",
  "version": "0.1.0"
}
```

#### Test Chat Endpoint
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"How do I check my oil?"}'
```

**Expected Response:**
```json
{
  "status": "success",
  "query": "How do I check my oil?",
  "response": "To check your oil safely...",
  "model": "mistral"
}
```

#### Test Metrics Endpoint
```bash
curl -X GET http://localhost:8000/metrics
```

**Expected Response:**
```json
{
  "total_requests": 5,
  "total_errors": 0,
  "avg_latency_ms": 450.5
}
```

---

### Browser Console Testing

**Open Browser DevTools:** F12 or Ctrl+Shift+I

#### Test 1: Check Configuration
```javascript
console.log(CONFIG);
```

#### Test 2: Check App State
```javascript
console.log(appState);
```

#### Test 3: Manual API Call
```javascript
fetch('http://localhost:8000/health')
  .then(r => r.json())
  .then(d => console.log(d))
  .catch(e => console.error(e));
```

#### Test 4: Test Toast Notification
```javascript
showToast('This is a test notification', 'success');
```

---

## Test Scenarios

### Scenario 1: Complete User Journey

1. **User Opens App**
   - [ ] Frontend loads at http://localhost:3000
   - [ ] Header displays properly
   - [ ] Status badge shows healthy

2. **User Asks Questions**
   - [ ] Send: "What does ABS warning light mean?"
   - [ ] Receive automotive-related response
   - [ ] Message history displays correctly

3. **User Checks Metrics**
   - [ ] Metrics panel shows request count = 1
   - [ ] Success rate = 100%
   - [ ] Click refresh button

4. **User Changes Settings**
   - [ ] Update API endpoint
   - [ ] Save configuration
   - [ ] Health check still works
   - [ ] Can still send messages

5. **User Closes and Reopens**
   - [ ] Close browser tab
   - [ ] Reopen http://localhost:3000
   - [ ] Settings persist (saved API endpoint)

---

### Scenario 2: Error Recovery

1. **Backend Goes Down**
   - [ ] Stop backend API
   - [ ] Status badge turns red
   - [ ] Try sending message
   - [ ] Error message appears
   - [ ] Restart backend API
   - [ ] Status badge turns green

2. **Invalid API Endpoint**
   - [ ] Change endpoint to http://invalid:9999
   - [ ] Click save
   - [ ] Try sending message
   - [ ] Error handling works

3. **Network Issues**
   - [ ] Disconnect internet
   - [ ] Try sending message
   - [ ] Error toast appears
   - [ ] Reconnect internet
   - [ ] Can send messages again

---

### Scenario 3: Performance Testing

1. **Rapid Requests**
   - [ ] Send 10 messages quickly
   - [ ] No crashed errors
   - [ ] Messages queue properly
   - [ ] Latency metrics update

2. **Long Responses**
   - [ ] Ask question that generates lengthy response
   - [ ] Chat scrolls to show full response
   - [ ] Latency metric updates correctly

3. **Large Input**
   - [ ] Send 1000-character query
   - [ ] Accepted without error
   - [ ] Response received correctly

---

## Troubleshooting

### Issue: "Connection Refused" on http://localhost:3000

**Solutions:**
```bash
# Check if frontend server is running
lsof -i :3000

# Or check with Node processes
ps aux | grep node

# If not running, start it:
cd frontend
node server.js
```

### Issue: "Cannot POST /chat"

**Solutions:**
```bash
# Verify backend is running
curl http://localhost:8000/health

# If not, start it:
source venv/bin/activate
python -m app.main

# Verify API endpoint in UI configuration
# Should be: http://localhost:8000
```

### Issue: CORS Errors

**Solution:**
The backend FastAPI service already has CORS enabled. If you still see errors:

1. Check browser console for exact error
2. Verify API_BASE_URL in frontend config matches backend
3. Ensure backend is running and accessible

### Issue: Changes Not Reflected

**Solutions:**
```bash
# For frontend changes:
# Hard refresh in browser: Ctrl+Shift+R

# For backend changes:
# Restart the Python server

# For cached settings:
# Clear browser localStorage:
```

In browser console:
```javascript
localStorage.clear();
location.reload();
```

### Issue: Docker Port Already in Use

**Solutions:**
```bash
# Find process using port 3000
lsof -i :3000

# Kill process
kill -9 <PID>

# Or use different port:
docker run -p 3001:3000 autoassist-frontend
```

---

## Test Report Template

Use this template to document your testing:

```
# AutoAssist UI Test Report
Date: [DATE]
Tester: [NAME]
Environment: [macOS/Linux/Windows]

## Test Results Summary
- Total Tests: __
- Passed: __
- Failed: __
- Skipped: __

## Test Details
| Test | Result | Notes |
|------|--------|-------|
| Chat Functionality | ✅/❌ | |
| Input Validation | ✅/❌ | |
| Health Check | ✅/❌ | |
| Metrics Display | ✅/❌ | |
| Responsive Design | ✅/❌ | |
| Error Handling | ✅/❌ | |

## Known Issues
1. [Issue 1]
2. [Issue 2]

## Recommendations
1. [Recommendation 1]
2. [Recommendation 2]
```

---

## Browser Compatibility Matrix

| Browser | Version | Status |
|---------|---------|--------|
| Chrome | Latest | ✅ Tested |
| Firefox | Latest | ✅ Tested |
| Safari | Latest | ✅ Tested |
| Edge | Latest | ✅ Tested |
| Mobile Safari | Latest | ⚠️ Limited |

---

## Performance Benchmarks

Target metrics:
- **Page Load:** < 2 seconds
- **Chat Response:** < 5 seconds
- **Metrics Refresh:** < 1 second
- **API Health Check:** < 500ms

---

## Quick Reference

### Start Services
```bash
# Terminal 1 - Backend
source venv/bin/activate
python -m app.main

# Terminal 2 - Frontend
cd frontend && node server.js
```

### Access Points
- **UI:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/health
- **Metrics:** http://localhost:8000/metrics

### Useful Commands
```bash
# Check if services are running
lsof -i :3000  # Frontend
lsof -i :8000  # Backend

# View logs
docker-compose logs -f

# Restart services
docker-compose restart

# Clean up
docker-compose down -v
```

---

**Last Updated:** February 2026  
**AutoAssist by Babu Srinivasan**
