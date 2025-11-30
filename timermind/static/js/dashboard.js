let currentSessionId = null;
let thoughtProcessLog = [];
let timerRationales = new Map(); // Store rationales by timer ID
let cachedTimers = []; // Cache timers for timeline rendering

// Load initial data
window.onload = function() {
    loadTimers();
    loadPreferences();
};

function switchTab(tabName) {
    // Remove active class only from chat panel tabs and content
    const chatPanel = document.querySelector('.chat-container');
    chatPanel.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    chatPanel.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    // Add active class to selected tab and content
    const selectedTab = event.target;
    selectedTab.classList.add('active');

    if (tabName === 'chat') {
        document.getElementById('chatTab').classList.add('active');
    } else if (tabName === 'thoughts') {
        document.getElementById('thoughtsTab').classList.add('active');
    }
}

function addThought(type, content, metadata = {}) {
    const timestamp = new Date().toLocaleTimeString();
    const thought = { type, content, metadata, timestamp };
    thoughtProcessLog.push(thought);

    const thoughtDiv = document.getElementById('thoughtProcess');
    const thoughtItem = document.createElement('div');
    thoughtItem.className = `thought-item ${type}`;

    let typeLabel = type === 'tool-call' ? 'Tool Call' :
                   type === 'delegation' ? 'Delegation' :
                   type === 'response' ? 'Response' : 'Event';

    thoughtItem.innerHTML = `<span class="timestamp">${timestamp}</span> <span class="event-type">${typeLabel}</span> ${content}`;

    thoughtDiv.appendChild(thoughtItem);
    thoughtDiv.scrollTop = thoughtDiv.scrollHeight;
}

function clearThoughts() {
    // DO NOT clear thoughtProcessLog - we want to preserve the full session history
    // Just add a separator to indicate a new message is being processed
    const thoughtDiv = document.getElementById('thoughtProcess');

    // Add a visual separator for new message
    const separator = document.createElement('div');
    separator.className = 'thought-item';
    separator.style.borderTop = '2px solid #ddd';
    separator.style.marginTop = '10px';
    separator.style.paddingTop = '10px';
    separator.innerHTML = `
        <div class="event-type">New Message</div>
        <div>Processing...</div>
    `;
    thoughtDiv.appendChild(separator);
    thoughtDiv.scrollTop = thoughtDiv.scrollHeight;
}

async function sendMessage() {
    const input = document.getElementById('userInput');
    const message = input.value.trim();
    if (!message) return;

    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;
    input.disabled = true;

    // Add user message to chat
    addMessage(message, 'user');
    input.value = '';

    // Clear and prepare thought process
    clearThoughts();
    addThought('event', `User message: "${message}"`);

    try {
        addThought('event', 'Sending request to TimerMind orchestrator...');

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                session_id: currentSessionId
            })
        });

        const data = await response.json();

        if (response.ok) {
            // Add assistant response
            addMessage(data.response, 'assistant');

            // Update session ID
            currentSessionId = data.session_id;
            document.getElementById('sessionInfo').textContent =
                `Session: ${currentSessionId.substring(0, 8)}...`;

            // Display execution trace from backend
            if (data.execution_trace && data.execution_trace.length > 0) {
                for (const event of data.execution_trace) {
                    let category = event.event_category || 'event';
                    let content = `${event.type}`;

                    if (event.agent) {
                        content += ` → Agent: ${event.agent}`;
                    }
                    if (event.tool_name) {
                        content += ` → 🔧 ${event.tool_name}`;

                        // Check if this is a memory-related tool call
                        if (event.tool_name === 'load_memory' || event.tool_name === 'preload_memory') {
                            addMemoryEvent(event.tool_name, event.tool_args || 'Memory operation');
                        }

                        if (event.tool_args) {
                            content += `\nArgs: ${event.tool_args}`;
                        }
                    }
                    if (event.content_preview) {
                        content += `\n💬 ${event.content_preview}`;
                    }

                    addThought(category, content);
                }
            } else {
                addThought('response', `Response: ${data.response}`);
            }

            // Refresh timers and preferences
            updateTimersList(data.timers);
            loadPreferences();
        } else {
            addMessage(`Error: ${data.detail}`, 'assistant');
            addThought('error', `Error: ${data.detail}`);
        }
    } catch (error) {
        addMessage(`Error: ${error.message}`, 'assistant');
        addThought('error', `Network error: ${error.message}`);
    }

    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
}

