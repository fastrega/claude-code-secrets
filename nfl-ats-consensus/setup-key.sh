#!/usr/bin/env bash
# Save an OpenRouter API key on THIS machine, safely.
#
#   ./setup-key.sh
#
# The key is read without echoing to the screen and without passing through the
# shell's argument list, so it never lands in your terminal scrollback or in
# ~/.bash_history. It is written to ~/.config/atsc/env with 0600 permissions,
# outside the git tree entirely, so it cannot be committed by accident.

set -euo pipefail

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/atsc"
CONFIG_FILE="$CONFIG_DIR/env"

printf 'OpenRouter key setup\n'
printf '  destination: %s\n' "$CONFIG_FILE"
printf '  get a key at https://openrouter.ai/keys\n\n'

if [ -f "$CONFIG_FILE" ] && grep -q '^OPENROUTER_API_KEY=' "$CONFIG_FILE" 2>/dev/null; then
  printf 'A key is already saved there. Replace it? [y/N] '
  read -r reply
  case "$reply" in
    [yY]*) ;;
    *) printf 'Left unchanged.\n'; exit 0 ;;
  esac
fi

# -s suppresses echo so the key is never displayed; -r stops backslash mangling.
printf 'Paste your key (it will not be shown), then press Enter: '
read -rs KEY
printf '\n'

if [ -z "${KEY:-}" ]; then
  printf 'Nothing entered. Aborted.\n' >&2
  exit 1
fi

case "$KEY" in
  sk-or-*) ;;
  *) printf 'Warning: OpenRouter keys normally start with "sk-or-". Saving anyway.\n' ;;
esac

mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

# umask first so the file is never briefly world-readable between create and chmod.
( umask 077; printf 'OPENROUTER_API_KEY=%s\n' "$KEY" > "$CONFIG_FILE" )
chmod 600 "$CONFIG_FILE"
unset KEY

printf '\nSaved to %s (permissions 600).\n' "$CONFIG_FILE"
printf 'The key is outside the git tree, so it cannot be committed.\n\n'
printf 'Verifying — this prints a fingerprint, never the key itself:\n\n'

if command -v python3 >/dev/null 2>&1 && python3 -m atsc.cli doctor 2>/dev/null; then
  :
else
  printf '  Could not run the check automatically — the key is still saved.\n'
  printf '  Most likely the dependencies are missing. From this directory:\n\n'
  printf '      pip install -r requirements.txt\n'
  printf '      python3 -m atsc.cli doctor\n'
fi
