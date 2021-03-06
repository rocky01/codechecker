# -----------------------------------------------------------------------------
#                     The CodeChecker Infrastructure
#   This file is distributed under the University of Illinois Open Source
#   License. See LICENSE.TXT for details.
# -----------------------------------------------------------------------------
"""
Test source-code level suppression data writing to suppress file.
"""


import logging
import os
import shlex
import sys
import subprocess
from subprocess import CalledProcessError
import unittest

from codechecker_api.codeCheckerDBAccess_v6.ttypes import ReviewStatus

from libtest import env
from libtest import codechecker
from libtest.thrift_client_to_db import get_all_run_results


def call_cmd(command, cwd, env):
    try:
        print(' '.join(command))
        proc = subprocess.Popen(
            shlex.split(' '.join(command)),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env, encoding="utf-8", errors="ignore")
        out, err = proc.communicate()
        print(out)
        print(err)
        return proc.returncode
    except CalledProcessError as cerr:
        print("Failed to call:\n" + ' '.join(cerr.cmd))
        return cerr.returncode


class TestSuppress(unittest.TestCase):
    """
    Test source-code level suppression data writing to suppress file.
    """

    def setUp(self):
        self._test_workspace = os.environ['TEST_WORKSPACE']

        self._testproject_data = env.setup_test_proj_cfg(self._test_workspace)
        self.assertIsNotNone(self._testproject_data)

        self._test_project_path = self._testproject_data['project_path']

        self._cc_client = env.setup_viewer_client(self._test_workspace)
        self.assertIsNotNone(self._cc_client)

        # Get the run names which belong to this test
        run_names = env.get_run_names(self._test_workspace)

        runs = self._cc_client.getRunData(None, None, 0, None)

        test_runs = [run for run in runs if run.name in run_names]

        self.assertEqual(len(test_runs), 1,
                         'There should be only one run for this test.')
        self._runid = test_runs[0].runId
        self._run_name = test_runs[0].name

    def test_suppress_import(self):
        """
        Test the suppress file importing.
        """

        generated_file = os.path.join(self._test_workspace,
                                      "generated.suppress")

        extract_cmd = ['CodeChecker', 'parse',
                       os.path.join(self._test_workspace, "reports"),
                       "--suppress", generated_file,
                       "--export-source-suppress"
                       ]

        ret = call_cmd(extract_cmd,
                       self._test_project_path,
                       env.test_env(self._test_workspace))
        self.assertEqual(ret, 0, "Failed to generate suppress file.")

        codechecker_cfg = env.import_test_cfg(
            self._test_workspace)['codechecker_cfg']

        product_url = env.parts_to_url(codechecker_cfg)
        import_cmd = ['CodeChecker', 'cmd', 'suppress', '-i', generated_file,
                      '--url', product_url, self._run_name]

        print(import_cmd)
        ret = call_cmd(import_cmd,
                       self._test_project_path,
                       env.test_env(self._test_workspace))
        self.assertEqual(ret, 0, "Failed to import suppress file.")

    def test_suppress_comment_in_db(self):
        """
        Exported source suppress comment stored as a review status in the db.
        """
        runid = self._runid
        logging.debug("Get all run results from the db for runid: " +
                      str(runid))

        hash_to_suppress_msgs = {}
        with open(os.path.join(self._test_project_path, "suppress.expected"),
                  'r', encoding="utf-8", errors="ignore") as expected:
            for line in expected:
                src_code_info = line.strip().split('||')

                status = None
                if len(src_code_info) == 4:
                    # Newest source code comment format where status is given.
                    bug_hash, _, msg, status = src_code_info
                elif len(src_code_info) == 3:
                    # Old format where review status is not given.
                    bug_hash, _, msg = src_code_info
                else:
                    # Oldest source code comment format where status and file
                    # name are not given.
                    bug_hash, msg = src_code_info

                rw_status = ReviewStatus.FALSE_POSITIVE
                if status == 'confirmed':
                    rw_status = ReviewStatus.CONFIRMED
                elif status == 'intentional':
                    rw_status = ReviewStatus.INTENTIONAL

                hash_to_suppress_msgs[bug_hash] = {'message': msg,
                                                   'status': rw_status}

        run_results = get_all_run_results(self._cc_client, runid)
        self.assertIsNotNone(run_results)
        self.assertNotEqual(len(run_results), 0)

        for bug_hash in hash_to_suppress_msgs:
            expected = hash_to_suppress_msgs[bug_hash]
            report = [x for x in run_results if x.bugHash == bug_hash][0]

            # Check the stored suppress comment
            self.assertEqual(report.reviewData.comment, expected['message'])
            self.assertEqual(report.reviewData.status, expected['status'])

            # Change review status to confirmed bug.
            review_comment = "This is really a bug"
            status = ReviewStatus.CONFIRMED
            success = self._cc_client.changeReviewStatus(
                report.reportId, status, review_comment)

            self.assertTrue(success)
            logging.debug("Bug review status changed successfully")

        # Get the results to compare.
        updated_results = get_all_run_results(self._cc_client, self._runid)
        self.assertIsNotNone(updated_results)
        self.assertNotEqual(len(updated_results), 0)

        for bug_hash in hash_to_suppress_msgs:
            report = [x for x in updated_results if x.bugHash == bug_hash][0]

            # Check the stored suppress comment
            self.assertEqual(report.reviewData.comment, "This is really a bug")
            self.assertEqual(report.reviewData.status, ReviewStatus.CONFIRMED)

        # Check the same project again.
        codechecker_cfg = env.import_test_cfg(
            self._test_workspace)['codechecker_cfg']

        initial_test_project_name = self._run_name

        ret = codechecker.check_and_store(codechecker_cfg,
                                          initial_test_project_name,
                                          self._test_project_path)
        if ret:
            sys.exit(1)

        # Get the results to compare.
        updated_results = get_all_run_results(self._cc_client, self._runid)
        self.assertIsNotNone(updated_results)
        self.assertNotEqual(len(updated_results), 0)

        for bug_hash in hash_to_suppress_msgs:
            expected = hash_to_suppress_msgs[bug_hash]
            report = [x for x in updated_results if x.bugHash == bug_hash][0]

            # Check that source code comments in the database are changed back
            # after storage.
            self.assertEqual(report.reviewData.comment, expected['message'])
            self.assertEqual(report.reviewData.status, expected['status'])
