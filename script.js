const API_URL = 'http://localhost:5000';
let currentRunId = null;
let pollInterval = null;
let startTime = null;
let reportData = null;

// Landing page to form transition
function openForm() {
    document.getElementById('landingPage').classList.add('slide-up');

    setTimeout(() => {
        document.getElementById('formSection').classList.add('active');
        document.getElementById('backBtn').style.display = 'block';
    }, 500);
}

document.getElementById('startCrawlingBtn').addEventListener('click', openForm);
document.getElementById('ctaStartBtn').addEventListener('click', openForm);

// Back button
document.getElementById('backBtn').addEventListener('click', () => {
    if (document.getElementById('statusCard').classList.contains('active')) {
        // If analysis is running, just go back to form
        document.getElementById('statusCard').classList.remove('active');
        document.getElementById('formCard').style.display = 'block';
    } else {
        // Go back to landing page
        document.getElementById('formSection').classList.remove('active');
        setTimeout(() => {
            document.getElementById('landingPage').classList.remove('slide-up');
            document.getElementById('backBtn').style.display = 'none';

            // Restore CRAWL AI text visibility
            const crawlAiText = document.querySelector('.hero-section h1');
            if (crawlAiText) {
                crawlAiText.style.opacity = '1';
                crawlAiText.style.transition = 'opacity 0.5s ease';
            }
        }, 300);
    }
});

document.getElementById('testForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const url = document.getElementById('url').value;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    // Hide form, show status
    document.getElementById('formCard').style.display = 'none';
    document.getElementById('statusCard').classList.add('active');

    startTime = Date.now();

    try {
        const response = await fetch(`${API_URL}/api/start-test`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url, username, password })
        });

        const data = await response.json();
        currentRunId = data.run_id;

        // Start polling for status
        pollStatus();
    } catch (error) {
        alert('Error starting test: ' + error.message);
        resetUI();
    }
});

async function pollStatus() {
    if (!currentRunId) return;

    try {
        const response = await fetch(`${API_URL}/api/test-status/${currentRunId}`);
        const data = await response.json();

        updateUI(data);

        if (data.status === 'completed') {
            clearInterval(pollInterval);
            await loadReport();
        } else if (data.status === 'failed') {
            clearInterval(pollInterval);
            showError(data.error || 'Test failed');
        } else {
            // Continue polling
            pollInterval = setTimeout(pollStatus, 2000);
        }
    } catch (error) {
        console.error('Polling error:', error);
        pollInterval = setTimeout(pollStatus, 2000);
    }
}

function updateUI(data) {
    document.getElementById('progressText').textContent = data.progress || 'Running';

    // Update duration
    if (startTime) {
        const duration = Math.floor((Date.now() - startTime) / 1000);
        document.getElementById('duration').textContent = duration + 's';
    }
}

function parseReport(reportText) {
    const report = reportText.toLowerCase();
    const metrics = {
        uxScore: 0,
        brokenButtons: 0,
        navigationIssues: 0,
        accessibilityIssues: 0,
        missingLabels: 0,
        deadEnds: 0,
        poorUX: 0
    };

    // Extract UX Score - try multiple patterns
    let scoreMatch = report.match(/ui\/ux\s*score[:\s]*(\d+(?:\.\d+)?)\s*\/?\s*10/i);
    if (!scoreMatch) {
        scoreMatch = report.match(/ux\s*score[:\s]*(\d+(?:\.\d+)?)\s*\/?\s*10/i);
    }
    if (!scoreMatch) {
        scoreMatch = report.match(/score[:\s]*(\d+(?:\.\d+)?)\s*\/?\s*10/i);
    }
    if (!scoreMatch) {
        // Try to find score in "FINAL SCORES" section
        const finalScoresSection = report.match(/final\s+scores[\s\S]*?ui\/ux\s*score[:\s]*(\d+(?:\.\d+)?)\s*\/?\s*10/i);
        if (finalScoresSection) {
            scoreMatch = finalScoresSection;
        }
    }
    if (scoreMatch) {
        metrics.uxScore = parseFloat(scoreMatch[1]);
        // Ensure score is between 0 and 10
        metrics.uxScore = Math.max(0, Math.min(10, metrics.uxScore));
    } else {
        // Fallback: try to extract any number followed by /10
        const fallbackMatch = report.match(/(\d+(?:\.\d+)?)\s*\/\s*10/i);
        if (fallbackMatch) {
            const potentialScore = parseFloat(fallbackMatch[1]);
            if (potentialScore >= 0 && potentialScore <= 10) {
                metrics.uxScore = potentialScore;
            }
        }
    }

    // Count issues
    metrics.brokenButtons = (report.match(/broken\s+button/gi) || []).length;
    metrics.navigationIssues = (report.match(/navigation\s+(?:issue|problem|dead\s+end)/gi) || []).length;
    metrics.accessibilityIssues = (report.match(/accessibility\s+(?:issue|problem)/gi) || []).length;
    metrics.missingLabels = (report.match(/missing\s+label/gi) || []).length;
    metrics.deadEnds = (report.match(/dead\s+end/gi) || []).length;
    metrics.poorUX = (report.match(/poor\s+ux|bad\s+ux/gi) || []).length;

    return metrics;
}

