# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import

import base64
import os
import cli_common.taskcluster
import shipit_signoff.config
import backend_common.auth0


DEBUG = bool(os.environ.get('DEBUG', False))
# TODO: is this the right way to tell the difference between staging and prod?
# Maybe we should require BALROG_API_ROOT set in the environment instead?
STAGING = bool(os.environ.get('DEBUG', False))
# Local auth defaults to True if DEBUG is set to True.
LOCAL_AUTH = bool(os.environ.get('LOCAL_AUTH', DEBUG))


# -- LOAD SECRETS -------------------------------------------------------------

required = [
    'SECRET_KEY_BASE64',
    'DATABASE_URL',
    'APP_URL',
    'AUTH_DOMAIN',
    'AUTH_CLIENT_ID',
    'AUTH_CLIENT_SECRET',
    'AUTH_REDIRECT_URI',
    'BALROG_USERNAME',
    'BALROG_PASSWORD',
]

existing = {x: os.environ.get(x) for x in required if x in os.environ}

secrets = cli_common.taskcluster.get_secrets(
    os.environ.get('TASKCLUSTER_SECRET'),
    shipit_signoff.config.PROJECT_NAME,
    required=required,
    existing=existing,
    taskcluster_client_id=os.environ.get('TASKCLUSTER_CLIENT_ID'),
    taskcluster_access_token=os.environ.get('TASKCLUSTER_ACCESS_TOKEN'),
)

locals().update(secrets)

SECRET_KEY = base64.b64decode(secrets['SECRET_KEY_BASE64'])


# -- DATABASE -----------------------------------------------------------------

SQLALCHEMY_DATABASE_URI = secrets['DATABASE_URL']
SQLALCHEMY_TRACK_MODIFICATIONS = False


# -- AUTH --------------------------------------------------------------------


# OIDC_CALLBACK_ROUTE='/redirect_url'
OIDC_USER_INFO_ENABLED = True
args = [
    secrets['AUTH_CLIENT_ID'],
    secrets['AUTH_CLIENT_SECRET'],
    secrets['APP_URL'],
]
if LOCAL_AUTH:
    args.append(secrets['APP_URL'] + 'fake_auth')
OIDC_CLIENT_SECRETS = backend_common.auth0.create_auth0_secrets_file(*args)

# -- BALROG -------------------------------------------------------------------

# Allow users to override for local development
if os.environ.get('BALROG_API_ROOT'):
    BALROG_API_ROOT = os.environ.get('BALROG_API_ROOT')
else:
    if not STAGING:
        BALROG_API_ROOT = 'https://aus4-admin.mozilla.org/api'
    else:
        BALROG_API_ROOT = 'https://balrog-admin.stage.mozaws.net/api'

BALROG_USERNAME = os.environ.get('BALROG_USERNAME', secrets['BALROG_USERNAME'])
BALROG_PASSWORD = os.environ.get('BALROG_PASSWORD', secrets['BALROG_PASSWORD'])
