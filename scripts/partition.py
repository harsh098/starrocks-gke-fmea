#!/usr/bin/env python3
"""Partition the lab's StarRocks pods by zone. Requires Python 3.9+ and kubectl."""
import argparse
import ipaddress
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
NAMESPACE = "starrocks"
OWNER = "app.starrocks.ownerreference/name"
CLUSTER = "starrocks-fmea"
ZONE = "fmea.starrocks.io/zone"
TAG = {"fmea.starrocks.io/experiment": "partition"}
SELECTOR = f"{OWNER}={CLUSTER}"


def kubectl(*args, data=None, check=True):
    return subprocess.run(
        ["kubectl", "-n", NAMESPACE, *args],
        input=json.dumps(data) if data is not None else None,
        text=True, check=check, capture_output=True, timeout=180,
    )


def pods():
    return json.loads(kubectl("get", "pods", "-l", SELECTOR, "-o", "json").stdout)["items"]


def policies(zone, dns_ip=None):
    def group(isolated):
        expressions = [{"key": ZONE, "operator": "Exists"}]
        expressions.append({"key": ZONE, "operator": "In" if isolated else "NotIn", "values": [zone]})
        return {"matchLabels": {OWNER: CLUSTER}, "matchExpressions": expressions}

    def policy(name, selector, ingress, egress):
        return {
            "apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
            "metadata": {"name": name, "namespace": NAMESPACE, "labels": TAG},
            "spec": {"podSelector": selector, "policyTypes": ["Ingress", "Egress"],
                     "ingress": ingress, "egress": egress},
        }

    # Select every lab pod, including newly recreated pods that lack a zone label.
    # Those replacements remain blocked until the experiment is stopped.
    dns = {"to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}},
                   "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}}}],
           "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}]}
    if dns_ip is not None:
        resolver = ipaddress.ip_address(dns_ip)
        dns['to'].append({'ipBlock': {'cidr': f'{resolver}/{resolver.max_prefixlen}'}})
    result = [policy("fmea-partition-default", {"matchLabels": {OWNER: CLUSTER}}, [], [dns])]
    for isolated, name in [(True, "isolated"), (False, "majority")]:
        peer = {"podSelector": group(isolated)}
        result.append(policy(f"fmea-partition-{name}", group(isolated), [{"from": [peer]}], [{"to": [peer]}]))
    return result


def stop():
    print(kubectl("delete", "networkpolicy", "-l", "fmea.starrocks.io/experiment=partition", "--ignore-not-found").stdout)
    kubectl("label", "pods", "-l", SELECTOR, f"{ZONE}-", check=False)
    (ROOT / ".local/partition.json").unlink(missing_ok=True)
    print("Partition policies and temporary labels removed. Check database membership and replica recovery.")


def check_debug_exit(pod, container):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status = json.loads(kubectl('get', 'pod', pod, '-o', 'json').stdout)['status']
        for item in status.get('ephemeralContainerStatuses', []):
            if item['name'] == container and 'terminated' in item.get('state', {}):
                code = item['state']['terminated']['exitCode']
                if code != 0:
                    raise RuntimeError(f'TCP reset container {container} in {pod} exited with {code}. Inspect its logs; policies remain applied.')
                return
        time.sleep(1)
    raise RuntimeError(f'TCP reset completion could not be verified in {pod}. Policies remain applied.')


def start(zone):
    existing = json.loads(kubectl("get", "networkpolicy", "-o", "json").stdout)["items"]
    if existing:
        raise RuntimeError("The lab namespace already has NetworkPolicies. Stop the current experiment or remove the conflicting lab policies first.")
    members = pods()
    if len(members) != 6:
        raise RuntimeError("Expected six FE/BE pods before partitioning.")
    for component in ['fe', 'be']:
        group = [p for p in members if p['metadata']['labels'].get('app.kubernetes.io/component') == component]
        if len(group) != 3 or not all(any(c['type'] == 'Ready' and c['status'] == 'True'
                                          for c in p['status'].get('conditions', [])) for p in group):
            raise RuntimeError(f'Expected three Ready {component} pods before partitioning.')
    zones = set()
    for pod in members:
        node = pod["spec"].get("nodeName")
        if not node or not pod["status"].get("podIP"):
            raise RuntimeError("All six pods must be scheduled and have IP addresses.")
        node_info = json.loads(kubectl("get", "node", node, "-o", "json").stdout)
        pod_zone = node_info["metadata"]["labels"]["topology.kubernetes.io/zone"]
        zones.add(pod_zone)
        pod["lab_zone"] = pod_zone
    if zone not in zones or len(zones) != 3:
        raise RuntimeError(f"Choose one of the three populated zones: {sorted(zones)}")
    for component in ['fe', 'be']:
        if len({p['lab_zone'] for p in members if p['metadata']['labels'].get('app.kubernetes.io/component') == component}) != 3:
            raise RuntimeError(f'Expected one {component} in each of three zones.')
    fe = next(p for p in members if p['metadata']['labels'].get('app.kubernetes.io/component') == 'fe')
    resolv = kubectl('exec', fe['metadata']['name'], '-c', 'fe', '--', 'cat', '/etc/resolv.conf').stdout
    resolvers = [line.split()[1] for line in resolv.splitlines() if line.startswith('nameserver')]
    if not resolvers:
        raise RuntimeError('Could not determine the pod DNS resolver.')
    for pod in members:
        kubectl("label", "pod", pod["metadata"]["name"], f"{ZONE}={pod['lab_zone']}", "--overwrite")
    kubectl("apply", "-f", "-", data={"apiVersion": "v1", "kind": "List", "items": policies(zone, resolvers[0])})
    (ROOT / ".local").mkdir(exist_ok=True)
    (ROOT / ".local/partition.json").write_text(json.dumps({"zone": zone}))
    # NetworkPolicy handling of existing connections varies. Reset them explicitly.
    # This adds a TCP-reset fault to the link-omission experiment; record that fact.
    for pod in members:
        opposite = [str(ipaddress.ip_address(p["status"]["podIP"])) for p in members
                    if (p["lab_zone"] == zone) != (pod["lab_zone"] == zone)]
        command = "set -eu; " + "; ".join(f"ss --kill state established dst {ip}" for ip in opposite)
        container = 'fmea-reset-' + uuid.uuid4().hex[:8]
        print(f"Resetting cross-zone connections in {pod['metadata']['name']}", flush=True)
        result = kubectl("debug", pod["metadata"]["name"], "--quiet", "--attach=true",
                         f'--container={container}', "--image=nicolaka/netshoot:v0.14", "--profile=netadmin", "--", "sh", "-c", command,
                         check=False)
        if result.returncode:
            raise RuntimeError(f"TCP reset failed: {result.stderr}\nPolicies remain applied. Run partition.py stop to recover.")
        # kubectl attach/debug success alone does not establish the command's exit status.
        check_debug_exit(pod['metadata']['name'], container)
    verify()


def verify():
    state = json.loads((ROOT / ".local/partition.json").read_text())
    zone = state["zone"]
    members = pods()
    fes = [p for p in members if p["metadata"]["labels"].get("app.kubernetes.io/component") == "fe"]
    if len(fes) != 3 or any(ZONE not in p["metadata"]["labels"] for p in members):
        raise RuntimeError("Pod membership changed. Recreated pods are blocked by the default policy. Stop the partition, restore health, and start again.")
    # Probe new TCP connections between every FE pair, in both directions.
    for source in fes:
        for target in fes:
            if source is target:
                continue
            same_side = ((source["metadata"]["labels"][ZONE] == zone) ==
                         (target["metadata"]["labels"][ZONE] == zone))
            ip = str(ipaddress.ip_address(target["status"]["podIP"]))
            result = kubectl("exec", source["metadata"]["name"], "-c", "fe", "--",
                             "timeout", "5", "bash", "-c", f"exec 3<>/dev/tcp/{ip}/9010", check=False)
            if same_side and result.returncode != 0:
                raise RuntimeError("An expected same-side FE connection failed. Inspect pod health and policy enforcement.")
            if not same_side and result.returncode != 124:
                raise RuntimeError(f"Expected a blocked cross-zone FE connection to time out; got {result.returncode}. Inspect connectivity before interpreting database behavior.")
    print("PASS: new FE TCP connections work within the majority and time out across the partition.")
    print("Now check FE quorum, BE health, and writes from each side. Run partition.py stop to recover.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "verify", "status", "stop"])
    parser.add_argument("zone", nargs="?")
    args = parser.parse_args()
    subprocess.run(["bash", "-c", 'source "$1"; lab_context', "bash", str(ROOT / "scripts/common.sh")], check=True)
    if args.action == "start":
        if not args.zone:
            parser.error("start requires a zone")
        start(args.zone)
    elif args.action == "verify":
        verify()
    elif args.action == "stop":
        stop()
    else:
        print(kubectl("get", "pods", "-l", SELECTOR, "-L", ZONE, "-o", "wide").stdout)
        print(kubectl("get", "networkpolicy", "-l", "fmea.starrocks.io/experiment=partition").stdout)


if __name__ == "__main__":
    try:
        main()
    except (subprocess.SubprocessError, RuntimeError, OSError, KeyError) as exc:
        print(f"Partition experiment failed: {exc}", file=sys.stderr)
        print("If policies were applied, run ./scripts/partition.py stop before continuing.", file=sys.stderr)
        sys.exit(1)
