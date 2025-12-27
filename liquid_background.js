/**
 * Liquid Background Component
 * Adds a subtle fluid/liquid ambient background to the home screen.
 * VISUAL-ONLY enhancement.
 */

class LiquidBackground {
    constructor(targetSelector = '#landingPage') {
        this.target = document.querySelector(targetSelector);
        if (!this.target) {
            this.target = document.body;
        }
        this.init();
    }

    init() {
        // Create container
        this.container = document.createElement('div');
        this.container.className = 'liquid-background';

        // SVG Filter for "Gooey" effect
        // High contrast alpha channel creates the liquid surface tension look
        const svgFilter = `
            <svg style="position: absolute; width: 0; height: 0; pointer-events: none;" aria-hidden="true">
                <defs>
                    <filter id="liquidGoo">
                        <feGaussianBlur in="SourceGraphic" stdDeviation="30" result="blur" />
                        <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 30 -12" result="goo" />
                        <feComposite in="SourceGraphic" in2="goo" operator="atop"/>
                    </filter>
                </defs>
            </svg>
        `;

        // Generate blobs
        let blobsHtml = '';
        const blobCount = 6;
        for (let i = 0; i < blobCount; i++) {
            blobsHtml += `<div class="liquid-blob liquid-blob-${i}"></div>`;
        }

        this.container.innerHTML = blobsHtml + svgFilter;

        // Inject Styles dynamically
        if (!document.getElementById('liquid-bg-styles')) {
            const style = document.createElement('style');
            style.id = 'liquid-bg-styles';
            style.textContent = `
                .liquid-background {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    overflow: hidden;
                    z-index: -1;
                    /* Subtle dark radial gradient base to create depth */
                    background: radial-gradient(circle at center, rgba(15, 20, 30, 0.4) 0%, rgba(5, 5, 10, 0.8) 100%);
                    opacity: 0.8; /* Slightly increased for visibility */
                    pointer-events: none;
                    transform: translateZ(0);
                }

                .liquid-blob {
                    position: absolute;
                    border-radius: 50%;
                    /* Lighter grey to contrast with black background, but still dark/neutral */
                    background: #3e4452; 
                    transform-origin: center center;
                    opacity: 1; 
                }
                
                /* Apply filter to container to blend blobs */
                .liquid-background {
                    filter: url('#liquidGoo');
                }

                @keyframes liquidFloat {
                    0% { transform: translate(0, 0) rotate(0deg) scale(1); }
                    33% { transform: translate(20px, -80px) rotate(10deg) scale(1.1); }
                    66% { transform: translate(-20px, 40px) rotate(-5deg) scale(0.9); }
                    100% { transform: translate(0, 0) rotate(0deg) scale(1); }
                }
                
                @keyframes liquidFloatReverse {
                    0% { transform: translate(0, 0) rotate(0deg) scale(1); }
                    33% { transform: translate(-20px, 70px) rotate(-10deg) scale(0.95); }
                    66% { transform: translate(30px, -30px) rotate(5deg) scale(1.05); }
                    100% { transform: translate(0, 0) rotate(0deg) scale(1); }
                }

                /* Large organic shapes - refined positioning for lava feel */
                .liquid-blob-0 { width: 50vw; height: 50vw; top: -15%; left: -10%; animation: liquidFloat 45s infinite ease-in-out; }
                .liquid-blob-1 { width: 45vw; height: 45vw; bottom: -10%; right: -5%; animation: liquidFloatReverse 40s infinite ease-in-out; }
                .liquid-blob-2 { width: 35vw; height: 35vw; top: 40%; left: 30%; animation: liquidFloat 50s infinite ease-in-out -5s; }
                .liquid-blob-3 { width: 30vw; height: 30vw; top: 15%; right: 20%; animation: liquidFloatReverse 35s infinite ease-in-out -12s; }
                .liquid-blob-4 { width: 40vw; height: 40vw; bottom: 5%; left: 5%; animation: liquidFloat 55s infinite ease-in-out -18s; }
                .liquid-blob-5 { width: 25vw; height: 25vw; top: 55%; right: 45%; animation: liquidFloatReverse 48s infinite ease-in-out -25s; }

                @media (prefers-reduced-motion: reduce) {
                    .liquid-blob {
                        animation: none;
                        opacity: 0.3;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        if (this.target.firstChild) {
            this.target.insertBefore(this.container, this.target.firstChild);
        } else {
            this.target.appendChild(this.container);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('landingPage')) {
        new LiquidBackground('#landingPage');
        console.log('Liquid Background initialized');
    }
});
