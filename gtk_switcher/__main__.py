# Copyright 2021 - 2022, Martijn Braam and the OpenAtem contributors
# SPDX-License-Identifier: GPL-3.0-only
import argparse
import locale
import gettext
import logging
import os
import sys

import gi

from gtk_switcher.atemwindow import AtemWindow
from pyatem.logging import setup_logging

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio

gi.require_version('Handy', '1')
from gi.repository import Handy


class AtemApplication(Gtk.Application):
    def __init__(self, application_id, flags, args):
        Gtk.Application.__init__(self, application_id=application_id, flags=flags)
        self.connect("activate", self.new_window)
        self.args = args

        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

    def new_window(self, *args):
        AtemWindow(self, self.args)


def main(version):
    Handy.init()

    parser = argparse.ArgumentParser(description="ATEM Control panel")
    parser.add_argument('ip', help='ip-address of the switcher to connect to', nargs='?')
    parser.add_argument('--persist', action='store_true', help='save the new ip address')
    parser.add_argument('--verbose', dest='level', action='store_const',
                        const=logging.INFO, default=None, help='Show more log messages')
    parser.add_argument('--debug', action='store_true', help='Display a lot of debugging info')
    parser.add_argument('--dump', help='dump data for specific packets', nargs='*')
    parser.add_argument('--view', choices=['switcher', 'media', 'audio', 'camera'], default='switcher',
                        help='default view to open when launching')
    args = parser.parse_args()

    if args.debug:
        args.level = logging.DEBUG
    setup_logging(args.level)

    log = logging.getLogger('Launcher')
    log.info(f'OpenSwitcher version {version}')
    if os.path.isfile('atem.gresource'):
        log.info('using resources from cwd')
        resource = Gio.resource_load("atem.gresource")
        Gio.Resource._register(resource)

    app = AtemApplication("nl.brixit.Switcher", Gio.ApplicationFlags.FLAGS_NONE, args=args)
    app.run()


if __name__ == '__main__':
    locale.bindtextdomain("openswitcher", os.getenv('LOCALEDIR', '.'))
    gettext.install("openswitcher", os.getenv('LOCALEDIR', '.'))
    locale.textdomain("openswitcher")

    main('')
