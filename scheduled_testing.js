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
            schedulesList.innerHTML = '<p style="color: #666; text-align: center; padding: 20px;">No scheduled tests yet. Create one above!</p>';
            return;
        }
        
        // Render schedules
        schedulesList.innerHTML = schedules.map(schedule => renderScheduleItem(schedule)).join('');
        
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
        schedulesList.innerHTML = '<p style="color: #f5576c; text-align: center; padding: 20px;">Error loading schedules: ' + error.message + '</p>';
    }
}

function renderScheduleItem(schedule) {
    const statusColors = {
        'pending': '#999',
        'running': '#667eea',
        'success': '#4ade80',
        'failed': '#f5576c'
    };
    
    const statusColor = statusColors[schedule.status] || '#999';
    
    // Format schedule description
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
    
    return `
        <div style="border: 1px solid #333; border-radius: 8px; padding: 20px; margin-bottom: 15px; background: #111;">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 15px;">
                <div style="flex: 1;">
                    <h3 style="color: #fff; margin: 0 0 10px 0;">${escapeHtml(schedule.site_url)}</h3>
                    <p style="color: #999; margin: 0 0 5px 0; font-size: 14px;">
                        <strong>Schedule:</strong> ${scheduleDesc}
                    </p>
                    ${schedule.task_description ? `
                        <p style="color: #999; margin: 5px 0; font-size: 14px;">
                            <strong>Task:</strong> ${escapeHtml(schedule.task_description)}
                        </p>
                    ` : ''}
                    <p style="color: #999; margin: 5px 0; font-size: 14px;">
                        <strong>Status:</strong> 
                        <span style="color: ${statusColor};">${schedule.status || 'pending'}</span>
                    </p>
                    <p style="color: #999; margin: 5px 0; font-size: 14px;">
                        <strong>Last Run:</strong> ${lastRunTime}
                    </p>
                    ${schedule.last_error ? `
                        <p style="color: #f5576c; margin: 5px 0; font-size: 12px;">
                            <strong>Error:</strong> ${escapeHtml(schedule.last_error.substring(0, 100))}
                        </p>
                    ` : ''}
                </div>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <label style="display: flex; align-items: center; color: #fff; cursor: pointer;">
                        <input type="checkbox" ${schedule.enabled ? 'checked' : ''} 
                               onchange="toggleSchedule(${schedule.id}, this.checked)" 
                               style="margin-right: 5px;">
                        ${schedule.enabled ? 'Enabled' : 'Disabled'}
                    </label>
                    <button onclick="deleteSchedule(${schedule.id})" 
                            style="background: #f5576c; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">
                        Delete
                    </button>
                </div>
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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initScheduledTesting);
} else {
    initScheduledTesting();
}

