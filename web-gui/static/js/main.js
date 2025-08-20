/**
 * Modern Web UI JavaScript for MCP Document Exchange System
 * Handles all interactive functionality, API calls, and UI updates
 */

// Global variables
let currentAction = 'process';
let isProcessing = false;

// DOM elements
const documentForm = document.getElementById('documentForm');
const responseArea = document.getElementById('responseArea');
const loadingContainer = document.getElementById('loadingContainer');
const submitButton = document.getElementById('submitButton');
const buttonText = document.getElementById('buttonText');
const loadingText = document.getElementById('loadingText');
const clearLogsBtn = document.getElementById('clearLogsBtn');
const sampleDocBtn = document.getElementById('sampleDocBtn');
const healthCheckBtn = document.getElementById('healthCheckBtn');
const copyResultBtn = document.getElementById('copyResultBtn');

// Status indicators
const documentServiceStatus = document.getElementById('documentServiceStatus');
const summarizationServiceStatus = document.getElementById('summarizationServiceStatus');
const connectionStatus = document.getElementById('connectionStatus');

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    performHealthCheck();
    updateActionSelection();
});

/**
 * Initialize all event listeners
 */
function initializeEventListeners() {
    // Form submission
    documentForm.addEventListener('submit', handleFormSubmission);
    
    // Action selection
    document.querySelectorAll('input[name="action"]').forEach(radio => {
        radio.addEventListener('change', updateActionSelection);
    });
    
    // Quick action buttons
    clearLogsBtn.addEventListener('click', clearLogs);
    sampleDocBtn.addEventListener('click', loadSampleDocument);
    healthCheckBtn.addEventListener('click', performHealthCheck);
    copyResultBtn.addEventListener('click', copyResults);
    
    // Auto-resize textarea
    const textarea = document.getElementById('document_content');
    textarea.addEventListener('input', autoResizeTextarea);
}

/**
 * Update UI based on selected action
 */
function updateActionSelection() {
    currentAction = document.querySelector('input[name="action"]:checked').value;
    
    // Update button text and loading text
    switch(currentAction) {
        case 'process':
            buttonText.textContent = 'Verify & Summarize';
            loadingText.textContent = 'Processing document (verify + summarize)';
            break;
        case 'verify':
            buttonText.textContent = 'Verify Document';
            loadingText.textContent = 'Verifying document';
            break;
        case 'summarize':
            buttonText.textContent = 'Summarize Text';
            loadingText.textContent = 'Summarizing text';
            break;
    }
}

/**
 * Handle form submission
 */
async function handleFormSubmission(event) {
    event.preventDefault();
    
    if (isProcessing) return;
    
    const documentContent = document.getElementById('document_content').value.trim();
    const accessCode = document.getElementById('access_code').value.trim();
    
    // Validation
    if (!documentContent || !accessCode) {
        addLogEntry('Please provide both document content and access code.', 'error', 'Validation Error');
        return;
    }
    
    // Start processing
    isProcessing = true;
    showLoading();
    clearInitialMessage();
    
    addLogEntry(`Started ${getActionDescription()} with access code: "${accessCode}"`, 'user', 'User Request');
    
    try {
        let result;
        
        switch(currentAction) {
            case 'process':
                result = await processDocument(documentContent, accessCode);
                break;
            case 'verify':
                result = await verifyDocument(documentContent, accessCode);
                break;
            case 'summarize':
                result = await summarizeText(documentContent, accessCode);
                break;
        }
        
        handleResult(result);
        
    } catch (error) {
        console.error('Processing error:', error);
        addLogEntry(`Error: ${error.message}`, 'error', 'System Error');
    } finally {
        isProcessing = false;
        hideLoading();
    }
}

/**
 * Process document (verify + summarize)
 */
async function processDocument(documentContent, accessCode) {
    addLogEntry('Initiating full document processing...', 'system', 'MCP System');
    
    const response = await fetch('/api/process_document', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            document_content: documentContent,
            access_code: accessCode
        })
    });
    
    return await handleApiResponse(response);
}

/**
 * Verify document only
 */
async function verifyDocument(documentContent, accessCode) {
    addLogEntry('Initiating document verification...', 'system', 'MCP System');
    
    const response = await fetch('/api/verify_document', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            document_content: documentContent,
            access_code: accessCode
        })
    });
    
    return await handleApiResponse(response);
}

/**
 * Summarize text only
 */
async function summarizeText(textContent, accessCode) {
    addLogEntry('Initiating text summarization...', 'system', 'MCP System');
    
    const response = await fetch('/api/summarize_text', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            text_content: textContent,
            access_code: accessCode
        })
    });
    
    return await handleApiResponse(response);
}

