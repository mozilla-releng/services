{ pkgs, python }:

let

  inherit (pkgs.lib) fileContents;

  skipOverrides = overrides: self: super:
    let
      overridesNames = builtins.attrNames overrides;
      superNames = builtins.attrNames super;
    in
      builtins.listToAttrs
        (builtins.map
          (name: { inherit name;
                   value = python.overrideDerivation super."${name}" (overrides."${name}" self);
                 }
          )
          (builtins.filter
            (name: builtins.elem name superNames)
            overridesNames
          )
        );

in skipOverrides {

  # enable test for common packages

  "mozilla-cli-common" = import ./../lib/cli_common/default.nix { inherit pkgs; };
  "mozilla-backend-common" = import ./../lib/backend_common/default.nix { inherit pkgs; };

  # -- in alphabetic order --

  "async-timeout" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['pytest-runner'\],||" setup.py
    '';
  };

  "attrs" = self: old: {
    propagatedBuildInputs =
      builtins.filter
        (x: (builtins.parseDrvName x.name).name != "${python.__old.python.libPrefix}-${python.__old.python.libPrefix}-pytest")
        old.propagatedBuildInputs;
  };

  "awscli" = self: old: {
    propagatedBuildInputs = old.propagatedBuildInputs ++ (with pkgs; [ groff less ]);
    postInstall = ''
      mkdir -p $out/etc/bash_completion.d
      echo "complete -C $out/bin/aws_completer aws" > $out/etc/bash_completion.d/awscli
      mkdir -p $out/share/zsh/site-functions
      mv $out/bin/aws_zsh_completer.sh $out/share/zsh/site-functions
      rm $out/bin/aws.cmd
    '';
  };

  "chardet" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['pytest-runner'\],||" setup.py
    '';
  };

  "clickclick" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['six', 'flake8'\],||" setup.py
      sed -i -e "s|command_options=command_options,||" setup.py
    '';
  };

  "click-spinner" = self: old: {
    patchPhase = ''
      rm README.md
      touch README.md
    '';
  };

  "connexion" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['flake8'\],||" setup.py
      sed -i -e "s|jsonschema>=2.5.1|jsonschema|" setup.py
      sed -i -e "s|'pathlib>=1.0.1; python_version < \"3.4\"',||" setup.py
    '';
  };

  "coveralls" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['pytest-runner'\],||" setup.py
    '';
  };

  "esFrontLine" = self: old: {
     patchPhase = ''
      sed -i \
        -e "s|Flask==0.10.1|Flask|" \
        -e "s|requests==2.3.0|requests|" \
          setup.py
     '';
  };

  "fancycompleter" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['setuptools_scm'\],||" setup.py
    '';
  };

  "flake8" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['pytest-runner'\],||" setup.py
    '';
  };

  "flake8-debugger" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['pytest-runner'\],||" setup.py
    '';
  };

  "flask-talisman" = self: old: {
    # XXX: from https://github.com/GoogleCloudPlatform/flask-talisman/pull/8
    patchPhase = ''
      sed -i \
        -e "s|view_function = flask.current_app.view_functions\[|view_function = flask.current_app.view_functions.get(|" \
        -e "s|flask.request.endpoint\]|flask.request.endpoint)|" \
          flask_talisman/talisman.py
    '';
  };

  "jsonschema" = self: old: {
    patchPhase = ''
      sed -i -e 's|setup_requires=\["vcversioner>=2.16.0.0"\],||' setup.py
    '';
  };

  "libmozdata" = self: old: {
    # Remove useless dependency
    patchPhase = ''
      sed -i -e "s|setuptools>=28.6.1||" requirements.txt
      sed -i -e "s|python-dateutil.*|python-dateutil|" requirements.txt
    '';
  };

  "mccabe" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['pytest-runner'\],||" setup.py
    '';
  };

  "pdbpp" = self: old: {
    patchPhase = ''
      sed -i \
        -e "s|setup_requires=\['setuptools_scm'\],||" \
        -e "s|fancycompleter>=0.8|fancycompleter|" \
        setup.py
    '';
  };

  "pytest" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['setuptools-scm'\],||" setup.py
    '';
  };

  "pytest-asyncio" = self: old: {
    patchPhase = ''
      sed -i -e "s|pytest >= 3.0.6|pytest|" setup.py
    '';
  };

  "pytest-cov" = self: old: {
    patchPhase = ''
      sed -i -e "s|pytest>=2.6.0|pytest|" setup.py
    '';
  };

  "python-dateutil" = self: old: {
    patchPhase = ''
      sed -i -e "s|setup_requires=\['setuptools_scm'\],||" setup.py
    '';
  };

  "taskcluster" = self: old: {
    patchPhase = ''
      sed -i -e "s|six>=1.10.0,<1.11|six|" setup.py
    '';
  };

  "Flask-Cache" = self: old: {
    # XXX: from https://github.com/thadeusb/flask-cache/pull/189
    patchPhase = ''
      sed -i -e "s|flask.ext.cache|flask_cache|" flask_cache/jinja2ext.py
    '';
  };

  "RBTools" = self: old: {
    patches = [
         (pkgs.fetchurl {
           url = "https://github.com/La0/rbtools/commit/190b4adb768897f65cf7ec57806649bc14c8e45d.diff";
           sha256 = "1hh6i3cffsc4fxr4jqlxralnf78529i0pspm7jn686a2s6bh26mw";
         })
      ];
  };
}
