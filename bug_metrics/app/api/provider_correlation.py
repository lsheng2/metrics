import hashlib
import re
from datetime import date


CORRELATION_STATES = frozenset({'candidate', 'confirmed', 'rejected', 'stale'})


class ProviderCorrelationService:
    def generate_candidates(self, source_facts: list[dict], target_facts: list[dict]) -> list[dict]:
        candidates = []
        for source in source_facts:
            for target in target_facts:
                evidence = self._evidence(source, target)
                if evidence:
                    candidates.append(self._candidate(source, target, evidence))
        return sorted(candidates, key=lambda candidate: candidate['confidence'], reverse=True)

    def review_correlation(self, candidate: dict, state: str, reviewer: str) -> dict:
        if state not in CORRELATION_STATES:
            raise ValueError(f'Unsupported correlation state: {state}.')
        reviewed = dict(candidate)
        reviewed['state'] = state
        reviewed['reviewer'] = reviewer
        return reviewed

    def evidence_view(self, correlations: list[dict]) -> dict:
        rows = []
        for correlation in correlations:
            rows.append(self._evidence_row(correlation, correlation['source']))
            rows.append(self._evidence_row(correlation, correlation['target']))
        return {
            'contract_version': '0.1',
            'rows': rows,
        }

    def explain_risk(self, correlations: list[dict]) -> dict:
        state_counts = {state: 0 for state in sorted(CORRELATION_STATES)}
        for correlation in correlations:
            state_counts[correlation.get('state', 'candidate')] += 1
        return {
            'contract_version': '0.1',
            'state_counts': state_counts,
            'answer': (
                f"confirmed={state_counts['confirmed']}, "
                f"candidate={state_counts['candidate']}, "
                f"rejected={state_counts['rejected']}, "
                f"stale={state_counts['stale']}; cross-provider risk explanation keeps Jira and HSD-ES native states separate."
            ),
        }

    def _candidate(self, source: dict, target: dict, evidence: list[dict]) -> dict:
        confidence = min(1.0, sum(item['weight'] for item in evidence))
        payload = f"{source.get('provider_id')}:{source.get('source_item_id')}->{target.get('provider_id')}:{target.get('source_item_id')}"
        return {
            'correlation_id': hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16],
            'state': 'candidate',
            'confidence': round(confidence, 2),
            'source': self._side(source),
            'target': self._side(target),
            'evidence': evidence,
        }

    def _side(self, fact: dict) -> dict:
        canonical_fields = fact.get('canonical_fields', {})
        native_fields = fact.get('native_fields') or fact.get('field_values') or {}
        return {
            'provider_id': fact.get('provider_id', ''),
            'profile_id': fact.get('profile_id', ''),
            'source_item_id': fact.get('source_item_id', ''),
            'canonical_fields': canonical_fields,
            'native_fields': native_fields,
        }

    def _evidence(self, source: dict, target: dict) -> list[dict]:
        evidence = []
        if self._explicitly_linked(source, target):
            evidence.append(self._evidence_item('explicit_link', source, target, 0.4, source.get('source_item_id', '')))
        if self._fingerprint(source) and self._fingerprint(source) == self._fingerprint(target):
            evidence.append(self._evidence_item('title_fingerprint', source, target, 0.25, self._fingerprint(source)))
        for field_name, evidence_type, weight in [
            ('component_or_area', 'component_overlap', 0.12),
            ('release_target', 'release_overlap', 0.1),
            ('owner', 'owner_overlap', 0.08),
        ]:
            if self._canonical(source, field_name) and self._canonical(source, field_name) == self._canonical(target, field_name):
                evidence.append(self._evidence_item(evidence_type, source, target, weight, self._canonical(source, field_name)))
        if self._within_time_window(source, target):
            evidence.append(self._evidence_item('time_window', source, target, 0.05, 'created_at<=7d'))
        return evidence

    def _evidence_item(self, evidence_type: str, source: dict, target: dict, weight: float, value: str) -> dict:
        return {
            'type': evidence_type,
            'weight': weight,
            'matched_value': value,
            'source_provider_id': source.get('provider_id', ''),
            'target_provider_id': target.get('provider_id', ''),
        }

    def _explicitly_linked(self, source: dict, target: dict) -> bool:
        source_id = source.get('source_item_id', '')
        target_id = target.get('source_item_id', '')
        source_native = source.get('native_fields', {})
        target_native = target.get('native_fields', {})
        if source_native.get('external_id') == target_id or target_native.get('external_id') == source_id:
            return True
        for link in source.get('links', []) + target.get('links', []):
            if link.get('target_id') in {source_id, target_id}:
                return True
        return False

    def _fingerprint(self, fact: dict) -> str:
        title = self._canonical(fact, 'title') or fact.get('summary', '')
        return re.sub(r'[^a-z0-9]+', '', title.lower())

    def _canonical(self, fact: dict, field_name: str) -> str:
        value = fact.get('canonical_fields', {}).get(field_name, '')
        if value is None:
            return ''
        return str(value)

    def _within_time_window(self, source: dict, target: dict) -> bool:
        source_date = self._date_from_iso(self._canonical(source, 'created_at'))
        target_date = self._date_from_iso(self._canonical(target, 'created_at'))
        if not source_date or not target_date:
            return False
        return abs((source_date - target_date).days) <= 7

    def _date_from_iso(self, value: str) -> date | None:
        if not value:
            return None
        return date.fromisoformat(value[:10])

    def _evidence_row(self, correlation: dict, side: dict) -> dict:
        return {
            'correlation_id': correlation['correlation_id'],
            'correlation_state': correlation['state'],
            'provider_id': side['provider_id'],
            'profile_id': side['profile_id'],
            'source_item_id': side['source_item_id'],
            'canonical_state': side['canonical_fields'].get('source_state', ''),
            'native_state': side['native_fields'].get('status', ''),
            'native_fields': side['native_fields'],
        }
