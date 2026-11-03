import assert from 'node:assert/strict';
import { createHash, webcrypto } from 'node:crypto';
import fs from 'node:fs';
import vm from 'node:vm';

class FakeClassList {
    constructor() {
        this.values = new Set();
    }

    toggle(name, force) {
        if (force) {
            this.values.add(name);
        } else {
            this.values.delete(name);
        }
    }

    contains(name) {
        return this.values.has(name);
    }
}

class FakeElement {
    constructor({ dataset = {}, value = '', type = 'text' } = {}) {
        this.dataset = dataset;
        this.value = value;
        this.type = type;
        this.checked = false;
        this.disabled = false;
        this.textContent = '';
        this.listeners = {};
        this.attributes = new Map();
        this.classList = new FakeClassList();
        this.childrenBySelector = new Map();
        this.listsBySelector = new Map();
    }

    addEventListener(name, callback) {
        this.listeners[name] = this.listeners[name] || [];
        this.listeners[name].push(callback);
    }

    async dispatch(name) {
        const event = {
            type: name,
            target: this,
            defaultPrevented: false,
            preventDefault() {
                this.defaultPrevented = true;
            },
        };
        for (const callback of this.listeners[name] || []) {
            await callback(event);
        }
        return event;
    }

    querySelector(selector) {
        return this.childrenBySelector.get(selector) || null;
    }

    querySelectorAll(selector) {
        return this.listsBySelector.get(selector) || [];
    }

    setAttribute(name, value) {
        this.attributes.set(name, String(value));
    }

    hasAttribute(name) {
        return this.attributes.has(name);
    }
}

const payload = {
    schema_version: 1,
    draft_id: 'draft-1',
    revision: 2,
    revision_hash: 'a'.repeat(64),
    snapshot_hash: 'b'.repeat(64),
    template_hash: 'c'.repeat(64),
    html_fragment: '<table><tr><td>ok</td></tr></table>',
    plain_text: 'ok',
    clipboard_available: true,
};
payload.html_sha256 = createHash('sha256').update(payload.html_fragment).digest('hex');
payload.plain_sha256 = createHash('sha256').update(payload.plain_text).digest('hex');
const badPayload = { ...payload, html_sha256: '0'.repeat(64) };

const root = new FakeElement({
    dataset: {
        reportEditor: '',
        draftId: payload.draft_id,
        revision: String(payload.revision),
        revisionHash: payload.revision_hash,
        snapshotHash: payload.snapshot_hash,
        templateHash: payload.template_hash,
        clipboardUrl: '/clipboard',
        messagePayloadMissing: 'payload missing',
        messageDownloadFallback: 'payload failed',
        messageReady: 'ready',
        messageSaveBeforeCopy: 'save first',
        messageNativeUnavailable: 'native missing',
        messageCopied: 'copied',
        messageCopyFailed: 'copy failed',
    },
});
const field = new FakeElement({ value: 'initial' });
const copyButton = new FakeElement();
const finalizeButton = new FakeElement();
const status = new FakeElement();
const dirtyBanner = new FakeElement();
const form = new FakeElement();
const languageForm = new FakeElement();

root.childrenBySelector.set('[data-report-save-form]', form);
root.childrenBySelector.set('[data-report-dirty-banner]', dirtyBanner);
root.childrenBySelector.set('[data-report-copy-button]', copyButton);
root.childrenBySelector.set('[data-report-finalize-button]', finalizeButton);
root.childrenBySelector.set('[data-report-copy-status]', status);
root.listsBySelector.set('[data-report-dirty-field]', [field]);
root.listsBySelector.set('form[action*="projects/language"]', [languageForm]);

const badRoot = new FakeElement({
    dataset: {
        ...root.dataset,
        clipboardUrl: '/bad-clipboard',
    },
});
const badCopyButton = new FakeElement();
const badStatus = new FakeElement();
badRoot.childrenBySelector.set('[data-report-save-form]', new FakeElement());
badRoot.childrenBySelector.set('[data-report-dirty-banner]', new FakeElement());
badRoot.childrenBySelector.set('[data-report-copy-button]', badCopyButton);
badRoot.childrenBySelector.set('[data-report-finalize-button]', new FakeElement());
badRoot.childrenBySelector.set('[data-report-copy-status]', badStatus);
badRoot.listsBySelector.set('[data-report-dirty-field]', [new FakeElement({ value: 'initial' })]);

const documentListeners = {};
const document = {
    body: new FakeElement(),
    addEventListener(name, callback) {
        documentListeners[name] = documentListeners[name] || [];
        documentListeners[name].push(callback);
    },
    querySelectorAll(selector) {
        return selector === '[data-report-editor]' ? [root, badRoot] : [];
    },
};

let rejectClipboard = false;
const writes = [];
const context = {
    Blob: class Blob {
        constructor(parts, options) {
            this.parts = parts;
            this.type = options.type;
        }
    },
    ClipboardItem: class ClipboardItem {
        constructor(items) {
            this.items = items;
        }
    },
    document,
    TextEncoder,
    navigator: {
        clipboard: {
            async write(items) {
                if (rejectClipboard) {
                    throw new Error('denied');
                }
                writes.push(items);
            },
        },
    },
    window: {
        crypto: webcrypto,
        async fetch(url) {
            if (url === '/clipboard') {
                return { ok: true, async json() { return payload; } };
            }
            if (url === '/bad-clipboard') {
                return { ok: true, async json() { return badPayload; } };
            }
            throw new Error(`unexpected ${url}`);
        },
    },
};
context.window.navigator = context.navigator;
context.window.ClipboardItem = context.ClipboardItem;
context.window.Blob = context.Blob;
context.window.TextEncoder = TextEncoder;

vm.createContext(context);
vm.runInContext(fs.readFileSync('ui_web/static/js/project_reports.js', 'utf-8'), context);
for (const callback of documentListeners.DOMContentLoaded) {
    callback();
}

async function waitFor(condition) {
    for (let index = 0; index < 20; index++) {
        if (condition()) {
            return;
        }
        await new Promise(resolve => setTimeout(resolve, 10));
    }
    assert.equal(condition(), true);
}

await waitFor(() => status.textContent === 'ready' && badStatus.textContent === 'payload failed');

assert.equal(copyButton.disabled, false);
assert.equal(copyButton.attributes.get('aria-disabled'), 'false');
assert.equal(status.textContent, 'ready');
assert.equal(badCopyButton.disabled, true);
assert.equal(badStatus.textContent, 'payload failed');

await copyButton.dispatch('click');
assert.equal(writes.length, 1);
assert.equal(writes[0][0].items['text/html'].type, 'text/html');
assert.equal(writes[0][0].items['text/plain'].type, 'text/plain');
assert.equal(status.textContent, 'copied');

rejectClipboard = true;
await copyButton.dispatch('click');
assert.equal(status.textContent, 'copy failed');

field.value = 'changed';
await field.dispatch('input');
assert.equal(copyButton.disabled, true);
assert.equal(finalizeButton.disabled, true);
assert.equal(dirtyBanner.classList.contains('is-hidden'), false);
const languageSubmit = await languageForm.dispatch('submit');
assert.equal(languageSubmit.defaultPrevented, true);
assert.equal(status.textContent, 'save first');
