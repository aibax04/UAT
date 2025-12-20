/**
 * Workspace JavaScript: Handles live browser workspace functionality
 * Manages WebSocket communication, task updates, and browser preview
 */

// Global workspace state
let workspaceSocket = null;
let currentSessionId = null;
let currentTasks = [];

// Make openAgentStatusPopup globally accessible - defined immediately
window.openAgentStatusPopup = function(e) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    // CRITICAL: Only allow popup when workspace is visible
    const workspaceSection = document.getElementById('workspaceSection');
    if (!workspaceSection || workspaceSection.style.display === 'none') {
        console.warn('Workspace is not active. Popup can only be opened from workspace.');
        return false;
    }
    
    const agentPopup = document.getElementById('workspaceAgentPopup');
    const button = e ? e.target.closest('button') : document.getElementById('workspaceAgentStatusBtn');
    
    if (agentPopup && button) {
        console.log('Opening agent status popup');
        
        // Get button position
        const buttonRect = button.getBoundingClientRect();
        const popupContent = agentPopup.querySelector('.workspace-agent-popup-content');
        
        if (popupContent) {
            // Position popup below and to the right of the button
            const topPosition = buttonRect.bottom + 10; // 10px below button
            const leftPosition = buttonRect.left; // Align with button left edge
            
            // Adjust if popup would go off screen
            const maxTop = window.innerHeight - 400; // Leave some space
            const maxLeft = window.innerWidth - 680; // Popup width + margin
            
            popupContent.style.top = Math.min(topPosition, maxTop) + 'px';
            popupContent.style.left = Math.min(leftPosition, maxLeft) + 'px';
        }
        
        agentPopup.style.display = 'flex';
        agentPopup.classList.add('active');
        document.body.style.overflow = 'hidden';
        
        // Call updateAgentStatusPopup if it exists
        if (typeof updateAgentStatusPopup === 'function') {
            updateAgentStatusPopup();
        } else {
            console.log('updateAgentStatusPopup not yet available, popup shown empty');
        }
    } else {
        console.error('Agent popup or button not found');
    }
    return false;
};

// API URL - use existing from script.js (loaded first) or fallback
const WORKSPACE_API_URL = (typeof API_URL !== 'undefined') ? API_URL : window.location.origin;

// Initialize workspace when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Ensure agent popup is hidden on page load
    const agentPopup = document.getElementById('workspaceAgentPopup');
    if (agentPopup) {
        agentPopup.style.display = 'none';
        agentPopup.classList.remove('active');
    }
    
    initWorkspace();
});

function initWorkspace() {
    // Check if socket.io is available
    if (typeof io === 'undefined') {
        console.error('Socket.IO library not loaded');
        return;
    }

    // Workspace button click handler
    const liveWorkspaceBtn = document.getElementById('liveWorkspaceBtn');
    if (liveWorkspaceBtn) {
        liveWorkspaceBtn.addEventListener('click', function() {
            showWorkspace();
        });
    }

    // Close workspace button
    const workspaceCloseBtn = document.getElementById('workspaceCloseBtn');
    if (workspaceCloseBtn) {
        workspaceCloseBtn.addEventListener('click', function() {
            hideWorkspace();
        });
    }

    // Load URL button
    const loadWorkspaceUrlBtn = document.getElementById('loadWorkspaceUrlBtn');
    if (loadWorkspaceUrlBtn) {
        loadWorkspaceUrlBtn.addEventListener('click', loadWorkspaceUrl);
    }

    // Plan tasks button
    const planTasksBtn = document.getElementById('planTasksBtn');
    if (planTasksBtn) {
        planTasksBtn.addEventListener('click', planTasks);
    }

    // Execution control buttons
    const startExecutionBtn = document.getElementById('startExecutionBtn');
    const pauseExecutionBtn = document.getElementById('pauseExecutionBtn');
    const resumeExecutionBtn = document.getElementById('resumeExecutionBtn');
    const stopExecutionBtn = document.getElementById('stopExecutionBtn');

    if (startExecutionBtn) {
        startExecutionBtn.addEventListener('click', startExecution);
    }
    if (pauseExecutionBtn) {
        pauseExecutionBtn.addEventListener('click', pauseExecution);
    }
    if (resumeExecutionBtn) {
        resumeExecutionBtn.addEventListener('click', resumeExecution);
    }
    if (stopExecutionBtn) {
        stopExecutionBtn.addEventListener('click', stopExecution);
    }
    
    // Agent Status Popup - attach handlers
    attachAgentStatusPopupHandlers();
}

