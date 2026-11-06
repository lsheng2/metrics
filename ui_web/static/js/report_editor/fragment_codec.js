const MARK_ORDER = ['strong', 'em', 'strike', 'code'];
const MARK_TO_PM = {
    strong: 'strong',
    em: 'em',
    strike: 'strike_through',
    code: 'inlineCode',
};
const PM_TO_MARK = {
    strong: 'strong',
    em: 'em',
    strike_through: 'strike',
    inlineCode: 'code',
};
const CODE_LANGUAGES = new Set(['', 'text', 'plain', 'python', 'json', 'markdown', 'yaml', 'sql', 'bash', 'powershell']);
const MAX_FRAGMENT_BYTES = 16384;
const MAX_NODES = 1000;
const MAX_DEPTH = 6;
const COLOR_RE = /^#[0-9a-f]{6}$/;

export class FragmentValidationError extends Error {
    constructor(message = 'invalid fragment') {
        super(message);
        this.name = 'FragmentValidationError';
    }
}

export function normalizeFragment(fragment) {
    const guard = { count: 0 };
    const input = requireObject(fragment);
    requireKeys(input, ['schema_version', 'blocks']);
    if (input.schema_version !== 1 && input.schema_version !== 2) {
        throw new FragmentValidationError('unsupported schema version');
    }
    const normalized = {
        schema_version: 2,
        blocks: requireArray(input.blocks).map(block => normalizeBlock(block, input.schema_version, guard, 1)),
    };
    if (utf8ByteLength(JSON.stringify(normalized)) > MAX_FRAGMENT_BYTES) {
        throw new FragmentValidationError('fragment too large');
    }
    return normalized;
}

export function fragmentToDoc(fragment) {
    const normalized = normalizeFragment(fragment);
    return { type: 'doc', content: normalized.blocks.map(blockToPm) };
}

export function docToFragment(doc) {
    const value = requireObject(doc);
    requireKeys(value, ['type', 'content']);
    if (value.type !== 'doc') {
        throw new FragmentValidationError('not a document');
    }
    return normalizeFragment({
        schema_version: 2,
        blocks: requireArray(value.content).map(pmBlockToFragment),
    });
}

export function fragmentText(fragment) {
    return normalizeFragment(fragment).blocks.map(blockText).join('\n');
}

export function emptyFragment() {
    return { schema_version: 2, blocks: [] };
}

export function plainTextFragment(value) {
    if (typeof value !== 'string') {
        throw new FragmentValidationError('text must be a string');
    }
    if (value === '') {
        return emptyFragment();
    }
    return {
        schema_version: 2,
        blocks: [{ type: 'paragraph', content: [{ type: 'text', text: value, marks: [], foreground: null, background: null }] }],
    };
}

export function fragmentToPreview(fragment) {
    const container = document.createElement('div');
    container.className = 'report-fragment-preview';
    normalizeFragment(fragment).blocks.forEach(block => {
        container.appendChild(blockPreview(block));
    });
    return container;
}

export function sanitizePastedHtml(html) {
    if (typeof document === 'undefined' || typeof DOMParser === 'undefined') {
        throw new FragmentValidationError('DOM paste sanitizer unavailable');
    }
    const parser = new DOMParser();
    const parsed = parser.parseFromString(String(html || ''), 'text/html');
    const notices = new Set();
    const blocks = [];
    Array.from(parsed.body.childNodes).forEach(node => {
        blocks.push(...domNodeToBlocks(node, notices));
    });
    return {
        fragment: normalizeFragment({ schema_version: 2, blocks }),
        notices: Array.from(notices),
        message: Array.from(notices).join(' ') || 'kept',
    };
}

export function htmlToFragment(html) {
    return sanitizePastedHtml(html).fragment;
}

