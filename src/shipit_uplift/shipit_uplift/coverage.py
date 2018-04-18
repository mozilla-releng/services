# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from abc import ABC
from abc import abstractmethod

import aiohttp
from async_lru import alru_cache
from cachetools import LRUCache

from cli_common import log
from shipit_uplift import secrets

logger = log.get_logger(__name__)


@alru_cache(maxsize=2048)
async def get_github_commit(mercurial_commit):
    async with aiohttp.request('GET', 'https://api.pub.build.mozilla.org/mapper/gecko-dev/rev/hg/{}'.format(mercurial_commit)) as r:
        text = await r.text()
        return text.split(' ')[0]


@alru_cache(maxsize=2048)
async def get_mercurial_commit(github_commit):
    async with aiohttp.request('GET', 'https://api.pub.build.mozilla.org/mapper/gecko-dev/rev/git/{}'.format(github_commit)) as r:
        text = await r.text()
        return text.split(' ')[1]


class CoverageException(Exception):
    pass


class Coverage(ABC):
    @staticmethod
    @abstractmethod
    async def get_coverage(changeset):
        pass

    @staticmethod
    @abstractmethod
    async def get_file_coverage(changeset, filename):
        pass

    @staticmethod
    @abstractmethod
    async def get_latest_build():
        pass


class CoverallsCoverage(Coverage):
    @staticmethod
    def _get(url=''):
        return aiohttp.request('GET', 'https://coveralls.io{}'.format(url))

    @staticmethod
    @alru_cache(maxsize=2048)
    async def get_coverage(changeset):
        async with CoverallsCoverage._get('/builds/{}.json'.format(await get_github_commit(changeset))) as r:
            if r.status != 200:
                raise CoverageException('Error while loading coverage data.')

            result = await r.json()

        return {
          'cur': result['covered_percent'],
          'prev': result['covered_percent'] + result['coverage_change'],
        }

    @staticmethod
    async def get_file_coverage(changeset, filename):
        async with CoverallsCoverage._get('/builds/{}/source.json?filename={}'.format(await get_github_commit(changeset), filename)) as r:
            if r.status != 200:
                return None

            return await r.json()

    @staticmethod
    async def get_latest_build():
        async with CoverallsCoverage._get('/github/marco-c/gecko-dev.json?page=1') as r:
            builds = (await r.json())['builds']

        return await get_mercurial_commit(builds[0]['commit_sha']), await get_mercurial_commit(builds[1]['commit_sha'])


class CodecovCoverage(Coverage):
    @staticmethod
    def _get(url=''):
        return aiohttp.request('GET', 'https://codecov.io/api/gh/marco-c/gecko-dev{}?access_token={}'.format(url, secrets.CODECOV_ACCESS_TOKEN))

    @staticmethod
    @alru_cache(maxsize=2048)
    async def get_coverage(changeset):
        async with CodecovCoverage._get('/commit/{}'.format(await get_github_commit(changeset))) as r:
            if r.status != 200:
                raise CoverageException('Error while loading coverage data.')

            result = await r.json()

        if result['commit']['state'] == 'error':
            logger.warn('{} is in an errored state.'.format(changeset))
            raise CoverageException('{} is in an errored state.'.format(changeset))

        return {
          'cur': result['commit']['totals']['c'],
          'prev': result['commit']['parent_totals']['c'] if result['commit']['parent_totals'] else '?',
        }

    @staticmethod
    async def get_file_coverage(changeset, filename):
        async with CodecovCoverage._get('/src/{}/{}'.format(await get_github_commit(changeset), filename)) as r:
            try:
                data = await r.json()
            except Exception as e:
                raise CoverageException('Can\'t parse codecov.io report for %s@%s (response: %s)' % (filename, changeset, r.text))

            if r.status != 200:
                if data['error']['reason'] == 'File not found in report':
                    return None

                raise CoverageException('Can\'t load codecov.io report for %s@%s (response: %s)' % (filename, changeset, r.text))

        if data['commit']['state'] == 'error':
            logger.warn('{} is in an errored state.'.format(changeset))
            raise CoverageException('{} is in an errored state.'.format(changeset))

        return dict([(int(l), v) for l, v in data['commit']['report']['files'][filename]['l'].items()])

    @staticmethod
    async def get_latest_build():
        async with CodecovCoverage._get() as r:
            commit = (await r.json())['commit']

        return await get_mercurial_commit(commit['commitid']), await get_mercurial_commit(commit['parent'])