// Attach agent status popup handlers
function attachAgentStatusPopupHandlers() {
    // Only attach handlers if workspace is visible
    const workspaceSection = document.getElementById('workspaceSection');
    if (!workspaceSection || workspaceSection.style.display === 'none') {
        return; // Don't attach handlers if workspace is not visible
    }
    
    const agentStatusBtn = document.getElementById('workspaceAgentStatusBtn');
    const agentPopup = document.getElementById('workspaceAgentPopup');
    const agentPopupClose = document.getElementById('workspaceAgentPopupClose');
    
    console.log('Attaching agent status popup handlers...', { agentStatusBtn, agentPopup });
    
    // Ensure popup is hidden by default
    if (agentPopup) {
        agentPopup.style.display = 'none';
        agentPopup.classList.remove('active');
    }
    
    if (agentStatusBtn && agentPopup) {
        // Use event delegation to ensure it works
        agentStatusBtn.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Agent status button clicked - opening popup');
            window.openAgentStatusPopup(e);
            return false;
        };
        console.log('Agent status button handler attached successfully');
    } else {
        console.warn('Agent status button or popup not found');
    }
    
    if (agentPopupClose && agentPopup) {
        const closePopup = () => {
            agentPopup.style.display = 'none';
            agentPopup.classList.remove('active');
            document.body.style.overflow = '';
        };
        
        agentPopupClose.addEventListener('click', closePopup);
        
        // Close on overlay click
        const overlay = agentPopup.querySelector('.workspace-agent-popup-overlay');
        if (overlay) {
            overlay.addEventListener('click', closePopup);
        }
        
        // Close on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && agentPopup.classList.contains('active')) {
                closePopup();
            }
        });
    }
    
    // Agent Chat Integration
    const agentChatInput = document.getElementById('workspaceAgentChatInput');
    const agentChatSend = document.getElementById('workspaceAgentChatSend');
    
    if (agentChatInput && agentChatSend) {
        const sendAgentMessage = () => {
            const message = agentChatInput.value.trim();
            if (!message) return;
            
            // Add user message to chat
            addAgentChatMessage(message, 'user');
            agentChatInput.value = '';
            
            // Send to chatbot API with task context
            sendAgentChatMessage(message);
        };
        
        agentChatSend.addEventListener('click', sendAgentMessage);
        agentChatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendAgentMessage();
            }
        });
    }
}

function showWorkspace() {
    const workspaceSection = document.getElementById('workspaceSection');
    const landingPage = document.getElementById('landingPage');
    const formSection = document.getElementById('formSection');
    const preview = document.getElementById('workspaceBrowserPreview');

    if (workspaceSection) {
        workspaceSection.style.display = 'flex';
    }
    if (landingPage) {
        landingPage.style.display = 'none';
    }
    if (formSection) {
        formSection.style.display = 'none';
    }
    
    // Initialize placeholder class if placeholder exists
    if (preview) {
        const placeholder = preview.querySelector('.workspace-placeholder');
        if (placeholder) {
            preview.classList.add('has-placeholder');
        } else {
            preview.classList.remove('has-placeholder');
        }
    }
    
    // Re-attach agent status popup handlers when workspace is shown
    setTimeout(() => {
        attachAgentStatusPopupHandlers();
    }, 200);
    
    // Focus on URL input
    const urlInput = document.getElementById('workspaceUrl');
    if (urlInput) {
        setTimeout(() => urlInput.focus(), 100);
    }
}

function hideWorkspace() {
    const workspaceSection = document.getElementById('workspaceSection');
    const landingPage = document.getElementById('landingPage');
    const agentPopup = document.getElementById('workspaceAgentPopup');

    // Close agent popup if open
    if (agentPopup) {
        agentPopup.style.display = 'none';
        agentPopup.classList.remove('active');
        document.body.style.overflow = '';
    }

    if (workspaceSection) {
        workspaceSection.style.display = 'none';
    }
    if (landingPage) {
        landingPage.style.display = 'block';
    }
    
    // Disconnect WebSocket if connected
    if (workspaceSocket) {
        workspaceSocket.disconnect();
        workspaceSocket = null;
    }
    
    currentSessionId = null;
    currentTasks = [];
    
    // Reset UI
    resetWorkspaceUI();
}

