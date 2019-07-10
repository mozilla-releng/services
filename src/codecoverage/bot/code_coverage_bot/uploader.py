# -*- coding: utf-8 -*-
import requests
import structlog
import zstandard as zstd

from code_coverage_bot.secrets import secrets
from code_coverage_bot.utils import retry
from code_coverage_tools.gcp import get_bucket

logger = structlog.get_logger(__name__)
GCP_COVDIR_PATH = '{repository}/{revision}.json.zstd'


def codecov(data, commit_sha, flags=None):
    logger.info('Upload report to Codecov')

    params = {
        'commit': commit_sha,
        'token': secrets[secrets.CODECOV_TOKEN],
        'service': 'custom',
    }

    if flags is not None:
        params['flags'] = ','.join(flags)

    r = requests.post('https://codecov.io/upload/v4', params=params, headers={
        'Accept': 'text/plain',
    })

    if r.status_code != requests.codes.ok:
        raise Exception('Failure to submit data. Response [%s]: %s' % (r.status_code, r.text))

    lines = r.text.splitlines()

    logger.info('Uploaded report to Codecov', report=lines[0])

    data += b'\n<<<<<< EOF'

    r = requests.put(lines[1], data=data, headers={
        'Content-Type': 'text/plain',
        'x-amz-acl': 'public-read',
        'x-amz-storage-class': 'REDUCED_REDUNDANCY',
    })

    if r.status_code != requests.codes.ok:
        raise Exception('Failure to upload data to S3. Response [%s]: %s' % (r.status_code, r.text))


def get_latest_codecov():
    def get_latest_codecov_int():
        r = requests.get('https://codecov.io/api/gh/{}?access_token={}'.format(secrets[secrets.CODECOV_REPO], secrets[secrets.CODECOV_ACCESS_TOKEN]))
        r.raise_for_status()
        return r.json()['commit']['commitid']

    return retry(get_latest_codecov_int)


def get_codecov(commit):
    r = requests.get('https://codecov.io/api/gh/{}/commit/{}?access_token={}'.format(secrets[secrets.CODECOV_REPO], commit, secrets[secrets.CODECOV_ACCESS_TOKEN]))  # noqa
    r.raise_for_status()
    return r.json()


def codecov_wait(commit):
    class TotalsNoneError(Exception):
        pass

    def check_codecov_job():
        data = get_codecov(commit)
        totals = data['commit']['totals']
        if totals is None:
            raise TotalsNoneError()
        return True

    try:
        return retry(check_codecov_job, retries=30)
    except TotalsNoneError:
        return False


def gcp(repository, revision, data):
    '''
    Upload a grcov raw report on Google Cloud Storage
    * Compress with zstandard
    * Upload on bucket using revision in name
    * Trigger ingestion on channel's backend
    '''
    assert isinstance(data, bytes)
    bucket = get_bucket(secrets[secrets.GOOGLE_CLOUD_STORAGE])

    # Compress report
    compressor = zstd.ZstdCompressor()
    archive = compressor.compress(data)

    # Upload archive
    path = GCP_COVDIR_PATH.format(repository=repository, revision=revision)
    blob = bucket.blob(path)
    blob.upload_from_string(archive)

    # Update headers
    blob.content_type = 'application/json'
    blob.content_encoding = 'zstd'
    blob.patch()

    logger.info('Uploaded {} on {}'.format(path, bucket))

    # Trigger ingestion on backend
    retry(lambda: gcp_ingest(repository, revision), retries=5)

    return blob


def gcp_covdir_exists(repository, revision):
    '''
    Check if a covdir report exists on the Google Cloud Storage bucket
    '''
    bucket = get_bucket(secrets[secrets.GOOGLE_CLOUD_STORAGE])
    path = GCP_COVDIR_PATH.format(repository=repository, revision=revision)
    blob = bucket.blob(path)
    return blob.exists()


def gcp_ingest(repository, revision):
    '''
    The GCP report ingestion is triggered remotely on a backend
    by making a simple HTTP request on the /v2/path endpoint
    By specifying the exact new revision processed, the backend
    will download automatically the new report.
    '''
    params = {
        'repository': repository,
        'changeset': revision,
    }
    backend_host = secrets[secrets.BACKEND_HOST]
    resp = requests.get('{}/v2/path'.format(backend_host), params=params)
    resp.raise_for_status()
    logger.info('Ingested report on backend', host=backend_host, repository=repository, revision=revision)
    return resp
