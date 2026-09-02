{
  description = "Ascension archive: scraper, client extractor, and viewer";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        # StormLib is the one hard native dependency. It is loaded at runtime through
        # ctypes rather than linked, so the path is handed over by an environment
        # variable instead of a build flag.
        stormlib = pkgs.stormlib;
        stormPath = "${stormlib}/lib/libstorm.so";

        python = pkgs.python313;
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            # The Python half: scraping, MPQ and DBC reading, the spellbook, the server.
            python
            uv
            stormlib

            # The web half. Pinned here so the machine needs none of it installed;
            # `nix develop` is the only prerequisite.
            nodejs_22          # npm ships with it

            # Running the whole thing as it is deployed.
            docker-compose

            # Used by the extractor and the preview routes.
            zlib
            bzip2
          ];

          # Pillow is installed through uv rather than nix, and its wheels expect to
          # find these at load time.
          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
            pkgs.zlib pkgs.libjpeg pkgs.libwebp pkgs.libtiff pkgs.freetype
            pkgs.lcms2 pkgs.openjpeg pkgs.libimagequant
          ];

          ASCENSION_STORMLIB = stormPath;

          shellHook = ''
            echo "ascension archive — $(python --version), node $(node --version)"
            echo "  ASCENSION_STORMLIB=$ASCENSION_STORMLIB"
            echo
            echo "  uv sync --extra assets      set up the Python side"
            echo "  npm --prefix web install    set up the viewer"
            echo "  docker compose up           run both, isolated"
          '';
        };

        # The same StormLib the shell uses, so a container build and a local run
        # cannot drift apart.
        packages.stormlib = stormlib;
      });
}
