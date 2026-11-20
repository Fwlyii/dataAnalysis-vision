"""Build and verify the approved presentation and retained atlas on loopback."""
import argparse
import functools
import os
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8847)
    parser.add_argument('--skip-build', action='store_true')
    args = parser.parse_args()
    if not args.skip_build:
        subprocess.run([sys.executable, 'scripts/system/build_web_app.py'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, 'scripts/system/check_reconstruction.py'], cwd=ROOT, check=True)
    handler = functools.partial(Handler, directory=str(ROOT / 'app/dist'))
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f'http://127.0.0.1:{args.port}/'
        for script, url in [('zhiwei-gate.mjs', base), ('zhiwei.mjs', base), ('defense.mjs', base + 'legacy.html')]:
            subprocess.run(['node', 'tests/browser/' + script], cwd=ROOT,
                           env={**os.environ, 'BASE_URL': url}, check=True)
    finally:
        server.shutdown()
        worker.join()
        server.server_close()


if __name__ == '__main__':
    main()