function resetWorkspaceUI() {
    // Clear inputs
    const urlInput = document.getElementById('workspaceUrl');
    const taskInput = document.getElementById('workspaceTaskInput');
    if (urlInput) urlInput.value = '';
    if (taskInput) taskInput.value = '';
    
    // Clear tasks
    const taskList = document.getElementById('taskList');
    if (taskList) taskList.innerHTML = '';
    
    // Reset buttons
    const planTasksBtn = document.getElementById('planTasksBtn');
    const startExecutionBtn = document.getElementById('startExecutionBtn');
    const pauseExecutionBtn = document.getElementById('pauseExecutionBtn');
    const resumeExecutionBtn = document.getElementById('resumeExecutionBtn');
    const stopExecutionBtn = document.getElementById('stopExecutionBtn');
    
    if (planTasksBtn) planTasksBtn.disabled = true;
    if (startExecutionBtn) startExecutionBtn.disabled = true;
    if (pauseExecutionBtn) pauseExecutionBtn.disabled = true;
    if (resumeExecutionBtn) resumeExecutionBtn.disabled = true;
    if (stopExecutionBtn) stopExecutionBtn.disabled = true;
    
    // Reset preview
    const preview = document.getElementById('workspaceBrowserPreview');
    if (preview) {
        preview.innerHTML = '<div class="workspace-placeholder"><p>Enter a URL and click "Load URL" to start</p></div>';
        preview.classList.add('has-placeholder');
    }
    
    // Reset URL display
    const urlDisplay = document.getElementById('workspaceBrowserUrl');
    if (urlDisplay) {
        urlDisplay.textContent = 'No URL loaded';
    }
    
    updateStatus('Ready to start');
}

function connectWebSocket(sessionId) {
    // Disconnect existing connection
    if (workspaceSocket) {
        workspaceSocket.disconnect();
    }
    
    // Connect to WebSocket
    workspaceSocket = io(WORKSPACE_API_URL, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000
    });

    workspaceSocket.on('connect', function() {
        console.log('WebSocket connected');
        updateStatus('Connected to workspace server');
        // Join session room
        workspaceSocket.emit('join_session', { session_id: sessionId });
    });

    workspaceSocket.on('disconnect', function() {
        console.log('WebSocket disconnected');
        updateStatus('Disconnected from server');
    });

    workspaceSocket.on('connect_error', function(error) {
        console.error('WebSocket connection error:', error);
        updateStatus('Connection error. Retrying...');
    });

    workspaceSocket.on('browser_update', handleBrowserUpdate);
    workspaceSocket.on('task_update', handleTaskUpdate);
}