function extractSummary(reportText) {
    if (!reportText || reportText.length < 50) return null;

    // Try to extract "Human Experience Summary" section (5-6 lines)
    // Format 1: **Human Experience Summary:** followed by text (5-6 lines)
    let summaryMatch = reportText.match(/\*\*Human Experience Summary:\*\*\s*([^\n]+(?:\n[^\n]+){0,5})/i);
    if (summaryMatch) {
        let summary = summaryMatch[1].trim();
        // Clean up markdown formatting
        summary = summary.replace(/\*\*/g, '').replace(/\[([^\]]+)\]/g, '$1');
        if (summary.length > 30) return summary;
    }

    // Format 2: Human Experience Summary: (without bold, can be in brackets or after colon)
    summaryMatch = reportText.match(/Human Experience Summary:?\s*\[([^\]]+)\]/i);
    if (summaryMatch) {
        let summary = summaryMatch[1].trim();
        if (summary.length > 30) return summary;
    }

    // Format 3: Human Experience Summary: followed by text (no brackets, 5-6 lines)
    summaryMatch = reportText.match(/Human Experience Summary:?\s*([^\n]+(?:\n[^\n]+){0,5})/i);
    if (summaryMatch) {
        let summary = summaryMatch[1].trim();
        // Remove markdown formatting
        summary = summary.replace(/\*\*/g, '').replace(/\[([^\]]+)\]/g, '$1');
        // Remove if it's just the label itself
        if (summary.toLowerCase().includes('human experience summary')) {
            summary = summary.replace(/human experience summary:?\s*/i, '').trim();
        }
        if (summary.length > 30) {
            return summary;
        }
    }

    // Format 4: Try to find summary after "FINAL SCORES" section (5-6 lines)
    const finalScoresMatch = reportText.match(/FINAL SCORES[\s\S]*?Human Experience Summary:?\s*\[?([^\n\]]+(?:\n[^\n\]]+){0,5})/i);
    if (finalScoresMatch) {
        let summary = finalScoresMatch[1].trim();
        summary = summary.replace(/\*\*/g, '').replace(/\[([^\]]+)\]/g, '$1');
        if (summary.length > 30) {
            return summary;
        }
    }

    // Fallback 1: Extract from "A first-time visitor will likely feel" pattern (demo format) - get 5-6 lines
    const firstTimeMatch = reportText.match(/A first-time visitor will likely feel[^\n]+[^\n]+[^\n]+[^\n]+[^\n]+[^\n]+/i);
    if (firstTimeMatch) {
        let summary = firstTimeMatch[0].trim();
        // Clean up
        summary = summary.replace(/A first-time visitor will likely feel:?\s*/i, '').trim();
        if (summary.length > 40) {
            return summary.substring(0, 600); // Allow for 5-6 lines
        }
    }

    // Fallback 2: Extract from "First Impressions" section - get 5-6 lines
    const firstImpressionsMatch = reportText.match(/First Impressions[^\n]*\n[^\n]*\n([^\n]+(?:\n[^\n]+){0,5})/i);
    if (firstImpressionsMatch) {
        let summary = firstImpressionsMatch[1].trim();
        if (summary.length > 40) return summary;
    }

    // Fallback 3: Extract first meaningful paragraph from report (5-6 lines worth)
    const paragraphs = reportText.split('\n\n').filter(p => p.trim().length > 50);
    if (paragraphs.length > 0) {
        // Find first paragraph that looks like a summary
        for (let para of paragraphs) {
            if (para.length > 100 && para.length < 800 &&
                !para.toLowerCase().includes('score') &&
                !para.toLowerCase().includes('breakdown') &&
                !para.toLowerCase().includes('adjustments applied')) {
                // Get first 5-6 lines
                const lines = para.split('\n').filter(l => l.trim().length > 10);
                if (lines.length >= 3) {
                    return lines.slice(0, 6).join('\n').trim();
                }
                return para.trim().substring(0, 500);
            }
        }
    }

    // Fallback 4: Extract from "Why:" section in First Impressions (usually has good summary content)
    const whyMatch = reportText.match(/Why:[\s\S]*?([^\n]+(?:\n[^\n]+){0,5})/i);
    if (whyMatch) {
        let summary = whyMatch[1].trim();
        summary = summary.replace(/\*\*/g, '').replace(/\[([^\]]+)\]/g, '$1');
        if (summary.length > 40) {
            return summary.substring(0, 600);
        }
    }

    return null;
}

