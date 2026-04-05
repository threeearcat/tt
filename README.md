# tt - Terminal Translator

A fast, simple terminal translator using Google Translate. No API key required.

## Features

- **GUI mode**: Tkinter-based GUI with dark theme (default)
- **Auto-toggle**: Korean input → English, otherwise → Korean
- **Clipboard monitoring**: Watch clipboard and auto-translate (GUI checkbox or `--clip`)
- **REPL mode**: Interactive translation with readline support (`--repl`)
- **Pipe support**: `echo "hello" | tt`
- **Font zoom**: Ctrl+scroll to resize text in GUI
- **Cross-platform**: macOS and Linux
- **Zero dependencies**: Python 3 stdlib only (tkinter)

## Install

```bash
git clone https://github.com/threeearcat/tt.git
ln -s $(pwd)/tt/tt.py ~/.local/bin/tt
```

## Usage

```bash
# GUI (default)
tt                          # opens GUI window
tt --clip                   # GUI with clipboard monitoring enabled

# Single translation
tt "hello"                  # → 안녕하세요
tt "안녕하세요"               # → hello (auto-toggle)
tt -t ja "hello"            # → こんにちは (specify target)

# Pipe
echo "hello" | tt           # → 안녕하세요

# Interactive REPL
tt --repl
> hello
안녕하세요
> :q
```

## Options

| Flag | Description |
|------|-------------|
| `-t`, `--target` | Target language code (default: auto-toggle ko/en) |
| `--clip` | Clipboard monitoring mode (GUI with auto-translate) |
| `--repl` | Interactive REPL mode |

## GUI Shortcuts

| Key | Action |
|-----|--------|
| Enter | Translate |
| Shift+Enter | New line |
| Ctrl+Scroll | Zoom in/out |
| Ctrl++/Ctrl+- | Zoom in/out |
| Ctrl+0 | Reset zoom |

## Requirements

- Python 3 with tkinter
- `xclip` (Linux, for clipboard features)
- `pbpaste` (macOS, for clipboard features, built-in)
