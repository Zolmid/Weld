"""Fail closed on VPN payloads, Mach-O links, implementation markers or entitlements."""
import plistlib
import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN = re.compile(
    r'NetworkExtension|NE(?:VPN|PacketTunnel|TransparentProxy)|BraveVPN|VPNHelper|'
    r'PacketTunnel|wireguard|personal-vpn|vpn\.api|vpn\.configuration', re.I
)
MACHO = {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'}


def audit(app):
    executables = 0
    extensions = list(app.rglob('*.appex'))
    if not extensions:
        raise SystemExit('No expected iOS app extensions found.')
    for path in sorted(app.rglob('*')):
        if FORBIDDEN.search(path.name):
            raise SystemExit(f'VPN payload {path.relative_to(app)}')
        if not path.is_file() or path.is_symlink():
            continue
        if path.name == 'Info.plist' or path.suffix == '.entitlements':
            try:
                config = plistlib.loads(path.read_bytes())
            except plistlib.InvalidFileException:
                raise SystemExit(f'Cannot parse {path.relative_to(app)}')
            else:
                if FORBIDDEN.search(str(config)):
                    raise SystemExit(f'VPN configuration in {path.relative_to(app)}')
        with path.open('rb') as stream:
            magic = stream.read(4)
        if magic not in MACHO:
            continue
        executables += 1
        links = subprocess.check_output(['otool', '-L', path], text=True)
        symbols = subprocess.check_output(['nm', '-um', path], text=True, errors='replace')
        if FORBIDDEN.search(links + symbols):
            raise SystemExit(f'VPN linkage in {path.relative_to(app)}')
        signing = subprocess.run(['codesign', '-d', '--entitlements', ':-', path],
                                 capture_output=True, text=True)
        if signing.returncode == 0 and FORBIDDEN.search(signing.stdout):
            raise SystemExit(f'VPN entitlements in {path.relative_to(app)}')
    if executables < len(extensions) + 1:
        raise SystemExit('Incomplete Mach-O scan.')
    print(f'PASS iOS VPN audit of {executables} Mach-O files and {len(extensions)} extensions.')


if __name__ == '__main__':
    audit(Path(sys.argv[1]).resolve(strict=True))
