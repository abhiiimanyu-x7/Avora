/**
 * AVORA Theme System
 * Instant, 1-click theme toggling with zero flash and localStorage persistence.
 */

(function() {
    // Immediate execution before DOM renders to prevent theme flash
    const savedTheme = localStorage.getItem('avora-theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme = savedTheme ? savedTheme : (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', initialTheme);
})();

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('avora-theme', next);
    
    // Dispatch custom event for Alpine or other listeners
    window.dispatchEvent(new CustomEvent('theme-changed', { detail: { theme: next } }));
}

window.toggleTheme = toggleTheme;
