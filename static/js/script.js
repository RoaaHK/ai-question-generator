document.addEventListener('DOMContentLoaded', function() {

    const images = document.querySelectorAll('.image-container img');
    const textBoxes = document.querySelectorAll('.text-box');
    const decorativeElements = document.querySelectorAll('.decorative-arrow, .decorative-planet');
    const primaryButton = document.querySelector('.primary-button');

    const animateImages = () => {
        images.forEach((img, index) => {
            img.style.animation = `float-${index} 3s ease-in-out ${index * 0.5}s infinite`;

            const keyframes = `
                @keyframes float-${index} {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-8px); }
                }
            `;

            const style = document.createElement('style');
            style.textContent = keyframes;
            document.head.appendChild(style);
        });
    };

    const animateTextBoxes = () => {
        textBoxes.forEach((box, index) => {
            setTimeout(() => {
                box.style.transform = 'translateY(-5px)';
                box.style.boxShadow = '0 8px 16px rgba(0, 0, 0, 0.12)';

                setTimeout(() => {
                    box.style.transform = 'translateY(0)';
                    box.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.08)';
                }, 300);
            }, index * 200);

            box.addEventListener('mouseenter', () => {
                box.style.transform = 'translateY(-4px)';
                box.style.boxShadow = '0 8px 16px rgba(0, 0, 0, 0.12)';
            });

            box.addEventListener('mouseleave', () => {
                box.style.transform = 'translateY(0)';
                box.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.08)';
            });
        });
    };

    const animateDecorative = () => {
        decorativeElements.forEach((element, index) => {
            if (element.classList.contains('decorative-planet')) {
                element.style.animation = 'planet-float 6s ease-in-out infinite';

                const keyframes = `
                    @keyframes planet-float {
                        0%, 100% { transform: translateY(0); }
                        50% { transform: translateY(-12px); }
                    }
                `;

                const style = document.createElement('style');
                style.textContent = keyframes;
                document.head.appendChild(style);
            } else {
                const isRightTop = element.classList.contains('right-top');
                const isLeftTop = element.classList.contains('left-top');
                const startRotation = isRightTop ? -20 : isLeftTop ? -10 : 180;

                element.style.animation = `arrow-rotate-${index} 5s ease-in-out infinite`;

                const keyframes = `
                    @keyframes arrow-rotate-${index} {
                        0%, 100% { transform: rotate(${startRotation}deg); }
                        50% { transform: rotate(${startRotation + (isRightTop ? 5 : isLeftTop ? -5 : -5)}deg); }
                    }
                `;

                const style = document.createElement('style');
                style.textContent = keyframes;
                document.head.appendChild(style);
            }
        });
    };

    const animateButton = () => {
        if (primaryButton) {
            primaryButton.addEventListener('mouseenter', () => {
                primaryButton.style.transform = 'translateY(-5px)';
                primaryButton.style.boxShadow = '0 10px 20px rgba(0, 0, 0, 0.15)';
            });

            primaryButton.addEventListener('mouseleave', () => {
                primaryButton.style.transform = 'translateY(0)';
                primaryButton.style.boxShadow = '0 5px 10px rgba(0, 0, 0, 0.12)';
            });

            primaryButton.style.animation = 'pulse 2s infinite';

            const keyframes = `
                @keyframes pulse {
                    0% { box-shadow: 0 0 0 0 rgba(51, 138, 103, 0.6); }
                    70% { box-shadow: 0 0 0 10px rgba(51, 138, 103, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(51, 138, 103, 0); }
                }
            `;

            const style = document.createElement('style');
            style.textContent = keyframes;
            document.head.appendChild(style);
        }
    };

    animateImages();
    animateTextBoxes();
    animateDecorative();
    animateButton();
});