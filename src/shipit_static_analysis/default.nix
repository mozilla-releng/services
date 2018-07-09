{ releng_pkgs 
}: 

let

  inherit (releng_pkgs.lib) mkTaskclusterHook mkTaskclusterMergeEnv mkTaskclusterMergeRoutes mkPython fromRequirementsFile filterSource ;
  inherit (releng_pkgs.pkgs) writeScript gcc cacert gcc-unwrapped glibc glibcLocales xorg patch nodejs-8_x git python27 python35 coreutils shellcheck clang_5 zlib;
  inherit (releng_pkgs.pkgs.lib) fileContents concatStringsSep ;
  inherit (releng_pkgs.tools) pypi2nix mercurial;

  nodejs = nodejs-8_x;
  python = import ./requirements.nix { inherit (releng_pkgs) pkgs; };
  name = "mozilla-shipit-static-analysis";
  dirname = "shipit_static_analysis";

  # Customize gecko environment with Nodejs & Python 3 for linters
  gecko-env = releng_pkgs.gecko-env.overrideDerivation(old : {
    buildPhase = old.buildPhase + ''
      echo "export PATH=${nodejs}/bin:${python35}/bin:\$PATH" >> $out/bin/gecko-env
    '';
 } );

  mkBot = branch:
    let
      cacheKey = "services-" + branch + "-shipit-static-analysis";
      secretsKey = "repo:github.com/mozilla-releng/services:branch:" + branch;
      hook = mkTaskclusterHook {
        name = "Static analysis automated tests";
        owner = "jan@mozilla.com";
        taskImage = self.docker;
        workerType = if branch == "production" then "releng-svc-prod" else "releng-svc";
        scopes = [
          # Used by taskclusterProxy
          ("secrets:get:" + secretsKey)

          # Send emails to relman
          "notify:email:*"

          # Used by cache
          ("docker-worker:cache:" + cacheKey)

          # Needed to index the task in the TaskCluster index
          ("index:insert-task:project.releng.services.project." + branch + ".shipit_static_analysis.*")
        ];
        cache = {
          "${cacheKey}" = "/cache";
        };
        taskEnv = mkTaskclusterMergeEnv {
          env = {
            "SSL_CERT_FILE" = "${cacert}/etc/ssl/certs/ca-bundle.crt";
            "APP_CHANNEL" = branch;
            "MOZ_AUTOMATION" = "1";
          };
        };

        taskRoutes = [
          # Latest route
          ("index.project.releng.services.project." + branch + ".shipit_static_analysis.latest")
        ];

        taskCapabilities = {};
        taskCommand = [
          "/bin/shipit-static-analysis"
          "--taskcluster-secret"
          secretsKey
          "--cache-root"
          "/cache"
        ];
        taskArtifacts = {
          "public/results" = {
            path = "/tmp/results";
            type = "directory";
          };
        };
      };
    in
      releng_pkgs.pkgs.writeText "taskcluster-hook-${self.name}.json" (builtins.toJSON hook);

  includes = concatStringsSep ":" [
    "${gcc-unwrapped}/include/c++/${gcc-unwrapped.version}"
    "${gcc-unwrapped}/include/c++/${gcc-unwrapped.version}/backward"
    "${gcc-unwrapped}/include/c++/${gcc-unwrapped.version}/x86_64-unknown-linux-gnu"
    "${glibc.dev}/include/"
    "${xorg.libX11.dev}/include"
    "${xorg.xproto}/include"
    "${xorg.libXrender.dev}/include"
    "${xorg.renderproto}/include"
  ];

  self = mkPython {
    inherit python name dirname;
    version = fileContents ./VERSION;
    src = filterSource ./. { inherit name; };
    buildInputs =
      [ mercurial clang_5 ] ++ 
      (fromRequirementsFile ./../../lib/cli_common/requirements-dev.txt python.packages) ++
      (fromRequirementsFile ./requirements-dev.txt python.packages);
    propagatedBuildInputs =
      [
        # Needed for the static analysis
        glibc
        gcc
        patch
        shellcheck

        # Needed for linters
        nodejs

        # Gecko environment
        gecko-env
      ] ++
      (fromRequirementsFile ./requirements.txt python.packages);
    postInstall = ''
      mkdir -p $out/tmp
      mkdir -p $out/bin
      mkdir -p $out/usr/bin
      mkdir -p $out/lib64
      ln -s ${mercurial}/bin/hg $out/bin
      ln -s ${patch}/bin/patch $out/bin

      # Mozlint deps
      ln -s ${gcc}/bin/gcc $out/bin
      ln -s ${nodejs}/bin/node $out/bin
      ln -s ${nodejs}/bin/npm $out/bin
      ln -s ${git}/bin/git $out/bin
      ln -s ${python27}/bin/python2.7 $out/bin/python2.7
      ln -s ${python27}/bin/python2.7 $out/bin/python2
      ln -s ${python35}/bin/python3.5 $out/bin/python3.5
      ln -s ${python35}/bin/python3.5 $out/bin/python3
      ln -s ${coreutils}/bin/env $out/usr/bin/env
      ln -s ${coreutils}/bin/ld $out/bin
      ln -s ${coreutils}/bin/as $out/bin

      # Add program interpreter needed to run clang Taskcluster static build
      # Found this info by using "readelf -l"
      ln -s ${glibc}/lib/ld-linux-x86-64.so.2 $out/lib64

      # Expose gecko env in final output
      ln -s ${gecko-env}/bin/gecko-env $out/bin
    '';
    shellHook = ''
      export PATH="${mercurial}/bin:${git}/bin:${python27}/bin:${python35}/bin:${nodejs}/bin:$PATH"

      # Setup mach automation
      export MOZ_AUTOMATION=1

      # Use clang mozconfig from gecko-env
      export MOZCONFIG=${gecko-env}/conf/mozconfig

      # Use common mozilla state directory
      export MOZBUILD_STATE_PATH=/tmp/mozilla-state

      # Extras for clang-tidy
      export CPLUS_INCLUDE_PATH=${includes}
      export C_INCLUDE_PATH=${includes}

      # Export linters tools
      export CODESPELL=${python.packages.codespell}/bin/codespell
      export SHELLCHECK=${shellcheck}/bin/shellcheck
    '';

    dockerEnv =
      [ "CPLUS_INCLUDE_PATH=${includes}"
        "C_INCLUDE_PATH=${includes}"
        "MOZCONFIG=${gecko-env}/conf/mozconfig"
        "CODESPELL=${python.packages.codespell}/bin/codespell"
        "SHELLCHECK=${shellcheck}/bin/shellcheck"
        "MOZ_AUTOMATION=1"
        "MOZBUILD_STATE_PATH=/tmp/mozilla-state"
        "SHELL=xterm"

        # Needed to run clang Taskcluster static build
        # only on built docker image from scratch
        "LD_LIBRARY_PATH=${zlib}/lib"
      ];
    dockerCmd = [];

    passthru = {
      deploy = {
        testing = mkBot "testing";
        staging = mkBot "staging";
        production = mkBot "production";
      };
      update = writeScript "update-${name}" ''
        pushd ${self.src_path}
        ${pypi2nix}/bin/pypi2nix -v \
          -V 3.5 \
          -E "libffi openssl pkgconfig freetype.dev" \
          -r requirements.txt \
          -r requirements-dev.txt
        popd
      '';
    };
  };

in self
