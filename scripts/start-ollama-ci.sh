#!/usr/bin/env bash
set -euo pipefail
# Official pinned release; CPU workflow excludes GPU libraries unless OLLAMA_GPU=true.
version=v0.35.1
runtime_dir="${RUNNER_TEMP:?}/knua-ollama"
mkdir -p "$runtime_dir"
if [[ "${OLLAMA_GPU:-false}" == "true" ]]; then
  curl --fail --location --retry 3 "https://github.com/ollama/ollama/releases/download/$version/ollama-linux-amd64.tar.zst" \
    | tar --zstd -x -C "$runtime_dir"
else
  curl --fail --location --retry 3 "https://github.com/ollama/ollama/releases/download/$version/ollama-linux-amd64.tar.zst" \
    | tar --zstd -x -C "$runtime_dir" --exclude='*cuda*' --exclude='*rocm*' --exclude='*vulkan*'
fi
export PATH="$runtime_dir/bin:$PATH"
printf '%s\n' "$runtime_dir/bin" >> "$GITHUB_PATH"
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
ollama serve > "$RUNNER_TEMP/ollama.log" 2>&1 &
ready=false
for attempt in {1..30}; do
  if curl --fail --silent http://127.0.0.1:11434/api/tags > /dev/null; then ready=true; break; fi
  sleep 2
done
if [ "$ready" != true ]; then cat "$RUNNER_TEMP/ollama.log"; exit 1; fi
model="$(python -c 'from briefing.build import read_yaml, ROOT; print(read_yaml(ROOT / "config/briefing.yaml")["slm"]["model"])')"
ollama pull "$model"
