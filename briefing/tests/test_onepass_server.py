import json
import time

import pytest

from briefing.onepass_server import (
    BoundedHTTPServer,
    MAX_REQUEST_SEGMENTS,
    OnePassAPI,
    OnePassError,
    OnePassQueue,
    Settings,
    TurnstileVerifier,
    _is_https_origin,
    cache_key,
    load_selected_script,
    parse_create_job,
)


def write_manifest(tmp_path, rows, *, day="2026-10-09"):
    path = tmp_path / "segments.json"
    path.write_text(json.dumps({"date": day, "segments": rows}, ensure_ascii=False), encoding="utf-8")
    return path


def settings(tmp_path, manifest, *, enabled=True):
    config = tmp_path / "briefing.yaml"
    config.write_text("tts:\n  instructions:\n    female: calm\ntempo: 1.0\n", encoding="utf-8")
    return Settings(manifest, tmp_path / "state", ("https://example.test",), "secret", ("example.test",),
                    config, device="cpu", tempo=1.0, worker_enabled=enabled)


def rows(*scripts):
    defaults = [("greeting", "안녕하세요."), ("intro", "오늘 날씨를 전해 드릴게요."),
                ("n1", "장학금 신청은 10월 12일까지 해요.", "notice"),
                ("meal", "오늘 학식은 준비되어 있어요."), ("outro", "좋은 하루 보내세요.")]
    chosen = scripts or defaults
    return [dict(id=row[0], script=row[1], **({"kind": row[2]} if len(row) > 2 else {})) for row in chosen]


def test_request_validation_rejects_malformed_or_unbounded_selection():
    with pytest.raises(OnePassError):
        parse_create_job({"date": "2026-02-30", "segment_ids": ["greeting", "outro"], "turnstile_token": "x"})
    with pytest.raises(OnePassError):
        parse_create_job({"date": "2026-10-09", "segment_ids": ["greeting", "greeting"], "turnstile_token": "x"})
    with pytest.raises(OnePassError):
        parse_create_job({"date": "2026-10-09", "segment_ids": ["greeting", "bad/id"], "turnstile_token": "x"})


def test_service_origins_require_exact_https_origin_shape():
    assert _is_https_origin("https://audio.example.test")
    assert _is_https_origin("https://audio.example.test:8443")
    assert not _is_https_origin("http://audio.example.test")
    assert not _is_https_origin("https://user:pass" + "@audio.example.test")
    assert not _is_https_origin("https://audio.example.test/path")
    assert not _is_https_origin("https://audio.example.test:99999")


def test_selection_preserves_order_and_rejects_wrong_date_missing_and_private_script(tmp_path):
    path = write_manifest(tmp_path, rows())
    script, selected = load_selected_script(path, "2026-10-09", ["greeting", "n1", "outro"])
    assert selected == ["greeting", "n1", "outro"]
    assert script == "안녕하세요. 장학금 신청은 10월 12일까지 해요. 좋은 하루 보내세요."
    with pytest.raises(OnePassError, match="날짜"):
        load_selected_script(path, "2026-10-08", ["greeting", "outro"])
    with pytest.raises(OnePassError, match="구간"):
        load_selected_script(path, "2026-10-09", ["unknown", "outro"])
    private = write_manifest(tmp_path, [dict(id="greeting", script="010-" + "0000" + "-" + "0000"), dict(id="outro", script="끝나요.")])
    with pytest.raises(OnePassError, match="개인정보"):
        load_selected_script(private, "2026-10-09", ["greeting", "outro"])


def test_selection_preserves_complete_long_script_and_never_omits_requested_segments(tmp_path):
    source = rows(("greeting", "안녕하세요."), ("intro", "날씨가 좋아요."),
                  ("n1", "첫 번째 행사는 10월 12일 15:00에 열려요." * 4, "notice"),
                  ("n2", "두 번째 공지는 신청해요." * 4, "notice"),
                  ("meal", "오늘 학식은 준비되어 있어요."), ("outro", "좋은 하루 보내세요."))
    path = write_manifest(tmp_path, source)
    requested = [row["id"] for row in source]
    script, selected = load_selected_script(path, "2026-10-09", requested)
    assert selected == requested
    assert len(script) > 140
    assert script == " ".join(row["script"] for row in source)


def test_selection_rejects_wrong_order_without_dropping_or_rewriting(tmp_path):
    source = rows(("greeting", "안녕하세요."), ("intro", "날씨가 맑아요."),
                  ("n1", "공지 신청을 해요." * 20, "notice"), ("outro", "좋은 하루."))
    path = write_manifest(tmp_path, source)
    script, selected = load_selected_script(path, "2026-10-09", [row["id"] for row in source])
    assert selected == [row["id"] for row in source]
    assert script.endswith("좋은 하루.")
    assert len(script) > 140


