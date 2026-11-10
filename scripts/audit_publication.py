"""Scan publication files, staged Git blobs and reachable history without echoing secrets."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--root', default='.')
parser.add_argument('--private-env', default=None)
args = parser.parse_args()
root = Path(args.root).resolve()
secrets = []
for name in ['ANTROUTER_API_KEY', 'CLASSROOM_DEMO_CODE', 'RENDER_API_KEY', 'GH_TOKEN', 'GITHUB_TOKEN']:
    if os.getenv(name):
        secrets.append(os.environ[name].encode())
if args.private_env:
    for line in Path(args.private_env).read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.startswith('#'):
            name, value = line.split('=', 1)
            if name in {'ANTROUTER_API_KEY', 'CLASSROOM_DEMO_CODE', 'RENDER_API_KEY', 'GH_TOKEN', 'GITHUB_TOKEN'} and value and not value.startswith('replace-'):
                secrets.append(value.strip().encode())
pattern = re.compile(rb'(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|rnd_[A-Za-z0-9]{25,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
findings = []
scanned = 0
def scan(label, data):
    global scanned
    scanned += 1
    if pattern.search(data) or any(value in data for value in secrets if len(value) >= 8):
        findings.append(label + ': credential-like or known private value detected (redacted)')

manifest_file = root / 'PUBLICATION_MANIFEST.json'
if not manifest_file.exists():
    raise SystemExit('Missing explicit PUBLICATION_MANIFEST.json')
manifest = set(json.loads(manifest_file.read_text(encoding='utf-8')))
actual = set()
for path in root.rglob('*'):
    rel = path.relative_to(root)
    if '.git' in rel.parts:
        continue
    if path.is_file():
        actual.add(rel.as_posix())
        scan(rel.as_posix(), path.read_bytes())
extra = actual - manifest
missing = manifest - actual
if extra:
    findings.append('Non-allowlisted files: ' + ', '.join(sorted(extra)))
if missing:
    findings.append('Missing allowlisted files: ' + ', '.join(sorted(missing)))
history = 0
staged = 0
def git(*args):
    return subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
if (root / '.git').exists():
    for entry in git('ls-files', '--stage', '-z').stdout.split(b'\x00'):
        if not entry:
            continue
        metadata, path = entry.split(b'\t', 1)
        sha = metadata.split()[1].decode()
        blob = git('cat-file', '-p', sha)
        scan('staged:' + path.decode(errors='replace'), blob.stdout)
        staged += 1
        if path.decode(errors='replace') not in manifest:
            findings.append('Non-allowlisted staged path: ' + path.decode(errors='replace'))
    # Scan each unique reachable historical blob, including earlier/deleted files.
    objects = git('rev-list', '--objects', '--all').stdout.splitlines()
    for item in objects:
        sha = item.split(b' ', 1)[0].decode()
        if git('cat-file', '-t', sha).stdout.strip() == b'blob':
            scan('history-object:' + sha[:12], git('cat-file', '-p', sha).stdout)
            history += 1
print(json.dumps({'ok': not findings, 'public_files': len(actual), 'staged_files': staged,
                  'history_blobs': history, 'scanned_items': scanned, 'findings': findings}, ensure_ascii=False, indent=2))
raise SystemExit(1 if findings else 0)
