# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

if __name__ == "__main__":
    from shipit_signoff.flask_control import app

    app.run(**app.run_options())
