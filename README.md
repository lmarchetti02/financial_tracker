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

## Install as macOS app

See [Flet](https://flet.dev/docs/publish/macos/) for the prerequisite, then run:

```
uv run flet build macos
```

Builds `Financial Tracker.app` into `build/macos/`. Move it to `/Applications` to install.

## Requirements

Python >= 3.12
