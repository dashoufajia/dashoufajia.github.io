"""Set an explicitly supplied real backend URL; do not guess a Render hostname."""
from pathlib import Path
import argparse
import json
from urllib.parse import urlsplit

parser = argparse.ArgumentParser()
parser.add_argument('--backend', required=True)
args = parser.parse_args()
url = args.backend.rstrip('/')
parts = urlsplit(url)
if parts.scheme != 'https' or not parts.hostname or parts.path or parts.query or parts.fragment or parts.username or parts.password:
    parser.error('--backend must be an HTTPS origin without a path, credentials, query or fragment')
root = Path(__file__).resolve().parents[1]
(root / 'docs' / 'config.js').write_text('window.WRITING_LAB_CONFIG = ' + json.dumps({'apiBaseUrl': url, 'backendRequired': True}) + ';\n', encoding='utf-8')
print('Configured public frontend backend origin:', url)