function addMessage(text, type) {
    const messagesDiv = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = text;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

async function loadTimers() {
    try {
        const response = await fetch('/api/timers');
        const data = await response.json();
        updateTimersList(data.timers);
    } catch (error) {
        console.error('Error loading timers:', error);
    }
}

function updateTimersList(timers) {
    const listDiv = document.getElementById('timersList');

    // Cache timers for timeline view
    cachedTimers = timers || [];

    if (!timers || timers.length === 0) {
        listDiv.innerHTML = '<div class="empty-state">No timers yet. Start by telling me about your tasks!</div>';
        return;
    }

    // Clear and rebuild rationales map
    timerRationales.clear();
    timers.forEach(timer => {
        timerRationales.set(timer.id, timer.rationale || 'No explanation available');
    });

    // Sort by deadline (earliest first), then by urgency if no deadline
    timers.sort((a, b) => {
        // Timers without deadlines go to the end
        if (!a.deadline && !b.deadline) return 0;
        if (!a.deadline) return 1;
        if (!b.deadline) return -1;

        // Compare deadlines
        return new Date(a.deadline) - new Date(b.deadline);
    });

    listDiv.innerHTML = timers.map(timer => {
        const urgencyClass = timer.urgency_score > 0.7 ? 'high-urgency' :
                            timer.urgency_score > 0.4 ? 'medium-urgency' : 'low-urgency';

        const deadline = timer.deadline ?
            new Date(timer.deadline).toLocaleString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit'
            }) : 'No deadline';

        const countdownHtml = timer.deadline ? createCountdownBar(timer.deadline, timer.id, timer.rationale) : createNoDeadlineBar(timer.id, timer.rationale);

        return `
            <div class="timer-item ${urgencyClass}">
                <div class="timer-header">
                    <div class="timer-label">${timer.label}</div>
                    <span class="timer-category">${timer.category}</span>
                </div>
                ${countdownHtml}
            </div>
        `;
    }).join('');
}

// Logarithmic countdown bar - non-linear scale
// Scale: |---minutes---|--hours--|--days--|months|yr|
// Total range: 0 (now) to 1 year
function createCountdownBar(deadlineStr, timerId, rationale) {
    const deadline = new Date(deadlineStr);
    const now = new Date();
    const msRemaining = deadline - now;

    // Time constants in milliseconds
    const MINUTE = 60 * 1000;
    const HOUR = 60 * MINUTE;
    const DAY = 24 * HOUR;
    const MONTH = 30 * DAY;
    const YEAR = 365 * DAY;

    // Calculate position on logarithmic scale (0 = now, 100 = 1 year+)
    // Scale segments: 0-40% for minutes (0-60min), 40-65% for hours (1-24h),
    // 65-85% for days (1-30d), 85-95% for months (1-12mo), 95-100% for year+
    let position;
    let timeLeftText;
    let timeLeftClass = '';

    if (msRemaining <= 0) {
        position = 0;
        timeLeftText = 'OVERDUE';
        timeLeftClass = 'overdue';
    } else if (msRemaining < HOUR) {
        // 0-60 minutes → 0-40% of bar
        const minutes = msRemaining / MINUTE;
        position = (minutes / 60) * 40;
        timeLeftText = `${Math.ceil(minutes)} min`;
        timeLeftClass = 'urgent';
    } else if (msRemaining < DAY) {
        // 1-24 hours → 40-65% of bar
        const hours = msRemaining / HOUR;
        position = 40 + ((hours - 1) / 23) * 25;
        timeLeftText = `${Math.floor(hours)} hr ${Math.floor((msRemaining % HOUR) / MINUTE)} min`;
        if (hours < 6) timeLeftClass = 'urgent';
    } else if (msRemaining < MONTH) {
        // 1-30 days → 65-85% of bar
        const days = msRemaining / DAY;
        position = 65 + ((days - 1) / 29) * 20;
        timeLeftText = `${Math.floor(days)} day${days >= 2 ? 's' : ''} ${Math.floor((msRemaining % DAY) / HOUR)} hr`;
    } else if (msRemaining < YEAR) {
        // 1-12 months → 85-95% of bar
        const months = msRemaining / MONTH;
        position = 85 + ((months - 1) / 11) * 10;
        timeLeftText = `${Math.floor(months)} month${months >= 2 ? 's' : ''}`;
    } else {
        // 1+ years → 95-100% of bar
        position = Math.min(100, 95 + (msRemaining / YEAR - 1) * 5);
        const years = msRemaining / YEAR;
        timeLeftText = `${Math.floor(years)} year${years >= 2 ? 's' : ''}`;
    }

    // Create tick marks for the scale
    const ticks = [
        { pos: 0, label: 'now' },
        { pos: 20, label: '30m' },
        { pos: 40, label: '1h' },
        { pos: 52.5, label: '12h' },
        { pos: 65, label: '1d' },
        { pos: 75, label: '15d' },
        { pos: 85, label: '1mo' },
        { pos: 90, label: '6mo' },
        { pos: 95, label: '1y' },
    ];

    const tickMarks = ticks.map(t =>
        `<span class="tick-mark" style="left: ${t.pos}%">${t.label}</span>`
    ).join('');

    // Calculate the width of the inner gradient so it spans the full bar
    // If fill is at X%, inner gradient should be (100/X * 100)% to span full bar width
    const innerWidth = position > 0 ? (100 / position) * 100 : 100;

    const deadlineText = deadline.toLocaleString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });

    return `
        <div class="countdown-container">
            <div class="countdown-bar">
                <div class="countdown-fill" style="width: ${position}%; --inner-width: ${innerWidth}%"></div>
            </div>
            <div class="countdown-scale">${tickMarks}</div>
            <div class="countdown-info">
                <span class="countdown-time-left ${timeLeftClass}">${timeLeftText} remaining</span>
                <span class="countdown-deadline">Due: ${deadlineText}</span>
            </div>
            <div class="timer-actions">
                <button class="btn-icon btn-why" onclick="showRationale(${timerId})" title="Why is this important?">?</button>
                <button class="btn-icon btn-complete" onclick="completeTimer(${timerId})" title="Complete">✓</button>
                <button class="btn-icon btn-delete" onclick="deleteTimer(${timerId})" title="Delete">✕</button>
            </div>
        </div>
    `;
}

