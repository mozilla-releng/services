# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import

import itertools
import os
import subprocess
from datetime import datetime
from datetime import timedelta

import hglib

from cli_common.command import run_check
from cli_common.log import get_logger
from cli_common.phabricator import PhabricatorAPI
from static_analysis_bot import CLANG_FORMAT
from static_analysis_bot import CLANG_TIDY
from static_analysis_bot import INFER
from static_analysis_bot import MOZLINT
from static_analysis_bot import AnalysisException
from static_analysis_bot import stats
from static_analysis_bot.clang import setup as setup_clang
from static_analysis_bot.clang.format import ClangFormat
from static_analysis_bot.clang.tidy import ClangTidy
from static_analysis_bot.config import ARTIFACT_URL
from static_analysis_bot.config import REPO_UNIFIED
from static_analysis_bot.config import Publication
from static_analysis_bot.config import settings
from static_analysis_bot.infer import setup as setup_infer
from static_analysis_bot.infer.infer import Infer
from static_analysis_bot.lint import MozLint
from static_analysis_bot.report.debug import DebugReporter
from static_analysis_bot.revisions import Revision
from static_analysis_bot.utils import build_temp_file

logger = get_logger(__name__)

TASKCLUSTER_NAMESPACE = 'project.releng.services.project.{channel}.static_analysis_bot.{name}'
TASKCLUSTER_INDEX_TTL = 7  # in days


