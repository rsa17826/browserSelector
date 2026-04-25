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
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
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
          inherit script desktop;
          default = pkgs.symlinkJoin {
            name = "browser-selector";
            paths = [
              script
              desktop
            ];
          };
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = [
              (pkgs.python3.withPackages (ps: [ ps.tkinter ]))
              pkgs.xdg-utils
              pkgs.basedpyright
            ];
            shellHook = ''
              echo "browser-selector dev shell"
              echo "run:  python3 browser_selector.py 'https://example.com'"
              echo "test: python3 browser_selector.py 'https://example.com' --force"
            '';
          };
        }
      );
    };
}
