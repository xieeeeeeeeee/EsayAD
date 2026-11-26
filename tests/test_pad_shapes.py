import copy
import json
from pathlib import Path
import tempfile
import unittest
import math

from assistant.pad_shapes import native_oval
from assistant.exporter import Exporter


class PadShapeTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((Path(__file__).parent / 'fixtures/C534876.json').read_text(encoding='utf-8-sig'))
        self.pad = next(s for s in self.raw['packageDetail']['dataStr']['shape'] if s.startswith('PAD~POLYGON~'))

    def test_btt6200_contours_become_numbered_native_oval_pads(self):
        original = copy.deepcopy(self.raw)
        with tempfile.TemporaryDirectory() as temp:
            result = Exporter(Path(temp)).export('C534876', self.raw)
            self.assertEqual(len(result.symbol.pins), 25)
            self.assertEqual(len(result.footprint.pads), 25)
            self.assertEqual(result.pin_numbers, result.pad_numbers)
            self.assertEqual(sum(p.shape == 9 for p in result.footprint.pads), 24)
            pad = next(p for p in result.footprint.pads if p.name == '1')
            self.assertEqual((pad.size_x, pad.size_y, pad.hole_size), (177160, 515750, 0))
            self.assertEqual(pad.rotation, 180)
            self.assertEqual(pad.layer, 1)
            self.assertTrue(result.pcblib.is_file())
        self.assertEqual(self.raw, original)

    def test_only_verified_oval_contour_is_accepted(self):
        fields = self.pad.split('~')
        self.assertEqual(native_oval(fields)[1], 'OVAL')
        for mutation in ('distorted', 'crossed', 'hole', 'truncated'):
            bad = fields.copy()
            values = bad[10].split()
            if mutation == 'distorted':
                values[0] = str(float(values[0]) - 0.1)
            elif mutation == 'crossed':
                pairs = list(zip(values[::2], values[1::2]))
                pairs = pairs[::2] + pairs[1::2]
                values = [v for pair in pairs for v in pair]
            elif mutation == 'hole':
                bad[9] = '0.2'
            else:
                values = values[:20]
            bad[10] = ' '.join(values)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                native_oval(bad)

    def test_long_chord_that_cuts_inside_oval_is_rejected(self):
        points=[(math.cos(.12),10+math.sin(.12)),(1,-10)]
        points += [(math.cos(-i*math.pi/64),-10+math.sin(-i*math.pi/64)) for i in range(1,65)]
        points += [(-1,10)]
        points += [(math.cos(math.pi-i*math.pi/64),10+math.sin(math.pi-i*math.pi/64)) for i in range(1,65)]
        fields=self.pad.split('~')
        fields[2:6]=['0','0','2','22']
        fields[11]='0'
        fields[10]=' '.join(str(v) for point in points for v in point)
        with self.assertRaises(ValueError):
            native_oval(fields)


if __name__ == '__main__':
    unittest.main()
