# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import asyncio
import sys

import aioamqp

import cli_common.log

logger = cli_common.log.get_logger(__name__)


async def create_consumer(user, password, exchange, topic, callback):
    '''
    Create an async consumer for Mozilla pulse queues
    Inspired by : https://github.com/mozilla-releng/fennec-aurora-task-creator/blob/master/fennec_aurora_task_creator/worker.py  # noqa
    '''
    assert isinstance(user, str)
    assert isinstance(password, str)
    assert isinstance(exchange, str)
    assert isinstance(topic, str)

    host = 'pulse.mozilla.org'
    port = 5671

    try:
        _, protocol = await aioamqp.connect(
            host=host,
            login=user,
            password=password,
            ssl=True,
            port=port,
        )
    except aioamqp.AmqpClosedConnection as acc:
        logger.exception('AMQP Connection closed: %s', acc)
        return

    channel = await protocol.channel()
    await channel.basic_qos(
        prefetch_count=1,
        prefetch_size=0,
        connection_global=False
    )

    queue = 'queue/{}/{}'.format(user, exchange)
    await channel.queue_declare(queue_name=queue, durable=True)
    logger.info('Connected', queue=queue, topic=topic, exchange=exchange)

    await channel.queue_bind(exchange_name=exchange,
                             queue_name=queue,
                             routing_key=topic)
    await channel.basic_consume(callback, queue_name=queue)

    logger.info('Worker starts consuming messages')


def run_consumer(consumer):
    '''
    Helper to run indefinitely an asyncio consumer
    '''
    event_loop = asyncio.get_event_loop()

    try:
        event_loop.run_until_complete(consumer)
        event_loop.run_forever()
    except KeyboardInterrupt:
        # TODO: make better shutdown
        logger.exception('KeyboardInterrupt registered, exiting.')
        event_loop.stop()
        while event_loop.is_running():
            pass
        event_loop.close()
        sys.exit()
