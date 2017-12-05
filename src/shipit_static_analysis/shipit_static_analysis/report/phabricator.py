# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from cli_common import log
from shipit_static_analysis.clang import ClangIssue
from shipit_static_analysis.report.base import Reporter
from shipit_static_analysis.revisions import PhabricatorRevision
from urllib.parse import urlparse
import requests

logger = log.get_logger(__name__)


class ConduitError(Exception):
    '''
    Exception to be raised when Phabricator returns an error response.
    '''
    def __init__(self, msg, error_code=None, error_info=None):
        super(ConduitError, self).__init__(msg)
        self.error_code = error_code
        self.error_info = error_info
        logger.warn('Conduit API error {} : {}'.format(
            self.error_code,
            self.error_info or 'unknown'
        ))

    @classmethod
    def raise_if_error(cls, response_body):
        '''
        Raise a ConduitError if the provided response_body was an error.
        '''
        if response_body['error_code'] is not None:
            raise cls(
                response_body.get('error_info'),
                error_code=response_body.get('error_code'),
                error_info=response_body.get('error_info')
            )


class PhabricatorReporter(Reporter):
    '''
    API connector to report on Phabricator
    '''
    def __init__(self, configuration, *args):
        self.url, self.api_key = self.requires(configuration, 'url', 'api_key')
        assert self.url.endswith('/api/'), \
            'Phabricator API must end with /api/'

        # Test authentication
        user = self.request('user.whoami')
        logger.info('Authenticated on phabricator', url=self.url, user=user['realName'])

    @property
    def hostname(self):
        parts = urlparse(self.url)
        return parts.netloc

    def load_diff(self, phid):
        '''
        Find a differential diff details
        '''
        out = self.request(
            'differential.diff.search',
            constraints={
                'phids': [phid, ],
            },
        )

        data = out['data']
        assert len(data) == 1, \
            'Not found'
        return data[0]

    def load_revision(self, phid):
        '''
        Find a differential revision details
        '''
        out = self.request(
            'differential.revision.search',
            constraints={
                'phids': [phid, ],
            },
        )

        data = out['data']
        assert len(data) == 1, \
            'Not found'
        return data[0]

    def publish(self, issues, revision, diff_url=None):
        '''
        Publish inline comments for each issues
        '''
        if not isinstance(revision, PhabricatorRevision):
            logger.info('Phabricator reporter only publishes Phabricator revisions. Skipping.')
            return

        # Use only publishable issues
        issues = list(filter(lambda i: i.is_publishable(), issues))
        if issues:

            # First publish inlines as drafts
            inlines = [
                self.comment_inline(revision, issue)
                for issue in issues
            ]
            logger.info('Added inline comments', ids=[i['id'] for i in inlines])

            # Then publish top comment
            self.comment(
                revision,
                self.build_comment(
                    issues=issues,
                    diff_url=diff_url,
                ),
            )
            logger.info('Published phabricator comment')

        else:
            # TODO: Publish a validated comment ?
            logger.info('No issues to publish on phabricator')

    def comment(self, revision, message):
        '''
        Comment on a Differential revision
        Using a frozen method as new transactions does not
        seem to support inlines publication
        '''
        assert isinstance(revision, PhabricatorRevision)

        return self.request(
            'differential.createcomment',
            revision_id=revision.id,
            message=message,
            attach_inlines=1,
        )

    def comment_inline(self, revision, issue):
        '''
        Post an inline comment on a diff
        '''
        assert isinstance(revision, PhabricatorRevision)
        assert isinstance(issue, ClangIssue)
        # TODO: check issue is instance of base Issue

        inline = self.request(
            'differential.createinline',
            diffID=revision.diff_id,
            filePath=issue.path,
            lineNumber=issue.line,
            lineLength=issue.nb_lines,
            content=issue.as_text(),

            # This displays on the new file (right side)
            # Python boolean is not recognized by Conduit :/
            isNewFile=1,
        )
        return inline

    def request(self, path, **payload):
        '''
        Send a request to Phabricator API
        '''

        def flatten_params(params):
            '''
            Flatten nested objects and lists.
            Phabricator requires query data in a application/x-www-form-urlencoded
            format, so we need to flatten our params dictionary.
            '''
            assert isinstance(params, dict)
            flat = {}
            remaining = list(params.items())

            # Run a depth-ish first search building the parameter name
            # as we traverse the tree.
            while remaining:
                key, o = remaining.pop()
                if isinstance(o, dict):
                    gen = o.items()
                elif isinstance(o, list):
                    gen = enumerate(o)
                else:
                    flat[key] = o
                    continue

                remaining.extend(('{}[{}]'.format(key, k), v) for k, v in gen)

            return flat

        # Add api token to payload
        payload['api.token'] = self.api_key

        # Run POST request on api
        response = requests.post(
            self.url + path,
            data=flatten_params(payload),
        )

        # Check response
        data = response.json()
        assert response.ok
        assert 'error_code' in data
        ConduitError.raise_if_error(data)

        # Outputs result
        assert 'result' in data
        return data['result']
