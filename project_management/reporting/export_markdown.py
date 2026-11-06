from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_exports import GENERATOR_REVISION, MAX_TEXT_LINES


def render_markdown(body, source_sha256, markdownify):
    class ReportMarkdownConverter(markdownify.MarkdownConverter):
        def convert_br(self, element, text, parent_tags):
            if element.find_parent(['td', 'th']):
                return '<br>' + text
            return super().convert_br(element, text, parent_tags)

        def convert_p(self, element, text, parent_tags):
            if element.find_parent(['td', 'th']):
                return text.strip() + '<br>' if text.strip() else ''
            return super().convert_p(element, text, parent_tags)

        def convert_td(self, element, text, parent_tags):
            return ' ' + text.strip().replace('\n', '<br>').removesuffix('<br>') + ' |'

        convert_th = convert_td

    converter = ReportMarkdownConverter(heading_style='ATX', escape_misc=True, autolinks=False)
    text = converter.convert_soup(body).strip()
    header = f'<!-- {GENERATOR_REVISION}; source-sha256={source_sha256}; paint_omitted -->'
    output = f'{header}\n\n{text}\n'
    if len(output.splitlines()) + output.count('<br>') > MAX_TEXT_LINES:
        raise ReportError('REPORT_LIMIT')
    return output.encode('utf-8')
