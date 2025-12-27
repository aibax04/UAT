/**
 * CRAWL AI - Autonomous Engine Visualization
 * Adds a subtle, high-tech background layer simulating an autonomous intelligence engine.
 * visualization consists of a node network with data flow and processing indicators.
 */

class AutonomousEngine {
    constructor() {
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.nodes = [];
        this.maxNodes = 60; // Number of active agents/nodes
        this.packets = [];
        this.connectionDistance = 150;
        this.mouse = { x: null, y: null };
        this.statusTexts = [
            'ANALYZING_DOM',
            'TRAINING_MODEL',
            'OPTIMIZING_PATH',
            'FETCHING_ASSETS',
            'VERIFYING_SELECTOR',
            'SYNC_DB',
            'AGENT_ACTIVE',
            'THREAD_IDLE',
            'PARSING_HTML',
            'VECTOR_SEARCH'
        ];

        this.init();
    }

    init() {
        this.canvas.id = 'autonomousEngineCanvas';
        this.canvas.style.position = 'absolute';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.pointerEvents = 'none';
        this.canvas.style.zIndex = '0'; // Same as gravityCanvas, but will be placed after

        // Insert into the background container if possible, otherwise body
        const container = document.querySelector('.background-container');
        const overlay = document.querySelector('.background-overlay');

        if (container && overlay) {
            container.insertBefore(this.canvas, overlay); // Insert before overlay (z-1) but after gravityCanvas
        } else {
            document.body.appendChild(this.canvas);
        }

        this.resize();
        window.addEventListener('resize', () => this.resize());
        window.addEventListener('mousemove', (e) => {
            this.mouse.x = e.clientX;
            this.mouse.y = e.clientY;
        });

        this.createNodes();
        this.animate();
    }

    resize() {
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.canvas.width = this.width;
        this.canvas.height = this.height;
    }

    createNodes() {
        this.nodes = [];
        for (let i = 0; i < this.maxNodes; i++) {
            this.nodes.push({
                x: Math.random() * this.width,
                y: Math.random() * this.height,
                vx: (Math.random() - 0.5) * 0.5, // Slow, autonomous movement
                vy: (Math.random() - 0.5) * 0.5,
                radius: Math.random() * 2 + 1,
                state: 'IDLE', // IDLE, PROCESSING, ERROR, SUCCESS
                stateTimer: 0,
                statusText: null,
                statusOpacity: 0
            });
        }
    }

