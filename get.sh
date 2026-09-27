#!/usr/bin/env bash
# One-line install / update of EskaBoard on Ubuntu (GNOME on Wayland):
#   curl -fsSL https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash
#   wget -qO- https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash
# Installs to ~/EskaBoard (or $ESKABOARD_DIR) and adds EskaBoard to the apps menu.
# Run it again to update. Never runs sudo. To uninstall, add "-s -- --uninstall":
#   curl -fsSL https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash -s -- --uninstall
#   wget -qO- https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash -s -- --uninstall
set -euo pipefail

REPO_URL="${ESKABOARD_REPO:-https://github.com/Mohamedeskali/EskaBoard.git}"
INSTALL_DIR="${ESKABOARD_DIR:-$HOME/EskaBoard}"
CONFIG_DIR="$HOME/.config/phonekb"   # saved Remote Desktop permission token (phonekb/injector.py)
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
MIN_PY="3.8"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

# PIDs of running EskaBoard copies; with a folder, only the ones started from it
# (menu launches run "<folder>/venv/bin/python3", terminal ones have it as cwd).
eskaboard_pids() {
  local dir="${1:-}" pid arg0 cwd
  for pid in $(pgrep -f 'python[0-9.]* -m phonekb' || true); do
    arg0="$(tr '\0' '\n' < "/proc/$pid/cmdline" 2>/dev/null | head -n 1)" || continue
    [[ "${arg0##*/}" == python* ]] || continue
    if [[ -n "$dir" ]]; then
      cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
      [[ "$arg0" == "$dir/"* || "$cwd" == "$dir" ]] || continue
    fi
    echo "$pid"
  done
}

# SIGTERM takes the app's normal Stop path; it gives itself 8 s before quitting anyway.
stop_copies() {
  local pid alive _
  kill -TERM "$@" 2>/dev/null || true
  for _ in $(seq 1 24); do
    alive=0
    for pid in "$@"; do kill -0 "$pid" 2>/dev/null && alive=1; done
    ((alive)) || return 0
    sleep 0.5
  done
  kill -KILL "$@" 2>/dev/null || true
}

# GNOME Settings has no page for Remote Desktop grants, so remove the ones the
# portal filed under EskaBoard's menu entries. Prints how many were removed.
revoke_permission() {
  python3 - <<'EOF' 2>/dev/null || echo "?"
from gi.repository import Gio, GLib

APPS = {"eskaboard", "org.phonekb.PhoneKB"}
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

def call(method, args, reply):
    return bus.call_sync(
        "org.freedesktop.impl.portal.PermissionStore", "/org/freedesktop/impl/portal/PermissionStore",
        "org.freedesktop.impl.portal.PermissionStore", method, args,
        GLib.VariantType(reply) if reply else None, Gio.DBusCallFlags.NONE, 5000, None)

try:
    ids = call("List", GLib.Variant("(s)", ("remote-desktop",)), "(as)").unpack()[0]
except GLib.Error:
    ids = []  # no grants were ever stored
removed = 0
for entry in ids:
    perms = call("Lookup", GLib.Variant("(ss)", ("remote-desktop", entry)), "(a{sas}v)").unpack()[0]
    if perms and set(perms) <= APPS:
        call("Delete", GLib.Variant("(ss)", ("remote-desktop", entry)), None)
        removed += 1
print(removed)
EOF
}

