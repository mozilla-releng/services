# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from shipit_dashboard.models import (
    BugResult, BugContributor, BugAnalysis, Contributor
)
from shipit_dashboard import SCOPES_ADMIN
from flask_login import current_user
from releng_common import log
import html


logger = log.get_logger('shipit_dashboard.serializers')


def serialize_contributor(contributor, link=None):
    """
    Helper to serialize a contributor & its role
    """
    assert isinstance(contributor, Contributor)

    out = {
        'id': contributor.id,
        'email': contributor.email,
        'name': contributor.name,
        'avatar': contributor.avatar_url,
        'karma': contributor.karma or 0,
        'comment_public': contributor.comment_public or '',
    }
    if current_user.has_permissions(SCOPES_ADMIN):
        # Only admins can see/edit the private comment
        out['comment_private'] = contributor.comment_private or ''

    if link is not None:
        assert isinstance(link, BugContributor)
        out['roles'] = link.roles.split(',')

    return out


def serialize_patch(patch):
    """
    Helper to serialize a Patch
    """
    assert isinstance(patch, dict)
    return {
        'source': patch['source'],
        'changes_add': patch['changes_add'],
        'changes_del': patch['changes_del'],
        'changes_size': patch['changes_size'],
        'url': patch['url'],
        'languages': patch.get('languages', []),
        'merge': patch.get('merge', {}),
    }


def serialize_bug(bug):
    """
    Helper to serialize a bug from its payload
    """
    assert isinstance(bug, BugResult)

    payload = bug.payload_data
    if not payload:
        raise Exception('Missing payload')
    bug_data = payload.get('bug')
    analysis = payload.get('analysis')
    if not bug_data or not analysis:
        raise Exception('Missing Bug data or Analysis')

    # Build uplift
    uplift = None
    if analysis.get('uplift_comment'):
        comment = analysis['uplift_comment']
        if 'html' in comment:
            comment_html = html.unescape(comment['html'])
        else:
            comment_html = comment.get('text', 'No comment.')
        uplift = {
            'id': comment['id'],
            'comment': comment_html,
        }

    # Build flags
    status_base_flag = 'cf_status_'
    tracking_base_flag = 'cf_tracking_'

    def _filter_flags(base):
        out = [(k.replace(base, '', 1), v) for k, v in bug_data.items() if k.startswith(base + 'firefox')]  # noqa
        return dict(out)

    return {
        # Base
        'id': bug.id,
        'bugzilla_id': bug.bugzilla_id,
        'url': payload.get('url', 'https://bugzil.la/{}'.format(bug.bugzilla_id)),  # noqa
        'summary': bug_data['summary'],
        'keywords': bug_data['keywords'],
        'component': bug_data['component'],
        'product': bug_data['product'],
        'status': bug_data['status'],
        'flags_status': _filter_flags(status_base_flag),
        'flags_tracking': _filter_flags(tracking_base_flag),

        # Contributor
        'contributors': [
            serialize_contributor(contrib, link)
            for contrib, link in bug.list_contributors()
        ],

        # Stats
        'changes_size': analysis.get('changes_size', 0),

        # Uplift request
        'uplift': uplift,

        # Patches
        'patches': dict([
            (patch_id, serialize_patch(patch))
            for patch_id, patch in analysis['patches'].items()
        ]),
        'landings': {k: v for k, v in analysis.get('landings', {}).items() if v is not None},  # noqa

        # Versions
        'versions': payload.get('versions', {}),
    }


def serialize_analysis(analysis, bugs_nb, full=True):
    """
    Helper to serialize an analysis
    """
    assert isinstance(analysis, BugAnalysis)
    assert isinstance(bugs_nb, int)

    logger.info('Serializing analysis', analysis=analysis, bugs_nb=bugs_nb, full=full)  # noqa

    out = {
        'id': analysis.id,
        'name': analysis.name,
        'count': bugs_nb,
        'parameters': analysis.parameters,
    }

    if full:
        # Add bugs
        out['bugs'] = [serialize_bug(b) for b in analysis.bugs]
    else:
        out['bugs'] = []

    return out
