# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import os
import tempfile

import structlog
from libmozdata.phabricator import PhabricatorAPI

from pulselistener import config
from pulselistener import taskcluster
from pulselistener.lib.log import init_logger
from pulselistener.listener import EventListener

logger = structlog.get_logger(__name__)


def parse_cli():
    '''
    Setup CLI options parser
    '''
    parser = argparse.ArgumentParser(description='Mozilla Code Review Bot')
    parser.add_argument(
        '--cache-root',
        help='Cache root, used to pull changesets',
        default=os.path.join(tempfile.gettempdir(), 'pulselistener'),
    )
    parser.add_argument(
        '--phab-build-target',
        type=str,
        help='A Phabricator build target PHID to test'
    )
    parser.add_argument(
        '--taskcluster-secret',
        help='Taskcluster Secret path',
        default=os.environ.get('TASKCLUSTER_SECRET')
    )
    parser.add_argument(
        '--taskcluster-client-id',
        help='Taskcluster Client ID',
    )
    parser.add_argument(
        '--taskcluster-access-token',
        help='Taskcluster Access token',
    )
    return parser.parse_args()


def main():
    args = parse_cli()
    taskcluster.auth(
        args.taskcluster_client_id,
        args.taskcluster_access_token,
    )
    taskcluster.load_secrets(
        args.taskcluster_secret,
        config.PROJECT_NAME,
        required=(
            'PULSE_USER',
            'PULSE_PASSWORD',
            'HOOKS',
            'ADMINS',
            'PHABRICATOR',
            'repositories',
        ),
        existing=dict(
            HOOKS=[],
            ADMINS=['babadie@mozilla.com', 'mcastelluccio@mozilla.com'],
            repositories=[]
        ),
    )

    init_logger(config.PROJECT_NAME,
                PAPERTRAIL_HOST=taskcluster.secrets.get('PAPERTRAIL_HOST'),
                PAPERTRAIL_PORT=taskcluster.secrets.get('PAPERTRAIL_PORT'),
                SENTRY_DSN=taskcluster.secrets.get('SENTRY_DSN'),
                )

    phabricator = PhabricatorAPI(
        api_key=taskcluster.secrets['PHABRICATOR']['token'],
        url=taskcluster.secrets['PHABRICATOR']['url'],
    )

    pl = EventListener(taskcluster.secrets['PULSE_USER'],
                       taskcluster.secrets['PULSE_PASSWORD'],
                       taskcluster.secrets['HOOKS'],
                       taskcluster.secrets['repositories'],
                       phabricator,
                       args.cache_root,
                       taskcluster.secrets['PHABRICATOR'].get('publish', False),
                       args.taskcluster_client_id,
                       args.taskcluster_access_token,
                       )
    logger.info('Listening to pulse messages...')

    if args.phab_build_target:
        pl.add_build(args.phab_build_target)

    pl.run()


if __name__ == '__main__':
    main()