uninstall() {
  local dir entry pids revoked
  dir="$(readlink -f "$INSTALL_DIR" 2>/dev/null || echo "$INSTALL_DIR")"
  [[ -n "$dir" && "$dir" != "/" && "$dir" != "$(readlink -f "$HOME")" ]] || fail "refusing to remove $INSTALL_DIR."
  if [[ -e "$dir" && ! ( -f "$dir/phonekb/__main__.py" && -f "$dir/install.sh" ) ]]; then
    fail "$dir does not look like EskaBoard; not removing it."
  fi

  mapfile -t pids < <(eskaboard_pids "$dir")
  if ((${#pids[@]})); then
    say "Stopping EskaBoard"
    stop_copies "${pids[@]}"
  fi

  # Menu entry and icons, only when they belong to this install
  entry="$DATA_HOME/applications/eskaboard.desktop"
  if [[ -f "$entry" ]] && grep -qxF -e "Path=$dir" -e "Path=$INSTALL_DIR" "$entry"; then
    say "Removing the apps-menu entry and icon"
    rm -f "$entry" "$DATA_HOME/applications/org.phonekb.PhoneKB.desktop" \
      "$DATA_HOME/icons/hicolor/256x256/apps/eskaboard.png" \
      "$DATA_HOME/icons/hicolor/scalable/apps/eskaboard.svg"
    update-desktop-database "$DATA_HOME/applications" >/dev/null 2>&1 || true
  elif [[ -f "$entry" ]]; then
    say "Keeping the apps-menu entry: it belongs to an EskaBoard in another folder."
  fi

  if [[ -e "$dir" ]]; then
    say "Removing $dir (program and venv)"
    rm -rf -- "$dir"
  else
    say "$dir is not there; nothing to remove."
  fi

  say "Removing the saved Remote Desktop permission"
  rm -rf -- "$CONFIG_DIR"
  revoked="$(revoke_permission)"

  say "EskaBoard is uninstalled."
  echo "    Removed $CONFIG_DIR (the token that let EskaBoard type without asking)."
  if [[ "$revoked" == "?" ]]; then
    echo "    Could not reach the portal permission store; without the token the old grant cannot be used anyway."
  else
    echo "    Removed $revoked Remote Desktop grant(s) from GNOME's permission store."
  fi
  echo "    GNOME Settings has no page for Remote Desktop grants. Grants from runs started in a"
  echo "    terminal are not labelled with a name; they are useless without the deleted token."
}

# Everything runs from main(), so a download cut off halfway through does nothing.
main() {
  case "${1:-}" in
    --uninstall) uninstall; return ;;
    "") ;;
    *) fail "unknown option '$1'. Use no option to install or update, or --uninstall." ;;
  esac

  local missing=()
  command -v python3 >/dev/null 2>&1 || missing+=(python3)
  command -v git >/dev/null 2>&1 || missing+=(git)
  if ((${#missing[@]})); then
    fail "missing: ${missing[*]}. Install it, then run this command again:
    sudo apt install ${missing[*]}"
  fi
  python3 -c "import sys; sys.exit(sys.version_info < (${MIN_PY/./,}))" \
    || fail "EskaBoard needs Python $MIN_PY or newer; found $(python3 -V 2>&1)."

  local dir pid pids mine others
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    dir="$(readlink -f "$INSTALL_DIR")"
    say "Checking for updates in $INSTALL_DIR"
    GIT_TERMINAL_PROMPT=0 git -C "$INSTALL_DIR" fetch --quiet \
      || fail "could not reach $REPO_URL to check for updates."
    if [[ "$(git -C "$INSTALL_DIR" rev-parse HEAD)" == "$(git -C "$INSTALL_DIR" rev-parse '@{u}')" ]]; then
      say "Already up to date"
    else
      # Stop a copy running from this folder so it does not keep running the old code
      mapfile -t pids < <(eskaboard_pids "$dir")
      if ((${#pids[@]})); then
        say "Stopping the running EskaBoard to update it"
        stop_copies "${pids[@]}"
      fi
      say "Updating $INSTALL_DIR"
      git -C "$INSTALL_DIR" merge --ff-only --quiet '@{u}' \
        || fail "could not update $INSTALL_DIR (local changes?). Fix it with git, or move the folder away and run this again."
    fi
  elif [[ -e "$INSTALL_DIR" ]]; then
    fail "$INSTALL_DIR exists but is not a git checkout. Move it away (or set ESKABOARD_DIR) and run this again."
  else
    say "Downloading EskaBoard to $INSTALL_DIR"
    GIT_TERMINAL_PROMPT=0 git clone --quiet --depth 1 "$REPO_URL" "$INSTALL_DIR" \
      || fail "could not download $REPO_URL."
    dir="$(readlink -f "$INSTALL_DIR")"
  fi

  say "Installing EskaBoard"
  bash "$INSTALL_DIR/install.sh" </dev/null

  # Only one copy can run at a time; a menu launch would just show the other one
  mapfile -t mine < <(eskaboard_pids "$dir")
  others=()
  for pid in $(eskaboard_pids); do
    [[ " ${mine[*]} " == *" $pid "* ]] || others+=("$pid")
  done
  if ((${#others[@]})); then
    echo "    Note: EskaBoard is already running from $(readlink -f "/proc/${others[0]}/cwd")."
    echo "    Close it (the إيقاف button) before opening this one."
  fi

  say "Done. Open EskaBoard from the apps menu."
  echo "    Update it:    run the same install command again."
  echo "    Uninstall it: run it again with  bash -s -- --uninstall  in place of  bash"
}

main "$@"
