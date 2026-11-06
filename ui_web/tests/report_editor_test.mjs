import assert from 'node:assert/strict';
import test from 'node:test';

import {
    FragmentValidationError,
    docToFragment,
    fragmentToDoc,
    fragmentText,
    normalizeFragment,
} from '../static/js/report_editor/fragment_codec.js';
import { createEditorHandle } from '../static/js/report_editor/adapter.js';
import { createContinuityController } from '../static/js/report_editor/report_continuity.js';

test('fragment codec preserves supported v1 and v2 nodes without dropping paint', () => {
    const rich = {
        schema_version: 2,
        blocks: [
            { type: 'heading', level: 3, content: [text('Status', ['strong'], '#0055aa', '#fff4cc')] },
            {
                type: 'paragraph',
                content: [
                    text('Painted ', [], '#aa0000', null),
                    {
                        type: 'link',
                        href: 'https://tracker.example.test/browse/DEMO-101?focused=true#activity',
                        reference_id: '11111111-1111-4111-8111-111111111111',
                        content: [text('ticket', ['em'], '#008000', '#ffff00')],
                    },
                    { type: 'break' },
                    text('after break', ['code'], null, null),
                ],
            },
            { type: 'quote', blocks: [{ type: 'paragraph', content: [text('Quoted', ['strike'], null, null)] }] },
            {
                type: 'list',
                ordered: false,
                items: [
                    { checked: true, blocks: [{ type: 'paragraph', content: [text('done', [], null, null)] }] },
                    { checked: false, blocks: [{ type: 'paragraph', content: [text('todo', [], null, null)] }] },
                ],
            },
            {
                type: 'table',
                headers: [[text('Key', [], null, null)], [text('Owner', [], null, null)]],
                rows: [[[text('DEMO-101', [], null, null)], [text('Alice', [], null, null)]]],
            },
            { type: 'code', language: 'json', text: '{"ok": true}' },
        ],
    };
    const old = {
        schema_version: 1,
        blocks: [
            { type: 'paragraph', content: [{ type: 'text', text: 'legacy', marks: ['em', 'strong'] }] },
            { type: 'paragraph', content: [{ type: 'link', href: 'https://example.test/item', text: 'old link' }] },
        ],
    };

    assert.deepEqual(docToFragment(fragmentToDoc(rich)), rich);
    assert.deepEqual(normalizeFragment(old), {
        schema_version: 2,
        blocks: [
            { type: 'paragraph', content: [text('legacy', ['strong', 'em'], null, null)] },
            {
                type: 'paragraph',
                content: [{
                    type: 'link',
                    href: 'https://example.test/item',
                    content: [text('old link', [], null, null)],
                }],
            },
        ],
    });
});

test('codec treats paint-only changes and empty fragments as real edits', () => {
    const plain = { schema_version: 2, blocks: [{ type: 'paragraph', content: [text('same', [], null, null)] }] };
    const painted = { schema_version: 2, blocks: [{ type: 'paragraph', content: [text('same', [], '#0055aa', null)] }] };
    const empty = { schema_version: 2, blocks: [] };

    assert.notDeepEqual(normalizeFragment(plain), normalizeFragment(painted));
    assert.deepEqual(docToFragment(fragmentToDoc(empty)), empty);
    assert.equal(fragmentText(empty), '');
});

test('codec refuses unknown nodes and unsafe links', () => {
    assert.throws(
        () => fragmentToDoc({ schema_version: 2, blocks: [{ type: 'image', src: 'x' }] }),
        FragmentValidationError,
    );
    assert.throws(
        () => normalizeFragment({
            schema_version: 2,
            blocks: [{ type: 'paragraph', content: [{ type: 'link', href: 'javascript:alert(1)', content: [text('x')] }] }],
        }),
        FragmentValidationError,
    );
});

test('editor handle rejects stale captures duplicate application and destroyed targets', () => {
    const runtime = new MemoryRuntime({ schema_version: 2, blocks: [{ type: 'paragraph', content: [text('Fix #DEMO-101 today')] }] });
    const dirtyVersions = [];
    const handle = createEditorHandle(runtime, 'issue-note', {
        onDirty: (dirty, fragment) => dirtyVersions.push([dirty, fragmentText(fragment)]),
    });

    const capture = handle.captureToken();
    assert.equal(capture.expected_text, '#DEMO-101');
    assert.equal(handle.applyCandidate(capture, { text: 'DEMO-101 resolved' }), 'applied');
    assert.equal(fragmentText(handle.getFragment()), 'Fix DEMO-101 resolved today');
    assert.equal(handle.applyCandidate(capture, { text: 'duplicate' }), 'stale');

    const stale = handle.captureToken();
    handle.replaceFragment(1, { schema_version: 2, blocks: [{ type: 'paragraph', content: [text('local edit')] }] });
    assert.equal(handle.applyCandidate(stale, { text: 'late candidate' }), 'stale');
    handle.destroy();
    assert.equal(handle.captureToken(), null);
    assert.equal(handle.replaceFragment(2, { schema_version: 2, blocks: [] }), 'stale');
    assert.deepEqual(dirtyVersions.map(item => item[0]), [true, true]);
});

