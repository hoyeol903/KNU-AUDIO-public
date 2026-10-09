import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import unquote


class DownloadBgmTest(unittest.TestCase):
    def test_downloads_catalog_verified_originals_and_reuses_files(self):
        fake_mutagen = ModuleType('mutagen')
        fake_mp3 = ModuleType('mutagen.mp3')
        fake_mp3.MP3 = lambda path: SimpleNamespace(info=SimpleNamespace(length=123.456, sample_rate=44100))
        fake_mutagen.mp3 = fake_mp3
        with patch.dict(sys.modules, {'mutagen': fake_mutagen, 'mutagen.mp3': fake_mp3}):
            path = Path(__file__).resolve().parents[2] / 'tools' / 'download_bgm.py'
            spec = importlib.util.spec_from_file_location('download_bgm_under_test', path)
            downloader = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(downloader)
            with tempfile.TemporaryDirectory() as temp:
                downloader.DEST = Path(temp)
                downloader.TRACKS = downloader.TRACKS[:2]
                pieces = [{'title': title, 'filename': title + '.mp3', 'isrc': isrc}
                          for title, isrc in downloader.TRACKS]
                original = {row['filename']: b'ID3 original ' + row['filename'].encode() for row in pieces}
                calls = []

                def get(url):
                    calls.append(url)
                    if url.endswith('pieces.json'):
                        return json.dumps(pieces).encode(), 'application/json'
                    name = unquote(url.rsplit('/', 1)[-1])
                    return original[name], 'audio/mpeg'

                with patch.object(downloader, 'get', side_effect=get), patch.object(downloader.time, 'sleep'):
                    (downloader.DEST / 'previous-track.mp3').write_bytes(b'old')
                    downloader.main()
                    self.assertFalse((downloader.DEST / 'previous-track.mp3').exists())
                    self.assertEqual(len(calls), 3)
                    catalog = json.loads((downloader.DEST / 'catalog.json').read_text(encoding='utf-8'))
                    self.assertEqual([row['title'] for row in catalog], [row['title'] for row in pieces])
                    for row in catalog:
                        self.assertEqual((downloader.DEST / row['file']).read_bytes(), original[row['file']])
                        self.assertEqual(row['duration_sec'], 123.456)
                    calls.clear()
                    downloader.main()
                    self.assertEqual(calls, ['https://incompetech.com/music/royalty-free/pieces.json'])


if __name__ == '__main__':
    unittest.main()
