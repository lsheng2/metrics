import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const sourcePath = 'ui_web/static/js/project_run_status.js';
const source = fs.existsSync(sourcePath) ? fs.readFileSync(sourcePath, 'utf8') : '';
const origin = 'http://127.0.0.1:8127';
const pathname = '/reports/runs/operation-1/';

function browser({ deferred = false, status = 200, nextId = 'operation-1', pollUrl = pathname } = {}) {
    let current;
    let resolveResponse;
    let rejectResponse;
    let count = 0;
    let lastRequest;
    const timers = new Map();
    const listeners = new Map();
    const error = { hidden: true };
    const element = (state, id, url) => ({
        id: 'project-run-status-fragment',
        isConnected: true,
        state,
        controls: state === 'queued' ? ['cancel'] : ['produced-revision', 'latest-draft'],
        dataset: { operationId: id, ...(url ? { runStatusUrl: url } : {}) },
        replaceWith(next) {
            this.isConnected = false;
            current = next;
        },
    });
    current = element('queued', 'operation-1', pollUrl);
    const html = '<div id="project-run-status-fragment"><h2>draft_ready</h2></div>';
    const response = {
        ok: status === 200,
        redirected: false,
        status,
        headers: { get: () => 'text/html; charset=utf-8' },
        url: origin + pathname,
        async text() { return html; },
    };
    const pending = deferred ? new Promise((resolve, reject) => {
        resolveResponse = resolve;
        rejectResponse = reject;
    }) : null;
    const document = {
        readyState: 'complete',
        getElementById(id) { return id === 'project-run-status-fragment' ? current : null; },
        querySelector(selector) { return selector === '[data-run-poll-error]' ? error : null; },
        addEventListener(name, callback) { listeners.set(name, callback); },
    };
    const window = {
        location: { href: origin + pathname, origin, pathname },
        addEventListener(name, callback) { listeners.set(name, callback); },
        setTimeout(callback, delay) {
            const id = Symbol('timer');
            timers.set(id, { callback, delay });
            return id;
        },
        clearTimeout(id) { timers.delete(id); },
        async fetch(url, options) {
            count++;
            lastRequest = options;
            assert.equal(String(url), origin + pathname);
            assert.equal(options.method, 'GET');
            assert.equal(options.headers['HX-Request'], 'true');
            assert.equal(options.credentials, 'same-origin');
            if (pending) {
                options.signal.addEventListener('abort', () => rejectResponse(new Error('aborted')), { once: true });
            }
            return pending || response;
        },
    };
    const context = {
        document, window, URL, AbortController,
        DOMParser: class {
            parseFromString(value, type) {
                assert.equal(value, html);
                assert.equal(type, 'text/html');
                const next = element('draft_ready', nextId);
                return {
                    body: { children: [next], firstElementChild: next },
                    getElementById(id) { return id === next.id ? next : null; },
                };
            }
        },
    };
    vm.createContext(context);
    vm.runInContext(source, context);
    return {
        get state() { return current.state; },
        get controls() { return current.controls; },
        get errorShown() { return !error.hidden; },
        get requests() { return count; },
        get aborted() { return lastRequest?.signal.aborted; },
        get pollTimers() { return [...timers.values()].filter(timer => timer.delay === 2000).length; },
        async tick(delay = 2000) {
            const entry = [...timers].find(([, timer]) => timer.delay === delay);
            if (!entry) return;
            timers.delete(entry[0]);
            await entry[1].callback();
        },
        hide() { listeners.get('pagehide')?.(); },
        respond() { resolveResponse?.(response); },
    };
}

test('queued status becomes the produced revision without loading full HTMX', async () => {
    const page = browser();
    await page.tick();
    assert.equal(page.state, 'draft_ready');
    assert.deepEqual(page.controls, ['produced-revision', 'latest-draft']);
    assert.equal(page.pollTimers, 0);
});

test('a slow status response cannot overlap another request', async () => {
    const page = browser({ deferred: true });
    const pending = page.tick();
    await page.tick();
    assert.equal(page.requests, 1);
    page.respond();
    await pending;
    assert.equal(page.state, 'draft_ready');
});

for (const [name, options] of [
    ['server failure', { status: 503 }],
    ['another operation', { nextId: 'operation-2' }],
    ['external status endpoint', { pollUrl: 'https://external.example/status' }],
]) {
    test(`${name} retains the old state and exposes unavailable status`, async () => {
        const page = browser(options);
        await page.tick();
        assert.equal(page.state, 'queued');
        assert.equal(page.errorShown, true);
        assert.equal(page.pollTimers, 0);
        if (options.pollUrl) assert.equal(page.requests, 0);
    });
}

test('leaving the page aborts the request without replacing the old document', async () => {
    const page = browser({ deferred: true });
    const pending = page.tick();
    page.hide();
    await pending;
    assert.equal(page.aborted, true);
    assert.equal(page.state, 'queued');
    assert.equal(page.errorShown, false);
    assert.equal(page.pollTimers, 0);
});

test('a stalled response reaches a bounded unavailable state', async () => {
    const page = browser({ deferred: true });
    const pending = page.tick();
    await page.tick(10000);
    await pending;
    assert.equal(page.errorShown, true);
    assert.equal(page.state, 'queued');
    assert.equal(page.pollTimers, 0);
});
