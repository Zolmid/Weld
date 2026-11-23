"""Install an iOS simulator app or Android APK and verify browsing and Shields."""
import argparse
import os
import plistlib
import re
import subprocess
from http.server import ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from threading import Thread
from time import monotonic, sleep
from xml.etree import ElementTree

from desktop_smoke import Fixture, expect_requests

CASES = [('control', False), ('shields-blocked', True), ('restored', False)]


def command(*args):
    return subprocess.check_output(args, text=True, timeout=120).strip()


def iphone(app, server):
    udid = os.environ['WELD_IOS_SIMULATOR_UDID']
    package = plistlib.loads((app / 'Info.plist').read_bytes())['CFBundleIdentifier']
    simctl = ('xcrun', 'simctl')
    command(*simctl, 'bootstatus', udid, '-b')
    command(*simctl, 'install', udid, app)
    for case, blocked in CASES:
        mode = '--brave-smoke-block-scripts' if blocked else '--brave-smoke-allow-scripts'
        command(*simctl, 'launch', '--terminate-running-process', udid, package,
                '--brave-smoke-url', f'http://127.0.0.1:{server.server_port}/page/{case}', mode)
        expect_requests(server, case, blocked)
    command(*simctl, 'terminate', udid, package)


def droid(apk, server):
    serial = os.environ['WELD_ANDROID_SERIAL']
    if not serial.startswith('emulator-'):
        raise SystemExit('The Android smoke test requires a dedicated emulator serial.')
    adb = ('adb', '-s', serial)
    if command(*adb, 'shell', 'getprop', 'ro.kernel.qemu') != '1':
        raise SystemExit('The Android target is not an emulator.')
    package = command('apkanalyzer', 'manifest', 'application-id', apk)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+', package):
        raise SystemExit('Invalid Android application identifier.')
    command(*adb, 'install', '-r', str(apk))
    target = f'tcp:{server.server_port}'
    command(*adb, 'reverse', target, target)

    def hierarchy():
        command(*adb, 'shell', 'uiautomator', 'dump', '/data/local/tmp/weld-ui.xml')
        data = command(*adb, 'exec-out', 'cat', '/data/local/tmp/weld-ui.xml')
        return list(ElementTree.fromstring(data).iter('node'))

    def tap(node):
        left, top, right, bottom = [int(n) for n in re.findall(r'\d+', node.get('bounds', ''))]
        command(*adb, 'shell', 'input', 'tap', str((left + right) // 2), str((top + bottom) // 2))

    def find(labels, attempts=6, checkable=False):
        for _ in range(attempts):
            for node in hierarchy():
                if checkable and node.get('checkable') != 'true':
                    continue
                if node.get('text') in labels or node.get('content-desc') in labels:
                    return node
        raise RuntimeError(f'Android UI control missing: {labels}')

    def launch(case):
        command(*adb, 'shell', 'am', 'start', '-W', '-a', 'android.intent.action.VIEW',
                '-d', f'http://127.0.0.1:{server.server_port}/page/{case}', '-p', package)

    def prepare():
        launch('control')
        deadline = monotonic() + 60
        while monotonic() < deadline:
            nodes = hierarchy()
            for node in nodes:
                if node.get('content-desc') == 'Enable/Disable Brave Shields':
                    launch('control')
                    return
            for node in nodes:
                if node.get('text') in {'Continue', 'Get started', 'Skip', 'Not now', 'Maybe later',
                                        'No thanks', 'Done', 'Cancel'} and node.get('enabled') == 'true':
                    tap(node)
                    break
            sleep(0.2)
        raise RuntimeError('The Android welcome flow did not reach the browser.')

    def scripts(desired):
        tap(find({'Enable/Disable Brave Shields'}))
        try:
            toggle = find({'Block scripts'}, attempts=1, checkable=True)
        except RuntimeError:
            tap(find({'Advanced controls'}))
            toggle = find({'Block scripts'}, checkable=True)
        if (toggle.get('checked') == 'true') != desired:
            tap(toggle)
            updated = find({'Block scripts'}, checkable=True)
            if (updated.get('checked') == 'true') != desired:
                raise RuntimeError('The Android Shields toggle did not change.')
        command(*adb, 'shell', 'input', 'keyevent', 'KEYCODE_BACK')

    try:
        prepare()
        expect_requests(server, 'control', False)
        for case, blocked in CASES[1:]:
            scripts(blocked)
            launch(case)
            expect_requests(server, case, blocked)
    finally:
        command(*adb, 'reverse', '--remove', target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('platform', choices=['ios', 'android'])
    parser.add_argument('artifact', type=Path)
    args = parser.parse_args()
    with ThreadingHTTPServer(('127.0.0.1', 0), Fixture) as listener:
        listener.requests = Queue()
        Thread(target=listener.serve_forever, daemon=True).start()
        try:
            smoke = iphone if args.platform == 'ios' else droid
            smoke(args.artifact.resolve(strict=True), listener)
        finally:
            listener.shutdown()
