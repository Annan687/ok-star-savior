"""Read-only source validation and an offline GUI smoke check for releases."""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'.venv', 'configs', 'logs', 'runs', 'screenshots', 'backups',
             'cache', 'work', 'preview', '.env', '.codex'}


def check_source(root=ROOT, repository=None):
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if '.git' in rel.parts or '__pycache__' in rel.parts:
            continue
        if path.is_symlink():
            raise ValueError(f'Symlink in release: {rel}')
        if any(part.lower() in FORBIDDEN for part in rel.parts):
            raise ValueError(f'Local data in release: {rel}')
        if path.is_file() and path.suffix == '.py':
            source = path.read_text(encoding='utf-8-sig')
            compile(source, str(rel), 'exec')
            if re.search(r'[A-Z]:[\\/]+Users[\\/]+annan', source, re.I):
                raise ValueError(f'Developer path in release: {rel}')
    cfg = json.loads((root / 'pyappify.yml').read_text(encoding='utf-8'))
    profile = cfg['profiles'][0]
    if cfg['name'] != 'ok-star-savior' or profile['name'] != 'Global':
        raise ValueError('Unexpected application or profile name')
    if repository and profile['git_url'] != f'https://github.com/{repository}.git':
        raise ValueError('Update repository does not match the build repository')
    if profile['admin'] or cfg['uac'] or profile['show_add_defender']:
        raise ValueError('Unexpected elevated or security-setting configuration')
    requirements = (root / 'requirements.txt').read_text(encoding='utf-8')
    for line in requirements.splitlines():
        if line and not line.startswith('#') and not re.fullmatch(r'[\w.-]+==[\w.+-]+', line):
            raise ValueError(f'Requirement is not a portable version pin: {line}')
    for relative in ('main.py', 'assets/icon.png', 'icons/icon.ico',
                     'vendor/ok-script/ok/__init__.py', 'vendor/ok-script/LICENSE.txt',
                     'THIRD-PARTY-NOTICES.md', 'licenses/pyappify/LICENSE.txt'):
        if not (root / relative).is_file():
            raise ValueError(f'Missing release file: {relative}')
    print('Release source validation passed')


def smoke():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    sys.path.insert(0, str(ROOT))
    from main import prepare
    prepare()
    from PySide6.QtWidgets import QApplication
    from starsavior.dashboard import DailyPanel, PreviewBackend
    from starsavior.tasks import STEPS
    import ok
    import cv2
    import openvino
    import onnxocr
    assert Path(ok.__file__).resolve() == ROOT / 'vendor/ok-script/ok/__init__.py'
    app = QApplication.instance() or QApplication([])
    panel = DailyPanel(PreviewBackend())
    assert len(panel.checks) == len(STEPS) == 17
    assert not panel.start_button.isEnabled()
    panel.timer.stop()
    panel.close()
    panel.deleteLater()
    app.processEvents()
    print('Offline GUI/runtime smoke check passed; no game was opened or clicked')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository')
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.smoke:
        smoke()
    else:
        check_source(repository=args.repository)