def test_selection_with_no_notices_keeps_opening_optional_section_and_outro(tmp_path):
    source = rows(("greeting", "안녕하세요."), ("intro", "날씨가 맑아요."),
                  ("meal", "오늘 학식은 준비되어 있어요."), ("outro", "좋은 하루 보내세요."))
    path = write_manifest(tmp_path, source)
    script, selected = load_selected_script(path, "2026-10-09", [row["id"] for row in source])
    assert selected == [row["id"] for row in source]
    assert script == " ".join(row["script"] for row in source)


def test_cache_key_covers_order_text_instruction_and_audio_profile():
    first = cache_key("2026-10-09", ["intro", "n1", "outro"], "hello", "calm", 1.0)
    assert first != cache_key("2026-10-09", ["intro", "outro", "n1"], "hello", "calm", 1.0)
    assert first != cache_key("2026-10-09", ["intro", "n1", "outro"], "changed", "calm", 1.0)
    assert first != cache_key("2026-10-09", ["intro", "n1", "outro"], "hello", "bright", 1.0)
    assert first != cache_key("2026-10-09", ["intro", "n1", "outro"], "hello", "calm", 1.25)


class FakeSynthesizer:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def synthesize(self, text, voice, model, tempo):
        self.calls.append((text, voice, model, tempo))
        if self.fail:
            raise RuntimeError("path or source details must not escape")
        return b"fake-mp3"


def wait_for(manager, job_id, wanted, timeout=2):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        row = manager.get(job_id)
        if row and row["status"] in wanted:
            return row
        time.sleep(0.01)
    raise AssertionError("background job did not finish")


def test_queue_synthesizes_once_caches_and_serves_atomic_audio(tmp_path):
    manifest = write_manifest(tmp_path, rows(("greeting", "안녕하세요."), ("intro", "날씨가 좋아요."),
                                             ("n1", "공지 신청을 해요.", "notice"), ("outro", "좋은 하루 보내세요.")))
    fake = FakeSynthesizer()
    manager = OnePassQueue(settings(tmp_path, manifest), synthesizer_factory=lambda: fake, duration_reader=lambda _: 15.2)
    try:
        manager.start()
        first, created = manager.submit("2026-10-09", ["greeting", "intro", "n1", "outro"])
        assert created
        row = wait_for(manager, first["job_id"], {"complete"})
        assert row["duration"] == 15.2
        assert manager.audio_file(row["job_id"]).read_bytes() == b"fake-mp3"
        assert fake.calls == [("안녕하세요. 날씨가 좋아요. 공지 신청을 해요. 좋은 하루 보내세요.", "Sohee",
                               "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", 1.0)]
        cached, created2 = manager.submit("2026-10-09", ["greeting", "intro", "n1", "outro"])
        assert not created2 and cached["job_id"] == row["job_id"]
        assert len(fake.calls) == 1
    finally:
        manager.stop()


def test_queue_synthesizes_every_selected_script_above_notice_prompt_length(tmp_path):
    long_notice = "신청 안내 문장을 원문대로 보존해요." * 8
    manifest = write_manifest(tmp_path, rows(("greeting", "안녕하세요."), ("intro", "날씨를 전해요."),
                                             ("n1", long_notice, "notice"), ("outro", "좋은 하루.")))
    fake = FakeSynthesizer()
    manager = OnePassQueue(settings(tmp_path, manifest), synthesizer_factory=lambda: fake, duration_reader=lambda _: 55.0)
    try:
        manager.start()
        submitted, created = manager.submit("2026-10-09", ["greeting", "intro", "n1", "outro"])
        assert created
        result = wait_for(manager, submitted["job_id"], {"complete"})
        assert result["duration"] == 55.0
        assert fake.calls[0][0] == " ".join(["안녕하세요.", "날씨를 전해요.", long_notice, "좋은 하루."])
        assert len(fake.calls[0][0]) > 140
    finally:
        manager.stop()


def test_queue_limits_jobs_and_hides_synthesis_exception(tmp_path):
    manifest = write_manifest(tmp_path, rows(("greeting", "안녕"), ("intro", "날씨"),
                                             ("n1", "첫 공지.", "notice"), ("n2", "둘 공지.", "notice"),
                                             ("n3", "셋 공지.", "notice"), ("meal", "학식."), ("outro", "끝")))
    manager = OnePassQueue(settings(tmp_path, manifest), synthesizer_factory=lambda: FakeSynthesizer(fail=True))
    try:
        selections = [["greeting", "intro", key, "outro"] for key in ("n1", "n2", "n3")]
        queued = [manager.submit("2026-10-09", ids)[0] for ids in selections]
        with pytest.raises(OnePassError, match="많아요"):
            manager.submit("2026-10-09", ["greeting", "intro", "meal", "outro"])
        manager.start()
        failed = wait_for(manager, queued[0]["job_id"], {"failed"})
        assert failed["error_code"] == "synthesis_failed"
        assert "path" not in json.dumps(manager.public_job(failed))
    finally:
        manager.stop()


