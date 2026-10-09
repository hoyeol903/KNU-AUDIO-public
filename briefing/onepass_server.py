"""Private GPU API for one-pass, profile-specific briefing audio.

The browser submits only a date and ordered segment IDs. Scripts are loaded from
the trusted app manifest on this server; arbitrary text is never accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as calendar_date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import threading
import time
from typing import Callable
from urllib.parse import unquote, urlsplit

from collector.privacy import redact_text
from briefing.qwen_tts import AUDIO_POSTPROCESS, CACHE_VERSION, MODEL, SEED, VOICES, QwenTTS

ROOT = Path(__file__).resolve().parents[1]
MAX_REQUEST_SEGMENTS = 60
MAX_AUDIO_SECONDS = 150
MAX_AUDIO_BYTES = 4 * 1024 * 1024
MAX_REQUEST_BYTES = 16_384
MAX_HTTP_WORKERS = 12
HTTP_SOCKET_TIMEOUT_SECONDS = 10
JOB_TTL_SECONDS = 15 * 60
MAX_PENDING_JOBS = 3
POLL_SECONDS = 0.25
ID_RE = re.compile(r"^[A-Za-z0-9:_-]{1,128}$")


def _is_https_origin(origin: str) -> bool:
    try:
        parsed = urlsplit(origin)
        return bool(parsed.scheme == "https" and parsed.hostname and parsed.netloc
                    and parsed.username is None and parsed.password is None
                    and not parsed.path and not parsed.query and not parsed.fragment
                    and (parsed.port is None or 1 <= parsed.port <= 65535))
    except ValueError:
        return False


class OnePassError(ValueError):
    """Safe, user-displayable request rejection."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Settings:
    manifest_path: Path
    state_dir: Path
    allowed_origins: tuple[str, ...]
    turnstile_secret: str
    turnstile_hosts: tuple[str, ...]
    config_path: Path
    device: str = "cuda:0"
    tempo: float = 1.0
    worker_enabled: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        import yaml

        config_path = Path(os.environ.get("BRIEFING_CONFIG", ROOT / "config/briefing.yaml"))
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        origins = tuple(x.strip() for x in os.environ.get("BRIEFING_ALLOWED_ORIGINS", "").split(",") if x.strip())
        hosts = tuple(x.strip().lower() for x in os.environ.get("BRIEFING_TURNSTILE_HOSTS", "").split(",") if x.strip())
        if any(not _is_https_origin(origin) for origin in origins):
            raise ValueError("BRIEFING_ALLOWED_ORIGINS must contain HTTPS origins only")
        if any(not re.fullmatch(r"[a-z0-9.-]+", host) for host in hosts):
            raise ValueError("BRIEFING_TURNSTILE_HOSTS contains an invalid hostname")
        enabled = bool(origins and hosts and os.environ.get("BRIEFING_TURNSTILE_SECRET"))
        tempo = float(config.get("tempo", 1.0))
        if not math.isfinite(tempo) or not .5 <= tempo <= 2:
            raise ValueError("configured TTS tempo must be between 0.5 and 2")
        return cls(
            manifest_path=Path(os.environ.get("BRIEFING_MANIFEST", ROOT / "output/app/data/briefing/segments.json")),
            state_dir=Path(os.environ.get("BRIEFING_STATE_DIR", ROOT / ".onepass-state")),
            allowed_origins=origins,
            turnstile_secret=os.environ.get("BRIEFING_TURNSTILE_SECRET", ""),
            turnstile_hosts=hosts,
            config_path=config_path,
            device=os.environ.get("BRIEFING_TTS_DEVICE", "cuda:0"),
            tempo=tempo,
            worker_enabled=enabled,
        )


def parse_create_job(payload) -> tuple[str, list[str], str]:
    if not isinstance(payload, dict) or set(payload) != {"date", "segment_ids", "turnstile_token"}:
        raise OnePassError("request_invalid", "요청 형식이 올바르지 않아요.")
    date = payload.get("date")
    ids = payload.get("segment_ids")
    token = payload.get("turnstile_token")
    if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise OnePassError("request_invalid", "날짜 형식이 올바르지 않아요.")
    try:
        calendar_date.fromisoformat(date)
    except ValueError as exc:
        raise OnePassError("request_invalid", "날짜 형식이 올바르지 않아요.") from exc
    if (not isinstance(ids, list) or not 2 <= len(ids) <= MAX_REQUEST_SEGMENTS
            or any(not isinstance(value, str) or not ID_RE.fullmatch(value) for value in ids)
            or len(set(ids)) != len(ids)):
        raise OnePassError("request_invalid", "브리핑 구간 목록이 올바르지 않아요.")
    if not isinstance(token, str) or not token or len(token) > 4096:
        raise OnePassError("challenge_failed", "요청 확인을 완료하지 못했어요.")
    return date, ids, token


