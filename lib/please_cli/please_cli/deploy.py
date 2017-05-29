# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import

import io
import json
import os
import shutil
import tempfile

import awscli
import click
import click_spinner
import push.image
import push.registry
import taskcluster.exceptions

import cli_common.log
import cli_common.taskcluster
import cli_common.click
import please_cli.config
import please_cli.build
import please_cli.utils


log = cli_common.log.get_logger(__name__)


@click.command()
@cli_common.click.taskcluster_options
@click.argument(
    'app',
    required=True,
    type=click.Choice(please_cli.config.APPS),
    )
@click.option(
    '--s3-bucket',
    required=True,
    type=str,
    )
@click.option(
    '--extra-attribute',
    multiple=True,
    )
@click.option(
    '--csp',
    required=False,
    multiple=True,
    default=None,
    )
@click.option(
    '--env',
    required=False,
    multiple=True,
    default=None,
    )
@click.option(
    '--nix-build',
    required=True,
    default=please_cli.config.NIX_BIN_DIR + 'nix-build',
    help='`nix-build` command',
    )
@click.option(
    '--nix-push',
    required=True,
    default=please_cli.config.NIX_BIN_DIR + 'nix-push',
    help='`nix-push` command',
    )
@click.option(
    '--interactive/--no-interactive',
    default=True,
    )
@click.pass_context
def cmd_S3(ctx,
           app,
           s3_bucket,
           extra_attribute,
           csp,
           env,
           nix_build,
           nix_push,
           taskcluster_secret,
           taskcluster_client_id,
           taskcluster_access_token,
           interactive,
           ):
    '''
    '''

    secrets = cli_common.taskcluster.get_secrets()

    AWS_ACCESS_KEY_ID = secrets['DEPLOY_S3_ACCESS_KEY_ID']
    AWS_SECRET_ACCESS_KEY = secrets['DEPLOY_S3_SECRET_ACCESS_KEY']

    # 1. build app (TODO: but only pull from cache)
    ctx.invoke(please_cli.build.cmd,
               app=app,
               extra_attribute=extra_attribute,
               nix_build=nix_build,
               nix_push=nix_push,
               taskcluster_secret=taskcluster_secret,
               taskcluster_client_id=taskcluster_client_id,
               taskcluster_access_token=taskcluster_access_token,
               interactive=interactive,
               )
    app_path = os.path.realpath(os.path.join(
        please_cli.config.TMP_DIR,
        'result-build-{}-1'.format(app),
    ))

    # 2. create temporary copy of app
    click.echo(' => Copying build artifacs to temporary location ... ', nl=False)
    with click_spinner.spinner():
        if not os.path.exists(please_cli.config.TMP_DIR):
            os.makedirs(please_cli.config.TMP_DIR)
        tmp_dir = tempfile.mkdtemp(
            prefix='copy-of-result-{}-'.format(app),
            dir=please_cli.config.TMP_DIR,
        )
        shutil.rmtree(tmp_dir)
        shutil.copytree(app_path, tmp_dir, copy_function=shutil.copy)
    please_cli.utils.check_result(
        0,
        'Copied build artifacs to temporary location: {}'.format(tmp_dir),
        ask_for_details=interactive,
    )

    # 3. apply csp and flags to index.html

    click.echo(' => Applying CSP and environment flags to index.html ... ', nl=False)
    with click_spinner.spinner():
        index_html_file = os.path.join(tmp_dir, 'index.html')
        with io.open(index_html_file, 'r', encoding='utf-8') as f:
            index_html = f.read()

        if csp:
            index_html = index_html.replace(
                'font-src \'self\';',
                'font-src \'self\'; connect-src {};'.format(' '.join(csp)),
            )
        if env:
            index_html = index_html.replace(
                '<body',
                '<body ' + (' '.join(['data-' + i for i in env])),
            )

        os.chmod(index_html_file, 755)
        with io.open(index_html_file, 'w', encoding='utf-8') as f:
            f.write(index_html)
    please_cli.utils.check_result(
        0,
        'Applied CSP and environment flags to index.html',
        ask_for_details=interactive,
    )

    # 4. sync to S3
    click.echo(' => Syncing to S3  ... ', nl=False)
    with click_spinner.spinner():
        os.environ['AWS_ACCESS_KEY_ID'] = AWS_ACCESS_KEY_ID
        os.environ['AWS_SECRET_ACCESS_KEY'] = AWS_SECRET_ACCESS_KEY
        aws = awscli.clidriver.create_clidriver().main
        aws([
            's3',
            'sync',
            '--quiet',
            '--delete',
            '--acl', 'public-read',
            tmp_dir,
            's3://' + s3_bucket,
        ])
    please_cli.utils.check_result(
        0,
        'Synced {} to S3 bucket {}'.format(app, s3_bucket),
        ask_for_details=interactive,
    )