def test_queue_returns_explicit_error_when_full_audio_exceeds_duration_limit(tmp_path):
    manifest = write_manifest(tmp_path, rows(("greeting", "안녕하세요."), ("intro", "날씨."), ("outro", "끝.")))
    manager = OnePassQueue(settings(tmp_path, manifest), synthesizer_factory=lambda: FakeSynthesizer(), duration_reader=lambda _: 151)
    try:
        manager.start()
        submitted, _ = manager.submit("2026-10-09", ["greeting", "intro", "outro"])
        failed = wait_for(manager, submitted["job_id"], {"failed"})
        assert failed["error_code"] == "audio_too_long"
        assert manager.audio_file(submitted["job_id"]) is None
    finally:
        manager.stop()


def test_queue_fails_closed_if_published_script_changes_before_synthesis(tmp_path):
    manifest = write_manifest(tmp_path, rows(("greeting", "안녕하세요."), ("intro", "날씨가 좋아요."), ("outro", "좋은 하루.")))
    fake = FakeSynthesizer()
    manager = OnePassQueue(settings(tmp_path, manifest), synthesizer_factory=lambda: fake, duration_reader=lambda _: 5)
    try:
        queued, _ = manager.submit("2026-10-09", ["greeting", "intro", "outro"])
        write_manifest(tmp_path, rows(("greeting", "안녕하세요."), ("intro", "날씨가 좋아요."), ("outro", "수정된 마무리.")))
        manager.start()
        failed = wait_for(manager, queued["job_id"], {"failed"})
        assert failed["error_code"] == "synthesis_failed"
        assert fake.calls == []
    finally:
        manager.stop()


class AllowVerifier:
    def verify(self, token):
        return token == "valid"


def test_api_cors_challenge_and_status_paths(tmp_path):
    manifest = write_manifest(tmp_path, rows(("greeting", "안녕하세요."), ("intro", "날씨가 좋아요."), ("outro", "좋은 하루.")))
    manager = OnePassQueue(settings(tmp_path, manifest, enabled=True), synthesizer_factory=lambda: FakeSynthesizer(), duration_reader=lambda _: 5)
    api = OnePassAPI(manager.settings, manager, AllowVerifier())
    try:
        denied = api.handle("POST", "/v1/jobs", {"origin": "https://evil.test", "content-type": "application/json"}, b"{}")
        assert denied[0] == 403
        no_content_type = api.handle("POST", "/v1/jobs", {"origin": "https://example.test"}, b"{}")
        assert no_content_type[0] == 415
        body = json.dumps({"date": "2026-10-09", "segment_ids": ["greeting", "intro", "outro"], "turnstile_token": "wrong"}).encode()
        rejected = api.handle("POST", "/v1/jobs", {"origin": "https://example.test", "content-type": "application/json"}, body)
        assert rejected[0] == 403 and json.loads(rejected[2])["error"] == "challenge_failed"
        body = json.dumps({"date": "2026-10-09", "segment_ids": ["greeting", "intro", "outro"], "turnstile_token": "valid"}).encode()
        accepted = api.handle("POST", "/v1/jobs", {"origin": "https://example.test", "content-type": "application/json"}, body)
        assert accepted[0] == 202 and accepted[1]["Access-Control-Allow-Origin"] == "https://example.test"
        job = json.loads(accepted[2])
        manager.start()
        wait_for(manager, job["job_id"], {"complete"})
        status = api.handle("GET", f"/v1/jobs/{job['job_id']}", {"origin": "https://example.test"})
        assert status[0] == 200 and json.loads(status[2])["status"] == "complete"
        audio = api.handle("GET", f"/v1/jobs/{job['job_id']}/audio", {"origin": "https://example.test"})
        assert audio[0] == 200 and audio[1]["Content-Type"] == "audio/mpeg" and audio[2] == b"fake-mp3"
    finally:
        manager.stop()


def test_turnstile_verifier_checks_action_hostname_and_secret():
    seen = []

    class Response:
        def __init__(self, body): self.body = body
        def json(self): return self.body

    verifier = TurnstileVerifier("private", ("example.test",), post=lambda url, **kwargs: (seen.append(kwargs) or Response({"success": True, "action": "onepass", "hostname": "example.test"})))
    assert verifier.verify("opaque") and seen[0]["timeout"] == 5
    assert not TurnstileVerifier("", ("example.test",), post=lambda *_a, **_k: None).verify("opaque")


def test_http_server_limits_concurrent_handlers_and_body_bytes():
    assert issubclass(BoundedHTTPServer, __import__("http.server").server.ThreadingHTTPServer)
    assert BoundedHTTPServer.request_queue_size <= 32
    assert MAX_REQUEST_SEGMENTS == 60
