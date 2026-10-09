import json
from types import SimpleNamespace

import pytest

from briefing import kaggle, kaggle_account as account, kaggle_recover

ROWS = [dict(slot='1', username='main', token='t1'), dict(slot='2', username='spare', token='t2')]


def pick(hours, minimum=3, readable=True, **kwargs):
    return account.choose(ROWS, minimum, quota=lambda row: hours[row['slot']], readable=lambda row, owner: readable,
                          exists=lambda row, slug: False, report=lambda text: None, **kwargs)['slot']


def test_primary_is_used_while_it_has_enough_quota_and_spare_only_when_it_has_more():
    assert pick({'1': 3.0, '2': 30.0}) == '1'
    assert pick({'1': 2.9, '2': 30.0}) == '2'
    assert pick({'1': 2.9, '2': 1.0}) == '1'
    assert pick({'1': None, '2': 5.0}) == '2'
    assert pick({'1': 1.0, '2': None}) == '1'


def test_spare_needs_access_to_the_shared_model_dataset():
    assert pick({'1': 0.5, '2': 30.0}, readable=False) == '1'


def test_resume_and_retry_stay_on_the_account_that_holds_the_saved_batches():
    assert pick({'1': 30.0, '2': 0.0}, owner='Spare') == '2'
    with pytest.raises(ValueError):
        pick({'1': 30.0, '2': 0.0}, owner='stranger')
    chosen = account.choose(ROWS, 3, previous_slug='knu-audio-briefing-9-1-b1', quota=lambda row: 30.0,
                            exists=lambda row, slug: row['slot'] == '2', report=lambda text: None)
    assert chosen['slot'] == '2'


def test_only_fully_configured_accounts_are_listed_and_quota_table_is_parsed():
    env = dict(KAGGLE_USERNAME_1='Main', KAGGLE_TOKEN_1='t1', KAGGLE_USERNAME_2='', KAGGLE_TOKEN_2='t2')
    assert account.accounts(env) == [dict(slot='1', username='main', token='t1')]
    table = 'resource  used    remaining  total   refreshAt\n--------  ------\nGPU       27.23h  2.77h      30.00h  2026-10-10T00:00:00\nTPU       0.00h   20.00h     20.00h  x\n'
    assert account.remaining_gpu_hours(ROWS[0], run=lambda row, *args: SimpleNamespace(returncode=0, stdout=table)) == 2.77
    assert account.remaining_gpu_hours(ROWS[0], run=lambda row, *args: SimpleNamespace(returncode=1, stdout='')) is None


def test_kernel_reads_the_model_from_the_primary_account_when_running_on_the_spare(tmp_path, monkeypatch):
    monkeypatch.setenv('KAGGLE_MODEL_OWNER', 'Main')
    kaggle.prepare_kernel(kaggle.ROOT, '2026-10-05', '1', '1', 'a' * 40, 'spare', tmp_path / 'kernel', tmp_path / 'expected.json')
    metadata = json.loads((tmp_path / 'kernel/kernel-metadata.json').read_text())
    assert metadata['id'].startswith('spare/') and metadata['dataset_sources'] == ['main/' + account.DATASET_SLUG]


def test_recover_uses_the_token_of_the_account_that_started_the_run(monkeypatch):
    monkeypatch.setenv('KAGGLE_USERNAME_1', 'main'); monkeypatch.setenv('KAGGLE_TOKEN_1', 't1')
    monkeypatch.setenv('KAGGLE_USERNAME_2', 'spare'); monkeypatch.setenv('KAGGLE_TOKEN_2', 't2')
    # activate가 바꾸는 값을 테스트가 끝나면 되돌리도록 먼저 등록한다.
    monkeypatch.setenv('KAGGLE_USERNAME', 'unset'); monkeypatch.setenv('KAGGLE_API_TOKEN', 'unset')
    account.activate('spare')
    import os
    assert os.environ['KAGGLE_USERNAME'] == 'spare' and os.environ['KAGGLE_API_TOKEN'] == 't2'
    with pytest.raises(ValueError):
        account.activate('stranger')
