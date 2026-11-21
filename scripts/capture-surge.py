#!/usr/bin/env python3
"""Capture a manually triggered GKE surge run; never changes nodes or FE metadata.

Writes only to a new, explicitly named SQL probe database and local evidence files.
Stop with SIGINT or an output/STOP file. Evidence can contain infrastructure names;
keep it private. Uses the lab context guard before doing any work.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
NS = "starrocks"
CLUSTER = "starrocks-fmea"
SELECTOR = f"app.starrocks.ownerreference/name in ({CLUSTER}-fe,{CLUSTER}-be)"
FAILURE = re.compile(r"Ids: \d+ were equal|UNEXPECTED_STATE|LogIntegrityException|ChecksumException")


def run(argv, timeout=25, input_text=None):
    started = datetime.now(timezone.utc).isoformat()
    try:
        p = subprocess.run(argv, text=True, input=input_text, capture_output=True, timeout=timeout)
        return {"started": started, "code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    except subprocess.TimeoutExpired as e:
        def decode(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
        return {"started": started, "code": 124, "stdout": decode(e.stdout), "stderr": decode(e.stderr) + "\nCAPTURE TIMEOUT; SQL outcome may be unknown"}


def kube(*args):
    return run(["kubectl", "--request-timeout=15s", *args])


def sql(pod, statement):
    return kube("-n", NS, "exec", pod, "-c", "fe", "--", "mysql",
                "--connect-timeout=5", "--batch", "--host=127.0.0.1", "--port=9030",
                "--user=root", "-e", statement)


def je_group(pod):
    helpers = " ".join(f"{CLUSTER}-fe-{i}.{CLUSTER}-fe-search.{NS}.svc.cluster.local" for i in range(3))
    command = ('d=$(mktemp -d /tmp/je-readonly.XXXXXX); '
               'trap \'rm -rf "$d"\' EXIT; cat > "$d/ReadJeGroup.java"; '
               'java -Xms16m -Xmx64m --class-path '
               '/opt/starrocks/fe/lib/starrocks-bdb-je-18.3.20.jar '
               '"$d/ReadJeGroup.java" ' + helpers)
    return run(["kubectl", "--request-timeout=15s", "-n", NS, "exec", "-i", pod,
                "-c", "fe", "--", "sh", "-c", command],
               input_text=(ROOT / "experiments/ReadJeGroup.java").read_text())


def save(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe-database", required=True, help="Must be a NEW database beginning fmea_surge_")
    parser.add_argument("--duration", type=int, default=3600)
    args = parser.parse_args()
    if not re.fullmatch(r"fmea_surge_[a-z0-9_]+", args.probe_database):
        parser.error("Use a new database named fmea_surge_<run_name>")
    os.environ.setdefault("KUBECONFIG", str(ROOT / ".local/kubeconfig"))
    guard = run(["bash", "-c", 'source "$1"; lab_context', "capture-surge", str(ROOT / "scripts/common.sh")])
    if guard["code"]:
        raise SystemExit(guard["stderr"])
    args.output.mkdir(parents=True, exist_ok=False)
    os.chmod(args.output, 0o700)
    db = args.probe_database
    initial = sql(f"{CLUSTER}-fe-0", f"CREATE DATABASE {db}; CREATE TABLE {db}.writes (id BIGINT NOT NULL, payload VARCHAR(64)) DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 1 PROPERTIES ('replication_num'='3');")
    save(args.output / "setup.json", initial)
    if initial["code"]:
        raise SystemExit("Probe setup failed. See setup.json; no upgrade started by this script.")
    save(args.output / "statefulsets-before.json", kube("-n", NS, "get", "statefulsets", "-o", "json"))
    started = time.monotonic()
    start_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save(args.output / "run.json", {"started": start_utc, "probe_database": db})
    stop = False
    def request_stop(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    acknowledged = []
    iteration = 0
    with ThreadPoolExecutor(max_workers=12) as pool:
        while not stop and not (args.output / "STOP").exists() and time.monotonic() - started < args.duration:
            iteration += 1
            snapshot = args.output / f"{iteration:04d}"
            snapshot.mkdir()
            tasks = {
                "pods": lambda: kube("-n", NS, "get", "pods", "-l", SELECTOR, "-o", "json"),
                "nodes": lambda: kube("get", "nodes", "-l", "starrocks-lab=true", "-o", "json"),
                "volumes": lambda: kube("-n", NS, "get", "pvc", "-o", "json"),
                "pvs": lambda: kube("get", "pv", "-o", "json"),
                "attachments": lambda: kube("get", "volumeattachments", "-o", "json"),
                "events": lambda: kube("-n", NS, "get", "events", "-o", "json"),
            }
            for ordinal in range(3):
                pod = f"{CLUSTER}-fe-{ordinal}"
                tasks[f"fe-{ordinal}-logs"] = lambda p=pod: kube("-n", NS, "logs", p, "-c", "fe", "--timestamps", f"--since-time={start_utc}")
                tasks[f"fe-{ordinal}-previous"] = lambda p=pod: kube("-n", NS, "logs", p, "-c", "fe", "--previous", "--timestamps", f"--since-time={start_utc}")
                tasks[f"fe-{ordinal}-identity"] = lambda p=pod: kube("-n", NS, "exec", p, "-c", "fe", "--", "sh", "-c", "cat /opt/starrocks/fe/meta/image/ROLE; ls -l /opt/starrocks/fe/meta/bdb; tail -n 100 /opt/starrocks/fe/meta/bdb/je.info.0 2>/dev/null")
                tasks[f"fe-{ordinal}-membership"] = lambda p=pod: sql(p, "SHOW FRONTENDS; SHOW BACKENDS;")
                tasks[f"fe-{ordinal}-je-group"] = lambda p=pod: je_group(p)
            futures = {key: pool.submit(fn) for key, fn in tasks.items()}
            for key, future in futures.items():
                result = future.result()
                save(snapshot / f"{key}.json", result)
                if key.endswith(("logs", "previous", "identity", "je-group")) and FAILURE.search(result["stdout"] + result["stderr"]):
                    (args.output / "IDENTITY_OR_INTEGRITY_FAILURE").write_text(str(snapshot / f"{key}.json") + "\n")
            pods_result = futures["pods"].result()
            ready = []
            if pods_result["code"] == 0:
                for pod in json.loads(pods_result["stdout"])["items"]:
                    if "-fe-" in pod["metadata"]["name"] and not pod["metadata"].get("deletionTimestamp") and any(c["type"] == "Ready" and c["status"] == "True" for c in pod["status"].get("conditions", [])):
                        ready.append(pod["metadata"]["name"])
            if ready and not stop and not (args.output / "STOP").exists():
                client = sorted(ready)[iteration % len(ready)]
                insert = sql(client, f"INSERT INTO {db}.writes VALUES ({iteration}, 'surge-{iteration}');")
                save(snapshot / "insert.json", {"client_pod": client, "id": iteration, **insert})
                if insert["code"] == 0:
                    acknowledged.append(iteration)
                save(snapshot / "read.json", sql(client, f"SELECT COUNT(*) AS row_count FROM {db}.writes WHERE id={iteration};"))
                if iteration % 3 == 0:
                    save(snapshot / "ddl.json", sql(client, f"CREATE TABLE {db}.ddl_{iteration} (id BIGINT) DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 1 PROPERTIES ('replication_num'='3'); DROP TABLE {db}.ddl_{iteration};"))
            save(args.output / "acknowledged.json", acknowledged)
            print(json.dumps({"iteration": iteration, "ready_clients": len(ready), "acknowledged": len(acknowledged), "identity_failure": (args.output / "IDENTITY_OR_INTEGRITY_FAILURE").exists()}), flush=True)
            if (args.output / "IDENTITY_OR_INTEGRITY_FAILURE").exists():
                print("Failure captured; stop cloud upgrade progression and preserve evidence before recovery.", flush=True)
                break
            for _ in range(15):
                if stop or (args.output / "STOP").exists():
                    break
                time.sleep(1)
    save(args.output / "finished.json", {"finished": datetime.now(timezone.utc).isoformat(), "iterations": iteration, "acknowledged": acknowledged})


if __name__ == "__main__":
    main()