function createDashboard(data) {
    const dashboard = document.getElementById('dashboard');
    dashboard.innerHTML = '';

    const metrics = parseReport(data.report || '');
    const totalPages = data.total_pages || 0;
    const totalClicks = data.total_clicks || 0;
    const duration = data.started_at && data.finished_at ?
        Math.floor((new Date(data.finished_at) - new Date(data.started_at)) / 1000) : 0;

    // Extract Human Experience Summary from report
    const summary = extractSummary(data.report || '');
    console.log('Summary extracted:', summary ? summary.substring(0, 100) + '...' : 'null');
    console.log('Report length:', (data.report || '').length);

    // UX Experience Summary (displayed prominently at top)
    // Always show summary block
    const summaryBlock = document.createElement('div');
    summaryBlock.className = 'dashboard-block full-width summary-block';
    summaryBlock.style.display = 'block';
    summaryBlock.style.visibility = 'visible';
    summaryBlock.style.opacity = '1';

    // Always show summary - extract or use fallback (5-6 lines)
    let displaySummary = summary;

    if (!displaySummary || displaySummary.length < 30) {
        // Try to extract a fallback summary from the report (5-6 lines)
        const reportText = data.report || '';

        // Try to get content from First Impressions section (5-6 lines)
        const firstImpMatch = reportText.match(/First Impressions[^\n]*\n[^\n]*\n([^\n]+(?:\n[^\n]+){0,5})/i);
        if (firstImpMatch) {
            displaySummary = firstImpMatch[1].trim();
            // Limit to 5-6 lines
            const lines = displaySummary.split('\n').filter(l => l.trim().length > 10);
            if (lines.length > 6) {
                displaySummary = lines.slice(0, 6).join('\n');
            }
        } else if (reportText.length > 100) {
            // Get first meaningful paragraph (5-6 lines worth)
            const paragraphs = reportText.split('\n\n').filter(p => p.trim().length > 50);
            const firstPara = paragraphs.find(p =>
                p.trim().length > 100 &&
                p.trim().length < 800 &&
                !p.toLowerCase().includes('score') &&
                !p.toLowerCase().includes('breakdown')
            );
            if (firstPara) {
                const lines = firstPara.split('\n').filter(l => l.trim().length > 10);
                if (lines.length >= 3) {
                    displaySummary = lines.slice(0, 6).join('\n').trim();
                } else {
                    displaySummary = firstPara.trim().substring(0, 500);
                }
            } else {
                // Last resort: first 400 chars formatted as lines
                const text = reportText.substring(0, 400).replace(/\n/g, ' ').trim();
                displaySummary = text;
            }
        }
    }

    // Format summary to ensure it's 5-6 lines if it's too short
    if (displaySummary && displaySummary.length > 30) {
        // Split into lines and ensure we have meaningful content
        const lines = displaySummary.split('\n').filter(l => l.trim().length > 15);
        if (lines.length < 3 && displaySummary.length > 200) {
            // If it's one long line, try to break it into 5-6 lines
            const words = displaySummary.split(' ');
            const wordsPerLine = Math.ceil(words.length / 5);
            const formattedLines = [];
            for (let i = 0; i < words.length; i += wordsPerLine) {
                formattedLines.push(words.slice(i, i + wordsPerLine).join(' '));
            }
            displaySummary = formattedLines.slice(0, 6).join('\n');
        } else if (lines.length > 6) {
            // Limit to 6 lines max
            displaySummary = lines.slice(0, 6).join('\n');
        } else if (lines.length >= 3) {
            // Use the lines as-is if we have 3-6 lines
            displaySummary = lines.join('\n');
        }

        summaryBlock.innerHTML = `
            <h3>UX Experience Summary</h3>
            <div class="summary-text">${displaySummary}</div>
        `;
    } else {
        // Show placeholder if no summary available
        summaryBlock.innerHTML = `
            <h3>UX Experience Summary</h3>
            <div class="summary-text">Analysis complete. Review the detailed report below for comprehensive UX insights and recommendations.</div>
        `;
    }

    // Force append at the beginning and ensure visibility
    if (dashboard.firstChild) {
        dashboard.insertBefore(summaryBlock, dashboard.firstChild);
    } else {
        dashboard.appendChild(summaryBlock);
    }

    // Force visibility with inline styles (completely override any CSS)
    summaryBlock.style.setProperty('display', 'block', 'important');
    summaryBlock.style.setProperty('visibility', 'visible', 'important');
    summaryBlock.style.setProperty('opacity', '1', 'important');
    summaryBlock.style.setProperty('grid-column', '1 / -1', 'important');
    summaryBlock.style.setProperty('width', '100%', 'important');
    summaryBlock.style.setProperty('max-width', '100%', 'important');
    summaryBlock.style.setProperty('margin-bottom', '35px', 'important');
    summaryBlock.style.setProperty('padding', '35px 40px', 'important');
    summaryBlock.style.setProperty('background', 'rgba(255, 255, 255, 0.05)', 'important');
    summaryBlock.style.setProperty('border-left', '4px solid rgba(255, 255, 255, 0.5)', 'important');
    summaryBlock.style.setProperty('border-radius', '4px', 'important');
    summaryBlock.style.setProperty('box-sizing', 'border-box', 'important');

    // Also ensure text is visible after a brief delay (to ensure DOM is ready)
    setTimeout(() => {
        const summaryText = summaryBlock.querySelector('.summary-text');
        if (summaryText) {
            summaryText.style.setProperty('color', 'rgba(255, 255, 255, 0.95)', 'important');
            summaryText.style.setProperty('display', 'block', 'important');
            summaryText.style.setProperty('visibility', 'visible', 'important');
            summaryText.style.setProperty('opacity', '1', 'important');
            summaryText.style.setProperty('margin', '0', 'important');
            summaryText.style.setProperty('padding', '0', 'important');
            summaryText.style.setProperty('line-height', '1.75', 'important');
            summaryText.style.setProperty('font-size', '0.98em', 'important');
        }

        // Debug: Log summary block status
        const computedStyle = window.getComputedStyle(summaryBlock);
        console.log('Summary block visibility check:', {
            inDOM: document.body.contains(summaryBlock),
            display: computedStyle.display,
            visibility: computedStyle.visibility,
            opacity: computedStyle.opacity,
            height: summaryBlock.offsetHeight,
            width: summaryBlock.offsetWidth,
            gridColumn: computedStyle.gridColumn
        });
    }, 200);

    // UX Score Gauge
    const scoreBlock = document.createElement('div');
    scoreBlock.className = 'dashboard-block';

    // Ensure score is valid, default to 0 if not found
    const displayScore = (metrics.uxScore && metrics.uxScore > 0) ? metrics.uxScore : 0;
    const scorePercent = (displayScore / 10) * 100;

    console.log('UX Score extracted:', metrics.uxScore, 'Display score:', displayScore);

    scoreBlock.innerHTML = `
        <h3>UX Score</h3>
        <div class="score-gauge">
            <div class="score-value" id="uxScoreValue">${displayScore.toFixed(1)}</div>
            <div class="score-label">Out of 10</div>
            <div class="chart-container">
                <canvas id="scoreChart"></canvas>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${scorePercent}%"></div>
            </div>
        </div>
    `;
    dashboard.appendChild(scoreBlock);

    // Ensure score block is visible
    scoreBlock.style.display = 'block';
    scoreBlock.style.visibility = 'visible';
    scoreBlock.style.opacity = '1';

    setTimeout(() => {
        if (displayScore > 0) {
            createScoreChart(displayScore);
        } else {
            console.warn('UX Score is 0 or not found in report');
        }
    }, 100);

    // Overview Metrics
    const overviewBlock = document.createElement('div');
    overviewBlock.className = 'dashboard-block';
    overviewBlock.innerHTML = `
        <h3>Overview</h3>
        <div class="metric-grid">
            <div class="metric-item">
                <div class="metric-value">${totalPages}</div>
                <div class="metric-label">Pages</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">${totalClicks}</div>
                <div class="metric-label">Interactions</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">${duration}s</div>
                <div class="metric-label">Duration</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">${(totalClicks / Math.max(totalPages, 1)).toFixed(1)}</div>
                <div class="metric-label">Clicks/Page</div>
            </div>
        </div>
    `;
    dashboard.appendChild(overviewBlock);

    // Issues Chart
    const issuesBlock = document.createElement('div');
    issuesBlock.className = 'dashboard-block';
    issuesBlock.innerHTML = `
        <h3>Issues Found</h3>
        <div class="chart-container">
            <canvas id="issuesChart"></canvas>
        </div>
    `;
    dashboard.appendChild(issuesBlock);
    createIssuesChart(metrics);

    // Pages with Click Counts
    if (data.pages_data && data.pages_data.length > 0) {
        const pagesBlock = document.createElement('div');
        pagesBlock.className = 'dashboard-block full-width';

        let pagesHTML = '<h3>Pages & Interactions</h3><div class="pages-list">';
        data.pages_data.forEach((page, index) => {
            const shortUrl = page.url.length > 60 ? page.url.substring(0, 60) + '...' : page.url;
            pagesHTML += `
                <div class="page-item">
                    <div class="page-info">
                        <div class="page-number">Page ${index + 1}</div>
                        <div class="page-url" title="${page.url}">${shortUrl}</div>
                    </div>
                    <div class="page-stats">
                        <div class="stat-badge">
                            <span class="stat-number">${page.click_count || 0}</span>
                            <span class="stat-label">Clicks</span>
                        </div>
                        <div class="stat-badge">
                            <span class="stat-number">${page.transitions_count || 0}</span>
                            <span class="stat-label">Transitions</span>
                        </div>
                        <div class="stat-badge">
                            <span class="stat-number">${page.buttons ? page.buttons.length : 0}</span>
                            <span class="stat-label">Elements</span>
                        </div>
                    </div>
                </div>
            `;
        });
        pagesHTML += '</div>';
        pagesBlock.innerHTML = pagesHTML;
        dashboard.appendChild(pagesBlock);
    }

    // Interaction Timeline
    if (totalClicks > 0) {
        const timelineBlock = document.createElement('div');
        timelineBlock.className = 'dashboard-block full-width';
        timelineBlock.innerHTML = `
            <h3>Interaction Timeline</h3>
            <div class="chart-container">
                <canvas id="timelineChart"></canvas>
            </div>
        `;
        dashboard.appendChild(timelineBlock);
        // Use actual page data for timeline if available
        if (data.pages_data && data.pages_data.length > 0) {
            createTimelineChartFromData(data.pages_data, duration);
        } else {
            createTimelineChart(totalPages, totalClicks, duration);
        }
    }

    // Issues List
    const issuesListBlock = document.createElement('div');
    issuesListBlock.className = 'dashboard-block';
    const totalIssues = metrics.brokenButtons + metrics.navigationIssues +
        metrics.accessibilityIssues + metrics.missingLabels +
        metrics.deadEnds + metrics.poorUX;
    issuesListBlock.innerHTML = `
        <h3>Issue Breakdown</h3>
        <ul class="issues-list">
            ${metrics.brokenButtons > 0 ? `<li class="issue-item">${metrics.brokenButtons} Broken Button${metrics.brokenButtons > 1 ? 's' : ''}</li>` : ''}
            ${metrics.navigationIssues > 0 ? `<li class="issue-item">${metrics.navigationIssues} Navigation Issue${metrics.navigationIssues > 1 ? 's' : ''}</li>` : ''}
            ${metrics.accessibilityIssues > 0 ? `<li class="issue-item">${metrics.accessibilityIssues} Accessibility Issue${metrics.accessibilityIssues > 1 ? 's' : ''}</li>` : ''}
            ${metrics.missingLabels > 0 ? `<li class="issue-item">${metrics.missingLabels} Missing Label${metrics.missingLabels > 1 ? 's' : ''}</li>` : ''}
            ${metrics.deadEnds > 0 ? `<li class="issue-item">${metrics.deadEnds} Dead End${metrics.deadEnds > 1 ? 's' : ''}</li>` : ''}
            ${metrics.poorUX > 0 ? `<li class="issue-item">${metrics.poorUX} Poor UX Pattern${metrics.poorUX > 1 ? 's' : ''}</li>` : ''}
            ${totalIssues === 0 ? '<li class="issue-item">No major issues detected</li>' : ''}
        </ul>
    `;
    dashboard.appendChild(issuesListBlock);

    // Screenshot Gallery
    if (data.screenshots && data.screenshots.length > 0) {
        const galleryBlock = document.createElement('div');
        galleryBlock.className = 'dashboard-block full-width';
        galleryBlock.innerHTML = `
            <h3>Screenshot Gallery</h3>
            <div class="screenshot-gallery" id="screenshotGallery"></div>
        `;
        dashboard.appendChild(galleryBlock);
        createScreenshotGallery(data.screenshots);
    }

    // Performance Metrics
    const performanceBlock = document.createElement('div');
    performanceBlock.className = 'dashboard-block';
    const avgTimePerPage = duration / Math.max(totalPages, 1);
    performanceBlock.innerHTML = `
        <h3>Performance</h3>
        <div class="metric-grid">
            <div class="metric-item">
                <div class="metric-value">${avgTimePerPage.toFixed(1)}s</div>
                <div class="metric-label">Avg/Page</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">${(totalPages / Math.max(duration, 1) * 60).toFixed(1)}</div>
                <div class="metric-label">Pages/Min</div>
            </div>
        </div>
    `;
    dashboard.appendChild(performanceBlock);
}

