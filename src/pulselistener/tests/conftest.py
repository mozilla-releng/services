# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import os.path
import urllib.parse
from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from unittest.mock import MagicMock

import hglib
import pytest
import responses
from libmozdata.phabricator import PhabricatorAPI
from taskcluster.utils import stringDate

from pulselistener.code_coverage import CodeCoverage

MOCK_DIR = os.path.join(os.path.dirname(__file__), 'mocks')


@pytest.fixture
def QueueMock():
    class Mock():
        def __init__(self):
            self.created_tasks = []

        def status(self, task_id):
            for status in ['failed', 'completed', 'exception', 'pending']:
                if status in task_id:
                    return {
                        'status': {
                            'state': status,
                        }
                    }
            assert False

        def task(self, task_id):
            now = datetime.utcnow()

            if 'retry:' in task_id:
                retry = int(task_id[task_id.index('retry:')+6])
            else:
                retry = 3

            return {
                'created': stringDate(now),
                'deadline': stringDate(now + timedelta(hours=2)),
                'dependencies': [],
                'expires': stringDate(now + timedelta(hours=24)),
                'payload': {
                    'command': ['/bin/command'],
                    'env': {},
                    'image': 'alpine',
                    'maxRunTime': 3600,
                },
                'priority': 'lowest',
                'provisionerId': 'aws-provisioner-v1',
                'requires': 'all-completed',
                'retries': retry,
                'scopes': [],
                'routes': [
                    'index.{}.latest'.format(task_id),
                ],
                'taskGroupId': 'group-{}'.format(task_id),
                'workerType': 'niceWorker'
            }

        def createTask(self, task_id, payload):
            self.created_tasks.append((task_id, payload))

    return Mock()


@pytest.fixture
def NotifyMock():
    class Mock():
        def __init__(self):
            self.email_obj = {}

        def email(self, obj):
            self.email_obj.update(obj)

    return Mock()


@pytest.fixture
def HooksMock():
    class Mock():
        def __init__(self):
            self.obj = {}

        def triggerHook(self, group_id, hook_id, payload):
            self.obj = {
              'group_id': group_id,
              'hook_id': hook_id,
              'payload': payload,
            }
            return {
                'status': {
                    'taskId': 'fake_task_id',
                },
            }

    return Mock()


@pytest.fixture
def IndexMock():
    class Mock():
        def __init__(self):
            pass

        def findTask(self, path):
            assert path.startswith('project.releng.services.tasks.')
            failed = 'failed' in path
            return {
                'taskId': path[30:],
                'data': {
                    'state': failed and 'error' or 'done',
                    'error_code': failed and 'somethingBad' or None,
                    'monitoring_restart': (failed and 'restart' in path)
                }
            }

    return Mock()


