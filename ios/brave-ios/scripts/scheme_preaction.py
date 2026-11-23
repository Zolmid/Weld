#!/usr/bin/env python3
# Copyright (c) 2024 The Brave Authors. All rights reserved.
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at https://mozilla.org/MPL/2.0/.
"""
Actions to run before every build in the brave-ios Xcode project
"""

import argparse
import os
import platform
import sys
import inspect
import plistlib
import json
import subprocess
from pathlib import Path

this_dir = os.path.dirname(os.path.abspath(__file__))
brave_root_dir = os.path.join(
    os.path.join(os.path.join(this_dir, os.pardir), os.pardir), os.pardir
)
src_dir = os.path.join(brave_root_dir, os.pardir)
scripts_dir = os.path.join(brave_root_dir, 'build', 'commands', 'scripts')

sys.path.append(os.path.join(src_dir, 'third_party', 'node'))

import node


def main():
    description = 'Runs actions before each build'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        '--configuration',
        nargs='?',
        default='Debug',
        help='Specify which configuration to build.',
    )
    parser.add_argument(
        '--platform_name', nargs='?', help='Specify which platform to build.'
    )
    parser.add_argument(
        '--only_update_symlink',
        action='store_true',
        default=False,
        help='Only update the symlink',
    )

    options = parser.parse_args()

    output_dir = BuildOutputDirectory(
        options.configuration, options.platform_name
    )
    target_arch = (
        'arm64'
        if platform.processor() == 'arm' or options.platform_name == 'iphoneos'
        else 'x64'
    )
    target_environment = (
        'simulator'
        if (options.platform_name == 'iphonesimulator')
        else 'device'
    )

    # Ensure node is executed from the brave root directory, node.RunNode offers
    # no option for passing in a custom working directory. This is required for
    # paths in the webpack config to be parsed correctly.
    os.chdir(brave_root_dir)

    prebuilt_core_dir = os.environ.get('BRAVE_IOS_PREBUILT_CORE_DIR')
    slim = os.environ.get('BRAVE_IOS_SLIM', '0')
    if slim not in ('0', '1'):
        raise ValueError('BRAVE_IOS_SLIM must be 0 or 1')
    if slim == '1' and not prebuilt_core_dir:
        raise ValueError('BRAVE_IOS_SLIM=1 requires BRAVE_IOS_PREBUILT_CORE_DIR')
    if prebuilt_core_dir:
        UsePrebuiltCore(prebuilt_core_dir, options.platform_name, target_arch, slim == '1')
        if not options.only_update_symlink:
            PackJavaScript()
        return

    if options.only_update_symlink:
        # If we're choosing to only update the symlink we should validate
        # that the resulting symlink will point to a valid folder
        if not os.path.exists(output_dir):
            err = inspect.cleandoc(f'''
            Expected out directory for chosen build doesn't exist:

            {output_dir}

            Ensure you run the correct `pnpm run build` command prior to building
            ''')
            raise Exception(err)
    else:
        BuildCore(options.configuration, target_arch, target_environment)
        PackJavaScript()
    ValidateCoreConfiguration(Path(output_dir), options.platform_name, target_arch, False)
    UpdateSymlink(options.configuration, target_arch, target_environment)


def BuildOutputDirectory(config, platform_name):
    directory_name = 'ios_%s' % config
    if platform.processor() == 'arm' or platform_name == 'iphoneos':
        directory_name += '_arm64'
    if platform_name == 'iphonesimulator':
        directory_name += '_simulator'
    return os.path.normpath(os.path.join(src_dir, 'out', directory_name))


SLIM_FLAGS = (
    'enable_ai_chat', 'enable_local_ai', 'enable_brave_wallet',
    'enable_brave_rewards', 'enable_brave_ads', 'enable_brave_vpn_v1',
    'enable_brave_vpn_v2',
)


