# Copyright 2025, Martijn Braam and the OpenAtem contributors
# SPDX-License-Identifier: GPL-3.0-only
from gi.repository import Gtk, GObject, Gdk

from gtk_switcher.palettepanel import PalettePanel
from pyatem.command import MediaplayerSelectCommand


class MediaPlayerPanel(PalettePanel):
    __gtype_name__ = 'MediaPlayerpanel'

    def __init__(self, index, model_media, connection):
        self.index = index
        self.model_media = model_media
        self.connection = connection

        self.name = _("Media Player {}").format(index + 1)
        super().__init__(self.name, connection)

        self.dropdown = self.add_control_dropdown(_("Media"), self.model_media, handler=self.on_mediaplayer_change)

        self.show_all()

    def __repr__(self):
        return '<MediaPlayerPanel {}>'.format(self.panel_name)

    @PalettePanel.event('change:mediaplayer-selected:*')
    def on_mediaplayer_switcher_source_change(self, data):
        if data.index != self.index:
            return

        with self.model:
            if data.source_type == 1:
                self.dropdown.set_active_id(str(data.slot))

    def on_mediaplayer_change(self, widget):
        index = widget.get_active_id()
        if index is None or index == "":
            return

        index = int(index)
        self.run(MediaplayerSelectCommand(self.index, still=index))
