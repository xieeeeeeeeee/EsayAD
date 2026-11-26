import json
from pathlib import Path
import tempfile
import unittest
import threading
from unittest.mock import patch

from assistant.bridge import Bridge, BridgeBusyError, pascal_string, read_receipt
from assistant.exporter import Exporter
from assistant.workflow import Selection


class BridgeTests(unittest.TestCase):
    def test_pascal_literal_cannot_inject_code_and_preserves_unicode(self):
        self.assertEqual(pascal_string("a'b"), "'a''b'")
        self.assertEqual(pascal_string('中文'), '#20013#25991')
        self.assertEqual(pascal_string('x\ny'), "'x'#10'y'")

    def test_prepares_unique_script_project_but_does_not_claim_placement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = json.loads((Path(__file__).parent / 'fixtures/C25804.json').read_text(encoding='utf-8'))['result']
            result = Exporter(root / 'libraries').export('C25804', raw)
            bridge = Bridge(root)
            project = bridge.prepare(result)
            self.assertTrue(project.exists())
            self.assertTrue(project.with_suffix('.pas').exists())
            request = json.loads((project.parent / 'request.json').read_text(encoding='utf-8'))
            self.assertEqual(request['state'], 'prepared')
            self.assertEqual(request['lcsc'], 'C25804')
            self.assertEqual(read_receipt(project), 'pending')
            (project.parent / 'cancelled.state').touch()
            self.assertEqual(read_receipt(project), 'cancelled')

    def test_receipts_do_not_open_files_while_ad_may_be_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / 'Import.PrjScr'
            (project.parent / 'opened.state').touch()
            (project.parent / 'placing.state').touch()
            with patch.object(Path, 'read_text', side_effect=PermissionError('writer holds file')):
                self.assertEqual(read_receipt(project), 'placing')
                (project.parent / 'placed.state').touch()
                self.assertEqual(read_receipt(project), 'placed')

    def test_duplicate_launch_is_blocked_across_bridge_instances_until_finished(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / 'X2.EXE'
            exe.touch()
            project = root / 'request1' / 'Import.PrjScr'
            project.parent.mkdir()
            project.touch()
            other = root / 'request2' / 'Import.PrjScr'
            other.parent.mkdir()
            other.touch()
            first, second = Bridge(root, exe), Bridge(root, exe)
            with patch('assistant.bridge.subprocess.Popen') as popen:
                first.launch(project)
                with self.assertRaises(BridgeBusyError):
                    second.launch(other)
                self.assertEqual(popen.call_count, 1)
                (project.parent / 'placed.state').touch()
                (project.parent / 'finished.state').touch()
                second.launch(other)
                self.assertEqual(popen.call_count, 2)

    def test_launch_failure_does_not_leave_a_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / 'X2.EXE'
            exe.touch()
            project = root / 'Import.PrjScr'
            project.touch()
            bridge = Bridge(root, exe)
            with patch('assistant.bridge.subprocess.Popen', side_effect=OSError('launch denied')):
                with self.assertRaises(OSError):
                    bridge.launch(project)
            self.assertIsNone(bridge.active_project())

    def test_other_instance_cannot_release_lock_while_submission_is_in_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / 'X2.EXE'
            exe.touch()
            project = root / 'Import.PrjScr'
            project.touch()
            entered, release = threading.Event(), threading.Event()
            errors = []
            def send(*args, **kwargs):
                entered.set()
                release.wait(3)
            def launch():
                try:
                    Bridge(root, exe).launch(project)
                except Exception as exc:
                    errors.append(exc)
            with patch('assistant.bridge.subprocess.Popen', side_effect=send):
                worker = threading.Thread(target=launch)
                worker.start()
                self.assertTrue(entered.wait(2))
                try:
                    with self.assertRaises(BridgeBusyError):
                        Bridge(root, exe).active_project()
                finally:
                    release.set()
                    worker.join(3)
            self.assertEqual(errors, [])
            self.assertEqual(Bridge(root, exe).active_project(), project)

    def test_bridge_rejects_foreign_library_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = json.loads((Path(__file__).parent / 'fixtures/C25804.json').read_text(encoding='utf-8'))['result']
            result = Exporter(root / 'external').export('C25804', raw)
            with self.assertRaises(ValueError):
                Bridge(root / 'other').prepare(result)

    def test_new_search_invalidates_stale_details_and_export(self):
        state = Selection()
        first = state.reset()
        self.assertTrue(state.accept(first, 'C25804', {'title': 'R'}))
        state.export = object()
        second = state.reset()
        self.assertIsNone(state.export)
        self.assertIsNone(state.raw)
        self.assertFalse(state.accept(first, 'C7593', {'title': 'IC'}))
        self.assertTrue(state.accept(second, 'C14663', {'title': 'C'}))


if __name__ == '__main__':
    unittest.main()
