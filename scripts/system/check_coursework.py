"""Check course deliverables and local navigation without third-party packages."""
from pathlib import Path
from urllib.parse import unquote, urlsplit
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = [
    'README.md', 'guide/README.md', 'app/README.md', 'data/DOWNLOAD.md',
    'docs/README.md', 'docs/submission.md', 'docs/repository-structure.md',
    'docs/reproducibility.md', 'docs/github-pages.md', 'docs/pages-preview.md',
    'report/README.md', 'presentation/README.md', 'tests/README.md',
    'docs/product.md', 'docs/project-summary.md',
]
REQUIRED = [
    'app/index.html', 'app/launch.py', 'data/raw', 'data/processed',
    'data/data_dictionary.md', 'scripts/pipeline.py',
    'guide/数据分析和可视化-题目2.pdf',
    'report/case_report.pdf', 'presentation/defense_slides.pdf',
]


def anchors(source):
    found = set(re.findall(r'<a\s+(?:id|name)="([^"]+)"', source))
    duplicates = {}
    for title in re.findall(r'^#{1,6}\s+(.+)$', source, flags=re.MULTILINE):
        title = re.sub(r'[^\w\-\s]', '', title.lower()).replace(' ', '-')
        count = duplicates.get(title, 0)
        found.add(title + (f'-{count}' if count else ''))
        duplicates[title] = count + 1
    return found


def check():
    errors = []
    link_count = 0
    for relative in [*DOCUMENTS, *REQUIRED]:
        path = ROOT / relative
        if not path.exists():
            errors.append(f'Missing course deliverable: {relative}')
        elif path.suffix == '.pdf' and not path.read_bytes().startswith(b'%PDF-'):
            errors.append(f'PDF is not hydrated: {relative}')
    for relative in DOCUMENTS:
        document = ROOT / relative
        if not document.is_file():
            continue
        source = document.read_text(encoding='utf-8')
        for target in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', source):
            address = urlsplit(target.strip('<>'))
            if address.scheme or address.netloc:
                continue
            link_count += 1
            destination = (document.parent / unquote(address.path)).resolve() if address.path else document
            if not destination.is_relative_to(ROOT):
                errors.append(f'{relative}: link escapes the project: {target}')
            elif not destination.exists():
                errors.append(f'{relative}: broken link: {target}')
            elif address.fragment and destination.suffix == '.md':
                if unquote(address.fragment) not in anchors(destination.read_text(encoding='utf-8')):
                    errors.append(f'{relative}: missing anchor: {target}')
    original = ROOT / 'guide/数据分析和可视化-题目2.pdf'
    snapshot = ROOT / 'app/data/course-assignment.pdf'
    if original.is_file() and snapshot.is_file():
        if hashlib.sha256(original.read_bytes()).digest() != hashlib.sha256(snapshot.read_bytes()).digest():
            errors.append('Course source and protected browser copy differ')
    if (ROOT / '.git').exists():
        result = subprocess.run(['git', 'ls-files', '-z', '--', 'submission'], cwd=ROOT,
                                capture_output=True, check=False)
        if result.returncode:
            errors.append('Could not inspect tracked submission duplicates')
        elif result.stdout:
            errors.append('Generated submission copies are still tracked')
    print(json.dumps({'documents': len(DOCUMENTS), 'local_links': link_count,
                      'errors': errors, 'manual_deliverables': ['member information', '5–6 min 1080P recording']},
                     ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == '__main__':
    sys.exit(check())
