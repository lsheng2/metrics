(function () {
    if (window.projectRunStatusPolling) return;
    window.projectRunStatusPolling = true;
    let timer = null;
    let controller = null;
    let stopped = false;
    let epoch = 0;

    function stop() {
        stopped = true;
        epoch++;
        window.clearTimeout(timer);
        timer = null;
        if (controller) controller.abort();
    }

    function unavailable() {
        stop();
        const notice = document.querySelector('[data-run-poll-error]');
        if (notice) notice.hidden = false;
    }

    function schedule() {
        const root = document.getElementById('project-run-status-fragment');
        if (!stopped && !controller && timer === null && root?.dataset.runStatusUrl) {
            timer = window.setTimeout(poll, 2000);
        }
    }

    async function poll() {
        timer = null;
        const root = document.getElementById('project-run-status-fragment');
        if (stopped || !root?.dataset.runStatusUrl) return;
        const currentEpoch = epoch;
        let deadline = null;
        try {
            const url = new URL(root.dataset.runStatusUrl, window.location.href);
            if (url.origin !== window.location.origin || url.pathname !== window.location.pathname ||
                url.username || url.password || url.search || url.hash) {
                throw new Error('Invalid status endpoint');
            }
            controller = new AbortController();
            deadline = window.setTimeout(() => controller?.abort(), 10000);
            const response = await window.fetch(url.href, {
                method: 'GET',
                headers: { 'HX-Request': 'true' },
                credentials: 'same-origin',
                cache: 'no-store',
                redirect: 'error',
                signal: controller.signal,
            });
            if (!response.ok || response.redirected ||
                !response.headers.get('Content-Type')?.startsWith('text/html')) {
                throw new Error('Status response unavailable');
            }
            const html = await response.text();
            if (stopped || currentEpoch !== epoch || root !== document.getElementById(root.id)) return;
            const parsed = new DOMParser().parseFromString(html, 'text/html');
            const next = parsed.getElementById(root.id);
            if (!next || parsed.body.children.length !== 1 || parsed.body.firstElementChild !== next ||
                next.dataset.operationId !== root.dataset.operationId) {
                throw new Error('Status response identity mismatch');
            }
            root.replaceWith(next);
            const notice = document.querySelector('[data-run-poll-error]');
            if (notice) notice.hidden = true;
        } catch (error) {
            if (!stopped && currentEpoch === epoch && root.isConnected) unavailable();
        } finally {
            window.clearTimeout(deadline);
            controller = null;
            schedule();
        }
    }

    window.addEventListener('pagehide', stop);
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            stopped = false;
            schedule();
        }
    });
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', schedule, { once: true });
    } else {
        schedule();
    }
}());