class ActiveDataCoverage(Coverage):
    URL = 'https://activedata.allizom.org/query'

    @staticmethod
    @alru_cache(maxsize=2048)
    async def get_coverage(changeset):
        assert False, 'Not implemented'

    @staticmethod
    async def get_file_coverage(changeset, filename):
        assert False, 'Not implemented'

    @staticmethod
    async def get_latest_build():
        assert False, 'Not implemented'


coverage_service = CodecovCoverage()


# Push ID to build changeset
MAX_PUSHES = 2048
push_to_changeset_cache = LRUCache(maxsize=MAX_PUSHES)
# Changeset to changeset data (files and push ID)
MAX_CHANGESETS = 2048
changeset_cache = LRUCache(maxsize=MAX_CHANGESETS)


async def get_pushes(push_id):
    async with aiohttp.request('GET', 'https://hg.mozilla.org/mozilla-central/json-pushes?version=2&full=1&startID={}&endID={}'.format(push_id - 1, push_id + 7)) as r:  # noqa
        data = await r.json()

    for pushid, pushdata in data['pushes'].items():
        pushid = int(pushid)

        push_to_changeset_cache[pushid] = pushdata['changesets'][-1]['node']

        for changeset in pushdata['changesets']:
            is_merge = any(text in changeset['desc'] for text in ['r=merge', 'a=merge'])

            if not is_merge:
                changeset_cache[changeset['node'][:12]] = {
                  'files': changeset['files'],
                  'push': pushid,
                }
            else:
                changeset_cache[changeset['node'][:12]] = {
                  'merge': True,
                  'push': pushid,
                }


async def get_pushes_changesets(push_id, push_id_end):
    if push_id not in push_to_changeset_cache:
        await get_pushes(push_id)

    for i in range(push_id, push_id_end):
        if i not in push_to_changeset_cache:
            continue

        yield push_to_changeset_cache[i]


async def get_changeset_data(changeset):
    if changeset[:12] not in changeset_cache:
        async with aiohttp.request('GET', 'https://hg.mozilla.org/mozilla-central/json-rev/{}'.format(changeset)) as r:
            rev = await r.json()

        push_id = int(rev['pushid'])

        await get_pushes(push_id)

    return changeset_cache[changeset[:12]]


async def get_coverage_build(changeset):
    '''
    This function returns the first successful coverage build after a given
    changeset.
    '''
    changeset_data = await get_changeset_data(changeset)
    push_id = changeset_data['push']

    # Find the first coverage build after the changeset.
    async for build_changeset in get_pushes_changesets(push_id, push_id + 8):
        try:
            overall = await coverage_service.get_coverage(build_changeset)
            return (changeset_data, build_changeset, overall)
        except CoverageException:
            pass

    assert False, 'Couldn\'t find a build after the changeset'


async def get_latest_build_info():
    latest_rev, previous_rev = await coverage_service.get_latest_build()
    latest_pushid = (await get_changeset_data(latest_rev))['push']
    return {
      'latest_pushid': latest_pushid,
      'latest_rev': latest_rev,
      'previous_rev': previous_rev,
    }


COVERAGE_EXTENSIONS = [
    # C
    'c', 'h',
    # C++
    'cpp', 'cc', 'cxx', 'hh', 'hpp', 'hxx',
    # JavaScript
    'js', 'jsm', 'xul', 'xml', 'html', 'xhtml',
]


def coverage_supported(path):
    return any([path.endswith('.' + ext) for ext in COVERAGE_EXTENSIONS])
