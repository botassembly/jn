{
  description = "JN - Universal Data Pipeline Tool";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Map Nix system to JN release naming
        platformMap = {
          "x86_64-linux" = { arch = "x86_64"; os = "linux"; };
          "aarch64-linux" = { arch = "aarch64"; os = "linux"; };
          "x86_64-darwin" = { arch = "x86_64"; os = "darwin"; };
          "aarch64-darwin" = { arch = "aarch64"; os = "darwin"; };
        };

        platform = platformMap.${system} or (throw "Unsupported system: ${system}");

        version = "0.1.0";  # Update this when releasing new versions

        jn = pkgs.stdenv.mkDerivation {
          pname = "jn";
          inherit version;

          src = pkgs.fetchurl {
            url = "https://github.com/botassembly/jn/releases/download/v${version}/jn-${version}-${platform.arch}-${platform.os}.tar.gz";
            # Note: Update these hashes when releasing new versions
            # Run: nix-prefetch-url <url> to get the hash
            sha256 = pkgs.lib.fakeSha256;
          };

          sourceRoot = ".";

          nativeBuildInputs = [ pkgs.autoPatchelfHook ];

          # Runtime dependencies for dynamically linked binaries (if any)
          buildInputs = pkgs.lib.optionals pkgs.stdenv.isLinux [
            pkgs.stdenv.cc.cc.lib
          ];

          installPhase = ''
            runHook preInstall

            mkdir -p $out/bin $out/lib/jn

            # Install main binaries
            cp -r bin/* $out/bin/

            # Install jn_home (Python plugins, tools, etc.)
            if [ -d jn_home ]; then
              cp -r jn_home $out/lib/jn/
            fi

            runHook postInstall
          '';

          meta = with pkgs.lib; {
            description = "Universal data pipeline tool with pure Zig core";
            homepage = "https://github.com/botassembly/jn";
            license = licenses.mit;
            platforms = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
            mainProgram = "jn";
          };
        };

        # Development shell with build dependencies
        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [
            zig
            python3
          ];

          shellHook = ''
            echo "JN development shell"
            echo "Run 'make build' to build from source"
          '';
        };

      in {
        packages = {
          default = jn;
          jn = jn;
        };

        apps.default = flake-utils.lib.mkApp {
          drv = jn;
        };

        devShells.default = devShell;
      }
    );
}
