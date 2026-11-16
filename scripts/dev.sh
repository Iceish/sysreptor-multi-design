#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-help}" in
  init)
    if [ ! -f .env.dev ]; then
      python3 - <<'PY'
import os, secrets
fd = os.open('.env.dev', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write('SECRET_KEY=' + secrets.token_urlsafe(64) + '\n')
    f.write('DATABASE_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
    f.write('ENCRYPTION_PLAINTEXT_FALLBACK=True\n')
PY
    fi
    ./scripts/fetch-upstream.sh
    ;;
  build)
    source upstream.env
    test "$(git -C sysreptor-src rev-parse HEAD)" = "$SYSREPTOR_COMMIT"
    docker build --build-arg VERSION="mdo-$SYSREPTOR_COMMIT" -t multidesign-upstream:6b0b1fcf sysreptor-src
    docker compose --env-file .env.dev build app
    ;;
  up) docker compose --env-file .env.dev up -d --wait --wait-timeout 120 ;;
  down) docker compose --env-file .env.dev down ;;
  test)
    docker compose --env-file .env.dev run --rm -e DJANGO_SETTINGS_MODULE=sysreptor.conf.settings_test app \
      pytest -c /app/api/src/pytest.ini -p no:cacheprovider --pyargs sysreptor_plugins.multidesign
    ;;
  check)
    docker compose --env-file .env.dev run --rm app python3 manage.py check
    docker compose --env-file .env.dev run --rm app python3 manage.py makemigrations --check --dry-run
    ;;
  smoke)
    docker compose --env-file .env.dev exec -T app python3 - < scripts/browser_acceptance.py
    ;;
  demo)
    docker compose --env-file .env.dev exec -T app python3 manage.py multidesign_demo "${@:2}"
    ;;
  *) echo 'Usage: scripts/dev.sh {init|build|up|down|check|test|demo|smoke}' ;;
esac