function handleBrowserUpdate(data) {
    console.log('Browser update received:', data.type, data);

    if (data.type === 'url_loaded' || data.type === 'screenshot') {
        const preview = document.getElementById('workspaceBrowserPreview');
        const urlDisplay = document.getElementById('workspaceBrowserUrl');

        if (preview && data.url) {
            // Remove placeholder
            const placeholder = preview.querySelector('.workspace-placeholder');
            if (placeholder) {
                placeholder.remove();
            }
            preview.classList.remove('has-placeholder');

            // Create or update iframe for live website
            let iframe = preview.querySelector('.browser-iframe');
            if (!iframe) {
                iframe = document.createElement('iframe');
                iframe.className = 'browser-iframe';
                iframe.setAttribute('sandbox', 'allow-same-origin allow-scripts allow-forms allow-popups allow-modals allow-top-navigation');
                preview.innerHTML = '';
                preview.appendChild(iframe);
            }

            // Always update iframe URL to show latest state (force reload)
            const currentSrc = iframe.src;
            const baseUrl = data.url.split('?')[0].split('#')[0];  // Get base URL without params
            const currentBaseUrl = currentSrc.split('?')[0].split('#')[0];
            
            if (currentBaseUrl !== baseUrl || data.force_reload) {
                // Different URL or forced reload - update immediately
                iframe.src = data.url;
                console.log('Iframe updated with URL:', data.url);
            } else {
                // Same URL but need to refresh to show latest state
                // Force reload by appending timestamp
                const separator = data.url.includes('?') ? '&' : '?';
                iframe.src = data.url + separator + '_t=' + Date.now();
                console.log('Iframe refreshed (same URL):', data.url);
            }
            
            // Ensure iframe loads and is scrollable
            iframe.onload = function() {
                try {
                    // Try to access iframe content to ensure it loaded
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                    updateStatus('Page loaded successfully');
                } catch (e) {
                    // Cross-origin restrictions - this is expected for external sites
                    updateStatus('Page loaded (external site)');
                }
            };

            // Update URL display
            if (urlDisplay) {
                urlDisplay.textContent = data.url;
            }
            
            // Update current action display
            const currentActionEl = document.getElementById('workspaceCurrentAction');
            if (currentActionEl) {
                if (data.action || data.task_name) {
                    const actionText = data.task_name 
                        ? `[${data.task_name}] ${data.action || ''}`
                        : (data.action || '');
                    currentActionEl.textContent = actionText;
                    currentActionEl.classList.add('active');
                } else {
                    currentActionEl.textContent = '';
                    currentActionEl.classList.remove('active');
                }
            }

            // Update status if action provided
            if (data.action) {
                updateStatus(data.action);
            } else if (data.type === 'url_loaded') {
                updateStatus('Page loaded');
            }
        }
    } else if (data.type === 'action_start') {
        const preview = document.getElementById('workspaceBrowserPreview');
        if (preview) {
            preview.classList.add('action-active');
        }
        // Show detailed action description
        const actionDesc = data.description || data.action || 'Executing action...';
        const taskName = data.task_name ? `[${data.task_name}] ` : '';
        updateStatus(`${taskName}${actionDesc}`);
        
        // Update current action display
        const currentActionEl = document.getElementById('workspaceCurrentAction');
        if (currentActionEl) {
            currentActionEl.textContent = `${taskName}${actionDesc}`;
            currentActionEl.classList.add('active');
        }
    } else if (data.type === 'action_complete') {
        const preview = document.getElementById('workspaceBrowserPreview');
        if (preview) {
            preview.classList.remove('action-active');
        }
        const actionDesc = data.description || data.action || 'Action';
        updateStatus(`Completed: ${actionDesc}`);
        
        // Clear current action after a delay
        const currentActionEl = document.getElementById('workspaceCurrentAction');
        if (currentActionEl) {
            setTimeout(() => {
                currentActionEl.textContent = '';
                currentActionEl.classList.remove('active');
            }, 1000);
        }
    } else if (data.type === 'button_clicked') {
        // Visual feedback for button clicks
        const preview = document.getElementById('workspaceBrowserPreview');
        if (preview) {
            // Add visual indicator
            preview.classList.add('button-click-indicator');
            setTimeout(() => {
                preview.classList.remove('button-click-indicator');
            }, 1000);
        }
        
        // Update status with button click info
        let statusMsg = `✓ Button Clicked: ${data.description || 'Element'}`;
        if (data.locator_strategy) {
            statusMsg += ` [${data.locator_strategy}]`;
        }
        if (data.healing_used) {
            statusMsg += ' (Self-healed)';
        }
        if (data.confidence) {
            statusMsg += ` [${(data.confidence * 100).toFixed(0)}% confidence]`;
        }
        updateStatus(statusMsg);
        
        // Show notification
        console.log('Button clicked:', data);
    } else if (data.type === 'execution_metadata') {
        // Display execution metadata (locator used, healing, confidence)
        const metadata = data.metadata;
        let statusMsg = data.description || 'Action executed';
        
        if (metadata.locator_strategy) {
            statusMsg += ` [${metadata.locator_strategy}]`;
        }
        
        if (metadata.healing_attempted) {
            if (metadata.healing_successful) {
                statusMsg += ' (Self-healed ✓)';
            } else {
                statusMsg += ' (Healing failed)';
            }
        }
        
        if (metadata.confidence) {
            statusMsg += ` [Confidence: ${(metadata.confidence * 100).toFixed(0)}%]`;
        }
        
        updateStatus(statusMsg);
        
        // Log detailed metadata to console
        console.log('Execution metadata:', metadata);
    } else if (data.type === 'healing_start' || data.type === 'healing_update') {
        updateStatus(data.message || 'Attempting self-healing...');
    } else if (data.type === 'error') {
        updateStatus(`Error: ${data.message || 'Unknown error'}`);
    }
}