@click.command()
@cli_common.click.taskcluster_options
@click.argument(
    'app',
    required=True,
    type=click.Choice(please_cli.config.APPS),
    )
@click.option(
    '--heroku-app',
    required=True,
    )
@click.option(
    '--extra-attribute',
    multiple=True,
    )
@click.option(
    '--nix-build',
    required=True,
    default=please_cli.config.NIX_BIN_DIR + 'nix-build',
    help='`nix-build` command',
    )
@click.option(
    '--nix-push',
    required=True,
    default=please_cli.config.NIX_BIN_DIR + 'nix-push',
    help='`nix-push` command',
    )
@click.option(
    '--interactive/--no-interactive',
    default=True,
    )
@click.pass_context
def cmd_HEROKU(ctx,
               app,
               heroku_app,
               extra_attribute,
               nix_build,
               nix_push,
               taskcluster_secret,
               taskcluster_client_id,
               taskcluster_access_token,
               interactive,
               ):

    secrets = cli_common.taskcluster.get_secrets()

    HEROKU_USERNAME = secrets['HEROKU_USERNAME']
    HEROKU_PASSWORD = secrets['HEROKU_PASSWORD']

    ctx.invoke(please_cli.build.cmd,
               app=app,
               extra_attribute=extra_attribute,
               nix_build=nix_build,
               nix_push=nix_push,
               taskcluster_secret=taskcluster_secret,
               taskcluster_client_id=taskcluster_client_id,
               taskcluster_access_token=taskcluster_access_token,
               interactive=interactive,
               )

    app_path = os.path.realpath(os.path.join(
        please_cli.config.TMP_DIR,
        'result-build-{}-1'.format(app),
    ))

    click.echo(' => Pushing {} to heroku ... '.format(app), nl=False)
    with click_spinner.spinner():
        push.registry.push(
            push.image.spec(app_path),
            "https://registry.heroku.com",
            HEROKU_USERNAME,
            HEROKU_PASSWORD,
            heroku_app + "/web",
            "latest",
        )
    please_cli.utils.check_result(
        0,
        'Pushed {} to heroku.'.format(app),
        ask_for_details=interactive,
    )


@click.command()
@cli_common.click.taskcluster_options
@click.argument(
    'app',
    required=True,
    type=click.Choice(please_cli.config.APPS),
    )
@click.option(
    '--extra-attribute',
    multiple=True,
    )
@click.option(
    '--hook-id',
    required=True,
    )
@click.option(
    '--hook-group-id',
    required=True,
    default='project-releng'
    )
@click.option(
    '--nix-build',
    required=True,
    default=please_cli.config.NIX_BIN_DIR + 'nix-build',
    help='`nix-build` command',
    )
@click.option(
    '--nix-push',
    required=True,
    default=please_cli.config.NIX_BIN_DIR + 'nix-push',
    help='`nix-push` command',
    )
@click.option(
    '--docker-repo',
    required=True,
    default=please_cli.config.DOCKER_REPO,
    help='Docker repository.',
    )