function normalizeBlock(block, version, guard, depth) {
    countNode(guard, depth);
    const value = requireObject(block);
    if (value.type === 'paragraph') {
        requireKeys(value, ['type', 'content']);
        return { type: 'paragraph', content: normalizeInlines(value.content, version, guard, depth + 1) };
    }
    if (value.type === 'heading') {
        requireKeys(value, ['type', 'level', 'content']);
        if (![1, 2, 3].includes(value.level)) {
            throw new FragmentValidationError('unsupported heading level');
        }
        return { type: 'heading', level: value.level, content: normalizeInlines(value.content, version, guard, depth + 1) };
    }
    if (value.type === 'quote') {
        requireKeys(value, ['type', 'blocks']);
        return { type: 'quote', blocks: requireArray(value.blocks).map(item => normalizeBlock(item, version, guard, depth + 1)) };
    }
    if (value.type === 'list') {
        requireKeys(value, ['type', 'ordered', 'items']);
        if (typeof value.ordered !== 'boolean') {
            throw new FragmentValidationError('list ordered must be boolean');
        }
        return {
            type: 'list',
            ordered: value.ordered,
            items: requireArray(value.items).map(item => normalizeListItem(item, value.ordered, version, guard, depth + 1)),
        };
    }
    if (value.type === 'table') {
        requireKeys(value, ['type', 'headers', 'rows']);
        const headers = requireArray(value.headers).map(cell => normalizeInlines(cell, version, guard, depth + 1));
        const rows = requireArray(value.rows).map(row => requireArray(row).map(cell => normalizeInlines(cell, version, guard, depth + 1)));
        if (!headers.length || rows.some(row => row.length !== headers.length)) {
            throw new FragmentValidationError('invalid table shape');
        }
        return { type: 'table', headers, rows };
    }
    if (value.type === 'code') {
        requireKeys(value, ['type', 'language', 'text']);
        if (typeof value.language !== 'string' || !CODE_LANGUAGES.has(value.language) || typeof value.text !== 'string') {
            throw new FragmentValidationError('invalid code block');
        }
        return { type: 'code', language: value.language, text: value.text };
    }
    throw new FragmentValidationError(`unsupported block ${value.type}`);
}

function normalizeListItem(item, ordered, version, guard, depth) {
    countNode(guard, depth);
    const value = requireObject(item);
    requireKeys(value, ['checked', 'blocks']);
    if (value.checked !== null && typeof value.checked !== 'boolean') {
        throw new FragmentValidationError('invalid task state');
    }
    if (ordered && value.checked !== null) {
        throw new FragmentValidationError('ordered tasks are unsupported');
    }
    return {
        checked: value.checked,
        blocks: requireArray(value.blocks).map(block => normalizeBlock(block, version, guard, depth + 1)),
    };
}

function normalizeInlines(inlines, version, guard, depth) {
    return requireArray(inlines).map(item => normalizeInline(item, version, guard, depth));
}

function normalizeInline(inline, version, guard, depth) {
    countNode(guard, depth);
    const value = requireObject(inline);
    if (value.type === 'text') {
        const keys = version === 1 ? ['type', 'text', 'marks'] : ['type', 'text', 'marks', 'foreground', 'background'];
        requireKeys(value, keys);
        return {
            type: 'text',
            text: requireText(value.text),
            marks: normalizeMarks(value.marks),
            foreground: version === 1 ? null : normalizeColor(value.foreground),
            background: version === 1 ? null : normalizeColor(value.background),
        };
    }
    if (value.type === 'link') {
        if (version === 1) {
            const keys = value.reference_id === undefined ? ['type', 'href', 'text'] : ['type', 'href', 'text', 'reference_id'];
            requireKeys(value, keys);
            return linkInline(value.href, [{ type: 'text', text: requireText(value.text), marks: [], foreground: null, background: null }], value.reference_id);
        }
        const keys = value.reference_id === undefined ? ['type', 'href', 'content'] : ['type', 'href', 'content', 'reference_id'];
        requireKeys(value, keys);
        const content = requireArray(value.content).map(item => {
            const text = normalizeInline(item, 2, guard, depth + 1);
            if (text.type !== 'text') {
                throw new FragmentValidationError('links may only contain text');
            }
            return text;
        });
        if (!content.length) {
            throw new FragmentValidationError('empty links are unsupported');
        }
        return linkInline(value.href, content, value.reference_id);
    }
    if (value.type === 'break') {
        requireKeys(value, ['type']);
        return { type: 'break' };
    }
    throw new FragmentValidationError(`unsupported inline ${value.type}`);
}

