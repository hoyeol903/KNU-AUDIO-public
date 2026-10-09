# One-pass voice service (prototype)

The static GitHub Pages app cannot load Qwen3-TTS or keep a GPU process alive. This prototype adds an optional private API service for one C/Sohee pass over the selected, already-published segment scripts. It is deliberately disabled until a GPU host, HTTPS endpoint, and Turnstile configuration are provisioned and verified. `data/briefing-service.json` is optional; when it is missing or disabled, the app states that one-pass is unavailable and offers the existing segmented player.

The browser sends only the publication date and ordered segment IDs, plus a Turnstile token. It never sends a transcript, profile name, department string, or other profile data. The server loads scripts from its trusted `segments.json`, checks privacy redactions, and never logs request bodies or synthesis exception text. This produces a generic greeting; it does not speak a student's name. The existing segmented player remains a separate fallback and can retain its current browser-personalized greeting; it does not provide the same single-pass voice continuity. Full name personalization in the GPU request would require an explicit privacy/product decision and a safe voice path.

The service synthesizes the complete selected briefing, from greeting through outro, in app order with one Qwen call. It never truncates or silently omits a selected segment. The separate notice-generation prompt asks the SLM to keep each notice concise (up to 140 non-whitespace characters); that per-notice prompt guidance is not a cap on the assembled one-pass audio.

## Service requirements

- One long-lived Linux service on a GPU host with an NVIDIA CUDA device supported by the configured Qwen3-TTS 1.7B CustomVoice model, the repository's existing `requirements-tts.txt` environment, and FFmpeg. The worker serializes synthesis; this prototype does not scale across multiple workers or hosts.
- A stable HTTPS API origin, reverse proxy/TLS, process supervision, persistent writable storage for SQLite job state and temporary MP3 cache, and firewall rules that expose only the API. Do not expose the Python development server directly to the public internet.
- A Cloudflare Turnstile site key configured in the static `data/briefing-service.json` and its matching secret configured only as `BRIEFING_TURNSTILE_SECRET` on the GPU host. The server also needs `BRIEFING_TURNSTILE_HOSTS` and `BRIEFING_ALLOWED_ORIGINS` set to the exact production hostname and Pages origin. No site key or secret is committed by this prototype.
- `BRIEFING_MANIFEST` pointing to a reviewed, privacy-redacted publication manifest, `BRIEFING_CONFIG` pointing to the approved C/Sohee voice settings, `BRIEFING_STATE_DIR` on persistent storage, `BRIEFING_TTS_DEVICE=cuda:0`, and `BRIEFING_BIND`/`BRIEFING_PORT` behind the proxy.

Example static config shape (keep disabled until the endpoint is live):

```json
{
  "enabled": false,
  "api_base": "https://audio.example.invalid",
  "site_key": "replace-with-public-turnstile-site-key"
}
```

The API accepts up to 60 selected IDs and limits each generated file to 150 seconds and 4 MiB; exceeding a synthesis bound fails the whole request and never removes selected chapters. It admits at most three active/queued jobs and retains cache entries for 15 minutes. A single GPU worker processes one job at a time. If the model cannot complete a very long selection, or the returned audio exceeds 150 seconds/4 MiB, the entire one-pass request fails with an explicit error; selected segments are never silently removed. Local tests use a fake synthesizer and exercise the API object directly. This sandbox does not permit binding a loopback socket, so HTTP-listener integration and real inference remain unverified. There is no measured throughput or load test for this prototype, and its three-job queue is intentionally too small to promise service to hundreds of simultaneous users. Before a broad release, choose a host with enough GPU workers, a shared transactional queue/cache, admission limits, and load-test capacity using public/redacted sample scripts. Do not estimate student wait time from the sample alone. Turnstile, origin checks, randomized job IDs, bounded HTTP handler threads, request-size/time limits, SQLite-backed deduplication, and atomic MP3 writes reduce abuse and partial-file exposure; they do not replace production monitoring, abuse review, backup, or a host-provider security review.

## Local tests

The fake synthesizer tests cover complete ordered manifest selection (including scripts longer than the per-notice prompt guidance), privacy rejection, cache identity, queue limits, failures, CORS, and status/audio responses without loading a model or opening a network listener. The browser helper tests use fake fetch and Turnstile providers. They do not validate GPU inference or a live HTTPS/Turnstile endpoint. A GPU endpoint, public HTTPS URL, Turnstile keys/hostname settings, deployed service config, real model synthesis, and an app playback test are not provisioned or validated by this code-only change. Do not enable the service in production until the exact deployed SHA passes those checks.
