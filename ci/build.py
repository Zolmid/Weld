"""Build and stage one Weld candidate from a pinned, isolated checkout."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from check import PINS, ROOT, SLIM_FLAGS, check

SRC = ROOT.parent
OUT = SRC / 'out'
PROJECT = ROOT / 'ios/brave-ios/App/Client.xcodeproj'
APP = 'Brave Browser Development.app'
LNX_RUNTIME = {
    'brave', 'brave_sandbox', 'chrome_crashpad_handler', 'chrome_management_service',
    'icudtl.dat', 'resources.pak', 'chrome_100_percent.pak', 'chrome_200_percent.pak',
    'brave_resources.pak', 'brave_100_percent.pak', 'brave_200_percent.pak', 'locales',
    'libEGL.so', 'libGLESv2.so', 'libvulkan.so.1', 'libvk_swiftshader.so',
    'vk_swiftshader_icd.json', 'libqt5_shim.so', 'libqt6_shim.so', 'v8_context_snapshot.bin',
    'snapshot_blob.bin', 'resources', 'MEIPreload', 'IwaKeyDistribution', 'WidevineCdm',
}
WIN_CRITICAL = {'brave.exe', 'chrome.dll', 'chrome_elf.dll', 'icudtl.dat', 'resources.pak', 'locales'}


def run(*cmd, cwd=ROOT, env=None):
    print('+', *cmd, flush=True)
    if os.name == 'nt' and str(cmd[0]).endswith('.cmd'):
        cmd = (os.environ['ComSpec'], '/d', '/c', subprocess.list2cmdline([str(arg) for arg in cmd]))
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def result(*cmd, cwd=ROOT):
    return subprocess.check_output(cmd, cwd=cwd, text=True).strip()


def pnpm(*args):
    run('pnpm.cmd' if os.name == 'nt' else 'pnpm', *args)


def toolchain(platform, arch):
    if ROOT.name != 'brave' or SRC.name != 'src':
        raise SystemExit('Checkout Weld into the workspace path src/brave.')
    check()
    os.environ.update({
        'DEPOT_TOOLS_METRICS': '0',
        'DEPOT_TOOLS_WIN_TOOLCHAIN': '0',
        'GIT_TERMINAL_PROMPT': '0',
    })
    os.environ.pop('SDKROOT', None)
    expected = {'linux': 'linux', 'android': 'linux', 'mac': 'darwin', 'ios': 'darwin', 'win': 'win32'}
    if sys.platform != expected[platform]:
        raise SystemExit(f'{platform} must build on {expected[platform]}.')
    if result('node', '--version') != 'v' + PINS['node']:
        raise SystemExit('Unexpected Node version.')
    mode = 'sync' if (SRC.parent / '.gclient').exists() else 'init'
    pnpm('run', mode, f'--target_os={platform}', f'--target_arch={arch}', '--no-history')
    if result('git', 'rev-parse', 'HEAD', cwd=SRC) != PINS['chromium_revision']:
        raise SystemExit('Synced Chromium commit differs from ci/pins.json.')


def native(platform, arch, name, config='Static', *extra, targets=None):
    args = [config, f'--target_os={platform}', f'--target_arch={arch}', '-C', name,
            '--slim', '--skip_signing', '--use_remoteexec', 'false']
    if targets:
        args.append(f'--target={targets}')
    pnpm('run', 'build', *args, *extra)
    build = OUT / name
    flags = (build / 'args.gn').read_text()
    for flag in SLIM_FLAGS:
        if not re.search(rf'(?m)^\s*{flag}\s*=\s*false\s*$', flags):
            raise SystemExit(f'Generated build is missing {flag} = false.')
    return build


def desktop(platform, arch, destination):
    name = f'weld_{platform}_{arch}'
    flags = ['--gn=symbol_level:0', '--gn=enable_updater:true',
             '--gn=enable_update_notifications:true'] if platform != 'linux' else []
    extras = {'linux': ',brave_sandbox', 'win': '', 'mac': ''}
    build = native(platform, arch, name, 'Static', *flags,
                   targets=f'brave,brave_unit_tests{extras[platform]}')
    tests = build / ('brave_unit_tests.exe' if os.name == 'nt' else 'brave_unit_tests')
    run(tests, '--gtest_filter=BraveShields*', '--gtest_fail_if_no_test_selected', cwd=build)

    stage = destination / 'Weld'
    stage.mkdir()
    if platform == 'mac':
        run('ditto', build / APP, stage / APP)
        browser = stage / APP / 'Contents/MacOS/Brave Browser Development'
    elif platform == 'win':
        # Use the runtime entries from Chromium's patched installer manifest.
        manifest = SRC / 'chrome/installer/mini_installer/chrome.release'
        for line in manifest.read_text().splitlines():
            pattern, separator, _ = line.partition(':')
            if not separator or line.startswith('#') or re.search(r'vpn|wireguard|\.sig$', pattern, re.I):
                continue
            for path in build.glob(pattern.replace('\\', '/')):
                if path.is_file():
                    target = stage / path.relative_to(build)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
        missing = WIN_CRITICAL - {p.name for p in stage.iterdir()}
        if missing:
            raise SystemExit(f'Missing Windows application files: {sorted(missing)}')
        browser = stage / 'brave.exe'
    else:
        for name in sorted(LNX_RUNTIME):
            path = build / name
            if path.is_dir():
                shutil.copytree(path, stage / name, symlinks=True)
            elif path.is_file():
                shutil.copy2(path, stage / name)
        for name in ('brave', 'brave_sandbox', 'icudtl.dat', 'resources.pak', 'locales'):
            if not (stage / name).exists():
                raise SystemExit(f'Missing Linux application file {name}')
        browser = stage / 'brave'
    shutil.copy2(ROOT / 'LICENSE', stage)
    prefix = ['xvfb-run', '-a'] if platform == 'linux' else []
    run(*prefix, sys.executable, ROOT / 'ci/desktop_smoke.py', browser)
    if platform == 'mac':
        run('ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', stage,
            destination / 'Weld-macos-arm64.zip')
    elif platform == 'win':
        shutil.make_archive(str(destination / 'Weld-windows-x64'), 'zip', destination, stage.name)
    else:
        with tarfile.open(destination / 'Weld-linux-x64.tar.gz', 'w:gz') as archive:
            archive.add(stage, arcname='Weld')


def android(arch, destination):
    out = native('android', arch, 'weld_android_arm64')
    candidates = sorted(out.glob('apks/BraveMono*.apk'))
    if len(candidates) != 1:
        raise SystemExit(f'Expected one arm64 mono APK, found: {candidates}')
    shutil.copy2(candidates[0], destination / 'Weld-android-arm64.apk')


def ios_client(environment, arch):
    simulator = environment == 'simulator'
    platform, sdk = ('iOS Simulator', 'iphonesimulator') if simulator else ('iOS', 'iphoneos')
    config = 'Debug' if simulator else 'Release'
    scheme = 'Debug (No Core)' if simulator else 'Release (AppStore)'
    name = f'weld_ios_core_{environment}'
    native('ios', arch, name, config, f'--target_environment={environment}', '--gn=is_official_build:false')
    env = dict(os.environ, BRAVE_IOS_SLIM='1', BRAVE_IOS_PREBUILT_CORE_DIR=name)
    run('python3', ROOT / 'ios/brave-ios/scripts/scheme_preaction.py', '--configuration', config,
        '--platform_name', sdk, '--only_update_symlink', env=env)
    derived = OUT / f'weld_ios_client_{environment}'
    packages = OUT / 'weld_spm'
    base = ['xcodebuild', '-project', PROJECT, '-scheme', scheme, '-sdk', sdk,
            '-destination', f'generic/platform={platform}', '-derivedDataPath', derived,
            '-clonedSourcePackagesDirPath', packages, '-onlyUsePackageVersionsFromResolvedFile']
    run(*base, '-resolvePackageDependencies', env=env)
    signing = ['CODE_SIGNING_ALLOWED=YES', 'CODE_SIGN_IDENTITY=-'] if simulator else [
        'CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO']
    run(*base, '-configuration', 'Debug' if simulator else scheme, '-disableAutomaticPackageResolution',
        'ARCHS=arm64', 'BRAVE_IOS_SLIM=1', f'BRAVE_IOS_PREBUILT_CORE_DIR={name}', *signing, 'build', env=env)
    candidates = sorted(derived.glob('Build/Products/*/Client.app'))
    if len(candidates) != 1:
        raise SystemExit(f'Expected one Client.app for {environment}, found {candidates}')
    return candidates[0]


def ios(arch, destination):
    simulator = ios_client('simulator', arch)
    device = ios_client('device', arch)
    for app in (simulator, device):
        run(sys.executable, ROOT / 'ci/ios_vpn_audit.py', app)
    run(sys.executable, ROOT / 'ci/mobile_smoke.py', 'ios', simulator)
    run('ditto', '-c', '-k', '--keepParent', device, destination / 'Weld-ios-arm64-unsigned.zip')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('platform', choices=['linux', 'win', 'mac', 'android', 'ios'])
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    platform = args.platform
    arch = 'x64' if platform in ('linux', 'win') else 'arm64'
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    toolchain(platform, arch)
    if platform == 'android':
        android(arch, destination)
    elif platform == 'ios':
        ios(arch, destination)
    else:
        desktop(platform, arch, destination)
    metadata = {'platform': platform, 'architecture': arch,
                'source': result('git', 'rev-parse', 'HEAD'),
                'chromium': PINS['chromium_revision'], 'type': 'candidate'}
    (destination / f'Weld-{platform}.json').write_text(json.dumps(metadata, indent=2) + '\n')


if __name__ == '__main__':
    main()