function linkInline(href, content, referenceId) {
    const result = { type: 'link', href: normalizeHttpsUrl(href), content };
    if (referenceId !== undefined) {
        result.reference_id = normalizeUuid(referenceId);
    }
    return result;
}

function blockToPm(block) {
    if (block.type === 'paragraph') {
        return { type: 'paragraph', content: inlinesToPm(block.content) };
    }
    if (block.type === 'heading') {
        return { type: 'heading', attrs: { level: block.level }, content: inlinesToPm(block.content) };
    }
    if (block.type === 'quote') {
        return { type: 'blockquote', content: block.blocks.map(blockToPm) };
    }
    if (block.type === 'list') {
        return {
            type: block.ordered ? 'ordered_list' : 'bullet_list',
            attrs: block.ordered ? { order: 1, spread: false } : { spread: false },
            content: block.items.map((item, index) => ({
                type: 'list_item',
                attrs: { label: block.ordered ? `${index + 1}.` : '•', listType: block.ordered ? 'ordered' : 'bullet', spread: false, checked: item.checked },
                content: item.blocks.map(blockToPm),
            })),
        };
    }
    if (block.type === 'table') {
        return {
            type: 'table',
            content: [
                {
                    type: 'table_header_row',
                    content: block.headers.map(cell => ({ type: 'table_header', attrs: { alignment: 'left' }, content: [cellParagraph(cell)] })),
                },
                ...block.rows.map(row => ({
                    type: 'table_row',
                    content: row.map(cell => ({ type: 'table_cell', attrs: { alignment: 'left' }, content: [cellParagraph(cell)] })),
                })),
            ],
        };
    }
    if (block.type === 'code') {
        return { type: 'code_block', attrs: { language: block.language }, content: block.text ? [{ type: 'text', text: block.text }] : [] };
    }
    throw new FragmentValidationError('unsupported block');
}

