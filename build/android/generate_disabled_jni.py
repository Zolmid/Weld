# Copyright (c) 2026 The Brave Authors. All rights reserved.
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at https://mozilla.org/MPL/2.0/.

"""Build Java-only entry points for features with no native implementation."""

import argparse
from pathlib import Path
import re
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('sources', type=Path, nargs='+')
    args = parser.parse_args()

    entries = {}
    for source in args.sources:
        contents = source.read_text(encoding='utf-8')
        package = re.search(r'^package ([\w.]+);$', contents, re.MULTILINE)
        if not package or not re.search(r'\binterface Natives\b', contents):
            raise ValueError(f'Expected a package and Natives interface in {source}')
        name = source.stem
        entry = f'{package[1].replace(".", "/")}/{name}Jni.java'
        if entry in entries:
            raise ValueError(f'Duplicate JNI wrapper: {entry}')
        entries[entry] = f"""package {package[1]};

public final class {name}Jni {{
    private {name}Jni() {{}}

    public static {name}.Natives get() {{
        throw new UnsupportedOperationException("{name} is disabled in this build");
    }}
}}
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w') as jar:
        for name, contents in sorted(entries.items()):
            jar.writestr(zipfile.ZipInfo(name), contents, zipfile.ZIP_DEFLATED)


if __name__ == '__main__':
    main()
