"""Exercise partition reachability, including pod replacement and DNS access."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import json

spec = importlib.util.spec_from_file_location('partition', Path(__file__).resolve().parent.parent / 'scripts/partition.py')
partition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(partition)


def matches(selector, labels):
    if any(labels.get(k) != v for k, v in selector.get('matchLabels', {}).items()):
        return False
    for e in selector.get('matchExpressions', []):
        key, op = e['key'], e['operator']
        if op == 'Exists' and key not in labels:
            return False
        if op == 'In' and labels.get(key) not in e['values']:
            return False
        if op == 'NotIn' and labels.get(key) in e['values']:
            return False
    return True


def allowed(policies, source, target):
    def direction(labels, peer, kind, key):
        selected = [p['spec'] for p in policies if matches(p['spec']['podSelector'], labels)]
        # Unselected pods are unrestricted, as in Kubernetes NetworkPolicy.
        return not selected or any(
            matches(p['podSelector'], peer)
            for policy in selected for rule in policy[kind] for p in rule.get(key, [])
            if 'podSelector' in p and 'namespaceSelector' not in p
        )
    return direction(source, target, 'egress', 'to') and direction(target, source, 'ingress', 'from')


class PartitionTest(unittest.TestCase):
    def setUp(self):
        self.policies = partition.policies('us-west4-a')
        self.a = {partition.OWNER: partition.CLUSTER + '-fe', partition.ZONE: 'us-west4-a'}
        self.b = {partition.OWNER: partition.CLUSTER + '-fe', partition.ZONE: 'us-west4-b'}
        self.c = {partition.OWNER: partition.CLUSTER + '-fe', partition.ZONE: 'us-west4-c'}

    def test_minority_cannot_reach_majority_in_either_direction(self):
        for healthy in [self.b, self.c]:
            self.assertFalse(allowed(self.policies, self.a, healthy))
            self.assertFalse(allowed(self.policies, healthy, self.a))

    def test_majority_can_communicate(self):
        self.assertTrue(allowed(self.policies, self.b, self.c))
        self.assertTrue(allowed(self.policies, self.c, self.b))
        self.assertTrue(allowed(self.policies, self.a, self.a))

    def test_replacement_without_zone_label_cannot_escape(self):
        replacement = {partition.OWNER: partition.CLUSTER + '-be'}
        for side in [self.a, self.b, self.c]:
            self.assertFalse(allowed(self.policies, replacement, side))
            self.assertFalse(allowed(self.policies, side, replacement))

    def test_unrelated_pods_cannot_bypass_partition(self):
        unrelated = {partition.ZONE: 'us-west4-a'}
        self.assertFalse(allowed(self.policies, self.a, unrelated))
        self.assertFalse(allowed(self.policies, unrelated, self.a))

    def test_backend_owners_are_selected_with_the_frontends(self):
        backend = {partition.OWNER: partition.CLUSTER + '-be', partition.ZONE: 'us-west4-b'}
        self.assertTrue(allowed(self.policies, self.c, backend))
        self.assertFalse(allowed(self.policies, self.a, backend))
        self.assertFalse(allowed(self.policies, backend, self.a))

    def test_dns_exception_is_limited_to_cluster_dns(self):
        for labels in [self.a, self.b, self.c]:
            rules = [r for p in self.policies if matches(p['spec']['podSelector'], labels)
                     for r in p['spec']['egress'] if 'ports' in r]
            self.assertEqual(len(rules), 1)
            self.assertEqual({p['port'] for p in rules[0]['ports']}, {53})
            peer = rules[0]['to'][0]
            self.assertTrue(matches(peer['namespaceSelector'], {'kubernetes.io/metadata.name': 'kube-system'}))
            self.assertFalse(matches(peer['namespaceSelector'], {'kubernetes.io/metadata.name': 'other'}))
            self.assertTrue(matches(peer['podSelector'], {'k8s-app': 'kube-dns'}))
            self.assertTrue(matches(peer['podSelector'], {'k8s-app': 'node-local-dns'}))
            self.assertFalse(matches(peer['podSelector'], {'k8s-app': 'other'}))

    def test_node_local_dns_is_scoped_to_the_resolver_and_dns_ports(self):
        policies = partition.policies('us-west4-a', '169.254.20.10')
        dns = policies[0]['spec']['egress'][0]
        self.assertIn({'ipBlock': {'cidr': '169.254.20.10/32'}}, dns['to'])
        self.assertEqual(dns['ports'], [{'protocol': 'UDP', 'port': 53}, {'protocol': 'TCP', 'port': 53}])
        self.assertFalse(allowed(policies, self.a, self.b))

    def test_failed_reset_is_rejected_even_when_kubectl_attached_successfully(self):
        response = {'status': {'ephemeralContainerStatuses': [
            {'name': 'reset', 'state': {'terminated': {'exitCode': 1}}}
        ]}}
        with patch.object(partition, 'kubectl', return_value=SimpleNamespace(stdout=json.dumps(response))):
            with self.assertRaises(RuntimeError):
                partition.check_debug_exit('fe-0', 'reset')

    def test_successful_reset_requires_a_confirmed_zero_exit_status(self):
        response = {'status': {'ephemeralContainerStatuses': [
            {'name': 'reset', 'state': {'terminated': {'exitCode': 0}}}
        ]}}
        with patch.object(partition, 'kubectl', return_value=SimpleNamespace(stdout=json.dumps(response))):
            partition.check_debug_exit('fe-0', 'reset')


if __name__ == '__main__':
    unittest.main()
