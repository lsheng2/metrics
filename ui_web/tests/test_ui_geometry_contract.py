import ast
import itertools
import re
import subprocess
import sys
from functools import cache
from pathlib import Path

from django.test import SimpleTestCase

from ui_web.tests import ui_geometry_contract as geometry

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
REGISTRY_PATH = TESTS_DIR / 'ui_geometry_contract.py'
OWN_FILES = {REGISTRY_PATH.name, Path(__file__).name}
ORDER_ASSERTS = {'assertLess', 'assertLessEqual', 'assertGreater', 'assertGreaterEqual'}
ORDER_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
VIEWPORT = re.compile(r'\d+x\d+')
# Any module that measures the rendered page is scanned, whether or not it imports the registry yet.
BROWSER_MEASUREMENT = re.compile(r'\.evaluate\w*\(|bounding_box\(|getBoundingClientRect')
JS_ORDER_LITERAL = re.compile(r'([\w.\])]+)\s*(<=|>=|<|>)(?!=)\s*(-?\d+(?:\.\d+)?)(?![\w.])')
# Lower-cased operand fragments that mark a literal comparison as a count or a ratio, not geometry.
NON_GEOMETRY_OPERANDS = {
    'len(': 'Python collection size',
    '.length': 'JavaScript collection size',
    'count': 'element count such as tab_count or provider_choice_count',
    'contrast': 'WCAG colour contrast ratio',
}


class TestUiGeometryContract(SimpleTestCase):
    def test_shouldDeclareEachRuleOnceFromItsOwnConstant(self):
        # Given
        rules = geometry.GEOMETRY_RULES
        limit_names = _rule_limit_names()

        # When
        keys = [rule.key for rule in rules]
        constants = {name for name, value in vars(geometry).items() if name.isupper() and type(value) in (int, float)}
        malformed = [
            rule.key for rule in rules
            if getattr(geometry, rule.key, None) != rule.limit
            or limit_names.get(rule.key) != rule.key
            or rule.comparison not in geometry.COMPARISONS
            or not (rule.unit and rule.surface and rule.measures and rule.enforced_by)
            or not all(VIEWPORT.fullmatch(viewport) for viewport in rule.viewports)
        ]

        # Then
        self.assertEqual([], sorted({key for key in keys if keys.count(key) > 1}))
        self.assertEqual(constants, set(keys))
        self.assertEqual([], malformed, 'Pass the constant itself as the rule limit and use a known comparison')
        self.assertEqual({rule.key: rule.limit for rule in rules}, geometry.browser_limits())

    def test_shouldReferenceEveryRuleConstantOutsideTheRegistry(self):
        # Given
        sources = _test_sources()

        # When
        unreferenced = [rule.key for rule in geometry.GEOMETRY_RULES if not _referencing_modules(rule.key, sources)]

        # Then
        self.assertEqual([], unreferenced, 'Remove the rule or enforce it from a ui_web test module')

    def test_shouldListExactlyTheModulesThatEnforceEachRule(self):
        # Given
        sources = _test_sources()

        # When
        missing = [
            f'{rule.key}: {module}'
            for rule in geometry.GEOMETRY_RULES
            for module in rule.enforced_by
            if not re.search(rf'\b{rule.key}\b', sources.get(module, ''))
        ]
        undeclared = [
            f'{rule.key}: {module}'
            for rule in geometry.GEOMETRY_RULES
            for module in sorted(_referencing_modules(rule.key, sources) - set(rule.enforced_by))
        ]

        # Then
        self.assertEqual([], missing, 'enforced_by names a module that is missing or does not reference the rule')
        self.assertEqual([], undeclared, 'Add these modules to the enforced_by tuple of the rule')

    def test_shouldCompareMeasuredGeometryOnlyToRegistryLimits(self):
        # Given
        sources = _test_sources()
        scanned = {
            module for module, source in sources.items()
            if 'ui_geometry_contract' in source or BROWSER_MEASUREMENT.search(source)
        }
        scanned |= {module for rule in geometry.GEOMETRY_RULES for module in rule.enforced_by}

        # When
        findings = sorted(finding for module in scanned for finding in _literal_findings(module, sources[module]))

        # Then
        self.assertEqual([], findings, 'Compare with a ui_geometry_contract constant, or limits.<KEY> in JavaScript')

    def test_shouldPrintTheContractAsMarkdownWhenRunAsAScript(self):
        # Given
        command = [sys.executable, '-I', '-X', 'utf8', str(REGISTRY_PATH)]

        # When
        result = subprocess.run(command, cwd=TESTS_DIR, capture_output=True, encoding='utf-8', check=False)

        # Then
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('| key | limit | unit | comparison | measures | enforced_by |', result.stdout)
        self.assertEqual([], [rule.key for rule in geometry.GEOMETRY_RULES if f'| {rule.key} |' not in result.stdout])
        self.assertEqual([], [rule.surface for rule in geometry.GEOMETRY_RULES if f'## {rule.surface}\n' not in result.stdout])


@cache
def _test_sources():
    return {
        '.'.join(path.relative_to(REPO_ROOT).with_suffix('').parts): path.read_text(encoding='utf-8')
        for path in sorted(TESTS_DIR.rglob('*.py'))
        if path.name not in OWN_FILES
    }


def _referencing_modules(key, sources):
    pattern = re.compile(rf'\b{key}\b')
    return {module for module, source in sources.items() if pattern.search(source)}


def _rule_limit_names():
    return {
        call.args[0].value: getattr(call.args[1], 'id', None)
        for call in ast.walk(ast.parse(REGISTRY_PATH.read_text(encoding='utf-8')))
        if isinstance(call, ast.Call) and getattr(call.func, 'id', None) == 'GeometryRule'
    }


def _literal_findings(module, source):
    findings = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert'):
            for measured, value in _python_literal_comparisons(node):
                text = ast.get_source_segment(source, measured)
                if not _is_non_geometry(text):
                    findings.add(f'{module}:{node.lineno}: {node.func.attr}({text} vs {value})')
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and ('=>' in node.value or 'document.' in node.value):
            for offset, line in enumerate(node.value.splitlines()):
                for match in JS_ORDER_LITERAL.finditer(line):
                    if abs(float(match.group(3))) >= 2 and not _is_non_geometry(match.group(1)):
                        findings.add(f'{module}:{node.lineno + offset}: JavaScript {match.group(0)}')
    return findings


def _python_literal_comparisons(call):
    operands = call.args[:2]
    pairs = [tuple(operands)] if call.func.attr in ORDER_ASSERTS and len(operands) == 2 else []
    pairs += [
        pair
        for operand in operands
        for compare in ast.walk(operand)
        if isinstance(compare, ast.Compare)
        for op, pair in zip(compare.ops, itertools.pairwise([compare.left, *compare.comparators]))
        if isinstance(op, ORDER_OPS)
    ]
    for left, right in pairs:
        for literal, measured in ((left, right), (right, left)):
            value = _numeric_literal(literal)
            if value is not None and abs(value) >= 2:
                yield measured, value


def _numeric_literal(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _numeric_literal(node.operand)
        return None if value is None else -value
    return node.value if isinstance(node, ast.Constant) and type(node.value) in (int, float) else None


def _is_non_geometry(text):
    return any(fragment in text.lower() for fragment in NON_GEOMETRY_OPERANDS)
