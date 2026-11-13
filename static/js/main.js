/**
 * AVORA Main JavaScript
 * Institutional Campus System
 * HTMX + Alpine.js + Native Flask
 */

/* ── Toast Notification System ── */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        success: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        error: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        warning: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        info: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        ${icons[type] || icons.info}
        <span style="flex: 1;">${message}</span>
        <button class="toast-close" aria-label="Close">&times;</button>
    `;

    toast.querySelector('.toast-close').onclick = () => toast.remove();
    container.appendChild(toast);

    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.25s ease';
            setTimeout(() => toast.remove(), 250);
        }
    }, 4500);
}

window.showToast = showToast;

/* ── Live Notification Status ── */
async function loadNotifications() {
    const badges = document.querySelectorAll('.notif-badge-count');
    if (!badges.length) return;

    try {
        const res = await fetch('/notifications');
        if (!res.ok) return;
        const data = await res.json();
        badges.forEach(badge => {
            if (data.unread_count > 0) {
                badge.textContent = data.unread_count > 9 ? '9+' : data.unread_count;
                badge.style.display = 'inline-flex';
            } else {
                badge.style.display = 'none';
            }
        });
    } catch (e) {
        // silent fail
    }
}

async function markAllNotificationsRead() {
    try {
        await fetch('/notifications/read-all', { method: 'POST' });
        const badges = document.querySelectorAll('.notif-badge-count');
        badges.forEach(b => b.style.display = 'none');
    } catch (e) {
        // silent fail
    }
}

/* ── Mobile Sidebar Navigation ── */
function bindMobileMenu() {
    const toggle = document.getElementById('mobile-toggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (toggle && sidebar && overlay) {
        toggle.onclick = () => {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        };
        overlay.onclick = () => {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        };
    }
}

/* ── Ask Avora Slide-in Panel with Intelligent Context ── */
function initAskAvora() {
    const launcher = document.getElementById('ask-avora-launcher');
    const panel = document.getElementById('ask-avora-panel');
    const overlay = document.getElementById('ask-avora-overlay');
    const closeBtn = document.getElementById('ask-avora-close');
    const form = document.getElementById('ask-avora-form');
    const input = document.getElementById('ask-avora-input');
    const messages = document.getElementById('ask-avora-messages');

    if (!launcher || !panel) return;

    // Multi-turn conversation context
    const chatHistory = [];

    const openPanel = () => {
        panel.classList.add('active');
        if (overlay) overlay.classList.add('active');
        if (input) input.focus();
    };

    const closePanel = () => {
        panel.classList.remove('active');
        if (overlay) overlay.classList.remove('active');
    };

    launcher.onclick = openPanel;
    if (closeBtn) closeBtn.onclick = closePanel;
    if (overlay) overlay.onclick = closePanel;

    const formatMessageText = (text) => {
        if (!text) return '';
        // Escape basic HTML
        let escaped = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Bold **text**
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // URLs to clickable links
        escaped = escaped.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer" style="color: var(--accent); text-decoration: underline;">$1</a>');

        // Convert bullet points • or - into neat lines
        const lines = escaped.split('\n');
        const formattedLines = lines.map(line => {
            const trimmed = line.trim();
            if (trimmed.startsWith('•') || trimmed.startsWith('-')) {
                return `<div style="display: flex; gap: 8px; margin-top: 4px; line-height: 1.5;"><span>•</span><div>${trimmed.replace(/^[•\-]\s*/, '')}</div></div>`;
            }
            return line;
        });

        return formattedLines.join('<br>').replace(/(<br\s*\/?>\s*){3,}/g, '<br><br>');
    };

    if (form && input && messages) {
        form.onsubmit = async (e) => {
            e.preventDefault();
            const query = input.value.trim();
            if (!query) return;

            // Append user bubble
            const userMsg = document.createElement('div');
            userMsg.className = 'ask-avora-msg ask-avora-msg-user';
            userMsg.textContent = query;
            messages.appendChild(userMsg);
            input.value = '';
            messages.scrollTop = messages.scrollHeight;

            // Append loading indicator
            const botMsg = document.createElement('div');
            botMsg.className = 'ask-avora-msg ask-avora-msg-bot';
            botMsg.innerHTML = '<span class="text-muted" style="font-size: 0.825rem;">Consulting KMCLU records...</span>';
            messages.appendChild(botMsg);
            messages.scrollTop = messages.scrollHeight;

            try {
                const res = await fetch('/ask-avora/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        history: chatHistory.slice(-6)
                    })
                });

                if (!res.ok) {
                    botMsg.innerHTML = 'Ask Avora is temporarily unavailable. Please try again.';
                    return;
                }

                const data = await res.json();

                // Save to conversation history for multi-turn tracking
                chatHistory.push({
                    query: query,
                    answer: data.answer,
                    entity: data.entity || null
                });

                let html = `<div>${formatMessageText(data.answer)}</div>`;

                // Render interactive clarification chips if provided
                if (data.clarification_options && data.clarification_options.length) {
                    html += `<div class="ask-avora-options-container" style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px;">`;
                    data.clarification_options.forEach(opt => {
                        html += `<button type="button" class="ask-clarification-chip badge badge-department" style="cursor: pointer; background: var(--surface-2); border: 1px solid var(--border); font-size: 0.72rem; padding: 4px 10px; border-radius: 999px;" data-opt="${encodeURIComponent(opt)}">${opt}</button>`;
                    });
                    html += `</div>`;
                }

                // Render Action Button if applicable
                if (data.action_link && data.action_link.url) {
                    html += `<div style="margin-top: 10px;">
                        <a href="${data.action_link.url}" class="btn btn-sm btn-primary" style="font-size: 0.75rem; padding: 4px 12px; display: inline-flex; align-items: center; gap: 6px; text-decoration: none;">
                            ${data.action_link.label} &rarr;
                        </a>
                    </div>`;
                }

                // Render clean source citation (never generic svgSource)
                if (data.source) {
                    const isWeb = data.web_sourced || (data.source && data.source.toLowerCase().includes('external'));
                    const chipClass = isWeb ? 'ask-avora-source-chip ask-avora-source-web' : 'ask-avora-source-chip';
                    const icon = isWeb
                        ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
                        : '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg>';
                    html += `<div class="${chipClass}">
                        ${icon}
                        Source: ${data.source}
                    </div>`;
                }

                botMsg.innerHTML = html;

                // Bind chip clicks to auto-submit
                botMsg.querySelectorAll('.ask-clarification-chip').forEach(btn => {
                    btn.onclick = () => {
                        const optText = decodeURIComponent(btn.getAttribute('data-opt'));
                        input.value = optText;
                        form.dispatchEvent(new Event('submit'));
                    };
                });

            } catch (err) {
                botMsg.innerHTML = 'Ask Avora is temporarily unavailable. Please try again.';
            } finally {
                messages.scrollTop = messages.scrollHeight;
            }
        };
    }
}

document.addEventListener('DOMContentLoaded', function () {
    loadNotifications();
    bindMobileMenu();
    initAskAvora();
});
