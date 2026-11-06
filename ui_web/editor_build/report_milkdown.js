import { Editor, defaultValueCtx, editorViewCtx, prosePluginsCtx, rootCtx } from '@milkdown/kit/core';
import { commonmark, linkSchema } from '@milkdown/kit/preset/commonmark';
import { gfm, tableSchema } from '@milkdown/kit/preset/gfm';
import { history as proseHistory, redo, undo } from '@milkdown/kit/prose/history';
import { keymap } from '@milkdown/kit/prose/keymap';
import { Fragment as ProseFragment, Node as ProseNode, Slice } from '@milkdown/kit/prose/model';
import { TextSelection } from '@milkdown/kit/prose/state';
import { setBlockType, toggleMark, wrapIn } from '@milkdown/kit/prose/commands';
import { wrapInList } from '@milkdown/kit/prose/schema-list';
import { addColumnAfter, addRowAfter, deleteColumn, deleteRow } from '@milkdown/kit/prose/tables';
import { $markSchema } from '@milkdown/kit/utils';

import { docToFragment, fragmentToDoc, normalizeFragment, sanitizePastedHtml } from '../static/js/report_editor/fragment_codec.js';

const paint = $markSchema('reportPaint', () => ({
    attrs: { foreground: { default: null }, background: { default: null } },
    toDOM(mark) {
        const style = [];
        if (mark.attrs.foreground) style.push(`color:${mark.attrs.foreground}`);
        if (mark.attrs.background) style.push(`background-color:${mark.attrs.background}`);
        return ['span', { style: style.join(';') }, 0];
    },
    parseDOM: [{
        tag: 'span[style]',
        getAttrs(node) {
            return {
                foreground: normalizeCssColor(node.style.color),
                background: normalizeCssColor(node.style.backgroundColor),
            };
        },
    }],
    parseMarkdown: { match: () => false, runner: () => undefined },
    toMarkdown: { match: () => false, runner: () => undefined },
}));