class Workflow(object):
    '''
    Static analysis workflow
    '''
    def __init__(self, reporters, analyzers, index_service, phabricator_api):
        assert isinstance(analyzers, list)
        assert len(analyzers) > 0, \
            'No analyzers specified, will not run.'
        self.analyzers = analyzers
        assert 'MOZCONFIG' in os.environ, \
            'Missing MOZCONFIG in environment'

        # Use share phabricator API client
        assert isinstance(phabricator_api, PhabricatorAPI)
        self.phabricator = phabricator_api

        # Save Taskcluster ID for logging
        if 'TASK_ID' in os.environ and 'RUN_ID' in os.environ:
            self.taskcluster_task_id = os.environ['TASK_ID']
            self.taskcluster_run_id = os.environ['RUN_ID']
            self.on_taskcluster = True
        else:
            self.taskcluster_task_id = 'local instance'
            self.taskcluster_run_id = 0
            self.on_taskcluster = False

        # Load reporters to use
        self.reporters = reporters
        if not self.reporters:
            logger.warn('No reporters configured, this analysis will not be published')

        # Always add debug reporter and Diff reporter
        self.reporters['debug'] = DebugReporter(output_dir=settings.taskcluster_results_dir)

        # Use TC index service client
        self.index_service = index_service

    @stats.api.timed('runtime.clone')
    def clone(self):
        '''
        Clone mozilla-unified
        '''
        logger.info('Clone mozilla unified', dir=settings.repo_dir)
        cmd = hglib.util.cmdbuilder('robustcheckout',
                                    REPO_UNIFIED,
                                    settings.repo_dir,
                                    purge=True,
                                    sharebase=settings.repo_shared_dir,
                                    branch=b'central')

        cmd.insert(0, hglib.HGPATH)
        proc = hglib.util.popen(cmd)
        out, err = proc.communicate()
        if proc.returncode:
            raise hglib.error.CommandError(cmd, proc.returncode, out, err)

        # Open new hg client
        client = hglib.open(settings.repo_dir)

        # Store MC top revision after robustcheckout
        self.top_revision = client.log('reverse(public())', limit=1)[0].node
        logger.info('Mozilla unified top revision', revision=self.top_revision)

        return client

    def run(self, revision):
        '''
        Run the static analysis workflow:
         * Pull revision from review
         * Checkout revision
         * Run static analysis
         * Publish results
        '''
        analyzers = []

        # Index ASAP Taskcluster task for this revision
        self.index(revision, state='started')

        # Add log to find Taskcluster task in papertrail
        logger.info(
            'New static analysis',
            taskcluster_task=self.taskcluster_task_id,
            taskcluster_run=self.taskcluster_run_id,
            channel=settings.app_channel,
            publication=settings.publication.name,
            revision=str(revision),
        )
        stats.api.event(
            title='Static analysis on {} for {}'.format(settings.app_channel, revision),
            text='Task {} #{}'.format(self.taskcluster_task_id, self.taskcluster_run_id),
        )
        stats.api.increment('analysis')

        with stats.api.timer('runtime.mercurial'):
            try:
                # Start by cloning the mercurial repository
                self.hg = self.clone()
                self.index(revision, state='cloned')

                # Force cleanup to reset top of MU
                # otherwise previous pull are there
                self.hg.update(rev=self.top_revision, clean=True)
                logger.info('Set repo back to Mozilla unified top', rev=self.hg.identify())
            except hglib.error.CommandError as e:
                raise AnalysisException('mercurial', str(e))

            # Load and analyze revision patch
            revision.load(self.hg)
            revision.analyze_patch()

        with stats.api.timer('runtime.mach'):
            # Only run mach if revision has any C/C++ or Java files
            if revision.has_clang_files:

                # Mach pre-setup with mozconfig
                try:
                    logger.info('Mach configure...')
                    run_check(['gecko-env', './mach', 'configure'], cwd=settings.repo_dir)

                    logger.info('Mach compile db...')
                    run_check(['gecko-env', './mach', 'build-backend', '--backend=CompileDB'], cwd=settings.repo_dir)

                    logger.info('Mach pre-export...')
                    run_check(['gecko-env', './mach', 'build', 'pre-export'], cwd=settings.repo_dir)

                    logger.info('Mach export...')
                    run_check(['gecko-env', './mach', 'build', 'export'], cwd=settings.repo_dir)
                except Exception as e:
                    raise AnalysisException('mach', str(e))

                # Download clang build from Taskcluster
                logger.info('Setup Taskcluster clang build...')
                setup_clang()

                # Use clang-tidy & clang-format
                if CLANG_TIDY in self.analyzers:
                    analyzers.append(ClangTidy)
                else:
                    logger.info('Skip clang-tidy')
                if CLANG_FORMAT in self.analyzers:
                    analyzers.append(ClangFormat)
                else:
                    logger.info('Skip clang-format')

            if revision.has_infer_files:
                if INFER in self.analyzers:
                    analyzers.append(Infer)
                    logger.info('Setup Taskcluster infer build...')
                    setup_infer(self.index_service)
                else:
                    logger.info('Skip infer')

            if not (revision.has_clang_files or revision.has_clang_files):
                logger.info('No clang or java files detected, skipping mach, infer and clang-*')

            # Setup python environment
            logger.info('Mach lint setup...')
            cmd = ['gecko-env', './mach', 'lint', '--list']
            out = run_check(cmd, cwd=settings.repo_dir)
            if 'error: problem with lint setup' in out.decode('utf-8'):
                raise AnalysisException('mach', 'Mach lint setup failed')

            # Always use mozlint
            if MOZLINT in self.analyzers:
                analyzers.append(MozLint)
            else:
                logger.info('Skip mozlint')

        if not analyzers:
            logger.error('No analyzers to use on revision')
            return

        self.index(revision, state='analyzing')
        with stats.api.timer('runtime.issues'):
            # Detect initial issues
            if settings.publication == Publication.BEFORE_AFTER:
                before_patch = self.detect_issues(analyzers, revision)
                logger.info('Detected {} issue(s) before patch'.format(len(before_patch)))
                stats.api.increment('analysis.issues.before', len(before_patch))

            # Apply patch
            revision.apply(self.hg)

            # Detect new issues
            issues = self.detect_issues(analyzers, revision)
            logger.info('Detected {} issue(s) after patch'.format(len(issues)))
            stats.api.increment('analysis.issues.after', len(issues))

            # Mark newly found issues
            if settings.publication == Publication.BEFORE_AFTER:
                for issue in issues:
                    issue.is_new = issue not in before_patch

        # Avoid duplicates
        issues = set(issues)

        if not issues:
            logger.info('No issues, stopping there.')
            self.index(revision, state='done', issues=0)
            return

        # Report issues publication stats
        nb_issues = len(issues)
        nb_publishable = len([i for i in issues if i.is_publishable()])
        self.index(revision, state='analyzed', issues=nb_issues, issues_publishable=nb_publishable)
        stats.api.increment('analysis.issues.publishable', nb_publishable)

        # Build patch to help developer improve their code
        self.build_improvement_patch(revision, issues)

        # Publish reports about these issues
        with stats.api.timer('runtime.reports'):
            for reporter in self.reporters.values():
                reporter.publish(issues, revision)

        self.index(revision, state='done', issues=nb_issues, issues_publishable=nb_publishable)

    def detect_issues(self, analyzers, revision):
        '''
        Detect issues for this revision
        '''
        issues = []
        for analyzer_class in analyzers:
            # Build analyzer
            logger.info('Run {}'.format(analyzer_class.__name__))
            analyzer = analyzer_class()

            # Run analyzer on revision and store generated issues
            issues += analyzer.run(revision)

        return issues

    def build_improvement_patch(self, revision, issues):
        '''
        Build a Diff to improve this revision (styling from clang-format)
        '''
        assert isinstance(issues, set)

        # Only use publishable issues
        # and sort them by filename
        issues = sorted(
            filter(lambda i: i.is_publishable(), issues),
            key=lambda i: i.path,
        )

        # Apply a patch on each modified file
        for filename, file_issues in itertools.groupby(issues, lambda i: i.path):
            full_path = os.path.join(settings.repo_dir, filename)
            assert os.path.exists(full_path), \
                'Modified file not found {}'.format(full_path)

            # Build raw "ed" patch
            patch = '\n'.join(filter(None, [issue.as_diff() for issue in file_issues]))
            if not patch:
                continue

            # Apply patch on repository file
            with build_temp_file(patch, '.diff') as patch_path:
                cmd = [
                    'patch',
                    '-i', patch_path,
                    full_path,
                ]
                cmd_output = subprocess.run(cmd)
                assert cmd_output.returncode == 0, \
                    'Generated patch {} application failed on {}'.format(patch_path, full_path)

        # Get clean Mercurial diff on modified files
        files = list(map(lambda x: os.path.join(settings.repo_dir, x).encode('utf-8'), revision.files))
        diff = self.hg.diff(files)
        if diff is None or diff == b'':
            logger.info('No improvement patch')
            return

        # Write diff in results directory
        diff_name = '{}-clang-format.diff'.format(repr(revision))
        diff_path = os.path.join(settings.taskcluster_results_dir, diff_name)
        with open(diff_path, 'w') as f:
            length = f.write(diff.decode('utf-8'))
            logger.info('Improvement diff dumped', path=diff_path, length=length)

        # Build diff download url
        revision.diff_url = ARTIFACT_URL.format(
            task_id=self.taskcluster_task_id,
            run_id=self.taskcluster_run_id,
            diff_name=diff_name,
        )
        logger.info('Diff available online', url=revision.diff_url)

    def index(self, revision, **kwargs):
        '''
        Index current task on Taskcluster index
        '''
        assert isinstance(revision, Revision)

        if not self.on_taskcluster:
            logger.info('Skipping taskcluster indexing', rev=str(revision), **kwargs)
            return

        # Build payload
        payload = revision.as_dict()
        payload.update(kwargs)

        # Always add the indexing
        now = datetime.utcnow()
        date_format = '%Y-%m-%dT%H:%M:%S.%fZ'
        payload['indexed'] = now.strftime(date_format)

        # Index for all required namespaces
        for name in revision.namespaces:
            namespace = TASKCLUSTER_NAMESPACE.format(channel=settings.app_channel, name=name)
            self.index_service.insertTask(
                namespace,
                {
                    'taskId': self.taskcluster_task_id,
                    'rank': 0,
                    'data': payload,
                    'expires': (now + timedelta(days=TASKCLUSTER_INDEX_TTL)).strftime(date_format),
                }
            )
