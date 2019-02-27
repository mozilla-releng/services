# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import json

import click
import click_spinner
import requests
import slugid

import cli_common.taskcluster
import common_naming
import please_cli.config
import please_cli.utils

PROJECTS = list(set(please_cli.config.PROJECTS) - set(please_cli.config.DEV_PROJECTS))


def get_build_task(index,
                   project,
                   task_group_id,
                   parent_task,
                   github_commit,
                   owner,
                   channel,
                   taskcluster_secret,
                   cache_bucket=None,
                   cache_region=None,
                   project_github_commit=None,
                   ):

    if project_github_commit is None:
        project_github_commit = github_commit
    command = [
        './please', '-vv', 'tools', 'build', project.name,
        '--taskcluster-secret=' + taskcluster_secret,
        '--no-interactive',
        '--task-group-id', task_group_id,
        '--github-commit', project_github_commit,
    ]

    nix_path_attributes = [project.name]
    deployments = please_cli.config.PROJECTS_CONFIG[project.name].get('deploys', [])
    for deployment in deployments:
        for channel in deployment['options']:
            if 'nix_path_attribute' in deployment['options'][channel]:
                nix_path_attributes.append('{}.{}'.format(
                    project.name,
                    deployment['options'][channel]['nix_path_attribute'],
                ))
    nix_path_attributes = list(set(nix_path_attributes))

    for nix_path_attribute in nix_path_attributes:
        command.append('--nix-path-attribute={}'.format(nix_path_attribute))

    if cache_bucket and cache_region:
        command += [
            '--cache-bucket={}'.format(cache_bucket),
            '--cache-region={}'.format(cache_region),
        ]
    return get_task(
        task_group_id,
        [parent_task],
        github_commit,
        channel,
        taskcluster_secret,
        ' '.join(command),
        {
            'name': '1.{index:02}. Building {project}'.format(
                index=index + 1,
                project=project.name,
            ),
            'description': '',
            'owner': owner,
            'source': 'https://github.com/mozilla/release-services/tree/' + channel,

        },
        max_run_time_in_hours=5,
    )


