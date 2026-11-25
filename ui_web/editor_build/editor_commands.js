import { redo, undo } from '@milkdown/kit/prose/history';
import { TextSelection } from '@milkdown/kit/prose/state';
import { setBlockType, toggleMark, wrapIn } from '@milkdown/kit/prose/commands';
import { wrapInList } from '@milkdown/kit/prose/schema-list';
import { addColumnAfter, addRowAfter, deleteColumn, deleteRow } from '@milkdown/kit/prose/tables';

import { synchronizeCommandSelection } from './editor_selection.js';

export function runCommand(view, command, value) {
    if (!synchronizeCommandSelection(view)) return false;
    const schema = view.state.schema;
    const commands = {
        bold: () => toggleMark(schema.marks.strong),
        italic: () => toggleMark(schema.marks.em),
        strike: () => toggleMark(schema.marks.strike_through),
        code: () => toggleMark(schema.marks.inlineCode),
        undo: () => undo,
        redo: () => redo,
        bullet: () => wrapInList(schema.nodes.bullet_list),
        ordered: () => wrapInList(schema.nodes.ordered_list),
        task: () => taskCommand(schema),
        table: () => insertTableCommand(schema),
        'table-row-add': () => addRowAfter,
        'table-row-delete': () => deleteRow,
        'table-column-add': () => addColumnAfter,
        'table-column-delete': () => deleteColumn,
        quote: () => wrapIn(schema.nodes.blockquote),
        'code-block': () => codeBlockCommand(schema, value),
        foreground: () => paintCommand(schema, { foreground: value }),
        background: () => paintCommand(schema, { background: value }),
        'clear-paint': () => clearPaintCommand(schema),
        link: () => toggleMark(schema.marks.link, { href: value, title: null, reference_id: null }),
    };
    if (command === 'block') {
        const applied = blockCommand(schema, value)(view.state, view.dispatch, view);
        view.focus();
        return applied;
    }
    const factory = commands[command];
    const applied = factory ? factory()(view.state, view.dispatch, view) : false;
    view.focus();
    return applied;
}

function blockCommand(schema, value) {
    if (value === 'h1') return setBlockType(schema.nodes.heading, { level: 1 });
    if (value === 'h2') return setBlockType(schema.nodes.heading, { level: 2 });
    if (value === 'h3') return setBlockType(schema.nodes.heading, { level: 3 });
    if (value === 'quote') return wrapIn(schema.nodes.blockquote);
    return setBlockType(schema.nodes.paragraph);
}

function codeBlockCommand(schema, value) {
    return (state, dispatch) => {
        const attrs = { language: normalizeCodeLanguage(value) };
        const { selection } = state;
        if (!selection.empty) {
            return setBlockType(schema.nodes.code_block, attrs)(state, dispatch);
        }
        const { $from } = selection;
        const parent = $from.parent;
        if (parent.type === schema.nodes.code_block) {
            dispatch?.(state.tr.setNodeMarkup($from.before($from.depth), undefined, attrs).scrollIntoView());
            return true;
        }
        if (parent.isTextblock && parent.content.size > 0) {
            const position = $from.after($from.depth);
            const node = schema.nodes.code_block.create(attrs);
            if (!$from.parent.type.validContent($from.parent.content)) {
                return false;
            }
            let tr = state.tr.insert(position, node);
            tr = tr.setSelection(TextSelection.create(tr.doc, position + 1));
            dispatch?.(tr.scrollIntoView());
            return true;
        }
        return setBlockType(schema.nodes.code_block, attrs)(state, dispatch);
    };
}

function clearPaintCommand(schema) {
    return (state, dispatch) => {
        if (state.selection.empty) {
            dispatch(state.tr.removeStoredMark(schema.marks.reportPaint).scrollIntoView());
            return true;
        }
        dispatch(state.tr.removeMark(state.selection.from, state.selection.to, schema.marks.reportPaint).scrollIntoView());
        return true;
    };
}

