# -*- coding: utf-8 -*-
import json
import os

import responses

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def test_is_coverage_task(code_coverage):
    cov_task = {
        'task': {
            'metadata': {
                'name': 'build-linux64-ccov'
            }
        }
    }
    assert code_coverage.is_coverage_task(cov_task)

    cov_task = {
        'task': {
            'metadata': {
                'name': 'build-linux64-ccov/opt'
            }
        }
    }
    assert code_coverage.is_coverage_task(cov_task)

    cov_task = {
        'task': {
            'metadata': {
                'name': 'build-win64-ccov/debug'
            }
        }
    }
    assert code_coverage.is_coverage_task(cov_task)

    nocov_task = {
        'task': {
            'metadata': {
                'name': 'test-linux64-ccov/opt-mochitest-1'
            }
        }
    }
    assert not code_coverage.is_coverage_task(nocov_task)

    nocov_task = {
        'task': {
            'metadata': {
                'name': 'test-linux64/opt-mochitest-1'
            }
        }
    }
    assert not code_coverage.is_coverage_task(nocov_task)


def test_get_build_task_in_group(code_coverage):
    code_coverage.triggered_groups.add('already-triggered-group')

    assert code_coverage.get_build_task_in_group('already-triggered-group') is None


def test_parse(code_coverage):
    code_coverage.triggered_groups.add('already-triggered-group')

    assert code_coverage.parse({
        'taskGroupId': 'already-triggered-group'
    }) is None


@responses.activate
def test_wrong_branch(code_coverage):
    with open(os.path.join(FIXTURES_DIR, 'bNq-VIT-Q12o6nXcaUmYNQ.json')) as f:
        responses.add(responses.GET, 'https://queue.taskcluster.net/v1/task-group/bNq-VIT-Q12o6nXcaUmYNQ/list?limit=200', json=json.load(f), status=200, match_querystring=True)  # noqa

    assert code_coverage.parse({
        'taskGroupId': 'bNq-VIT-Q12o6nXcaUmYNQ'
    }) is None


@responses.activate
def test_success(code_coverage):
    with open(os.path.join(FIXTURES_DIR, 'RS0UwZahQ_qAcdZzEb_Y9g.json')) as f:
        responses.add(responses.GET, 'https://queue.taskcluster.net/v1/task-group/RS0UwZahQ_qAcdZzEb_Y9g/list?limit=200', json=json.load(f), status=200, match_querystring=True)  # noqa

    assert code_coverage.parse({
        'taskGroupId': 'RS0UwZahQ_qAcdZzEb_Y9g'
    }) == [{'REPOSITORY': 'https://hg.mozilla.org/mozilla-central', 'REVISION': 'ec3dd3ee2ae4b3a63529a912816a110e925eb2d0'}]


@responses.activate
def test_success_windows(code_coverage):
    with open(os.path.join(FIXTURES_DIR, 'MibGDsa4Q7uFNzDf7EV6nw.json')) as f:
        responses.add(responses.GET, 'https://queue.taskcluster.net/v1/task-group/MibGDsa4Q7uFNzDf7EV6nw/list?limit=200', json=json.load(f), status=200, match_querystring=True)  # noqa

    assert code_coverage.parse({
        'taskGroupId': 'MibGDsa4Q7uFNzDf7EV6nw'
    }) == [{'REPOSITORY': 'https://hg.mozilla.org/mozilla-central', 'REVISION': '63519bfd42ee379f597c0357af2e712ec3cd9f50'}]


@responses.activate
def test_success_try(code_coverage):
    with open(os.path.join(FIXTURES_DIR, 'FG3goVnCQfif8ZEOaM_4IA.json')) as f:
        responses.add(responses.GET, 'https://queue.taskcluster.net/v1/task-group/FG3goVnCQfif8ZEOaM_4IA/list?limit=200', json=json.load(f), status=200, match_querystring=True)  # noqa

    assert code_coverage.parse({
        'taskGroupId': 'FG3goVnCQfif8ZEOaM_4IA'
    }) == [{'REPOSITORY': 'https://hg.mozilla.org/try', 'REVISION': '066cb18ba95a7efe144e729713c429e422d9f95b'}]
