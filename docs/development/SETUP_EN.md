# Developer setup

[English README](../../README.en.md) · [日本語の詳細手順](SETUP_JA.md)

This page is for maintainers and developers authorized by the copyright holders. Desktop-app users should download a package from [GitHub Releases](https://github.com/k-botsui/lumvia/releases); they do not need these tools or commands. Source code visibility does not grant permission to modify or redistribute Lumvia. See [LICENSE](../../LICENSE).

## Architecture

The web interface uses Next.js 16, React 19, TypeScript, TanStack Query, and Three.js. FastAPI, SQLAlchemy, and Alembic provide the API and database migrations. PostgreSQL holds durable data; videos are stored as local files. FFmpeg/FFprobe handle media processing.

The packaged Mac app uses Swift/AppKit/WKWebView and includes Node 22, Python 3.13, PostgreSQL, Valkey, and FFmpeg. Its bounded desktop executor reads durable jobs from PostgreSQL. It does not require Docker, Homebrew, RabbitMQ, or a separate Python installation on the user's Mac.

The source-development configuration uses Node 24, pnpm 11.25.0, Python 3.13, PostgreSQL 17, Celery/RabbitMQ, and Redis. The native development launcher assumes an Apple Silicon Mac with Homebrew. The Windows `.cmd` files invoke Python and Docker Compose; they are development entry points, not standalone Windows applications. Windows desktop packaging is not implemented or validated.

## Native development on Apple Silicon macOS

Run from the repository root. These commands belong to the development machine, not the receiving user's machine.

```sh
brew install node pnpm python@3.13 postgresql@17 rabbitmq redis ffmpeg
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r apps/api/requirements.txt
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web build
python3 scripts/run_local.py start
```

Open `http://127.0.0.1:3000`. The launcher creates private configuration, a random secret, and initial credentials outside the repository. Open `ログイン情報を開く.command` to view the development credentials. Do not publish or attach them to an Issue.

- Start: `python3 scripts/run_local.py start`
- Stop: `python3 scripts/run_local.py stop`
- Development mode, after stopping the normal instance: `python3 scripts/run_local.py start --dev`
- After changing the web interface: build it again and restart the normal instance.

Set `LUMVIA_NODE` to the Node executable if it cannot be detected. Stopping the app preserves the database and videos. The native launcher does not install an autostart service.

## Data locations

| Configuration                        | Location                                             |
| ------------------------------------ | ---------------------------------------------------- |
| Packaged Mac app                     | `~/Library/Application Support/Lumvia Desktop/`      |
| Native/source development on Mac     | `~/Library/Application Support/Lumvia/`              |
| Windows source/Compose configuration | `%LOCALAPPDATA%\Lumvia\`                             |
| Linux configuration                  | `$XDG_DATA_HOME/lumvia/` or `~/.local/share/lumvia/` |
| Docker database and media            | Dedicated Docker volumes                             |

The app and development data directories are separate. Do not copy live PostgreSQL clusters between incompatible versions. The current backup script targets the native Homebrew development configuration; it is not a cross-platform desktop backup tool.

## Configuration and limits

The launchers generate private configuration. `.env.example` documents available settings; a repository-local `.env` file is not required. API settings use private `config.env`, and Compose uses private `compose.env`. Environment variables override these values.

Important settings include `DATABASE_URL`, `SECRET_KEY`, `APP_URL`, `FFMPEG_BIN`, `FFPROBE_BIN`, `STORAGE_ROOT`, `REFERENCE_PREVIEW_ROOT`, `BROKER_URL`, and `REDIS_URL`. See [.env.example](../../.env.example) and [Settings](../../apps/api/app/config.py) for the full definitions. Production requires HTTPS; normal desktop loopback use is a separate configuration. Do not disable authentication, CSRF/Origin checks, TLS validation, or processing limits to make an environment work.

Defaults include a 2 GiB / 60-minute / 4096-pixel limit per video, 10 GiB of original videos, 500 managed videos, 2,000 Cells, and a five-minute limit per Cell export. Temporary external previews expire after 30 minutes, with a 32 MB per-video and 256 MB total cache limit. The current configuration rejects cloud storage, external databases/queues, and OIDC sign-in.

## Other development configurations

[Docker configuration](DOCKER.md), [optional private-Wi-Fi HTTPS](MOBILE.md), [backup scope](BACKUP.md), [verification results](VERIFICATION.md), and [Mac packaging](MAC_APP.md) are documented in Japanese. Configuration-file resolution and path unit tests do not establish that a Windows installer or application has been tested. Do not label an untested platform as supported.

## Checks

```sh
.venv/bin/ruff check apps/api scripts tests packaging/macos
.venv/bin/ruff format --check apps/api scripts tests packaging/macos
.venv/bin/python scripts/test.py -q
pnpm --dir apps/web typecheck
pnpm --dir apps/web lint
pnpm --dir apps/web build
pnpm --dir apps/web audit
.venv/bin/pip-audit
python3 scripts/check_publication.py
python3 scripts/scan_secrets.py
```

Tests use an isolated `lumvia_test` database and `test-storage`; they must not use an owner's library. Browser E2E tests require explicit disposable-account credentials in `LUMVIA_E2E_EMAIL` and `LUMVIA_E2E_PASSWORD`. Keep test credentials and traces private.

Before publishing changes, follow [CONTRIBUTING.md](../../CONTRIBUTING.md), [SECURITY.md](../../SECURITY.md), and the [publication boundary](PUBLICATION.md). These documents do not authorize changing repository security settings or publishing releases without the owner's instruction.
