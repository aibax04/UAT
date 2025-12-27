/**
 * Motion Polish Utility
 * Adds premium scroll-reveal animations to the landing page.
 * Uses IntersectionObserver for performance.
 * Respects 'prefers-reduced-motion'.
 */

class MotionPolish {
    constructor() {
        this.observer = null;
        this.init();
    }

    init() {
        // Check for reduced motion preference
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return; // Exit if user prefers no motion
        }

        this.setupHeroAnimations();
        this.setupScrollObserver();
        this.targetElements();
    }

    setupHeroAnimations() {
        // Animate hero elements immediately on load
        const heroTitle = document.querySelector('.hero-section h1');
        const heroTagline = document.querySelector('.hero-section .tagline');
        const heroBtns = document.querySelector('.hero-section > div'); // Buttons container

        if (heroTitle) heroTitle.classList.add('hero-animate');
        if (heroTagline) heroTagline.classList.add('hero-animate', 'hero-animate-delay-1');
        if (heroBtns) heroBtns.classList.add('hero-animate', 'hero-animate-delay-2');
    }

    setupScrollObserver() {
        const options = {
            root: null,
            rootMargin: '0px 0px -50px 0px', // Trigger slightly before element is fully in view
            threshold: 0.1
        };

        this.observer = new IntersectionObserver((entries, obs) => {
            entries.forEach(entry => {
                const target = entry.target;

                if (entry.isIntersecting) {
                    // Element enters viewport - Play animation
                    if (target.classList.contains('scroll-trigger-animation')) {
                        target.classList.add('play');
                    } else {
                        target.classList.add('visible');
                    }
                } else {
                    // Element leaves viewport - Reset animation so it can play again
                    if (target.classList.contains('scroll-trigger-animation')) {
                        target.classList.remove('play');
                    } else {
                        target.classList.remove('visible');
                    }
                }
            });
        }, options);
    }

    targetElements() {
        if (!this.observer) return;

        // 1. Feature Cards (Staggered)
        document.querySelectorAll('.feature-card').forEach((card, index) => {
            card.classList.add('reveal-card');
            // Stagger based on column position (approximate)
            const staggerIndex = (index % 3) + 1;
            card.classList.add(`stagger-${staggerIndex}`);
            this.observer.observe(card);
        });

        // 2. Section Titles
        document.querySelectorAll('.section-title').forEach(title => {
            title.classList.add('reveal-title');
            this.observer.observe(title);
        });

        // 3. Workflow Steps (Complex Animation Trigger)
        // These already have their own keyframes, we just pause/play them
        document.querySelectorAll('.workflow-step').forEach(step => {
            step.classList.add('scroll-trigger-animation');
            this.observer.observe(step);
        });

        // 4. Prototype Screenshots
        document.querySelectorAll('.screenshot-item').forEach((item, index) => {
            item.classList.add('reveal-card');
            const staggerIndex = (index % 3) + 1;
            item.classList.add(`stagger-${staggerIndex}`);
            this.observer.observe(item);
        });

        // 5. CTA Section
        const cta = document.querySelector('.cta-section');
        if (cta) {
            cta.classList.add('scroll-reveal');
            this.observer.observe(cta);
        }

        // 6. How It Works Section Container (for the diagram lines opacity)
        const diagram = document.querySelector('.diagram-container');
        if (diagram) {
            diagram.classList.add('scroll-reveal');
            this.observer.observe(diagram);
        }
    }
}

// Initialize on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new MotionPolish());
} else {
    new MotionPolish();
}