def get_deploy_task(index,
                    project,
                    project_requires,
                    deploy_target,
                    deploy_options,
                    task_group_id,
                    parent_task,
                    github_commit,
                    owner,
                    channel,
                    taskcluster_secret,
                    nix_hash,
                    project_github_commit=None,
                    ):

    scopes = []

    if project_github_commit is None:
        project_github_commit = github_commit

    nix_path_attribute = deploy_options.get('nix_path_attribute')
    if nix_path_attribute:
        nix_path_attribute = '{}.{}'.format(project.name, nix_path_attribute)
    else:
        nix_path_attribute = project.name

    if deploy_target == 'S3':
        subfolder = []
        if 'subfolder' in deploy_options:
            subfolder = [deploy_options['subfolder']]
        project_csp = []
        for url in deploy_options.get('csp', []):
            project_csp.append('--csp="{}"'.format(url))
        for require in project_requires:
            require_config = please_cli.config.PROJECTS_CONFIG.get(require, {})

            require_urls = [
                i.get('options', {}).get(channel, {}).get('url')
                for i in require_config.get('deploys', [])
            ]
            require_urls = filter(lambda x: x is not None, require_urls)
            require_urls = map(lambda x: '--csp="{}"'.format(x), require_urls)

            project_csp += require_urls

        project_envs = []
        project_envs.append('--env="release-version: {}"'.format(please_cli.config.VERSION))
        project_envs.append('--env="release-channel: {}"'.format(channel))
        for env_name, env_value in deploy_options.get('envs', {}).items():
            project_envs.append('--env="{}: {}"'.format(env_name, env_value))
        for require in project_requires:
            require_config = please_cli.config.PROJECTS_CONFIG.get(require, {})

            require_urls = [
                (
                    i.get('options', {}).get(channel, {}).get('url'),
                    i.get('options', {}).get(channel, {}).get('name-suffix', ''),
                )
                for i in require_config.get('deploys', [])
            ]
            require_urls = filter(lambda x: x[0] is not None, require_urls)
            normalized_require = please_cli.utils.normalize_name(require, normalizer='-')
            require_urls = map(lambda x: '--env="{}{}-url: {}"'.format(normalized_require, x[1], x[0]), require_urls)

            project_envs += require_urls

        project_name = '{}{} to AWS S3 ({})'.format(
            project.name,
            ' ({})'.format(nix_path_attribute),
            deploy_options['s3_bucket'],
        )
        command = [
            './please', '-vv',
            'tools', 'deploy:S3',
            project.name,
            '--s3-bucket=' + deploy_options['s3_bucket'],
            '--taskcluster-secret=' + taskcluster_secret,
            '--nix-path-attribute=' + nix_path_attribute,
            '--no-interactive',
        ] + subfolder + project_csp + project_envs

    elif deploy_target == 'HEROKU':
        project_name = '{}{} to HEROKU ({}/{})'.format(
            project.name,
            ' ({})'.format(nix_path_attribute),
            deploy_options['heroku_app'],
            deploy_options['heroku_dyno_type'],
        )
        command = [
            './please', '-vv',
            'tools', 'deploy:HEROKU',
            project.name,
            '--heroku-app=' + deploy_options['heroku_app'],
            '--heroku-dyno-type=' + deploy_options['heroku_dyno_type'],
        ]

        heroku_command = deploy_options.get('heroku_command')
        if heroku_command:
            command.append('--heroku-command="{}"'.format(heroku_command))

        command += [
            '--taskcluster-secret=' + taskcluster_secret,
            '--nix-path-attribute=' + nix_path_attribute,
            '--no-interactive',
        ]

    elif deploy_target == 'DOCKERHUB':
        try:
            docker_registry = deploy_options['docker_registry']
            docker_repo = deploy_options['docker_repo']
            docker_stable_tag = deploy_options['docker_stable_tag']
        except KeyError:
            raise click.ClickException(
                'Missing `docker_registry` or `docker_repo` or `docker_stable_tag` in deploy options')

        project_name = (
            f'{project.name} ({nix_path_attribute}) to DOCKERHUB '
            f'({docker_registry}/{docker_repo}:{project.name}-{nix_path_attribute}-{channel})'
        )
        command = [
            './please', '-vv', 'tools', 'deploy:DOCKERHUB', project.name,
            f'--taskcluster-secret={taskcluster_secret}',
            f'--nix-path-attribute={nix_path_attribute}',
            f'--docker-repo={docker_repo}',
            f'--docker-registry={docker_registry}',
            f'--channel={channel}',
            f'--docker-stable-tag={docker_stable_tag}',
            '--no-interactive',
        ]

    elif deploy_target == 'TASKCLUSTER_HOOK':
        try:
            docker_registry = deploy_options['docker_registry']
            docker_repo = deploy_options['docker_repo']
            docker_stable_tag = deploy_options.get('docker_stable_tag')
        except KeyError:
            raise click.ClickException('Missing `docker_registry` or `docker_repo` in deploy options')
        hook_group_id = 'project-releng'
        name_suffix = deploy_options.get('name-suffix', '')
        hook_id = f'services-{channel}-{project.name}{name_suffix}'
        project_name = f'{project.name} ({nix_path_attribute}) to TASKCLUSTER HOOK ({hook_group_id}/{hook_id})'
        command = [
            './please', '-vv',
            'tools', 'deploy:TASKCLUSTER_HOOK',
            project.name,
            f'--docker-registry={docker_registry}',
            f'--docker-repo={docker_repo}',
            f'--hook-group-id={hook_group_id}',
            f'--hook-id={hook_id}',
            f'--taskcluster-secret={taskcluster_secret}',
            f'--nix-path-attribute={nix_path_attribute}',
            '--no-interactive',
        ]
        if docker_stable_tag is not None:
            command.append(f'--docker-stable-tag={docker_stable_tag}')
        scopes += [
          f'assume:hook-id:project-releng/services-{channel}-*',
          f'hooks:modify-hook:project-releng/services-{channel}-*',
        ]

    else:
        raise click.ClickException(f'Unknown deployment target `{deploy_target}` for project `{project.name}`')

    # store revision and nix hash into taskcluster index service
    routes = [
        f'index.project.releng.services.deployment.{channel}.{project.taskcluster_route_name}'
    ]
    extra = dict(
        index=dict(
            data=dict(
                revision=project_github_commit,
                nix_hash=nix_hash,
            )
        )
    )

    return get_task(
        task_group_id,
        [parent_task],
        github_commit,
        channel,
        taskcluster_secret,
        ' '.join(command),
        {
            'name': '3.{index:02}. Deploying {project_name}'.format(
                index=index + 1,
                project_name=project_name,
            ),
            'description': '',
            'owner': owner,
            'source': 'https://github.com/mozilla/release-services/tree/' + channel,

        },
        scopes=scopes,
        routes=routes,
        extra=extra,
    )


