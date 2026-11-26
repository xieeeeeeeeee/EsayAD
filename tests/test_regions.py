import json
import math
from pathlib import Path
import tempfile
import unittest

from assistant.regions import flatten_region
from assistant.exporter import Exporter


class RegionTests(unittest.TestCase):
    def test_capsule_bounds_area_and_sweep_are_preserved(self):
        points = flatten_region('M 0 0 A 1 1 0 0 1 0 -2 L 4 -2 A 1 1 0 0 1 4 0 Z')
        self.assertEqual(points[0], points[-1])
        self.assertAlmostEqual(min(x for x, y in points), -1, delta=0.004)
        self.assertAlmostEqual(max(x for x, y in points), 5, delta=0.004)
        self.assertEqual(min(y for x, y in points), -2)
        self.assertEqual(max(y for x, y in points), 0)
        area = abs(sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(points,points[1:]))) / 2
        self.assertAlmostEqual(area, 8+math.pi, delta=0.03)

    def test_reverse_sweep_changes_the_arc_side(self):
        top = flatten_region('M 0 0 A 1 1 0 0 1 2 0 L 0 0 Z')
        bottom = flatten_region('M 0 0 A 1 1 0 0 0 2 0 L 0 0 Z')
        self.assertLess(min(y for x,y in top), -0.99)
        self.assertGreater(max(y for x,y in bottom), 0.99)

    def test_unhandled_path_never_silently_discards_commands(self):
        for path in ('M0 0 C1 2 3 4 5 6 Z', 'M0 0 L1 0 M2 0 L3 0 Z', 'M0 0 L1 0', 'M0 0 A1 2 0 0 1 2 0 Z', 'M0 0 LNaN 0 Z'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                flatten_region(path)

    def test_esp8266_paste_regions_are_kept_with_original_layer_and_count(self):
        raw = json.loads((Path(__file__).parent / 'fixtures/C77967.json').read_text(encoding='utf-8-sig'))
        with tempfile.TemporaryDirectory() as temp:
            result = Exporter(Path(temp)).export('C77967', raw)
            self.assertEqual(len(result.symbol.pins), 33)
            self.assertEqual(len(result.footprint.pads), 33)
            source_count = sum(s.startswith('SOLIDREGION~5~') for s in raw['packageDetail']['dataStr']['shape'])
            regions = [r for r in result.footprint.regions if r.layer == 35]
            self.assertEqual(source_count, 33)
            self.assertEqual(len(regions), 33)
            self.assertEqual(sum(len(r.points) > 10 for r in regions), 32)
            self.assertTrue(all(r.points[0] == r.points[-1] for r in regions))
            self.assertTrue(any('曲线' in w for w in result.warnings))


if __name__ == '__main__':
    unittest.main()
