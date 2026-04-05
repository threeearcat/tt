#!/usr/bin/env -S python3 -u
"""tt - Terminal Translator using Google Translate."""

import argparse
import json
import os
import platform
import readline  # noqa: F401 - enables input() line editing
import subprocess
import sys
import time
import urllib.parse
import urllib.request

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
TIMEOUT = 5
MAX_RETRIES = 2


def translate(text, target="ko", source="auto"):
    """Translate text. Returns (translated_text, detected_source_lang)."""
    params = urllib.parse.urlencode({
        "client": "gtx",
        "sl": source,
        "tl": target,
        "dt": "t",
        "q": text,
    })
    url = f"{TRANSLATE_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    last_err = None
    for _ in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
            translated = "".join(part[0] for part in data[0] if part[0])
            detected = data[2] if len(data) > 2 else source
            return translated, detected
        except Exception as e:
            last_err = e
            time.sleep(0.3)
    raise last_err


def auto_target(text):
    """Determine target language: ko input -> en, otherwise -> ko."""
    for ch in text:
        if "\uac00" <= ch <= "\ud7a3":  # Hangul syllables
            return "en"
    return "ko"


def translate_auto(text, fixed_target=None):
    """Translate with auto-toggle unless fixed_target is set."""
    target = fixed_target if fixed_target else auto_target(text)
    translated, detected = translate(text, target=target)
    return translated


def repl(fixed_target=None):
    """Interactive REPL mode."""
    label = fixed_target if fixed_target else "auto"
    print(f"tt ({label}) | :q to quit")
    while True:
        try:
            text = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not text:
            continue
        if text == ":q":
            break
        try:
            print(translate_auto(text, fixed_target))
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)


def _ensure_display():
    """Set DISPLAY and XAUTHORITY for xclip in tmux/tty sessions."""
    if platform.system() != "Linux":
        return
    if not os.environ.get("DISPLAY"):
        try:
            out = subprocess.run(
                ["pgrep", "-a", "Xorg"], capture_output=True, text=True, timeout=2
            ).stdout
            for line in out.splitlines():
                for token in line.split():
                    if token.startswith(":"):
                        os.environ["DISPLAY"] = token.split()[0]
                        break
                if os.environ.get("DISPLAY"):
                    break
            else:
                os.environ["DISPLAY"] = ":0"
        except Exception:
            os.environ["DISPLAY"] = ":0"
    if not os.environ.get("XAUTHORITY"):
        # GDM stores Xauthority here; other DMs may differ
        candidates = [
            f"/run/user/{os.getuid()}/gdm/Xauthority",
            os.path.expanduser("~/.Xauthority"),
        ]
        for path in candidates:
            if os.path.exists(path):
                os.environ["XAUTHORITY"] = path
                break


def get_clipboard():
    """Read clipboard content. Supports macOS and Linux."""
    system = platform.system()
    try:
        if system == "Darwin":
            return subprocess.run(
                ["pbpaste"], capture_output=True, text=True, timeout=2
            ).stdout
        else:
            _ensure_display()
            return subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=2
            ).stdout
    except FileNotFoundError:
        cmd = "pbpaste" if system == "Darwin" else "xclip"
        print(f"[error] {cmd} not found", file=sys.stderr)
        sys.exit(1)
    except Exception:
        return ""


def clip_watch(fixed_target=None):
    """Watch clipboard and translate new content."""
    label = fixed_target if fixed_target else "auto"
    print(f"tt clip ({label}) | Ctrl+C to stop")
    prev = get_clipboard()
    while True:
        try:
            time.sleep(0.5)
            current = get_clipboard()
            if current and current != prev:
                prev = current
                text = current.strip()
                if text:
                    try:
                        result = translate_auto(text, fixed_target)
                        print(f"\n--- [{text[:60]}{'...' if len(text) > 60 else ''}]")
                        print(result)
                    except Exception as e:
                        print(f"[error] {e}", file=sys.stderr)
        except KeyboardInterrupt:
            print()
            break


def main():
    parser = argparse.ArgumentParser(
        description="tt - Terminal Translator",
        usage="tt [text] | tt --clip | tt -t <lang> [text]",
    )
    parser.add_argument("text", nargs="*", help="text to translate")
    parser.add_argument("-t", "--target", default=None, help="target language (default: auto-toggle ko/en)")
    parser.add_argument("--clip", action="store_true", help="clipboard monitoring mode")
    args = parser.parse_args()

    if args.clip:
        clip_watch(args.target)
    elif args.text:
        try:
            print(translate_auto(" ".join(args.text), args.target))
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)
            sys.exit(1)
    else:
        repl(args.target)


if __name__ == "__main__":
    main()
