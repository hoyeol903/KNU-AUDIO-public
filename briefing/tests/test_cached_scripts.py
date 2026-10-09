from copy import deepcopy
import json
from unittest.mock import Mock

import pytest
import yaml

from briefing import content, kaggle_worker, slm


CONFIG = {'model': 'qwen3:4b'}


def row(title='모집'):
    return dict(id=title, kind='notice', generation='slm', title=title,
                source_text='신청은 5일 마감이에요.', reference='')


def save_scripts(cache, *, revised=False):
    rows = [row(), row('추가 모집')]
    provider = Mock()
    provider.identity.return_value = 'qwen3:4b:original-digest'
    provider.generate.side_effect = ['6일 마감이에요.', '5일 마감이에요.'] * 2 if revised else None
    provider.generate.return_value = '5일 마감이에요.'
    slm.generate_segments(rows, provider, cache, cache / 'report.json')
    return rows


def worker_root(tmp_path, monkeypatch, rows):
    root = tmp_path / 'source'
    (root / 'config').mkdir(parents=True)
    (root / 'data').mkdir()
    (root / 'config/briefing.yaml').write_text(yaml.safe_dump({'slm': CONFIG}))
    (root / 'config/events.yaml').write_text('[]')
    (root / 'data/channels.yaml').write_text('[]')
    monkeypatch.setattr(content, 'create_segments', lambda *args: (deepcopy(rows), []))
    prepare = Mock()
    monkeypatch.setattr(kaggle_worker.subprocess, 'run', prepare)
    return root, prepare


@pytest.mark.parametrize('revised', [False, True])
def test_complete_cached_scripts_skip_ollama_and_keep_review_policy(tmp_path, monkeypatch, revised):
    cache = tmp_path / 'cache'
    rows = save_scripts(cache, revised=revised)
    root, prepare = worker_root(tmp_path, monkeypatch, rows)
    provider = kaggle_worker.prepare_slm(root, {}, cache, tmp_path, {}, tmp_path / 'github-path')
    prepare.assert_not_called()
    assert provider.identity() == 'qwen3:4b:original-digest'
    monkeypatch.setattr(slm.requests.Session, 'get', Mock(side_effect=AssertionError('AI 접속 금지')))
    monkeypatch.setattr(slm.requests.Session, 'post', Mock(side_effect=AssertionError('AI 접속 금지')))
    assert slm.generate_segments(rows, provider, cache, tmp_path / 'report.json')
    assert all(r['review']['status'] == 'passed' for r in rows)


@pytest.mark.parametrize('change', ['missing', 'input', 'invalid', 'model', 'prompt', 'review-version'])
def test_missing_or_incompatible_script_prepares_ollama(tmp_path, monkeypatch, change):
    cache = tmp_path / 'cache'
    rows = save_scripts(cache)
    path = next((cache / 'scripts').glob('*.json'))
    if change == 'missing':
        path.unlink()
    elif change == 'input':
        rows[0]['source_text'] = '신청은 7일 마감이에요.'
    elif change == 'invalid':
        saved = json.loads(path.read_text()); saved['script'] = '9일 마감이에요.'
        path.write_text(json.dumps(saved))
    elif change == 'model':
        monkeypatch.setitem(CONFIG, 'model', 'different-model')
    elif change == 'prompt':
        monkeypatch.setattr(slm, 'PROMPT_VERSION', 'changed')
    else:
        monkeypatch.setattr(slm, 'VERSION', 'changed')
    root, prepare = worker_root(tmp_path, monkeypatch, rows)
    assert kaggle_worker.prepare_slm(root, {}, cache, tmp_path, {}, tmp_path / 'github-path') is None
    prepare.assert_called_once()
    assert prepare.call_args.args[0][0] == 'bash'


def test_fixed_scripts_need_no_model_and_missing_cache_fails_explicitly(tmp_path):
    fixed = dict(row(), generation='fixed', script='학교 소식이에요.')
    provider = slm.cached_provider([fixed], CONFIG, tmp_path)
    assert provider is not None
    slm.generate_segments([fixed], provider, tmp_path, tmp_path / 'report.json')
    with pytest.raises(RuntimeError, match='캐시가 없어졌습니다'):
        provider.generate({}, [])
