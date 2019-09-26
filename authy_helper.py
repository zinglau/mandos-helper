#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright © 2019 Zing Lau (zinglau2015@gmail.com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#

from threading import activeCount, current_thread, Thread
from polling import poll
from time import sleep

from settings import *

from authy.api import AuthyApiClient

import logging
logger = logging.getLogger()


class AuthyHelper(object):
    def __init__(self, bus, busname):
        self.handledSignals = ['NeedApproval']
        self._authy_api = AuthyApiClient(TWILLO_AUTHY_API_KEY)
        self._clients = {}

    def _check_response(self, uuid, client):
        logger.debug('Latest thread for client {} is {}'.format(client, self._clients[client]))
        thread_id = current_thread().ident
        if self._clients[client] != thread_id:
            return 'outdated'
        status_response = self._authy_api.one_touch.get_approval_status(uuid)
        if status_response.ok():
            # one of 'pending', 'approved', 'denied', or 'expired'
            approval_status = status_response.content['approval_request']['status']
            if approval_status != 'pending':
                return approval_status
        else:
            logger.error(status_response.errors())
        return 'continue'

    def _run(self, signal, path, args, properties, proxy):
        # UGLY HACK: wait so main thread has time to store our thread id
        sleep(1)
        thread_id = current_thread().ident
        current_thread().name = current_thread().name + ' ' + str(thread_id)
        logger.info("Authy helper child thread starts processing signal: {} on {}".format(signal, path))
        for arg in args:
            logger.debug('            ' + str(arg))
        client_address = None
        if len(args) == 3:
            milliseconds_to_expire, default, client_address = args
        else:
            milliseconds_to_expire, default = args
        seconds_to_expire = int(milliseconds_to_expire / 1000)
        client = path[9:]
        details = {
                   'Client': str(properties['Name']),
                   'Host': str(properties['Host']),
                   'Connecting from': str(client_address),
                   'Default response': ('Approved' if default == 1 else 'Denied'),
                   'Timeout (seconds)': str(seconds_to_expire)
                  }
        logger.debug(details)
        request = self._authy_api.one_touch.send_request(
            AUTHY_USER_ID,
            "Boot request approval required on {}:".format(MANDOS_SERVER_NAME),
            seconds_to_expire=seconds_to_expire,
            details=details,
        )
        if request.ok():
            uuid = request.get_uuid()
            status = poll(
                lambda: self._check_response(uuid, client),
                check_success=lambda s: s != 'continue',
                step=AUTHY_POLL_INTERVAL,
                timeout=seconds_to_expire
            )
            logger.info(status)
            if self._clients[client] == thread_id:
                logger.info('Authy helper child thread received request result: ' + status)
                if status == 'approved':
                    proxy.Approve(True)
                elif status == 'denied':
                    proxy.Approve(False)
                    if AUTHY_DISABLE_IF_DENIED: proxy.Disable()
        else:
            logger.error(request.errors())

    def process(self, signal, path, args, properties, proxy):
        logger.debug("Authy helper starts processing signal: {} on {}".format(signal, path))
        for arg in args: logger.debug('            ' + str(arg))
        client = path[9:]
        t = Thread(name=client, target=self._run, args=(signal, path, args, properties, proxy))
        t.setDaemon(True)
        t.start()
        self._clients[client] = t.ident

    def stop(self):
        pass
