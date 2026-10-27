#!/usr/bin/env bash
# Deploy one environment on the workshop VM from its GitHub branch.
#   deploy-one.sh prod   -> origin/main
#   deploy-one.sh dev    -> origin/dev
# Called by watch-deploy.sh (cron) or manually over SSH.
set -euo pipefail

ENVIRONMENT=${1:?usage: deploy-one.sh prod|dev}
BASE=/srv/maingau-nba
REPO=$BASE/repo
case "$ENVIRONMENT" in
  prod) BRANCH=main ;;
  dev)  BRANCH=dev ;;
  *) echo "unknown environment: $ENVIRONMENT" >&2; exit 1 ;;
esac

# Docker needs the docker group; sg applies it without a fresh login.
run() { if docker ps >/dev/null 2>&1; then "$@"; else sg docker -c "$*"; fi; }

cd "$REPO"
git config core.filemode false >/dev/null   # ignore mode-only diffs (e.g. chmod on the VM)
git fetch origin "$BRANCH" -q
SHA=$(git rev-parse "origin/$BRANCH")
LAST=$(cat "$BASE/.deployed-$ENVIRONMENT" 2>/dev/null || echo none)
if [ "$SHA" = "$LAST" ]; then
  echo "[$(date -Is)] $ENVIRONMENT already at $SHA"
  exit 0
fi

echo "[$(date -Is)] deploying $ENVIRONMENT from $BRANCH @ ${SHA:0:9}"
git checkout -q -B "deploy-$ENVIRONMENT" "origin/$BRANCH"

run docker compose -f deploy/docker-compose.yml build --pull "app-$ENVIRONMENT"
run docker compose -f deploy/docker-compose.yml up -d "app-$ENVIRONMENT" nginx

echo "$SHA" > "$BASE/.deployed-$ENVIRONMENT"
echo "[$(date -Is)] $ENVIRONMENT deployed OK ($SHA)"

# Health check with a short grace period for first-run data import.
for i in $(seq 1 30); do
  if curl -sf -m 5 "http://127.0.0.1:80/api/health" >/dev/null 2>&1 || true; then break; fi
  sleep 2
done
run docker image prune -f >/dev/null
