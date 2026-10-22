import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from chc_runtime import distribution as dist


class DistributionTests(unittest.TestCase):
    def test_development_keeps_existing_paths_and_browser(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(dist, 'packaged', return_value=False):
            self.assertEqual(dist.data_root(), dist.CODE_ROOT)
            self.assertEqual(dist.bot_data_root('bls'), dist.CODE_ROOT / 'bots/bls')
            self.assertEqual(dist.chromium_options(), {})
            self.assertEqual(dist.daily_driver(), dist.CODE_ROOT / 'integrations/duas_source/drivers/msedgedriver.exe')

    def test_package_uses_user_data_without_creating_or_migrating_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            with patch.dict(os.environ, {'LOCALAPPDATA': str(local)}, clear=True), patch.object(dist, 'packaged', return_value=True):
                home = local / 'CHC Consultores/Workbench'
                self.assertEqual(dist.data_root(), home)
                for bot in ('detalles', 'duas_transito', 'talon', 'xmovimientos', 'manifiestos', 'bls'):
                    self.assertEqual(dist.bot_data_root(bot), home / 'bots' / bot)
                self.assertFalse(home.exists())
                self.assertEqual(dist.chromium_options(), {'channel': 'chromium'})
                self.assertEqual(dist.daily_driver(), dist.CODE_ROOT / '_runtime/selenium/chromedriver-win64/chromedriver.exe')

    def test_explicit_isolated_home_wins_and_all_modules_share_it(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'CHC_WORKBENCH_HOME': directory}), patch.object(dist, 'packaged', return_value=True):
                self.assertEqual(dist.data_root(), Path(directory).resolve())
                self.assertEqual(dist.bot_data_root('manifiestos'), Path(directory).resolve() / 'bots/manifiestos')


if __name__ == '__main__':
    unittest.main()
