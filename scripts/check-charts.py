#!/usr/bin/env python3
"""Verify the upstream chart archives before rendering or deployment."""
import hashlib
from pathlib import Path

charts = Path(__file__).resolve().parent.parent / 'deploy/charts'
for line in (charts / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split()
    assert hashlib.sha256((charts / name).read_bytes()).hexdigest() == expected, f'Chart checksum mismatch: {name}'
print('PASS: upstream chart checksums')