def load_selected_script(manifest_path: Path, date: str, segment_ids: list[str]) -> tuple[str, list[str]]:
    """Resolve an ordered selection against the published manifest, fail closed."""
    if not 2 <= len(segment_ids) <= MAX_REQUEST_SEGMENTS:
        raise OnePassError("selection_invalid", "선택한 브리핑 구간 수가 범위를 벗어났어요.")
    if any(not isinstance(value, str) or not ID_RE.fullmatch(value) for value in segment_ids):
        raise OnePassError("selection_invalid", "브리핑 구간 ID 형식이 올바르지 않아요.")
    if len(set(segment_ids)) != len(segment_ids):
        raise OnePassError("selection_invalid", "같은 브리핑 구간이 두 번 선택됐어요.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OnePassError("manifest_unavailable", "오늘 브리핑 자료를 읽지 못했어요.") from exc
    if not isinstance(manifest, dict) or manifest.get("date") != date or not isinstance(manifest.get("segments"), list):
        raise OnePassError("date_unavailable", "요청한 날짜의 브리핑 자료가 없어요.")
    by_id = {}
    for row in manifest["segments"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise OnePassError("manifest_invalid", "브리핑 자료 형식이 올바르지 않아요.")
        if row["id"] in by_id:
            raise OnePassError("manifest_invalid", "브리핑 자료에 중복 구간이 있어요.")
        by_id[row["id"]] = row
    rows = [by_id.get(segment_id) for segment_id in segment_ids]
    if any(row is None for row in rows):
        raise OnePassError("segment_unavailable", "선택한 브리핑 구간을 찾지 못했어요.")
    scripts = []
    for row in rows:
        script = row.get("script")
        if not isinstance(script, str) or not script.strip():
            raise OnePassError("script_unavailable", "대본이 없는 구간이 포함되어 있어요.")
        # A redacted placeholder must not be read aloud as if it were content.
        if "[개인정보 가림]" in script or redact_text(script) != script:
            raise OnePassError("privacy_blocked", "개인정보 확인이 필요한 대본이 포함되어 있어요.")
        scripts.append(script.strip())
    # Preserve the app's complete ordered selection. Notice length guidance is
    # applied during script generation; playback never drops selected sections.
    if segment_ids[0] not in {"greeting", "intro"} or segment_ids[-1] != "outro":
        raise OnePassError("selection_invalid", "인사와 마무리가 포함된 전체 브리핑을 선택해 주세요.")
    return " ".join(scripts), segment_ids


def cache_key(date: str, segment_ids: list[str], script: str, instruction: str, tempo: float) -> str:
    profile = {
        "version": CACHE_VERSION,
        "date": date,
        "segment_ids": segment_ids,
        "script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        "model": MODEL,
        "voice": VOICES["female"],
        "instruction": instruction,
        "seed": SEED,
        "tempo": tempo,
        "postprocess": AUDIO_POSTPROCESS,
    }
    return hashlib.sha256(json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def audio_duration(audio: bytes) -> float:
    from mutagen.mp3 import MP3
    import io
    return float(MP3(io.BytesIO(audio)).info.length)


class OnePassQueue:
    """SQLite-backed, single-worker queue and immutable audio cache."""

    def __init__(self, settings: Settings, *, synthesizer_factory: Callable[[], object] | None = None,
                 duration_reader: Callable[[bytes], float] = audio_duration,
                 now: Callable[[], float] = time.time):
        self.settings = settings
        self.settings.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.settings.state_dir, 0o700)
        self.audio_dir = self.settings.state_dir / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.audio_dir, 0o700)
        self.db_path = self.settings.state_dir / "jobs.sqlite3"
        self.synthesizer_factory = synthesizer_factory or self._default_synthesizer
        self.duration_reader = duration_reader
        self.now = now
        self._wake = threading.Condition()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._synthesizer = None
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY, cache_key TEXT NOT NULL, date TEXT NOT NULL,
                segment_ids TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL,
                updated REAL NOT NULL, expires REAL NOT NULL, audio_name TEXT,
                duration REAL, error_code TEXT
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS jobs_cache_status ON jobs(cache_key, status)")
            db.execute("CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created)")
            db.execute("UPDATE jobs SET status='queued', updated=? WHERE status='running'", (self.now(),))
        os.chmod(self.db_path, 0o600)
        self._prune_audio()

    def _default_synthesizer(self):
        import yaml
        config = yaml.safe_load(self.settings.config_path.read_text(encoding="utf-8"))
        instructions = config.get("tts", {}).get("instructions", {})
        tts = QwenTTS(device=self.settings.device, instructions=instructions)
        tts.verify(VOICES["female"], "female", MODEL)
        return tts

    def start(self):
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, name="onepass-tts-worker", daemon=True)
        self._worker.start()

    def stop(self, timeout=3):
        self._stop.set()
        with self._wake:
            self._wake.notify_all()
        if self._worker:
            self._worker.join(timeout)

    def submit(self, date: str, segment_ids: list[str]) -> tuple[dict, bool]:
        try:
            calendar_date.fromisoformat(date)
        except (TypeError, ValueError) as exc:
            raise OnePassError("request_invalid", "날짜 형식이 올바르지 않아요.") from exc
        script, ids = load_selected_script(self.settings.manifest_path, date, segment_ids)
        import yaml
        config = yaml.safe_load(self.settings.config_path.read_text(encoding="utf-8"))
        instruction = config.get("tts", {}).get("instructions", {}).get("female", "")
        tempo = self.settings.tempo
        key = cache_key(date, ids, script, instruction, tempo)
        now = self.now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM jobs WHERE expires <= ?", (now,))
            existing = db.execute("SELECT * FROM jobs WHERE cache_key=? AND expires>? ORDER BY created DESC LIMIT 1", (key, now)).fetchone()
            if existing and (existing["status"] in {"queued", "running"}
                             or existing["status"] == "complete" and self._audio_path(existing["audio_name"]).is_file()):
                db.commit()
                return dict(existing), False
            pending = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running') AND expires> ?", (now,)).fetchone()[0]
            if pending >= MAX_PENDING_JOBS:
                db.rollback()
                raise OnePassError("queue_full", "연속 음성 요청이 많아요. 잠시 후 다시 시도해 주세요.")
            job_id = secrets.token_urlsafe(24)
            db.execute("INSERT INTO jobs(job_id,cache_key,date,segment_ids,status,created,updated,expires) VALUES(?,?,?,?,?,?,?,?)",
                       (job_id, key, date, json.dumps(ids, ensure_ascii=False), "queued", now, now, now + JOB_TTL_SECONDS))
            db.commit()
        with self._wake:
            self._wake.notify()
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            return dict(row), True

    def _audio_path(self, name):
        if not name or Path(name).name != name:
            return self.audio_dir / "invalid"
        return self.audio_dir / name

    def get(self, job_id: str):
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row or row["expires"] <= self.now():
            return None
        return dict(row)

    def public_job(self, row: dict, public_base: str = "") -> dict:
        result = {"job_id": row["job_id"], "status": row["status"], "expires_at": int(row["expires"])}
        if row["status"] == "complete":
            result.update(duration_sec=row["duration"], audio_url=f"{public_base}/v1/jobs/{row['job_id']}/audio")
        elif row["status"] == "failed":
            result["error"] = row["error_code"] or "synthesis_failed"
        return result

    def audio_file(self, job_id: str) -> Path | None:
        row = self.get(job_id)
        if not row or row["status"] != "complete":
            return None
        path = self._audio_path(row["audio_name"])
        return path if path.is_file() else None

    def _next_job(self):
        now = self.now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM jobs WHERE expires <= ?", (now,))
            row = db.execute("SELECT job_id FROM jobs WHERE status='queued' AND expires>? ORDER BY created LIMIT 1", (now,)).fetchone()
            if not row:
                db.commit()
                return None
            changed = db.execute("UPDATE jobs SET status='running',updated=? WHERE job_id=? AND status='queued'", (now, row["job_id"])).rowcount
            db.commit()
            return row["job_id"] if changed else None

    def _run(self):
        while not self._stop.is_set():
            job_id = self._next_job()
            if not job_id:
                with self._wake:
                    self._wake.wait(timeout=POLL_SECONDS)
                continue
            try:
                self._process(job_id)
            except OnePassError as exc:
                self._finish_failed(job_id, exc.code)
            except Exception:
                # Never store or log exception text; it may contain local paths or source text.
                self._finish_failed(job_id, "synthesis_failed")

    def _process(self, job_id):
        row = self.get(job_id)
        if not row:
            return
        script, ids = load_selected_script(self.settings.manifest_path, row["date"], json.loads(row["segment_ids"]))
        import yaml
        config = yaml.safe_load(self.settings.config_path.read_text(encoding="utf-8"))
        instruction = config.get("tts", {}).get("instructions", {}).get("female", "")
        if cache_key(row["date"], ids, script, instruction, self.settings.tempo) != row["cache_key"]:
            raise RuntimeError("published script or voice profile changed while queued")
        if self._synthesizer is None:
            self._synthesizer = self.synthesizer_factory()
        audio = self._synthesizer.synthesize(script, VOICES["female"], MODEL, self.settings.tempo)
        if not isinstance(audio, bytes) or not audio:
            raise ValueError("invalid audio output")
        if len(audio) > MAX_AUDIO_BYTES:
            raise OnePassError("audio_too_large", "생성 음성이 처리 가능한 크기를 넘었어요.")
        duration = self.duration_reader(audio)
        if not math.isfinite(duration) or duration < 1:
            raise ValueError("invalid audio duration")
        if duration > MAX_AUDIO_SECONDS:
            raise OnePassError("audio_too_long", "선택한 브리핑이 한 번에 생성할 수 있는 길이를 넘었어요.")
        filename = row["cache_key"] + ".mp3"
        target = self._audio_path(filename)
        temp = self.audio_dir / (filename + ".tmp-" + secrets.token_hex(6))
        try:
            with temp.open("xb") as stream:
                os.chmod(temp, 0o600)
                stream.write(audio)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        with self._connect() as db:
            db.execute("UPDATE jobs SET status='complete',updated=?,audio_name=?,duration=?,error_code=NULL WHERE job_id=? AND status='running'",
                       (self.now(), filename, duration, job_id))
        self._prune_audio()

    def _finish_failed(self, job_id, code):
        with self._connect() as db:
            db.execute("UPDATE jobs SET status='failed',updated=?,error_code=? WHERE job_id=? AND status='running'",
                       (self.now(), code, job_id))

    def _prune_audio(self):
        now = self.now()
        with self._connect() as db:
            db.execute("DELETE FROM jobs WHERE expires <= ?", (now,))
            keep = {row[0] for row in db.execute("SELECT DISTINCT audio_name FROM jobs WHERE status='complete' AND audio_name IS NOT NULL")}
        for path in self.audio_dir.glob("*.mp3"):
            if path.name not in keep:
                path.unlink(missing_ok=True)


