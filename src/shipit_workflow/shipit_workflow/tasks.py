# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import copy

import jsone
import requests
import slugid
import taskcluster

from cli_common.log import get_logger
from shipit_workflow.release import is_rc

log = get_logger(__name__)

# Phases per product, ordered
SUPPORTED_FLAVORS = {
    'firefox': [
        {'name': 'promote_firefox', 'in_previous_graph_ids': True},
        {'name': 'push_firefox', 'in_previous_graph_ids': True},
        {'name': 'ship_firefox', 'in_previous_graph_ids': True},
    ],
    'firefox_rc': [
        {'name': 'promote_firefox_rc', 'in_previous_graph_ids': True},
        {'name': 'ship_firefox_rc', 'in_previous_graph_ids': False},
        {'name': 'push_firefox', 'in_previous_graph_ids': True},
        {'name': 'ship_firefox', 'in_previous_graph_ids': True},
    ],
    'fennec': [
        {'name': 'promote_fennec', 'in_previous_graph_ids': True},
        {'name': 'ship_fennec', 'in_previous_graph_ids': True},
    ],
    'fennec_rc': [
        {'name': 'promote_fennec', 'in_previous_graph_ids': True},
        {'name': 'ship_fennec_rc', 'in_previous_graph_ids': True},
        {'name': 'ship_fennec', 'in_previous_graph_ids': True},
    ],
    'devedition': [
        {'name': 'promote_devedition', 'in_previous_graph_ids': True},
        {'name': 'push_devedition', 'in_previous_graph_ids': True},
        {'name': 'ship_devedition', 'in_previous_graph_ids': True},
    ],
    'thunderbird': [
        {'name': 'promote_thunderbird', 'in_previous_graph_ids': True},
        {'name': 'push_thunderbird', 'in_previous_graph_ids': True},
        {'name': 'ship_thunderbird', 'in_previous_graph_ids': True},
    ],
}


class UnsupportedFlavor(Exception):
    def __init__(self, description):
        self.description = description


def get_trust_domain(project):
    if 'comm' in project:
        return 'comm'
    else:
        return 'gecko'


def find_decision_task_id(project, revision):
    decision_task_route = '{trust_domain}.v2.{project}.revision.{revision}.taskgraph.decision'.format(
        trust_domain=get_trust_domain(project), project=project, revision=revision)
    index = taskcluster.Index()
    return index.findTask(decision_task_route)['taskId']


def fetch_actions_json(task_id):
    queue = taskcluster.Queue()
    actions_url = queue.buildUrl('getLatestArtifact', task_id, 'public/actions.json')
    q = requests.get(actions_url)
    q.raise_for_status()
    return q.json()


def find_action(name, actions):
    for action in actions['actions']:
        if action['name'] == name:
            return copy.deepcopy(action)
    else:
        return None


def extract_our_flavors(avail_flavors, product, version, partial_updates):
    if is_rc(version, partial_updates):
        product_key = '{}_rc'.format(product)
    else:
        product_key = product
    # sanity check
    all_flavors = set([fl['name'] for fl in SUPPORTED_FLAVORS[product_key]])
    if not set(avail_flavors).issuperset(all_flavors):
        description = 'Some flavors are not in actions.json: {}.'.format(
            all_flavors.difference(set(avail_flavors)))
        raise UnsupportedFlavor(description=description)
    return SUPPORTED_FLAVORS[product_key]


def generate_action_task(action_name, action_task_input, actions):
    target_action = find_action(action_name, actions)
    context = copy.deepcopy(actions['variables'])  # parameters
    action_task_id = slugid.nice().decode('utf-8')
    context.update({
        'input': action_task_input,
        'taskGroupId': action_task_id,
        'ownTaskId': action_task_id,
        'taskId': None,
        'task': None,
    })
    action_task = copy.deepcopy(target_action['task'])
    log.info('TASK: %s', action_task)
    return action_task_id, action_task, context


def render_action_task(task, context, action_task_id):
    action_task = jsone.render(task, context)
    return action_task
