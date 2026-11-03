from django.template import Context, Engine
from uuid import UUID

from project_management.app.domain.capture_values import canonical_bytes, content_hash, sha256_bytes
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_edits import validate_edit_targets
from project_management.app.domain.report_presentation import RenderedReport
from project_management.reporting.templates import load_default_registry, resolve_template
from project_management.reporting.text import build_plain_text
from project_management.reporting.validation import validate_rendered_html
from project_management.reporting.view_model import build_report_model


MAX_SNAPSHOT_BYTES = 8_388_608


class ReportRenderer:
    def __init__(self, registry=None, *, max_html_bytes=16_777_216, max_clipboard_bytes=2_097_152):
        self._validate_limits(max_html_bytes, max_clipboard_bytes)
        package_registry = load_default_registry()
        self._registry = package_registry if registry is None else self._verified_registry(package_registry, registry)
        self._max_html_bytes = max_html_bytes
        self._max_clipboard_bytes = max_clipboard_bytes
        self._engine = Engine(
            debug=False,
            autoescape=True,
            loaders=[('django.template.loaders.locmem.Loader', self._partials())],
        )

    def render(self, snapshot, template, edits=(), *, draft_id, revision, revision_hash=None, edition_state='draft') -> RenderedReport:
        self._validate_render_request(draft_id, revision, edition_state, revision_hash)
        template_value, definition = resolve_template(self._registry, template)
        snapshot_hash = self._snapshot_hash(snapshot)
        validated_edits = validate_edit_targets(snapshot, edits)
        model = build_report_model(
            snapshot,
            definition,
            validated_edits,
            draft_id=draft_id,
            revision=revision,
            revision_hash=revision_hash,
            edition_state=edition_state,
        )
        fragment = self._render_fragment(template_value.content, model)
        plain_text = build_plain_text(model)
        document = self._document(fragment, model['title'])
        validate_rendered_html(document)
        document_bytes = document.encode('utf-8')
        fragment_bytes = fragment.encode('utf-8')
        plain_text_bytes = plain_text.encode('utf-8')
        if len(document_bytes) > self._max_html_bytes:
            raise ReportError('REPORT_LIMIT')
        return RenderedReport(
            draft_id=draft_id,
            revision=revision,
            revision_hash=revision_hash,
            snapshot_hash=snapshot_hash,
            template_hash=definition.template_hash,
            html_document=document_bytes,
            html_fragment=fragment,
            plain_text=plain_text,
            html_document_sha256=sha256_bytes(document_bytes),
            html_document_bytes=len(document_bytes),
            html_fragment_sha256=sha256_bytes(fragment_bytes),
            html_fragment_bytes=len(fragment_bytes),
            plain_text_sha256=sha256_bytes(plain_text_bytes),
            plain_text_bytes=len(plain_text_bytes),
            content_language='en',
            clipboard_available=len(fragment_bytes) <= self._max_clipboard_bytes,
        )

    def template_definition(self, template):
        _, definition = resolve_template(self._registry, template)
        return definition

    def _snapshot_hash(self, snapshot) -> str:
        snapshot_bytes = canonical_bytes(snapshot)
        if len(snapshot_bytes) > MAX_SNAPSHOT_BYTES:
            raise ReportError('REPORT_LIMIT')
        return content_hash(snapshot)

    def _render_fragment(self, content: str, model: dict) -> str:
        compiled = self._engine.from_string(content)
        return compiled.render(Context(model, autoescape=True, use_l10n=False, use_tz=False)).strip()

    def _document(self, fragment: str, title: str) -> str:
        return (
            '<!doctype html>\n'
            '<html lang="en">\n'
            '<head>\n'
            '<meta charset="utf-8">\n'
            f'<title>{title}</title>\n'
            '</head>\n'
            '<body style="margin:0; background:#ffffff; color:#1f2933; '
            'font-family:Segoe UI, Arial, sans-serif; font-size:14px; line-height:1.45;">\n'
            f'{fragment}\n'
            '</body>\n'
            '</html>'
        )

    def _validate_render_request(self, draft_id, revision, edition_state, revision_hash) -> None:
        if type(draft_id) is not str:
            raise ReportError('REPORT_INVALID')
        try:
            parsed = UUID(draft_id)
        except (TypeError, ValueError, AttributeError):
            raise ReportError('REPORT_INVALID') from None
        if str(parsed) != draft_id.lower():
            raise ReportError('REPORT_INVALID')
        if type(revision) is not int or revision < 1:
            raise ReportError('REPORT_INVALID')
        if edition_state not in {'draft', 'final'}:
            raise ReportError('REPORT_INVALID')
        if revision_hash is not None and (
                type(revision_hash) is not str
                or len(revision_hash) != 64
                or any(character not in '0123456789abcdef' for character in revision_hash)):
            raise ReportError('REPORT_INVALID')

    def _validate_limits(self, max_html_bytes, max_clipboard_bytes) -> None:
        for value in (max_html_bytes, max_clipboard_bytes):
            if type(value) is not int or value <= 0:
                raise ReportError('REPORT_INVALID')

    def _partials(self) -> dict[str, str]:
        partials = {}
        for template in self._registry.values():
            for name, content in getattr(template, 'dependencies', {}).items():
                if name in partials and partials[name] != content:
                    raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
                partials[name] = content
        return partials

    def _verified_registry(self, package_registry, registry):
        supplied = dict(registry)
        if set(supplied.keys()) != set(package_registry.keys()):
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        for key, expected in package_registry.items():
            actual = supplied.get(key)
            if (actual != expected
                    or actual.content != expected.content
                    or actual.dependencies != expected.dependencies
                    or actual.template_hash != expected.template_hash):
                raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        return supplied