async function createRuntime(element, fragment, { readOnly = false, onChange, onSelectionChange } = {}) {
    element.replaceChildren();
    const editor = await Editor.make()
        .config(ctx => {
            ctx.set(rootCtx, element);
            ctx.set(defaultValueCtx, { type: 'json', value: fragmentToEditorDoc(fragment) });
            ctx.update(tableSchema.key, previous => inner => ({
                ...previous(inner),
                content: 'table_header_row table_row*',
            }));
            ctx.update(linkSchema.key, previous => inner => {
                const base = previous(inner);
                return { ...base, attrs: { ...base.attrs, reference_id: { default: null } } };
            });
            ctx.update(prosePluginsCtx, plugins => [
                proseHistory(),
                keymap({ 'Mod-z': undo, 'Mod-y': redo, 'Shift-Mod-z': redo }),
                ...plugins,
            ]);
        })
        .use(commonmark)
        .use(gfm)
        .use(paint)
        .create();
    const view = () => editor.action(ctx => ctx.get(editorViewCtx));
    const runtime = {
        getFragment() {
            return editor.action(ctx => docToFragment(ctx.get(editorViewCtx).state.doc.toJSON()));
        },
        replaceFragment(nextFragment) {
            const nextDoc = ProseNode.fromJSON(view().state.schema, fragmentToEditorDoc(nextFragment));
            dispatchTransaction(view(), view().state.tr.replaceWith(0, view().state.doc.content.size, nextDoc.content));
        },
        findToken() {
            return findTokenAtSelection(view().state);
        },
        textForBookmark(bookmark) {
            if (bookmark?.kind !== 'pm-token') return '';
            return view().state.doc.textBetween(bookmark.from, bookmark.to, '');
        },
        rectForBookmark(bookmark) {
            if (bookmark?.kind !== 'pm-token') return null;
            const start = view().coordsAtPos(bookmark.from);
            const end = view().coordsAtPos(bookmark.to);
            const left = Math.min(start.left, end.left);
            const right = Math.max(start.right, end.right);
            const top = Math.min(start.top, end.top);
            const bottom = Math.max(start.bottom, end.bottom);
            return { left, right, top, bottom, width: right - left, height: bottom - top };
        },
        selectionLocation() {
            const { from, to } = view().state.selection;
            return { from, to };
        },
        replaceBookmark(bookmark, replacement) {
            if (bookmark?.kind !== 'pm-token') return false;
            if (typeof replacement === 'string') {
                dispatchTransaction(view(), view().state.tr.insertText(replacement, bookmark.from, bookmark.to));
                return true;
            } else {
                const inlineContent = inlineReplacementContent(view().state, bookmark, replacement);
                if (!inlineContent) return false;
                let tr = view().state.tr.replace(bookmark.from, bookmark.to, new Slice(inlineContent, 0, 0));
                tr = tr.setSelection(TextSelection.create(tr.doc, bookmark.from + inlineContent.size));
                dispatchTransaction(view(), tr);
                return true;
            }
        },
        command(command, value) {
            return runCommand(view(), command, value);
        },
        pasteHtml(html) {
            const sanitized = sanitizePastedHtml(html);
            const nodes = fragmentToDoc(sanitized.fragment).content.map(item => ProseNode.fromJSON(view().state.schema, item));
            const slice = new Slice(ProseFragment.fromArray(nodes), 0, 0);
            dispatchTransaction(view(), view().state.tr.replaceSelection(slice));
            return sanitized.notices?.join(',') || 'kept';
        },
        clearReferenceIds() {
            return clearReferenceIds(view());
        },
        destroy() {
            editor.destroy();
        },
    };
    if (readOnly) {
        view().setProps({ editable: () => false });
    }
    const originalDispatch = view().dispatch.bind(view());
    view().dispatch = transaction => {
        originalDispatch(transaction);
        if (transaction.docChanged && typeof onChange === 'function') {
            onChange(runtime.getFragment());
            return;
        }
        if (transaction.selectionSet && typeof onSelectionChange === 'function') {
            onSelectionChange();
        }
    };
    return runtime;
}

function fragmentToEditorDoc(fragment) {
    const doc = fragmentToDoc(fragment);
    if (!doc.content.length) {
        return { type: 'doc', content: [{ type: 'paragraph' }] };
    }
    return doc;
}

