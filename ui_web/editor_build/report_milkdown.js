import { Editor, defaultValueCtx, editorViewCtx, prosePluginsCtx, rootCtx } from '@milkdown/kit/core';
import { commonmark, linkSchema } from '@milkdown/kit/preset/commonmark';
import { gfm, tableSchema } from '@milkdown/kit/preset/gfm';
import { history as proseHistory, redo, undo } from '@milkdown/kit/prose/history';
import { keymap } from '@milkdown/kit/prose/keymap';
import { Fragment as ProseFragment, Node as ProseNode, Slice } from '@milkdown/kit/prose/model';
import { TextSelection } from '@milkdown/kit/prose/state';
import { $markSchema } from '@milkdown/kit/utils';

import { docToFragment, fragmentToDoc, normalizeFragment, sanitizePastedHtml } from '../static/js/report_editor/fragment_codec.js';
import { paintAttrsFromMarks, runCommand } from './editor_commands.js';

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
        view().setProps({
            attributes: editorViewAttributes(element, readOnly),
            editable: () => false,
        });
    } else {
        view().setProps({ attributes: editorViewAttributes(element, readOnly) });
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

function editorViewAttributes(element, readOnly) {
    const attributes = {
        role: 'textbox',
        'aria-multiline': 'true',
        'aria-readonly': String(Boolean(readOnly)),
    };
    const label = element.getAttribute('aria-label');
    const labelledBy = element.getAttribute('aria-labelledby');
    if (label) {
        attributes['aria-label'] = label;
    } else if (labelledBy) {
        attributes['aria-labelledby'] = labelledBy;
    }
    return attributes;
}

function fragmentToEditorDoc(fragment) {
    const doc = fragmentToDoc(fragment);
    if (!doc.content.length) {
        return { type: 'doc', content: [{ type: 'paragraph' }] };
    }
    return doc;
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

function normalizeCssColor(value) {
    if (!value) return null;
    const lower = value.toLowerCase();
    if (/^#[0-9a-f]{6}$/.test(lower)) return lower;
    const match = /^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/.exec(lower);
    if (!match) return null;
    return `#${match.slice(1).map(item => Number(item).toString(16).padStart(2, '0')).join('')}`;
}

window.ReportMilkdownEditor = { createRuntime, normalizeFragment };
