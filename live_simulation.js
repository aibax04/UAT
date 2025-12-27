/**
 * Live Simulation Panel Logic
 * Handles the visual-only demonstration of "agent activity" on the home screen.
 * Strictly frontend-only. No real execution.
 */

class LiveSimulation {
    constructor() {
        this.container = document.getElementById('liveAgentSimulation');
        this.logContainer = document.getElementById('simLogs');
        this.logs = [
            "Initializing background context...",
            "Loading heuristic models (v4.2)...",
            "Establishing neural pathways...",
            "Scanning DOM tree structure...",
            "Vectorizing view hierarchy...",
            "Identifying interactive nodes...",
            "Optimizing traversal graph...",
            "Pre-calculating route metrics...",
            "Analyzing semantic relationships...",
            "Validating selector robustness...",
            "Synchronizing state vectors...",
            "Evaluating interaction readiness...",
            "Monitoring event loop latency...",
            "Constructing decision matrix...",
            "Checking viewport boundaries...",
            "Refreshing element cache...",
            "Predicting user flow anomalies...",
            "Calibrating visual sensors..."
        ];
        this.currentLogIndex = 0;
        this.interval = null;
        this.isRunning = true;

        this.init();
    }

    init() {
        if (!this.container || !this.logContainer) return;

        // Start the loop
        this.startLoop();

        // Bind exit triggers
        this.bindExitTriggers();
    }

    startLoop() {
        // Initial log
        this.addLog(this.logs[0]);
        this.currentLogIndex = 1;

        // Loop
        this.interval = setInterval(() => {
            if (!this.isRunning) return;

            const log = this.logs[this.currentLogIndex];
            this.addLog(log);

            this.currentLogIndex++;
            if (this.currentLogIndex >= this.logs.length) {
                this.currentLogIndex = 0; // Loop
            }
        }, 2500 + Math.random() * 1000); // Random interval 2.5s - 3.5s
    }

    addLog(text) {
        if (!this.logContainer) return;

        const item = document.createElement('div');
        item.className = 'sim-log-item';

        // Add timestamp for realism (optional, but requested "realistic")
        // const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        // item.textContent = `[${time}] ${text}`; 
        // Keeping it simple/clean as per "Thin typography" request without too much noise
        item.textContent = `> ${text}`;

        // Prepend to keep expanding or append? 
        // A terminal usually appends at bottom.
        // But "mask-image" suggests a scrolling view.
        this.logContainer.appendChild(item);

        // Auto scroll to bottom
        this.logContainer.scrollTop = this.logContainer.scrollHeight;

        // Highlight latest
        const previous = this.logContainer.querySelectorAll('.sim-log-item.active');
        previous.forEach(el => el.classList.remove('active'));
        item.classList.add('active');

        // Clean up old logs to prevent DOM bloat
        if (this.logContainer.children.length > 20) {
            this.logContainer.removeChild(this.logContainer.firstChild);
        }
    }

    bindExitTriggers() {
        const exitButtons = [
            'startCrawlingBtn',
            'ctaStartBtn',
            'liveWorkspaceBtn',
            'scheduledTestingBtn'
        ];

        exitButtons.forEach(id => {
            const btn = document.getElementById(id);
            if (btn) {
                btn.addEventListener('click', () => {
                    this.stopAndUnmount();
                });
            }
        });
    }

    stopAndUnmount() {
        this.isRunning = false;
        clearInterval(this.interval);

        if (this.container) {
            this.container.classList.add('fade-out');

            // Remove from DOM after transition
            setTimeout(() => {
                if (this.container && this.container.parentNode) {
                    this.container.parentNode.removeChild(this.container);
                }
            }, 1000);
        }
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    // Only init if the element exists (inserted via HTML)
    setTimeout(() => {
        new LiveSimulation();
    }, 500); // Slight delay to let page settle
});
