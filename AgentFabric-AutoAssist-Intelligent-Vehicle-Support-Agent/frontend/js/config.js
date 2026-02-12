/**
 * Frontend Configuration
 * Configure API endpoint and other settings
 */

const CONFIG = {
    // API Configuration
    API_BASE_URL: localStorage.getItem('apiEndpoint') || 'http://localhost:8000',
    
    // Endpoints
    ENDPOINTS: {
        CHAT: '/chat',
        HEALTH: '/health',
        METRICS: '/metrics'
    },
    
    // Request Configuration
    REQUEST_TIMEOUT: 30000, // 30 seconds
    
    // Retry Policy
    MAX_RETRIES: 3,
    RETRY_DELAY: 1000, // 1 second
    
    // Metrics Refresh Interval
    METRICS_REFRESH_INTERVAL: 5000, // 5 seconds
    
    // Chat Configuration
    CHAT_CONFIG: {
        MAX_QUERY_LENGTH: 1000,
        MIN_QUERY_LENGTH: 1
    }
};

/**
 * Get full API endpoint URL
 * @param {string} endpoint - Endpoint path
 * @returns {string} Full API URL
 */
function getApiUrl(endpoint) {
    return `${CONFIG.API_BASE_URL}${endpoint}`;
}

/**
 * Update API endpoint
 * @param {string} endpoint - New API endpoint
 */
function updateApiEndpoint(endpoint) {
    CONFIG.API_BASE_URL = endpoint;
    localStorage.setItem('apiEndpoint', endpoint);
}

/**
 * Fetch with retry logic
 * @param {string} url - URL to fetch
 * @param {object} options - Fetch options
 * @returns {Promise} Fetch response
 */
async function fetchWithRetry(url, options = {}, retries = CONFIG.MAX_RETRIES) {
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT);
        
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        
        clearTimeout(timeout);
        return response;
    } catch (error) {
        if (retries > 0 && error.name !== 'AbortError') {
            await new Promise(resolve => setTimeout(resolve, CONFIG.RETRY_DELAY));
            return fetchWithRetry(url, options, retries - 1);
        }
        throw error;
    }
}
