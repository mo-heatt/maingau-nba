# Deployment — workshop VM (wsvm41)

The team workshop VM runs two container stacks that deploy automatically from Git:

| Environment | Branch | URL | Container |
| --- | --- | --- | --- |
| **prod** (approved) | `main` | http://130.83.85.181:41080 | `app-prod` behind nginx :80 |
| **dev** (test) | `dev` | https://130.83.85.181:41443 (self-signed TLS) | `app-dev` behind nginx :443 |

VM: 4 CPU cores / 8 GB RAM (observed: 2 cores / 3.8 GB), Docker + Compose preinstalled,
project data on `/srv`, SSH on port `41022`. Access data comes from the workshop handout;
credentials are **not** stored in this repository.

## VM layout

```text
/srv/maingau-nba/
├── repo/                 git clone of mo-heatt/maingau-nba
├── data/                 maingau_nba_mockdata.xlsx + event_stream_2026-10-01.jsonl (read-only mount)
├── tls/                  selfsigned.crt / selfsigned.key for nginx :443
├── .deployed-prod        last deployed main SHA
├── .deployed-dev         last deployed dev SHA
└── deploy.log            watcher log
```

Each container keeps its own SQLite database in a named volume
(`nba-prod-db`, `nba-dev-db`), so prod and dev never share state. The mock dataset is
mounted read-only at `/opt/app/data`; it is never baked into the image and never committed.

## Auto-deploy (watcher, no GitHub configuration needed)

`wsvm41-admin`'s crontab runs `scripts/watch-deploy.sh` every 2 minutes
(`flock` prevents overlap). For each environment it compares `origin/main` / `origin/dev`
with the last deployed SHA and, on change:

1. `git fetch` + checkout the branch head,
2. `docker compose build app-<env> --pull`,
3. `docker compose up -d app-<env> nginx`,
4. records the SHA and prunes old images.

Push to `dev` → dev container rebuilds within ~2 minutes. Merge to `main` → prod.
A deploy takes a few minutes (frontend build runs inside Docker on the VM).

Install/repair the watcher after cloning:

```sh
crontab -l | { cat; echo '*/2 * * * * flock -n /tmp/nba-deploy.lock /srv/maingau-nba/repo/scripts/watch-deploy.sh >> /srv/maingau-nba/deploy.log 2>&1'; } | crontab -
```

## Optional: deploy from GitHub Actions immediately

`.github/workflows/deploy.yml` pushes the same deploy over SSH right after a push
to `main`/`dev`. It skips itself with a notice until an admin adds the repository
secrets (`Settings → Secrets and variables → Actions`):

| Secret | Value |
| --- | --- |
| `DEPLOY_SSH_KEY` | private key of the deploy keypair (public half lives in the VM's `authorized_keys`) |
| `DEPLOY_HOST` | `130.83.85.181` |
| `DEPLOY_PORT` | `41022` |
| `DEPLOY_USER` | `wsvm41-admin` |

Until then the watcher is the deployment path; CI (`ci.yml`) runs tests and the
frontend build on every pull request and every push to `main`/`dev`.

## Branch protection (repo admin)

`main` should accept changes only through pull requests so that CI gates every merge
and nobody pushes broken code to the auto-deployed production stack. Set it in
**Settings → Branches → Add branch ruleset** (or classic **Branch protection rules**):

- Rule name `protect-main`, enforcement **Active**, target `main`.
- Require a pull request before merging (1 approval), dismiss stale approvals on new commits.
- Require status checks: `backend-tests`, `frontend-build` (names as defined in `.github/workflows/ci.yml`).
- Block force pushes and deletions.

Apply the same rule to `dev` (approvals can stay at 0 — the PR requirement itself
blocks direct pushes). Admins can also add `Protect-main` for `deploy/*`… not needed:
deploy branches are created by the watcher only.

## First manual install on a fresh VM

```sh
sudo usermod -aG docker wsvm41-admin        # re-login or use sg docker
mkdir -p /srv/maingau-nba/{data,tls}
# copy the mock dataset (from the organisers) into /srv/maingau-nba/data/
git clone https://github.com/mo-heatt/maingau-nba.git /srv/maingau-nba/repo
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout /srv/maingau-nba/tls/selfsigned.key -out /srv/maingau-nba/tls/selfsigned.crt \
  -subj "/CN=130.83.85.181" -addext "subjectAltName=IP:130.83.85.181"
/srv/maingau-nba/repo/scripts/deploy-one.sh prod
/srv/maingau-nba/repo/scripts/deploy-one.sh dev
# then install the crontab line shown above
```

## Limits and notes

- No Hessian key is configured on the VM: both stacks run in **engine-only mode**
  (AI generation is disabled until a key is provided). To enable it, put `HAI_API_KEY`
  into `/srv/maingau-nba/repo/.env` on the VM and restart the containers — the key
  stays on the VM and is never committed.
- The dev URL uses a self-signed certificate; browsers show a one-time warning.
- The VM is reachable while the workshop infrastructure keeps it online; deploys
  fail harmlessly (logged) when it is off.
- No external message sending exists in the app; both stacks are demo environments.
