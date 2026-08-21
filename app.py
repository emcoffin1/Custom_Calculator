#!/usr/bin/env python3
"""On-demand GTK calculator for X11 and Wayland desktops."""
import json
import math
import os
import signal
import fcntl
import re
import sys
from itertools import product
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, GObject, Gtk, Pango
from calculator import evaluate, format_engineering, format_measurement, format_number
from components import preferred_summary
from conversions import CATEGORIES, convert, parse_conversion_input
from engineering import AUTO_UNIT, DISCIPLINES, UNITS, best_unit, calculations_for, description_for, from_base, network_equivalents, nozzle_exit_state, pcb_width, presets_for, rc_filter_response, reference_for, series_rlc_response, standard_atmosphere, to_base as engineering_to_base, validate_inputs, warnings_for, wire_drop, wire_gauge_chart
from features import HistoryEntry, add_history, is_favorite, normalize_state, normalized_precision, search_items, toggle_favorite
from math_editor import MathEditor
from quantities import parse_any_quantity, parse_quantity as parse_engineering_quantity
from unit_math import contains_unit, evaluate_unit_expression

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
DEFAULT_STATE_FILE = os.path.join(CONFIG_HOME, "conversions-calculator", "state.json")
STATE_FILE = os.environ.get("CONVERSIONS_CALCULATOR_STATE", DEFAULT_STATE_FILE)
LEGACY_STATE_FILE = os.path.join(APP_DIR, "state.json")
CUSTOM_LIVE_CALCULATIONS = {"PCB traces", "Wire sizing & voltage drop", "Isentropic flow", "Series / parallel resistance", "Series / parallel capacitance", "Series / parallel inductance", "Series / parallel thermal resistance", "Preferred resistor value", "Preferred capacitor value", "Series RLC impedance", "RC filter response", "Nozzle exit state", "Standard atmosphere"}
ENGINEERING_GROUPS = ("Favorites",) + tuple(DISCIPLINES)
RESERVED_MATH_NAMES = {"pi","e","x","sqrt","cbrt","root","factorial","sin","cos","tan","asin","acos","atan","ln","log","log10","log2","logbase","exp","abs","floor","ceil","degrees","radians","gcd","integral","derivative","summation"}


class ClickOnlyComboBoxText(Gtk.Overlay):
    """Native GTK combo opened on a completed click instead of pointer-down."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self):
        super().__init__()
        self.combo = Gtk.ComboBoxText()
        for renderer in self.combo.get_cells():
            if isinstance(renderer,Gtk.CellRendererText):renderer.set_property("ellipsize",Pango.EllipsizeMode.END);renderer.set_property("max-width-chars",28)
        self.add(self.combo)
        # GTK3's popup otherwise inherits the opening button press and may use
        # that same press's release to activate a row.  The transparent overlay
        # waits for a full click before opening the untouched native combo.
        self.click_surface = Gtk.Button()
        self.click_surface.set_opacity(0)
        self.click_surface.set_can_focus(False)
        self.click_surface.set_tooltip_text("Click to open")
        self.click_surface.connect("clicked", lambda _button: self.combo.popup())
        self.add_overlay(self.click_surface)
        self.combo.connect("changed", lambda _combo: self.emit("changed"))

    def append_text(self, text): self.combo.append_text(text)
    def remove_all(self): self.combo.remove_all()
    def set_active(self, index): self.combo.set_active(index)
    def get_active(self): return self.combo.get_active()
    def get_active_text(self): return self.combo.get_active_text()
    def get_model(self): return self.combo.get_model()
    def popup(self): self.combo.popup()
    def popdown(self): self.combo.popdown()

    def grab_focus(self):
        return self.combo.grab_focus()


def toggle_existing_instance():
    """Return an owned lock, or signal the running instance and return None."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    lock_path = os.path.join(runtime_dir, f"conversions-calculator-{os.getuid()}.lock")
    lock_file = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.seek(0)
        try:
            running_pid = int(lock_file.read().strip())
            os.kill(running_pid, signal.SIGUSR1)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        lock_file.close()
        return None
    lock_file.seek(0); lock_file.truncate(); lock_file.write(str(os.getpid())); lock_file.flush()
    return lock_file

class CalculatorWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Calculator & Converter")
        self.set_default_size(470, 520); self.set_position(Gtk.WindowPosition.CENTER)
        self.set_decorated(False); self.set_resizable(True); self.set_size_request(390, 360)
        self.set_keep_above(True); self.set_accept_focus(True)
        self.set_focus_on_map(True); self.set_skip_taskbar_hint(True); self.set_name("calculator_window")
        self.connect("destroy", self.on_destroy); self.connect("key-press-event", self.on_key_press)
        self.state_data = self.load_state()
        saved_history=self.state_data.get("history",[])
        self.session_features={"history":list(saved_history) if self.state_data.get("save_values",True) and isinstance(saved_history,list) else []}
        saved_variables=self.state_data.get("variables",{})
        self.variables=dict(saved_variables) if self.state_data.get("save_values",True) and isinstance(saved_variables,dict) else {}
        self.result_precision = normalized_precision(self.state_data.get("result_precision", 6))
        self.load_css(); self.build_ui()

    def fmt(self, value):
        return format_number(value, self.result_precision)

    def fmt_measurement(self, value, unit=""):
        return format_measurement(value, unit, self.result_precision)

    def to_base(self,value,dimension,unit):
        return engineering_to_base(value,dimension,unit,self.variables)

    def parse_quantity(self,value,dimension,unit):
        return parse_engineering_quantity(value,dimension,unit,UNITS,self.variables)

    def math_variables(self):
        return {name:(value.get("base_value") if isinstance(value,dict) else value) for name,value in self.variables.items()}

    def load_css(self):
        provider = Gtk.CssProvider(); provider.load_from_path(os.path.join(APP_DIR, "style.css"))
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def build_ui(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10); outer.set_border_width(14); self.add(outer)
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        title = Gtk.Label(label="Calculator"); title.set_xalign(0); title.get_style_context().add_class("window-title")
        title_drag = Gtk.EventBox(); title_drag.set_visible_window(False); title_drag.add(title)
        title_drag.add_events(Gdk.EventMask.BUTTON_PRESS_MASK); title_drag.connect("button-press-event", self.begin_window_move)
        close = Gtk.Button(label="×"); close.set_name("close_button"); close.connect("clicked", lambda _b: self.close())
        self.save_values_switch=Gtk.Switch();self.save_values_switch.set_active(self.state_data.get("save_values",True));self.save_values_switch.set_tooltip_text("Save entered values between launches")
        save_label=Gtk.Label(label="Save values");save_label.get_style_context().add_class("hint")
        title_row.pack_start(title_drag, True, True, 0); title_row.pack_end(close, False, False, 0); outer.pack_start(title_row, False, False, 0)
        self.notebook = Gtk.Notebook(); self.notebook.set_name("main_notebook")
        pages = (
            (self.build_math_calculator(False), "Basic"),
            (self.build_math_calculator(True), "Advanced"),
            (self.build_engineering(), "Engineering"),
            (self.build_converter(), "Convert"),
        )
        for page, label in pages:
            self.notebook.append_page(page, Gtk.Label(label=label))
            self.notebook.child_set_property(page, "tab-expand", True)
            self.notebook.child_set_property(page, "tab-fill", True)
        self.save_values_switch.connect("notify::active",self.save_values_toggled)
        self.restored_tab = self.load_tab()
        self.restoring_tab = False
        self.notebook.connect("switch-page", self.tab_changed)
        outer.pack_start(self.notebook, True, True, 0)
        resize_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        resize_row.pack_start(save_label, False, False, 0); resize_row.pack_start(self.save_values_switch, False, False, 6)
        # Pack the grip at the end first: Gtk.Box's subsequent pack_end calls
        # are inserted to its left, leaving the resize target in the corner.
        resize_grip = Gtk.EventBox(); resize_grip.set_visible_window(False); resize_grip.set_tooltip_text("Drag to resize")
        resize_grip.get_accessible().set_name("Resize window")
        resize_icon = Gtk.Label(label="◢"); resize_icon.get_style_context().add_class("resize-grip"); resize_grip.add(resize_icon)
        resize_grip.add_events(Gdk.EventMask.BUTTON_PRESS_MASK); resize_grip.connect("button-press-event", self.begin_window_resize)
        resize_row.pack_end(resize_grip, False, False, 0)
        search_button = Gtk.Button(label="⌕"); search_button.set_tooltip_text("Find calculation (Ctrl+K)"); search_button.get_style_context().add_class("utility-button")
        search_button.get_accessible().set_name("Find calculation")
        search_button.connect("clicked", self.show_search_popover); resize_row.pack_end(search_button, False, False, 2)
        self.build_search_popover(search_button)
        history_button = Gtk.Button(label="◷"); history_button.set_tooltip_text("Calculation history (Ctrl+H)"); history_button.get_style_context().add_class("utility-button")
        history_button.get_accessible().set_name("Calculation history")
        history_button.connect("clicked", self.show_history_popover); resize_row.pack_end(history_button, False, False, 2)
        self.build_history_popover(history_button)
        utility_button = Gtk.Button(label="⋮"); utility_button.set_tooltip_text("Result precision")
        utility_button.get_accessible().set_name("Result precision")
        utility_button.get_style_context().add_class("utility-button"); utility_button.connect("clicked", self.show_precision_popover)
        resize_row.pack_end(utility_button, False, False, 3)
        self.precision_popover = Gtk.Popover.new(utility_button); self.precision_popover.set_no_show_all(True)
        precision_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7); precision_box.set_border_width(10)
        precision_label = Gtk.Label(label="Result precision"); precision_label.set_xalign(0); precision_label.get_style_context().add_class("field-label")
        self.precision_spin = Gtk.SpinButton.new_with_range(3, 10, 1); self.precision_spin.set_value(self.result_precision)
        self.precision_spin.set_tooltip_text("Significant digits shown in results"); self.precision_spin.connect("value-changed", self.precision_changed)
        self.variable_summary=Gtk.Label();self.variable_summary.set_xalign(0);self.variable_summary.set_line_wrap(True);self.variable_summary.set_max_width_chars(30);self.variable_summary.get_style_context().add_class("hint")
        clear_variables=Gtk.Button(label="Clear variables");clear_variables.connect("clicked",self.clear_variables)
        precision_box.pack_start(precision_label, False, False, 0); precision_box.pack_start(self.precision_spin, False, False, 0);precision_box.pack_start(self.variable_summary,False,False,4);precision_box.pack_start(clear_variables,False,False,0)
        self.precision_popover.add(precision_box); precision_box.show_all()
        outer.pack_end(resize_row, False, False, 0)

    def build_search_popover(self, button):
        self.search_popover = Gtk.Popover.new(button); self.search_popover.set_no_show_all(True); self.search_popover.set_position(Gtk.PositionType.TOP)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); box.set_border_width(8)
        self.command_search = Gtk.SearchEntry(); self.command_search.set_placeholder_text("Find a calculation…"); self.command_search.set_width_chars(34)
        self.command_search.connect("search-changed", self.update_command_results); self.command_search.connect("activate", self.activate_first_command);self.command_search.connect("key-press-event",self.command_search_key)
        self.command_results = Gtk.ListBox(); self.command_results.set_selection_mode(Gtk.SelectionMode.SINGLE); self.command_results.connect("row-activated", self.command_row_activated)
        box.pack_start(self.command_search, False, False, 0); box.pack_start(self.command_results, False, False, 0)
        self.search_popover.add(box); box.show_all()

    def build_history_popover(self, button):
        self.history_popover = Gtk.Popover.new(button); self.history_popover.set_no_show_all(True); self.history_popover.set_position(Gtk.PositionType.TOP)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); box.set_border_width(8)
        title = Gtk.Label(label="Recent calculations"); title.set_xalign(0); title.get_style_context().add_class("field-label")
        self.history_list = Gtk.ListBox(); self.history_list.set_selection_mode(Gtk.SelectionMode.NONE); self.history_list.connect("row-activated", self.history_row_activated)
        clear=Gtk.Button(label="Clear history");clear.get_style_context().add_class("compact-button");clear.connect("clicked",self.clear_history)
        box.pack_start(title, False, False, 0); box.pack_start(self.history_list, False, False, 0);box.pack_start(clear,False,False,2); self.history_popover.add(box); box.show_all()

    def command_catalog(self):
        items = [
            {"key":"tab|basic", "label":"Basic calculator", "detail":"Calculator", "action":("tab",0)},
            {"key":"tab|advanced", "label":"Advanced calculator", "detail":"Calculus, integral, derivative", "action":("tab",1)},
        ]
        for discipline in DISCIPLINES:
            for calculation in calculations_for(discipline):
                key=f"{discipline}|{calculation.name}"
                input_terms=" ".join(f"{spec.label} {spec.dimension} {' '.join(UNITS.get(spec.dimension,{}))}" for spec in calculation.inputs)
                items.append({"key":key,"label":calculation.name,"detail":discipline,"keywords":" ".join((description_for(calculation),calculation.formula,calculation.note,input_terms)),"action":("engineering",discipline,calculation.name)})
        for category in CATEGORIES:
            items.append({"key":f"convert|{category}","label":f"Convert {category}","detail":"Unit conversion","action":("conversion",category)})
        for index,item in enumerate(self.session_features["history"][:20]):
            items.append({"key":f"history|{index}","label":str(item.get("title","Recent calculation")),"detail":"Recent · "+str(item.get("result","")),"keywords":str(item.get("result","")),"action":("history",item)})
        return items

    def show_search_popover(self, _button=None):
        self.command_search.set_text(""); self.update_command_results(); self.search_popover.popup(); GLib.idle_add(self.command_search.grab_focus)

    def update_command_results(self, *_args):
        for child in self.command_results.get_children(): self.command_results.remove(child)
        favorites=self.state_data.get("favorites",[]); matches=search_items(self.command_catalog(),self.command_search.get_text(),favorites)[:8]
        for item in matches:
            row=Gtk.ListBoxRow(); row.command=item
            content=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8); label=Gtk.Label(label=("★ " if item["key"] in favorites else "")+item["label"]);label.set_xalign(0)
            detail=Gtk.Label(label=item["detail"]);detail.set_xalign(1);detail.get_style_context().add_class("hint")
            content.pack_start(label,True,True,0);content.pack_end(detail,False,False,0);row.add(content);self.command_results.add(row)
        self.command_results.show_all()

    def activate_first_command(self, _entry):
        row=self.command_results.get_selected_row();rows=self.command_results.get_children()
        if row or rows:self.activate_command((row or rows[0]).command)

    def command_search_key(self,_entry,event):
        rows=self.command_results.get_children()
        if event.keyval==Gdk.KEY_Escape:self.search_popover.popdown();return True
        if event.keyval not in (Gdk.KEY_Down,Gdk.KEY_Up) or not rows:return False
        selected=self.command_results.get_selected_row();index=rows.index(selected) if selected in rows else (-1 if event.keyval==Gdk.KEY_Down else 0)
        index=(index+(1 if event.keyval==Gdk.KEY_Down else -1))%len(rows);self.command_results.select_row(rows[index]);return True

    def command_row_activated(self, _listbox, row): self.activate_command(row.command)

    def activate_command(self, item):
        action=item["action"]
        if action[0]=="tab": self.notebook.set_current_page(action[1])
        elif action[0]=="engineering":
            self.notebook.set_current_page(2); discipline,name=action[1],action[2]; self.engineering_discipline.set_active(ENGINEERING_GROUPS.index(discipline))
            names=[calculation.name for calculation in calculations_for(discipline)]
            if name in names:self.engineering_calculation.set_active(names.index(name))
        elif action[0]=="conversion":
            self.notebook.set_current_page(3); names=list(CATEGORIES); self.category.set_active(names.index(action[1]))
        elif action[0]=="history":self.restore_history_item(action[1])
        self.search_popover.popdown(); GLib.idle_add(self.focus_page_input,self.notebook.get_current_page())

    def show_history_popover(self, _button=None):
        for child in self.history_list.get_children(): self.history_list.remove(child)
        history=self.session_features["history"]
        for item in history[:8]:
            row=Gtk.ListBoxRow();row.history_item=item
            row.add_events(Gdk.EventMask.BUTTON_PRESS_MASK);row.connect("button-press-event",self.history_context_requested)
            content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=1);title=Gtk.Label(label=("📌 " if item.get("pinned") else "")+str(item.get("title","")));title.set_xalign(0);title.set_ellipsize(3)
            result=Gtk.Label(label=str(item.get("result","")));result.set_xalign(0);result.get_style_context().add_class("hint")
            content.pack_start(title,False,False,0);content.pack_start(result,False,False,0);row.add(content);self.history_list.add(row)
        if not history:
            empty=Gtk.Label(label="No calculations yet");empty.get_style_context().add_class("hint");self.history_list.add(empty)
        self.history_list.show_all();self.history_popover.popup()

    def history_row_activated(self, _listbox, row):
        item=getattr(row,"history_item",None)
        if not item:return
        self.restore_history_item(item);self.history_popover.popdown()

    def clear_history(self,_button=None):
        self.session_features["history"].clear();self.save_tab();self.show_history_popover()

    def history_context_requested(self,row,event):
        if event.button!=3:return False
        item=row.history_item;popover=Gtk.Popover.new(row);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=2);box.set_border_width(5)
        pin=Gtk.Button(label="Unpin" if item.get("pinned") else "Pin");pin.connect("clicked",self.toggle_history_pin,item,popover);box.pack_start(pin,False,False,0)
        copy=Gtk.Button(label="Copy result");copy.connect("clicked",lambda _b:(Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(str(item.get("result","")),-1),popover.popdown()));box.pack_start(copy,False,False,0)
        delete=Gtk.Button(label="Delete");delete.connect("clicked",self.delete_history_item,item,popover);box.pack_start(delete,False,False,0)
        popover.add(box);box.show_all();popover.popup();self._history_action_popover=popover;return True

    def toggle_history_pin(self,_button,item,popover):
        item["pinned"]=not item.get("pinned",False);self.session_features["history"].sort(key=lambda entry:not entry.get("pinned",False));self.save_tab();popover.popdown();self.show_history_popover()

    def delete_history_item(self,_button,item,popover):
        if item in self.session_features["history"]:self.session_features["history"].remove(item)
        self.save_tab();popover.popdown();self.show_history_popover()

    def restore_history_item(self,item):
        kind=item.get("kind");expression=item.get("payload",{}).get("expression","")
        if kind in ("basic","advanced"):
            page=0 if kind=="basic" else 1;editor=self.basic_expression if page==0 else self.advanced_expression
            self.notebook.set_current_page(page);editor.set_text(expression);editor.grab_focus()
        elif kind=="engineering":
            payload=item.get("payload",{});discipline=payload.get("discipline");name=payload.get("calculation")
            if discipline in DISCIPLINES:
                self.notebook.set_current_page(2);self.engineering_discipline.set_active(ENGINEERING_GROUPS.index(discipline));names=[c.name for c in calculations_for(discipline)]
                if name in names:self.engineering_calculation.set_active(names.index(name))
                for key,saved in payload.get("fields",{}).items():
                    if key in self.engineering_fields:
                        entry,unit,_spec=self.engineering_fields[key];entry.set_text(str(saved.get("value","")));units=[unit.get_model()[i][0] for i in range(len(unit.get_model()))]
                        if saved.get("unit") in units:unit.set_active(units.index(saved["unit"]))
                output_units=[self.engineering_output_unit.get_model()[i][0] for i in range(len(self.engineering_output_unit.get_model()))]
                if payload.get("output_unit") in output_units:self.engineering_output_unit.set_active(output_units.index(payload["output_unit"]))
                self.calculate_engineering()
        elif kind=="conversion":
            payload=item.get("payload",{});category=payload.get("category");names=list(CATEGORIES)
            if category in names:
                self.notebook.set_current_page(3);self.category.set_active(names.index(category));units=list(CATEGORIES[category])
                if payload.get("from_unit") in units:self.from_unit.set_active(units.index(payload["from_unit"]))
                if payload.get("to_unit") in units:self.to_unit.set_active(units.index(payload["to_unit"]))
                self.from_value.set_text(str(payload.get("value","")));self.update_conversion()

    def show_precision_popover(self, _button):
        items=[]
        for name,value in sorted(self.variables.items()):items.append(f"{name} = {value.get('text',value.get('base_value')) if isinstance(value,dict) else self.fmt(value)}")
        self.variable_summary.set_text("Variables\n"+("\n".join(items) if items else "None"))
        self.precision_popover.popup()

    def clear_variables(self,_button):
        self.variables.clear();self.variable_summary.set_text("Variables\nNone");self.save_tab()

    def precision_changed(self, spin):
        self.result_precision = normalized_precision(spin.get_value_as_int())
        self.state_data["result_precision"] = self.result_precision
        self.save_tab()
        self.refresh_current_result()

    def refresh_current_result(self):
        page = self.notebook.get_current_page() if hasattr(self, "notebook") else -1
        if page == 0: self.calculate_math(self.basic_expression, self.basic_result, record=False)
        elif page == 1: self.calculate_math(self.advanced_expression, self.advanced_result, record=False)
        elif page == 2 and getattr(self, "current_engineering_calculation",None): self.calculate_engineering()
        elif page == 3: self.update_conversion()

    def copy_result(self, _widget, event, label):
        if event.button == 3:
            self.show_result_actions(_widget,label);return True
        if event.button != 1: return False
        text = label.get_text().strip()
        if text and text not in ("—", "0") and not text.startswith("Error:"):
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
        return True

    def copyable(self, label):
        event_box = Gtk.EventBox(); event_box.set_visible_window(False); event_box.set_tooltip_text("Click to copy · right-click for options")
        event_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK); event_box.connect("button-press-event", self.copy_result, label); event_box.add(label)
        return event_box

    def show_result_actions(self,event_box,label):
        popover=Gtk.Popover.new(event_box);popover.set_no_show_all(True)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=2);box.set_border_width(5)
        number=self.first_number(label.get_text());numeric=float(number) if number!=label.get_text() or re.fullmatch(r"[-+0-9.eE]+",number) else None
        actions=[("Copy result",label.get_text()),("Copy number",number)]
        if numeric is not None:actions.extend((("Copy scientific",f"{numeric:.{self.result_precision}e}"),("Copy engineering",format_engineering(numeric,self.result_precision))))
        actions.append(("Copy calculation",self.current_calculation_report()))
        for caption,text in actions:
            button=Gtk.Button(label=caption);button.set_relief(Gtk.ReliefStyle.NONE);button.connect("clicked",lambda _b,value=text,p=popover:(Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(value,-1),p.popdown()));box.pack_start(button,False,False,0)
        if numeric is not None:
            for caption,page in (("Use in Basic",0),("Use in Advanced",1)):
                button=Gtk.Button(label=caption);button.set_relief(Gtk.ReliefStyle.NONE);button.connect("clicked",self.use_result_in_math,number,page,popover);box.pack_start(button,False,False,0)
            store=Gtk.Button(label="Store as ans");store.set_relief(Gtk.ReliefStyle.NONE);store.connect("clicked",self.store_result_as_ans,number,popover);box.pack_start(store,False,False,0)
        popover.add(box);box.show_all();popover.popup();self._result_actions_popover=popover

    def use_result_in_math(self,_button,number,page,popover):
        editor=self.basic_expression if page==0 else self.advanced_expression
        editor.set_text(number);self.notebook.set_current_page(page);popover.popdown();GLib.idle_add(editor.grab_focus)

    def store_result_as_ans(self,_button,number,popover):
        self.variables["ans"]=float(number)
        self.save_tab();popover.popdown()

    @staticmethod
    def first_number(text):
        match=re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?",text)
        return match.group(0) if match else text

    def current_calculation_report(self):
        page=self.notebook.get_current_page()
        if page in (0,1):
            editor=self.basic_expression if page==0 else self.advanced_expression;result=self.basic_result if page==0 else self.advanced_result
            return f"{'Basic' if page==0 else 'Advanced'} calculator\nExpression: {editor.get_text()}\nResult: {result.get_text()}"
        if page==2 and hasattr(self,"current_engineering_calculation"):
            calculation=self.current_engineering_calculation;lines=[f"{calculation.discipline} — {calculation.name}",f"Equation: {calculation.formula}"]
            for _key,(entry,unit,spec) in self.engineering_fields.items():lines.append(f"{spec.label}: {entry.get_text()} {unit.get_active_text()}".rstrip())
            lines.append(self.engineering_result.get_text())
            if calculation.note:lines.append(f"Note: {calculation.note}")
            if reference_for(calculation):lines.append(f"Reference: {reference_for(calculation)}")
            if self.engineering_warning.get_text():lines.append(self.engineering_warning.get_text())
            return "\n".join(lines)
        return f"Convert {self.category.get_active_text()}\n{self.from_value.get_text()} {self.from_unit.get_active_text()}\nResult: {self.conversion_result.get_text()}"

    def begin_window_move(self, _widget, event):
        if event.button == 1:
            self.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)
            return True
        return False

    def begin_window_resize(self, _widget, event):
        if event.button == 1:
            self.begin_resize_drag(Gdk.WindowEdge.SOUTH_EAST, event.button, int(event.x_root), int(event.y_root), event.time)
            return True
        return False

    def build_math_calculator(self, calculus):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); box.set_border_width(12)
        expression_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        editor = MathEditor(); result = Gtk.Label(label="0")
        if calculus: self.advanced_expression, self.advanced_result = editor, result
        else: self.basic_expression, self.basic_result = editor, result
        expression_key = "advanced_expression" if calculus else "basic_expression"
        if self.save_values_switch.get_active() and self.state_data.get(expression_key): editor.set_text(self.state_data[expression_key])
        editor.connect_activate(lambda *_args: self.calculate_math(editor, result))
        expression_row.pack_start(editor, True, True, 0)
        left = Gtk.Button(label="←"); left.set_tooltip_text("Previous value box"); left.connect("clicked", lambda _button: editor.move_slot(-1))
        right = Gtk.Button(label="→"); right.set_tooltip_text("Next value box"); right.connect("clicked", lambda _button: editor.move_slot(1))
        undo = Gtk.Button(label="↶"); undo.set_tooltip_text("Undo (Ctrl+Z)"); undo.connect("clicked", lambda _button: editor.undo())
        expression_row.pack_start(undo, False, False, 0); expression_row.pack_start(left, False, False, 0); expression_row.pack_start(right, False, False, 0)
        box.pack_start(expression_row, False, False, 0)
        result.set_xalign(1); result.set_selectable(True); result.set_ellipsize(3); result.get_style_context().add_class("result"); box.pack_start(self.copyable(result), False, False, 0)
        hint = Gtk.Label(label="Hover for shortcuts · Ctrl+Z undoes · name=value stores a variable · trig uses radians")
        hint.set_xalign(0); hint.get_style_context().add_class("hint"); box.pack_start(hint, False, False, 0)
        grid = Gtk.Grid(column_spacing=5, row_spacing=5, column_homogeneous=True, row_homogeneous=True)
        keys = [
            [("sin", r"\sin(#0)"), ("cos", r"\cos(#0)"), ("tan", r"\tan(#0)"), ("π", r"\pi"), ("e", "e")],
            [("sin⁻¹", r"\arcsin(#0)"), ("cos⁻¹", r"\arccos(#0)"), ("tan⁻¹", r"\arctan(#0)"), ("ln", r"\ln(#0)"), ("log", r"\log(#0)")],
            [("√", r"\sqrt{#0}"), ("∛", r"\sqrt[3]{#0}"), ("ⁿ√", r"\sqrt[#0]{#1}"), ("a/b", r"\frac{#0}{#1}"), ("xʸ", r"^{#0}")],
            [("7", "7"), ("8", "8"), ("9", "9"), ("(", "("), (")", ")")],
            [("4", "4"), ("5", "5"), ("6", "6"), ("×", "*"), ("÷", "/")],
            [("1", "1"), ("2", "2"), ("3", "3"), ("+", "+"), ("−", "-")],
            [("0", "0"), (".", "."), ("x!", r"\operatorname{factorial}(#0)"), ("C", "C"), ("=", "=")],
        ]
        if calculus:
            keys.insert(3, [("∫", r"\int_{#1}^{#2}#0\,\mathrm{d}x"), ("d/dx", r"\left.\frac{\mathrm{d}}{\mathrm{d}x}#0\right|_{x=#1}"), ("Σ", r"\sum_{x=#1}^{#2}#0"), ("|x|", r"\left|#0\right|"), ("logₙ", r"\log_{#0}(#1)")])
        for row, buttons in enumerate(keys):
            for col, (label, token) in enumerate(buttons):
                button = Gtk.Button(label=label)
                if token in ("*", "/", "+", "-", "^", "="): button.get_style_context().add_class("operator")
                shortcuts = {"√":"sqrt", "∛":"cbrt", "ⁿ√":"root", "a/b":"frac", "x!":"fact", "∫":"integral(expression, lower, upper)", "d/dx":"derivative(expression, x-value)", "Σ":"sum(expression, start, end)", "|x|":"abs", "logₙ":"log base"}
                if label in shortcuts: button.set_tooltip_text("Type: " + shortcuts[label])
                button.connect("clicked", self.math_button_pressed, editor, result, token); grid.attach(button, col, row, 1, 1)
        box.pack_start(grid, True, True, 0); return box

    def build_engineering(self):
        scroll = Gtk.ScrolledWindow(); scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); box.set_border_width(12); scroll.add(box)
        selectors = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5);selector_top=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8)
        self.engineering_discipline = ClickOnlyComboBoxText(); self.engineering_calculation = ClickOnlyComboBoxText()
        for name in ENGINEERING_GROUPS: self.engineering_discipline.append_text(name)
        self.engineering_info_button=Gtk.ToggleButton(label="ⓘ");self.engineering_info_button.set_tooltip_text("Show equation and description");self.engineering_info_button.connect("toggled",self.toggle_engineering_info)
        self.engineering_favorite_button=Gtk.ToggleButton(label="☆");self.engineering_favorite_button.set_tooltip_text("Favorite this calculation");self.engineering_favorite_button.connect("toggled",self.toggle_engineering_favorite)
        selector_top.pack_start(self.engineering_discipline,True,True,0);selector_top.pack_end(self.engineering_info_button,False,False,0);selector_top.pack_end(self.engineering_favorite_button,False,False,0)
        selectors.pack_start(selector_top,False,False,0);selectors.pack_start(self.engineering_calculation,False,False,0);box.pack_start(selectors,False,False,0)
        self.engineering_preset_row=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8);preset_label=Gtk.Label(label="Preset");preset_label.set_xalign(0);preset_label.get_style_context().add_class("field-label")
        self.engineering_preset=ClickOnlyComboBoxText();self.engineering_preset.connect("changed",self.apply_engineering_preset);self.engineering_preset_row.pack_start(preset_label,False,False,0);self.engineering_preset_row.pack_start(self.engineering_preset,True,True,0);box.pack_start(self.engineering_preset_row,False,False,0)
        self.engineering_info=Gtk.Revealer();self.engineering_info.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN);self.engineering_info.set_transition_duration(150)
        info_box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);info_box.set_name("engineering_info")
        self.engineering_formula = Gtk.Label(); self.engineering_formula.set_xalign(0);self.engineering_formula.set_line_wrap(True);self.engineering_formula.set_max_width_chars(48); self.engineering_formula.get_style_context().add_class("engineering-formula");info_box.pack_start(self.engineering_formula,False,False,0)
        self.engineering_description=Gtk.Label();self.engineering_description.set_xalign(0);self.engineering_description.set_line_wrap(True);self.engineering_description.set_max_width_chars(48);self.engineering_description.get_style_context().add_class("engineering-description");info_box.pack_start(self.engineering_description,False,False,0)
        self.engineering_note = Gtk.Label(); self.engineering_note.set_xalign(0); self.engineering_note.set_line_wrap(True);self.engineering_note.set_max_width_chars(48); self.engineering_note.get_style_context().add_class("hint");info_box.pack_start(self.engineering_note,False,False,0)
        self.engineering_reference=Gtk.Label();self.engineering_reference.set_xalign(0);self.engineering_reference.set_line_wrap(True);self.engineering_reference.get_style_context().add_class("reference");info_box.pack_start(self.engineering_reference,False,False,0)
        self.engineering_info.add(info_box);box.pack_start(self.engineering_info,False,False,0)
        self.engineering_inputs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); box.pack_start(self.engineering_inputs_box, False, False, 0)
        output_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.engineering_result = Gtk.Label(label="Result: —"); self.engineering_result.set_xalign(0); self.engineering_result.set_selectable(True);self.engineering_result.set_line_wrap(True);self.engineering_result.set_max_width_chars(44); self.engineering_result.get_style_context().add_class("engineering-result")
        self.engineering_output_unit = ClickOnlyComboBoxText(); output_row.pack_start(self.copyable(self.engineering_result), True, True, 0); output_row.pack_end(self.engineering_output_unit, False, False, 0); box.pack_start(output_row, False, False, 4)
        self.engineering_warning=Gtk.Label();self.engineering_warning.set_xalign(0);self.engineering_warning.set_line_wrap(True);self.engineering_warning.get_style_context().add_class("engineering-warning");box.pack_start(self.engineering_warning,False,False,0)
        self.engineering_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8); box.pack_start(self.engineering_actions, False, False, 0)
        self.engineering_fields = {}; self.restoring_engineering = True
        saved_discipline = self.state_data.get("engineering_discipline")
        initial=saved_discipline if saved_discipline in ENGINEERING_GROUPS else ("Favorites" if self.favorite_calculations() else DISCIPLINES[0])
        if initial=="Favorites" and not self.favorite_calculations():initial=DISCIPLINES[0]
        self.engineering_discipline.set_active(ENGINEERING_GROUPS.index(initial))
        self.engineering_discipline.connect("changed", self.engineering_discipline_changed)
        self.engineering_calculation.connect("changed", self.engineering_calculation_changed)
        self.engineering_output_unit.connect("changed", self.engineering_output_unit_changed)
        self.engineering_discipline_changed(self.engineering_discipline, restore=True)
        self.restoring_engineering = False
        return scroll

    def engineering_discipline_changed(self, _combo, restore=False):
        discipline = self.engineering_discipline.get_active_text()
        calculations = self.engineering_choices(discipline); self.engineering_calculation.remove_all()
        if not calculations:
            self.engineering_calculation.append_text("No favorites yet");self.engineering_calculation.set_active(0);self.current_engineering_calculation=None
            self.engineering_favorite_button.set_sensitive(False)
            for container in (self.engineering_inputs_box,self.engineering_actions):
                for child in container.get_children():container.remove(child)
            self.engineering_fields={};self.engineering_formula.set_text("");self.engineering_description.set_text("Favorite a calculation with ☆ or Ctrl+D.");self.engineering_note.set_text("");self.engineering_reference.set_text("");self.set_engineering_result("Result: —","neutral");return
        for calculation in calculations: self.engineering_calculation.append_text(calculation.name)
        saved = self.state_data.get("engineering_calculation") if restore else None
        if saved in ("Series resistance", "Parallel resistance"):
            saved = "Series / parallel resistance"
        names = [calculation.name for calculation in calculations]
        self.engineering_calculation.set_active(names.index(saved) if saved in names else 0)
        self.engineering_calculation_changed(self.engineering_calculation, restore=restore)
        self.engineering_state_changed()

    def engineering_calculation_changed(self, _combo, restore=False):
        discipline = self.engineering_discipline.get_active_text(); name = self.engineering_calculation.get_active_text()
        matches = [item for item in self.engineering_choices(discipline) if item.name == name]
        if not matches: return
        self.current_engineering_calculation = matches[0]
        self.engineering_favorite_button.set_sensitive(True)
        favorite_key = f"{discipline}|{name}"
        self.engineering_favorite_button.handler_block_by_func(self.toggle_engineering_favorite)
        self.engineering_favorite_button.set_active(is_favorite(self.state_data, favorite_key)); self.engineering_favorite_button.set_label("★" if self.engineering_favorite_button.get_active() else "☆")
        self.engineering_favorite_button.handler_unblock_by_func(self.toggle_engineering_favorite)
        self.restoring_preset=True;self.engineering_preset.remove_all();preset_names=list(presets_for(self.current_engineering_calculation))
        if preset_names:self.engineering_preset.append_text("Choose preset…")
        for preset_name in preset_names:self.engineering_preset.append_text(preset_name)
        self.engineering_preset_row.set_visible(bool(preset_names));self.engineering_preset.set_active(0 if preset_names else -1);self.restoring_preset=False
        for child in self.engineering_inputs_box.get_children(): self.engineering_inputs_box.remove(child)
        self.engineering_fields = {}; saved_all = self.state_data.get("engineering_values", {})
        saved = saved_all.get(f"{self.current_engineering_calculation.discipline}|{name}", {}) if isinstance(saved_all, dict) else {}
        if name=="Series / parallel resistance" and "values" not in saved and ("r1" in saved or "r2" in saved):
            old=[saved[key].get("value","") for key in ("r1","r2") if isinstance(saved.get(key),dict) and saved[key].get("value","")]
            old_unit=next((saved[key].get("unit") for key in ("r1","r2") if isinstance(saved.get(key),dict) and saved[key].get("unit")),"Ω");saved=dict(saved);saved["values"]={"value":", ".join(old),"unit":old_unit}
        for spec in self.current_engineering_calculation.inputs:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8); label = Gtk.Label(label=spec.label); label.set_xalign(0);label.set_ellipsize(3);label.set_max_width_chars(24);label.set_tooltip_text(spec.label); row.pack_start(label, True, True, 0)
            entry = Gtk.Entry(); entry.set_width_chars(12); entry.set_placeholder_text("Value"); saved_value=saved.get(spec.key, {}).get("value",spec.default) if self.save_values_switch.get_active() else spec.default;entry.set_text(str(saved_value))
            label.set_mnemonic_widget(entry);entry.get_accessible().set_name(spec.label)
            unit = ClickOnlyComboBoxText(); unit_names = list(UNITS[spec.dimension])
            for unit_name in unit_names: unit.append_text(unit_name)
            saved_unit = saved.get(spec.key, {}).get("unit"); preferred_unit = saved_unit if saved_unit in unit_names else spec.default_unit
            unit.set_active(unit_names.index(preferred_unit) if preferred_unit in unit_names else 0)
            if spec.dimension=="series":entry.set_no_show_all(True);entry.hide()
            entry.connect("changed", self.engineering_input_changed); entry.connect("activate", self.calculate_engineering); entry.connect("focus-out-event",self.engineering_typed_unit); unit.connect("changed", self.engineering_input_changed)
            row.pack_start(entry, False, False, 0); row.pack_start(unit, False, False, 0); self.engineering_inputs_box.pack_start(row, False, False, 0)
            self.engineering_fields[spec.key] = (entry, unit, spec)
        self.engineering_formula.set_text(self.current_engineering_calculation.formula)
        self.engineering_description.set_text(description_for(self.current_engineering_calculation))
        self.engineering_note.set_text(self.current_engineering_calculation.note)
        self.engineering_reference.set_text(("Reference: "+reference_for(self.current_engineering_calculation)) if reference_for(self.current_engineering_calculation) else "")
        self.engineering_info_button.set_tooltip_text(f"Equation: {self.current_engineering_calculation.formula}")
        self.engineering_output_unit.remove_all(); output_units = list(UNITS[self.current_engineering_calculation.output_dimension])
        if self.current_engineering_calculation.output_dimension!="none":output_units.insert(0,AUTO_UNIT)
        for unit_name in output_units: self.engineering_output_unit.append_text(unit_name)
        saved_output = saved.get("_output_unit");default_index=1 if AUTO_UNIT in output_units else 0;self.engineering_output_unit.set_active(output_units.index(saved_output) if saved_output in output_units else default_index)
        self.engineering_output_unit.set_visible(not bool(self.current_engineering_calculation.solvers) and self.current_engineering_calculation.output_dimension != "none")
        self.set_engineering_result("Result: —", "neutral"); self.engineering_inputs_box.show_all(); self.engineering_state_changed()
        for child in self.engineering_actions.get_children(): self.engineering_actions.remove(child)
        custom_live = self.current_engineering_calculation.name in CUSTOM_LIVE_CALCULATIONS
        actions = () if self.current_engineering_calculation.solvers or custom_live else (self.current_engineering_calculation.actions or (("Calculate", self.current_engineering_calculation.compute),))
        for label, compute in actions:
            button = Gtk.Button(label=label); button.get_style_context().add_class("operator")
            button.connect("clicked", self.calculate_engineering, compute); self.engineering_actions.pack_start(button, True, True, 0)
        if self.current_engineering_calculation.name == "Wire sizing & voltage drop":
            chart=Gtk.Button(label="AWG chart");chart.set_tooltip_text("Wire gauge reference and copper resistance at 20 °C")
            chart.connect("clicked",self.show_wire_gauge_chart);self.engineering_actions.pack_start(chart,True,True,0)
        self.engineering_actions.show_all()
        if self.current_engineering_calculation.solvers or custom_live: self.calculate_engineering()

    def apply_engineering_preset(self,_combo):
        if getattr(self,"restoring_preset",False) or not hasattr(self,"current_engineering_calculation"):return
        preset=presets_for(self.current_engineering_calculation).get(self.engineering_preset.get_active_text(),{})
        for key,(value,unit_name) in preset.items():
            if key not in self.engineering_fields:continue
            entry,unit,_spec=self.engineering_fields[key];entry.set_text(value);units=[unit.get_model()[i][0] for i in range(len(unit.get_model()))]
            if unit_name in units:unit.set_active(units.index(unit_name))

    def calculate_engineering(self, _widget=None, compute=None):
        try:
            self.engineering_warning.set_text("")
            for entry,_unit,_spec in self.engineering_fields.values():
                entry.get_style_context().remove_class("invalid-entry");entry.set_tooltip_text(None)
            calculation = self.current_engineering_calculation
            if calculation.name in ("Series / parallel resistance","Series / parallel capacitance","Series / parallel inductance","Series / parallel thermal resistance"):
                entry,unit_widget,spec=self.engineering_fields["values"];parts=[part.strip() for part in re.split(r"[,;\n]+",entry.get_text()) if part.strip()]
                if len(parts)<2:self.set_engineering_result("Enter at least two values", "neutral");return
                values=[self.parse_quantity(part,spec.dimension,unit_widget.get_active_text()).base_value for part in parts]
                unit=unit_widget.get_active_text();dimension=spec.dimension;series,parallel=network_equivalents(values,dimension=="capacitance")
                self.set_engineering_result(f"Series: {self.fmt_measurement(from_base(series,dimension,unit), unit)} {unit}\nParallel: {self.fmt_measurement(from_base(parallel,dimension,unit), unit)} {unit}","live");return
            if calculation.name in ("Preferred resistor value","Preferred capacitor value"):
                target_entry,target_unit,target_spec=self.engineering_fields["target"];series_name=self.engineering_fields["series"][1].get_active_text()
                if not target_entry.get_text().strip():self.set_engineering_result("Enter a target value","neutral");return
                target=self.parse_quantity(target_entry.get_text(),target_spec.dimension,target_unit.get_active_text());summary=preferred_summary(target.base_value,series_name)
                output_unit=self.engineering_output_unit.get_active_text();output_unit=best_unit(summary["nearest"],target_spec.dimension) if output_unit==AUTO_UNIT else output_unit
                shown={key:from_base(value,target_spec.dimension,output_unit) for key,value in summary.items() if key!="error_percent"}
                self.set_engineering_result(f"Lower: {self.fmt_measurement(shown['lower'],output_unit)} {output_unit}\nNearest: {self.fmt_measurement(shown['nearest'],output_unit)} {output_unit}  ({self.fmt_measurement(summary['error_percent'],'%')}%)\nHigher: {self.fmt_measurement(shown['higher'],output_unit)} {output_unit}","live");return
            if calculation.name=="Series RLC impedance":
                values={key:self.to_base(entry.get_text(),spec.dimension,unit.get_active_text()) for key,(entry,unit,spec) in self.engineering_fields.items() if entry.get_text().strip()}
                if len(values)!=4:raise ValueError("Fill every impedance input")
                response=series_rlc_response(values["resistance"],values["inductance"],values["capacitance"],values["frequency"]);reactance=response["reactance"]
                sign="+" if reactance>=0 else "−";self.set_engineering_result(f"Z: {self.fmt_measurement(response['resistance'],'Ω')} {sign} j{self.fmt_measurement(abs(reactance),'Ω')} Ω\nMagnitude: {self.fmt_measurement(response['magnitude'],'Ω')} Ω\nPhase: {self.fmt_measurement(response['phase_deg'])}°","live");return
            if calculation.name=="RC filter response":
                values={key:self.to_base(entry.get_text(),spec.dimension,unit.get_active_text()) for key,(entry,unit,spec) in self.engineering_fields.items() if entry.get_text().strip()}
                if len(values)!=3:raise ValueError("Fill every filter input")
                response=rc_filter_response(values["resistance"],values["capacitance"],values["frequency"]);low=response["low_gain"];high=response["high_gain"]
                self.set_engineering_result(f"Cutoff: {self.fmt_measurement(response['cutoff'],'Hz')} Hz\nLow-pass: {self.fmt_measurement(low)}  ({self.fmt_measurement(20*math.log10(low))} dB), phase {self.fmt_measurement(response['low_phase'])}°\nHigh-pass: {self.fmt_measurement(high)}  ({self.fmt_measurement(20*math.log10(high))} dB), phase {self.fmt_measurement(response['high_phase'])}°","live");return
            if calculation.name=="Nozzle exit state":
                values={key:self.to_base(entry.get_text(),spec.dimension,unit.get_active_text()) for key,(entry,unit,spec) in self.engineering_fields.items() if entry.get_text().strip()}
                if len(values)!=5:raise ValueError("Fill every nozzle input")
                state=nozzle_exit_state(values["total_pressure"],values["total_temperature"],values["exit_pressure"],values["gamma"],values["gas_constant"])
                self.set_engineering_result(f"Exit Mach: {self.fmt_measurement(state['mach'])}\nExit temperature: {self.fmt_measurement(state['temperature'],'K')} K\nSpeed of sound: {self.fmt_measurement(state['sound_speed'],'m/s')} m/s\nExit velocity: {self.fmt_measurement(state['velocity'],'m/s')} m/s","live");return
            if calculation.name=="Standard atmosphere":
                entry,unit,spec=self.engineering_fields["altitude"];altitude=self.to_base(entry.get_text(),spec.dimension,unit.get_active_text())
                state=standard_atmosphere(altitude)
                self.set_engineering_result(f"Temperature: {self.fmt_measurement(state['temperature'],'K')} K\nPressure: {self.fmt_measurement(state['pressure']/1000,'kPa')} kPa\nDensity: {self.fmt_measurement(state['density'],'kg/m³')} kg/m³\nSpeed of sound: {self.fmt_measurement(state['sound_speed'],'m/s')} m/s","live");return
            if calculation.name == "PCB traces":
                current_entry,current_unit,current_spec=self.engineering_fields["current"];rise_entry,rise_unit,rise_spec=self.engineering_fields["rise"];thick_entry,thick_unit,thick_spec=self.engineering_fields["thickness"]
                if not current_entry.get_text().strip():raise ValueError("Enter Current")
                values={"current":self.to_base(current_entry.get_text(),current_spec.dimension,current_unit.get_active_text()),"rise":self.to_base(rise_entry.get_text(),rise_spec.dimension,rise_unit.get_active_text()),"thickness":self.to_base(thick_entry.get_text(),thick_spec.dimension,thick_unit.get_active_text())}
                outer=pcb_width(values,.048);inner=pcb_width(values,.024);lines=[f"External width: {self.fmt_measurement(outer/.0000254, 'mil')} mil  ({self.fmt_measurement(outer*1000, 'mm')} mm)",f"Internal width: {self.fmt_measurement(inner/.0000254, 'mil')} mil  ({self.fmt_measurement(inner*1000, 'mm')} mm)"]
                length_entry,length_unit,length_spec=self.engineering_fields["length"]
                if length_entry.get_text().strip():
                    length=self.to_base(length_entry.get_text(),length_spec.dimension,length_unit.get_active_text());rho=1.724e-8
                    lines.extend([f"External resistance: {self.fmt_measurement(rho*length/(outer*values['thickness']), 'Ω')} Ω",f"Internal resistance: {self.fmt_measurement(rho*length/(inner*values['thickness']), 'Ω')} Ω"])
                self.set_engineering_result("\n".join(lines),"live");self.set_engineering_warnings(warnings_for(calculation,values,0));return
            if calculation.name == "Isentropic flow":
                values={key:self.to_base(entry.get_text(),spec.dimension,unit.get_active_text()) for key,(entry,unit,spec) in self.engineering_fields.items() if entry.get_text().strip()}
                if len(values)!=len(self.engineering_fields):raise ValueError("Fill every flow input")
                m,gamma=values["mach"],values["gamma"]
                if m<=0 or gamma<=1:raise ValueError("Mach must be positive and γ must exceed 1")
                factor=1+(gamma-1)*m*m/2;tr=1/factor;pr=factor**(-gamma/(gamma-1));rr=factor**(-1/(gamma-1));area=(1/m)*((2/(gamma+1))*factor)**((gamma+1)/(2*(gamma-1)))
                static_t=values["temperature"]*tr;static_p=values["pressure"]*pr;sound=math.sqrt(gamma*values["gas_constant"]*static_t)
                p_unit=self.engineering_fields["pressure"][1].get_active_text();self.set_engineering_result(f"T/Tₜ: {self.fmt_measurement(tr)}\nP/Pₜ: {self.fmt_measurement(pr)}\nρ/ρₜ: {self.fmt_measurement(rr)}\nA/A*: {self.fmt_measurement(area)}\nStatic T: {self.fmt_measurement(static_t, 'K')} K\nStatic P: {self.fmt_measurement(from_base(static_p,'pressure',p_unit), p_unit)} {p_unit}\nSpeed of sound: {self.fmt_measurement(sound, 'm/s')} m/s\nVelocity: {self.fmt_measurement(m*sound, 'm/s')} m/s","live");return
            if calculation.solvers:
                blank_keys = [key for key, (entry, _unit, _spec) in self.engineering_fields.items() if not entry.get_text().strip()]
                if len(blank_keys) != 1:
                    self.set_engineering_result("Leave exactly one value blank", "neutral")
                    return
                missing = blank_keys[0]; values = {}; quantities={}
                for key, (entry, unit, spec) in self.engineering_fields.items():
                    if key != missing:
                        try: quantities[key]=self.parse_quantity(entry.get_text(),spec.dimension,unit.get_active_text());values[key]=quantities[key].base_value
                        except ValueError as error: self.mark_invalid_entry(entry,error);raise
                validate_inputs(calculation,values);answer = calculation.solvers[missing](values)
                if not math.isfinite(float(answer)): raise ValueError("Result is not finite")
                _entry, unit, spec = self.engineering_fields[missing]; output_unit = unit.get_active_text()
                shown = from_base(answer, spec.dimension, output_unit); suffix = f" {output_unit}" if output_unit else ""
                text=f"{spec.label}: {self.fmt_measurement(shown, output_unit)}{suffix}";bounds=self.engineering_bounds(calculation.solvers[missing],quantities)
                if bounds:
                    low,high=(from_base(value,spec.dimension,output_unit) for value in bounds);text+=f"\nRange: {self.fmt_measurement(low,output_unit)}–{self.fmt_measurement(high,output_unit)}{suffix}"
                self.set_engineering_result(text, "live")
                self.set_engineering_warnings(warnings_for(calculation,values,answer))
                return
            values = {};quantities={}
            for key, (entry, unit, spec) in self.engineering_fields.items():
                if not entry.get_text().strip(): self.mark_invalid_entry(entry,f"Enter {spec.label}");raise ValueError(f"Enter {spec.label}")
                try: quantities[key]=self.parse_quantity(entry.get_text(),spec.dimension,unit.get_active_text());values[key]=quantities[key].base_value
                except ValueError as error: self.mark_invalid_entry(entry,error);raise
            validate_inputs(calculation,values);operation=compute or calculation.compute;answer = operation(values)
            if not math.isfinite(float(answer)): raise ValueError("Result is not finite")
            if calculation.name == "Wire sizing & voltage drop":
                gauge = int(answer); drop = wire_drop(values, gauge); percent = 100 * drop / values["voltage"]
                self.set_engineering_result(f"Gauge\nRecommended: {gauge} AWG\n\nVoltage drop\n{self.fmt_measurement(drop, 'V')} V  ({self.fmt_measurement(percent, '%')}%)", "live")
                self.set_engineering_warnings(("Verify insulation rating, bundling, ambient temperature, duty cycle, and applicable electrical code.",))
                return
            output_unit = self.engineering_output_unit.get_active_text();dimension=self.current_engineering_calculation.output_dimension
            if output_unit==AUTO_UNIT:output_unit=best_unit(answer,dimension)
            shown = from_base(answer, dimension, output_unit)
            suffix = f" {output_unit}" if output_unit else ""
            text=f"{self.current_engineering_calculation.output_label}: {self.fmt_measurement(shown, output_unit)}{suffix}";bounds=self.engineering_bounds(operation,quantities)
            if bounds:
                low,high=(from_base(value,self.current_engineering_calculation.output_dimension,output_unit) for value in bounds);text+=f"\nRange: {self.fmt_measurement(low,output_unit)}–{self.fmt_measurement(high,output_unit)}{suffix}"
            self.set_engineering_result(text, "live")
            self.set_engineering_warnings(warnings_for(calculation,values,answer))
        except (ValueError, ZeroDivisionError, OverflowError, TypeError) as error:
            self.set_engineering_result(f"Error: {error}", "error")
        finally:
            if _widget is not None and self.engineering_result.get_style_context().has_class("live-result"):
                self.record_engineering_history()

    def record_engineering_history(self):
        calculation=self.current_engineering_calculation;fields={}
        for key,(entry,unit,_spec) in self.engineering_fields.items():fields[key]={"value":entry.get_text(),"unit":unit.get_active_text()}
        payload={"discipline":calculation.discipline,"calculation":calculation.name,"fields":fields,"output_unit":self.engineering_output_unit.get_active_text()}
        add_history(self.session_features,HistoryEntry("engineering",calculation.name,self.engineering_result.get_text(),payload));self.save_tab()

    @staticmethod
    def engineering_bounds(operation,quantities):
        if not any(quantity.minimum!=quantity.maximum for quantity in quantities.values()):return None
        keys=list(quantities);choices=[tuple(dict.fromkeys((quantities[key].minimum,quantities[key].maximum))) for key in keys];answers=[]
        for corner in product(*choices):
            answer=float(operation(dict(zip(keys,corner))))
            if math.isfinite(answer):answers.append(answer)
        return (min(answers),max(answers)) if answers else None

    def engineering_input_changed(self, *_args):
        if _args and isinstance(_args[0],Gtk.Entry):
            _args[0].get_style_context().remove_class("invalid-entry");_args[0].set_tooltip_text(None)
        self.engineering_state_changed()
        if hasattr(self, "current_engineering_calculation") and (self.current_engineering_calculation.solvers or self.current_engineering_calculation.name in CUSTOM_LIVE_CALCULATIONS):
            self.calculate_engineering()
        elif hasattr(self,"engineering_result"):
            self.engineering_warning.set_text("");self.set_engineering_result("Result: —","neutral")

    @staticmethod
    def mark_invalid_entry(entry,error):
        entry.get_style_context().add_class("invalid-entry");entry.set_tooltip_text(str(error))

    def engineering_output_unit_changed(self,*_args):
        self.engineering_state_changed()
        if (hasattr(self,"current_engineering_calculation") and
                self.current_engineering_calculation.output_dimension != "none"):
            self.calculate_engineering()

    def show_wire_gauge_chart(self,button):
        popover=Gtk.Popover.new(button);popover.set_no_show_all(True);popover.set_position(Gtk.PositionType.TOP)
        outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5);outer.set_border_width(8)
        title=Gtk.Label(label="Copper AWG reference — 20 °C");title.set_xalign(0);title.get_style_context().add_class("field-label");outer.pack_start(title,False,False,0)
        scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);scroll.set_min_content_height(220);scroll.set_max_content_height(300)
        grid=Gtk.Grid(column_spacing=12,row_spacing=3);grid.get_style_context().add_class("wire-chart")
        headings=("AWG","Ø mm","mm²","Ω/km","Screen A")
        for column,text in enumerate(headings):
            label=Gtk.Label(label=text);label.get_style_context().add_class("field-label");grid.attach(label,column,0,1,1)
        for row_index,row in enumerate(wire_gauge_chart(),1):
            values=(str(row["gauge"]),f'{row["diameter_mm"]:.3g}',f'{row["area_mm2"]:.3g}',f'{row["ohm_per_km"]:.3g}',f'{row["screen_current"]:g}')
            for column,text in enumerate(values):grid.attach(Gtk.Label(label=text),column,row_index,1,1)
        scroll.add(grid);outer.pack_start(scroll,True,True,0)
        note=Gtk.Label(label="Screen current is an application estimate, not a universal ampacity.\nVerify insulation, bundling, ambient temperature, duty cycle, and code.");note.set_xalign(0);note.set_line_wrap(True);note.set_max_width_chars(48);note.get_style_context().add_class("hint");outer.pack_start(note,False,False,2)
        popover.add(outer);outer.show_all();popover.popup();self._wire_chart_popover=popover

    def engineering_typed_unit(self, entry, _event):
        for _key,(candidate,unit,spec) in self.engineering_fields.items():
            if candidate is entry and entry.get_text().strip():
                try:
                    parsed=self.parse_quantity(entry.get_text(),spec.dimension,unit.get_active_text())
                    if parsed.explicit_unit:
                        names=[unit.get_model()[i][0] for i in range(len(unit.get_model()))]
                        if parsed.unit in names:unit.set_active(names.index(parsed.unit))
                except ValueError:
                    pass
                break
        return False

    def set_engineering_result(self, text, state):
        context=self.engineering_result.get_style_context()
        for css_class in ("live-result","neutral-result","error-result"):context.remove_class(css_class)
        context.add_class({"live":"live-result","neutral":"neutral-result","error":"error-result"}[state])
        self.engineering_result.set_text(text)

    def set_engineering_warnings(self,messages):
        self.engineering_warning.set_text("\n".join(f"⚠ {message}" for message in messages))

    def engineering_state_changed(self, *_args):
        if not getattr(self, "restoring_engineering", True): self.save_tab()

    def toggle_engineering_info(self, button):
        self.engineering_info.set_reveal_child(button.get_active())
        calculation=getattr(self,"current_engineering_calculation",None)
        button.set_tooltip_text("Hide equation and description" if button.get_active() else f"Equation: {calculation.formula if calculation else ''}")

    def toggle_engineering_favorite(self, button):
        if not hasattr(self, "current_engineering_calculation"): return
        key = f"{self.current_engineering_calculation.discipline}|{self.current_engineering_calculation.name}"
        active = toggle_favorite(self.state_data, key)
        button.set_active(active); button.set_label("★" if active else "☆"); self.save_tab()
        if self.engineering_discipline.get_active_text()=="Favorites" and not active:
            self.engineering_discipline_changed(self.engineering_discipline)

    def favorite_calculations(self):
        keys=set(self.state_data.get("favorites",[]));return [calculation for discipline in DISCIPLINES for calculation in calculations_for(discipline) if f"{discipline}|{calculation.name}" in keys]

    def engineering_choices(self,discipline):
        return self.favorite_calculations() if discipline=="Favorites" else calculations_for(discipline)

    def build_converter(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10); box.set_border_width(12)
        box.pack_start(self.field_label("Conversion type"), False, False, 0)
        self.category = ClickOnlyComboBoxText(); [self.category.append_text(x) for x in CATEGORIES]; box.pack_start(self.category, False, False, 0)
        box.pack_start(self.field_label("From"), False, False, 0)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.from_value = Gtk.Entry(); self.from_value.set_placeholder_text("Value"); self.from_value.set_input_purpose(Gtk.InputPurpose.NUMBER)
        if self.save_values_switch.get_active(): self.from_value.set_text(str(self.state_data.get("conversion_value", "")))
        self.from_value.connect("changed", self.update_conversion)
        self.from_value.connect("activate", self.record_conversion_history)
        self.from_unit = ClickOnlyComboBoxText(); self.from_unit.connect("changed", self.update_conversion); row.pack_start(self.from_value, True, True, 0); row.pack_start(self.from_unit, False, False, 0); box.pack_start(row, False, False, 0)
        swap = Gtk.Button(label="⇅  Swap units"); swap.connect("clicked", self.swap_units); box.pack_start(swap, False, False, 0)
        box.pack_start(self.field_label("To"), False, False, 0); self.to_unit = ClickOnlyComboBoxText(); self.to_unit.connect("changed", self.update_conversion); box.pack_start(self.to_unit, False, False, 0)
        self.conversion_result = Gtk.Label(label="—"); self.conversion_result.set_xalign(0); self.conversion_result.set_selectable(True); self.conversion_result.set_line_wrap(True); self.conversion_result.get_style_context().add_class("conversion-result"); box.pack_start(self.copyable(self.conversion_result), True, True, 8)
        saved_category = self.state_data.get("conversion_category")
        category_names = list(CATEGORIES)
        self.category.set_active(category_names.index(saved_category) if saved_category in category_names else 0)
        self.category.connect("changed", self.category_changed)
        self.category_changed(self.category, restore_units=True)
        self.category.connect("changed", self.conversion_selection_changed)
        self.from_unit.connect("changed", self.conversion_selection_changed)
        self.to_unit.connect("changed", self.conversion_selection_changed)
        return box

    @staticmethod
    def field_label(text):
        label = Gtk.Label(label=text); label.set_xalign(0); label.get_style_context().add_class("field-label"); return label

    def math_button_pressed(self, _button, editor, result, token):
        if token == "C": editor.clear(); result.set_text("0")
        elif token == "=": self.calculate_math(editor, result)
        else: editor.insert_math(token)

    def calculate_math(self, editor, result, record=True):
        try:
            expression = editor.get_text();assignment=re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.+)",expression)
            if assignment:
                name,body=assignment.groups()
                if name in RESERVED_MATH_NAMES:raise ValueError(f"'{name}' is reserved")
                if contains_unit(body,UNITS):
                    quantity,dimension=evaluate_unit_expression(body,UNITS)
                    if dimension is None:raise ValueError("Result has a derived unit that is not yet displayable")
                    self.variables[name]={"base_value":quantity.value,"dimension":dimension,"text":body.strip()};shown=f"{name} = {self.format_unit_result(quantity.value,dimension)}"
                else:
                    value=evaluate(body,self.math_variables());self.variables[name]=value;shown=f"{name} = {self.fmt(value)}"
            elif contains_unit(expression,UNITS):
                quantity,dimension=evaluate_unit_expression(expression,UNITS)
                if dimension is None:raise ValueError("Result has a derived unit that is not yet displayable")
                shown=self.format_unit_result(quantity.value,dimension)
            else:shown = self.fmt(evaluate(expression,self.math_variables()))
            result.set_text(shown)
            if record and expression.strip():
                kind = "advanced" if editor is self.advanced_expression else "basic"
                add_history(self.session_features, HistoryEntry(kind, expression, shown, {"expression": expression}))
                self.save_tab()
        except (ValueError, TypeError, SyntaxError, ZeroDivisionError, OverflowError) as error: result.set_text(f"Error: {error}")

    def format_unit_result(self,base_value,dimension):
        if dimension=="none":return self.fmt(base_value)
        unit=best_unit(base_value,dimension);shown=from_base(base_value,dimension,unit)
        return f"{self.fmt_measurement(shown,unit)} {unit}".strip()

    def load_state(self):
        candidates=[STATE_FILE]
        if STATE_FILE==DEFAULT_STATE_FILE and LEGACY_STATE_FILE!=STATE_FILE:candidates.append(LEGACY_STATE_FILE)
        for candidate in candidates:
            try:
                with open(candidate, "r", encoding="utf-8") as state_file:data=json.load(state_file)
                return normalize_state(data)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return {}

    def load_tab(self):
        try:
            page = int(self.state_data.get("selected_tab", 0))
            version = self.state_data.get("layout_version")
            if version == 6: return page if 0 <= page < 4 else 0
            if version == 5: return 3 if page == 4 else (2 if page == 3 else page)
            if version == 4: return 3 if page == 3 else page
            if version == 3: return 3 if page == 2 else page
            if version == 2: return 3 if page == 1 else 0
            return 1 if page == 2 else 0
        except (ValueError, TypeError):
            return 0

    def tab_changed(self, _notebook, _page, page_number):
        if self.restoring_tab:
            return
        self.save_tab(page_number)
        GLib.idle_add(self.focus_page_input, page_number)

    def focus_page_input(self, page_number):
        if page_number == 0:
            self.basic_expression.grab_focus()
        elif page_number == 1:
            self.advanced_expression.grab_focus()
        elif page_number == 2:
            fields = list(self.engineering_fields.values())
            if fields: fields[0][0].grab_focus()
        elif page_number == 3:
            self.from_value.grab_focus()
        return False

    def save_tab(self, page_number=None):
        if page_number is None:
            page_number = self.notebook.get_current_page()
        self.state_data["selected_tab"] = page_number
        self.state_data["layout_version"] = 6
        self.state_data["save_values"] = self.save_values_switch.get_active()
        if self.save_values_switch.get_active(): self.state_data["history"]=self.session_features["history"]
        else: self.state_data.pop("history",None)
        if self.save_values_switch.get_active():self.state_data["variables"]=self.variables
        else:self.state_data.pop("variables",None)
        if hasattr(self, "category"):
            self.state_data["conversion_category"] = self.category.get_active_text()
            self.state_data["conversion_from_unit"] = self.from_unit.get_active_text()
            self.state_data["conversion_to_unit"] = self.to_unit.get_active_text()
            if self.save_values_switch.get_active(): self.state_data["conversion_value"] = self.from_value.get_text()
            else: self.state_data.pop("conversion_value", None)
        if hasattr(self, "basic_expression"):
            if self.save_values_switch.get_active():
                self.state_data["basic_expression"] = self.basic_expression.get_text(); self.state_data["advanced_expression"] = self.advanced_expression.get_text()
            else:
                self.state_data.pop("basic_expression", None); self.state_data.pop("advanced_expression", None)
        if hasattr(self, "engineering_discipline") and getattr(self, "current_engineering_calculation", None):
            discipline = self.engineering_discipline.get_active_text(); calculation = self.engineering_calculation.get_active_text();intrinsic=self.current_engineering_calculation.discipline
            self.state_data["engineering_discipline"] = discipline; self.state_data["engineering_calculation"] = calculation
            all_values = self.state_data.setdefault("engineering_values", {}); current = {}
            for key, (entry, unit, _spec) in self.engineering_fields.items():
                current[key] = {"unit": unit.get_active_text()}
                if self.save_values_switch.get_active(): current[key]["value"] = entry.get_text()
            current["_output_unit"] = self.engineering_output_unit.get_active_text()
            all_values[f"{intrinsic}|{calculation}"] = current
            if not self.save_values_switch.get_active():
                for calculation_values in all_values.values():
                    if isinstance(calculation_values, dict):
                        for item in calculation_values.values():
                            if isinstance(item, dict): item.pop("value", None)
        temporary = STATE_FILE + ".tmp"
        try:
            state_directory=os.path.dirname(STATE_FILE)
            if state_directory:os.makedirs(state_directory,exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as state_file:
                json.dump(self.state_data, state_file, indent=2)
            os.replace(temporary, STATE_FILE)
        except OSError:
            pass

    def on_destroy(self, _window):
        self.save_tab()
        Gtk.main_quit()

    def save_values_toggled(self, *_args):
        self.save_tab()

    def category_changed(self, _combo, restore_units=False):
        category = self.category.get_active_text()
        if not category: return
        self.from_unit.remove_all(); self.to_unit.remove_all()
        for unit in CATEGORIES[category]: self.from_unit.append_text(unit); self.to_unit.append_text(unit)
        self.from_unit.set_active(0); self.to_unit.set_active(1 if len(CATEGORIES[category]) > 1 else 0); self.update_conversion()
        if restore_units:
            units = list(CATEGORIES[category])
            saved_from = self.state_data.get("conversion_from_unit")
            saved_to = self.state_data.get("conversion_to_unit")
            if saved_from in units: self.from_unit.set_active(units.index(saved_from))
            if saved_to in units: self.to_unit.set_active(units.index(saved_to))

    def conversion_selection_changed(self, _combo):
        self.save_tab()

    def update_conversion(self, *_args):
        value = self.from_value.get_text().strip(); category = self.category.get_active_text(); source = self.from_unit.get_active_text(); target = self.to_unit.get_active_text()
        if not value or not all((category, source, target)): self.conversion_result.set_text("—"); return
        try:
            _number,typed_source,explicit=parse_conversion_input(value,category,source)
            if explicit and typed_source!=source:
                units=list(CATEGORIES[category]);self.from_unit.set_active(units.index(typed_source));source=typed_source
            self.conversion_result.set_text(f"{self.fmt(convert(value, category, source, target))}  {target}")
        except (ValueError, OverflowError): self.conversion_result.set_text("Enter a valid number")

    def record_conversion_history(self, _entry):
        self.update_conversion();result=self.conversion_result.get_text()
        if result not in ("—","Enter a valid number"):
            payload={"category":self.category.get_active_text(),"value":self.from_value.get_text(),"from_unit":self.from_unit.get_active_text(),"to_unit":self.to_unit.get_active_text()}
            add_history(self.session_features,HistoryEntry("conversion",f"{payload['from_unit']} → {payload['to_unit']}",result,payload));self.save_tab()

    def swap_units(self, _button):
        source, target = self.from_unit.get_active(), self.to_unit.get_active(); self.from_unit.set_active(target); self.to_unit.set_active(source)

    def on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape: self.close(); return True
        if event.keyval == Gdk.KEY_Tab and event.state & Gdk.ModifierType.CONTROL_MASK: self.notebook.next_page(); return True
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_k, Gdk.KEY_K): self.show_search_popover(); return True
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_h, Gdk.KEY_H): self.show_history_popover(); return True
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_d, Gdk.KEY_D) and self.notebook.get_current_page()==2:
            self.engineering_favorite_button.set_active(not self.engineering_favorite_button.get_active()); return True
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.state & Gdk.ModifierType.SHIFT_MASK and event.keyval in (Gdk.KEY_c, Gdk.KEY_C):
            label={0:self.basic_result,1:self.advanced_result,2:self.engineering_result,3:self.conversion_result}.get(self.notebook.get_current_page())
            if label:Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(label.get_text(),-1)
            return True
        return False

    def show_focused(self):
        self.restoring_tab = True
        self.show_all()
        self.notebook.set_current_page(self.restored_tab)
        self.restoring_tab = False
        self.present_with_time(Gdk.CURRENT_TIME); GLib.timeout_add(80, self.force_focus)
    def force_focus(self):
        # Direct GdkWindow focus is an X11 mechanism.  Wayland compositors
        # intentionally arbitrate focus, so presentation/startup activation
        # must be allowed to do its job there.
        if not is_wayland_session() and self.get_window():self.get_window().focus(Gdk.CURRENT_TIME)
        self.present_with_time(Gdk.CURRENT_TIME)
        self.focus_page_input(self.notebook.get_current_page())
        return False

def is_wayland_session():
    return bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE","").casefold()=="wayland"

def main():
    if "--diagnostics" in sys.argv:
        state=CalculatorWindow.load_state(None)
        print(f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}")
        display=Gdk.Display.get_default();print(f"Session: {'Wayland' if is_wayland_session() else 'X11/other'} · display {display.get_name() if display else 'unavailable'}")
        print(f"State file: {STATE_FILE}")
        print(f"Calculations: {sum(len(calculations_for(name)) for name in DISCIPLINES)}")
        print(f"State: readable · history {len(state.get('history',[]))} · favorites {len(state.get('favorites',[]))}")
        return
    instance_lock = toggle_existing_instance()
    if instance_lock is None:
        return
    window = CalculatorWindow()
    def request_close(_signal, _frame):
        GLib.idle_add(window.close)
    signal.signal(signal.SIGUSR1, request_close)
    signal.signal(signal.SIGTERM, request_close)
    signal.signal(signal.SIGINT, request_close)
    window.show_focused()
    try:
        Gtk.main()
    finally:
        instance_lock.close()

if __name__ == "__main__": main()