/**
 * Handle API response
 */
async function handleApiResponse(response) {
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    
    if (result.status === 'error') {
        throw new Error(result.error);
    }
    
    return result;
}

/**
 * Handle processing results
 */
function handleResult(result) {
    switch(result.status) {
        case 'success':
            handleSuccessResult(result);
            break;
        case 'verification_failed':
            handleVerificationFailed(result);
            break;
        default:
            addLogEntry(`Unexpected result status: ${result.status}`, 'error', 'System Error');
    }
}

/**
 * Handle successful results
 */
function handleSuccessResult(result) {
    if (currentAction === 'process') {
        // Full processing
        addLogEntry('Document verification completed successfully!', 'success', 'MCP Document Service');
        
        if (result.verification) {
            displayVerificationResult(result.verification);
        }
        
        if (result.summarization) {
            addLogEntry('Text summarization completed successfully!', 'success', 'MCP Summarization Service');
            displaySummarizationResult(result.summarization);
        }
        
    } else if (currentAction === 'verify') {
        // Verification only
        addLogEntry('Document verification completed!', 'success', 'MCP Document Service');
        displayVerificationResult(result.result);
        
    } else if (currentAction === 'summarize') {
        // Summarization only
        addLogEntry('Text summarization completed!', 'success', 'MCP Summarization Service');
        displaySummarizationResult(result.result);
    }
    
    // Show modal with results
    showResultModal(result);
}

/**
 * Handle verification failed
 */
function handleVerificationFailed(result) {
    addLogEntry('Document verification failed!', 'error', 'MCP Document Service');
    
    if (result.verification && result.verification.message) {
        addLogEntry(result.verification.message, 'mcp', 'Verification Details');
    }
}

/**
 * Display verification result
 */
function displayVerificationResult(verification) {
    if (verification.verified) {
        addLogEntry(`✓ Document verified successfully`, 'success', 'Verification Result');
        if (verification.message) {
            addLogEntry(verification.message, 'mcp', 'Verification Details');
        }
    } else {
        addLogEntry(`✗ Document verification failed`, 'error', 'Verification Result');
        if (verification.message) {
            addLogEntry(verification.message, 'mcp', 'Verification Details');
        }
    }
}

/**
 * Display summarization result
 */
function displaySummarizationResult(summarization) {
    if (summarization.summary) {
        addLogEntry(`Summary generated successfully:\n\n${summarization.summary}`, 'success', 'Summary Result');
    }
    
    if (summarization.message && summarization.message !== summarization.summary) {
        addLogEntry(summarization.message, 'mcp', 'Summarization Details');
    }
}

/**
 * Show result modal
 */
function showResultModal(result) {
    const modalBody = document.getElementById('modalBody');
    let content = '';
    
    if (currentAction === 'process' && result.verification && result.summarization) {
        content = `
            <div class="result-section">
                <h5><i class="fas fa-shield-check text-primary"></i> Verification Result</h5>
                <div class="result-content">${formatResultContent(result.verification)}</div>
            </div>
            <div class="result-section">
                <h5><i class="fas fa-file-signature text-info"></i> Summary Result</h5>
                <div class="result-content">${formatResultContent(result.summarization)}</div>
            </div>
        `;
    } else if (result.result) {
        const iconClass = currentAction === 'verify' ? 'fas fa-shield-check text-primary' : 'fas fa-file-signature text-info';
        const title = currentAction === 'verify' ? 'Verification Result' : 'Summary Result';
        
        content = `
            <div class="result-section">
                <h5><i class="${iconClass}"></i> ${title}</h5>
                <div class="result-content">${formatResultContent(result.result)}</div>
            </div>
        `;
    }
    
    modalBody.innerHTML = content;
    $('#resultModal').modal('show');
}

/**
 * Format result content for display
 */
function formatResultContent(result) {
    return JSON.stringify(result, null, 2);
}

/**
 * Copy results to clipboard
 */
function copyResults() {
    const resultContent = document.querySelector('#modalBody .result-content');
    if (resultContent) {
        navigator.clipboard.writeText(resultContent.textContent).then(() => {
            // Show feedback
            const originalText = copyResultBtn.innerHTML;
            copyResultBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
            copyResultBtn.classList.add('btn-success');
            copyResultBtn.classList.remove('btn-primary');
            
            setTimeout(() => {
                copyResultBtn.innerHTML = originalText;
                copyResultBtn.classList.remove('btn-success');
                copyResultBtn.classList.add('btn-primary');
            }, 2000);
        });
    }
}

/**
 * Add log entry to response area
 */
