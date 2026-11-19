import unittest

from ui_web.utils.color_utils import CHART_PALETTE_SIZE, ColorUtils


class TestColorUtilsPaletteSlot(unittest.TestCase):

    def test_shouldReturnSameSlotWhenSameNameProvidedTwice(self):
        self.assertEqual(ColorUtils.palette_slot("Abdul Bram"), ColorUtils.palette_slot("Abdul Bram"))

    def test_shouldSpreadNamesAcrossOneBasedPaletteSlots(self):
        names = [f"Developer {index}" for index in range(40)]

        slots = {ColorUtils.palette_slot(name) for name in names}

        self.assertTrue(slots <= set(range(1, CHART_PALETTE_SIZE + 1)))
        self.assertGreater(len(slots), CHART_PALETTE_SIZE // 2)

    def test_shouldUseDefaultSlotWhenNameMissing(self):
        expected = ColorUtils.palette_slot("default")

        self.assertEqual(expected, ColorUtils.palette_slot(""))
        self.assertEqual(expected, ColorUtils.palette_slot(None))
