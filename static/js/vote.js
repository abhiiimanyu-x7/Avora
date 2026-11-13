/**
 * Avora - Vote page JS
 * Handles candidate selection, vote confirmation modal, and submission.
 */

document.addEventListener('DOMContentLoaded', function () {
    const candidateLabels = document.querySelectorAll('[data-candidate-id]');
    const voteBtn = document.getElementById('vote-btn');
    const modal = document.getElementById('vote-modal');
    const cancelBtn = document.getElementById('vote-cancel');
    const confirmBtn = document.getElementById('vote-confirm');

    if (!candidateLabels.length || !voteBtn) return;

    let selectedCandidateId = null;

    // Candidate selection
    candidateLabels.forEach(label => {
        const radio = label.querySelector('input[type="radio"]');
        label.addEventListener('click', () => {
            // Reset all
            candidateLabels.forEach(l => {
                l.style.borderColor = 'var(--border)';
                const check = l.querySelector('.vote-check');
                if (check) {
                    check.style.borderColor = 'var(--gray-300)';
                    check.style.background = 'transparent';
                    check.innerHTML = '';
                }
            });

            // Select this one
            radio.checked = true;
            selectedCandidateId = label.getAttribute('data-candidate-id');
            label.style.borderColor = 'var(--accent)';
            const check = label.querySelector('.vote-check');
            if (check) {
                check.style.borderColor = 'var(--accent)';
                check.style.background = 'var(--accent)';
                check.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
            }

            voteBtn.disabled = false;
        });
    });

    // Open modal
    voteBtn.addEventListener('click', () => {
        if (!selectedCandidateId) return;
        modal.classList.add('active');
    });

    // Cancel modal
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }

    // Close modal on backdrop click
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.classList.remove('active');
        });
    }

    // Confirm vote
    if (confirmBtn) {
        confirmBtn.addEventListener('click', async () => {
            if (!selectedCandidateId) return;

            confirmBtn.disabled = true;
            confirmBtn.textContent = 'Submitting...';

            try {
                const electionId = window.location.pathname.split('/vote/')[1];
                const res = await fetch(`/student/vote/${electionId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ candidate_id: selectedCandidateId }),
                });

                const data = await res.json();

                if (data.success) {
                    showToast('Vote cast successfully!', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    showToast(data.message || 'Failed to cast vote.', 'error');
                    modal.classList.remove('active');
                    confirmBtn.disabled = false;
                    confirmBtn.textContent = 'Confirm Vote';
                }
            } catch (e) {
                showToast('Network error. Please try again.', 'error');
                modal.classList.remove('active');
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Confirm Vote';
            }
        });
    }
});
