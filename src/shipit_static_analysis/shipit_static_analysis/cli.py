# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import

from shipit_static_analysis.workflow import Workflow
from shipit_static_analysis.batchreview import build_api_root
from shipit_static_analysis.lock import LockDir
from shipit_static_analysis import config
from cli_common.click import taskcluster_options
from cli_common.log import init_logger
from cli_common.taskcluster import get_secrets
import click
import re
from cli_common.log import get_logger

logger = get_logger(__name__)

REGEX_COMMIT = re.compile(r'(\w+):(\d+):(\d+)')


@click.command()
@taskcluster_options
@click.argument('commits', envvar='COMMITS')
@click.option(
    '--cache-root',
    required=True,
    help='Cache root, used to pull changesets'
)
def main(commits,
         cache_root,
         taskcluster_secret,
         taskcluster_client_id,
         taskcluster_access_token,
         ):

    secrets = get_secrets(taskcluster_secret,
                          config.PROJECT_NAME,
                          required=(
                              'APP_CHANNEL',
                              'STATIC_ANALYSIS_NOTIFICATIONS',
                              'MOZREVIEW_URL',
                              'MOZREVIEW_USER',
                              'MOZREVIEW_API_KEY',
                          ),
                          existing={
                              'APP_CHANNEL': 'development',
                              'MOZREVIEW_ENABLED': False,
                              'MOZREVIEW_PUBLISH_SUCCESS': False,
                              'CLANG_FORMAT_ENABLED': True,
                          },
                          taskcluster_client_id=taskcluster_client_id,
                          taskcluster_access_token=taskcluster_access_token,
                          )

    init_logger(config.PROJECT_NAME,
                PAPERTRAIL_HOST=secrets.get('PAPERTRAIL_HOST'),
                PAPERTRAIL_PORT=secrets.get('PAPERTRAIL_PORT'),
                SENTRY_DSN=secrets.get('SENTRY_DSN'),
                MOZDEF=secrets.get('MOZDEF'),
                )

    mozreview = build_api_root(
        secrets['MOZREVIEW_URL'],
        secrets['MOZREVIEW_USER'],
        secrets['MOZREVIEW_API_KEY'],
    )

    with LockDir(cache_root, 'shipit-sa-') as work_dir:
        w = Workflow(work_dir,
                     secrets['STATIC_ANALYSIS_NOTIFICATIONS'],
                     secrets['APP_CHANNEL'],
                     mozreview,
                     secrets['MOZREVIEW_ENABLED'],
                     secrets['MOZREVIEW_PUBLISH_SUCCESS'],
                     secrets['CLANG_FORMAT_ENABLED'],
                     taskcluster_client_id,
                     taskcluster_access_token,
                     )

        for commit in REGEX_COMMIT.findall(commits):
            try:
                w.run(*commit)
            except Exception as e:
                # Log errors to papertrail
                logger.error(
                    'Static analysis failure',
                    commit=commit,
                    error=e,
                )


if __name__ == '__main__':
    main()
