#!/usr/bin/env bash
# Install (or remove) the EskaBoard apps-menu entry for the current user.
#
#   ./install.sh              check system packages, set up the venv, install icon and menu entry
#   ./install.sh --uninstall  remove the icon and menu entry (the project and venv stay)
#
# Never runs sudo: if system packages are missing it prints the apt command and stops.
# Re-run it after moving the project folder or updating: the paths are taken from
# where this script is, and the Python packages are brought up to date every time.
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT/venv/bin/python3"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS_DIR="$DATA_HOME/applications"
DESKTOP_FILE="$APPS_DIR/eskaboard.desktop"
OLD_DESKTOP_FILE="$APPS_DIR/org.phonekb.PhoneKB.desktop"   # launcher from before the rename
ICON_PNG="$DATA_HOME/icons/hicolor/256x256/apps/eskaboard.png"
ICON_SVG="$DATA_HOME/icons/hicolor/scalable/apps/eskaboard.svg"
APP_ID="org.phonekb.PhoneKB"   # GTK application id (phonekb/app.py), matches windows to this entry
APT_PACKAGES=(python3-venv python3-gi gir1.2-gtk-4.0)

warn() { echo "Warning: $*" >&2; }

refresh_menu() {
    if command -v update-desktop-database >/dev/null; then
        update-desktop-database "$APPS_DIR"
    else
        echo "update-desktop-database not found; the menu may take a moment to refresh"
    fi
}

remove_old_entry() {
    if [[ -e "$OLD_DESKTOP_FILE" ]]; then
        rm -f "$OLD_DESKTOP_FILE"
        echo "Removed old launcher: $OLD_DESKTOP_FILE"
    fi
}

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -f "$DESKTOP_FILE" "$ICON_PNG" "$ICON_SVG"
    remove_old_entry
    refresh_menu
    echo "EskaBoard removed from the apps menu."
    echo "The project folder, its venv and ~/.config/phonekb were left in place."
    exit 0
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--uninstall]" >&2
    exit 2
fi

# These characters would need escaping in the Exec/Path/Icon keys; refuse them instead
unsupported='["`$\%]'
if [[ "$PROJECT$DATA_HOME" =~ $unsupported ]]; then
    echo "The path contains one of \" \` \$ \\ % which is not supported: $PROJECT" >&2
    exit 1
fi

# Typing goes through the GNOME Remote Desktop portal, which is only tested on Wayland
case "${XDG_SESSION_TYPE:-}" in
    wayland) ;;
    x11) warn "this is an X11 session. EskaBoard is made for GNOME on Wayland; typing may not work." ;;
    *) warn "could not tell the session type (XDG_SESSION_TYPE is empty). EskaBoard needs GNOME on Wayland." ;;
esac
if [[ -z "${XDG_CURRENT_DESKTOP:-}" ]]; then
    warn "could not tell the desktop (XDG_CURRENT_DESKTOP is empty). EskaBoard needs GNOME."
elif [[ "$XDG_CURRENT_DESKTOP" != *GNOME* ]]; then
    warn "the desktop is $XDG_CURRENT_DESKTOP, not GNOME. Typing on the PC will probably not work."
fi

if command -v dpkg-query >/dev/null; then
    missing=()
    for pkg in "${APT_PACKAGES[@]}"; do
        status="$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true)"
        [[ "$status" == *"ok installed"* ]] || missing+=("$pkg")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Some system packages are missing. Install them, then run this again:" >&2
        echo "" >&2
        echo "    sudo apt install ${missing[*]}" >&2
        echo "" >&2
        exit 1
    fi
else
    warn "dpkg-query not found (not Ubuntu/Debian?). Make sure Python venv, PyGObject and GTK 4 introspection are installed."
fi

# (Re)create the venv if it is missing or broken, e.g. after a Python upgrade
if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
    echo "Creating venv in $PROJECT/venv ..."
    python3 -m venv --system-site-packages "$PROJECT/venv"
fi
echo "Installing Python packages ..."
"$PYTHON" -m pip install --disable-pip-version-check --quiet -r "$PROJECT/requirements.txt"

if ! "$PYTHON" -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk; import aiohttp, nacl, qrcode" 2>/dev/null; then
    echo "The venv cannot import GTK 4 or the Python packages. Check the messages above." >&2
    exit 1
fi
gtk_minor="$("$PYTHON" -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk; print(Gtk.get_minor_version())")"
if [[ "$gtk_minor" -lt 8 ]]; then
    warn "GTK 4.$gtk_minor is too old for the window (needs 4.8, Ubuntu 24.04 or newer). The terminal mode still works."
fi

install -D -m 644 "$PROJECT/assets/eskaboard.png" "$ICON_PNG"
install -D -m 644 "$PROJECT/assets/eskaboard.svg" "$ICON_SVG"

mkdir -p "$APPS_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=EskaBoard
GenericName=Phone Keyboard
GenericName[ar]=لوحة الهاتف
Comment=Use your phone as a keyboard for this PC
Comment[ar]=استخدم هاتفك كلوحة مفاتيح لهذا الحاسوب
Keywords=phone;keyboard;remote;typing;هاتف;لوحة;مفاتيح;
Exec="$PYTHON" -m phonekb --gui
Path=$PROJECT
Icon=$ICON_PNG
Terminal=false
Categories=Utility;
StartupNotify=true
StartupWMClass=$APP_ID
EOF
chmod 644 "$DESKTOP_FILE"
echo "Installed launcher: $DESKTOP_FILE"

remove_old_entry
refresh_menu
echo "EskaBoard is in the apps menu."
