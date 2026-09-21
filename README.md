# FinancialTracker

Personal desktop finance tracker built with [Flet](https://flet.dev).

## Setup

```
uv sync
```

## Usage

```
uv run flet run              # run the app (dev mode, hot reload)
uv run pytest                # run tests
```

## App password

Optionally, the app can ask for a password at startup. Set one from **Settings → Require password
at startup** (minimum 10 characters, with at least one uppercase letter and one special character).
Three wrong attempts close the window.

This is a convenience lock, not encryption: the database files stay readable on disk to anyone with
filesystem access. It only stops someone who launches the app.

There is no in-app recovery. If you forget the password, clear it by hand:

```
sqlite3 ~/Library/Application\ Support/Financial\ Tracker/config.db \
  "DELETE FROM preferences WHERE key IN ('password_hash', 'password_salt');"
```

## Install as macOS app

See [Flet](https://flet.dev/docs/publish/macos/) for the prerequisite, then run:

```
uv run flet build macos
```

Builds `Financial Tracker.app` into `build/macos/`. Move it to `/Applications` to install.

## Requirements

Python >= 3.12
