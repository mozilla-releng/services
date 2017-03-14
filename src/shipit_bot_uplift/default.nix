{ releng_pkgs 
}: 

let

  inherit (releng_pkgs.lib) mkTaskclusterHook mkPython fromRequirementsFile filterSource;
  inherit (releng_pkgs.pkgs) writeScript makeWrapper mercurial cacert fetchurl;
  inherit (releng_pkgs.pkgs.stdenv) mkDerivation;
  inherit (releng_pkgs.pkgs.lib) fileContents optional licenses;
  inherit (releng_pkgs.tools) pypi2nix;

  python = import ./requirements.nix { inherit (releng_pkgs) pkgs; };
  name = "mozilla-shipit-bot-uplift";
  dirname = "shipit_bot_uplift";

  robustcheckout = mkDerivation {
    name = "robustcheckout";
    src = fetchurl { 
      url = "https://hg.mozilla.org/hgcustom/version-control-tools/archive/1a8415be17e8.tar.bz2";
      sha256 = "005n7ar8cn7162s1qx970x1aabv263zp7mxm38byxc23nzym37kn";
    };
    installPhase = ''
      mkdir -p $out
      cp -rf hgext/robustcheckout $out
    '';
    doCheck = false;
    buildInputs = [];
    propagatedBuildInputs = [ ];
    meta = {
      homepage = "https://hg.mozilla.org/hgcustom/version-control-tools";
      license = licenses.mit;
      description = "Mozilla Version Control Tools: robustcheckout";
    };
  };

  mercurial' = mercurial.overrideDerivation (old: {
    postInstall = old.postInstall + ''
      cat > $out/etc/mercurial/hgrc <<EOF
      [web]
      cacerts = ${cacert}/etc/ssl/certs/ca-bundle.crt

      [extensions]
      purge =
      robustcheckout = ${robustcheckout}/robustcheckout/__init__.py
      EOF
    '';
  });

  mkBot = branch:
    let
      cacheKey = "shipit-bot-" + branch;
      secretsKey = "repo:github.com/mozilla-releng/services:branch:" + branch;
    in
      mkTaskclusterHook {
        name = "Shipit bot updating bug analysis";
        owner = "babadie@mozilla.com";
        schedule = [ "0 0 * * * *" ];  # every hour
        taskImage = self.docker;
        scopes = [
          # Used by taskclusterProxy
          ("secrets:get:" + secretsKey)

          # Email notifications
          "notify:email:babadie@mozilla.com"
          "notify:email:sledru@mozilla.com"

          # Used by cache
          ("docker-worker:cache:" + cacheKey)
        ];
        cache = {
          "${cacheKey}" = "/cache";
        };
        taskEnv = {
          "SSL_CERT_FILE" = "${releng_pkgs.pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
        };
        taskCommand = [
          "/bin/shipit-bot-uplift"
          "--secrets"
          secretsKey
          "--cache-root"
          "/cache"
        ];
      };

  self = mkPython {
    inherit python name dirname;
    inProduction = true;
    version = fileContents ./../../VERSION;
    src = filterSource ./. { inherit name; };
    buildInputs =
      fromRequirementsFile ./requirements-dev.txt python.packages;
    propagatedBuildInputs =
      fromRequirementsFile ./requirements.txt python.packages;
    postInstall = ''
      mkdir -p $out/bin
      ln -s ${mercurial'}/bin/hg $out/bin
    '';
    passthru = {
      taskclusterHooks = {
        master = {
        };
        staging = {
          bot = mkBot "staging";
        };
        production = {
          bot = mkBot "production";
        };
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
