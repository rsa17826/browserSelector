# NixOS module for browser-selector
# Add this file to your config and import it from configuration.nix:
#   imports = [ ./browser-selector.nix ];

{
  config,
  pkgs,
  lib,
  ...
}:

let
  browserSelectorScript = pkgs.writeScriptBin "browser-selector" ''
    #!${pkgs.python3.withPackages (ps: [ ps.tkinter ])}/bin/python3
    ${builtins.readFile ./browser_selector.py}
  '';

  # Desktop entry pointing at the wrapper
  desktopEntry = pkgs.writeTextFile {
    name = "browser-selector.desktop";
    destination = "/share/applications/browser-selector.desktop";
    text = ''
      [Desktop Entry]
      Name=Browser Selector
      GenericName=Web Browser
      Comment=Pick which browser to open URLs with
      Exec=${browserSelectorScript}/bin/browser-selector %u
      Type=Application
      MimeType=x-scheme-handler/http;x-scheme-handler/https;x-scheme-handler/ftp;x-scheme-handler/mailto;
      NoDisplay=false
      StartupNotify=false
      Icon=web-browser
    '';
  };

in
{
  # 1. Make the script available system-wide
  environment.systemPackages = [
    browserSelectorScript
    desktopEntry
    # Make sure tkinter is available (it's part of python3 full by default)
    (pkgs.python3.withPackages (ps: [ ps.tkinter ]))
  ];

  # 2. Install the .desktop file
  environment.pathsToLink = [ "/share/applications" ];

  # environment.etc."browser-selector/settings.json" = {
  #   source = ./settings.json;
  #   mode = "0644";
  # };

  # 4. Set as default browser at the system level
  #    Users can also run:  xdg-settings set default-web-browser browser-selector.desktop
  environment.sessionVariables = {
    BROWSER = "${browserSelectorScript}/bin/browser-selector";
  };

  # Optional: set via xdg-mime at activation (uncomment if you want it automatic)
  system.activationScripts.browserSelector = ''
    ${pkgs.xdg-utils}/bin/xdg-mime default browser-selector.desktop x-scheme-handler/http
    ${pkgs.xdg-utils}/bin/xdg-mime default browser-selector.desktop x-scheme-handler/https
  '';
}