function createScoreChart(score) {
    const canvas = document.getElementById('scoreChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Score', 'Remaining'],
            datasets: [{
                data: [score, 10 - score],
                backgroundColor: [
                    'rgba(255, 255, 255, 0.8)',
                    'rgba(255, 255, 255, 0.1)'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            cutout: '70%',
            animation: {
                animateRotate: true,
                duration: 1500
            }
        }
    });
}

function createIssuesChart(metrics) {
    const ctx = document.getElementById('issuesChart').getContext('2d');
    const issuesData = {
        'Broken Buttons': metrics.brokenButtons,
        'Navigation': metrics.navigationIssues,
        'Accessibility': metrics.accessibilityIssues,
        'Missing Labels': metrics.missingLabels,
        'Dead Ends': metrics.deadEnds,
        'Poor UX': metrics.poorUX
    };

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(issuesData),
            datasets: [{
                label: 'Issues',
                data: Object.values(issuesData),
                backgroundColor: 'rgba(255, 255, 255, 0.6)',
                borderColor: 'rgba(255, 255, 255, 0.8)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: 'rgba(255, 255, 255, 0.3)',
                    borderWidth: 1
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.6)',
                        stepSize: 1
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                x: {
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.6)'
                    },
                    grid: {
                        display: false
                    }
                }
            },
            animation: {
                duration: 1000,
                easing: 'easeOutQuart'
            }
        }
    });
}

