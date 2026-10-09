import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from tools.update_meals import main
from collector.store import SEOUL


class UpdateMealsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 10, 6, 10, 0, tzinfo=SEOUL)
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def runner(self, args, **kwargs):
        self.calls.append(args)
        git_args = args[1:] if args[0] == 'git' else None
        if git_args == ['remote', 'get-url', 'origin']:
            return subprocess.CompletedProcess(args, 0, 'https://github.com/hoyeol903/KNU-AUDIO.git\n', '')
        if git_args == ['status', '--porcelain', '--untracked-files=all']:
            return subprocess.CompletedProcess(args, 0, '', '')
        if git_args == ['symbolic-ref', 'refs/remotes/origin/HEAD']:
            return subprocess.CompletedProcess(args, 0, 'refs/remotes/origin/main\n', '')
        if git_args and git_args[:2] == ['diff', '--cached'] and '--quiet' in git_args:
            return subprocess.CompletedProcess(args, 1, '', '')
        if git_args and git_args[:2] == ['diff', '--cached']:
            return subprocess.CompletedProcess(args, 0, f'data/raw/{self.now.date()}/context.json\noutput/app/index.html\n', '')
        if args[0] == 'gh' and args[1:3] == ['auth', 'status']:
            return subprocess.CompletedProcess(args, 0, '', '')
        if args[0] == 'gh' and args[1:3] == ['pr', 'create']:
            self.pr_args = args
            self.pr_body = Path(args[-1]).read_text(encoding='utf-8')
            return subprocess.CompletedProcess(args, 0, 'https://github.com/hoyeol903/KNU-AUDIO/pull/12\n', '')
        if args[0] == 'git':
            return subprocess.CompletedProcess(args, 0, '', '')
        if args[1:4] == ['-m', 'collector.daily_sources', '--meals-only']:
            path = self.root / 'data/raw' / str(self.now.date()) / 'context.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                'date': str(self.now.date()), 'collected_at': self.now.isoformat(),
                'channels': [{'meals': []}],
                'meal_week': {'meal-46': [{'date': str(self.now.date()), 'meals': [{'menu': ['밥']}]}]},
                'errors': [{'source': 'meal-46', 'message': '오늘 메뉴 미게시'}],
            }), encoding='utf-8')
            return subprocess.CompletedProcess(args, 1, '', 'partial')
        if args[1:3] == ['-m', 'collector.export_app']:
            self.root.joinpath('output/app').mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(args, 0, '', '')
        raise AssertionError(args)

    def test_dirty_tree_stops_before_collection(self):
        original = self.runner

        def dirty(args, **kwargs):
            self.calls.append(args)
            if args[0] == 'git' and args[1:2] == ['status']:
                return subprocess.CompletedProcess(args, 0, ' M README.md\n', '')
            if args[0] == 'gh':
                return subprocess.CompletedProcess(args, 0, '', '')
            return original(args, **kwargs)

        self.assertEqual(main(self.root, dirty, lambda: self.now), 1)
        self.assertFalse(any('collector.daily_sources' in call for call in self.calls))

    def test_old_context_does_not_survive_failed_collection(self):
        path = self.root / 'data/raw' / str(self.now.date()) / 'context.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'date': str(self.now.date()), 'collected_at': self.now.isoformat(),
                                    'channels': [{'meals': [{'menu': ['stale']}]}], 'meal_week': {}, 'errors': []}))
        original = self.runner

        def failed(args, **kwargs):
            self.calls.append(args)
            if args[1:4] == ['-m', 'collector.daily_sources', '--meals-only']:
                return subprocess.CompletedProcess(args, 1, '', 'failed')
            return original(args, **kwargs)

        # The same timestamp models a pre-existing report; the collector never refreshes it.
        later = lambda: self.now.replace(second=self.now.second + 1)
        self.assertEqual(main(self.root, failed, later), 1)
        self.assertFalse(any(call[:2] == ['git', 'push'] for call in self.calls))
        self.assertFalse(any(call[0] == 'gh' and call[1:3] == ['pr', 'create'] for call in self.calls))

    def test_partial_meal_data_exports_allowlisted_files_and_opens_pr(self):
        self.assertEqual(main(self.root, self.runner, lambda: self.now), 0)
        self.assertIn('오늘 메뉴 미게시', self.pr_body)
        self.assertIn('--repo', self.pr_args)
        self.assertFalse(any('merge' in call for call in self.calls))
        add = next(call for call in self.calls if call[:2] == ['git', 'add'])
        self.assertEqual(add[3:], ['data/raw/2026-10-06/context.json', 'output/app'])

    def test_export_failure_stops_before_push(self):
        original = self.runner

        def fail_export(args, **kwargs):
            if args[1:3] == ['-m', 'collector.export_app']:
                return subprocess.CompletedProcess(args, 2, '', 'failed')
            return original(args, **kwargs)

        self.assertEqual(main(self.root, fail_export, lambda: self.now), 1)
        self.assertFalse(any(call[:2] == ['git', 'push'] for call in self.calls))


if __name__ == '__main__':
    unittest.main()
