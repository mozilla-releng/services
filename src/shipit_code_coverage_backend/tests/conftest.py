# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import glob
import json
import os

import pytest

import backend_common.testing

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture(scope='session')
def app():
    '''
    Load shipit_code_coverage_backend app in test mode
    '''
    import shipit_code_coverage_backend

    config = backend_common.testing.get_app_config({
    })
    app = shipit_code_coverage_backend.create_app(config)

    with app.app_context():
        backend_common.testing.configure_app(app)
        yield app


@pytest.fixture
async def coverage_responses(aresponses):
    with open(os.path.join(FIXTURES_DIR, 'codecov_main.json')) as f:
        aresponses.add('codecov.io',
                       '/api/gh/marco-c/gecko-dev',
                       'get',
                       aresponses.Response(text=f.read(), content_type='application/json'))

    directories = [
        {
            'path': 'hgmo_json_revs',
            'host': 'hg.mozilla.org',
            'url': lambda fname: '/mozilla-central/json-rev/{}'.format(fname),
        },
        {
            'path': 'hgmo_json_pushes',
            'host': 'hg.mozilla.org',
            'url': lambda fname: '/mozilla-central/json-pushes?version=2&full=1&startID={}&endID={}'.format(int(fname), int(fname) + 8),
            'match_querystring': True,
        },
        {
            'path': 'hg_git_map',
            'host': 'api.pub.build.mozilla.org',
            'url': lambda fname: '/mapper/gecko-dev/rev/hg/{}'.format(fname),
        },
        {
            'path': 'git_hg_map',
            'host': 'api.pub.build.mozilla.org',
            'url': lambda fname: '/mapper/gecko-dev/rev/git/{}'.format(fname),
        },
        {
            'path': 'codecov_commits',
            'host': 'codecov.io',
            'url': lambda fname: '/api/gh/marco-c/gecko-dev/commit/{}'.format(fname),
            'status': lambda data: json.loads(data)['meta']['status'],
        },
        {
            'path': 'codecov_src',
            'host': 'codecov.io',
            'url': lambda fname: '/api/gh/marco-c/gecko-dev/src/{}'.format(fname.replace('_', '/')),
            'status': lambda data: json.loads(data)['meta']['status'],
        },
        {
            'path': 'hgmo_json_annotate',
            'host': 'hg.mozilla.org',
            'url': lambda fname: '/mozilla-central/json-annotate/{}'.format(fname.replace('_', '/')),
        },
    ]

    for directory in directories:
        dir_path = os.path.join(FIXTURES_DIR, directory['path'])
        for fname in os.listdir(dir_path):
            with open(os.path.join(dir_path, fname)) as f:
                data = f.read()
                match_querystring = directory['match_querystring'] if 'match_querystring' in directory else False
                content_type = 'application/json' if fname.endswith('.json') else 'text/plain'
                status = directory['status'](data) if 'status' in directory else 200

                aresponses.add(directory['host'],
                               directory['url'](os.path.splitext(fname)[0]),
                               'get',
                               aresponses.Response(text=data, content_type=content_type, status=status),
                               match_querystring=match_querystring)


@pytest.fixture(scope='session')
def coverage_changeset_by_file():
    with open(os.path.join(FIXTURES_DIR, 'coverage_changeset_by_file.json')) as f:
        changeset_by_file_info = json.load(f)

    for entry in changeset_by_file_info:
        entry['data'] = {int(key): value for key, value in entry['data'].items()}

    return changeset_by_file_info


@pytest.fixture(scope='session')
def coverage_builds():
    paths = glob.glob(os.path.join(FIXTURES_DIR, 'coverage_build_*.json'))
    builds = {'info': {}, 'summary': {}}
    for path in sorted(paths):
        with open(path) as f:
            build_data = json.load(f)
        builds['info'].update(build_data['info'])
        builds['summary'].update(build_data['summary'])

    return builds
