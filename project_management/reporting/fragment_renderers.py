from html import escape

from project_management.app.domain.report_authoring_fragments import rich_text_fragment_plain_text, validate_rich_text_fragment


MARK_TAGS = {'strong': 'strong', 'em': 'em', 'strike': 's', 'code': 'code'}


def rich_fragment_to_html(fragment) -> str:
    return ''.join(_block_html(block) for block in validate_rich_text_fragment(fragment)['blocks'])


def rich_fragment_to_plain_text(fragment) -> str:
    return rich_text_fragment_plain_text(fragment)


def _block_html(block):
    node_type = block['type']
    if node_type == 'paragraph':
        return f'<p style="margin:0 0 8px 0;">{_inlines_html(block["content"])}</p>'
    if node_type == 'heading':
        return f'<h{block["level"]}>{_inlines_html(block["content"])}</h{block["level"]}>'
    if node_type == 'quote':
        return f'<blockquote style="margin:0 0 8px 0; padding-left:10px; border-left:3px solid #cbd5e1;">{_blocks_html(block["blocks"])}</blockquote>'
    if node_type == 'list':
        tag = 'ol' if block['ordered'] else 'ul'
        return f'<{tag}>' + ''.join(_list_item_html(item) for item in block['items']) + f'</{tag}>'
    if node_type == 'table':
        headers = ''.join(f'<th>{_inlines_html(cell)}</th>' for cell in block['headers'])
        rows = ''.join('<tr>' + ''.join(f'<td>{_inlines_html(cell)}</td>' for cell in row) + '</tr>' for row in block['rows'])
        return f'<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>'
    if node_type == 'code':
        return f'<pre><code>{escape(block["text"])}</code></pre>'
    return ''


def _blocks_html(blocks):
    return ''.join(_block_html(block) for block in blocks)


def _list_item_html(item):
    marker = ''
    if item['checked'] is True:
        marker = '[x] '
    if item['checked'] is False:
        marker = '[ ] '
    return f'<li>{marker}{_blocks_html(item["blocks"])}</li>'


def _inlines_html(inlines):
    return ''.join(_inline_html(inline) for inline in inlines)


def _inline_html(inline):
    node_type = inline['type']
    if node_type == 'break':
        return '<br>'
    if node_type == 'link':
        reference = ''
        if inline.get('reference_id'):
            reference = f' data-reference-id="{escape(inline["reference_id"], quote=True)}"'
        return f'<a href="{escape(inline["href"], quote=True)}"{reference}>{_inlines_html(inline["content"])}</a>'
    text = escape(inline['text'])
    marks = inline['marks']
    style = _style(inline)
    if not marks:
        return f'<span style="{style}">{text}</span>' if style else text
    result = text
    for mark in reversed(marks):
        tag = MARK_TAGS[mark]
        style_attr = f' style="{style}"' if mark == marks[0] and style else ''
        result = f'<{tag}{style_attr}>{result}</{tag}>'
    return result


def _style(inline):
    parts = []
    if inline['foreground'] is not None:
        parts.append(f'color:{inline["foreground"]};')
    if inline['background'] is not None:
        parts.append(f'background-color:{inline["background"]};')
    return ' '.join(parts)
