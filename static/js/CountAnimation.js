
document.addEventListener('DOMContentLoaded', () => {
    const duration = 1500; // durée de l'animation en ms

    function animateNumber(el, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            el.textContent = Math.floor(progress * (end - start) + start).toLocaleString();
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }

    const animatedNumbers = document.querySelectorAll('.animated-number');
    animatedNumbers.forEach(el => {
        const endValue = parseFloat(el.getAttribute('data-value')) || 0;
        animateNumber(el, 0, endValue, duration);
    });
});
