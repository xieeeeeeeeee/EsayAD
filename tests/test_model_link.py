import json
from pathlib import Path
import struct
import tempfile
import unittest

import olefile
from assistant.exporter import Exporter


def records(blob):
    result, offset = [], 0
    while offset < len(blob):
        size = struct.unpack_from('<I', blob, offset)[0]
        length = size & 0xFFFFFF
        payload = blob[offset+4:offset+4+length]
        if size >> 24:
            result.append({})
        else:
            text = payload.rstrip(b'\0').decode('gbk', errors='replace')
            result.append(dict(p.split('=',1) for p in text.split('|') if '=' in p))
        offset += 4 + length
    return result


class ModelLinkTests(unittest.TestCase):
    def test_schlib_footprint_has_valid_parent_tree_and_existing_library(self):
        raw = json.loads((Path(__file__).parent / 'fixtures/C25804.json').read_text(encoding='utf-8'))['result']
        with tempfile.TemporaryDirectory() as temp:
            exported = Exporter(Path(temp)).export('C25804', raw)
            with olefile.OleFileIO(str(exported.schlib)) as library:
                data = records(library.openstream(['C25804','Data']).read())
            lists = [(i,r) for i,r in enumerate(data) if r.get('RECORD') == '44']
            self.assertEqual(len(lists), 1, 'model list is required for AD to discover the footprint')
            list_index, model_list = lists[0]
            self.assertEqual(model_list['OwnerIndex'], '0')
            model_index, model = next((i,r) for i,r in enumerate(data) if r.get('RECORD') == '45')
            self.assertEqual(int(model['OwnerIndex']), list_index)
            self.assertEqual(model['ModelName'], 'C25804_FP')
            self.assertEqual(model['ModelType'], 'PCBLIB')
            self.assertEqual(model['IsCurrent'], 'T')
            self.assertEqual(Path(model['ModelDatafile0']), exported.pcblib.resolve())
            for child in ('46', '48'):
                record = next(r for r in data if r.get('RECORD') == child)
                self.assertEqual(int(record['OwnerIndex']), model_index)
            with olefile.OleFileIO(model['ModelDatafile0']) as library:
                self.assertTrue(library.exists([model['ModelName'], 'Data']))
