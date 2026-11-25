"""Check smoke-test diagnostics without a running Kubernetes cluster."""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = (Path(__file__).resolve().parents[1] / 'scripts/smoke-test.sh').read_text()
POD_CHECK = re.findall(r"python3 -c '\n(.*?)\n'", SCRIPT, re.S)[1]


def pods():
    return [
        {
            'metadata': {'labels': {'app.kubernetes.io/component': component}},
            'spec': {'nodeName': f'worker-{index}'},
            'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]},
        }
        for component in ('fe', 'be')
        for index in range(3)
    ]


class SmokeDiagnosticsTests(unittest.TestCase):
    def check_pods(self, items, expected_message=None):
        # The checks must work with assertions disabled, too.
        result = subprocess.run(
            [sys.executable, '-O', '-c', POD_CHECK],
            input=json.dumps({'items': items}), text=True, capture_output=True,
        )
        if expected_message:
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr.strip(), 'FAIL: ' + expected_message)
            self.assertNotIn('Traceback', result.stderr)
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('PASS:', result.stdout)

    def test_ready_pods_pass(self):
        self.check_pods(pods())

    def test_recovering_fe_reports_readiness_failure(self):
        items = pods()
        items[0]['status']['conditions'][0]['status'] = 'False'
        self.check_pods(items, 'fe pods are not all Ready')

    def test_recovering_be_reports_readiness_failure(self):
        items = pods()
        items[3]['status']['conditions'] = []
        self.check_pods(items, 'be pods are not all Ready')

    def test_pending_pod_reports_scheduling_failure(self):
        items = pods()
        items[0]['spec'] = {}
        self.check_pods(items, 'fe pods are not all scheduled')

    def test_missing_pod_reports_count_failure(self):
        self.check_pods(pods()[1:], 'Expected three fe pods')

    def test_colocated_pods_report_placement_failure(self):
        items = pods()
        items[0]['spec']['nodeName'] = 'worker-1'
        self.check_pods(items, 'fe pods must use distinct workers')