function createTimelineChartFromData(pagesData, duration) {
    const ctx = document.getElementById('timelineChart').getContext('2d');
    const maxPoints = Math.min(pagesData.length, 20);
    const labels = pagesData.slice(0, maxPoints).map((_, i) => `Page ${i + 1}`);
    const clicksData = pagesData.slice(0, maxPoints).map(page => page.click_count || 0);

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Clicks per Page',
                data: clicksData,
                borderColor: 'rgba(255, 255, 255, 0.8)',
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: 'rgba(255, 255, 255, 0.3)',
                    borderWidth: 1
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.6)',
                        stepSize: 1
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                x: {
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.6)'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            },
            animation: {
                duration: 1500,
                easing: 'easeOutQuart'
            }
        }
    });
}

function createTimelineChart(pages, clicks, duration) {
    const ctx = document.getElementById('timelineChart').getContext('2d');
    const timePoints = Math.min(pages, 10);
    const labels = Array.from({ length: timePoints }, (_, i) => `Page ${i + 1}`);
    const clicksData = Array.from({ length: timePoints }, () =>
        Math.floor(clicks / timePoints) + Math.floor(Math.random() * 3)
    );

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Interactions',
                data: clicksData,
                borderColor: 'rgba(255, 255, 255, 0.8)',
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: 'rgba(255, 255, 255, 0.3)',
                    borderWidth: 1
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.6)',
                        stepSize: 1
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                x: {
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.6)'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            },
            animation: {
                duration: 1500,
                easing: 'easeOutQuart'
            }
        }
    });
}

