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

from datetime import datetime
from time import time

from settings import *

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, BaseFilter

import logging
logger = logging.getLogger()


class FilterUsers(BaseFilter):
    def filter(self, message):
        return message.from_user['id'] != TG_USER_ID


class TgHelper(object):
    def __init__(self, bus, busname):
        self.handledSignals = ['NeedApproval']
        if MANAGE_ENABLE_DISABLE:
            self.handledSignals.append('PropertyChanged')
        self._clients = {}
        self._filter_users = FilterUsers()
        self._bus = bus
        self._busname = busname
        self._updater = Updater(token=TG_TOKEN,
                                request_kwargs=TG_REQUEST_KWARGS,
                                workers=TG_WORKERS,
                                use_context=True
                                )
        self._dp = self._updater.dispatcher
        self._dp.add_handler(MessageHandler(self._filter_users, self._reject))
        self._dp.add_handler(CommandHandler("start", self._start))
        self._dp.add_handler(CallbackQueryHandler(self._mandos))
        self._dp.add_error_handler(self._error)
        self._updater.start_polling(poll_interval=TG_POLL_INTERVAL)

    def _reject(self, update, context):
        user = update.message.from_user
        logger.info('Message from unauthorized user {} ({})'.format(user['username'], user['id']))
        self._updater.message.reply_markdown('*Unauthorized user!*')

    def _main_menu(self, update, mode='update'):
        clients = self._bus.get_object(self._busname, '/', follow_name_owner_changes=True
                                       ).GetAllClientsWithProperties()
        menu = []
        for c in clients:
            name = clients[c]['Name']
            host = ' Host {}, '.format(str(clients[c]['Host'])) if str(clients[c]['Host']) else ' '
            enable = 'Enabled' if clients[c]['Enabled'] else 'Disabled'
            approve = ', Awaiting Approval' if clients[c]['ApprovalPending'] else ''
            menu.append([
                InlineKeyboardButton(text='{}:{}{}{}'.format(name, host, enable, approve), callback_data=str(c))
                         ])
        if mode != 'update':
            func = update.message.reply_markdown
        else:
            func = update.callback_query.edit_message_text

        func('Welcome to Mandos Server bot on {0}!\n{0} is serving these clients:'.format(MANDOS_SERVER_NAME),
             reply_markup=InlineKeyboardMarkup(menu, resize_keyboard=True)
             )

    def _client_menu(self, client, update, mode='update'):
        logger.debug('Retrieving {} info.'.format(client))
        clients = self._bus.get_object(self._busname, '/', follow_name_owner_changes=True
                                           ).GetAllClientsWithProperties()
        menu = []

        if mode != 'update':
            func = update.message.reply_markdown
        else:
            func = update.callback_query.edit_message_text

        if client not in clients:
            m = '\u2757 ERROR: client not found!\n'
        else:
            c = clients[client]
            m = '{} on {} details:\n'.format(c['Name'], MANDOS_SERVER_NAME)
            if str(c['Host']):
                m += 'Host: {}\n'.format(str(c['Host']))
            if c['Enabled']:
                m += 'Status: Enabled\n'
                menu.append([InlineKeyboardButton(text='Disable', callback_data='D|' + client)])
            else:
                m += 'Status: Disabled\n'
                menu.append([InlineKeyboardButton(text='Enable', callback_data='E|' + client)])
            m += 'Approved by default: {}\n'.format('Yes' if c['ApprovedByDefault'] else 'No')
            m += 'Checker: {}\nLatest Checker Success: {} (UTC)\n'.format(
                           c['Checker'],               c['LastCheckedOK'].replace('T', ' ')[0:-7])
            m += 'Current time: {} (UTC)\n'.format(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        menu.append([InlineKeyboardButton(text='\ud83d\udd19', callback_data='main')])
        func(m, reply_markup=InlineKeyboardMarkup(menu, resize_keyboard=True))

    def _enable_menu(self, signal, path, args, properties, ts):
        client_info = "{} ({}) on {}".format(str(properties['Name']), str(properties['Host']), MANDOS_SERVER_NAME)
        enabled = args[1]
        logger.debug("Status change of {} : {}".format(client_info, 'Enabled' if enabled else 'Disabled'))
        m = "Client {} has been {} at {} (UTC):\n".format(
                    client_info, 'ENABLED!' if enabled else 'DISABLED!',
                                      datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        menu = [[InlineKeyboardButton(text='\u2705 Accept', callback_data='I|' + ts + '|' + path),
                InlineKeyboardButton(text='\u274c Reverse', callback_data='R|' + ts + '|' + path + '|' + str(enabled))]]
        mes = self._updater.bot.sendMessage(chat_id=TG_USER_ID,
                                            text=m,
                                            reply_markup=InlineKeyboardMarkup(menu, resize_keyboard=True)
                                            )
        return

    def _approve_menu(self, path, args, properties, ts):
        client_address = None
        if len(args) == 3:
            milliseconds_to_expire, default, client_address = args
        else:
            milliseconds_to_expire, default = args
        m = "Boot request approval required on {} at {} (UTC):\n".format(
                                               MANDOS_SERVER_NAME,
                                                     datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        m += "Client: {}\n".format(properties['Name'])
        if str(properties['Host']):
            m += 'Host: {}\n'.format(str(properties['Host']))
        if client_address:
            m += 'Connecting from: {}\n'.format(str(client_address))
        m += 'Default response: {}\n'.format('Approved' if default == 1 else 'Denied')
        m += 'Timeout (seconds): {}\n'.format(str(int(milliseconds_to_expire / 1000)))
        menu = [[InlineKeyboardButton(text='\u2705 Approve', callback_data='a|' + ts + '|' + path),
                InlineKeyboardButton(text='\u274c Deny', callback_data='d|' + ts + '|' + path)]]
        mes = self._updater.bot.sendMessage(chat_id=TG_USER_ID,
                                            text=m,
                                            reply_markup=InlineKeyboardMarkup(menu, resize_keyboard=True)
                                            )

    def _client_toggle(self, d, update):
        client = d[2:]
        proxy = self._bus.get_object(self._busname, client, follow_name_owner_changes=True)
        if d[0:1] == 'D':
            proxy.Disable()
        else:
            proxy.Enable()
        self._client_menu(client, update)

    def _client_enable(self, d, update):
        ts = d.split('|')[1]
        client = d.split('|')[2]
        if client not in self._clients or ts != self._clients[client]['PropertyChanged']['timestamp']:
            update.callback_query.edit_message_text(update.callback_query.message.text + '\n\nOutdated!\n----\n')
            return
        m = update.callback_query.message.text + '\n\n'
        if d[0:1] == 'R':
            proxy = self._bus.get_object(self._busname, client, follow_name_owner_changes=True)
            if d.split('|')[3] == '1':
                proxy.Disable()
            else:
                proxy.Enable()
            m += '\u21b6 Reversed!\n----\n'
        else:
            m += '\u2713 Accepted!\n----\n'
        update.callback_query.edit_message_text(m)

    def _client_approve(self, d, update):
        ts = d.split('|')[1]
        client = d.split('|')[2]
        if client not in self._clients or ts != self._clients[client]['NeedApproval']['timestamp']:
            update.callback_query.edit_message_text(update.callback_query.message.text + '\n\nOutdated!\n----\n')
            return
        proxy = self._bus.get_object(self._busname, client, follow_name_owner_changes=True)
        proxy.Approve(d[0:1] == 'a')
        if d[0:1] == 'd' and DISABLE_IF_DENIED:
            proxy.Disable()
        m = '\n\n{} at {} (UTC)\n----\n'.format(
               '\u2705 Approved' if d[0:1] == 'a' else '\u274c Denied',
                       datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        update.callback_query.edit_message_text(update.callback_query.message.text + m)

    def _start(self, update, context):
        user = update.message.from_user
        logger.info('Start talking with user {} ({})'.format(user['username'], user['id']))
        self._main_menu(update, 'new')

    def _mandos(self, update, context):
        d = update.callback_query.data
        logger.debug("Telegram helper starts processing query with data: {}".format(d))
        if d == 'main':
            self._main_menu(update)
        elif d[0:9] == '/clients/':
            self._client_menu(d, update)
        elif d[0:2] == 'D|' or d[0:2] == 'E|':
            self._client_toggle(d, update)
        elif d[0:2] == 'a|' or d[0:2] == 'd|':
            self._client_approve(d, update)
        elif d[0:2] == 'I|' or d[0:2] == 'R|':
            self._client_enable(d, update)

    def _error(self, update, context):
        logger.warning('Update "%s" caused error "%s"', update, context.error)

    def process(self, signal, path, args, properties, proxy):
        logger.debug("Telegram helper starts processing signal: {} on {}".format(signal, path))
        for arg in args:
            logger.debug('            ' + str(arg))
        if signal == "PropertyChanged" and args[0] != "Enabled":
            logger.debug("Ignored")
            return
        client = str(path)
        if client not in self._clients:
            self._clients[client] = {
                "PropertyChanged": {"timestamp": 0},
                "NeedApproval": {"timestamp": 0}
            }
        ts = str(int(time()))
        self._clients[client][signal]['timestamp'] = ts
        if signal == "PropertyChanged":
            self._enable_menu(signal, path, args, properties, ts)
        if signal == "NeedApproval":
            self._approve_menu(path, args, properties, ts)

    def stop(self):
        self._updater.stop()
