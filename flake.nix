{
  description = "Browser Selector — pick which browser opens a URL";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
    in
    {
      # ── nix run / nix build ──────────────────────────────────────────────
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3.withPackages (ps: [ ps.tkinter ]);
        in
        {
          default = pkgs.writeShellApplication {
            name = "browser-selector";
            runtimeInputs = [ python ];
            text = ''
              exec python3 "${./browser_selector.py}" "$@"
            '';
          };
        }
      );

      # ── nix develop / direnv ─────────────────────────────────────────────
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = [
              (pkgs.python3.withPackages (ps: [ ps.tkinter ]))
              pkgs.xdg-utils # xdg-settings, xdg-mime
              pkgs.basedpyright # type checker
            ];
            shellHook = ''
              echo "browser-selector dev shell"
              echo "run:  python3 browser_selector.py 'https://example.com'"
              echo "test: python3 browser_selector.py 'https://example.com' --force"
            '';
          };
        }
      );

      # ── NixOS module ─────────────────────────────────────────────────────
      nixosModules.default =
        {
          config,
          pkgs,
          lib,
          ...
        }:
        let
          python = pkgs.python3.withPackages (ps: [ ps.tkinter ]);
          script = pkgs.writeShellApplication {
            name = "browser-selector";
            runtimeInputs = [ python ];
            text = ''exec python3 "${./browser_selector.py}" "$@"'';
          };
          desktop = pkgs.writeTextFile {
            name = "browser-selector.desktop";
            destination = "/share/applications/browser-selector.desktop";
            text = ''
              [Desktop Entry]
              Name=Browser Selector
              GenericName=Web Browser
              Exec=${script}/bin/browser-selector %u
              Type=Application
              MimeType=x-scheme-handler/http;x-scheme-handler/https;
              NoDisplay=false
              StartupNotify=false
              Icon=web-browser
            '';
          };
        in
        {
          environment.systemPackages = [
            script
            desktop
          ];
          environment.etc."browser-selector/settings.json" = {
            source = ./settings.json;
            mode = "0644";
          };
          environment.etc."browser-selector/settings.schema.jsonc" = {
            source = ./settings.schema.jsonc;
            mode = "0644";
          };
        };
    };
}