function createScreenshotGallery(screenshots) {
    const gallery = document.getElementById('screenshotGallery');
    screenshots.forEach((screenshot, index) => {
        const item = document.createElement('div');
        item.className = 'screenshot-item';
        item.innerHTML = `
            <img src="${API_URL}/api/screenshot/${screenshot}" 
                 alt="Screenshot ${index + 1}" 
                 loading="lazy"
                 onerror="this.style.display='none'">
            <div class="screenshot-overlay">Page ${index + 1}</div>
        `;
        item.addEventListener('click', () => {
            document.getElementById('modalImage').src = `${API_URL}/api/screenshot/${screenshot}`;
            document.getElementById('screenshotModal').classList.add('active');
        });
        gallery.appendChild(item);
    });
}

async function loadReport() {
    try {
        const response = await fetch(`${API_URL}/api/test-report/${currentRunId}`);
        const data = await response.json();
        reportData = data;

        // Update status icon
        const statusIcon = document.getElementById('statusIcon');
        statusIcon.className = 'status-icon completed';
        statusIcon.textContent = '✓';

        document.getElementById('statusTitle').textContent = 'Analysis Complete';
        document.getElementById('progressText').textContent = 'Report generated successfully';

        // Hide spinner
        document.getElementById('spinner').style.display = 'none';

        // Show stats
        document.getElementById('stats').style.display = 'grid';
        document.getElementById('totalPages').textContent = data.total_pages || 0;
        document.getElementById('totalClicks').textContent = data.total_clicks || 0;

        // Update duration
        if (data.started_at && data.finished_at) {
            const start = new Date(data.started_at);
            const end = new Date(data.finished_at);
            const duration = Math.floor((end - start) / 1000);
            document.getElementById('duration').textContent = duration + 's';
        }

        // Show dashboard
        const reportContainer = document.getElementById('reportContainer');
        reportContainer.style.display = 'block';

        const reportMeta = document.getElementById('reportMeta');
        reportMeta.innerHTML = `
            <strong>URL:</strong> ${data.url || 'N/A'}<br>
            <strong>Started:</strong> ${data.started_at ? new Date(data.started_at).toLocaleString() : 'N/A'}<br>
            <strong>Finished:</strong> ${data.finished_at ? new Date(data.finished_at).toLocaleString() : 'N/A'}
        `;

        // Create dashboard
        createDashboard(data);

        // Show action buttons
        document.getElementById('actionButtons').style.display = 'flex';

        // Update chatbot badge
        if (typeof updateChatbotBadge === 'function') {
            updateChatbotBadge();
        }
    } catch (error) {
        showError('Error loading report: ' + error.message);
    }
}

function showError(message) {
    const statusIcon = document.getElementById('statusIcon');
    statusIcon.className = 'status-icon failed';
    statusIcon.textContent = 'X';

    document.getElementById('statusTitle').textContent = 'Test Failed';
    document.getElementById('progressText').textContent = message;
    document.getElementById('spinner').style.display = 'none';
    document.getElementById('actionButtons').style.display = 'flex';
}