function blockPreview(block) {
    if (block.type === 'paragraph') {
        const node = document.createElement('p');
        appendInlines(node, block.content);
        return node;
    }
    if (block.type === 'heading') {
        const node = document.createElement(`h${block.level}`);
        appendInlines(node, block.content);
        return node;
    }
    if (block.type === 'quote') {
        const node = document.createElement('blockquote');
        block.blocks.forEach(child => node.appendChild(blockPreview(child)));
        return node;
    }
    if (block.type === 'list') {
        const node = document.createElement(block.ordered ? 'ol' : 'ul');
        block.items.forEach(item => {
            const li = document.createElement('li');
            if (item.checked !== null) {
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = item.checked;
                checkbox.disabled = true;
                li.appendChild(checkbox);
            }
            item.blocks.forEach(child => li.appendChild(blockPreview(child)));
            node.appendChild(li);
        });
        return node;
    }
    if (block.type === 'table') {
        const table = document.createElement('table');
        const thead = document.createElement('thead');
        const headRow = document.createElement('tr');
        block.headers.forEach(cell => {
            const th = document.createElement('th');
            appendInlines(th, cell);
            headRow.appendChild(th);
        });
        thead.appendChild(headRow);
        table.appendChild(thead);
        const tbody = document.createElement('tbody');
        block.rows.forEach(row => {
            const tr = document.createElement('tr');
            row.forEach(cell => {
                const td = document.createElement('td');
                appendInlines(td, cell);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        return table;
    }
    if (block.type === 'code') {
        const pre = document.createElement('pre');
        const code = document.createElement('code');
        code.textContent = block.text;
        pre.appendChild(code);
        return pre;
    }
    throw new FragmentValidationError('unsupported preview block');
}

function appendInlines(parent, inlines) {
    inlines.forEach(inline => {
        if (inline.type === 'break') {
            parent.appendChild(document.createElement('br'));
            return;
        }
        if (inline.type === 'link') {
            const link = document.createElement('a');
            link.href = inline.href;
            appendInlines(link, inline.content);
            parent.appendChild(link);
            return;
        }
        const node = document.createElement(inline.marks.includes('code') ? 'code' : 'span');
        node.textContent = inline.text;
        if (inline.marks.includes('strong')) node.style.fontWeight = '700';
        if (inline.marks.includes('em')) node.style.fontStyle = 'italic';
        if (inline.marks.includes('strike')) node.style.textDecoration = 'line-through';
        if (inline.foreground) node.style.color = inline.foreground;
        if (inline.background) node.style.backgroundColor = inline.background;
        parent.appendChild(node);
    });
}

function cellParagraph(cell) {
    return { type: 'paragraph', content: inlinesToPm(cell) };
}

function inlinesToPm(inlines) {
    const result = [];
    inlines.forEach(inline => {
        if (inline.type === 'break') {
            result.push({ type: 'hardbreak', attrs: { isInline: false } });
            return;
        }
        if (inline.type === 'link') {
            inline.content.forEach(textRun => {
                result.push(textRunToPm(textRun, { href: inline.href, reference_id: inline.reference_id ?? null, title: null }));
            });
            return;
        }
        result.push(textRunToPm(inline));
    });
    return result;
}

function textRunToPm(textRun, link = null) {
    const marks = textRun.marks.map(mark => ({ type: MARK_TO_PM[mark] }));
    if (textRun.foreground || textRun.background) {
        marks.push({ type: 'reportPaint', attrs: { foreground: textRun.foreground, background: textRun.background } });
    }
    if (link) {
        marks.push({ type: 'link', attrs: link });
    }
    return { type: 'text', text: textRun.text, marks };
}

function pmBlockToFragment(block) {
    const value = requireObject(block);
    if (value.type === 'paragraph') {
        return { type: 'paragraph', content: pmInlinesToFragment(value.content || []) };
    }
    if (value.type === 'heading') {
        const level = value.attrs?.level;
        if (![1, 2, 3].includes(level)) {
            throw new FragmentValidationError('unsupported heading level');
        }
        return { type: 'heading', level, content: pmInlinesToFragment(value.content || []) };
    }
    if (value.type === 'blockquote') {
        return { type: 'quote', blocks: requireArray(value.content || []).map(pmBlockToFragment) };
    }
    if (value.type === 'bullet_list' || value.type === 'ordered_list') {
        const ordered = value.type === 'ordered_list';
        return {
            type: 'list',
            ordered,
            items: requireArray(value.content || []).map(item => ({
                checked: item.attrs?.checked ?? null,
                blocks: requireArray(item.content || []).map(pmBlockToFragment),
            })),
        };
    }
    if (value.type === 'table') {
        const rows = requireArray(value.content || []);
        if (!rows.length || rows[0].type !== 'table_header_row') {
            throw new FragmentValidationError('table requires header row');
        }
        const headers = requireArray(rows[0].content || []).map(pmCellInlines);
        return {
            type: 'table',
            headers,
            rows: rows.slice(1).map(row => requireArray(row.content || []).map(pmCellInlines)),
        };
    }
    if (value.type === 'code_block') {
        return { type: 'code', language: value.attrs?.language || '', text: pmTextContent(value.content || []) };
    }
    throw new FragmentValidationError(`unsupported ProseMirror block ${value.type}`);
}

function pmCellInlines(cell) {
    const content = requireArray(cell.content || []);
    if (content.length !== 1 || content[0].type !== 'paragraph') {
        throw new FragmentValidationError('table cell must contain one paragraph');
    }
    return pmInlinesToFragment(content[0].content || []);
}

function pmInlinesToFragment(content) {
    const result = [];
    let link = null;
    requireArray(content).forEach(node => {
        if (node.type === 'hardbreak') {
            flushLink(result, link);
            link = null;
            result.push({ type: 'break' });
            return;
        }
        if (node.type !== 'text') {
            throw new FragmentValidationError(`unsupported inline node ${node.type}`);
        }
        const textRun = pmTextToFragment(node);
        const linkMark = (node.marks || []).find(mark => mark.type === 'link');
        if (!linkMark) {
            flushLink(result, link);
            link = null;
            result.push(textRun);
            return;
        }
        const signature = JSON.stringify({ href: linkMark.attrs.href, reference_id: linkMark.attrs.reference_id ?? null });
        if (!link || link.signature !== signature) {
            flushLink(result, link);
            link = {
                signature,
                value: {
                    type: 'link',
                    href: normalizeHttpsUrl(linkMark.attrs.href),
                    content: [],
                },
            };
            if (linkMark.attrs.reference_id) {
                link.value.reference_id = normalizeUuid(linkMark.attrs.reference_id);
            }
        }
        link.value.content.push(textRun);
    });
    flushLink(result, link);
    return result;
}

function pmTextToFragment(node) {
    const marks = [];
    let foreground = null;
    let background = null;
    (node.marks || []).forEach(mark => {
        if (PM_TO_MARK[mark.type]) {
            marks.push(PM_TO_MARK[mark.type]);
        }
        if (mark.type === 'reportPaint') {
            foreground = normalizeColor(mark.attrs?.foreground ?? null);
            background = normalizeColor(mark.attrs?.background ?? null);
        }
    });
    return { type: 'text', text: requireText(node.text || ''), marks: normalizeMarks(marks), foreground, background };
}

function flushLink(result, link) {
    if (link) {
        result.push(link.value);
    }
}

function pmTextContent(content) {
    return requireArray(content).map(node => node.text || '').join('');
}

function domNodeToBlocks(node, notices) {
    if (node.nodeType === Node.TEXT_NODE) {
        const textValue = node.textContent || '';
        return textValue ? [{ type: 'paragraph', content: [{ type: 'text', text: textValue, marks: [], foreground: null, background: null }] }] : [];
    }
    if (node.nodeType !== Node.ELEMENT_NODE) {
        return [];
    }
    const tag = node.tagName.toLowerCase();
    if (['script', 'style', 'iframe', 'object'].includes(tag)) {
        notices.add('script');
        return [];
    }
    if (['img', 'video', 'audio', 'canvas', 'svg'].includes(tag)) {
        notices.add('media');
        return [];
    }
    if (tag === 'p' || tag === 'div') {
        return [{ type: 'paragraph', content: domInlineChildren(node, notices) }];
    }
    if (/^h[1-6]$/.test(tag)) {
        const level = Number(tag.slice(1));
        if (level > 3) {
            notices.add('heading');
            return [{ type: 'paragraph', content: domInlineChildren(node, notices) }];
        }
        return [{ type: 'heading', level, content: domInlineChildren(node, notices) }];
    }
    if (tag === 'blockquote') {
        const blocks = Array.from(node.childNodes).flatMap(child => domNodeToBlocks(child, notices));
        return [{ type: 'quote', blocks: blocks.length ? blocks : [{ type: 'paragraph', content: [] }] }];
    }
    if (!['span', 'strong', 'b', 'em', 'i', 'del', 's', 'code', 'a', 'br'].includes(tag)) {
        notices.add('html');
    }
    return [{ type: 'paragraph', content: domInlineChildren(node, notices) }];
}

function domInlineChildren(element, notices, inheritedMarks = [], inheritedPaint = {}) {
    const result = [];
    Array.from(element.childNodes).forEach(child => {
        result.push(...domInlineNode(child, notices, inheritedMarks, inheritedPaint));
    });
    return result;
}

function domInlineNode(node, notices, inheritedMarks, inheritedPaint) {
    if (node.nodeType === Node.TEXT_NODE) {
        const textValue = node.textContent || '';
        return textValue ? [{ type: 'text', text: textValue, marks: normalizeMarks(inheritedMarks), foreground: inheritedPaint.foreground || null, background: inheritedPaint.background || null }] : [];
    }
    if (node.nodeType !== Node.ELEMENT_NODE) {
        return [];
    }
    const tag = node.tagName.toLowerCase();
    if (['script', 'style', 'iframe', 'object'].includes(tag)) {
        notices.add('script');
        return [];
    }
    if (['img', 'video', 'audio', 'canvas', 'svg'].includes(tag)) {
        notices.add('media');
        return [];
    }
    if (tag === 'br') {
        return [{ type: 'break' }];
    }
    const marks = [...inheritedMarks];
    if (tag === 'strong' || tag === 'b') marks.push('strong');
    if (tag === 'em' || tag === 'i') marks.push('em');
    if (tag === 'del' || tag === 's') marks.push('strike');
    if (tag === 'code') marks.push('code');
    const paint = { ...inheritedPaint, ...paintFromStyle(node.getAttribute('style') || '') };
    const content = domInlineChildren(node, notices, marks, paint);
    if (tag !== 'a') {
        return content;
    }
    const href = node.getAttribute('href') || '';
    try {
        return [{ type: 'link', href: normalizeHttpsUrl(href), content: content.filter(item => item.type === 'text') }];
    } catch (error) {
        notices.add('link');
        return content;
    }
}

function paintFromStyle(style) {
    const result = {};
    style.split(';').forEach(rule => {
        const [name, rawValue] = rule.split(':').map(part => (part || '').trim().toLowerCase());
        if (name === 'color') result.foreground = cssColor(rawValue);
        if (name === 'background-color') result.background = cssColor(rawValue);
    });
    return result;
}

function cssColor(value) {
    if (!value) return null;
    if (COLOR_RE.test(value)) return value;
    const match = /^rgb\((\d{1,3}),\s*(\d{1,3}),\s*(\d{1,3})\)$/.exec(value);
    if (!match) return null;
    const parts = match.slice(1).map(number => Number(number));
    if (parts.some(part => part < 0 || part > 255)) return null;
    return `#${parts.map(part => part.toString(16).padStart(2, '0')).join('')}`;
}

function normalizeMarks(value) {
    const marks = requireArray(value);
    marks.forEach(mark => {
        if (!MARK_ORDER.includes(mark)) {
            throw new FragmentValidationError('unsupported mark');
        }
    });
    return MARK_ORDER.filter(mark => marks.includes(mark));
}

function normalizeColor(value) {
    if (value === null) {
        return null;
    }
    if (typeof value !== 'string' || !COLOR_RE.test(value)) {
        throw new FragmentValidationError('invalid color');
    }
    return value;
}

function normalizeHttpsUrl(value) {
    if (typeof value !== 'string') {
        throw new FragmentValidationError('invalid link');
    }
    let parsed;
    try {
        parsed = new URL(value);
    } catch (error) {
        throw new FragmentValidationError('invalid link');
    }
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password || /[\u0000-\u001f\u007f]/.test(value)) {
        throw new FragmentValidationError('unsafe link');
    }
    return parsed.href;
}

function normalizeUuid(value) {
    if (typeof value !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value)) {
        throw new FragmentValidationError('invalid reference id');
    }
    return value;
}

function requireObject(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        throw new FragmentValidationError('object expected');
    }
    return value;
}

function requireArray(value) {
    if (!Array.isArray(value)) {
        throw new FragmentValidationError('array expected');
    }
    return value;
}

function requireKeys(value, expected) {
    const keys = Object.keys(value).sort();
    const wanted = [...expected].sort();
    if (keys.length !== wanted.length || keys.some((key, index) => key !== wanted[index])) {
        throw new FragmentValidationError('unexpected keys');
    }
}

function requireText(value) {
    if (typeof value !== 'string' || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value)) {
        throw new FragmentValidationError('invalid text');
    }
    return value;
}

function countNode(guard, depth) {
    guard.count += 1;
    if (guard.count > MAX_NODES || depth > MAX_DEPTH) {
        throw new FragmentValidationError('fragment limits exceeded');
    }
}

function utf8ByteLength(value) {
    return new TextEncoder().encode(value).length;
}

function blockText(block) {
    if (block.type === 'paragraph' || block.type === 'heading') {
        return inlineText(block.content);
    }
    if (block.type === 'quote') {
        return block.blocks.map(blockText).join('\n');
    }
    if (block.type === 'list') {
        return block.items.map(item => item.blocks.map(blockText).join('\n')).join('\n');
    }
    if (block.type === 'table') {
        return [block.headers, ...block.rows].map(row => row.map(inlineText).join('\t')).join('\n');
    }
    if (block.type === 'code') {
        return block.text;
    }
    return '';
}

function inlineText(content) {
    return content.map(inline => {
        if (inline.type === 'break') return '\n';
        if (inline.type === 'link') return inlineText(inline.content);
        return inline.text;
    }).join('');
}
