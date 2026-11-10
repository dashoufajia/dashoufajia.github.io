"""Generate a static, subpath-safe frontend. This never reads private .env files."""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'starter' / 'static'
target = ROOT / 'docs'
target.mkdir(exist_ok=True)
html = (source / 'index.html').read_text(encoding='utf-8-sig')
html = html.replace('href="/static/lab.css"', 'href="./lab.css"')
html = html.replace('src="/static/config.js"', 'src="./config.js"')
html = html.replace('src="/static/lab.js"', 'src="./lab.js"')
html = html.replace('class="brand" href="/"', 'class="brand" href="./"')
(target / 'index.html').write_text(html, encoding='utf-8')
for name in ['lab.css', 'lab.js']:
    shutil.copy2(source / name, target / name)
if not (target / 'config.js').exists():
    (target / 'config.js').write_text(
        '// Set the real Render HTTPS origin only after its deployment succeeds. No secrets belong here.\n'
        'window.WRITING_LAB_CONFIG = {apiBaseUrl: "", backendRequired: true};\n', encoding='utf-8')
data = json.loads((ROOT / '03_Data.json').read_text(encoding='utf-8-sig'))
(target / 'samples.json').write_text(json.dumps({'version': data['version'], 'samples': data['samples']}, ensure_ascii=False, indent=2), encoding='utf-8')
(target / '.nojekyll').touch()
print('Built docs/index.html, relative assets, and W1-W3 public sample fallback.')