def get_task(task_group_id,
             dependencies,
             github_commit,
             channel,
             taskcluster_secret,
             command,
             metadata,
             scopes=[],
             deadline=dict(hours=5),
             max_run_time_in_hours=1,
             routes=[],
             extra=dict(),
             ):
    priority = 'high'
    if channel == 'production':
        priority = 'very-high'
    now = datetime.datetime.utcnow()
    command = (' && '.join([
      # debug
      'ls -la /etc/services',
      'env',
      # cleanup
      'rm -rf /home/app/.cache/nix',
      # setup
      'source /etc/nix/profile.sh',
      'mkdir -p /tmp/app',
      'cd /tmp/app',
      'wget --retry-connrefused --waitretry=1 --read-timeout=20 --timeout=15 -t 5 https://github.com/mozilla/release-services/archive/{github_commit}.tar.gz',
      'tar zxf {github_commit}.tar.gz',
      'cd release-services-{github_commit}',
      command
    ])).format(github_commit=github_commit)
    return {
        'provisionerId': 'aws-provisioner-v1',
        'workerType': 'releng-svc',
        'schedulerId': 'taskcluster-github',
        'taskGroupId': task_group_id,
        'dependencies': dependencies,
        'created': now,
        'deadline': now + datetime.timedelta(**deadline),
        'scopes': [
          'secrets:get:' + taskcluster_secret,
          'docker-worker:capability:privileged',
        ] + scopes,
        'routes': routes,
        'priority': priority,
        'payload': {
            'maxRunTime': 60 * 60 * max_run_time_in_hours,
            'image': '{}:{}'.format(please_cli.config.DOCKER_BASE_REPO,
                                    please_cli.config.DOCKER_BASE_TAG),
            'features': {
                'taskclusterProxy': True,
            },
            'capabilities': {
                'privileged': True,
            },
            'env': {
                'GITHUB_COMMIT': github_commit,
                'TASK_GROUP_ID': task_group_id,
            },
            'command': [
                '/bin/bash',
                '-c',
                command,
            ],
        },
        'metadata': metadata,
        'extra': extra,
    }


@click.command()
@click.option(
    '--github-commit',
    envvar='GITHUB_HEAD_SHA',
    required=True,
    )
@click.option(
    '--channel',
    type=click.Choice(please_cli.config.CHANNELS),
    envvar='GITHUB_BRANCH',
    required=True,
    )
@click.option(
    '--owner',
    envvar='GITHUB_HEAD_USER_EMAIL',
    required=True,
    )
@click.option(
    '--pull-request',
    envvar='GITHUB_PULL_REQUEST',
    default=None,
    required=False,
    )
@click.option(
    '--task-id',
    envvar='TASK_ID',
    required=True,
    )
@click.option(
    '--cache-url',
    'cache_urls',
    multiple=True,
    default=please_cli.config.CACHE_URLS,
    help='Locations of build artifacts.',
    )
@click.option(
    '--nix-instantiate',
    required=True,
    default=please_cli.config.NIX_BIN_DIR + 'nix-instantiate',
    help='`nix-instantiate` command',
    )
@click.option(
    '--taskcluster-client-id',
    default=None,
    required=False,
    )
@click.option(
    '--taskcluster-access-token',
    default=None,
    required=False,
    )
@click.option(
    '--dry-run',
    is_flag=True,
    )
