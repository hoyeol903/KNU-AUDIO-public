import json
from copy import deepcopy
import pytest
from collector import store


def notice(**changes):
    row = dict(source_board_id="korean-academic", source_post_id="101",
               channel_ids=["notice-korean"], title="수강 안내",
               url="https://example.com/board/101", posted_at="2026-09-30",
               deadline=None, body="원문 수강 안내", body_status="text")
    return dict(row, **changes)


def test_duplicate_channels_and_repeated_run(tmp_path):
    path = tmp_path / "notices.json"
    assert store.load_notices(path) == []
    rows = [notice(), notice(channel_ids=["notice-college"])]
    result = store.upsert_notices(rows, path=path, checked_at="2026-09-30T05:37:00+09:00")
    assert result["new"] == ["korean-academic:101"]
    original = path.read_bytes()
    assert store.upsert_notices(rows, path=path, checked_at="2026-09-30T05:37:00+09:00")["unchanged"] == result["new"]
    assert path.read_bytes() == original
    assert store.load_notices(path)[0]["channel_ids"] == ["notice-college", "notice-korean"]


def test_revision_preserves_first_seen_and_unrelated_notice(tmp_path):
    path = tmp_path / "notices.json"
    store.upsert_notices([notice(), notice(source_post_id="102")], path=path,
                         checked_at="2026-09-30T05:37:00+09:00")
    before = store.load_notices(path)
    changed = notice(body="원문 변경 안내", deadline="2026-10-02")
    result = store.upsert_notices([changed], path=path, checked_at="2026-10-01T05:37:00+09:00")
    after = store.load_notices(path)
    assert result["updated"] == ["korean-academic:101"]
    assert after[0]["first_seen_at"] == before[0]["first_seen_at"]
    assert after[0]["last_checked_at"] == "2026-10-01T05:37:00+09:00"
    assert after[0]["content_hash"] != before[0]["content_hash"]
    assert after[1] == before[1]


@pytest.mark.parametrize("bad", [
    notice(deadline="2026-02-30"), notice(body=""), notice(channel_ids=[]),
    notice(url="javascript:alert(1)"), notice(source_board_id="board:ambiguous"),
])
def test_invalid_batch_does_not_partially_save(tmp_path, bad):
    path = tmp_path / "notices.json"
    store.upsert_notices([notice()], path=path, checked_at="2026-09-30T05:37:00+09:00")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        store.upsert_notices([notice(source_post_id="102"), bad], path=path)
    assert path.read_bytes() == before


def test_corrupt_file_is_not_silently_reset(tmp_path):
    path = tmp_path / "notices.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        store.upsert_notices([notice()], path=path)
    assert path.read_text() == "{broken"


def test_replace_failure_preserves_original_and_cleans_temp(tmp_path, monkeypatch):
    path = tmp_path / "notices.json"
    store.upsert_notices([notice()], path=path, checked_at="2026-09-30T05:37:00+09:00")
    before = path.read_bytes()
    def fail(*args):
        raise OSError("교체 실패")
    monkeypatch.setattr(store.os, "replace", fail)
    with pytest.raises(OSError):
        store.upsert_notices([notice(body="새 본문")], path=path)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_conflicts_and_stale_runs_are_rejected(tmp_path):
    path = tmp_path / "notices.json"
    store.upsert_notices([notice()], path=path, checked_at="2026-10-01T05:37:00+09:00")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        store.upsert_notices([notice(), notice(body="상충")], path=path)
    with pytest.raises(ValueError):
        store.upsert_notices([notice()], path=path, checked_at="2026-09-30T05:37:00+09:00")
    assert path.read_bytes() == before


def test_body_states_and_tampered_hash(tmp_path):
    path = tmp_path / "notices.json"
    store.upsert_notices([notice(body=None, body_status="image-only"),
                         notice(source_post_id="102", body="", body_status="empty")], path=path)
    rows = store.load_notices(path)
    assert rows[0]["body"] is None and rows[1]["body"] == ""
    damaged = deepcopy(rows)
    damaged[0]["title"] = "해시와 다른 제목"
    # 손상 상황을 만드는 테스트만 store를 거치지 않고 파일을 작성한다.
    path.write_text(json.dumps(damaged), encoding="utf-8")
    with pytest.raises(ValueError, match="해시"):
        store.load_notices(path)


def test_wrong_timezone_never_creates_file(tmp_path):
    path = tmp_path / "notices.json"
    with pytest.raises(ValueError, match="Asia/Seoul"):
        store.upsert_notices([notice()], path=path, checked_at="2026-09-30T05:37:00+00:00")
    assert not path.exists()
