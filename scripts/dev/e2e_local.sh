#!/usr/bin/env bash
# Build, start a fresh local stack, run every end-to-end test, stop the stack. Windows (Git Bash) and Linux.
# The tests run against the installed Chrome unless E2E_CHANNEL is set to another channel.
set -u
cd "$(dirname "$0")/../.."
PY=.venv/bin/python; [ -x "$PY" ] || PY=.venv/Scripts/python
mkdir -p .dev
stop() {
  for port in 3000 8000 54321; do
    if command -v taskkill >/dev/null; then
      netstat -ano | grep ":$port " | grep LISTEN | awk '{print $5}' | sort -u | while read -r pid; do taskkill //F //PID "$pid" >/dev/null 2>&1; done
    else
      fuser -k "$port/tcp" >/dev/null 2>&1
    fi
  done
}
stop
(cd frontend && npm run build >../.dev/build.log 2>&1) || { tail -20 .dev/build.log; exit 1; }
"$PY" -u -m scripts.dev.run_local --reset >.dev/api.log 2>&1 &
(cd frontend && npm start >../.dev/web.log 2>&1) &
for _ in $(seq 60); do curl -sf localhost:8000/ready >/dev/null && curl -sf localhost:3000/login >/dev/null && break; sleep 1; done
(cd frontend && E2E_CHANNEL="${E2E_CHANNEL-chrome}" npx playwright test "$@")
code=$?
stop
exit $code
