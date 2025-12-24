{
  description = "JN - Universal Data Pipeline Tool";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    zig-overlay.url = "github:mitchellh/zig-overlay";
  };

  outputs = { self, nixpkgs, flake-utils, zig-overlay }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        zigPkgs = zig-overlay.packages.${system};

        # Use Zig 0.13.0 (stable version compatible with the codebase)
        zig = zigPkgs."0.13.0" or pkgs.zig;

        jn = pkgs.stdenv.mkDerivation {
          pname = "jn";
          version = "0.1.0-dev";

          src = ./.;

          nativeBuildInputs = [ zig ];

          # Zig needs a writable cache directory
          ZIG_LOCAL_CACHE_DIR = ".zig-cache";
          ZIG_GLOBAL_CACHE_DIR = ".zig-cache";

          buildPhase = ''
            runHook preBuild

            # Module definitions
            JN_CORE="-Mjn-core=libs/zig/jn-core/src/root.zig"
            JN_CLI="-Mjn-cli=libs/zig/jn-cli/src/root.zig"
            JN_PLUGIN="-Mjn-plugin=libs/zig/jn-plugin/src/root.zig"
            JN_ADDRESS="-Mjn-address=libs/zig/jn-address/src/root.zig"
            JN_PROFILE="-Mjn-profile=libs/zig/jn-profile/src/root.zig"

            mkdir -p dist/bin

            # Build jn orchestrator
            echo "Building jn..."
            pushd tools/zig/jn
            zig build-exe -O ReleaseFast \
              --dep jn-core -Mroot=./main.zig \
              -Mjn-core=../../../libs/zig/jn-core/src/root.zig \
              -femit-bin=../../../dist/bin/jn
            popd

            # Build CLI tools
            for tool in jn-cat jn-put jn-filter jn-head jn-tail jn-analyze jn-inspect jn-join jn-merge jn-sh jn-edit; do
              echo "Building $tool..."
              pushd tools/zig/$tool
              zig build-exe -O ReleaseFast \
                --dep jn-core --dep jn-cli --dep jn-address --dep jn-profile \
                -Mroot=./main.zig \
                -Mjn-core=../../../libs/zig/jn-core/src/root.zig \
                -Mjn-cli=../../../libs/zig/jn-cli/src/root.zig \
                -Mjn-address=../../../libs/zig/jn-address/src/root.zig \
                -Mjn-profile=../../../libs/zig/jn-profile/src/root.zig \
                -femit-bin=../../../dist/bin/$tool
              popd
            done

            # Build ZQ
            echo "Building zq..."
            pushd zq
            zig build-exe src/main.zig -O ReleaseFast -femit-bin=../dist/bin/zq
            popd

            # Build plugins
            for plugin in csv json jsonl gz yaml toml; do
              echo "Building $plugin..."
              pushd plugins/zig/$plugin
              zig build-exe -O ReleaseFast \
                --dep jn-core --dep jn-cli --dep jn-plugin \
                -Mroot=./main.zig \
                -Mjn-core=../../../libs/zig/jn-core/src/root.zig \
                -Mjn-cli=../../../libs/zig/jn-cli/src/root.zig \
                -Mjn-plugin=../../../libs/zig/jn-plugin/src/root.zig \
                -femit-bin=../../../dist/bin/$plugin
              popd
            done

            runHook postBuild
          '';

          installPhase = ''
            runHook preInstall

            mkdir -p $out/bin $out/lib/jn

            # Install binaries
            cp -r dist/bin/* $out/bin/

            # Install jn_home
            cp -r jn_home $out/lib/jn/

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

        devShell = pkgs.mkShell {
          buildInputs = [
            zig
            pkgs.python3
          ];

          shellHook = ''
            echo "JN development shell"
            echo "Zig version: $(zig version)"
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