    updateNodes() {
        this.nodes.forEach(node => {
            // Movement
            node.x += node.vx;
            node.y += node.vy;

            // Boundary wrap
            if (node.x < 0) node.x = this.width;
            if (node.x > this.width) node.x = 0;
            if (node.y < 0) node.y = this.height;
            if (node.y > this.height) node.y = 0;

            // Mouse interaction (gentle repulsion)
            if (this.mouse.x) {
                const dx = this.mouse.x - node.x;
                const dy = this.mouse.y - node.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 200) {
                    const force = (200 - dist) / 200;
                    node.vx -= (dx / dist) * force * 0.05;
                    node.vy -= (dy / dist) * force * 0.05;
                }
            }

            // State Logic - Randomly switch states to simulate "work"
            if (node.stateTimer <= 0) {
                if (Math.random() < 0.01) { // 1% chance to start a task
                    node.state = 'PROCESSING';
                    node.stateTimer = 100 + Math.random() * 200;
                    node.targetRadius = 4 + Math.random() * 2;
                    // Occasionally show text
                    if (Math.random() < 0.3) {
                        node.statusText = this.statusTexts[Math.floor(Math.random() * this.statusTexts.length)];
                        node.statusOpacity = 1;
                    }
                } else if (node.state === 'PROCESSING') {
                    // Task done
                    node.state = 'IDLE';
                    node.stateTimer = 0;
                    node.targetRadius = Math.random() * 2 + 1;
                }
            } else {
                node.stateTimer--;
            }

            // Radius animation
            if (node.state === 'PROCESSING') {
                node.radius += (node.targetRadius - node.radius) * 0.1;
            } else {
                node.radius += ((Math.random() * 2 + 1) - node.radius) * 0.1;
            }

            // Status text fade out
            if (node.statusText) {
                node.statusOpacity -= 0.005;
                if (node.statusOpacity <= 0) {
                    node.statusText = null;
                }
            }
        });
    }

    draw() {
        this.ctx.clearRect(0, 0, this.width, this.height);

        // Ensure faint visibility
        this.ctx.globalCompositeOperation = 'lighter';

        // Draw connections
        this.nodes.forEach((nodeA, i) => {
            for (let j = i + 1; j < this.nodes.length; j++) {
                const nodeB = this.nodes[j];
                const dx = nodeA.x - nodeB.x;
                const dy = nodeA.y - nodeB.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < this.connectionDistance) {
                    const opacity = 1 - (dist / this.connectionDistance);
                    this.ctx.beginPath();
                    this.ctx.moveTo(nodeA.x, nodeA.y);
                    this.ctx.lineTo(nodeB.x, nodeB.y);

                    // Dynamic coloring based on node state
                    if (nodeA.state === 'PROCESSING' || nodeB.state === 'PROCESSING') {
                        this.ctx.strokeStyle = `rgba(100, 200, 255, ${opacity * 0.4})`;
                    } else {
                        this.ctx.strokeStyle = `rgba(100, 100, 100, ${opacity * 0.15})`;
                    }
                    this.ctx.stroke();

                    // Optional: Data packets flowing
                    if (nodeA.state === 'PROCESSING' && Math.random() < 0.05) {
                        this.packets.push({
                            x: nodeA.x,
                            y: nodeA.y,
                            tx: nodeB.x,
                            ty: nodeB.y,
                            progress: 0,
                            speed: 0.02 + Math.random() * 0.03
                        });
                    }
                }
            }
        });

        // Draw Packets
        for (let i = this.packets.length - 1; i >= 0; i--) {
            const p = this.packets[i];
            p.progress += p.speed;
            if (p.progress >= 1) {
                this.packets.splice(i, 1);
                continue;
            }
            const curX = p.x + (p.tx - p.x) * p.progress;
            const curY = p.y + (p.ty - p.y) * p.progress;

            this.ctx.beginPath();
            this.ctx.arc(curX, curY, 1.5, 0, Math.PI * 2);
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
            this.ctx.fill();
        }

        // Draw Nodes
        this.nodes.forEach(node => {
            this.ctx.beginPath();
            this.ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);

            if (node.state === 'PROCESSING') {
                this.ctx.fillStyle = `rgba(100, 200, 255, 0.8)`;
                // Pulse ring
                this.ctx.shadowBlur = 10;
                this.ctx.shadowColor = 'rgba(100, 200, 255, 0.5)';
            } else {
                this.ctx.fillStyle = `rgba(150, 150, 150, 0.4)`;
                this.ctx.shadowBlur = 0;
            }
            this.ctx.fill();
            this.ctx.shadowBlur = 0; // Reset

            // Processing Ring Indicator
            if (node.state === 'PROCESSING') {
                this.ctx.beginPath();
                this.ctx.arc(node.x, node.y, node.radius + 3 + Math.sin(Date.now() / 200) * 2, 0, Math.PI * 2);
                this.ctx.strokeStyle = `rgba(100, 200, 255, 0.3)`;
                this.ctx.stroke();
            }

            // Draw text
            if (node.statusText) {
                this.ctx.font = '10px monospace';
                this.ctx.fillStyle = `rgba(100, 200, 255, ${node.statusOpacity})`;
                this.ctx.fillText(node.statusText, node.x + 10, node.y - 10);
            }
        });
    }

    animate() {
        this.updateNodes();
        this.draw();
        requestAnimationFrame(() => this.animate());
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new AutonomousEngine();
});
