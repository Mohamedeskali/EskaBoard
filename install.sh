#!/usr/bin/env bash
# Install (or remove) the EskaBoard apps-menu entry for the current user.
#
#   ./install.sh              create the venv if needed, install icon and menu entry
#   ./install.sh --uninstall  remove the icon and menu entry (the project and venv stay)
#
# Re-run it after moving the project folder: the paths are taken from where
# this script is, so the menu entry always points at the current location.
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

if [[ ! -x "$PYTHON" ]]; then
    echo "Creating venv in $PROJECT/venv ..."
    python3 -m venv --system-site-packages "$PROJECT/venv"
    "$PROJECT/venv/bin/pip" install -r "$PROJECT/requirements.txt"
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
