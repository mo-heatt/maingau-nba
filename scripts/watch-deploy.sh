#!/usr/bin/env bash
# GitHub-side auto-deploy watcher. Runs from cron every 2 minutes:
#   */2 * * * * flock -n /tmp/nba-deploy.lock /srv/maingau-nba/scripts/watch-deploy.sh >> /srv/maingau-nba/deploy.log 2>&1
# Deploys origin/main -> prod (port 80) and origin/dev -> dev (port 443) when the refs move.
set -uo pipefail

BASE=/srv/maingau-nba
LOCK=/tmp/nba-deploy.lock
LOG=$BASE/deploy.log

exec 9>"$LOCK"
flock -n 9 || exit 0   # a deploy is already running

"$BASE/repo/scripts/deploy-one.sh" prod
rc1=$?
"$BASE/repo/scripts/deploy-one.sh" dev
rc2=$?
exit $(( rc1 > rc2 ? rc1 : rc2 ))