function createNoDeadlineBar(timerId, rationale) {
    return `
        <div class="countdown-container">
            <div class="countdown-info">
                <span class="countdown-time-left">No deadline</span>
                <span></span>
            </div>
            <div class="timer-actions">
                <button class="btn-icon btn-why" onclick="showRationale(${timerId})" title="Why is this important?">?</button>
                <button class="btn-icon btn-complete" onclick="completeTimer(${timerId})" title="Complete">✓</button>
                <button class="btn-icon btn-delete" onclick="deleteTimer(${timerId})" title="Delete">✕</button>
            </div>
        </div>
    `;
}

// Update countdown bars every second
setInterval(() => {
    const timersList = document.getElementById('timersList');
    if (timersList.querySelector('.countdown-container')) {
        loadTimers();
    }
}, 60000); // Update every minute to avoid excessive refreshes

async function loadPreferences() {
    try {
        const response = await fetch('/api/preferences');
        const data = await response.json();
        updatePreferencesDisplay(data.preferences);
    } catch (error) {
        console.error('Error loading preferences:', error);
    }
}

function updatePreferencesDisplay(prefs) {
    const contentDiv = document.getElementById('preferencesContent');

    if (!prefs || Object.keys(prefs).length === 0) {
        contentDiv.innerHTML = '<div class="empty-state">No preferences set yet.</div>';
        return;
    }

    let html = '';

    // Rules
    if (prefs.rules && prefs.rules.length > 0) {
        html += '<div class="pref-section"><h3>Rules</h3>';
        for (const rule of prefs.rules) {
            html += `<div style="padding: 4px 0; font-size: 0.9em;">• ${rule.description}</div>`;
        }
        html += '</div>';
    }

    contentDiv.innerHTML = html || '<div class="empty-state">No preferences configured.</div>';
}

async function resetData() {
    if (!confirm('This will delete all timers and preferences. Continue?')) return;

    try {
        const response = await fetch('/api/reset', { method: 'POST' });
        if (response.ok) {
            currentSessionId = null;
            document.getElementById('sessionInfo').textContent = 'Session: None';
            loadTimers();
            loadPreferences();

            // Clear chat except first message
            const chatMessages = document.getElementById('chatMessages');
            chatMessages.innerHTML = `
                <div class="message assistant">
                    Data reset! I'm TimerMind. Tell me about tasks you need to track, or let me know your priorities.
                </div>
            `;
        }
    } catch (error) {
        alert('Error resetting data: ' + error.message);
    }
}

async function completeTimer(timerId) {
    try {
        const response = await fetch(`/api/timers/${timerId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'completed' })
        });
        if (response.ok) {
            loadTimers();
        }
    } catch (error) {
        alert('Error completing timer: ' + error.message);
    }
}

async function deleteTimer(timerId) {
    if (!confirm('Delete this timer?')) return;

    try {
        const response = await fetch(`/api/timers/${timerId}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            loadTimers();
        }
    } catch (error) {
        alert('Error deleting timer: ' + error.message);
    }
}