function handleTaskUpdate(data) {
    console.log('Task update received:', data);

    if (data.type === 'task_update' && data.task) {
        const task = data.task;
        updateTaskInUI(task);
        
        // Update currentTasks array
        const taskIndex = currentTasks.findIndex(t => (t.id || t.name) === (task.id || task.name));
        if (taskIndex >= 0) {
            currentTasks[taskIndex] = task;
        } else {
            currentTasks.push(task);
        }
        
        // Update status message
        if (task.status === 'running') {
            updateStatus(`Executing: ${task.name || 'Task ' + task.id}`);
        } else if (task.status === 'done') {
            updateStatus(`Completed: ${task.name || 'Task ' + task.id}`);
        } else if (task.status === 'failed') {
            updateStatus(`Failed: ${task.name || 'Task ' + task.id}`);
        }
        
        // Update message if provided
        if (data.message) {
            updateStatus(data.message);
        }
        
        // Update agent status popup
        updateAgentStatusPopup();
    } else if (data.type === 'step_start') {
        // Step-level update
        updateStatus(data.step || data.message || 'Executing step...');
        if (data.task) {
            updateTaskInUI(data.task);
        }
    } else if (data.type === 'step_complete') {
        // Step completed
        const statusMsg = data.success 
            ? `Step completed: ${data.step || data.message || ''}`
            : `Step failed: ${data.step || data.message || ''}`;
        updateStatus(statusMsg);
        if (data.task) {
            updateTaskInUI(data.task);
        }
    } else if (data.type === 'step_error') {
        updateStatus(`Step error: ${data.error || data.message || 'Unknown error'}`);
        if (data.task) {
            updateTaskInUI(data.task);
        }
    } else if (data.type === 'execution_started') {
        updateStatus('Agent execution started');
    } else if (data.type === 'execution_complete') {
        updateStatus('All tasks completed successfully!');
        
        // Reset button states
        const startExecutionBtn = document.getElementById('startExecutionBtn');
        const pauseExecutionBtn = document.getElementById('pauseExecutionBtn');
        const resumeExecutionBtn = document.getElementById('resumeExecutionBtn');
        const stopExecutionBtn = document.getElementById('stopExecutionBtn');
        if (startExecutionBtn) startExecutionBtn.disabled = false;
        if (pauseExecutionBtn) pauseExecutionBtn.disabled = true;
        if (resumeExecutionBtn) resumeExecutionBtn.disabled = true;
        if (stopExecutionBtn) stopExecutionBtn.disabled = true;
    } else if (data.type === 'execution_error') {
        updateStatus(`Error: ${data.error || 'Execution failed'}`);
    } else if (data.type === 'execution_paused') {
        updateStatus('Execution paused');
    } else if (data.type === 'execution_resumed') {
        updateStatus('Execution resumed');
    } else if (data.type === 'execution_stopped') {
        updateStatus('Execution stopped');
    }
}

