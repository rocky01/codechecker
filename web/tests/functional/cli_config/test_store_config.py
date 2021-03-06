#
# -----------------------------------------------------------------------------
#                     The CodeChecker Infrastructure
#   This file is distributed under the University of Illinois Open Source
#   License. See LICENSE.TXT for details.
# -----------------------------------------------------------------------------

"""
Test store configuration file.
"""


import json
import os
import subprocess
import unittest

from libtest import env


class TestStoreConfig(unittest.TestCase):
    _ccClient = None

    def setUp(self):

        # TEST_WORKSPACE is automatically set by test package __init__.py .
        self.test_workspace = os.environ['TEST_WORKSPACE']
        self.codechecker_cfg = env.import_codechecker_cfg(self.test_workspace)

        test_class = self.__class__.__name__
        print('Running ' + test_class + ' tests in ' + self.test_workspace)

        # Get the CodeChecker cmd if needed for the tests.
        self._codechecker_cmd = env.codechecker_cmd()

        self.config_file = os.path.join(self.test_workspace,
                                        "codechecker.json")

        # Create an empty report directory which will be used to check store
        # command.
        if not os.path.exists(self.codechecker_cfg['reportdir']):
            os.mkdir(self.codechecker_cfg['reportdir'])

    def test_valid_config(self):
        """ Store with a valid configuration file. """
        with open(self.config_file, 'w+',
                  encoding="utf-8", errors="ignore") as config_f:
            json.dump({
                'store': [
                    '--name=' + 'store_config',
                    '--url=' + env.parts_to_url(self.codechecker_cfg),
                    self.codechecker_cfg['reportdir']]}, config_f)

        store_cmd = [env.codechecker_cmd(), 'store', '--config',
                     self.config_file]

        subprocess.check_output(
            store_cmd, encoding="utf-8", errors="ignore")

    def test_invalid_config(self):
        """ Store with an invalid configuration file. """
        with open(self.config_file, 'w+',
                  encoding="utf-8", errors="ignore") as config_f:
            json.dump({
                'store': ['--dummy-option']}, config_f)

        store_cmd = [env.codechecker_cmd(), 'store',
                     '--name', 'store_config',
                     '--config', self.config_file,
                     '--url', env.parts_to_url(self.codechecker_cfg),
                     self.codechecker_cfg['reportdir']]

        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.check_output(
                store_cmd, encoding="utf-8", errors="ignore")

    def test_empty_config(self):
        """ Store with an empty configuration file. """
        with open(self.config_file, 'w+',
                  encoding="utf-8", errors="ignore") as config_f:
            config_f.write("")

        store_cmd = [env.codechecker_cmd(), 'store',
                     '--name', 'store_config',
                     '--config', self.config_file,
                     '--url', env.parts_to_url(self.codechecker_cfg),
                     self.codechecker_cfg['reportdir']]

        subprocess.check_output(
            store_cmd, encoding="utf-8", errors="ignore")