@pytest.fixture
@contextmanager
def PhabricatorMock():
    '''
    Mock phabricator authentication process
    '''
    json_headers = {
        'Content-Type': 'application/json',
    }

    def _response(name):
        path = os.path.join(MOCK_DIR, 'phabricator', '{}.json'.format(name))
        assert os.path.exists(path), 'Missing mock {}'.format(path)
        return open(path).read()

    def _phab_params(request):
        # What a weird way to send parameters
        return json.loads(urllib.parse.parse_qs(request.body)['params'][0])

    def _diff_search(request):
        params = _phab_params(request)
        assert 'constraints' in params
        if 'revisionPHIDs' in params['constraints']:
            # Search from revision
            mock_name = 'search-{}'.format(params['constraints']['revisionPHIDs'][0])
        elif 'phids' in params['constraints']:
            # Search from diffs
            diffs = '-'.join(params['constraints']['phids'])
            mock_name = 'search-{}'.format(diffs)
        elif 'ids' in params['constraints']:
            diffs = '-'.join(map(str, params['constraints']['ids']))
            mock_name = 'search-{}'.format(diffs)
        else:
            raise Exception('Unsupported diff mock {}'.format(params))
        return (200, json_headers, _response(mock_name))

    def _revision_search(request):
        params = _phab_params(request)
        assert 'constraints' in params
        ids = '-'.join(map(str, params['constraints']['ids']))
        return (200, json_headers, _response('search-rev-{}'.format(ids)))

    def _diff_raw(request):
        params = _phab_params(request)
        assert 'diffID' in params
        return (200, json_headers, _response('raw-{}'.format(params['diffID'])))

    def _edges(request):
        params = _phab_params(request)
        assert 'sourcePHIDs' in params
        return (200, json_headers, _response('edges-{}'.format(params['sourcePHIDs'][0])))

    def _create_artifact(request):
        params = _phab_params(request)
        assert 'buildTargetPHID' in params
        return (200, json_headers, _response('artifact-{}'.format(params['buildTargetPHID'])))

    def _send_message(request):
        params = _phab_params(request)
        assert 'buildTargetPHID' in params
        name = 'message-{}-{}'.format(params['buildTargetPHID'], params['type'])
        if params['unit']:
            name += '-unit'
        if params['lint']:
            name += '-lint'
        return (200, json_headers, _response(name))

    with responses.RequestsMock(assert_all_requests_are_fired=False) as resp:

        resp.add(
            responses.POST,
            'http://phabricator.test/api/user.whoami',
            body=_response('auth'),
            content_type='application/json',
        )

        resp.add_callback(
            responses.POST,
            'http://phabricator.test/api/edge.search',
            callback=_edges,
        )

        resp.add_callback(
            responses.POST,
            'http://phabricator.test/api/differential.revision.search',
            callback=_revision_search,
        )

        resp.add_callback(
            responses.POST,
            'http://phabricator.test/api/differential.diff.search',
            callback=_diff_search,
        )

        resp.add_callback(
            responses.POST,
            'http://phabricator.test/api/differential.getrawdiff',
            callback=_diff_raw,
        )

        resp.add_callback(
            responses.POST,
            'http://phabricator.test/api/harbormaster.createartifact',
            callback=_create_artifact,
        )

        resp.add_callback(
            responses.POST,
            'http://phabricator.test/api/harbormaster.sendmessage',
            callback=_send_message,
        )

        resp.add(
            responses.POST,
            'http://phabricator.test/api/diffusion.repository.search',
            body=_response('repositories'),
            content_type='application/json',
        )

        resp.add(
            responses.POST,
            'http://phabricator.test/api/project.search',
            body=_response('projects'),
            content_type='application/json',
        )

        api = PhabricatorAPI(
            url='http://phabricator.test/api/',
            api_key='deadbeef',
        )
        api.mocks = resp  # used to assert in tests on callbacks
        yield api


def build_repository(tmpdir, name):
    '''
    Mock a local mercurial repo
    '''
    # Init empty repo
    repo_dir = str(tmpdir.mkdir(name).realpath())
    hglib.init(repo_dir)

    # Add default pull in Mercurial config
    hgrc = tmpdir.join(name, '.hg', 'hgrc')
    hgrc.write('[paths]\ndefault = {}'.format(repo_dir))

    # Open repo with config
    repo = hglib.open(repo_dir)

    # Commit a file on central
    readme = tmpdir.join(name, 'README.md')
    readme.write('Hello World')
    repo.add(str(readme.realpath()).encode('utf-8'))
    repo.branch(name=b'central', force=True)
    repo.commit(message=b'Readme', user='test')

    # Mock push to avoid reaching try server
    repo.push = MagicMock(return_value=True)

    return repo


@pytest.fixture
def mock_mc(tmpdir):
    '''
    Mock a Mozilla Central repository
    '''
    return build_repository(tmpdir, 'mozilla-central')


@pytest.fixture
def mock_nss(tmpdir):
    '''
    Mock an NSS repository
    '''
    return build_repository(tmpdir, 'nss')


@pytest.fixture
def code_coverage():
    '''
    Helper to build a CodeCoverage instance
    '''
    return CodeCoverage({
       'PULSE_USER': 'test',
       'PULSE_PASSWORD': 'xxx',
       'APP_CHANNEL': 'staging',
       'ADMINS': ['test@allizom.org'],
    }, 'user', 'token')