test('selection-only change rejects old capture', () => {
    const runtime = new MemoryRuntime({ schema_version: 2, blocks: [{ type: 'paragraph', content: [text('Resolve #ALPHA-2 now')] }] });
    const handle = createEditorHandle(runtime, 'issue-note');
    const selectionOnly = handle.captureToken();

    runtime.moveSelectionToEnd();
    handle._selectionChanged();
    assert.equal(handle.applyCandidate(selectionOnly, { text: 'ALPHA-2 selected' }), 'stale');
    assert.equal(fragmentText(handle.getFragment()), 'Resolve #ALPHA-2 now');

    const stale = handle.captureToken();
    handle.replaceFragment(handle.local_version, { schema_version: 2, blocks: [{ type: 'paragraph', content: [text('Resolve #ALPHA-2 after edit')] }] });
    assert.equal(handle.applyCandidate(stale, { text: 'late' }), 'stale');

    const fresh = handle.captureToken();
    const rich = {
        schema_version: 2,
        blocks: [{ type: 'paragraph', content: [{
            type: 'link',
            href: 'https://tracker.example.test/browse/ALPHA-2',
            content: [text('ALPHA-2 linked', ['strong'], '#0055aa', '#fff4cc')],
        }] }],
    };
    assert.equal(handle.applyCandidate(fresh, { fragment: rich }), 'applied');
    assert.deepEqual(handle.getFragment(), {
        schema_version: 2,
        blocks: [{ type: 'paragraph', content: [text('Resolve ALPHA-2 linked after edit')] }],
    });
});

test('same-token text at moved caret does not qualify old capture', () => {
    const runtime = new MemoryRuntime({
        schema_version: 2,
        blocks: [{ type: 'paragraph', content: [text('#ALPHA-1 first #ALPHA-1 second')] }],
    });
    runtime.moveSelectionToToken(0);
    const handle = createEditorHandle(runtime, 'issue-note');
    const oldCapture = handle.captureToken();

    runtime.moveSelectionToToken(1);
    handle._selectionChanged();

    assert.equal(handle.applyCandidate(oldCapture, { text: 'ALPHA-1 linked' }), 'stale');
    assert.equal(handle.getTokenRect(oldCapture), null);
    assert.equal(fragmentText(handle.getFragment()), '#ALPHA-1 first #ALPHA-1 second');
});

test('capture observation is stable until content or selection changes', () => {
    const runtime = new MemoryRuntime({ schema_version: 2, blocks: [{ type: 'paragraph', content: [text('Resolve #ALPHA-2 now')] }] });
    const handle = createEditorHandle(runtime, 'issue-note');

    const first = handle.captureToken();
    const second = handle.captureToken();

    assert.equal(Object.hasOwn(first, 'capture_sequence'), false);
    assert.deepEqual(second, first);
});

test('editor handle delegates undo to the runtime history authority', () => {
    const runtime = new MemoryRuntime({ schema_version: 2, blocks: [] });
    const dirtyVersions = [];
    const handle = createEditorHandle(runtime, 'issue-note', {
        initialFragment: { schema_version: 2, blocks: [] },
        onDirty: (dirty, fragment) => dirtyVersions.push([dirty, fragmentText(fragment)]),
    });

    runtime.replaceFragment({ schema_version: 2, blocks: [{ type: 'paragraph', content: [text('x')] }] });
    handle._changedFromRuntime();

    assert.equal(fragmentText(handle.getFragment()), 'x');
    assert.equal(handle.command('undo'), true);
    assert.equal(fragmentText(handle.getFragment()), 'x');
    assert.deepEqual(runtime.commands, ['undo']);
    assert.deepEqual(dirtyVersions, [[true, 'x']]);
});

