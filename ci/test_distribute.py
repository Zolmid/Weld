"""Exercise the release gate without credentials or platform build runners."""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from distribute import CANDIDATES, PINS, digest, extract, release_name, verify


class DistributionTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        env = patch.dict(os.environ, {'WELD_VERSION': 'v1.2.3', 'GITHUB_SHA': '1' * 40})
        env.start()
        self.addCleanup(env.stop)

    def prepare_packages(self):
        for platform in CANDIDATES:
            directory = self.root / f'weld-release-{platform}'
            directory.mkdir()
            artifact = directory / release_name(platform)
            artifact.write_text(f'example package for {platform}')
            receipt = {
                'platform': platform, 'source': os.environ['GITHUB_SHA'],
                'chromium': PINS['chromium_revision'], 'type': 'release',
                'file': artifact.name, 'size': artifact.stat().st_size, 'sha256': digest(artifact),
            }
            (directory / f'{platform}.json').write_text(json.dumps(receipt))

    def test_collects_five_verified_packages(self):
        self.prepare_packages()
        verify(self.root)
        checksum = self.root / 'verified/SHA256SUMS'
        self.assertEqual(len(checksum.read_text().splitlines()), 5)

    def test_rejects_modified_package(self):
        self.prepare_packages()
        artifact = self.root / 'weld-release-win' / release_name('win')
        artifact.write_text('different file')
        with self.assertRaisesRegex(SystemExit, 'invalid artifact checksum'):
            verify(self.root)

    def test_rejects_zip_path_escape(self):
        fixture = self.root / 'example.zip'
        with ZipFile(fixture, 'w') as archive:
            archive.writestr('../outside.txt', 'not part of package')
        target = self.root / 'inside'
        target.mkdir()
        with self.assertRaisesRegex(SystemExit, 'Unsafe archive member'):
            extract(fixture, target)
        self.assertFalse((self.root / 'outside.txt').exists())