function taskCommand(schema) {
    return (state, dispatch, view) => {
        const task = taskItemAtSelection(state) || taskItemInSelection(state);
        if (task) {
            dispatch?.(state.tr.setNodeMarkup(task.pos, undefined, {
                ...task.node.attrs,
                checked: !task.node.attrs.checked,
            }).scrollIntoView());
            return true;
        }
        const wrapped = wrapInList(schema.nodes.bullet_list)(state, transaction => {
            transaction.doc.nodesBetween(transaction.selection.from, transaction.selection.to, (node, position) => {
                if (node.type.name === 'list_item') {
                    transaction.setNodeMarkup(position, undefined, { ...node.attrs, checked: false });
                }
            });
            dispatch(transaction);
        }, view);
        return wrapped;
    };
}

function taskItemInSelection(state) {
    let result = null;
    state.doc.nodesBetween(state.selection.from, state.selection.to, (node, pos) => {
        if (!result && node.type.name === 'list_item' && node.attrs.checked !== null) {
            result = { node, pos };
            return false;
        }
        return !result;
    });
    return result;
}

function taskItemAtSelection(state) {
    const { $from } = state.selection;
    for (let depth = $from.depth; depth > 0; depth -= 1) {
        const node = $from.node(depth);
        if (node.type.name === 'list_item' && node.attrs.checked !== null) {
            return { node, pos: $from.before(depth) };
        }
    }
    return null;
}

function insertTableCommand(schema) {
    return (state, dispatch) => {
        const header = schema.nodes.table_header.create({ alignment: 'left' }, schema.nodes.paragraph.create(null, schema.text('Header')));
        const cell = schema.nodes.table_cell.create({ alignment: 'left' }, schema.nodes.paragraph.create(null, schema.text('Value')));
        const table = schema.nodes.table.create(null, [
            schema.nodes.table_header_row.create(null, [header]),
            schema.nodes.table_row.create(null, [cell]),
        ]);
        dispatch(state.tr.replaceSelectionWith(table).scrollIntoView());
        return true;
    };
}

function paintCommand(schema, attrs) {
    return (state, dispatch) => {
        const markType = schema.marks.reportPaint;
        if (state.selection.empty) {
            const current = storedPaintAttrs(state);
            const mark = markType.create(mergePaintAttrs(current, attrs));
            dispatch(state.tr.addStoredMark(mark).scrollIntoView());
            return true;
        }
        let tr = state.tr;
        let changed = false;
        state.doc.nodesBetween(state.selection.from, state.selection.to, (node, position) => {
            if (!node.isText) {
                return true;
            }
            const from = Math.max(state.selection.from, position);
            const to = Math.min(state.selection.to, position + node.nodeSize);
            if (from >= to) {
                return false;
            }
            const current = paintAttrsFromMarks(node.marks);
            const next = mergePaintAttrs(current, attrs);
            tr = tr.removeMark(from, to, markType);
            if (next.foreground || next.background) {
                tr = tr.addMark(from, to, markType.create(next));
            }
            changed = true;
            return false;
        });
        if (!changed) return false;
        dispatch(tr.scrollIntoView());
        return true;
    };
}

function mergePaintAttrs(current, changes) {
    return {
        foreground: Object.prototype.hasOwnProperty.call(changes, 'foreground') ? changes.foreground : current.foreground,
        background: Object.prototype.hasOwnProperty.call(changes, 'background') ? changes.background : current.background,
    };
}

function storedPaintAttrs(state) {
    return paintAttrsFromMarks(state.storedMarks || state.selection.$from.marks());
}

export function paintAttrsFromMarks(marks = []) {
    const mark = marks.find(item => item.type.name === 'reportPaint');
    return {
        foreground: mark?.attrs.foreground || null,
        background: mark?.attrs.background || null,
    };
}

function normalizeCodeLanguage(value) {
    const allowed = new Set(['', 'text', 'plain', 'python', 'json', 'markdown', 'yaml', 'sql', 'bash', 'powershell']);
    return allowed.has(value) ? value : '';
}
