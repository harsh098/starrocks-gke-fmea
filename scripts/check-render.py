#!/usr/bin/env python3
"""Check rendered resources, CRD schema, and lab invariants without cloud access."""
from pathlib import Path
import jsonschema
import yaml

root = Path(__file__).resolve().parent.parent
cluster = list(yaml.safe_load_all((root / '.local/validation/cluster.yaml').read_text()))
operator = list(yaml.safe_load_all((root / '.local/validation/operator.yaml').read_text()))
cr = next(d for d in cluster if d and d.get('kind') == 'StarRocksCluster')
crd = next(d for d in operator if d and d.get('kind') == 'CustomResourceDefinition'
           and d['metadata']['name'] == 'starrocksclusters.starrocks.com')
schema = next(v for v in crd['spec']['versions'] if v['name'] == 'v1')['schema']['openAPIV3Schema']

# Kubernetes prunes null values on non-nullable optional fields before validation.
def prune_nulls(value):
    if isinstance(value, dict):
        return {k: prune_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [prune_nulls(v) for v in value]
    return value

jsonschema.validate(prune_nulls(cr), schema)
assert cr['metadata']['name'] == 'starrocks-fmea'
assert 'starRocksCnSpec' not in cr['spec'], 'The lab must be shared-nothing'
for key, image in [('starRocksFeSpec', 'starrocks/fe-ubuntu:3.5.0'),
                   ('starRocksBeSpec', 'starrocks/be-ubuntu:3.5.0')]:
    spec = cr['spec'][key]
    assert spec['replicas'] == 3 and spec['image'] == image
    assert spec['service']['type'] == 'ClusterIP', 'Do not expose the database'
    env = spec.get('feEnvVars', spec.get('beEnvVars'))
    pwd = next(e for e in env if e['name'] == 'MYSQL_PWD')
    assert pwd['valueFrom']['secretKeyRef'] == {'name': 'starrocks-admin-password', 'key': 'password'}
    assert spec['nodeSelector'] == {'starrocks-lab': 'true'}
    volumes = [v for v in spec['storageVolumes'] if v.get('storageSize') != '0Gi']
    assert len(volumes) == 1 and volumes[0]['storageSize'] == '100Gi'
    assert volumes[0]['storageClassName'] == 'premium-rwo'
assert all(d.get('kind') != 'Secret' for d in cluster if d), 'No generated credential may enter Helm values'
deployment = next(d for d in operator if d and d.get('kind') == 'Deployment')
assert deployment['spec']['template']['spec']['containers'][0]['image'] == 'starrocks/operator:v1.11.1'
print('PASS: CRD schema, pinned images, replicas, zonal storage, internal access, and Secret references')
