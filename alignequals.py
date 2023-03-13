import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")

from gi.repository import GObject, Gio, Gtk, Gedit

try:
    import gettext
    gettext.bindtextdomain("gedit-plugins")
    gettext.textdomain("gedit-plugins")
    _ = gettext.gettext
except:
    _ = lambda s: s



class AlignEqualsAppActivatable(GObject.Object, Gedit.AppActivatable):

    app = GObject.Property(type=Gedit.App)

    def __init__(self):
        GObject.Object.__init__(self)

    def do_activate(self):
        self.app.add_accelerator("<Primary>E", "win.alignequals", None)
        self.app.add_accelerator("<Primary><Shift>E", "win.unalignequals", None)

    def do_deactivate(self):
        self.app.remove_accelerator("win.alignequals", None)
        self.app.remove_accelerator("win.unalignequals", None)



class AlignEqualsWindowActivatable(GObject.Object, Gedit.WindowActivatable):

    window = GObject.Property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)

    def do_activate(self):
        self._add_action("alignequals",   self.do_alignequals)
        self._add_action("unalignequals", self.do_unalignequals)

    def do_deactivate(self):
        self.window.remove_action("alignequals")
        self.window.remove_action("unalignequals")

    def _add_action(self, name, callback):
        action = Gio.SimpleAction(name=name)
        action.connect("activate", callback)
        self.window.add_action(action)


    def do_alignequals(self, _action, _param):
        self._apply()

    def do_unalignequals(self, _action, _param):
        self._apply(undo=True)

    def _apply(self, undo=False):
        view = self.window.get_active_view()
        if view and view.align_equals_view_activatable:
            buf = view.get_buffer()
            view.align_equals_view_activatable._apply(buf, undo=undo)


    def do_update_state(self):
        sensitive = False
        view = self.window.get_active_view()
        if view and hasattr(view, "align_equals_view_activatable"):
            sensitive = view.align_equals_view_activatable.has_equal_sign()

        self.window.lookup_action("alignequals").set_enabled(sensitive)
        self.window.lookup_action("unalignequals").set_enabled(sensitive)



class AlignEqualsViewActivatable(GObject.Object, Gedit.ViewActivatable):

    view = GObject.Property(type=Gedit.View)

    def __init__(self):
        GObject.Object.__init__(self)
        self.popup_handler_id = None

    def do_activate(self):
        self.view.align_equals_view_activatable = self
        self.popup_handler_id = self.view.connect("populate-popup", self.populate_popup)

    def do_deactivate(self):
        if self.popup_handler_id is not None:
            self.view.disconnect(self.popup_handler_id)
            self.popup_handler_id = None
        delattr(self.view, "align_equals_view_activatable")


    def populate_popup(self, view, popup):
        if not isinstance(popup, Gtk.MenuShell):
            return

        item = Gtk.SeparatorMenuItem()
        item.show()
        popup.append(item)

        self._make_popup_item(view, popup, "Align Equals",   self.do_alignequals,   self.has_equal_sign)
        self._make_popup_item(view, popup, "Unalign Equals", self.do_unalignequals, self.has_equal_sign)


    def _make_popup_item(self, view, popup, name, callback, sensitivity_check):
        name = _(name)
        item = Gtk.MenuItem.new_with_mnemonic(name)
        sensitive = sensitivity_check()
        item.set_sensitive(sensitive)
        item.show()
        buf = view.get_buffer()
        item.connect("activate", lambda _i: callback(buf))
        popup.append(item)


    def has_equal_sign(self):
        buf = self.view.get_buffer()
        if not buf:
            return False
        #TODO check what?
        return True


    def do_alignequals(self, buf):
        self._apply(buf)

    def do_unalignequals(self, buf):
        self._apply(buf, undo=True)


    def _apply(self, buf, undo=False):
        sel = self._get_selection_bounds(buf)
        if not sel:
            return

        start, end = sel
        txt = buf.get_text(start, end, True)

        conv = apply_unalignequals if undo else apply_alignequals
        new_txt = conv(txt)

        if new_txt == txt:
            # nothing changed, skip replace step
            return

        sel = self._save_selection(buf, *sel)
        self._replace_text(buf, start, end, new_txt)
        self._restore_selection(buf, *sel)


    def _get_selection_bounds(self, buf):
        sel = buf.get_selection_bounds()
        if not sel:
            return None

        start, end = sel

        if start.ends_line():
            start.forward_line()
        elif not start.starts_line():
            start.set_line_offset(0)

        if end.starts_line():
            end.backward_char()
        elif not end.ends_line():
            end.forward_to_line_end()

        return start, end


    def _save_selection(self, buf, start, end):
        # You must use marks, character numbers, or line numbers to preserve a position across buffer modifications.
        start_mark = buf.create_mark("start", start, True)
        end_mark   = buf.create_mark("end",   end,   False)
        return start_mark, end_mark


    def _restore_selection(self, buf, start_mark, end_mark):
        new_start = buf.get_iter_at_mark(start_mark)
        new_end   = buf.get_iter_at_mark(end_mark)

        buf.select_range(new_start, new_end)

        buf.delete_mark(start_mark)
        buf.delete_mark(end_mark)


    def _replace_text(self, buf, start, end, new_txt):
        buf.begin_user_action()

        buf.delete(start, end)
        buf.insert(start, new_txt)

        buf.end_user_action()





def apply_alignequals(txt):
    lines = txt.split("\n")

    lefts = []
    for line in lines:
        if "=" not in line:
            continue
        left, _right = line.split("=", 1)
        left = left.rstrip()
        lefts.append(left)

    maxlen = max(len(i) for i in lefts)

    new_lines = []
    for line in lines:
        if "=" not in line:
            new_lines.append(line)
            continue
        left, right = line.split("=", 1)
        left = left.rstrip()
        right = right.lstrip()
        new_left = left.ljust(maxlen)
        new_line = new_left + " = " + right
        new_lines.append(new_line)

    new_txt = "\n".join(new_lines)
    return new_txt


def apply_unalignequals(txt):
    lines = txt.split("\n")

    new_lines = []
    for line in lines:
        if "=" not in line:
            new_lines.append(line)
            continue
        left, right = line.split("=", 1)
        left = left.rstrip()
        right = right.lstrip()
        new_line = left + " = " + right
        new_lines.append(new_line)

    new_txt = "\n".join(new_lines)
    return new_txt





#            a   = 1
#            bb  = 2
#            ccc = 3
# ignore
#        x       = 123
#        yy      = 456
# z              = 789



