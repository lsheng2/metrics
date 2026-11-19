"""Browser reader for the required-field state that form-validation.js publishes."""

# Each missing control is re-measured without its hook class (transitions off) to prove that
# foundation/forms.css keeps the state visible, including on the focused field.
REQUIRED_STATE_SCRIPT = """
    () => {
        const missing = Array.from(document.querySelectorAll('.is-required-missing-control'));
        const visibleBorderCount = missing.filter(field => {
            field.style.transition = 'none';
            const missingBorder = getComputedStyle(field).borderTopColor;
            field.classList.remove('is-required-missing-control');
            const plainBorder = getComputedStyle(field).borderTopColor;
            field.classList.add('is-required-missing-control');
            field.style.removeProperty('transition');
            return missingBorder !== plainBorder;
        }).length;
        return {
            missing_names: missing.map(field => field.name),
            visible_border_count: visibleBorderCount,
            summary_visible: !document.querySelector('[data-required-summary]').classList.contains('is-hidden'),
            focused_id: document.activeElement.id,
            messages: Array.from(document.querySelectorAll('.dashboard-required-message')).map(message => message.textContent),
        };
    }
"""