@click.pass_context
def cmd(ctx,
        github_commit,
        channel,
        owner,
        pull_request,
        task_id,
        cache_urls,
        nix_instantiate,
        taskcluster_client_id,
        taskcluster_access_token,
        dry_run,
        ):
    '''A tool to be ran on each commit.
    '''

    taskcluster_secret = 'repo:github.com/mozilla-releng/services:branch:' + channel
    if pull_request is not None:
        taskcluster_secret = 'repo:github.com/mozilla-releng/services:pull-request'

    taskcluster_queue = cli_common.taskcluster.get_service('queue')
    taskcluster_notify = cli_common.taskcluster.get_service('notify')

    click.echo(' => Retriving taskGroupId ... ', nl=False)
    with click_spinner.spinner():
        task = taskcluster_queue.task(task_id)
        if 'taskGroupId' not in task:
            please_cli.utils.check_result(1, 'taskGroupId does not exists in task: {}'.format(json.dumps(task)))
        task_group_id = task['taskGroupId']
        please_cli.utils.check_result(0, '')
        click.echo('    taskGroupId: ' + task_group_id)

    if channel in please_cli.config.DEPLOY_CHANNELS:
        taskcluster_notify.irc(dict(channel='#release-services',
                                    message=f'New deployment on {channel} is about to start: https://tools.taskcluster.net/groups/{task_group_id}'))

    message = ('release-services team is about to release a new version of mozilla/release-services '
               '(*.mozilla-releng.net, *.moz.tools). Any alerts coming up soon will be best directed '
               'to #release-services IRC channel. Automated message (such as this) will be send '
               'once deployment is done. Thank you.')

    '''This message will only be sent when channel is production.
    '''
    if channel == 'production':
        for msgChannel in ['#ci', '#moc']:
            taskcluster_notify.irc(dict(channel=msgChannel, message=message))

    click.echo(' => Checking cache which project needs to be rebuilt')
    build_projects = []
    project_hashes = dict()
    for project in sorted(PROJECTS):
        click.echo('     => ' + project)
        project_exists_in_cache, project_hash = ctx.invoke(
            please_cli.check_cache.cmd,
            project=project,
            cache_urls=cache_urls,
            nix_instantiate=nix_instantiate,
            channel=channel,
            indent=8,
            interactive=False,
        )
        project_hashes[project] = project_hash
        if not project_exists_in_cache:
            build_projects.append(project)

    click.echo(' => Checking github for project revisions')

    project_revisions = {p: github_commit for p in PROJECTS}
    project_url_cache = dict()
    for project in sorted(PROJECTS):
        # TODO: how should we handle outside projects?
        #       skip project defined outside for now
        if project in please_cli.config.OUTSIDE_PROJECTS:
            continue

        click.echo('     => ' + project)

        project_path = '/'.join(project.split('/')[:-1])
        project_path_end = project.split('/')[-1]

        url = f'https://api.github.com/repos/mozilla/release-services/contents/src/{project_path}?ref={github_commit}'

        if url in project_url_cache:
            response = project_url_cache[url]
        else:
            r = requests.get(url)
            r.raise_for_status()
            response = r.json()
            project_url_cache[url] = response

        for item in response:
            if project_path_end == item['name']:
                project_revisions[project] = item['sha']
                break

    click.echo(' => Gathering deployed projects revisions')

    deployed_projects = {}
    for project in sorted(PROJECTS):
        # TODO: how should we handle outside projects?
        #       skip project defined outside for now
        if project in please_cli.config.OUTSIDE_PROJECTS:
            continue

        click.echo('     => ' + project)

        project = common_naming.Project(project)
        url = f'https://index.taskcluster.net/v1/task/project.releng.services.deployment.staging.{project.taskcluster_route_name}'

        r = requests.get(url)
        r.raise_for_status()
        response = r.json()

        deployed_projects[project.name] = response['data']

    projects_to_deploy = []
    if channel in please_cli.config.DEPLOY_CHANNELS:
        click.echo(' => Checking which project needs to be redeployed')

        for project_name in sorted(PROJECTS):
            if project_name in deployed_projects and \
               project_name in project_hashes and \
               deployed_projects[project_name]['nix_hash'] == project_hashes[project_name]:
                continue

            # update hook for each project
            if please_cli.config.PROJECTS_CONFIG[project_name]['update'] is True:

                if channel == 'production':
                    update_hook_nix_path_atttribute = f'updateHook.{channel}.scheduled'
                else:
                    update_hook_nix_path_atttribute = f'updateHook.{channel}.notScheduled'

                projects_to_deploy.append((
                    project_name,
                    [],
                    'TASKCLUSTER_HOOK',
                    {
                        'enable': True,
                        'docker_registry': 'index.docker.io',
                        'docker_repo': 'mozillareleng/services',
                        'name-suffix': '-update-dependencies',
                        'nix_path_attribute': update_hook_nix_path_atttribute,
                    },
                ))

            if 'deploys' in please_cli.config.PROJECTS_CONFIG[project_name]:
                for deploy in please_cli.config.PROJECTS_CONFIG[project_name]['deploys']:
                    for deploy_channel in deploy['options']:
                        if channel == deploy_channel:
                            projects_to_deploy.append((
                                project_name,
                                please_cli.config.PROJECTS_CONFIG[project_name].get('requires', []),
                                deploy['target'],
                                deploy['options'][channel],
                            ))

    click.echo(' => Creating taskcluster tasks definitions')
    tasks = []

    # 1. build tasks
    build_tasks = {}
    for index, project in enumerate(sorted(build_projects)):
        project_uuid = slugid.nice().decode('utf-8')
        required = []
        if pull_request is not None:
            required += [
                'CACHE_BUCKET',
                'CACHE_REGION',
            ]
        secrets = cli_common.taskcluster.get_secrets(
            taskcluster_secret,
            project,
            required=required,
            taskcluster_client_id=taskcluster_client_id,
            taskcluster_access_token=taskcluster_access_token,
        )
        build_tasks[project_uuid] = get_build_task(
            index,
            common_naming.Project(project),
            task_group_id,
            task_id,
            github_commit,
            owner,
            channel,
            taskcluster_secret,
            pull_request is None and secrets.get('CACHE_BUCKET') or None,
            pull_request is None and secrets.get('CACHE_REGION') or None,
            project_revisions[project],
        )
        tasks.append((project_uuid, build_tasks[project_uuid]))

    if projects_to_deploy:

        # 2. maintanance on task
        maintanance_on_uuid = slugid.nice().decode('utf-8')
        if len(build_tasks.keys()) == 0:
            maintanance_on_dependencies = [task_id]
        else:
            maintanance_on_dependencies = [i for i in build_tasks.keys()]
        maintanance_on_task = get_task(
            task_group_id,
            maintanance_on_dependencies,
            github_commit,
            channel,
            taskcluster_secret,
            './please -vv tools maintanance:on ' + ' '.join(list(set([i[0] for i in projects_to_deploy]))),
            {
                'name': '2. Maintanance ON',
                'description': '',
                'owner': owner,
                'source': 'https://github.com/mozilla/release-services/tree/' + channel,

            },
        )
        tasks.append((maintanance_on_uuid, maintanance_on_task))

        # 3. deploy tasks (if on production/staging)
        deploy_tasks = {}
        for index, (project, project_requires, deploy_target, deploy_options) in \
                enumerate(sorted(projects_to_deploy, key=lambda x: x[0])):
            try:
                enable = deploy_options['enable']
            except KeyError:
                raise click.ClickException(f'Missing {enable} in project {project} and channel {channel} deploy options')

            if not enable:
                continue

            project_uuid = slugid.nice().decode('utf-8')
            project_task = get_deploy_task(
                index,
                common_naming.Project(project),
                project_requires,
                deploy_target,
                deploy_options,
                task_group_id,
                maintanance_on_uuid,
                github_commit,
                owner,
                channel,
                taskcluster_secret,
                project_hashes[project],
                project_revisions[project],
            )
            if project_task:
                deploy_tasks[project_uuid] = project_task
                tasks.append((project_uuid, deploy_tasks[project_uuid]))

        # 4. maintanance off task
        maintanance_off_uuid = slugid.nice().decode('utf-8')
        maintanance_off_task = get_task(
            task_group_id,
            [i for i in deploy_tasks.keys()],
            github_commit,
            channel,
            taskcluster_secret,
            './please -vv tools maintanance:off ' + ' '.join(list(set([i[0] for i in projects_to_deploy]))),
            {
                'name': '4. Maintanance OFF',
                'description': '',
                'owner': owner,
                'source': 'https://github.com/mozilla/release-services/tree/' + channel,

            },
        )
        maintanance_off_task['requires'] = 'all-resolved'
        tasks.append((maintanance_off_uuid, maintanance_off_task))

    click.echo(' => Submitting taskcluster definitions to taskcluster')
    if dry_run:
        tasks2 = {task_id: task for task_id, task in tasks}
        for task_id, task in tasks:
            click.echo(' => %s [taskId: %s]' % (task['metadata']['name'], task_id))
            click.echo('    dependencies:')
            deps = []
            for dep in task['dependencies']:
                depName = '0. Decision task'
                if dep in tasks2:
                    depName = tasks2[dep]['metadata']['name']
                    deps.append('      - %s [taskId: %s]' % (depName, dep))
            for dep in sorted(deps):
                click.echo(dep)
    else:
        for task_id, task in tasks:
            taskcluster_queue.createTask(task_id, task)


if __name__ == '__main__':
    cmd()
