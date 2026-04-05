# tt - Terminal Translator

A fast, simple terminal translator using Google Translate. No API key required.

## Features

- **Auto-toggle**: Korean input → English, otherwise → Korean
- **REPL mode**: Interactive translation with readline support (history, line editing)
- **Clipboard monitoring**: Watch clipboard and auto-translate new content
- **Cross-platform**: macOS and Linux
- **Zero dependencies**: Python 3 stdlib only

## Install

```bash
git clone https://github.com/threeearcat/tt.git
ln -s $(pwd)/tt/tt.py ~/.local/bin/tt
```

## Usage

```bash
# Single translation
tt "hello"                  # → 안녕하세요
tt "안녕하세요"               # → hello (auto-toggle)
tt -t ja "hello"            # → こんにちは (specify target)

# Interactive REPL
tt
> hello
안녕하세요
> 안녕하세요
hello
> :q

# Clipboard monitoring
tt --clip                   # translates whenever you copy text
```

## Options

| Flag | Description |
|------|-------------|
| `-t`, `--target` | Target language code (default: auto-toggle ko/en) |
| `--clip` | Clipboard monitoring mode |

## Requirements

- Python 3
- `xclip` (Linux, for `--clip` mode)
- `pbpaste` (macOS, for `--clip` mode, built-in)
