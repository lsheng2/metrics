import assert from 'node:assert/strict';
import test from 'node:test';

import { Schema } from '../editor_build/node_modules/prosemirror-model/dist/index.js';
import {
    AllSelection, EditorState, NodeSelection, TextSelection,
} from '../editor_build/node_modules/prosemirror-state/dist/index.js';
import { runCommand } from '../editor_build/editor_commands.js';
import { synchronizeCommandSelection } from '../editor_build/editor_selection.js';

const schema = new Schema({
    nodes: {
        doc: { content: 'block+' },
        paragraph: { group: 'block', content: 'text*' },
        atom: { group: 'block', atom: true },
        text: { group: 'inline' },
    },
    marks: { strong: {} },
});

function fixture({ anchor = 6, head = 2, outsideAnchor = false, outsideHead = false } = {}) {
    const doc = schema.node('doc', null, [schema.node('paragraph', null, schema.text('abcdef'))]);
    const anchorNode = { owned: !outsideAnchor };
    const focusNode = { owned: !outsideHead };
    const native = { anchorNode, anchorOffset: anchor, focusNode, focusOffset: head };
    const view = {
        state: EditorState.create({ doc, selection: new AllSelection(doc) }),
        composing: false,
        dom: {
            contains: node => node.owned,
            ownerDocument: { getSelection: () => native },
        },
        posAtDOM: (_node, offset) => offset,
        focus() {},
    };
    view.dispatch = transaction => { view.state = view.state.apply(transaction); };
    return { view, native };
}

test('backward native range changes only its selected text and keeps direction', () => {
    const { view } = fixture();
    assert.equal(runCommand(view, 'bold'), true);
    assert.deepEqual(view.state.doc.toJSON(), {
        type: 'doc', content: [{ type: 'paragraph', content: [
            { type: 'text', text: 'a' },
            { type: 'text', text: 'bcde', marks: [{ type: 'strong' }] },
            { type: 'text', text: 'f' },
        ] }],
    });
    assert.equal(view.state.selection.anchor, 6);
    assert.equal(view.state.selection.head, 2);
});

test('collapsed native caret replaces stale text and whole-document selections', () => {
    for (const kind of ['text', 'all']) {
        const { view } = fixture({ anchor: 4, head: 4 });
        if (kind === 'text') {
            view.state = view.state.apply(view.state.tr.setSelection(TextSelection.create(view.state.doc, 1, 7)));
        }
        assert.equal(synchronizeCommandSelection(view), true);
        assert.equal(view.state.selection.anchor, 4);
        assert.equal(view.state.selection.head, 4);
        assert.equal(view.state.doc.textContent, 'abcdef');
    }
});

test('genuine whole-document selection remains AllSelection', () => {
    const { view } = fixture({ anchor: 0, head: 8 });
    const before = view.state;
    assert.equal(synchronizeCommandSelection(view), true);
    assert.equal(view.state, before);
    assert.ok(view.state.selection instanceof AllSelection);
    assert.equal(runCommand(view, 'bold'), true);
    assert.deepEqual(view.state.doc.firstChild.firstChild.marks.map(mark => mark.type.name), ['strong']);
    assert.equal(view.state.doc.textContent, 'abcdef');
});

test('NodeSelection remains a node selection despite its browser representation', () => {
    const { view } = fixture({ anchor: 1, head: 1 });
    const doc = schema.node('doc', null, [schema.node('atom'), schema.node('paragraph')]);
    view.state = EditorState.create({ doc, selection: NodeSelection.create(doc, 0) });
    const before = view.state;
    assert.equal(synchronizeCommandSelection(view), true);
    assert.equal(view.state, before);
    assert.ok(view.state.selection instanceof NodeSelection);
});

test('selection wholly outside the owner leaves the canonical target intact', () => {
    const { view } = fixture({ outsideAnchor: true, outsideHead: true });
    const before = view.state;
    assert.equal(synchronizeCommandSelection(view), true);
    assert.equal(view.state, before);
    assert.equal(runCommand(view, 'bold'), true);
    assert.equal(view.state.doc.firstChild.firstChild.text, 'abcdef');
    assert.equal(view.state.doc.firstChild.firstChild.marks[0].type.name, 'strong');
});

test('cross-editor selection is refused in either direction before mutation', () => {
    for (const direction of ['anchor', 'head']) {
        const { view } = fixture({
            outsideAnchor: direction === 'anchor',
            outsideHead: direction === 'head',
        });
        const before = view.state;
        assert.equal(runCommand(view, 'bold'), false);
        assert.equal(view.state, before);
    }
});

test('composition refuses toolbar mutation without replacing its selection', () => {
    const { view } = fixture();
    view.composing = true;
    const before = view.state;
    assert.equal(runCommand(view, 'bold'), false);
    assert.equal(view.state, before);
});

test('unmappable in-editor DOM selection refuses mutation', () => {
    const { view } = fixture();
    view.posAtDOM = () => { throw new RangeError('Detached DOM position'); };
    const before = view.state;
    assert.equal(runCommand(view, 'bold'), false);
    assert.equal(view.state, before);
});

test('out-of-document mapped position refuses mutation', () => {
    const { view } = fixture({ anchor: 999, head: 999 });
    const before = view.state;
    assert.equal(runCommand(view, 'bold'), false);
    assert.equal(view.state, before);
});

test('unexpected mapper errors are not converted to a silent fallback', () => {
    const { view } = fixture();
    view.posAtDOM = () => { throw new TypeError('Unexpected mapper error'); };
    assert.throws(() => runCommand(view, 'bold'), TypeError);
});

test('selection dispatch errors are not mistaken for unmappable DOM positions', () => {
    const { view } = fixture();
    view.dispatch = transaction => {
        view.state = view.state.apply(transaction);
        throw new RangeError('Selection listener failed');
    };
    assert.throws(() => runCommand(view, 'bold'), /Selection listener failed/u);
    assert.equal(view.state.doc.firstChild.firstChild.marks.length, 0);
});
