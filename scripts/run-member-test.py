#!/usr/bin/env python3
"""Run one member-outage test and print only the evidence needed to follow it."""

import argparse
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('test', choices=['FE-1', 'FE-2', 'BE-1'])
    args = parser.parse_args()
    os.chdir(ROOT)
    os.environ.setdefault('KUBECONFIG', str(ROOT / '.local/kubeconfig'))
    run_id = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + uuid.uuid4().hex[:6]
    evidence = ROOT / '.local/runs' / run_id
    evidence.mkdir(parents=True, mode=0o700)
    sequence = 0

    def run(command, timeout=40, check=True, env=None):
        nonlocal sequence
        sequence += 1
        result = subprocess.run(command, text=True, capture_output=True,
                                timeout=timeout, env=env)
        (evidence / f'{sequence:03}.json').write_text(json.dumps({
            'command': command, 'time': time.strftime('%FT%TZ', time.gmtime()),
            'returncode': result.returncode, 'stdout': result.stdout,
            'stderr': result.stderr,
        }, indent=2))
        if check and result.returncode:
            raise RuntimeError(f'Command failed with exit {result.returncode}. See private evidence {sequence:03}.json.')
        return result

    def sql(statement, fe, check=True):
        env = dict(os.environ, SR_FE_POD=fe)
        return run(['./scripts/sql.sh', '--batch', '-e', statement], env=env, check=check)

    def members(fe, kind):
        statement = 'SHOW FRONTENDS;' if kind == 'fe' else 'SHOW BACKENDS;'
        result = sql(statement, fe, check=False)
        if result.returncode:
            return []
        return list(csv.DictReader(io.StringIO(result.stdout), delimiter='\t'))

    def wait_for(description, condition, seconds=600):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(5)
        raise RuntimeError(f'Timed out waiting for {description}.')

    print(f'{args.test} — started {run_id}', flush=True)
    run(['bash', '-c', 'source scripts/common.sh; lab_context'])
    run(['./scripts/smoke-test.sh'], timeout=90)
    print('Baseline: 3 alive FEs, 3 alive BEs, 12 healthy tablet replicas.', flush=True)
    frontends = members('starrocks-fmea-fe-0', 'fe')
    role = 'LEADER' if args.test == 'FE-2' else 'FOLLOWER'
    target = next(row['Name'].split('.')[0] for row in frontends if row['Role'] == role)
    kind = 'be' if args.test == 'BE-1' else 'fe'
    if kind == 'be':
        target = 'starrocks-fmea-be-0'
    survivor = next(row['Name'].split('.')[0] for row in frontends
                    if row['Name'].split('.')[0] != target)

    def pod():
        return json.loads(run(['kubectl', '-n', 'starrocks', 'get', 'pod', target, '-o', 'json']).stdout)

    original = pod()
    worker = original['spec']['nodeName']

    def claims(value):
        return sorted(v['persistentVolumeClaim']['claimName'] for v in value['spec']['volumes']
                      if 'persistentVolumeClaim' in v)

    cordoned = False
    verdict = 'INCONCLUSIVE'
    try:
        cordoned = True
        run(['kubectl', 'cordon', worker])
        run(['kubectl', '-n', 'starrocks', 'delete', 'pod', target,
             '--grace-period=0', '--force', '--wait=false'])

        def down():
            field = 'IP' if kind == 'be' else 'Name'
            return any(row[field].split('.')[0] == target and row['Alive'].lower() == 'false'
                       for row in members(survivor, kind))

        wait_for('StarRocks to mark the selected member down', down, seconds=180)
        print(f'Outage: {target} Alive=false.', flush=True)
        probe = 'fmea_probe_' + uuid.uuid4().hex[:12]
        event = time.time_ns()
        if kind == 'fe':
            sql(f'CREATE DATABASE {probe};', survivor)
            readback = f"SHOW DATABASES LIKE '{probe}';"
            expected = probe
        else:
            sql('ADMIN SHOW REPLICA STATUS FROM fmea.events;', survivor)
            sql(f"INSERT INTO fmea.events VALUES ({event}, NOW(), 'be-outage');", survivor)
            readback = f'SELECT * FROM fmea.events WHERE event_id={event};'
            expected = str(event)
        print('Client probe: acknowledged.', flush=True)
        run(['kubectl', 'uncordon', worker])
        cordoned = False
        wait_for('membership and all tablet replicas to recover',
                 lambda: run(['./scripts/smoke-test.sh'], timeout=90, check=False).returncode == 0)
        replacement = pod()
        if replacement['metadata']['uid'] == original['metadata']['uid']:
            raise RuntimeError('The pod UID did not change.')
        if claims(replacement) != claims(original):
            raise RuntimeError('The PVC claims changed.')
        result = sql(readback, survivor)
        if not any(line.split('\t')[0] == expected for line in result.stdout.splitlines()[1:]):
            raise RuntimeError('The acknowledged probe is absent after recovery.')
        print('Readback: acknowledged probe is present.', flush=True)
        if kind == 'fe':
            roles = [row['Name'].split('.')[0] for row in members(survivor, 'fe') if row['Role'] == 'LEADER']
            print('Leader: ' + ', '.join(roles), flush=True)
        print('Recovery: 3 alive FEs, 3 alive BEs, 12 healthy replicas.', flush=True)
        print('Storage: same PVC claims; replacement pod has a new UID.', flush=True)
        verdict = 'PASS'
    finally:
        if cordoned:
            result = run(['kubectl', 'uncordon', worker], check=False)
            if result.returncode:
                print('Cleanup failed: uncordon the selected worker before another test.', flush=True)
        (evidence / 'summary.json').write_text(json.dumps({
            'test': args.test, 'verdict': verdict, 'target': target, 'run_id': run_id,
        }, indent=2))
    print(f'Status: {verdict}', flush=True)
    print(f'Private evidence: .local/runs/{run_id}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError, OSError, ValueError, KeyError, StopIteration) as error:
        raise SystemExit(f'FAIL: {error}')
