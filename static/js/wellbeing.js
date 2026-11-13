/**
 * Avora - Digital Wellbeing JS
 * Handles mood selection highlighting and trend interaction.
 */

document.addEventListener('DOMContentLoaded', function () {
    // Mood option interactive selection
    const moodOptions = document.querySelectorAll('.mood-option');
    moodOptions.forEach(opt => {
        const radio = opt.querySelector('input[type="radio"]');
        if (radio && radio.checked) {
            opt.style.borderColor = 'var(--accent)';
            opt.style.background = 'var(--accent-subtle)';
        }

        opt.addEventListener('click', () => {
            moodOptions.forEach(o => {
                o.style.borderColor = 'var(--border)';
                o.style.background = '';
            });
            opt.style.borderColor = 'var(--accent)';
            opt.style.background = 'var(--accent-subtle)';
        });
    });

    // Trend chart bar animation on load
    const bars = document.querySelectorAll('#mood-chart div > div');
    bars.forEach(bar => {
        const targetHeight = bar.style.height;
        bar.style.height = '0%';
        setTimeout(() => {
            bar.style.height = targetHeight;
        }, 150);
    });
});