function runCommand(view, command, value) {
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

function paintAttrsFromMarks(marks = []) {
    const mark = marks.find(item => item.type.name === 'reportPaint');
    return {
        foreground: mark?.attrs.foreground || null,
        background: mark?.attrs.background || null,
    };
}

function dispatchTransaction(view, transaction) {
    view.dispatch(transaction.scrollIntoView());
    view.focus();
}

function inlineReplacementContent(state, bookmark, replacement) {
    let normalized;
    try {
        normalized = normalizeFragment(replacement);
    } catch (error) {
        return null;
    }
    if (normalized.blocks.length !== 1 || normalized.blocks[0].type !== 'paragraph') {
        return null;
    }
    const inheritedPaint = paintAttrsForRange(state, bookmark.from, bookmark.to);
    const prepared = {
        schema_version: 2,
        blocks: [{
            type: 'paragraph',
            content: normalized.blocks[0].content.map(inline => inheritPaint(inline, inheritedPaint)),
        }],
    };
    try {
        const paragraph = fragmentToDoc(prepared).content[0];
        const nodes = (paragraph.content || []).map(item => ProseNode.fromJSON(state.schema, item));
        return ProseFragment.fromArray(nodes);
    } catch (error) {
        return null;
    }
}

function inheritPaint(inline, inheritedPaint) {
    if (inline.type === 'link') {
        return {
            ...inline,
            content: inline.content.map(item => inheritPaint(item, inheritedPaint)),
        };
    }
    if (inline.type !== 'text') {
        return inline;
    }
    return {
        ...inline,
        foreground: inline.foreground === null ? inheritedPaint.foreground : inline.foreground,
        background: inline.background === null ? inheritedPaint.background : inline.background,
    };
}

function paintAttrsForRange(state, from, to) {
    const result = { foreground: null, background: null };
    state.doc.nodesBetween(from, to, node => {
        if (!node.isText) {
            return true;
        }
        const paint = paintAttrsFromMarks(node.marks);
        result.foreground = result.foreground || paint.foreground;
        result.background = result.background || paint.background;
        return !result.foreground || !result.background;
    });
    return result;
}

function clearReferenceIds(view) {
    const link = view.state.schema.marks.link;
    let tr = view.state.tr;
    let changed = false;
    view.state.doc.descendants((node, pos) => {
        if (!node.isText) return true;
        const mark = node.marks.find(item => item.type === link && item.attrs.reference_id);
        if (!mark) return true;
        const from = pos;
        const to = pos + node.nodeSize;
        tr = tr.removeMark(from, to, link);
        tr = tr.addMark(from, to, link.create({ ...mark.attrs, reference_id: null }));
        changed = true;
        return true;
    });
    if (!changed) return false;
    dispatchTransaction(view, tr);
    return true;
}

function findTokenAtSelection(state) {
    if (!state.selection.empty) return null;
    const { $from } = state.selection;
    if (!$from.parent.isTextblock || $from.parent.type.name === 'heading' || $from.parent.type.name === 'code_block') return null;
    const projection = inlineProjection($from);
    const text = projection.map(item => item.text).join('');
    for (const match of text.matchAll(/#(?:[A-Z][A-Z0-9_]*-[1-9][0-9]*|[0-9]+)/g)) {
        const tokenStart = match.index;
        const tokenEnd = tokenStart + match[0].length;
        if (tokenStart > 0 && !/\s/u.test(text[tokenStart - 1])) continue;
        const chars = projection.slice(tokenStart, tokenEnd);
        if (!chars.length || chars.some(item => item.blocked)) continue;
        const first = chars[0];
        const last = chars[chars.length - 1];
        if ($from.parentOffset < first.parentOffset || $from.parentOffset > last.parentOffset + 1) continue;
        return { text: match[0], bookmark: { kind: 'pm-token', from: first.from, to: last.to } };
    }
    return null;
}

function inlineProjection($from) {
    const projection = [];
    $from.parent.forEach((node, nodeOffset) => {
        if (!node.isText) {
            projection.push({
                text: '\n',
                blocked: true,
                parentOffset: nodeOffset,
                from: $from.start() + nodeOffset,
                to: $from.start() + nodeOffset + node.nodeSize,
            });
            return;
        }
        const blocked = node.marks?.some(mark => mark.type.name === 'inlineCode' || mark.type.name === 'link');
        const textValue = node.text || '';
        for (let index = 0; index < textValue.length; index += 1) {
            projection.push({
                text: textValue[index],
                blocked,
                parentOffset: nodeOffset + index,
                from: $from.start() + nodeOffset + index,
                to: $from.start() + nodeOffset + index + 1,
            });
        }
    });
    return projection;
}

function normalizeCodeLanguage(value) {
    const allowed = new Set(['', 'text', 'plain', 'python', 'json', 'markdown', 'yaml', 'sql', 'bash', 'powershell']);
    return allowed.has(value) ? value : '';
}

function normalizeCssColor(value) {
    if (!value) return null;
    const lower = value.toLowerCase();
    if (/^#[0-9a-f]{6}$/.test(lower)) return lower;
    const match = /^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/.exec(lower);
    if (!match) return null;
    return `#${match.slice(1).map(item => Number(item).toString(16).padStart(2, '0')).join('')}`;
}

window.ReportMilkdownEditor = { createRuntime, normalizeFragment };
