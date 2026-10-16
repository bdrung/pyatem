# Copyright 2025, Martijn Braam and the OpenAtem contributors
# SPDX-License-Identifier: GPL-3.0-only
from gi.repository import Gtk, GObject, Gdk

from gtk_switcher.palettepanel import PalettePanel
from pyatem.command import ColorGeneratorCommand, DkeySetFillCommand, DkeySetKeyCommand, DkeyGainCommand, \
    DkeyMaskCommand
from pyatem.field import DkeyPropertiesField


class DownstreamKeyerPanel(PalettePanel):
    __gtype_name__ = 'DownstreamKeyerPanel'

    def __init__(self, connection, index, model_fill, model_key):
        self.connection = connection
        self.name = _("Downstream keyer {}").format(index + 1)
        self.index = index

        super().__init__(self.name, connection, preset_domain="dsk", preset_override=[self.index], preset_fields=[
            'dkey-properties-base',
            'dkey-properties'
        ])

        self.adj_clip = Gtk.Adjustment(upper=1000, step_increment=1, page_increment=10)
        self.adj_gain = Gtk.Adjustment(upper=1000, step_increment=1, page_increment=10)

        self.adj_top = Gtk.Adjustment(upper=9000, lower=-9000, step_increment=1, page_increment=10)
        self.adj_bottom = Gtk.Adjustment(upper=9000, lower=-9000, step_increment=1, page_increment=10)
        self.adj_left = Gtk.Adjustment(upper=16000, lower=-16000, step_increment=1, page_increment=10)
        self.adj_right = Gtk.Adjustment(upper=16000, lower=-16000, step_increment=1, page_increment=10)

        self.fill_source = self.add_control_dropdown(_("Fill source"), model_fill, handler=self.on_fill_change)
        self.key_source = self.add_control_dropdown(_("Key source"), model_key, handler=self.on_key_change)
        self.add_separator()
        self.premultiplied = self.add_control_toggle(_("Key"), _("Pre multiplied"), handler=self.on_premultiplied)
        self.clip = self.add_control_slider(_("Clip"), self.adj_clip, handler=self.on_clip)
        self.gain = self.add_control_slider(_("Gain"), self.adj_gain, handler=self.on_gain)
        self.invert = self.add_control_toggle(_("Invert"), _("Invert"), handler=self.on_invert)
        self.add_separator()
        self.mask_enable = self.add_control_toggle(_("Use mask"), _("Mask"), handler=self.on_mask_enable)

        self.top = self.add_control_slider_box(_("Top"), self.adj_top, display_min=-9, display_max=9,
                                               handler=self.on_mask, handler_args=['top'])
        self.bottom = self.add_control_slider_box(_("Bottom"), self.adj_bottom, display_min=-9, display_max=9,
                                                  handler=self.on_mask, handler_args=['bottom'])
        self.left = self.add_control_slider_box(_("Left"), self.adj_left, display_min=-16, display_max=16,
                                                handler=self.on_mask, handler_args=['left'])
        self.right = self.add_control_slider_box(_("Right"), self.adj_right, display_min=-16, display_max=16,
                                                 handler=self.on_mask, handler_args=['right'])

        self.show_all()

    def __repr__(self):
        return '<DownstreamKeyerPanel {}>'.format(self.panel_name)

    @PalettePanel.event('change:dkey-properties-base:*')
    def event_key_properties_base(self, data):
        if data.index != self.index:
            return

        with self.model:
            self.fill_source.set_active_id(str(data.fill_source))
            self.key_source.set_active_id(str(data.key_source))

    @PalettePanel.event('change:dkey-properties:*')
    def event_dkey_properties(self, data: DkeyPropertiesField):
        if data.index != self.index:
            return

        self.set_class(self.premultiplied, 'active', data.premultiplied)
        self.set_class(self.invert, 'active', data.invert_key)
        self.set_class(self.mask_enable, 'active', data.masked)

        self.clip.set_sensitive(not data.premultiplied)
        self.gain.set_sensitive(not data.premultiplied)
        self.adj_clip.set_value(data.clip)
        self.adj_gain.set_value(data.gain)

        self.adj_top.set_value(data.top)
        self.adj_bottom.set_value(data.bottom)
        self.adj_left.set_value(data.left)
        self.adj_right.set_value(data.right)

    def on_fill_change(self, widget):
        active_id = widget.get_active_id()
        if active_id is None:
            return
        source = int(active_id)
        self.run(DkeySetFillCommand(index=self.index, source=source))

    def on_key_change(self, widget):
        active_id = widget.get_active_id()
        if active_id is None:
            return
        source = int(active_id)
        self.run(DkeySetKeyCommand(index=self.index, source=source))

    def on_premultiplied(self, widget):
        state = widget.get_style_context().has_class('active')
        self.run(DkeyGainCommand(index=self.index, premultiplied=not state))

    def on_clip(self, widget):
        self.run(DkeyGainCommand(index=self.index, clip=int(widget.get_value())))

    def on_gain(self, widget):
        self.run(DkeyGainCommand(index=self.index, gain=int(widget.get_value())))

    def on_invert(self, widget):
        state = widget.get_style_context().has_class('active')
        self.run(DkeyGainCommand(index=self.index, invert=not state))

    def on_mask(self, widget, side):
        prop = {side: int(widget.get_value())}
        self.run(DkeyMaskCommand(index=self.index, **prop))

    def on_mask_enable(self, widget):
        state = widget.get_style_context().has_class('active')
        self.run(DkeyMaskCommand(index=self.index, enabled=not state))
