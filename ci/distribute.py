"""Gate Weld's release on same-source candidates and verified platform packages."""
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from check import PINS

CANDIDATES = {
    'linux': 'Weld-linux-x64.tar.gz',
    'win': 'Weld-windows-x64.zip',
    'mac': 'Weld-macos-arm64.zip',
    'ios': 'Weld-ios-arm64-unsigned.zip',
    'android': 'Weld-android-arm64.apk',
}
RELEASE_SUFFIX = {'linux': '.tar.gz', 'win': '.zip', 'mac': '.dmg', 'ios': '.ipa', 'android': '.apk'}


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            sha.update(block)
    return sha.hexdigest()


def release_name(platform):
    version = os.environ['WELD_VERSION']
    if not re.fullmatch(r'v\d+\.\d+\.\d+', version):
        raise SystemExit('Invalid release tag.')
    stem = CANDIDATES[platform].split('.')[0].removesuffix('-unsigned')
    return f'{stem}-{version}{RELEASE_SUFFIX[platform]}'


def run(*command):
    subprocess.run(command, check=True)


def extract(package, target):
    with ZipFile(package) as archive:
        for member in archive.infolist():
            path = (target / member.filename).resolve()
            if target not in path.parents:
                raise SystemExit(f'Unsafe archive member: {member.filename}')
        archive.extractall(target)


def validate_signed(platform, package):
    if platform == 'mac':
        run('hdiutil', 'verify', package)
        run('xcrun', 'stapler', 'validate', package)
        run('spctl', '--assess', '--type', 'open', '--context', 'context:primary-signature', package)
    elif platform == 'ios':
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            extract(package, root)
            apps = list((root / 'Payload').glob('*.app'))
            if len(apps) != 1:
                raise SystemExit('Expected one Payload app in the IPA.')
            app = apps[0]
            identifier = plistlib.loads((app / 'Info.plist').read_bytes())['CFBundleIdentifier']
            if identifier.startswith('com.brave.'):
                raise SystemExit('The IPA must use Weld-owned distribution identifiers.')
            run('codesign', '--verify', '--deep', '--strict', app)
            run(sys.executable, Path(__file__).with_name('ios_vpn_audit.py'), app)
    elif platform == 'win':
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            extract(package, root)
            browser = root / 'Weld/brave.exe'
            for required in ('brave.exe', 'chrome.dll', 'chrome_elf.dll', 'resources.pak'):
                if not (browser.parent / required).is_file():
                    raise SystemExit(f'Windows package lacks {required}.')
            run('signtool.exe', 'verify', '/pa', browser)
            run(sys.executable, Path(__file__).with_name('desktop_smoke.py'), browser)
    elif platform == 'android':
        run('apksigner', 'verify', '--verbose', package)
        identifier = subprocess.check_output(
            ['apkanalyzer', 'manifest', 'application-id', package], text=True).strip()
        if identifier.startswith('com.brave.'):
            raise SystemExit('The APK must use a Weld-owned application identifier.')
        run(sys.executable, Path(__file__).with_name('mobile_smoke.py'), 'android', package)


def package(platform, source, destination):
    metadata = json.loads((source / f'Weld-{platform}.json').read_text())
    if (metadata['platform'], metadata['source'], metadata['chromium'], metadata['type']) != (
        platform, os.environ['GITHUB_SHA'], PINS['chromium_revision'], 'candidate'
    ):
        raise SystemExit('The candidate is not from the expected source and Chromium pin.')
    candidate = (source / CANDIDATES[platform]).resolve(strict=True)
    destination.mkdir()
    output = (destination / release_name(platform)).resolve()
    if platform == 'linux':
        shutil.copy2(candidate, output)
    else:
        driver = Path(os.environ['WELD_RELEASE_DRIVER'])
        if not driver.is_absolute() or not driver.is_file():
            raise SystemExit('Configure a platform release driver on the protected signing runner.')
        command = [str(driver), platform, str(candidate), str(output), os.environ['WELD_VERSION']]
        if driver.suffix.lower() == '.ps1':
            command = ['pwsh', '-NoProfile', '-NonInteractive', '-File', *command]
        run(*command)
    if not output.is_file() or output.stat().st_size == 0:
        raise SystemExit('The signing driver did not produce a valid package file.')
    validate_signed(platform, output)
    receipt = {**metadata, 'type': 'release', 'file': output.name, 'sha256': digest(output),
               'size': output.stat().st_size, 'candidate_sha256': digest(candidate)}
    (destination / f'{platform}.json').write_text(json.dumps(receipt, indent=2) + '\n')


def verify(root):
    destination = root / 'verified'
    destination.mkdir()
    checksums = []
    for platform in sorted(CANDIDATES):
        directory = root / f'weld-release-{platform}'
        receipt = json.loads((directory / f'{platform}.json').read_text())
        artifact = directory / release_name(platform)
        if (receipt['platform'], receipt['source'], receipt['chromium'], receipt['type'], receipt['file']) != (
            platform, os.environ['GITHUB_SHA'], PINS['chromium_revision'], 'release', artifact.name
        ):
            raise SystemExit(f'{platform} has inconsistent provenance.')
        if artifact.stat().st_size != receipt['size'] or digest(artifact) != receipt['sha256']:
            raise SystemExit(f'{platform} has an invalid artifact checksum.')
        shutil.copy2(artifact, destination)
        shutil.copy2(directory / f'{platform}.json', destination)
        checksums.append(f"{receipt['sha256']}  {artifact.name}")
    (destination / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')


if __name__ == '__main__':
    if sys.argv[1] == 'verify':
        verify(Path(sys.argv[2]))
    else:
        package(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))
