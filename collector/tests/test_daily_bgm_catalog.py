import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.daily_bgm import export


class DailyBgmCatalogTest(unittest.TestCase):
    def test_selected_track_exports_credits_and_rejects_bad_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output = root / 'source', root / 'output'
            source.mkdir()
            audio = b'original mp3 bytes for selector test'
            (source / 'Easy Lemon.mp3').write_bytes(audio)
            catalog = [{'file': 'Easy Lemon.mp3', 'title': 'Easy Lemon', 'artist': 'Kevin MacLeod',
                        'source_url': 'https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1200076',
                        'license': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
                        'attribution': 'Easy Lemon — Kevin MacLeod', 'changes': '없음', 'isrc': 'USUAN1200076',
                        'sha256': hashlib.sha256(audio).hexdigest()}]
            (source / 'catalog.json').write_text(json.dumps(catalog), encoding='utf-8')
            metadata = export(output, source_dir=source, day='2026-10-06')
            self.assertEqual(metadata['title'], 'Easy Lemon')
            self.assertEqual(metadata['license'], 'CC BY 4.0')
            self.assertEqual((output / metadata['audio']).read_bytes(), audio)
            catalog[0]['sha256'] = '0' * 64
            (source / 'catalog.json').write_text(json.dumps(catalog), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                export(output, source_dir=source, day='2026-10-06')


if __name__ == '__main__':
    unittest.main()
