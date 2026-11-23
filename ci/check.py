"""Check Weld's source contract without downloading Chromium."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = json.loads((ROOT / 'ci/pins.json').read_text())
PACKAGE = json.loads((ROOT / 'package.json').read_text())
SLIM_FLAGS = (
    'enable_ai_chat', 'enable_local_ai', 'enable_brave_wallet',
    'enable_brave_rewards', 'enable_brave_ads', 'enable_brave_promotions',
    'enable_brave_vpn_v1', 'enable_brave_vpn_v2',
)


def check():
    if PACKAGE['config']['projects']['chrome']['tag'] != PINS['chromium_tag']:
        raise SystemExit('Update the Chromium tag and reviewed commit in ci/pins.json together.')
    for key in ('brave_base', 'chromium_revision'):
        if not re.fullmatch(r'[0-9a-f]{40}', PINS[key]):
            raise SystemExit(f'Invalid commit pin: {key}')
    build = (ROOT / 'build/commands/lib/build.ts').read_text()
    for flag in SLIM_FLAGS:
        if f"'{flag}:false'" not in build:
            raise SystemExit(f'--slim must disable {flag}.')
    forbidden = re.compile(r'(networkextension|vpn\.api|personal-vpn|vpn\.configuration)', re.I)
    entitlements = list((ROOT / 'ios/brave-ios/App/iOS/Entitlements').glob('*-NoVPN.entitlements'))
    if len(entitlements) != 6:
        raise SystemExit('Expected six slim iOS application entitlements.')
    for path in entitlements:
        if forbidden.search(path.read_text()):
            raise SystemExit(f'VPN entitlement in {path.relative_to(ROOT)}')
    subprocess.run(['git', 'merge-base', '--is-ancestor', PINS['brave_base'], 'HEAD'], cwd=ROOT, check=True)
    print('Weld source contract passed.')


if __name__ == '__main__':
    check()