function showRationale(timerId) {
    const rationale = timerRationales.get(timerId) || 'No explanation available';
    alert('Why this matters:\n\n' + rationale);
}

async function loadMemories() {
    try {
        const response = await fetch('/api/memories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId
            })
        });
        const data = await response.json();
        updateMemoriesDisplay(data.memories);
    } catch (error) {
        console.error('Error loading memories:', error);
        const memoriesDiv = document.getElementById('memoriesDisplay');
        memoriesDiv.innerHTML = `
            <div class="thought-item">
                <div class="event-type">Error</div>
                <div>Failed to load memories: ${error.message}</div>
            </div>
        `;
    }
}

function updateMemoriesDisplay(memories) {
    const memoriesDiv = document.getElementById('memoriesDisplay');

    if (!memories || memories.length === 0) {
        memoriesDiv.innerHTML = `
            <div class="thought-item">
                <div class="event-type">No memories yet...</div>
                <div>Memories will appear here as the agent learns about your preferences and context.</div>
            </div>
        `;
        return;
    }

    memoriesDiv.innerHTML = memories.map(memory => {
        const timestamp = new Date(memory.created_at || memory.timestamp).toLocaleString();
        return `
            <div class="thought-item" style="margin-bottom: 8px;">
                <span class="timestamp">${timestamp}</span>
                <span class="event-type">Memory</span>
                <div style="margin-top: 4px;">${memory.content || memory.text}</div>
            </div>
        `;
    }).join('');

    memoriesDiv.scrollTop = memoriesDiv.scrollHeight;
}

function addMemoryEvent(toolName, content) {
    const timestamp = new Date().toLocaleTimeString();
    const memoriesDiv = document.getElementById('memoriesDisplay');

    // Create a new memory notification in the memories tab
    const memoryItem = document.createElement('div');
    memoryItem.className = 'thought-item';
    memoryItem.style.marginBottom = '8px';
    memoryItem.style.backgroundColor = '#f0f8ff';
    memoryItem.style.borderLeft = '2px solid #4CAF50';

    const action = toolName === 'load_memory' ? 'Storing' : 'Retrieving';
    const icon = toolName === 'load_memory' ? '💾' : '🔍';

    memoryItem.innerHTML = `
        <span class="timestamp">${timestamp}</span>
        <span class="event-type">${icon} ${action}</span>
        <div style="margin-top: 4px;">${content}</div>
    `;

    // Clear "No memories yet" message if it exists
    if (memoriesDiv.querySelector('.event-type') &&
        memoriesDiv.querySelector('.event-type').textContent === 'No memories yet...') {
        memoriesDiv.innerHTML = '';
    }

    memoriesDiv.appendChild(memoryItem);
    memoriesDiv.scrollTop = memoriesDiv.scrollHeight;
}

// Timeline View Functions

function switchTimersTab(tabName, event) {
    // Remove active class from all tabs in the timers panel
    const timersTabs = document.querySelectorAll('.panel:last-child .tab');
    timersTabs.forEach(tab => tab.classList.remove('active'));

    // Add active class to selected tab
    if (event && event.target) {
        event.target.classList.add('active');
    }

    // Hide all tab content
    document.getElementById('timersTabContent').classList.remove('active');
    document.getElementById('timelineTabContent').classList.remove('active');

    // Show selected tab content
    if (tabName === 'timers') {
        document.getElementById('timersTabContent').classList.add('active');
    } else if (tabName === 'timeline') {
        document.getElementById('timelineTabContent').classList.add('active');
        renderTimeline();
    }
}

function renderTimeline() {
    const timelineView = document.getElementById('timelineView');

    if (!cachedTimers || cachedTimers.length === 0) {
        timelineView.innerHTML = '<div class="empty-state">No events scheduled. Timeline will appear here.</div>';
        return;
    }

    // Build timeline blocks from timers
    const blocks = buildTimelineBlocks(cachedTimers);

    if (blocks.length === 0) {
        timelineView.innerHTML = '<div class="empty-state">No upcoming events in the next 48 hours.</div>';
        return;
    }

    // Render timeline
    const html = renderTimelineHTML(blocks);
    timelineView.innerHTML = html;
}

