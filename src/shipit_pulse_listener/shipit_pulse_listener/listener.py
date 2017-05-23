from cli_common.pulse import run_consumer
from cli_common.taskcluster import get_secrets
from cli_common.log import get_logger
from shipit_pulse_listener.hook import Hook
import asyncio

logger = get_logger(__name__)


class HookStaticAnalysis(Hook):
    """
    Taskcluster hook handling the static analysis
    """
    def __init__(self, branch):
        super().__init__(
            'project-releng',
            'services-{}-shipit-static-analysis-bot'.format(branch),
            'exchange/mozreview/',
            'mozreview.commits.published',
        )

    def parse_payload(self, payload):
        """
        Start new tasks for every bugzilla id
        """
        # Filter on repo url
        repository_url = payload.get('repository_url')
        if not repository_url:
            raise Exception('Missing repository url in payload')
        if repository_url != 'https://reviewboard-hg.mozilla.org/gecko':
            logger.warn('Skipping this message, invalid repository url', url=repository_url)  # noqa
            return

        # Extract commits
        commits = [c['rev'] for c in payload.get('commits', [])]
        logger.info('Received new commits', commits=commits)
        return {
            'REVISIONS': ' '.join(commits),
        }


class HookRiskAssessment(Hook):
    """
    Taskcluster hook handling the risk assessment
    """
    def __init__(self, branch):
        super().__init__(
            'project-releng',
            'services-{}-shipit-risk-assessment-bot'.format(branch),
            'exchange/hgpushes/v1',
        )

    def parse_payload(self, payload):
        """
        Start new tasks for every bugzilla id
        """
        bugzilla_id = payload.get('id')
        if not bugzilla_id:
            raise Exception('Missing bugzilla id')
        logger.info('Received new Bugzilla message', bz_id=bugzilla_id)

        return {
            'REVISION': bugzilla_id,
        }


class PulseListener(object):
    """
    Listen to pulse messages and trigger new tasks
    """
    def __init__(self):

        # Fetch pulse credentials from TC secrets
        self.secrets = get_secrets(required=('PULSE_USER', 'PULSE_PASSWORD',))

    def run(self, branch):

        # Build hooks for branch
        hooks = [
            HookStaticAnalysis(branch),
            HookRiskAssessment(branch),
        ]

        # Run hooks pulse listeners together
        # but only use hoks with active definitions
        consumers = [
            hook.connect_pulse(self.secrets)
            for hook in hooks
            if hook.connect_taskcluster()
        ]
        run_consumer(asyncio.gather(*consumers))
