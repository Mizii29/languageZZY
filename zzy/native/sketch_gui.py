"""Tk adapter. Imported exclusively by the explicit --gui CLI entry."""
from queue import Empty
from threading import Thread, current_thread, main_thread
import math

from ..interpreter import Interpreter
from .sketch_session import Bridge
from .sketch_svg import rgb


class View:
    def __init__(self, tk, root, session):
        self.tk,self.session=tk,session
        self.window=tk.Toplevel(root)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.scene=None;self.zoom=1.;self.offset=[0.,0.];self.points=[]
        self.toolbar=tk.Frame(self.window);self.toolbar.pack(fill='x')
        self.mode=tk.StringVar(value='free');self.pen=tk.StringVar(value='studio')
        self.color=tk.StringVar(value='#000000');self.width=tk.DoubleVar(value=2.)
        tk.OptionMenu(self.toolbar,self.mode,'free','line','rectangle','circle','polygon','text','pan').pack(side='left')
        tk.Entry(self.toolbar,textvariable=self.pen,width=10).pack(side='left')
        tk.Button(self.toolbar,text='颜色',command=self.choose_color).pack(side='left')
        tk.Spinbox(self.toolbar,from_=1,to=100,textvariable=self.width,width=5).pack(side='left')
        tk.Button(self.toolbar,text='+',command=lambda:self.scale(1.25)).pack(side='left')
        tk.Button(self.toolbar,text='−',command=lambda:self.scale(.8)).pack(side='left')
        self.grid=tk.BooleanVar(value=False)
        tk.Checkbutton(self.toolbar,text='网格',variable=self.grid,command=self.draw).pack(side='left')
        self.label=tk.Label(self.window,text='');self.label.pack(side='bottom')
        self.layers=tk.Listbox(self.window,width=22);self.layers.pack(side='right',fill='y')
        self.area=tk.Canvas(self.window,width=700,height=500,background='#dddddd')
        self.area.pack(fill='both',expand=True)
        self.area.bind('<Configure>',lambda e:self.draw())
        self.area.bind('<ButtonPress-1>',self.press)
        self.area.bind('<B1-Motion>',self.drag)
        self.area.bind('<ButtonRelease-1>',self.release)
        self.area.bind('<Motion>',self.motion)
        self.area.bind('<MouseWheel>',lambda e:self.scale(1.25 if e.delta>0 else .8))

    def close(self):
        self.session.closed.set()
        self.window.destroy()

    def choose_color(self):
        from tkinter.colorchooser import askcolor
        value=askcolor(self.color.get(),parent=self.window)[1]
        if value:self.color.set(value)

    def scale(self,factor):
        self.zoom=max(.05,min(20.,self.zoom*factor));self.draw()

    def screen(self,p):
        return (self.area.winfo_width()/2+self.offset[0]+p[0]*self.zoom,
                self.area.winfo_height()/2+self.offset[1]-p[1]*self.zoom)

    def logical(self,e):
        cx,cy=self.screen((0.,0.))
        return ((e.x-cx)/self.zoom,(cy-e.y)/self.zoom)

    def motion(self,e):
        x,y=self.logical(e);self.label.config(text=f'({x:.2f}, {y:.2f}) · {self.zoom:.2f}× · {self.mode.get()}')

    def press(self,e):
        self.points=[self.logical(e)];self.pan_start=(e.x,e.y)

    def drag(self,e):
        if self.mode.get()=='pan':
            self.offset[0]+=e.x-self.pan_start[0];self.offset[1]+=e.y-self.pan_start[1]
            self.pan_start=(e.x,e.y);self.draw();return
        if len(self.points)>=10000:self.session.failed.set();self.session.closed.set();return
        self.points.append(self.logical(e))
        self.area.delete('preview')
        if len(self.points)>1:self.area.create_line(*(v for p in self.points for v in self.screen(p)),fill=self.color.get(),tags='preview')

    def release(self,e):
        if not self.points or self.mode.get()=='pan':return
        self.points.append(self.logical(e));content=''
        if self.mode.get()=='text':
            from tkinter.simpledialog import askstring
            content=askstring('文字','内容',parent=self.window)
            if content is None:return
        color=tuple(int(self.color.get()[i:i+2],16) for i in (1,3,5))
        try:width=float(self.width.get())
        except (ValueError,self.tk.TclError):self.label.config(text='线宽无效');return
        self.session.send(('tool',self.mode.get(),self.pen.get(),color,width,tuple(self.points),content))
        self.points=[];self.area.delete('preview')

    def render(self,scene):
        self.scene=scene;self.window.title(scene.title)
        self.layers.delete(0,'end')
        for identity,name,visible,locked in reversed(scene.layers):
            self.layers.insert('end',f'{name} {"隐藏" if not visible else ""} {"锁定" if locked else ""}')
        self.draw()

    def draw(self):
        if self.scene is None:return
        a=self.area;s=self.scene;a.delete('all')
        x0,y0=self.screen((-s.width/2,s.height/2));x1,y1=self.screen((s.width/2,-s.height/2))
        a.create_rectangle(x0,y0,x1,y1,fill=rgb(s.background),outline='')
        if self.grid.get():
            step=max(20,20/self.zoom)
            for x in range(math.ceil(-s.width/2/step),math.floor(s.width/2/step)+1):
                a.create_line(*self.screen((x*step,s.height/2)),*self.screen((x*step,-s.height/2)),fill='#eeeeee')
            for y in range(math.ceil(-s.height/2/step),math.floor(s.height/2/step)+1):
                a.create_line(*self.screen((-s.width/2,y*step)),*self.screen((s.width/2,y*step)),fill='#eeeeee')
        for g in s.geometries:
            if g.boundary:a.create_polygon(*(v for p in g.boundary for v in self.screen(p)),fill=rgb(g.fill),outline='')
            if g.kind=='dot':
                x,y=self.screen(g.center);radius=g.diameter*self.zoom/2
                a.create_oval(x-radius,y-radius,x+radius,y+radius,fill=rgb(g.fill),outline='')
            if g.kind=='text':
                x,y=self.screen(g.center)
                a.create_text(x,y,text=g.text,fill=rgb(g.fill),font=(g.font if g.font!='sans-serif' else 'Arial',-max(1,round(g.size*self.zoom))),anchor={'left':'w','center':'center','right':'e'}[g.align])
            for stroke in g.strokes:
                a.create_line(*(v for p in stroke.points for v in self.screen(p)),fill=rgb(stroke.color),width=stroke.width*self.zoom,capstyle='round',joinstyle='round')
        # Cover geometry outside logical canvas without changing document data.
        width,height=a.winfo_width(),a.winfo_height()
        for box in ((0,0,width,y0),(0,y1,width,height),(0,y0,x0,y1),(x1,y0,width,y1)):
            if box[2]>box[0] and box[3]>box[1]:a.create_rectangle(*box,fill='#dddddd',outline='')


