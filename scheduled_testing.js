/**
 * Scheduled Testing JavaScript Module
 * Handles UI interactions for scheduled testing feature
 */

const SCHEDULED_TESTING_API = `${API_URL}/api/scheduled-tests`;

// Initialize scheduled testing module
function initScheduledTesting() {
    const scheduledTestingBtn = document.getElementById('scheduledTestingBtn');
    const scheduledTestingSection = document.getElementById('scheduledTestingSection');
    const scheduledTestingBackBtn = document.getElementById('scheduledTestingBackBtn');
    const scheduleForm = document.getElementById('scheduleForm');
    const scheduleFrequency = document.getElementById('scheduleFrequency');

    // Show scheduled testing section
    if (scheduledTestingBtn) {
        scheduledTestingBtn.addEventListener('click', () => {
            document.getElementById('landingPage').style.display = 'none';
            document.getElementById('formSection').style.display = 'none';
            document.getElementById('workspaceSection').style.display = 'none';
            scheduledTestingSection.style.display = 'block';
            loadSchedules();
        });
    }

    // Hide scheduled testing section
    if (scheduledTestingBackBtn) {
        scheduledTestingBackBtn.addEventListener('click', () => {
            scheduledTestingSection.style.display = 'none';
            document.getElementById('landingPage').style.display = 'block';
        });
    }

    // Handle frequency change to show/hide relevant fields
    if (scheduleFrequency) {
        scheduleFrequency.addEventListener('change', handleFrequencyChange);
    }

    // Handle form submission
    if (scheduleForm) {
        scheduleForm.addEventListener('submit', handleScheduleSubmit);
    }

    // Initialize form state
    handleFrequencyChange();
}

function handleFrequencyChange() {
    const frequency = document.getElementById('scheduleFrequency').value;
    const timeGroup = document.getElementById('scheduleTimeGroup');
    const daysGroup = document.getElementById('scheduleDaysGroup');
    const intervalGroup = document.getElementById('scheduleIntervalGroup');
    const dateGroup = document.getElementById('scheduleDateGroup');
    const dateInput = document.getElementById('scheduleDate');

    // Hide all groups first
    timeGroup.style.display = 'none';
    daysGroup.style.display = 'none';
    intervalGroup.style.display = 'none';
    dateGroup.style.display = 'none';

    // Remove required attribute from date field initially
    if (dateInput) {
        dateInput.removeAttribute('required');
    }

    // Show relevant groups based on frequency
    if (frequency === 'daily' || frequency === 'weekly') {
        timeGroup.style.display = 'block';
        if (frequency === 'weekly') {
            daysGroup.style.display = 'block';
        }
    } else if (frequency === 'interval') {
        intervalGroup.style.display = 'block';
    } else if (frequency === 'once') {
        dateGroup.style.display = 'block';
        // Set required only when date field is visible
        if (dateInput) {
            dateInput.setAttribute('required', 'required');
        }
    }
}

