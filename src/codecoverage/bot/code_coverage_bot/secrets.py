# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from code_coverage_bot import config
from code_coverage_bot.taskcluster import taskcluster_config


class Secrets(dict):
    CODECOV_REPO = 'CODECOV_REPO'
    CODECOV_TOKEN = 'CODECOV_TOKEN'
    CODECOV_ACCESS_TOKEN = 'CODECOV_ACCESS_TOKEN'
    GECKO_DEV_USER = 'GECKO_DEV_USER'
    GECKO_DEV_PWD = 'GECKO_DEV_PWD'
    HG_GIT_MAPPER = 'HG_GIT_MAPPER'
    EMAIL_ADDRESSES = 'EMAIL_ADDRESSES'
    REPO_MAPPER_EMAIL_ADDRESSES = 'REPO_MAPPER_EMAIL_ADDRESSES'
    APP_CHANNEL = 'APP_CHANNEL'
    BACKEND_HOST = 'BACKEND_HOST'
    PHABRICATOR_ENABLED = 'PHABRICATOR_ENABLED'
    PHABRICATOR_URL = 'PHABRICATOR_URL'
    PHABRICATOR_TOKEN = 'PHABRICATOR_TOKEN'
    GOOGLE_CLOUD_STORAGE = 'GOOGLE_CLOUD_STORAGE'

    def load(self, taskcluster_secret):
        taskcluster_config.load_secrets(
            taskcluster_secret,
            config.PROJECT_NAME,
            required=[
                Secrets.APP_CHANNEL,
                Secrets.BACKEND_HOST,
                Secrets.CODECOV_REPO,
                Secrets.CODECOV_TOKEN,
                Secrets.CODECOV_ACCESS_TOKEN,
                Secrets.GOOGLE_CLOUD_STORAGE,
                Secrets.PHABRICATOR_ENABLED,
                Secrets.PHABRICATOR_URL,
                Secrets.PHABRICATOR_TOKEN,
            ],
            existing={
                Secrets.REPO_MAPPER_EMAIL_ADDRESSES: []
            },
        )
        self.update(taskcluster_config.secrets)


secrets = Secrets()
