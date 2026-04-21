#!/usr/bin/env bash
# install.sh — quick manual install without the NixOS module
# Run once: bash install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/browser-selector"
DESKTOP_DIR="$HOME/.local/share/applications"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$INSTALL_DIR" "$DESKTOP_DIR" "$BIN_DIR"

# Copy files
cp "$SCRIPT_DIR/browser_selector.py" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/browser_selector.py"

# Only copy settings if one doesn't already exist there
cp "$SCRIPT_DIR/settings.schema.jsonc" "$INSTALL_DIR/"
if [ ! -f "$INSTALL_DIR/settings.json" ]; then
  cp "$SCRIPT_DIR/settings.json" "$INSTALL_DIR/"
  echo "Copied default settings to $INSTALL_DIR/settings.json"
else
  echo "Settings already exist at $INSTALL_DIR/settings.json — not overwriting"
fi

# Wrapper in ~/bin
cat > "$BIN_DIR/browser-selector" <<EOF
#!/usr/bin/env bash
exec python3 "$INSTALL_DIR/browser_selector.py" "\$@"
EOF
chmod +x "$BIN_DIR/browser-selector"

# Desktop entry
cat > "$DESKTOP_DIR/browser-selector.desktop" <<EOF
[Desktop Entry]
Name=Browser Selector
GenericName=Web Browser
Comment=Pick which browser to open URLs with
Exec=$BIN_DIR/browser-selector %u
Type=Application
MimeType=x-scheme-handler/http;x-scheme-handler/https;x-scheme-handler/ftp;x-scheme-handler/mailto;
NoDisplay=false
StartupNotify=false
Icon=web-browser
EOF

# Update mime database
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

# Register as default browser
xdg-settings set default-web-browser browser-selector.desktop

echo ""
echo "✓ Installed to $INSTALL_DIR"
echo "✓ Registered as default browser"
echo ""
echo "Edit settings: $INSTALL_DIR/settings.json"
echo "Test it:       browser-selector 'https://example.com'"
echo "Force picker:  browser-selector 'https://example.com' --force"
