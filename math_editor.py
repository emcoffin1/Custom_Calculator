"""Small GTK/Cairo natural-math editor used by the Advanced calculator."""
import gi
gi.require_version("Gtk", "3.0"); gi.require_version("Gdk", "3.0")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")
from gi.repository import Gdk, Gtk, WebKit2
import json
import os


class Node:
    def size(self, cr, scale=1): return (0, 28 * scale, 20 * scale)
    def draw(self, cr, x, y, scale=1): pass

class Text(Node):
    def __init__(self, text): self.text = text or " "
    def size(self, cr, scale=1):
        cr.set_font_size(22 * scale); ext = cr.text_extents(self.text)
        return ext.x_advance, 30 * scale, 21 * scale
    def draw(self, cr, x, y, scale=1):
        cr.set_font_size(22 * scale); cr.move_to(x, y + 21 * scale); cr.show_text(self.text)

class Box(Node):
    def size(self, cr, scale=1): return 18 * scale, 26 * scale, 19 * scale
    def draw(self, cr, x, y, scale=1):
        cr.set_source_rgb(.38, .55, .78); cr.set_line_width(1.5); cr.rectangle(x+1, y+2, 15*scale, 21*scale); cr.stroke()
        cr.set_source_rgb(1, 1, 1)

class Row(Node):
    def __init__(self, children): self.children = children or [Text(" ")]
    def size(self, cr, scale=1):
        sizes=[n.size(cr,scale) for n in self.children]; baseline=max(s[2] for s in sizes)
        return sum(s[0] for s in sizes), max(baseline+s[1]-s[2] for s in sizes), baseline
    def draw(self, cr, x, y, scale=1):
        _,_,base=self.size(cr,scale)
        for node in self.children:
            w,_,b=node.size(cr,scale); node.draw(cr,x,y+base-b,scale); x+=w

class Fraction(Node):
    def __init__(self, top, bottom): self.top,self.bottom=top,bottom
    def size(self, cr, scale=1):
        tw,th,_=self.top.size(cr,.82*scale); bw,bh,_=self.bottom.size(cr,.82*scale)
        return max(tw,bw)+10*scale, th+bh+8*scale, th+4*scale
    def draw(self, cr, x, y, scale=1):
        w,h,base=self.size(cr,scale); tw,th,_=self.top.size(cr,.82*scale); bw,_,_=self.bottom.size(cr,.82*scale)
        self.top.draw(cr,x+(w-tw)/2,y,.82*scale); cr.move_to(x+2*scale,y+th+2*scale); cr.line_to(x+w-2*scale,y+th+2*scale); cr.stroke()
        self.bottom.draw(cr,x+(w-bw)/2,y+th+6*scale,.82*scale)

class Power(Node):
    def __init__(self, base, exponent): self.base,self.exponent=base,exponent
    def size(self, cr, scale=1):
        bw,bh,bb=self.base.size(cr,scale); ew,eh,_=self.exponent.size(cr,.65*scale)
        return bw+ew, max(bh,eh+bb), max(bb,eh+bb-bh)
    def draw(self, cr, x, y, scale=1):
        bw,bh,_=self.base.size(cr,scale); _,eh,_=self.exponent.size(cr,.65*scale)
        self.base.draw(cr,x,y+eh*.55,scale); self.exponent.draw(cr,x+bw,y,.65*scale)

class Radical(Node):
    def __init__(self, value, degree=None): self.value,self.degree=value,degree
    def size(self, cr, scale=1):
        vw,vh,vb=self.value.size(cr,scale); dw=0 if not self.degree else self.degree.size(cr,.55*scale)[0]
        return vw+22*scale+dw/2, vh+6*scale, vb+6*scale
    def draw(self, cr, x, y, scale=1):
        vw,vh,_=self.value.size(cr,scale); offset=0
        if self.degree:
            self.degree.draw(cr,x,y,.55*scale); offset=self.degree.size(cr,.55*scale)[0]/2
        x+=offset; cr.set_line_width(2); cr.move_to(x,y+vh*.58); cr.line_to(x+5*scale,y+vh*.78); cr.line_to(x+10*scale,y+5*scale); cr.line_to(x+18*scale,y+5*scale); cr.line_to(x+18*scale+vw,y+5*scale); cr.stroke()
        self.value.draw(cr,x+18*scale,y+6*scale,scale)

class Parser:
    def __init__(self,text): self.text,self.i=text,0
    def parse(self, stop=""):
        parts=[]; current=[]
        while self.i<len(self.text) and self.text[self.i] not in stop:
            ch=self.text[self.i]
            if ch=="/":
                self.i+=1; left=Row(current); current=[Fraction(left,self.atom())]
            elif ch=="^":
                self.i+=1; left=current.pop() if current else Box(); current.append(Power(left,self.atom()))
            else: current.append(self.atom())
        parts.extend(current); return Row(parts)
    def atom(self):
        if self.i>=len(self.text): return Box()
        if self.text.startswith("ⁿ√",self.i): self.i+=2; args=self.arguments(); return Radical(args[0],args[1] if len(args)>1 else Box())
        if self.text[self.i] in ("√","∛"):
            cube=self.text[self.i]=="∛"; self.i+=1; args=self.arguments(); return Radical(args[0],Text("3") if cube else None)
        ch=self.text[self.i]
        if ch=="□": self.i+=1; return Box()
        if ch=="(":
            self.i+=1; inside=self.parse(")"); self.i+=self.i<len(self.text) and self.text[self.i]==")"; return Row([Text("("),inside,Text(")")])
        start=self.i
        while self.i<len(self.text) and (self.text[self.i].isalnum() or self.text[self.i] in ".π") : self.i+=1
        if self.i>start:
            name=self.text[start:self.i]
            if self.i<len(self.text) and self.text[self.i]=="(": return Row([Text(name), self.atom()])
            return Text(name)
        self.i+=1; return Text(ch)
    def arguments(self):
        if self.i>=len(self.text) or self.text[self.i]!="(": return [Box()]
        self.i+=1; args=[]
        while self.i<len(self.text) and self.text[self.i] != ")":
            args.append(self.parse(",)"))
            if self.i<len(self.text) and self.text[self.i]==",": self.i+=1
        if self.i<len(self.text): self.i+=1
        return args or [Box()]

