from pathlib import Path
import tempfile
import unittest

from assistant.installations import load_altium, save_altium, file_version


class InstallationTests(unittest.TestCase):
    def test_selected_installation_survives_restart_and_missing_path_falls_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            executable=root/'AD20'/'X2.EXE'
            executable.parent.mkdir()
            executable.touch()
            config=root/'settings.json'
            save_altium(config,executable)
            self.assertEqual(load_altium(config,[]),executable)
            executable.unlink()
            fallback=root/'AD26'/'X2.EXE'
            fallback.parent.mkdir()
            fallback.touch()
            self.assertEqual(load_altium(config,[fallback]),fallback)

    def test_real_installation_version_is_read_without_launching_it(self):
        self.assertEqual(file_version(Path(r'E:\AD24\X2.EXE')),'24.0.1.36')