function addLogEntry(message, type = 'system', source = 'System') {
    const entry = document.createElement('div');
    entry.classList.add('log-entry', `log-${type}`);
    
    // Icon mapping
    const icons = {
        user: { symbol: 'U', class: 'user-icon' },
        system: { symbol: 'S', class: 'system-icon' },
        mcp: { symbol: 'M', class: 'mcp-icon' },
        error: { symbol: '!', class: 'error-icon' },
        success: { symbol: '✓', class: 'success-icon' }
    };
    
    const icon = icons[type] || icons.system;
    const timestamp = new Date().toLocaleTimeString();
    
    entry.innerHTML = `
        <span class="agent-icon ${icon.class}">${icon.symbol}</span>
        <strong>[${timestamp}] ${source}:</strong><br>
        ${message.replace(/\n/g, '<br>')}
    `;
    
    // Add to top of response area
    const firstChild = responseArea.firstElementChild;
    if (firstChild && firstChild.classList.contains('initial-message')) {
        responseArea.removeChild(firstChild);
    }
    
    responseArea.insertBefore(entry, responseArea.firstChild);
    
    // Scroll to top
    responseArea.scrollTop = 0;
}

/**
 * Clear initial message
 */
function clearInitialMessage() {
    const initialMessage = responseArea.querySelector('.initial-message');
    if (initialMessage) {
        initialMessage.remove();
    }
}

/**
 * Clear all logs
 */
function clearLogs() {
    responseArea.innerHTML = `
        <div class="initial-message">
            <i class="fas fa-info-circle"></i>
            System ready. Enter document content and access code to begin processing.
        </div>
    `;
}

/**
 * Load sample document
 */
function loadSampleDocument() {
    const sampleDoc = `This is a sample document for testing the MCP Document Exchange System.

The document contains multiple paragraphs of text that can be used to test both document verification and text summarization capabilities.

Key features being tested:
- Document verification through MCP SDK
- Text summarization through MCP SDK  
- Hybrid encryption for secure communication
- Access control mechanisms
- Error handling and user feedback

This sample document should be long enough to provide meaningful summarization results while being short enough for quick testing during development.

The system supports various access codes for different types of operations, allowing fine-grained control over document processing permissions.`;

    const sampleCode = 'DOC001';
    
    document.getElementById('document_content').value = sampleDoc;
    document.getElementById('access_code').value = sampleCode;
    
    addLogEntry('Sample document and access code loaded for testing.', 'system', 'UI Helper');
    
    // Animate the form
    document.querySelector('.form-card').classList.add('bounce');
    setTimeout(() => {
        document.querySelector('.form-card').classList.remove('bounce');
    }, 1000);
}

/**
 * Perform health check
 */
async function performHealthCheck() {
    addLogEntry('Performing system health check...', 'system', 'Health Monitor');
    
    try {
        const response = await fetch('/api/health');
        const result = await response.json();
        
        if (result.status === 'healthy') {
            addLogEntry('System health check passed. All services operational.', 'success', 'Health Monitor');
            updateServiceStatus(result.clients);
        } else {
            addLogEntry(`System health check failed: ${result.error}`, 'error', 'Health Monitor');
            updateServiceStatus({});
        }
        
    } catch (error) {
        addLogEntry(`Health check error: ${error.message}`, 'error', 'Health Monitor');
        updateServiceStatus({});
    }
}

/**
 * Update service status indicators
 */
function updateServiceStatus(clients) {
    // Update status dots
    updateStatusDot(documentServiceStatus, clients.document_client);
    updateStatusDot(summarizationServiceStatus, clients.summarization_client);
    updateStatusDot(connectionStatus, clients.document_client && clients.summarization_client);
}

/**
 * Update individual status dot
 */
function updateStatusDot(element, isOnline) {
    element.className = 'status-dot';
    if (isOnline) {
        element.classList.add('online');
    } else {
        element.classList.add('warning');
    }
}

/**
 * Show loading state
 */
function showLoading() {
    loadingContainer.classList.add('show');
    submitButton.classList.add('loading');
    submitButton.disabled = true;
}

/**
 * Hide loading state
 */
function hideLoading() {
    loadingContainer.classList.remove('show');
    submitButton.classList.remove('loading');
    submitButton.disabled = false;
}

/**
 * Auto-resize textarea
 */
function autoResizeTextarea() {
    const textarea = document.getElementById('document_content');
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 300) + 'px';
}

/**
 * Get action description for logging
 */
function getActionDescription() {
    switch(currentAction) {
        case 'process': return 'document processing (verify + summarize)';
        case 'verify': return 'document verification';
        case 'summarize': return 'text summarization';
        default: return 'unknown action';
    }
}

// Periodic health checks
setInterval(performHealthCheck, 60000); // Every minute
