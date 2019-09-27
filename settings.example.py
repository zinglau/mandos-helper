#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Unique name for this Mandos server
MANDOS_SERVER_NAME = ""

# Whether denied client should also be disabled to avoid further notifications
DISABLE_IF_DENIED = False

# Whether client enable/disable changes should be managed, with option to reverse
MANAGE_ENABLE_DISABLE = True

### BEGIN Authy helper settings

# In Twillo console, navigate to the Authy application and locate the following
# SETTINGS -> Properties -> PRODUCTION API KEY
TWILLO_AUTHY_API_KEY = ""

# Authy user id to send the push notifications to
# This user must be added to your Twillo Authy application and set active
AUTHY_USER_ID = 0

# Polling frequency in seconds
AUTHY_POLL_INTERVAL = 5

### END Authy helper settings


### BEGIN Telegram helper settings

# This is given by @BotFather as HTTP API token when new bot is registered
# See https://core.telegram.org/bots#6-botfather
TG_TOKEN = ""

# TG user ID used to control the bot
TG_USER_ID = 0

# Optional, HTTP PROXY for the bot if required
# See https://github.com/python-telegram-bot/python-telegram-bot/wiki/Working-Behind-a-Proxy
TG_REQUEST_KWARGS = {
    #'proxy_url': 'http://ip:port/',
    # Optional, if you need authentication:
    #'username': 'PROXY_USER',
    #'password': 'PROXY_PASS',
}

# Number of async workers to run. One should be enough for personal use
TG_WORKERS = 1

# Polling frequency in seconds
TG_POLL_INTERVAL = 5.0

### END Telegram helper settings
