import json
import os
from pathlib import Path

from .hsdes_projection import HsdesProviderProjectionService
from .provider_aggregate_contracts import FIRST_HSDES_PROFILE_ID, FIRST_HSDES_QUERY_ID


class HsdesSeedFactRepository:
    def __init__(self, projection_service=None, seed_path=None, preview_seed_path=None):
        self._projection_service = projection_service or HsdesProviderProjectionService()
        self._seed_path = seed_path or Path(__file__).resolve().parents[2] / 'fixtures' / 'hsdes_nvu_ttl_seed_articles.json'
        configured_preview_path = os.environ.get('METRICS_HSDES_PREVIEW_SEED_PATH', '')
        self._preview_seed_path = preview_seed_path or (Path(configured_preview_path) if configured_preview_path else None)

    def facts_for_profile(self, profile_id: str) -> list[dict]:
        seed_path = self._resolved_seed_path()
        if profile_id != FIRST_HSDES_PROFILE_ID or not seed_path.exists():
            return []
        payload = json.loads(seed_path.read_text(encoding='utf-8'))
        if payload.get('profile_id') != profile_id or payload.get('seeded_from_query_id') != FIRST_HSDES_QUERY_ID:
            return []
        return self._projection_service.normalize_search_page(profile_id, payload)['facts']

    def _resolved_seed_path(self) -> Path:
        if self._preview_seed_path and self._preview_seed_path.exists():
            return self._preview_seed_path
        return self._seed_path
