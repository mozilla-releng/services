# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import List

from flask import current_app
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import Conflict
from werkzeug.exceptions import NotFound

from backend_common.auth import auth

from .models import Identity
from .models import Preference

AUTHENTICATION_SCOPE_PREFIX = 'project:releng:services/releng_notification_identity/permission/'


def _get_identity_preferences(identity_name: str) -> List[Preference]:
    session = current_app.db.session

    identity = session.query(Identity).filter(Identity.name == identity_name).first()
    if identity:
        preferences = session.query(Preference).filter(identity.id == Preference.identity).all()
        if preferences:
            return preferences
        else:
            raise NotFound('Identity with name {} has no configured notification preferences.'.format(identity_name))

    else:
        raise NotFound('Identity with name {} could not be found.'.format(identity_name))


@auth.require_scopes([AUTHENTICATION_SCOPE_PREFIX + 'put_identity'])
def put_identity(identity_name: str, body: dict) -> None:
    try:
        session = current_app.db.session

        if session.query(Identity).filter(Identity.name == identity_name).count():
            raise Conflict('Identity with the name {} already exists'.format(identity_name))

        new_identity = Identity(name=identity_name)
        session.add(new_identity)
        session.flush()

        preferences = [
            Preference(**pref, identity=new_identity.id)
            for pref in body['preferences']
        ]

        session.add_all(preferences)
        session.commit()

        return None

    except IntegrityError as ie:
        raise BadRequest('Request preferences contain duplicate urgency level {}.'.format(ie.params.get('urgency')))


def modify_existing_preferences(new_preferences_lookup: dict, existing_preferences: list):
    for record in existing_preferences:
        if record.urgency not in new_preferences_lookup:
            continue

        new_preference = new_preferences_lookup[record.urgency]

        record.channel = new_preference['channel']
        record.target = new_preference['target']

        yield record


@auth.require_scopes([AUTHENTICATION_SCOPE_PREFIX + 'post_identity'])
def post_identity(identity_name: str, body: dict) -> None:
    session = current_app.db.session
    preference_records = _get_identity_preferences(identity_name)
    new_preference_lookup = {
        new_preference['urgency']: new_preference
        for new_preference in body['preferences']
    }

    for record in modify_existing_preferences(new_preference_lookup, preference_records):
        session.merge(record)
        new_preference_lookup.pop(record.urgency)

    if new_preference_lookup:
        identity = session.query(Identity).filter(Identity.name == identity_name).first()
        for new_urgency, new_preference in new_preference_lookup.items():
            new_pref = Preference(**new_preference, identity=identity.id)
            session.add(new_pref)

    session.commit()
    return None


@auth.require_scopes([AUTHENTICATION_SCOPE_PREFIX + 'get_identity'])
def get_identity(identity_name: str) -> dict:
    preferences = _get_identity_preferences(identity_name)
    if preferences:
        return {
            'preferences': [
                {**pref.to_dict(), 'name': identity_name}
                for pref in preferences
            ],
        }

    else:
        raise NotFound('No preferences found for identity {}.'.format(identity_name))


@auth.require_scopes([AUTHENTICATION_SCOPE_PREFIX + 'get_identity_preference_by_urgency'])
def get_identity_preference_by_urgency(identity_name: str, urgency: str) -> dict:
    preferences = _get_identity_preferences(identity_name)
    preference_by_urgency_level = list(filter(lambda pref: pref.urgency == urgency, preferences))
    if preference_by_urgency_level:
        return {
            'preferences': [
                {
                    'name': identity_name,
                    **preference_by_urgency_level[0].to_dict(),
                }
            ],
        }

    else:
        raise NotFound('No {} preference found for identity {}.'.format(urgency, identity_name))


@auth.require_scopes([AUTHENTICATION_SCOPE_PREFIX + 'delete_identity_by_name'])
def delete_identity_by_name(identity_name: str) -> None:
    session = current_app.db.session
    identity = session.query(Identity).filter(Identity.name == identity_name).first()
    if identity:
        session.delete(identity)
        session.commit()

        return None

    else:
        raise NotFound('Identity with name {} not found.'.format(identity_name))


@auth.require_scopes([AUTHENTICATION_SCOPE_PREFIX + 'delete_identity_preferences_by_urgency'])
def delete_identity_preference_by_urgency(identity_name: str, urgency: str) -> None:
    session = current_app.db.session
    identity_key = session.query(Identity).filter(Identity.name == identity_name).value(Identity.id)
    if identity_key:
        notification_preference = session.query(Preference)\
            .filter(Preference.identity == identity_key)\
            .filter(Preference.urgency == urgency)\
            .first()

        if notification_preference:
            session.delete(notification_preference)
            session.commit()

            return None

        else:
            raise NotFound('Identity {} has no preferences for urgency level {}.'.format(identity_name, urgency))
    else:
        raise NotFound('Identity with name {} not found.'.format(identity_name))
