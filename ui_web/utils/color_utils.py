import hashlib

# Matches the DashboardCharts palette (--color-chart-1..8); templates expose a slot as `data-palette-slot`.
CHART_PALETTE_SIZE = 8


class ColorUtils:
    @staticmethod
    def palette_slot(input_str: str) -> int:
        """Stable 1-based palette slot for a name, so a person keeps one avatar colour everywhere."""
        hash_bytes = hashlib.sha256((input_str or "default").encode('utf-8')).digest()
        return int.from_bytes(hash_bytes[0:2], byteorder='big') % CHART_PALETTE_SIZE + 1