def run_gui(program,output,*,probe=None):
    if current_thread() is not main_thread():raise RuntimeError('Tk requires main thread')
    try:
        import tkinter as tk
        root=tk.Tk();root.withdraw()
    except (ImportError,RuntimeError) as error:
        runtime=Interpreter(program,output);runtime.gui_bridge=Bridge('GUI unavailable: '+str(error));runtime.run();return
    except Exception as error:
        # Tk's documented missing-display/runtime failure only; unexpected bugs propagate.
        if type(error).__name__!='TclError':raise
        runtime=Interpreter(program,output);runtime.gui_bridge=Bridge('GUI unavailable: '+str(error));runtime.run();return
    bridge=Bridge();failures=[];views=[]
    def callback_error(kind,error,traceback):
        failures.append(error)
        output.meter.cancellation.cancel()
        if bridge.active:bridge.active.closed.set()
        root.quit()
    root.report_callback_exception=callback_error
    def worker():
        try:
            runtime=Interpreter(program,output);runtime.gui_bridge=bridge;runtime.run()
        except BaseException as error:failures.append(error)
    thread=Thread(target=worker,name='ZZY-execution')
    def poll():
        try:
            session=bridge.requests.get_nowait()
            view=View(tk,root,session);views.append(view)
            if probe:probe(view,thread)
        except Empty:pass
        for view in tuple(views):
            if view.session.closed.is_set():
                if view.window.winfo_exists():view.window.destroy()
                views.remove(view);continue
            try:view.render(view.session.renders.get_nowait())
            except Empty:pass
        if thread.is_alive():root.after(16,poll)
        else:root.quit()
    thread.start();root.after(0,poll)
    try:root.mainloop()
    finally:
        if thread.is_alive():output.meter.cancellation.cancel()
        if bridge.active:bridge.active.closed.set()
        thread.join();root.destroy()
    if failures:raise failures[0]
