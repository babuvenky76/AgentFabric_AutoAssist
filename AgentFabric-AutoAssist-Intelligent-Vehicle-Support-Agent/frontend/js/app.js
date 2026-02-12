/**
 * AutoAssist Frontend Application
 * Main application logic
 */

// DOM Elements
const chatForm = document.getElementById('chatForm');
const queryInput = document.getElementById('queryInput');
const chatButton = document.getElementById('chatButton');
const chatContainer = document.getElementById('chatContainer');
const charCount = document.getElementById('charCount');
const statusBadge = document.getElementById('statusBadge');
const statusText = document.getElementById('statusText');
const statusIndicator = document.getElementById('statusIndicator');
const apiEndpointInput = document.getElementById('apiEndpoint');
const saveConfigButton = document.getElementById('saveConfig');
const refreshMetricsButton = document.getElementById('refreshMetrics');
const loadingSpinner = document.getElementById('loadingSpinner');
const toast = document.getElementById('toast');
const modelInfo = document.getElementById('modelInfo');

// Application State
const appState = {
    isLoading: false,
    currentModel: 'Loading...',
    metrics: {
        totalRequests: 0,
        totalErrors: 0,
        avgLatency: 0,
        successRate: 100
    },
    healthStatus: 'unknown'
};

// ===========================
// Initialization
// ===========================

document.addEventListener('DOMContentLoaded', async () => {
    console.log('AutoAssist UI initialized');
    
    // Setup event listeners
    setupEventListeners();
    
    // Initialize app
    await initializeApp();
    
    // Start periodic checks
    startPeriodicUpdates();
});

function setupEventListeners() {
    // Chat form
    chatForm.addEventListener('submit', handleChatSubmit);
    queryInput.addEventListener('input', updateCharCount);
    
    // Configuration
    saveConfigButton.addEventListener('click', handleSaveConfig);
    apiEndpointInput.value = CONFIG.API_BASE_URL;
    
    // Metrics
    refreshMetricsButton.addEventListener('click', refreshMetrics);
}

async function initializeApp() {
    try {
        // Check health
        await checkHealth();
        
        // Load metrics
        await refreshMetrics();
        
        showToast('AutoAssist ready! Ask a vehicle-related question.', 'success');
    } catch (error) {
        console.error('Initialization error:', error);
        showToast('Failed to initialize. Check your API endpoint.', 'error');
    }
}

function startPeriodicUpdates() {
    // Periodic health check
    setInterval(checkHealth, 10000);
    
    // Periodic metrics refresh
    setInterval(refreshMetrics, CONFIG.METRICS_REFRESH_INTERVAL);
}

// ===========================
// Chat Functionality
// ===========================

async function handleChatSubmit(e) {
    e.preventDefault();
    
    const query = queryInput.value.trim();
    
    // Validation
    if (!query) {
        showToast('Please enter a question', 'error');
        return;
    }
    
    if (query.length < CONFIG.CHAT_CONFIG.MIN_QUERY_LENGTH) {
        showToast('Question too short', 'error');
        return;
    }
    
    if (query.length > CONFIG.CHAT_CONFIG.MAX_QUERY_LENGTH) {
        showToast('Question too long (max 1000 characters)', 'error');
        return;
    }
    
    // Send chat
    await sendChatQuery(query);
}

async function sendChatQuery(query) {
    if (appState.isLoading) return;
    
    appState.isLoading = true;
    chatButton.disabled = true;
    queryInput.disabled = true;
    showLoadingSpinner(true);
    
    // Add processing message
    const processingMsgId = addMessageToChat('🤖 Processing your query... This may take up to 5 minutes. Please wait...', 'system');
    
    try {
        // Add user message to chat
        addMessageToChat(query, 'user');
        
        // Clear input
        queryInput.value = '';
        charCount.textContent = '0';
        
        // Send request
        const response = await fetchWithRetry(
            getApiUrl(CONFIG.ENDPOINTS.CHAT),
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query })
            }
        );
        
        // Remove processing message
        removeMessageFromChat(processingMsgId);
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update model info
        if (data.model) {
            appState.currentModel = data.model;
            updateModelInfo();
        }
        
        // Handle response
        if (data.status === 'success') {
            addMessageToChat(data.response, 'agent');
            showToast('Response received', 'success');
        } else if (data.error) {
            addMessageToChat(`Error: ${data.error}`, 'error');
            showToast('Error processing query', 'error');
        }
        
        // Refresh metrics
        await refreshMetrics();
        
    } catch (error) {
        console.error('Chat error:', error);
        removeMessageFromChat(processingMsgId);
        addMessageToChat(`Error: ${error.message}`, 'error');
        showToast('Failed to send message. Check your connection.', 'error');
    } finally {
        appState.isLoading = false;
        chatButton.disabled = false;
        queryInput.disabled = false;
        showLoadingSpinner(false);
        queryInput.focus();
    }
}

