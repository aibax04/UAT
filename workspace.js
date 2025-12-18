/**
 * Workspace JavaScript: Handles live browser workspace functionality
 * Manages WebSocket communication, task updates, and browser preview
 */

// Global workspace state
let workspaceSocket = null;
let currentSessionId = null;
let currentTasks = [];

// API URL - use existing from script.js (loaded first) or fallback
// script.js declares: const API_URL = 'http://localhost:5000';
// We'll use that if available, otherwise use window.location.origin
const WORKSPACE_API_URL = (typeof API_URL !== 'undefined') ? API_URL : window.location.origin;

// Initialize workspace when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
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
    
    // Focus on URL input
    const urlInput = document.getElementById('workspaceUrl');
    if (urlInput) {
        setTimeout(() => urlInput.focus(), 100);
    }
}

function hideWorkspace() {
    const workspaceSection = document.getElementById('workspaceSection');
    const landingPage = document.getElementById('landingPage');

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

            // Update iframe URL (force reload if same URL)
            const currentSrc = iframe.src;
            if (currentSrc !== data.url) {
                iframe.src = data.url;
                console.log('Iframe loaded with URL:', data.url);
            } else {
                // Force reload by appending timestamp
                iframe.src = data.url + (data.url.includes('?') ? '&' : '?') + '_t=' + Date.now();
            }
            
            // Ensure iframe loads and is scrollable
            iframe.onload = function() {
                try {
                    // Try to access iframe content to ensure it loaded
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                    updateStatus('Page loaded successfully');
                } catch (e) {
                    // Cross-origin restrictions - this is expected for external sites
                    // The iframe will still display and be scrollable
                    updateStatus('Page loaded (external site)');
                }
            };

            // Update URL display
            if (urlDisplay) {
                urlDisplay.textContent = data.url;
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
        if (data.action) {
            updateStatus(`Executing: ${data.action}`);
        }
    } else if (data.type === 'action_complete') {
        const preview = document.getElementById('workspaceBrowserPreview');
        if (preview) {
            preview.classList.remove('action-active');
        }
        updateStatus('Action completed');
    } else if (data.type === 'error') {
        updateStatus(`Error: ${data.message || 'Unknown error'}`);
    }
}

function handleTaskUpdate(data) {
    console.log('Task update received:', data);

    if (data.type === 'task_update' && data.task) {
        const task = data.task;
        updateTaskInUI(task);
        
        // Update status message
        if (task.status === 'running') {
            updateStatus(`Executing: ${task.name || 'Task ' + task.id}`);
        } else if (task.status === 'done') {
            updateStatus(`Completed: ${task.name || 'Task ' + task.id}`);
        } else if (task.status === 'failed') {
            updateStatus(`Failed: ${task.name || 'Task ' + task.id}`);
        }
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
    const taskList = document.getElementById('taskList');
    if (!taskList) return;

    let taskItem = document.getElementById(`task-${task.id}`);
    
    if (!taskItem) {
        // Create new task item
        taskItem = document.createElement('div');
        taskItem.id = `task-${task.id}`;
        taskList.appendChild(taskItem);
    }

    // Update task item
    taskItem.className = `task-item ${task.status}`;
    
    taskItem.innerHTML = `
        <div class="task-item-header">
            <span class="task-item-name">${task.name || 'Task ' + task.id}</span>
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
}

