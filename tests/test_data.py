import copy
import json
import tempfile
import unittest
from pathlib import Path

from assistant.catalog import Catalog, ServiceError, normalize_id, parse_search
from assistant.exporter import Exporter, ConversionError

FIXTURES = Path(__file__).parent / 'fixtures'


class CatalogTests(unittest.TestCase):
    def test_id_normalization_rejects_paths_and_partial_matches(self):
        self.assertEqual(normalize_id(' c25804 '), 'C25804')
        for value in ('../C25804', 'C25804.exe', 'C0', 'hello', ''):
            with self.assertRaises(ValueError):
                normalize_id(value)

    def test_maps_actual_search_response_and_preserves_total(self):
        payload = {'code': 200, 'data': {'componentPageInfo': {'total': 62, 'list': [
            {'componentCode': 'C7593', 'componentModelEn': 'NE555DR',
             'componentBrandEn': 'Texas Instruments', 'componentSpecificationEn': 'SOIC-8',
             'describe': '555 timer', 'lcscGoodsUrl': 'https://www.lcsc.com/product-detail/C7593.html'}]}}}
        page = parse_search(payload, 1)
        self.assertEqual(page.total, 62)
        self.assertEqual(page.parts[0].lcsc, 'C7593')
        self.assertEqual(page.parts[0].model, 'NE555DR')
        self.assertEqual(page.parts[0].package, 'SOIC-8')
        self.assertIsNone(page.parts[0].has_model)

    def test_service_error_is_not_reported_as_no_results(self):
        for payload in ({'code': 403, 'message': 'denied'}, {'code': 200, 'data': {}}):
            with self.assertRaises(ServiceError):
                parse_search(payload, 1)

    def test_corrupt_cache_refetches_and_failed_fetch_does_not_poison_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'C25804.json').write_text('broken', encoding='utf-8')
            fixture = json.loads((FIXTURES / 'C25804.json').read_text(encoding='utf-8'))
            client = Catalog(root, transport=lambda *a, **kw: fixture)
            self.assertEqual(client.component('C25804')['title'], '0603WAF1002T5E')
            self.assertEqual(json.loads((root / 'C25804.json').read_text(encoding='utf-8'))['title'], '0603WAF1002T5E')
            client = Catalog(root, transport=lambda *a, **kw: {'success': False})
            with self.assertRaises(ServiceError):
                client.component('C7593')
            self.assertFalse((root / 'C7593.json').exists())


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.exporter = Exporter(Path(self.temp.name))
        self.raw = json.loads((FIXTURES / 'C25804.json').read_text(encoding='utf-8'))['result']

    def test_actual_resistor_outputs_readable_paired_libraries(self):
        import olefile
        result = self.exporter.export('C25804', self.raw)
        self.assertEqual(result.pin_numbers, ['1', '2'])
        self.assertEqual(result.pad_numbers, ['1', '2'])
        self.assertEqual(result.symbol.package, result.footprint.name)
        self.assertAlmostEqual(result.footprint.pads[0].size_x / 10000, 31.751, places=2)
        with olefile.OleFileIO(str(result.schlib)) as lib:
            blob = lib.openstream([result.symbol.name, 'Data']).read()
            self.assertIn(b'C25804', blob)
            self.assertIn(b'0603WAF1002T5E', blob)
            self.assertIn(b'https://', blob)
        with olefile.OleFileIO(str(result.pcblib)) as lib:
            self.assertTrue(lib.exists([result.footprint.name, 'Data']))
        self.assertEqual(json.loads(result.manifest.read_text(encoding='utf-8'))['state'], 'generated')

    def test_no_footprint_does_not_leave_partial_success(self):
        self.raw.pop('packageDetail')
        with self.assertRaises(ConversionError):
            self.exporter.export('C25804', self.raw)
        self.assertEqual(list(Path(self.temp.name).rglob('*.SchLib')), [])

    def test_unknown_copper_shape_is_blocked(self):
        self.raw['packageDetail']['dataStr']['shape'].append('FUTURE_COPPER~1~2')
        with self.assertRaises(ConversionError):
            self.exporter.export('C25804', self.raw)

    def test_missing_pin_pad_mapping_is_blocked(self):
        shapes = self.raw['packageDetail']['dataStr']['shape']
        self.raw['packageDetail']['dataStr']['shape'] = [s for s in shapes if not (s.startswith('PAD~') and s.split('~')[8] == '2')]
        with self.assertRaises(ConversionError):
            self.exporter.export('C25804', self.raw)

    def test_complex_slotted_pad_is_blocked(self):
        shapes = self.raw['packageDetail']['dataStr']['shape']
        index = next(i for i, s in enumerate(shapes) if s.startswith('PAD~'))
        fields = shapes[index].split('~')
        fields[1] = 'POLYGON'
        shapes[index] = '~'.join(fields)
        with self.assertRaises(ConversionError):
            self.exporter.export('C25804', self.raw)

    def test_two_exports_never_overwrite_prior_library(self):
        first = self.exporter.export('C25804', self.raw)
        before = first.schlib.read_bytes()
        second = self.exporter.export('C25804', self.raw)
        self.assertNotEqual(first.schlib, second.schlib)
        self.assertEqual(first.schlib.read_bytes(), before)

    def test_ams1117_decimal_zero_is_not_a_slot(self):
        raw = json.loads((FIXTURES / 'C6186.json').read_text(encoding='utf-8'))
        result = self.exporter.export('C6186', raw)
        self.assertEqual(result.pin_numbers, ['1', '2', '3', '4'])
        self.assertEqual(result.pad_numbers, ['1', '2', '3', '4'])
        self.assertTrue(all(p.hole_size == 0 for p in result.footprint.pads))
        self.assertTrue(result.schlib.is_file())
        self.assertTrue(result.pcblib.is_file())

    def test_numeric_zero_hole_lengths_export_but_real_slots_are_rejected(self):
        original = copy.deepcopy(self.raw)
        for length in ('0', '0.0000', '0.0', '', '0e0'):
            with self.subTest(length=length):
                raw = copy.deepcopy(original)
                for i, shape in enumerate(raw['packageDetail']['dataStr']['shape']):
                    if shape.startswith('PAD~'):
                        fields = shape.split('~')
                        fields[13] = length
                        raw['packageDetail']['dataStr']['shape'][i] = '~'.join(fields)
                self.assertTrue(self.exporter.export('C25804', raw).pcblib.is_file())
        for length, points in (('3.0', ''), ('0.0000', '1 2 3 4'), ('NaN', ''), ('unknown', '')):
            with self.subTest(length=length, points=points):
                raw = copy.deepcopy(original)
                shapes = raw['packageDetail']['dataStr']['shape']
                index = next(i for i, shape in enumerate(shapes) if shape.startswith('PAD~'))
                fields = shapes[index].split('~')
                fields[13], fields[14] = length, points
                shapes[index] = '~'.join(fields)
                with self.assertRaises(ConversionError):
                    self.exporter.export('C25804', raw)

    def test_ams1117_uses_physical_pin_numbers_and_defaults_blank_rotation_to_zero(self):
        raw = json.loads((FIXTURES / 'C12087.json').read_text(encoding='utf-8-sig'))
        original = copy.deepcopy(raw)
        result = self.exporter.export('C12087', raw)
        pins = {p.name: p for p in result.symbol.pins}
        self.assertEqual(pins['In'].number, '3')
        self.assertEqual(pins['Out'].number, '2')
        self.assertEqual(pins['GND'].number, '1')
        self.assertEqual(pins['TAB'].number, '4')
        self.assertEqual(pins['TAB'].orientation, 2)
        self.assertEqual(raw, original)


if __name__ == '__main__':
    unittest.main()
