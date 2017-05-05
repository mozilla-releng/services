import gzip
import time
import requests

from cli_common.log import get_logger


logger = get_logger(__name__)


def coveralls(data):
    r = requests.post('https://coveralls.io/api/v1/jobs', files={
        'json_file': ('json_file', gzip.compress(data), 'gzip/json')
    })

    try:
        result = r.json()
        logger.info('Uploaded build to Coveralls: %s' % r.text)
    except ValueError:
        raise Exception('Failure to submit data. Response [%s]: %s' % (r.status_code, r.text))  # NOQA

    return result['url'] + '.json'


def coveralls_wait(job_url):
    while True:
        r = requests.get(job_url)
        if r.json()['covered_percent']:
            break
        time.sleep(60)


def codecov(data, commit_sha, flags, token):
    r = requests.post('https://codecov.io/upload/v4?commit=%s&flags=%s&token=%s&service=custom' % (commit_sha, ','.join(flags), token), headers={  # NOQA
        'Accept': 'text/plain',
    })

    if r.status_code != requests.codes.ok:
        raise Exception('Failure to submit data. Response [%s]: %s' % (r.status_code, r.text))  # NOQA

    lines = r.text.splitlines()

    logger.info('Codecov report URL: %s' % lines[0])

    data += b'\n<<<<<< EOF'

    r = requests.put(lines[1], data=data, headers={
        'Content-Type': 'text/plain',
        'x-amz-acl': 'public-read',
        'x-amz-storage-class': 'REDUCED_REDUNDANCY',
    })

    if r.status_code != requests.codes.ok:
        raise Exception('Failure to upload data to S3. Response [%s]: %s' % (r.status_code, r.text))  # NOQA