function updateTaskInUI(task) {
    // Update agent status popup when task changes
    updateAgentStatusPopup();
    const taskList = document.getElementById('taskList');
    if (!taskList) return;

    let taskItem = document.getElementById(`task-${task.id}`);
    
    if (!taskItem) {
        // Create new task item
        taskItem = document.createElement('div');
        taskItem.id = `task-${task.id}`;
        taskList.appendChild(taskItem);
    }

    // Check if task was healed
    const wasHealed = task.metadata && task.metadata.healing_successful;
    const healingClass = wasHealed ? 'task-healed' : '';
    
    // Update task item
    taskItem.className = `task-item ${task.status} ${healingClass}`;
    
    // Add healing indicator
    const healingIndicator = wasHealed 
        ? '<span class="healing-badge" title="This task was self-healed">🔧</span>' 
        : '';
    
    // Add confidence indicator if available
    const confidence = task.metadata && task.metadata.confidence;
    const confidenceBadge = confidence 
        ? `<span class="confidence-badge" title="Locator confidence: ${(confidence * 100).toFixed(0)}%">${(confidence * 100).toFixed(0)}%</span>`
        : '';
    
    taskItem.innerHTML = `
        <div class="task-item-header">
            <span class="task-item-name">${task.name || 'Task ' + task.id} ${healingIndicator} ${confidenceBadge}</span>
            <span class="task-item-status ${task.status}">${task.status}</span>
        </div>
        <div class="task-item-description">${task.description || ''}</div>
    `;

    // Update currentTasks array
    const index = currentTasks.findIndex(t => t.id === task.id);
    if (index >= 0) {
        currentTasks[index] = task;
    } else {
        currentTasks.push(task);
    }

    // Scroll to current task if running
    if (task.status === 'running') {
        taskItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

async function loadWorkspaceUrl() {
    const urlInput = document.getElementById('workspaceUrl');
    const url = urlInput?.value.trim();

    if (!url) {
        updateStatus('Please enter a URL');
        urlInput?.focus();
        return;
    }

    // Validate URL
    try {
        new URL(url);
    } catch (e) {
        updateStatus('Please enter a valid URL (e.g., https://example.com)');
        urlInput?.focus();
        return;
    }

    updateStatus('Creating workspace session...');
    
    // Disable input while loading
    if (urlInput) urlInput.disabled = true;
    const loadBtn = document.getElementById('loadWorkspaceUrlBtn');
    if (loadBtn) {
        loadBtn.disabled = true;
        loadBtn.textContent = 'Loading...';
    }

    try {
        const response = await fetch(`${WORKSPACE_API_URL}/api/workspace/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url,
                socket_id: workspaceSocket?.id || null
            })
        });

        const data = await response.json();

        if (response.ok && data.session_id) {
            currentSessionId = data.session_id;
            connectWebSocket(currentSessionId);
            updateStatus('Workspace created. Loading page...');
            
            // Enable plan tasks button
            const planTasksBtn = document.getElementById('planTasksBtn');
            if (planTasksBtn) {
                planTasksBtn.disabled = false;
            }
            
            // Focus on task input
            const taskInput = document.getElementById('workspaceTaskInput');
            if (taskInput) {
                setTimeout(() => taskInput.focus(), 500);
            }
        } else {
            updateStatus('Error: ' + (data.error || 'Failed to create workspace'));
            // Re-enable input
            if (urlInput) urlInput.disabled = false;
        }
    } catch (error) {
        console.error('Error loading workspace URL:', error);
        updateStatus('Error: ' + error.message);
        // Re-enable input
        if (urlInput) urlInput.disabled = false;
    } finally {
        // Reset load button
        if (loadBtn) {
            loadBtn.disabled = false;
            loadBtn.textContent = 'Load URL';
        }
    }
}

async function planTasks() {
    const taskInput = document.getElementById('workspaceTaskInput');
    const instruction = taskInput?.value.trim();

    if (!instruction) {
        updateStatus('Please enter task instructions');
        taskInput?.focus();
        return;
    }

    if (!currentSessionId) {
        updateStatus('Please load a URL first');
        return;
    }

    updateStatus('Planning tasks with AI...');
    
    // Disable input while planning
    if (taskInput) taskInput.disabled = true;
    const planBtn = document.getElementById('planTasksBtn');
    if (planBtn) {
        planBtn.disabled = true;
        planBtn.textContent = 'Planning...';
    }

    try {
        const response = await fetch(`${WORKSPACE_API_URL}/api/workspace/${currentSessionId}/plan-tasks`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                instruction: instruction
            })
        });

        const data = await response.json();

        if (response.ok && data.tasks) {
            currentTasks = data.tasks || [];
            renderTasks(currentTasks);
            updateStatus(`Planned ${currentTasks.length} tasks. Ready to start!`);
            
            // Update agent status popup with new tasks
            updateAgentStatusPopup();
            
            // Enable start button
            const startExecutionBtn = document.getElementById('startExecutionBtn');
            if (startExecutionBtn) {
                startExecutionBtn.disabled = false;
                startExecutionBtn.focus();
            }
            
            // Re-enable task input for editing
            if (taskInput) taskInput.disabled = false;
        } else {
            updateStatus('Error: ' + (data.error || 'Failed to plan tasks'));
            if (taskInput) taskInput.disabled = false;
        }
    } catch (error) {
        console.error('Error planning tasks:', error);
        updateStatus('Error: ' + error.message);
        if (taskInput) taskInput.disabled = false;
    } finally {
        // Reset plan button
        if (planBtn) {
            planBtn.disabled = false;
            planBtn.textContent = 'Plan Tasks';
        }
    }
}

function renderTasks(tasks) {
    const taskList = document.getElementById('taskList');
    if (!taskList) return;

    taskList.innerHTML = '';

    if (tasks.length === 0) {
        taskList.innerHTML = '<p style="color: #666; text-align: center; padding: 20px; font-size: 13px;">No tasks planned yet</p>';
        return;
    }

    tasks.forEach((task, index) => {
        const taskItem = document.createElement('div');
        taskItem.id = `task-${task.id}`;
        taskItem.className = `task-item ${task.status || 'pending'}`;
        
        taskItem.innerHTML = `
            <div class="task-item-header">
                <span class="task-item-name">${task.name || 'Task ' + (index + 1)}</span>
                <span class="task-item-status ${task.status || 'pending'}">${task.status || 'pending'}</span>
            </div>
            <div class="task-item-description">${task.description || ''}</div>
        `;
        
        taskList.appendChild(taskItem);
    });
}

async function startExecution() {
    if (!currentSessionId) {
        updateStatus('No active session');
        return;
    }

    if (currentTasks.length === 0) {
        updateStatus('No tasks to execute. Please plan tasks first.');
        return;
    }

    updateStatus('Starting task execution...');

    try {
        const response = await fetch(`${WORKSPACE_API_URL}/api/workspace/${currentSessionId}/start`, {
            method: 'POST'
        });

        if (response.ok) {
            updateStatus('Executing tasks...');
            
            // Update button states
            const startExecutionBtn = document.getElementById('startExecutionBtn');
            const pauseExecutionBtn = document.getElementById('pauseExecutionBtn');
            const stopExecutionBtn = document.getElementById('stopExecutionBtn');

            if (startExecutionBtn) startExecutionBtn.disabled = true;
            if (pauseExecutionBtn) pauseExecutionBtn.disabled = false;
            if (stopExecutionBtn) stopExecutionBtn.disabled = false;
        } else {
            const data = await response.json();
            updateStatus('Error: ' + (data.error || 'Failed to start execution'));
        }
    } catch (error) {
        console.error('Error starting execution:', error);
        updateStatus('Error: ' + error.message);
    }
}

async function pauseExecution() {
    if (!currentSessionId) return;

    try {
        const response = await fetch(`${WORKSPACE_API_URL}/api/workspace/${currentSessionId}/pause`, {
            method: 'POST'
        });

        if (response.ok) {
            const pauseExecutionBtn = document.getElementById('pauseExecutionBtn');
            const resumeExecutionBtn = document.getElementById('resumeExecutionBtn');

            if (pauseExecutionBtn) pauseExecutionBtn.disabled = true;
            if (resumeExecutionBtn) resumeExecutionBtn.disabled = false;

            updateStatus('Execution paused');
        }
    } catch (error) {
        console.error('Error pausing execution:', error);
        updateStatus('Error pausing execution');
    }
}

async function resumeExecution() {
    if (!currentSessionId) return;

    try {
        const response = await fetch(`${WORKSPACE_API_URL}/api/workspace/${currentSessionId}/resume`, {
            method: 'POST'
        });

        if (response.ok) {
            const pauseExecutionBtn = document.getElementById('pauseExecutionBtn');
            const resumeExecutionBtn = document.getElementById('resumeExecutionBtn');

            if (pauseExecutionBtn) pauseExecutionBtn.disabled = false;
            if (resumeExecutionBtn) resumeExecutionBtn.disabled = true;

            updateStatus('Execution resumed');
        }
    } catch (error) {
        console.error('Error resuming execution:', error);
        updateStatus('Error resuming execution');
    }
}

async function stopExecution() {
    if (!currentSessionId) return;

    try {
        const response = await fetch(`${WORKSPACE_API_URL}/api/workspace/${currentSessionId}/stop`, {
            method: 'POST'
        });

        if (response.ok) {
            // Reset button states
            const startExecutionBtn = document.getElementById('startExecutionBtn');
            const pauseExecutionBtn = document.getElementById('pauseExecutionBtn');
            const resumeExecutionBtn = document.getElementById('resumeExecutionBtn');
            const stopExecutionBtn = document.getElementById('stopExecutionBtn');

            if (startExecutionBtn) startExecutionBtn.disabled = false;
            if (pauseExecutionBtn) pauseExecutionBtn.disabled = true;
            if (resumeExecutionBtn) resumeExecutionBtn.disabled = true;
            if (stopExecutionBtn) stopExecutionBtn.disabled = true;

            updateStatus('Execution stopped');
        }
    } catch (error) {
        console.error('Error stopping execution:', error);
        updateStatus('Error stopping execution');
    }
}


function updateStatus(message) {
    const statusElement = document.getElementById('workspaceStatus');
    if (statusElement) {
        const p = statusElement.querySelector('p');
        if (p) {
            p.textContent = message;
            console.log('[Workspace Status]:', message);
        }
    }
    
    // Update agent status popup if open
    updateAgentStatusPopup();
}

// Update Agent Status Popup
function updateAgentStatusPopup() {
    const currentActionEl = document.getElementById('workspaceAgentCurrentAction');
    const taskChecklistEl = document.getElementById('workspaceAgentTaskChecklist');
    
    if (!currentActionEl || !taskChecklistEl) return;
    
    // Update current action
    const statusEl = document.getElementById('workspaceStatus');
    const currentAction = statusEl ? statusEl.querySelector('p')?.textContent || 'Ready' : 'Ready';
    currentActionEl.innerHTML = `<p class="workspace-agent-action-text">${currentAction}</p>`;
    
    // Update task checklist
    if (currentTasks && currentTasks.length > 0) {
        const checklistHTML = currentTasks.map(task => {
            const taskId = task.id || 'unknown';
            const taskName = task.name || `Task ${taskId}`;
            const taskDesc = task.description || '';
            const taskStatus = task.status || 'pending';
            const isChecked = taskStatus === 'done';
            const hasError = taskStatus === 'failed';
            const isRunning = taskStatus === 'running';
            
            let statusIcon = '⏳';
            let statusClass = 'pending';
            if (isChecked) {
                statusIcon = '✅';
                statusClass = 'done';
            } else if (hasError) {
                statusIcon = '❌';
                statusClass = 'failed';
            } else if (isRunning) {
                statusIcon = '🔄';
                statusClass = 'running';
            }
            
            return `
                <div class="workspace-agent-task-item ${statusClass}">
                    <input type="checkbox" 
                           class="workspace-agent-task-checkbox" 
                           ${isChecked ? 'checked' : ''} 
                           disabled>
                    <div class="workspace-agent-task-content">
                        <div class="workspace-agent-task-header">
                            <span class="workspace-agent-task-icon">${statusIcon}</span>
                            <span class="workspace-agent-task-name">${taskName}</span>
                        </div>
                        ${taskDesc ? `<div class="workspace-agent-task-desc">${taskDesc}</div>` : ''}
                        ${hasError && task.metadata?.error ? `
                            <div class="workspace-agent-task-error">Error: ${task.metadata.error}</div>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
        
        taskChecklistEl.innerHTML = checklistHTML;
    } else {
        taskChecklistEl.innerHTML = '<p class="workspace-agent-empty">No tasks yet. Plan tasks to see them here.</p>';
    }
}

// Add message to agent chat
function addAgentChatMessage(message, sender) {
    const chatMessages = document.getElementById('agentChatMessages');
    if (!chatMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `agent-chat-msg agent-chat-${sender}`;
    
    const content = document.createElement('p');
    content.textContent = message;
    messageDiv.appendChild(content);
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Send message to chatbot with task context
async function sendAgentChatMessage(userMessage) {
    try {
        // Build task context for chatbot
        const taskContext = {
            current_tasks: currentTasks,
            total_tasks: currentTasks.length,
            completed_tasks: currentTasks.filter(t => t.status === 'done').length,
            failed_tasks: currentTasks.filter(t => t.status === 'failed').length,
            running_tasks: currentTasks.filter(t => t.status === 'running').length,
            pending_tasks: currentTasks.filter(t => t.status === 'pending').length,
            session_id: currentSessionId,
            current_action: document.getElementById('workspaceStatus')?.querySelector('p')?.textContent || 'N/A'
        };
        
        // Get task details for context
        const taskDetails = currentTasks.map(task => ({
            id: task.id,
            name: task.name,
            description: task.description,
            status: task.status,
            action_type: task.action_type,
            error: task.metadata?.error || null,
            execution_time: task.execution_time || null
        }));
        
        const response = await fetch(`${WORKSPACE_API_URL}/api/chatbot`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: userMessage,
                context: {
                    type: 'workspace_tasks',
                    task_context: taskContext,
                    task_details: taskDetails
                },
                history: []
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to get chatbot response');
        }
        
        const data = await response.json();
        addAgentChatMessage(data.response || data.message || 'I apologize, but I couldn\'t process your request.', 'bot');
    } catch (error) {
        console.error('Error sending agent chat message:', error);
        addAgentChatMessage('Sorry, I encountered an error. Please try again.', 'bot');
    }
}