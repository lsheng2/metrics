document.addEventListener('DOMContentLoaded', function () {
    let activeFrame = null;
    let activeHost = null;
    let activeContext = '';
    let generation = 0;

    function theme() {
        return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
    }

    function openView(message) {
        if (!['metrics.openChart', 'metrics.openEvidence'].includes(message.actionId)) return;
        const payload = message.payload;
        if (Object.keys(payload).some(key => !['chart_id', 'bucket', 'series'].includes(key))) return;
        if (typeof payload.chart_id !== 'string' || !/^[A-Za-z0-9._:-]{1,160}$/.test(payload.chart_id)) return;
        if (['bucket', 'series'].some(key => payload[key] !== undefined
            && (typeof payload[key] !== 'string' || payload[key].length > 160))) return;
        const url = new URL(window.location.href);
        url.searchParams.set('chart_id', payload.chart_id);
        ['bucket', 'series'].forEach(key => {
            if (message.actionId === 'metrics.openEvidence' && payload[key]) {
                url.searchParams.set(key, payload[key]);
            } else {
                url.searchParams.delete(key);
            }
        });
        const target = `${url.pathname}${url.search}`;
        if (window.htmx) {
            window.history.pushState({}, '', target);
            window.htmx.ajax('GET', target, {
                target: '.workbench-shell', select: '.workbench-shell', swap: 'outerHTML ignoreTitle:true'
            }).then(() => {
                const pane = message.actionId === 'metrics.openEvidence' ? 'evidence' : 'chart';
                document.querySelector(`[data-workbench-pane="${pane}"]`)?.scrollIntoView({ block: 'nearest' });
            });
        } else {
            window.location.assign(target);
        }
    }

    function discard() {
        activeHost?.dispose();
        activeFrame = null;
        activeHost = null;
        activeContext = '';
    }

    async function initialize() {
        const currentGeneration = ++generation;
        const contextNode = document.getElementById('workbench-ai-context');
        const frame = document.querySelector('.workbench-ai-chat-frame');
        if (!contextNode || !frame) {
            discard();
            return;
        }
        const runtime = JSON.parse(contextNode.textContent).runtime;
        if (!runtime.context_ref || !runtime.session_id || !runtime.embed_host_url) {
            discard();
            return;
        }
        if (activeFrame === frame && activeHost) {
            activeHost.setTheme(theme());
            const nextContext = JSON.stringify(runtime.context_ref);
            if (nextContext !== activeContext) {
                activeContext = nextContext;
                activeHost.notifyContextChanged(runtime.session_id);
            }
            return;
        }
        discard();
        try {
            const asset = new URL(runtime.embed_host_url, window.location.href);
            if (asset.origin !== window.location.origin) throw new Error('embed asset origin');
            const { EmbedHost } = await import(asset.href);
            if (currentGeneration !== generation || !frame.isConnected) return;
            const host = new EmbedHost(frame, {
                onReady() {
                    host.setTheme(theme());
                },
                onHostAction: openView,
            });
            activeFrame = frame;
            activeHost = host;
            activeContext = JSON.stringify(runtime.context_ref);
            host.setTheme(theme());
            frame.dataset.embedHostReady = 'true';
        } catch {
            const error = document.querySelector('[data-ai-embed-error]');
            if (error) error.hidden = false;
        }
    }

    initialize();
    document.addEventListener('workbench:ask-ai', async event => {
        const { ticketIds, button } = event.detail;
        const shell = document.querySelector('.workbench-shell');
        if (!shell || !Array.isArray(ticketIds) || !ticketIds.length || !window.htmx || button.disabled) return;
        const previous = window.location.href;
        const url = new URL(previous);
        url.searchParams.delete('ticket_id');
        ticketIds.forEach(id => url.searchParams.append('ticket_id', id));
        const target = `${url.pathname}${url.search}`;
        button.disabled = true;
        window.history.replaceState({}, '', target);
        try {
            await window.htmx.ajax('GET', target, {
                source: button, target: '.workbench-shell', select: '.workbench-shell', swap: 'outerHTML ignoreTitle:true',
            });
            document.querySelector('[data-workbench-pane="ai-assistant"]')?.scrollIntoView({ block: 'nearest' });
            document.querySelector('.workbench-ai-chat-frame')?.focus();
        } catch {
            if (window.location.href === url.href) window.history.replaceState({}, '', previous);
        } finally {
            button.disabled = false;
        }
    });
    document.body.addEventListener('htmx:afterSwap', initialize);
    document.addEventListener('dashboard:themechange', () => activeHost?.setTheme(theme()));
    window.addEventListener('pagehide', discard);
});
