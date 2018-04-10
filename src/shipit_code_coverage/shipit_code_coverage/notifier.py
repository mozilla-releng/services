# -*- coding: utf-8 -*-

import requests

from cli_common.log import get_logger
from cli_common.taskcluster import get_service
from cli_common.utils import retry
from shipit_code_coverage.secrets import secrets

logger = get_logger(__name__)


class Notifier(object):

    def __init__(self, revision, client_id, access_token):
        self.revision = revision
        self.notify_service = get_service('notify', client_id, access_token)

    def get_coverage_summary(self, changeset):
        r = requests.get('https://uplift.shipit.staging.mozilla-releng.net/coverage/changeset_summary/{}'.format(changeset))
        r.raise_for_status()

        if r.status_code == 202:
            return None

        return r.json()

    def notify(self):
        content = ''

        # Get pushlog and ask the backend to generate the coverage by changeset
        # data, which will be cached.
        r = requests.get('https://hg.mozilla.org/mozilla-central/json-pushes?changeset={}&version=2&full'.format(self.revision))
        r.raise_for_status()
        push_data = r.json()
        changesets = sum((data['changesets'] for data in push_data['pushes'].values()), [])

        for changeset in changesets:
            desc = changeset['desc'].split('\n')[0]

            if any(text in desc for text in ['r=merge', 'a=merge']):
                continue

            rev = changeset['node']

            try:
                coverage = retry(lambda: self.get_coverage_summary(rev))
            except requests.exceptions.HTTPError:
                logger.warn('Failure to retrieve coverage summary', rev=rev)
                continue

            if coverage is None:
                continue

            if coverage['commit_covered'] < 0.2 * coverage['commit_added']:
                content += '* [{}](https://firefox-code-coverage.herokuapp.com/#/changeset/{}): {} covered out of {} added.\n'.format(desc, rev, coverage['commit_covered'], coverage['commit_added'])  # noqa

        if content == '':
            return
        elif len(content) > 102400:
            # Content is 102400 chars max
            content = content[:102000] + '\n\n... Content max limit reached!'

        for email in secrets[secrets.EMAIL_ADDRESSES]:
            self.notify_service.email({
                'address': email,
                'subject': 'Coverage patches for {}'.format(self.revision),
                'content': content,
                'template': 'fullscreen',
            })