function downloadPDF() {
    if (!reportData) {
        alert('No report data available');
        return;
    }

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    // Set font
    doc.setFont('helvetica');

    // Title
    doc.setFontSize(18);
    doc.setFont('helvetica', 'bold');
    doc.text('CRAWL AI - Analysis Report', 20, 20);

    // Meta information
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    let yPos = 35;
    doc.text(`URL: ${reportData.url || 'N/A'}`, 20, yPos);
    yPos += 7;
    doc.text(`Pages Crawled: ${reportData.total_pages || 0}`, 20, yPos);
    yPos += 7;
    doc.text(`Interactions: ${reportData.total_clicks || 0}`, 20, yPos);
    yPos += 7;
    if (reportData.started_at) {
        doc.text(`Started: ${new Date(reportData.started_at).toLocaleString()}`, 20, yPos);
        yPos += 7;
    }
    if (reportData.finished_at) {
        doc.text(`Finished: ${new Date(reportData.finished_at).toLocaleString()}`, 20, yPos);
        yPos += 7;
    }

    // Report content
    yPos += 5;
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.text('Analysis Report', 20, yPos);
    yPos += 10;

    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');

    // Split report text into lines that fit the page
    const reportText = reportData.report || 'No report available';
    const maxWidth = 170;
    const lineHeight = 6;
    const pageHeight = 280;
    const startX = 20;

    const lines = doc.splitTextToSize(reportText, maxWidth);

    lines.forEach((line) => {
        if (yPos > pageHeight) {
            doc.addPage();
            yPos = 20;
        }
        doc.text(line, startX, yPos);
        yPos += lineHeight;
    });

    // Save the PDF
    const filename = `CRAWL_AI_Report_${currentRunId || 'report'}.pdf`;
    doc.save(filename);
}

async function downloadScreenshotPDF() {
    if (!reportData || !reportData.screenshots || reportData.screenshots.length === 0) {
        alert('No screenshots available');
        return;
    }

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF('landscape', 'mm', 'a4');
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const imgWidth = pageWidth - 40;
    const imgHeight = (imgWidth * 9) / 16; // 16:9 aspect ratio

    try {
        for (let i = 0; i < reportData.screenshots.length; i++) {
            const screenshotPath = reportData.screenshots[i];
            const screenshotUrl = `${API_URL}/api/screenshot/${screenshotPath}`;

            // Fetch screenshot as blob
            const response = await fetch(screenshotUrl);
            if (!response.ok) continue;

            const blob = await response.blob();
            const imgData = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result);
                reader.readAsDataURL(blob);
            });

            // Add new page for each screenshot (except first)
            if (i > 0) {
                doc.addPage();
            }

            // Add screenshot to PDF
            const yPos = (pageHeight - imgHeight) / 2;
            doc.addImage(imgData, 'PNG', 20, yPos, imgWidth, imgHeight);

            // Add caption
            doc.setFontSize(10);
            doc.text(`Screenshot ${i + 1} - ${screenshotPath}`, 20, yPos + imgHeight + 10);
        }

        const filename = `CRAWL_AI_Screenshots_${currentRunId || 'screenshots'}.pdf`;
        doc.save(filename);
    } catch (error) {
        alert('Error generating screenshot PDF: ' + error.message);
        console.error('Screenshot PDF error:', error);
    }
}

function resetUI() {
    document.getElementById('formCard').style.display = 'block';
    document.getElementById('statusCard').classList.remove('active');
    document.getElementById('spinner').style.display = 'block';
    document.getElementById('stats').style.display = 'none';
    document.getElementById('reportContainer').style.display = 'none';
    document.getElementById('actionButtons').style.display = 'none';

    // Reset form
    document.getElementById('testForm').reset();

    // Reset status
    const statusIcon = document.getElementById('statusIcon');
    statusIcon.className = 'status-icon running';
    statusIcon.textContent = '...';
    document.getElementById('statusTitle').textContent = 'Running Analysis';
    document.getElementById('progressText').textContent = 'Initializing';

    currentRunId = null;
    startTime = null;
    reportData = null;
}

document.getElementById('newTestBtn').addEventListener('click', resetUI);
document.getElementById('downloadPdfBtn').addEventListener('click', downloadPDF);
document.getElementById('downloadScreenshotPdfBtn').addEventListener('click', downloadScreenshotPDF);

// Modal close
document.getElementById('closeModal').addEventListener('click', () => {
    document.getElementById('screenshotModal').classList.remove('active');
});

document.getElementById('screenshotModal').addEventListener('click', (e) => {
    if (e.target.id === 'screenshotModal') {
        document.getElementById('screenshotModal').classList.remove('active');
    }
});

// Chatbot Functionality
let chatbotOpen = false;
let chatHistory = [];

