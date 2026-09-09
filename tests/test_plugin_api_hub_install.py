from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_PATH = REPO_ROOT / "dashboard" / "plugin_api.py"


def load_api_module():
    spec = importlib.util.spec_from_file_location("aiianer_plugin_api_test", API_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HubRootInstallTest(unittest.TestCase):
    def test_installs_root_hybrid_plugin_to_agent_and_desktop_targets(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded-repo"
            hermes_home = root / "hermes-home"
            (source / "dashboard" / "dist").mkdir(parents=True)
            (source / "desktop").mkdir()
            (source / "guard").mkdir()
            (source / "plugin.yaml").write_text("name: aiianer-hub\nversion: 9.9.9\n")
            (source / "__init__.py").write_text("def register(ctx): pass\n")
            (source / "catalog.json").write_text('{"components": []}\n')
            (source / "guard_check.py").write_text("# guard\n")
            (source / "dashboard" / "manifest.json").write_text('{"name": "aiianer-hub"}\n')
            (source / "dashboard" / "plugin_api.py").write_text("# backend\n")
            (source / "dashboard" / "dist" / "index.js").write_text("// dashboard\n")
            (source / "desktop" / "plugin.js").write_text("// desktop\n")
            (source / "guard" / "HOOK.yaml").write_text("name: guard\n")
            (source / "guard" / "handler.py").write_text("# hook\n")

            api.HERMES_HOME = hermes_home
            api.PLUGINS = hermes_home / "plugins"
            api.STATE_DIR = hermes_home / "aiianer"

            legacy_desktop = hermes_home / "desktop-plugins" / "aiianer-hermes-extensions"
            legacy_desktop.mkdir(parents=True)
            (legacy_desktop / "plugin.js").write_text("// stale desktop\n")

            api._install_hub_from_root(source)

            self.assertEqual(
                (hermes_home / "plugins" / "aiianer-hub" / "plugin.yaml").read_text(),
                "name: aiianer-hub\nversion: 9.9.9\n",
            )
            self.assertTrue((hermes_home / "plugins" / "aiianer-hub" / "dashboard" / "plugin_api.py").is_file())
            expected_desktop = (source / "desktop" / "plugin.js").read_text()
            self.assertEqual(
                (hermes_home / "plugins" / "aiianer-hub" / "desktop" / "plugin.js").read_text(),
                expected_desktop,
            )
            self.assertFalse(legacy_desktop.exists())
            self.assertFalse((hermes_home / "plugins" / "aiianer-hub" / "desktop" / "plugin.js.neu").exists())
            self.assertTrue((hermes_home / "hooks" / "aiianer-guard" / "handler.py").is_file())


if __name__ == "__main__":
    unittest.main()
