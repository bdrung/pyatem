# Copyright 2025, Martijn Braam and the OpenAtem contributors
# SPDX-License-Identifier: GPL-3.0-only
from gi.repository import Gtk, GObject, Gdk

from gtk_switcher.palettepanel import PalettePanel
from pyatem.command import SupersourceBoxPropertiesCommand, SupersourcePropertiesCommand
from pyatem.field import SupersourceBoxPropertiesField, SupersourcePropertiesField


class SupersourcePanel(PalettePanel):
    __gtype_name__ = 'SupersourcePanel'

    def __init__(self, connection, index, box_model, art_model):
        self.connection = connection
        self.name = _("SuperSource {}".format(index + 1))
        self.index = index

        super().__init__(self.name, connection, preset_domain="supersource",
                         preset_fields=['supersource-properties', 'supersource-box-properties'],
                         preset_override=[self.index])

        self.ctrl = {}

        tabs = self.add_tabs()
        for i in range(4):
            self.ctrl[i] = {}
            box = tabs.add_page(f"box{i}", _("Box {}").format(i + 1))
            self.ctrl[i]["enable"] = box.add_control_toggle(_("Enable box"), _("Enable"),
                                                            handler=self.on_box_enable, handler_args=[i])
            self.ctrl[i]["source"] = box.add_control_dropdown(_("Source"), box_model,
                                                              handler=self.on_box_source, handler_args=[i])
            self.ctrl[i]["adj_x"] = Gtk.Adjustment(lower=-4800, upper=4800)
            self.ctrl[i]["x"] = box.add_control_slider_box(_("Position X"), self.ctrl[i]["adj_x"],
                                                           display_min=-48, display_max=48,
                                                           handler=self.on_box_pos, handler_args=[i, "x"])
            self.ctrl[i]["adj_y"] = Gtk.Adjustment(lower=-3400, upper=3400)
            self.ctrl[i]["y"] = box.add_control_slider_box(_("Position Y"), self.ctrl[i]["adj_y"],
                                                           display_min=-34, display_max=34,
                                                           handler=self.on_box_pos, handler_args=[i, "y"])
            self.ctrl[i]["adj_size"] = Gtk.Adjustment(lower=7, upper=1000)
            self.ctrl[i]["size"] = box.add_control_slider_box(_("Size"), self.ctrl[i]["adj_size"],
                                                              display_min=0.07, display_max=1,
                                                              handler=self.on_box_pos, handler_args=[i, "size"])
            box.add_separator()

            self.ctrl[i]["crop"] = box.add_control_toggle(_("Crop enable"), _("Crop"),
                                                          handler=self.on_box_crop, handler_args=[i])
            self.ctrl[i]["adj_top"] = Gtk.Adjustment(lower=0, upper=18000)
            self.ctrl[i]["top"] = box.add_control_slider_box(_("Top"), self.ctrl[i]["adj_top"],
                                                             display_min=0, display_max=18,
                                                             handler=self.on_box_pos, handler_args=[i, "top"])
            self.ctrl[i]["adj_bottom"] = Gtk.Adjustment(lower=0, upper=18000)
            self.ctrl[i]["bottom"] = box.add_control_slider_box(_("Bottom"), self.ctrl[i]["adj_bottom"],
                                                                display_min=0, display_max=18,
                                                                handler=self.on_box_pos, handler_args=[i, "bottom"])
            self.ctrl[i]["adj_left"] = Gtk.Adjustment(lower=0, upper=32000)
            self.ctrl[i]["left"] = box.add_control_slider_box(_("Left"), self.ctrl[i]["adj_left"],
                                                              display_min=0, display_max=32,
                                                              handler=self.on_box_pos, handler_args=[i, "left"])
            self.ctrl[i]["adj_right"] = Gtk.Adjustment(lower=0, upper=32000)
            self.ctrl[i]["right"] = box.add_control_slider_box(_("Right"), self.ctrl[i]["adj_right"],
                                                               display_min=0, display_max=32,
                                                               handler=self.on_box_pos, handler_args=[i, "right"])

        art = tabs.add_page("art", _("Art"))
        self.art_fill = art.add_control_dropdown(_("Source"), art_model, handler=self.on_art_source,
                                                 handler_args=['fill_source'])
        self.art_key = art.add_control_dropdown(_("Key"), art_model, handler=self.on_art_source,
                                                handler_args=['key_source'])
        self.layer = art.add_control_radio(_("Layer"), {
            0: _("Background"),
            1: _("Foreground"),
        }, handler=self.on_layer)
        art.add_separator()
        self.adj_clip = Gtk.Adjustment(upper=1000, step_increment=1, page_increment=10)
        self.adj_gain = Gtk.Adjustment(upper=1000, step_increment=1, page_increment=10)
        self.premultiplied = art.add_control_toggle(_("Key"), _("Pre multiplied"), handler=self.on_premultiplied)
        self.clip = art.add_control_slider(_("Clip"), self.adj_clip, handler=self.on_clip)
        self.gain = art.add_control_slider(_("Gain"), self.adj_gain, handler=self.on_gain)
        self.invert = art.add_control_toggle(_("Invert"), _("Invert"), handler=self.on_invert)

        self.show_all()

    def __repr__(self):
        return '<SupersourcePanel {}>'.format(self.panel_name)

    @PalettePanel.event('change:supersource-properties:*')
    def event_properties(self, data: SupersourcePropertiesField):
        if data.index != self.index:
            return
        self.art_fill.set_active_id(str(data.fill_source))
        self.art_key.set_active_id(str(data.key_source))
        self.set_class(self.premultiplied, 'active', data.premultiplied)
        self.set_class(self.invert, 'active', data.inverted)

        self.layer.set_value(data.layer)

        self.clip.set_sensitive(not data.premultiplied)
        self.gain.set_sensitive(not data.premultiplied)
        self.clip.set_value(data.clip)
        self.gain.set_value(data.gain)

    @PalettePanel.event('change:supersource-box-properties:*')
    def event_boxproperties(self, data: SupersourceBoxPropertiesField):
        if data.index != self.index:
            return
        self.set_class(self.ctrl[data.box]["enable"], "active", data.enabled)
        self.ctrl[data.box]["source"].set_active_id(str(data.source))
        self.ctrl[data.box]["adj_x"].set_value(data.x)
        self.ctrl[data.box]["adj_y"].set_value(data.y)
        self.ctrl[data.box]["adj_size"].set_value(data.size)

        self.set_class(self.ctrl[data.box]["crop"], "active", data.masked)
        self.ctrl[data.box]["top"].set_value(data.mask_top)
        self.ctrl[data.box]["bottom"].set_value(data.mask_bottom)
        self.ctrl[data.box]["left"].set_value(data.mask_left)
        self.ctrl[data.box]["right"].set_value(data.mask_right)

    def on_box_enable(self, widget, box):
        state = widget.get_style_context().has_class('active')
        self.run(SupersourceBoxPropertiesCommand(self.index, box, enabled=not state))

    def on_box_source(self, widget, box):
        active_id = widget.get_active_id()
        if active_id is None:
            return
        source = int(active_id)
        self.run(SupersourceBoxPropertiesCommand(self.index, box, source=source))

    def on_box_crop(self, widget, box):
        state = widget.get_style_context().has_class('active')
        self.run(SupersourceBoxPropertiesCommand(self.index, box, masked=not state))

    def on_box_pos(self, widget, box, prop):
        kwarg = {prop: int(widget.get_value())}
        self.run(SupersourceBoxPropertiesCommand(self.index, box, **kwarg))

    def on_art_source(self, widget, prop):
        active_id = widget.get_active_id()
        if active_id is None:
            return
        kwarg = {prop: int(active_id)}
        self.run(SupersourcePropertiesCommand(self.index, **kwarg))

    def on_premultiplied(self, widget):
        state = widget.get_style_context().has_class('active')
        self.run(SupersourcePropertiesCommand(index=self.index, premultiplied=not state))

    def on_clip(self, widget):
        self.run(SupersourcePropertiesCommand(index=self.index, clip=int(widget.get_value())))

    def on_gain(self, widget):
        self.run(SupersourcePropertiesCommand(index=self.index, gain=int(widget.get_value())))

    def on_invert(self, widget):
        state = widget.get_style_context().has_class('active')
        self.run(SupersourcePropertiesCommand(index=self.index, invert=not state))

    def on_layer(self, widget, value):
        self.run(SupersourcePropertiesCommand(index=self.index, layer=value))