// Initialize chatbot
function initChatbot() {
    const chatbotToggle = document.getElementById('chatbotToggle');
    const chatbotClose = document.getElementById('chatbotClose');
    const chatbotContainer = document.getElementById('chatbotContainer');
    const chatbotSend = document.getElementById('chatbotSend');
    const chatbotInput = document.getElementById('chatbotInput');

    if (!chatbotToggle || !chatbotContainer) {
        console.error('Chatbot elements not found:', {
            toggle: !!chatbotToggle,
            container: !!chatbotContainer
        });
        return;
    }

    // Ensure toggle button is visible
    chatbotToggle.style.display = 'flex';
    chatbotToggle.style.visibility = 'visible';
    chatbotToggle.style.opacity = '1';
    chatbotToggle.style.zIndex = '10000';

    // Toggle chatbot
    chatbotToggle.addEventListener('click', () => {
        chatbotOpen = !chatbotOpen;
        if (chatbotOpen) {
            chatbotContainer.classList.add('active');
            if (chatbotInput) chatbotInput.focus();
        } else {
            chatbotContainer.classList.remove('active');
        }
    });

    // Close chatbot
    if (chatbotClose) {
        chatbotClose.addEventListener('click', () => {
            chatbotOpen = false;
            chatbotContainer.classList.remove('active');
        });
    }

    // Send message on button click
    if (chatbotSend) {
        chatbotSend.addEventListener('click', sendChatMessage);
    }

    // Send message on Enter key
    if (chatbotInput) {
        chatbotInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }

    // Show badge when report is available
    updateChatbotBadge();
}

// Update chatbot badge visibility
function updateChatbotBadge() {
    const badge = document.getElementById('chatbotBadge');
    if (badge && reportData) {
        badge.style.display = 'flex';
    } else if (badge) {
        badge.style.display = 'none';
    }
}

// Send chat message
async function sendChatMessage() {
    const chatbotInput = document.getElementById('chatbotInput');
    const chatbotMessages = document.getElementById('chatbotMessages');
    const chatbotLoading = document.getElementById('chatbotLoading');
    const chatbotSend = document.getElementById('chatbotSend');

    if (!chatbotInput || !chatbotMessages) return;

    const message = chatbotInput.value.trim();
    if (!message) return;

    // Disable input and send button
    chatbotInput.disabled = true;
    if (chatbotSend) chatbotSend.disabled = true;

    // Add user message to chat
    addChatMessage(message, 'user');
    chatbotInput.value = '';

    // Show loading
    if (chatbotLoading) chatbotLoading.style.display = 'flex';

    try {
        // Prepare context with report data if available
        const context = reportData ? {
            report: reportData.report || '',
            url: reportData.url || '',
            total_pages: reportData.total_pages || 0,
            total_clicks: reportData.total_clicks || 0,
            started_at: reportData.started_at || '',
            finished_at: reportData.finished_at || ''
        } : null;

        // Send to backend
        const response = await fetch(`${API_URL}/api/chatbot`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                context: context,
                history: chatHistory.slice(-10) // Last 10 messages for context
            })
        });

        if (!response.ok) {
            throw new Error('Failed to get response from chatbot');
        }

        const data = await response.json();

        // Add bot response to chat
        addChatMessage(data.response, 'bot');

        // Update chat history
        chatHistory.push({ role: 'user', content: message });
        chatHistory.push({ role: 'assistant', content: data.response });

    } catch (error) {
        console.error('Chatbot error:', error);
        addChatMessage('Sorry, I encountered an error. Please make sure the backend server is running and your Gemini API key is configured in the .env file.', 'bot');
    } finally {
        // Re-enable input and send button
        chatbotInput.disabled = false;
        if (chatbotSend) chatbotSend.disabled = false;
        if (chatbotLoading) chatbotLoading.style.display = 'none';
        chatbotInput.focus();
    }
}

// Add message to chat
function addChatMessage(text, type) {
    const chatbotMessages = document.getElementById('chatbotMessages');
    if (!chatbotMessages) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = `chatbot-message ${type}-message`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Split text into paragraphs
    const paragraphs = text.split('\n\n').filter(p => p.trim());
    paragraphs.forEach((para) => {
        const p = document.createElement('p');
        p.textContent = para.trim();
        contentDiv.appendChild(p);
    });

    // Add timestamp
    const timeP = document.createElement('p');
    timeP.className = 'message-time';
    timeP.textContent = 'Just now';
    contentDiv.appendChild(timeP);

    messageDiv.appendChild(contentDiv);
    chatbotMessages.appendChild(messageDiv);

    // Scroll to bottom
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

// Initialize chatbot when DOM is ready
function initializeChatbotOnReady() {
    // Wait a bit to ensure all elements are loaded
    setTimeout(() => {
        const chatbotToggle = document.getElementById('chatbotToggle');
        if (chatbotToggle) {
            initChatbot();
            console.log('Chatbot initialized successfully');
        } else {
            console.error('Chatbot toggle button not found');
            // Retry after a short delay
            setTimeout(initializeChatbotOnReady, 500);
        }
    }, 100);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeChatbotOnReady);
} else {
    initializeChatbotOnReady();
}