class TurnstileVerifier:
    """Fail-closed Cloudflare Turnstile verifier. The secret is environment-only."""

    def __init__(self, secret: str, hostnames: tuple[str, ...], *, post=None):
        self.secret, self.hostnames = secret, {h.lower() for h in hostnames}
        self.post = post

    def verify(self, token: str) -> bool:
        if not self.secret or not token:
            return False
        try:
            import requests
            response = (self.post or requests.post)(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": self.secret, "response": token}, timeout=5)
            data = response.json()
        except Exception:
            return False
        hostname = str(data.get("hostname", "")).lower()
        return bool(data.get("success") is True and data.get("action") == "onepass" and hostname in self.hostnames)


class OnePassAPI:
    """Small HTTP adapter kept dependency-free; synthesis remains in one worker thread."""

    def __init__(self, settings: Settings, manager: OnePassQueue, verifier: TurnstileVerifier):
        self.settings, self.manager, self.verifier = settings, manager, verifier

    def handle(self, method: str, target: str, headers: dict[str, str], body: bytes = b""):
        origin = headers.get("origin", "")
        out_headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}
        if origin:
            if origin not in self.settings.allowed_origins:
                return 403, out_headers, b'{"error":"origin_not_allowed"}'
            out_headers["Access-Control-Allow-Origin"] = origin
            out_headers["Vary"] = "Origin"
        elif method in {"POST", "OPTIONS"}:
            return 403, out_headers, b'{"error":"origin_not_allowed"}'
        if method == "OPTIONS":
            out_headers.update({"Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                                "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "600"})
            return 204, out_headers, b""
        if not self.settings.worker_enabled:
            return 503, out_headers, b'{"error":"onepass_disabled"}'
        path = urlsplit(target).path
        if method == "GET" and path == "/healthz":
            return self._json(200, {"status": "ready"}, out_headers)
        if method == "POST" and path == "/v1/jobs":
            if len(body) > MAX_REQUEST_BYTES:
                return self._json(413, {"error": "request_too_large"}, out_headers)
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                return self._json(415, {"error": "content_type_required"}, out_headers)
            try:
                payload = json.loads(body)
                request_date, ids, token = parse_create_job(payload)
            except (json.JSONDecodeError, OnePassError) as exc:
                code = exc.code if isinstance(exc, OnePassError) else "request_invalid"
                return self._json(400, {"error": code}, out_headers)
            if not self.verifier.verify(token):
                return self._json(403, {"error": "challenge_failed"}, out_headers)
            try:
                row, created = self.manager.submit(request_date, ids)
            except OnePassError as exc:
                return self._json(429 if exc.code == "queue_full" else 400, {"error": exc.code}, out_headers)
            return self._json(202, {**self.manager.public_job(row), "created": created}, out_headers)
        if method == "GET":
            parts = [unquote(x) for x in path.strip("/").split("/")]
            if len(parts) in {3, 4} and parts[:2] == ["v1", "jobs"]:
                job_id = parts[2]
                if not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", job_id):
                    return self._json(404, {"error": "job_not_found"}, out_headers)
                if len(parts) == 3:
                    row = self.manager.get(job_id)
                    if not row:
                        return self._json(404, {"error": "job_not_found"}, out_headers)
                    return self._json(200, self.manager.public_job(row), out_headers)
                if parts[3] == "audio":
                    audio = self.manager.audio_file(job_id)
                    if not audio:
                        return self._json(404, {"error": "audio_not_found"}, out_headers)
                    data = audio.read_bytes()
                    out_headers.update({"Content-Type": "audio/mpeg", "Content-Length": str(len(data)),
                                        "Cache-Control": "private, max-age=300",
                                        "Content-Disposition": 'inline; filename="briefing.mp3"'})
                    return 200, out_headers, data
        return self._json(404, {"error": "not_found"}, out_headers)

    @staticmethod
    def _json(status, payload, headers):
        headers = dict(headers)
        headers["Content-Type"] = "application/json; charset=utf-8"
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers["Content-Length"] = str(len(body))
        return status, headers, body