async function handleScheduleSubmit(e) {
    e.preventDefault();

    const formData = new FormData(e.target);
    const frequency = formData.get('frequency');
    const scheduleData = {
        site_url: formData.get('url'),
        task_description: formData.get('task_description') || '',
        frequency: frequency,
        enabled: document.getElementById('scheduleEnabled').checked
    };

    // Validate and add frequency-specific fields
    if (frequency === 'daily' || frequency === 'weekly') {
        const time = formData.get('time');
        if (!time) {
            alert('Time is required for daily/weekly schedules');
            return;
        }
        scheduleData.time = time;
        if (frequency === 'weekly') {
            const daysCheckboxes = formData.getAll('days_of_week');
            if (daysCheckboxes.length === 0) {
                alert('Please select at least one day for weekly schedule');
                return;
            }
            scheduleData.days_of_week = daysCheckboxes;
        }
    } else if (frequency === 'interval') {
        const hours = parseInt(formData.get('interval_hours')) || 0;
        const minutes = parseInt(formData.get('interval_minutes')) || 0;
        if (hours === 0 && minutes === 0) {
            alert('Interval must be greater than 0');
            return;
        }
        scheduleData.interval_hours = hours;
        scheduleData.interval_minutes = minutes;
    } else if (frequency === 'once') {
        const dateValue = formData.get('date');
        if (!dateValue) {
            alert('Date and time is required for one-time schedules');
            return;
        }
        // Convert datetime-local to ISO format
        scheduleData.date = new Date(dateValue).toISOString();
    }

    // Add email notification settings
    const notifyEmail = formData.get('notify_email');
    if (notifyEmail) {
        scheduleData.notify_email = notifyEmail;
        // Always set these to true backend-side, but sending true for now to be safe with any remaining logic
        scheduleData.notify_on_success = true;
        scheduleData.notify_on_failure = true;
    }

    try {
        const response = await fetch(SCHEDULED_TESTING_API, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(scheduleData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to create schedule');
        }

        const result = await response.json();
        alert('Schedule created successfully!');

        // Reset form and reload schedules
        e.target.reset();
        handleFrequencyChange();
        loadSchedules();
    } catch (error) {
        console.error('Error creating schedule:', error);
        alert('Error: ' + error.message);
    }
}

async function loadSchedules() {
    const schedulesList = document.getElementById('schedulesList');
    if (!schedulesList) return;

    try {
        const response = await fetch(SCHEDULED_TESTING_API);
        if (!response.ok) {
            throw new Error('Failed to load schedules');
        }

        const data = await response.json();
        const schedules = data.schedules || [];

        if (schedules.length === 0) {
            schedulesList.innerHTML = '<p class="schedule-empty">No scheduled tests yet. Create one above!</p>';
            return;
        }

        // Render schedules
        schedulesList.innerHTML = schedules.map(schedule => renderScheduleItem(schedule)).join('');

        // Update Dashboard Stats
        updateDashboardStats(schedules);

        // Attach event listeners
        schedules.forEach(schedule => {
            const toggleBtn = document.getElementById(`toggleSchedule${schedule.id}`);
            const deleteBtn = document.getElementById(`deleteSchedule${schedule.id}`);

            if (toggleBtn) {
                toggleBtn.addEventListener('click', () => toggleSchedule(schedule.id, !schedule.enabled));
            }
            if (deleteBtn) {
                deleteBtn.addEventListener('click', () => deleteSchedule(schedule.id));
            }
        });
    } catch (error) {
        console.error('Error loading schedules:', error);
        schedulesList.innerHTML = '<p class="schedule-error-msg">Error loading schedules: ' + error.message + '</p>';
        // Reset stats on error
        updateDashboardStats([]);
    }
}

function updateDashboardStats(schedules) {
    const totalElement = document.getElementById('statTotal');
    const activeElement = document.getElementById('statActive');
    const successElement = document.getElementById('statSuccess');

    if (!totalElement || !activeElement || !successElement) return;

    const total = schedules.length;
    const active = schedules.filter(s => s.enabled).length;

    // Calculate success rate based on 'last_notification_status' or 'status'
    // Assuming 'status' == 'success' means last run was successful
    const successfulRuns = schedules.filter(s => s.status === 'success').length;
    const successRate = total > 0 ? Math.round((successfulRuns / total) * 100) : 0;

    // Animate numbers (simple implementation)
    totalElement.textContent = total;
    activeElement.textContent = active;
    successElement.textContent = `${successRate}%`;
}

function renderScheduleItem(schedule) {
    const statusColors = {
        'pending': '#999',
        'running': '#667eea',
        'success': '#4ade80',
        'failed': '#f5576c'
    };

    const statusBadgeClass = `status-badge status-${schedule.status || 'pending'}`;
    const statusLabel = (schedule.status || 'pending').toUpperCase();

    // Format schedule description (same as before)
    let scheduleDesc = '';
    if (schedule.frequency === 'daily') {
        scheduleDesc = `Daily at ${schedule.time || '00:00'}`;
    } else if (schedule.frequency === 'weekly') {
        const days = schedule.days_of_week && schedule.days_of_week.length > 0
            ? schedule.days_of_week.join(', ')
            : 'No days selected';
        scheduleDesc = `Weekly on ${days} at ${schedule.time || '00:00'}`;
    } else if (schedule.frequency === 'interval') {
        const hours = schedule.interval_hours || 0;
        const minutes = schedule.interval_minutes || 0;
        scheduleDesc = `Every ${hours > 0 ? hours + 'h ' : ''}${minutes}m`;
    } else if (schedule.frequency === 'once') {
        const date = schedule.schedule_date ? new Date(schedule.schedule_date).toLocaleString() : 'Not set';
        scheduleDesc = `One time: ${date}`;
    }

    const lastRunTime = schedule.last_run_time
        ? new Date(schedule.last_run_time).toLocaleString()
        : 'Never';

    // Icons (SVGs)
    const bellIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>`;
    const trashIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>`;
    const checkIcon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #4ade80;"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    const xIcon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #f5576c;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;

    return `
        <div class="schedule-item">
            <div class="schedule-info">
                <h3>${escapeHtml(schedule.site_url)}</h3>
                <div class="schedule-meta">
                    <p><strong>Schedule:</strong> ${scheduleDesc}</p>
                    ${schedule.task_description ? `<p><strong>Task:</strong> ${escapeHtml(schedule.task_description)}</p>` : ''}
                    <div class="status-row">
                        <strong>Status:</strong> 
                        <span class="${statusBadgeClass}">${statusLabel}</span>
                    </div>
                    <p><strong>Last Run:</strong> ${lastRunTime}</p>
                    ${schedule.notify_email ? `
                        <div class="notification-meta">
                            <span class="meta-icon">${bellIcon}</span>
                            <span>${escapeHtml(schedule.notify_email)}</span>
                            ${schedule.notify_on_success ? checkIcon : ''}
                            ${schedule.notify_on_failure ? xIcon : ''}
                        </div>
                    ` : ''}
                    ${schedule.last_error ? `
                        <p class="error-meta">
                            <strong>Error:</strong> ${escapeHtml(schedule.last_error.substring(0, 100))}
                        </p>
                    ` : ''}
                </div>
            </div>
            <div class="schedule-actions">
                <label class="checkbox-label">
                    <input type="checkbox" ${schedule.enabled ? 'checked' : ''} 
                           onchange="toggleSchedule(${schedule.id}, this.checked)">
                    ${schedule.enabled ? 'Active' : 'Paused'}
                </label>
                <button onclick="deleteSchedule(${schedule.id})" class="delete-btn" title="Delete Schedule">
                    ${trashIcon}
                </button>
            </div>
        </div>
    `;
}

async function toggleSchedule(scheduleId, enabled) {
    try {
        const response = await fetch(`${SCHEDULED_TESTING_API}/${scheduleId}/toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled })
        });

        if (!response.ok) {
            throw new Error('Failed to toggle schedule');
        }

        loadSchedules(); // Reload to update UI
    } catch (error) {
        console.error('Error toggling schedule:', error);
        alert('Error: ' + error.message);
    }
}

async function deleteSchedule(scheduleId) {
    if (!confirm('Are you sure you want to delete this schedule?')) {
        return;
    }

    try {
        const response = await fetch(`${SCHEDULED_TESTING_API}/${scheduleId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to delete schedule');
        }

        loadSchedules(); // Reload to update UI
    } catch (error) {
        console.error('Error deleting schedule:', error);
        alert('Error: ' + error.message);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Test email functionality
async function testEmailNotification() {
    const emailInput = document.getElementById('scheduleNotifyEmail');
    const testResult = document.getElementById('emailTestResult');
    const testBtn = document.getElementById('testEmailBtn');

    const email = emailInput.value.trim();
    if (!email) {
        testResult.innerHTML = '<span style="color: #f5576c;">Please enter an email address</span>';
        return;
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        testResult.innerHTML = '<span style="color: #f5576c;">Invalid email format</span>';
        return;
    }

    testBtn.disabled = true;
    testBtn.textContent = 'Testing...';
    testResult.innerHTML = '<span style="color: #999;">Sending test email...</span>';

    try {
        const response = await fetch(`${API_URL}/api/scheduled-tests/test-email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email })
        });

        const data = await response.json();

        if (data.success) {
            testResult.innerHTML = `<span style="color: #4ade80;">✓ ${data.message}</span>`;
        } else {
            testResult.innerHTML = `<span style="color: #f5576c;">✗ ${data.error || data.message || 'Failed to send test email'}</span>`;
        }
    } catch (error) {
        testResult.innerHTML = `<span style="color: #f5576c;">✗ Error: ${error.message}</span>`;
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = 'Test Email';
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initScheduledTesting);
} else {
    initScheduledTesting();
}

// Attach test email button handler
document.addEventListener('DOMContentLoaded', () => {
    const testEmailBtn = document.getElementById('testEmailBtn');
    if (testEmailBtn) {
        testEmailBtn.addEventListener('click', testEmailNotification);
    }
});