def ValidateCoreConfiguration(output_dir, platform_name, target_arch, slim):
    args_files = [output_dir / 'args.gn', output_dir / 'args_generated.gni']
    # GN leaves args.xcconfig unchanged when its contents match the new graph.
    if not (output_dir / 'args.xcconfig').is_file():
        raise FileNotFoundError(output_dir / 'args.xcconfig')
    if max(path.stat().st_mtime_ns for path in args_files) > (
        output_dir / 'build.ninja'
    ).stat().st_mtime_ns:
        raise ValueError(f'{output_dir}: GN configuration is stale')

    gn = Path(src_dir, 'buildtools', 'mac', 'gn')
    result = subprocess.run(
        [str(gn), 'args', str(output_dir), '--list', '--json'],
        cwd=src_dir, check=True, capture_output=True, text=True,
    )
    args = {entry['name']: entry for entry in json.loads(result.stdout)}
    def value(name):
        entry = args[name]
        return entry.get('current', entry['default'])['value']

    expected_environment = 'simulator' if platform_name == 'iphonesimulator' else 'device'
    if (value('target_os') != '"ios"' or value('target_cpu') != f'"{target_arch}"'
            or value('target_environment') != f'"{expected_environment}"'):
        raise ValueError(f'{output_dir}: GN target does not match {platform_name}/{target_arch}')
    if slim:
        for flag in SLIM_FLAGS:
            current = args[flag].get('current', {})
            if current.get('value') != 'false' or Path(current.get('file', '')).name not in (
                'args.gn', 'args_generated.gni'
            ):
                raise ValueError(f'{output_dir}: slim requires explicit {flag}=false')
    elif any(value(flag) != 'true' for flag in ('enable_ai_chat', 'enable_brave_wallet')):
        raise ValueError(f'{output_dir}: AI and wallet require BRAVE_IOS_SLIM=1')


def UsePrebuiltCore(directory, platform_name, target_arch, slim):
    """Select an existing GN output without rebuilding a different variant."""
    output_root = Path(src_dir, 'out').resolve()
    output_dir = (output_root / directory).resolve()
    if output_root not in output_dir.parents:
        raise ValueError('BRAVE_IOS_PREBUILT_CORE_DIR must be inside src/out')

    package = output_dir / 'BraveCore.xcframework'
    with (package / 'Info.plist').open('rb') as info_file:
        libraries = plistlib.load(info_file)['AvailableLibraries']
    simulator = platform_name == 'iphonesimulator'
    binaries = [
        package / library['LibraryIdentifier'] / library['BinaryPath']
        for library in libraries
        if library['SupportedPlatform'] == 'ios'
        and library.get('SupportedPlatformVariant') == (
            'simulator' if simulator else None
        )
        and target_arch in library['SupportedArchitectures']
    ]
    if platform_name not in ('iphoneos', 'iphonesimulator') or not any(
        binary.is_file() for binary in binaries
    ):
        raise ValueError(f'{package} has no binary for {platform_name}/{target_arch}')
    if any(binary.stat().st_mtime_ns < max(
        (output_dir / name).stat().st_mtime_ns
        for name in ('args.gn', 'args_generated.gni')
    ) for binary in binaries if binary.is_file()):
        raise ValueError(f'{package}: binary predates GN arguments')
    for filename in ('args.xcconfig', 'NalaAssets.xcframework',
                     'PartitionAllocSupport.xcframework'):
        if not (output_dir / filename).exists():
            raise FileNotFoundError(output_dir / filename)

    ValidateCoreConfiguration(output_dir, platform_name, target_arch, slim)

    current_link = output_root / 'ios_current_link'
    if os.environ.get('BRAVE_IOS_REQUIRE_SELECTED_CORE') == '1' and (
        not current_link.is_symlink() or current_link.resolve() != output_dir
    ):
        raise ValueError('Select the prebuilt core before starting Xcode; package and xcconfig loading precede the scheme preaction')
    if current_link.is_symlink() and current_link.resolve() == output_dir:
        return
    if current_link.exists() and not current_link.is_symlink():
        raise ValueError(f'Preserve the bootstrap directory at {current_link} before selecting a prebuilt core')
    temporary_link = output_root / f'.ios_current_link.{os.getpid()}'
    temporary_link.symlink_to(output_dir)
    temporary_link.replace(current_link)


def UpdateSymlink(config, target_arch, target_environment):
    """Updates the 'ios_current_link' symlink"""
    cmd_args = [
        os.path.join(scripts_dir, 'iosCommands.js'),
        'ios_update_current_link',
        config,
        '--target_arch',
        target_arch,
        '--target_environment',
        target_environment,
    ]
    node.RunNode(cmd_args)


def PackJavaScript():
    """Bundles the iOS user script JavaScript resources via webpack"""
    webpack_cli = os.path.join(
        brave_root_dir, 'node_modules', 'webpack-cli', 'bin', 'cli.js'
    )
    webpack_config = os.path.join(
        brave_root_dir, 'ios', 'brave-ios', 'webpack.config.js'
    )
    node.RunNode([webpack_cli, '--config', webpack_config])


def BuildCore(config, target_arch, target_environment):
    """Generates and builds the BraveCore.framework"""
    cmd_args = [
        os.path.join(scripts_dir, 'build.ts'),
        config,
        '--target_os',
        'ios',
        '--target_arch',
        target_arch,
        '--target_environment',
        target_environment,
    ]
    node.RunNode(cmd_args)


if __name__ == '__main__':
    sys.exit(main())
