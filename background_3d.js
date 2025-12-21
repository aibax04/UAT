/**
 * 3D Anti-Gravity Background with Cursor Interaction
 * Visual-only enhancement for premium feel.
 * Non-interactive, decorative, performance-optimized.
 */

class AntiGravityParticle {
    constructor(canvasWidth, canvasHeight) {
        this.reset(canvasWidth, canvasHeight, true);
    }

    reset(w, h, initial = false) {
        this.x = Math.random() * w;
        // If initial, scatter vertically. If reset, start at bottom.
        this.y = initial ? Math.random() * h : h + Math.random() * 100;

        // Depth (z) affects size, speed, and opacity
        this.z = Math.random() * 2 + 0.5; // 0.5 to 2.5

        // Subtle upward movement (anti-gravity)
        this.baseVy = -(Math.random() * 0.2 + 0.1) / this.z;
        this.vy = this.baseVy;

        // Very subtle horizontal drift
        this.baseVx = (Math.random() - 0.5) * 0.1;
        this.vx = this.baseVx;

        this.size = (Math.random() * 2 + 1) * this.z;
        this.baseOpacity = (Math.random() * 0.3 + 0.1) / this.z; // Further away = less opaque
        this.opacity = this.baseOpacity;

        // Oscillation for smooth organic movement
        this.angle = Math.random() * Math.PI * 2;
        this.angleSpeed = 0.001 + Math.random() * 0.002;
    }

    update(w, h, mouse) {
        // Anti-gravity movement mixed with oscillation
        this.angle += this.angleSpeed;

        // Target velocity starts with base movement
        let targetVx = this.baseVx + Math.sin(this.angle) * 0.2;
        let targetVy = this.baseVy;

        // Mouse interaction
        if (mouse.x !== -1000) {
            const dx = mouse.x - this.x;
            const dy = mouse.y - this.y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            // Interaction radius based on screen size (approx 300px)
            const interactionRadius = 600;

            if (dist < interactionRadius) {
                // Calculate attraction force (stronger when closer)
                const force = (interactionRadius - dist) / interactionRadius;

                // Gentle pull towards mouse
                // Z-index affects how easily they are pulled (lighter particles move easier?)
                // Actually, let's say closer particles (larger Z) react more
                const pullStrength = 0.08 * force * this.z;

                targetVx += dx * pullStrength * 0.1; // Horizontal pull
                targetVy += dy * pullStrength * 0.1; // Vertical pull
            }
        }

        // Apply velocities with simple inertia/easing
        this.vx += (targetVx - this.vx) * 0.1;
        this.vy += (targetVy - this.vy) * 0.1;

        this.x += this.vx;
        this.y += this.vy;

        // Fade in/out at edges
        if (this.y < h * 0.1) {
            this.opacity = Math.max(0, this.opacity - 0.005);
        } else if (this.y > h * 0.9) {
            this.opacity = Math.min(this.baseOpacity, this.opacity + 0.005);
        }

        // Reset if off-screen (bottom or top)
        // Allow them to go off-screen upwards significantly before resetting
        if (this.y < -50 || this.y > h + 150 || this.x < -50 || this.x > w + 50) {
            // Only reset if opacity is also low or very far off
            if (this.opacity <= 0.01) {
                this.reset(w, h);
            }
        }

        // Hard reset if lost
        if (this.y < -200 || this.y > h + 300) {
            this.reset(w, h);
        }
    }

    draw(ctx) {
        ctx.beginPath();
        ctx.fillStyle = `rgba(200, 200, 200, ${this.opacity})`;
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fill();
    }
}

class Background3D {
    constructor() {
        this.canvas = document.getElementById('gravityCanvas');
        if (!this.canvas) {
            console.error('Gravity Canvas not found');
            return;
        }

        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.isActive = true;
        this.mouse = { x: -1000, y: -1000 };

        // Cap particle count based on screen size
        this.particleCount = window.innerWidth < 768 ? 40 : 100;

        this.init();

        // Bind methods
        this.animate = this.animate.bind(this);
        this.handleResize = this.handleResize.bind(this);
        this.handleMouseMove = this.handleMouseMove.bind(this);

        window.addEventListener('resize', this.handleResize);
        window.addEventListener('mousemove', this.handleMouseMove);

        // Visibility API to pause when tab hidden
        document.addEventListener('visibilitychange', () => {
            this.isActive = !document.hidden;
            if (this.isActive) this.animate();
        });

        this.animate();
    }

    init() {
        this.resize();
        this.particles = [];
        for (let i = 0; i < this.particleCount; i++) {
            this.particles.push(new AntiGravityParticle(this.width, this.height));
        }
    }

    resize() {
        this.width = window.innerWidth;
        this.height = window.innerHeight;

        // Handle high DPI displays
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = this.width * dpr;
        this.canvas.height = this.height * dpr;
        this.ctx.scale(dpr, dpr);

        this.canvas.style.width = `${this.width}px`;
        this.canvas.style.height = `${this.height}px`;
    }

    handleResize() {
        this.resize();
    }

    handleMouseMove(e) {
        this.mouse.x = e.clientX;
        this.mouse.y = e.clientY;
    }

    animate() {
        if (!this.isActive) return;

        this.ctx.clearRect(0, 0, this.width, this.height);

        // Update and draw particles
        this.particles.forEach(p => {
            p.update(this.width, this.height, this.mouse);
            p.draw(this.ctx);
        });

        // Add subtle connection lines for nearby particles
        this.drawConnections();

        requestAnimationFrame(this.animate);
    }

    drawConnections() {
        // Only connect a few to save performance
        const connectDistance = 150;
        this.ctx.lineWidth = 0.5;

        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const p1 = this.particles[i];
                const p2 = this.particles[j];

                // Simple distance check
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < connectDistance) {
                    // Line opacity based on distance and particle opacity
                    const alpha = (1 - dist / connectDistance) * 0.15 * Math.min(p1.opacity, p2.opacity);
                    if (alpha > 0) {
                        this.ctx.strokeStyle = `rgba(180, 180, 180, ${alpha})`;
                        this.ctx.beginPath();
                        this.ctx.moveTo(p1.x, p1.y);
                        this.ctx.lineTo(p2.x, p2.y);
                        this.ctx.stroke();
                    }
                }
            }
        }
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    new Background3D();
});