function addMessageToChat(message, sender) {
    const messageEl = document.createElement('div');
    const messageId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    messageEl.id = messageId;
    messageEl.className = `message ${sender}`;
    
    const time = new Date().toLocaleTimeString();
    
    if (sender === 'error') {
        messageEl.innerHTML = `
            <div class="error-message">
                ${escapeHtml(message)}
            </div>
        `;
    } else if (sender === 'system') {
        messageEl.innerHTML = `
            <div class="system-message">
                ${escapeHtml(message)}
            </div>
        `;
    } else {
        messageEl.innerHTML = `
            <div class="message-content">${escapeHtml(message)}</div>
            <span class="message-time">${time}</span>
        `;
    }
    
    chatContainer.appendChild(messageEl);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    return messageId;
}

function removeMessageFromChat(messageId) {
    const messageEl = document.getElementById(messageId);
    if (messageEl) {
        messageEl.remove();
    }
}

function updateCharCount() {
    charCount.textContent = queryInput.value.length;
}

// ===========================
// Health Check
// ===========================

async function checkHealth() {
    try {
        const response = await fetchWithRetry(
            getApiUrl(CONFIG.ENDPOINTS.HEALTH),
            { method: 'GET' }
        );
        
        if (response.ok) {
            const data = await response.json();
            appState.healthStatus = 'healthy';
            updateHealthStatus('healthy');
            document.getElementById('apiStatus').innerHTML = `
                <span class="health-indicator healthy"></span>
                Healthy
            `;
        } else {
            appState.healthStatus = 'error';
            updateHealthStatus('error');
            document.getElementById('apiStatus').innerHTML = `
                <span class="health-indicator error"></span>
                Unhealthy
            `;
        }
    } catch (error) {
        console.error('Health check error:', error);
        appState.healthStatus = 'error';
        updateHealthStatus('error');
        document.getElementById('apiStatus').innerHTML = `
            <span class="health-indicator error"></span>
            Unreachable
        `;
    }
}

function updateHealthStatus(status) {
    statusBadge.className = `status-badge ${status}`;
    statusText.textContent = status === 'healthy' ? 'Service Healthy' : 'Service Unhealthy';
}

// ===========================
// Metrics
// ===========================

async function refreshMetrics() {
    try {
        const response = await fetchWithRetry(
            getApiUrl(CONFIG.ENDPOINTS.METRICS),
            { method: 'GET' }
        );
        
        if (response.ok) {
            const data = await response.json();
            updateMetricsDisplay(data);
            document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();
        }
    } catch (error) {
        console.error('Metrics fetch error:', error);
    }
}

function updateMetricsDisplay(metrics) {
    // Total requests
    document.getElementById('totalRequests').textContent = metrics.total_requests || 0;
    
    // Total errors
    document.getElementById('totalErrors').textContent = metrics.total_errors || 0;
    
    // Average latency
    const avgLatency = (metrics.avg_latency_ms || 0).toFixed(0);
    document.getElementById('avgLatency').textContent = `${avgLatency}ms`;
    
    // Success rate
    const totalRequests = metrics.total_requests || 0;
    const totalErrors = metrics.total_errors || 0;
    const successRate = totalRequests > 0 
        ? (((totalRequests - totalErrors) / totalRequests) * 100).toFixed(0)
        : 100;
    document.getElementById('successRate').textContent = `${successRate}%`;
}

function updateModelInfo() {
    modelInfo.textContent = `Model: ${appState.currentModel}`;
}

// ===========================
// Configuration
// ===========================

function handleSaveConfig() {
    const endpoint = apiEndpointInput.value.trim();
    
    if (!endpoint) {
        showToast('Please enter a valid API endpoint', 'error');
        return;
    }
    
    try {
        new URL(endpoint);
        updateApiEndpoint(endpoint);
        showToast('Settings saved successfully', 'success');
        
        // Reinitialize with new endpoint
        initializeApp();
    } catch (error) {
        showToast('Invalid API endpoint URL', 'error');
    }
}

// ===========================
// UI Utilities
// ===========================

function showLoadingSpinner(show) {
    if (show) {
        loadingSpinner.classList.add('active');
    } else {
        loadingSpinner.classList.remove('active');
    }
}

function showToast(message, type = 'info') {
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===========================
// Keyboard Shortcuts
// ===========================

document.addEventListener('keydown', (e) => {
    // Ctrl+Enter or Cmd+Enter to submit
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (document.activeElement === queryInput) {
            handleChatSubmit(new Event('submit'));
        }
    }
    
    // Escape to clear input
    if (e.key === 'Escape' && document.activeElement === queryInput) {
        queryInput.value = '';
        charCount.textContent = '0';
    }
});

console.log('AutoAssist Frontend loaded successfully');