test('continuity controller serializes changes into save signature and hidden field', () => {
    const hidden = { value: '', name: 'continuity_changes' };
    const checkbox = new FakeControl({
        continuityChange: JSON.stringify({
            kind: 'set_persistent_carry',
            note_id: '76000000-0000-4000-8000-000000000011',
            carry_forward: false,
        }),
        continuityValueField: 'carry_forward',
    }, true);
    const root = new FakeRoot([checkbox]);
    const form = { querySelector: selector => selector === '[name="continuity_changes"]' ? hidden : null };

    const controller = createContinuityController(root, form);
    const clean = controller.signature();
    checkbox.checked = false;
    checkbox.emit('change');
    const dirty = controller.write();
    controller.destroy();

    assert.notEqual(clean, dirty);
    assert.equal(hidden.value, dirty);
    assert.deepEqual(JSON.parse(dirty), [{
        kind: 'set_persistent_carry',
        note_id: '76000000-0000-4000-8000-000000000011',
        carry_forward: false,
    }]);
    assert.equal(root.events.at(-1), 'report-continuity-change');
    assert.equal(checkbox.aborted, true);
});

test('codec enforces fragment size using utf8 bytes', () => {
    assert.throws(
        () => normalizeFragment({
            schema_version: 2,
            blocks: [{ type: 'paragraph', content: [text('汉'.repeat(6000))] }],
        }),
        FragmentValidationError,
    );
});

class MemoryRuntime {
    constructor(fragment) {
        this.fragment = normalizeFragment(fragment);
        this.destroyed = false;
        this.commands = [];
        this.selection = { from: 0, to: 0 };
    }

    getFragment() {
        return this.fragment;
    }

    replaceFragment(fragment) {
        this.fragment = normalizeFragment(fragment);
    }

    findToken() {
        const textValue = fragmentText(this.fragment);
        for (const match of textValue.matchAll(/#[A-Za-z0-9._:-]+/g)) {
            const from = match.index;
            const to = from + match[0].length;
            if (this.selection.from >= from && this.selection.from <= to) {
                return { text: match[0], bookmark: { kind: 'memory-token', from, to } };
            }
        }
        const match = /#[A-Za-z0-9._:-]+/.exec(textValue);
        return match ? { text: match[0], bookmark: { kind: 'memory-token', from: match.index, to: match.index + match[0].length } } : null;
    }

    replaceText(from, to, textValue) {
        const original = fragmentText(this.fragment);
        this.fragment = {
            schema_version: 2,
            blocks: [{ type: 'paragraph', content: [text(original.slice(0, from) + textValue + original.slice(to))] }],
        };
    }

    replaceBookmark(bookmark, replacement) {
        this.replaceText(bookmark.from, bookmark.to, typeof replacement === 'string' ? replacement : fragmentText(replacement));
        this.selection = { from: bookmark.from + fragmentText(this.fragment).length, to: bookmark.from + fragmentText(this.fragment).length };
        return true;
    }

    textForBookmark(bookmark) {
        return fragmentText(this.fragment).slice(bookmark.from, bookmark.to);
    }

    rectForBookmark(bookmark) {
        return { left: bookmark.from, right: bookmark.to, top: 0, bottom: 10, width: bookmark.to - bookmark.from, height: 10 };
    }

    selectionLocation() {
        return { ...this.selection };
    }

    moveSelectionToEnd() {
        const end = fragmentText(this.fragment).length;
        this.selection = { from: end, to: end };
    }

    moveSelectionToToken(index) {
        const matches = Array.from(fragmentText(this.fragment).matchAll(/#[A-Za-z0-9._:-]+/g));
        const match = matches[index];
        this.selection = { from: match.index + match[0].length, to: match.index + match[0].length };
    }

    destroy() {
        this.destroyed = true;
    }

    command(command) {
        this.commands.push(command);
        return true;
    }
}

class FakeRoot {
    constructor(controls) {
        this.controls = controls;
        this.events = [];
    }

    querySelectorAll(selector) {
        return selector === '[data-continuity-change]' ? this.controls : [];
    }

    dispatchEvent(event) {
        this.events.push(event.type);
    }
}

class FakeControl {
    constructor(dataset, checked) {
        this.dataset = dataset;
        this.checked = checked;
        this.type = 'checkbox';
        this.listeners = {};
        this.aborted = false;
    }

    addEventListener(type, callback, options = {}) {
        this.listeners[type] = callback;
        options.signal?.addEventListener('abort', () => {
            this.aborted = true;
        });
    }

    emit(type) {
        this.listeners[type]?.();
    }
}

function text(value, marks = [], foreground = null, background = null) {
    return { type: 'text', text: value, marks, foreground, background };
}