@click.option(
    '--interactive/--no-interactive',
    default=True,
    )
@click.pass_context
def cmd_TASKCLUSTER_HOOK(ctx,
                         app,
                         extra_attribute,
                         hook_id,
                         hook_group_id,
                         nix_build,
                         nix_push,
                         taskcluster_secret,
                         taskcluster_client_id,
                         taskcluster_access_token,
                         docker_repo,
                         interactive,
                         ):

    secrets = cli_common.taskcluster.get_secrets(
        taskcluster_secret,
        [
            'DOCKER_USERNAME',
            'DOCKER_PASSWORD',
        ],
        taskcluster_client_id,
        taskcluster_access_token,
    )

    docker_username = secrets['DOCKER_USERNAME']
    docker_password = secrets['DOCKER_PASSWORD']

    hooks_tool = cli_common.taskcluster.get_service('hooks')

    click.echo(' => Hook `{}/{}` exists? ... '.format(hook_group_id, hook_id), nl=False)
    with click_spinner.spinner():
        hooks = [i['hookId'] for i in hooks_tool.listHooks(hook_group_id).get('hooks', [])]

    hook_exists = False
    result = 1
    output = 'Hook {} not exists in {}'.format(hook_id, str(hooks))
    if hook_id in hooks:
        hook_exists = True
        result = 0
        output = 'Hook {} exists in {}'.format(hook_id, str(hooks))

    please_cli.utils.check_result(
        result,
        output,
        success_message='EXISTS',
        error_message='NOT EXISTS',
        ask_for_details=interactive,
        raise_exception=False,
    )

    ctx.invoke(please_cli.build.cmd,
               app=app,
               extra_attribute=extra_attribute,
               nix_build=nix_build,
               nix_push=nix_push,
               taskcluster_secret=taskcluster_secret,
               taskcluster_client_id=taskcluster_client_id,
               taskcluster_access_token=taskcluster_access_token,
               interactive=interactive,
               )
    app_path = os.path.realpath(os.path.join(
        please_cli.config.TMP_DIR,
        'result-build-{}-1'.format(app),
    ))

    with open(app_path) as f:
        hook = json.load(f)

    image = hook.get('task', {}).get('payload', {}).get('image', '')
    if image.startswith('/nix/store'):

        image_tag = '-'.join(reversed(image[11:-7].split('-', 1)))
        click.echo(' => Uploading docker image `{}:{}` ... '.format(docker_repo, image_tag), nl=False)
        with click_spinner.spinner():
            push.registry.push(
                push.image.spec(image),
                please_cli.config.DOCKER_REGISTRY,
                docker_username,
                docker_password,
                docker_repo,
                image_tag,
            )

        please_cli.utils.check_result(
            0,
            'Pushed {}:{} docker image.'.format(docker_repo, image_tag),
            ask_for_details=interactive,
        )

        hook['task']['payload']['image'] = '{}:{}'.format(docker_repo, image_tag)

    if hook_exists:
        click.echo(' => Updating hook `{}/{}` ... '.format(hook_group_id, hook_id), nl=False)
        with click_spinner.spinner():
            try:
                hooks_tool.updateHook(hook_group_id, hook_id, hook)
                result = 0
                output = ''
            except taskcluster.exceptions.TaskclusterRestFailure as e:
                log.exception(e)
                output = str(e)
                result = 1
    else:
        click.echo(' => Creating hook `{}/{}` ... '.format(hook_group_id, hook_id), nl=False)
        with click_spinner.spinner():
            try:
                hooks_tool.createHook(hook_group_id, hook_id, hook)
                result = 0
                output = ''
            except taskcluster.exceptions.TaskclusterRestFailure as e:
                log.exception(e)
                output = str(e)
                result = 1

    please_cli.utils.check_result(
        result,
        output,
        ask_for_details=interactive,
    )