class MathEditor(Gtk.DrawingArea):
    """Editable expression canvas with the subset of Gtk.Entry API the app uses."""
    def __init__(self):
        super().__init__(); self.text=""; self.cursor=0; self.selection=None
        self.set_name("math_editor"); self.set_size_request(-1,100); self.set_can_focus(True)
        self.connect("draw",self.on_draw); self.connect("key-press-event",self.on_key); self.connect("button-press-event",lambda *_: self.grab_focus())
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
    def set_placeholder_text(self,_): pass
    def set_alignment(self,_): pass
    def connect_activate(self,callback): self.activate_callback=callback
    def get_text(self): return self.text
    def set_text(self,text): self.text=text; self.cursor=len(text); self.selection=None; self.queue_draw()
    def get_position(self): return self.cursor
    def set_position(self,pos): self.cursor=max(0,min(len(self.text),pos)); self.selection=None; self.queue_draw()
    def get_selection_bounds(self): return self.selection or ()
    def select_region(self,start,end): self.selection=(start,end); self.cursor=end; self.queue_draw()
    def delete_text(self,start,end): self.text=self.text[:start]+self.text[end:]; self.cursor=start; self.selection=None; self.queue_draw()
    def insert_text(self,value,position): self.text=self.text[:position]+value+self.text[position:]; self.cursor=position+len(value); self.queue_draw()
    def on_key(self,_widget,event):
        if event.keyval in (Gdk.KEY_Return,Gdk.KEY_KP_Enter):
            if hasattr(self,"activate_callback"): self.activate_callback(self)
            return True
        if event.keyval in (Gdk.KEY_Left,Gdk.KEY_Right): self.set_position(self.cursor+(-1 if event.keyval==Gdk.KEY_Left else 1)); return True
        if event.keyval in (Gdk.KEY_BackSpace,Gdk.KEY_Delete):
            if self.selection: self.delete_text(*self.selection)
            elif event.keyval==Gdk.KEY_BackSpace and self.cursor: self.delete_text(self.cursor-1,self.cursor)
            elif event.keyval==Gdk.KEY_Delete and self.cursor<len(self.text): self.delete_text(self.cursor,self.cursor+1)
            return True
        if event.string and event.string.isprintable():
            if self.selection: start,end=self.selection; self.delete_text(start,end)
            self.insert_text(event.string,self.cursor); return True
        return False


class StructuredMathEditor(Gtk.Box):
    """MathLive-backed expression-tree editor embedded in WebKitGTK."""
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.value = ""; self.activate_callback = None
        manager = WebKit2.UserContentManager()
        manager.register_script_message_handler("changed"); manager.register_script_message_handler("activate")
        manager.connect("script-message-received::changed", self._changed)
        manager.connect("script-message-received::activate", self._activate)
        self.webview = WebKit2.WebView.new_with_user_content_manager(manager)
        self.ready = False; self.pending_value = None; self.webview.connect("load-changed", self._load_changed)
        self.webview.set_size_request(-1, 112); self.webview.set_background_color(Gdk.RGBA(0.18, 0.18, 0.18, 1))
        settings = self.webview.get_settings(); settings.set_enable_javascript(True); settings.set_enable_write_console_messages_to_stdout(False)
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "math_editor.html")
        self.webview.load_uri("file://" + html_path); self.pack_start(self.webview, True, True, 0)
    def _changed(self, _manager, result): self.value = result.get_js_value().to_string()
    def _activate(self, *_args):
        if self.activate_callback: self.activate_callback(self)
    def connect_activate(self, callback): self.activate_callback = callback
    def get_text(self): return self.value
    def _load_changed(self, _webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            self.ready = True
            if self.pending_value is not None:
                value, self.pending_value = self.pending_value, None; self._js("setValue(" + json.dumps(value) + ")")
    def set_text(self, value):
        self.value = value
        if self.ready: self._js("setValue(" + json.dumps(value) + ")")
        else: self.pending_value = value
    def clear(self): self.set_text("")
    def insert_math(self, latex): self._js("insertMath(" + json.dumps(latex) + ")")
    def move_slot(self, direction): self._js("moveSlot(" + json.dumps(direction) + ")")
    def undo(self): self._js("undoMath()")
    def grab_focus(self): self._js("focusMath()"); return True
    def _js(self, expression): self.webview.run_javascript(expression, None, None, None)


# Public editor used by the application. The original canvas classes remain only
# as dependency-free fallback code; all live editing uses the structured field.
MathEditor = StructuredMathEditor