function buildTimelineBlocks(timers) {
    const now = new Date();
    const endTime = new Date(now.getTime() + 48 * 60 * 60 * 1000); // 48 hours from now
    const blocks = [];

    // Sort timers by deadline
    const sortedTimers = timers
        .filter(t => t.deadline)
        .map(t => ({
            ...t,
            deadlineDate: new Date(t.deadline)
        }))
        .filter(t => t.deadlineDate >= now && t.deadlineDate <= endTime)
        .sort((a, b) => a.deadlineDate - b.deadlineDate);

    // Track last block end time to create "free" blocks
    let currentTime = now;

    for (const timer of sortedTimers) {
        const timerStart = timer.deadlineDate;

        // Determine duration and type based on label/category
        const isTransit = timer.label.toLowerCase().includes('leave') ||
                         timer.label.toLowerCase().includes('depart') ||
                         timer.category === 'transit';

        let duration = 30; // Default 30 minutes for events
        let blockType = 'event';

        if (isTransit) {
            // Transit blocks - extract duration from metadata if available
            duration = 30; // Default transit time
            blockType = 'transit';
        } else if (timer.label.toLowerCase().includes('appointment')) {
            duration = 60; // 1 hour for appointments
            blockType = 'appointment';
        }

        const timerEnd = new Date(timerStart.getTime() + duration * 60 * 1000);

        // Add free time block if there's a gap
        if (currentTime < timerStart) {
            blocks.push({
                type: 'free',
                start: currentTime,
                end: timerStart,
                label: 'Free time'
            });
        }

        // Add timer block
        blocks.push({
            type: blockType,
            start: timerStart,
            end: timerEnd,
            label: timer.label,
            timer: timer
        });

        currentTime = timerEnd;
    }

    // Add final free time block if there's time left
    if (currentTime < endTime) {
        blocks.push({
            type: 'free',
            start: currentTime,
            end: endTime,
            label: 'Free time'
        });
    }

    return blocks;
}

function renderTimelineHTML(blocks) {
    if (blocks.length === 0) return '';

    const startTime = blocks[0].start;
    const endTime = blocks[blocks.length - 1].end;

    // Calculate hour range
    const startHour = startTime.getHours();
    const endHour = Math.ceil((endTime.getTime() - startTime.getTime()) / (60 * 60 * 1000)) + startHour;

    // Build time ruler
    let rulerHTML = '';
    let currentDate = new Date(startTime);
    currentDate.setMinutes(0, 0, 0);

    const hours = [];
    for (let h = 0; h < (endHour - startHour + 2); h++) {
        const hour = new Date(currentDate.getTime() + h * 60 * 60 * 1000);
        hours.push(hour);

        const hourText = hour.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });

        const isCurrentHour = (hour.getHours() === new Date().getHours() &&
                               hour.getDate() === new Date().getDate());

        rulerHTML += `<div class="timeline-hour ${isCurrentHour ? 'current' : ''}">${hourText}</div>`;
    }

    // Build blocks
    let blocksHTML = '';
    let lastDay = null;

    for (const block of blocks) {
        // Check if we need a day header
        const blockDay = block.start.toLocaleDateString('en-US', {
            weekday: 'long',
            month: 'short',
            day: 'numeric'
        });

        if (blockDay !== lastDay) {
            const topPosition = ((block.start - hours[0]) / (60 * 60 * 1000)) * 60;
            blocksHTML += `<div class="timeline-day-header" style="top: ${topPosition}px">${blockDay}</div>`;
            lastDay = blockDay;
        }

        // Calculate position and height
        const topPosition = ((block.start - hours[0]) / (60 * 60 * 1000)) * 60; // 60px per hour
        const duration = (block.end - block.start) / (60 * 60 * 1000); // hours
        const height = Math.max(duration * 60, 20); // Minimum 20px height

        const startTimeStr = block.start.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
        const endTimeStr = block.end.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });

        // Determine urgency class
        const urgencyClass = block.timer && block.timer.urgency_score > 0.7 ? 'urgent' : '';

        blocksHTML += `
            <div class="timeline-block ${block.type} ${urgencyClass}"
                 style="top: ${topPosition}px; height: ${height}px"
                 title="${block.label}: ${startTimeStr} - ${endTimeStr}">
                <div class="timeline-block-title">${block.label}</div>
                <div class="timeline-block-time">${startTimeStr} - ${endTimeStr}</div>
            </div>
        `;
    }

    return `
        <div class="timeline-container">
            <div class="timeline-ruler">${rulerHTML}</div>
            <div class="timeline-content">${blocksHTML}</div>
        </div>
    `;
}
