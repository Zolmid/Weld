"""Track official Brave and Chromium sources and prepare a reviewable merge."""
import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from check import PINS, ROOT

BRAVE = 'https://github.com/brave/brave-core.git'
CHROMIUM = 'https://chromium.googlesource.com/chromium/src.git'
RELEASES = 'https://chromiumdash.appspot.com/fetch_releases'
PLATFORMS = ('Linux', 'Windows', 'Mac', 'Android')
BRAVE_REF = 'refs/remotes/weld-upstream/master'


def git(*args, check=True):
    result = subprocess.run(['git', *args], cwd=ROOT, text=True, capture_output=True, check=check)
    return result.stdout.strip(), result.returncode


def tag_sha(tag):
    if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', tag):
        raise ValueError(f'Invalid Chromium tag {tag}')
    ref = f'refs/tags/{tag}'
    rows = git('ls-remote', CHROMIUM, ref, ref + '^{}')[0].splitlines()
    refs = {key: sha for sha, key in (line.split() for line in rows)}
    sha = refs.get(ref + '^{}') or refs.get(ref)
    if not sha or not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError(f'Missing official Chromium tag {tag}')
    return sha


def brave_head():
    line = git('ls-remote', '--exit-code', BRAVE, 'refs/heads/master')[0]
    brave, ref = line.split()
    if ref != 'refs/heads/master' or not re.fullmatch(r'[0-9a-f]{40}', brave):
        raise ValueError('Unexpected official Brave branch response.')
    url = f'https://raw.githubusercontent.com/brave/brave-core/{brave}/package.json'
    with urlopen(url, timeout=30) as response:
        package = json.load(response)
    tag = package['config']['projects']['chrome']['tag']
    return brave, tag, tag_sha(tag)


def stable(platform):
    query = urlencode({'channel': 'Stable', 'platform': platform, 'num': 1})
    with urlopen(f'{RELEASES}?{query}', timeout=30) as response:
        release = json.load(response)[0]
    if release['channel'] != 'Stable' or release['platform'] != platform:
        raise ValueError(f'Unexpected Chromium Dash response for {platform}')
    return release['version']


def version(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', value):
        raise ValueError(f'Invalid version {value}')
    return tuple(map(int, value.split('.')))


def report(path):
    brave, tag, revision = brave_head()
    stable_versions = {platform: stable(platform) for platform in PLATFORMS}
    impact = {platform: value for platform, value in stable_versions.items()
              if version(value) > version(PINS['chromium_tag'])}
    status = {
        'weld': PINS,
        'brave_upstream': {'commit': brave, 'chromium_tag': tag, 'chromium_revision': revision},
        'chromium_stable': stable_versions,
        'stable_newer_than_weld': impact,
        'brave_pin_lags_stable': {platform: value for platform, value in stable_versions.items()
                                 if version(value) > version(tag)},
        'security_bulletins': 'https://chromereleases.googleblog.com/',
    }
    path.write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps(status, indent=2))


def prepare(expected):
    if git('status', '--porcelain')[0]:
        raise SystemExit('Use a clean Weld checkout.')
    brave, tag, revision = brave_head()
    if brave != expected:
        raise SystemExit(f'Brave head is now {brave}. Review the newest report first.')
    if git('merge-base', '--is-ancestor', brave, 'HEAD', check=False)[1] == 0:
        raise SystemExit('This Brave commit is already merged.')
    git('fetch', '--no-tags', BRAVE, f'+refs/heads/master:{BRAVE_REF}')
    if git('rev-parse', BRAVE_REF)[0] != brave:
        raise SystemExit('Brave advanced during fetch. Review a new report.')
    branch = f'codex/upstream-{brave[:12]}'
    subprocess.run(['git', 'switch', '-c', branch], cwd=ROOT, check=True)
    merged = subprocess.run(['git', 'merge', '--no-ff', '--no-commit', brave], cwd=ROOT)
    if merged.returncode:
        raise SystemExit('Resolve the merge on this branch before updating pins and running tests.')
    automation = git('diff', '--cached', '--name-only', '--', '.github', 'ci')[0]
    if automation:
        raise SystemExit(f'Review changes in workflow or CI files before continuing:\n{automation}')
    pins = dict(PINS, brave_base=brave, chromium_tag=tag, chromium_revision=revision)
    (ROOT / 'ci/pins.json').write_text(json.dumps(pins, indent=2) + '\n')
    print('Review the staged merge and update ci/pins.json in the merge commit.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('report').add_argument('path', type=Path)
    actions.add_parser('prepare').add_argument('reviewed_brave_commit')
    args = parser.parse_args()
    if args.action == 'report':
        report(args.path)
    else:
        prepare(args.reviewed_brave_commit)