class BoundedHTTPServer(ThreadingHTTPServer):
    """Cap concurrent client sockets so slow headers cannot spawn unbounded threads."""

    daemon_threads = True
    request_queue_size = 24

    def __init__(self, server_address, RequestHandlerClass, *, max_workers=MAX_HTTP_WORKERS):
        super().__init__(server_address, RequestHandlerClass)
        self._request_slots = threading.BoundedSemaphore(max_workers)

    def process_request(self, request, client_address):
        if not self._request_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()

    def get_request(self):
        request, client_address = super().get_request()
        request.settimeout(HTTP_SOCKET_TIMEOUT_SECONDS)
        return request, client_address


def main():
    settings = Settings.from_env()
    manager = OnePassQueue(settings)
    verifier = TurnstileVerifier(settings.turnstile_secret, settings.turnstile_hosts)
    api = OnePassAPI(settings, manager, verifier)
    handler_type = type("OnePassHandler", (BaseHTTPRequestHandler,), {
        "do_GET": lambda self: self._dispatch(),
        "do_POST": lambda self: self._dispatch(),
        "do_OPTIONS": lambda self: self._dispatch(),
        "log_message": lambda self, fmt, *args: None,
        "_dispatch": lambda self: _handle_http(self, api),
    })
    bind = os.environ.get("BRIEFING_BIND", "127.0.0.1")
    port = int(os.environ.get("BRIEFING_PORT", "8000"))
    manager.start()
    try:
        with BoundedHTTPServer((bind, port), handler_type) as server:
            print(f"KNU one-pass API listening on {bind}:{port}; worker={'enabled' if settings.worker_enabled else 'disabled'}", flush=True)
            server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop()


def _handle_http(handler: BaseHTTPRequestHandler, api: OnePassAPI):
    try:
        length = int(handler.headers.get("Content-Length", "0"))
        if handler.headers.get("Transfer-Encoding"):
            status, headers, body = api._json(400, {"error": "transfer_encoding_unsupported"}, {})
        elif length < 0 or length > MAX_REQUEST_BYTES:
            status, headers, body = api._json(413, {"error": "request_too_large"}, {})
        else:
            body_in = handler.rfile.read(length) if handler.command == "POST" else b""
            status, headers, body = api.handle(handler.command, handler.path,
                                               {key.lower(): value for key, value in handler.headers.items()}, body_in)
    except Exception:
        status, headers, body = api._json(500, {"error": "internal_error"}, {})
    handler.send_response(status)
    for key, value in headers.items():
        handler.send_header(key, value)
    handler.end_headers()
    if handler.command != "HEAD" and body:
        handler.wfile.write(body)


if __name__ == "__main__":
    main()
