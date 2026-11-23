"""Launch a packaged desktop build and exercise its site script setting."""
import argparse
import base64
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Queue
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic

PIXEL = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/ak2q1kAAAAASUVORK5CYII='
)


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        kind, _, case = self.path[1:].partition('/')
        if kind == 'page':
            body = (f'<!doctype html><title>Weld acceptance</title><img src="/image/{case}">'
                    f'<script>fetch("/script/{case}")</script>').encode()
            content_type = 'text/html'
        elif kind == 'image':
            body, content_type = PIXEL, 'image/png'
        elif kind == 'script':
            body, content_type = b'ok', 'text/plain'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.server.requests.put((kind, case))


def expect_requests(server, case, blocked, timeout=45):
    expected = {'page', 'image'} if blocked else {'page', 'image', 'script'}
    seen = set()
    deadline = monotonic() + timeout
    while not expected <= seen and monotonic() < deadline:
        try:
            kind, scenario = server.requests.get(timeout=max(0, deadline - monotonic()))
        except Empty:
            break
        if scenario == case:
            seen.add(kind)
    if blocked:
        deadline = monotonic() + 3
        while monotonic() < deadline:
            try:
                kind, scenario = server.requests.get(timeout=max(0, deadline - monotonic()))
            except Empty:
                break
            if scenario == case:
                seen.add(kind)
    if not expected <= seen or blocked and 'script' in seen:
        raise RuntimeError(f'{case}: expected {sorted(expected)}, received {sorted(seen)}')
    print(f'PASS {case}: {sorted(seen)}', flush=True)


def run(browser):
    with TemporaryDirectory(prefix='weld-desktop-') as directory:
        root = Path(directory)
        with ThreadingHTTPServer(('127.0.0.1', 0), Fixture) as server:
            server.requests = Queue()
            Thread(target=server.serve_forever, daemon=True).start()
            origin = f'http://127.0.0.1:{server.server_port}'
            try:
                for case, blocked in [('control', False), ('shields-blocked', True), ('restored', False)]:
                    profile = root / case
                    (profile / 'Default').mkdir(parents=True)
                    if blocked:
                        settings = {'profile': {'content_settings': {'exceptions': {
                            'javascript': {f'{origin},*': {'setting': 2}},
                        }}}}
                        (profile / 'Default/Preferences').write_text(json.dumps(settings))
                    with (root / f'{case}.log').open('wb') as log:
                        process = subprocess.Popen([
                            str(browser), f'--user-data-dir={profile}', '--no-first-run',
                            '--no-default-browser-check', '--disable-background-networking',
                            '--disable-crashpad-for-testing', '--use-mock-keychain',
                            '--enable-logging=stderr',
                            '--disable-brave-update', '--disable-updater-scheduler',
                            '--disable-features=BraveUseOmaha4',
                            '--no-proxy-server', '--disable-gpu', f'{origin}/page/{case}',
                        ], cwd=browser.parent, stdout=log, stderr=subprocess.STDOUT)
                        try:
                            expect_requests(server, case, blocked)
                        except RuntimeError:
                            print((root / f'{case}.log').read_text(errors='replace')[-4000:])
                            raise
                        finally:
                            if process.poll() is None:
                                process.terminate()
                                try:
                                    process.wait(timeout=10)
                                except subprocess.TimeoutExpired:
                                    process.kill()
                                    process.wait(timeout=10)
            finally:
                server.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('browser', type=Path)
    run(parser.parse_args().browser.resolve(strict=True))
