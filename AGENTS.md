# Repository Guidelines

## Project Structure & Module Organization

- `src/superwhisper/` contains the application code (entry point in `main.py`).
- `assets/` stores tray icon SVGs used for status display.
- `build/` holds build artifacts (do not edit by hand).
- `README.md` and `CLAUDE.md` describe usage, architecture, and system setup.

Key modules:
- `audio.py` (recording), `transcribe.py` (Whisper inference), `tray.py` (AppIndicator UI),
  `hotkey.py` (toggle signaling), `install.py` (desktop/systemd integration).

## Build, Test, and Development Commands

- `uv sync` — install Python dependencies into the local environment.
- `uv run superwhisper` — run the app locally from source.
- `uv run superwhisper install` — install the desktop entry and global command.
- `superwhisper toggle` — simulate the hotkey toggle (useful for debugging).

## Coding Style & Naming Conventions

- Python code follows PEP 8 with 4-space indentation.
- Naming: `snake_case` for functions/variables, `CapWords` for classes, constants in `UPPER_SNAKE_CASE`.
- Keep logging consistent with `logging_config.py`; prefer structured, actionable messages.

## Testing Guidelines

- No automated test suite is currently defined in this repository.
- If you add tests, document how to run them in `README.md` and keep test names descriptive (e.g., `test_transcribe_*`).

## Commit & Pull Request Guidelines

- Commit messages in history are short, imperative, and sentence-cased (e.g., “Add model selection menu to system tray”).
- Keep commits scoped and avoid mixing refactors with functional changes.
- PRs should include: a clear summary, rationale, and how you verified changes (commands/logs).
- This is a public repo: never commit secrets or local machine paths.

## Configuration & Runtime Notes

- User config lives at `~/.config/superwhisper-linux/config.json` and logs at `~/.config/superwhisper-linux/logs/`.
- The app uses a PID file at `/run/user/$UID/superwhisper.pid` and signals (SIGUSR1) for toggling.
