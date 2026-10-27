"""Tk adapter. Imported exclusively by the explicit --gui CLI entry."""
from queue import Empty
from threading import Thread, current_thread, main_thread
import math
import time

from ..interpreter import Interpreter
from .sketch_session import Bridge
from .sketch_svg import rgb


class View:
    def __init__(self, tk, root, session):
        self.tk,self.session=tk,session
        self.root=root
        self.window=tk.Toplevel(root)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.scene=None;self.zoom=1.;self.offset=[0.,0.];self.points=[]
        self.render_task=None;self.render_complete=True;self.render_version=0;self.is_closed=False;self.item_count=0
        self.toolbar=tk.Frame(self.window);self.toolbar.pack(fill='x')
        self.mode=tk.StringVar(value='free');self.pen=tk.StringVar(value='studio')
        self.color=tk.StringVar(value='#000000');self.width=tk.DoubleVar(value=2.)
        tk.OptionMenu(self.toolbar,self.mode,'free','line','rectangle','circle','polygon','text','pan','select','move','copy','erase','callbacks').pack(side='left')
        tk.Entry(self.toolbar,textvariable=self.pen,width=10).pack(side='left')
        tk.Button(self.toolbar,text='颜色',command=self.choose_color).pack(side='left')
        tk.Spinbox(self.toolbar,from_=1,to=100,textvariable=self.width,width=5).pack(side='left')
        tk.Button(self.toolbar,text='+',command=lambda:self.scale(1.25)).pack(side='left')
        tk.Button(self.toolbar,text='−',command=lambda:self.scale(.8)).pack(side='left')
        self.grid=tk.BooleanVar(value=False)
        tk.Checkbutton(self.toolbar,text='网格',variable=self.grid,command=self.draw).pack(side='left')
        history=tk.Frame(self.window);history.pack(fill='x')
        for label,op in [('撤销','undo'),('重做','redo')]:
            tk.Button(history,text=label,command=lambda op=op:self.history_action(op)).pack(side='left')
        for label,op in [('播放','play'),('暂停','pause'),('单步','step')]:
            tk.Button(history,text=label,command=lambda op=op:self.session.send(('replay',op))).pack(side='left')
        self.seek=tk.Scale(history,from_=0,to=0,orient='horizontal',showvalue=True)
        self.seek.pack(side='left',fill='x',expand=True)
        self.seek.bind('<ButtonRelease-1>',lambda e:self.session.send(('replay','seek',int(self.seek.get()))))
        self.label=tk.Label(self.window,text='');self.label.pack(side='bottom')
        layerbar=tk.Frame(self.window);layerbar.pack(side='right',fill='y')
        for label,op in [('新图层','add_layer'),('显隐','layer_visible'),('锁定','lock_layer'),('改名','rename_layer'),('上移','up'),('下移','down'),('笔归此层','set_layer')]:
            tk.Button(layerbar,text=label,command=lambda op=op:self.layer_action(op)).pack(fill='x')
        self.layers=tk.Listbox(layerbar,width=22,exportselection=False);self.layers.pack(side='right',fill='y')
        self.area=tk.Canvas(self.window,width=700,height=500,background='#dddddd')
        self.area.pack(fill='both',expand=True)
        self.area.bind('<Configure>',lambda e:self.draw())
        for button in (1,2,3):
            self.area.bind(f'<ButtonPress-{button}>',lambda e,b=button:self.press(e,b))
            self.area.bind(f'<B{button}-Motion>',lambda e,b=button:self.drag(e,b))
            self.area.bind(f'<ButtonRelease-{button}>',lambda e,b=button:self.release(e,b))
        self.area.bind('<KeyPress>',self.key)
        self.area.bind('<Motion>',self.motion)
        self.area.bind('<MouseWheel>',lambda e:self.scale(1.25 if e.delta>0 else .8))

    def key(self,event):
        names={'Return':'Enter','Escape':'Escape','BackSpace':'Backspace','space':'Space','Prior':'PageUp','Next':'PageDown'}
        key=names.get(event.keysym,event.char if event.char and event.char.isprintable() else event.keysym)
        self.session.send(('callback','key',key))

    def layer_action(self,op):
        if self.scene is None:return
        from tkinter.simpledialog import askstring
        if op=='add_layer':
            name=askstring('图层','名字',parent=self.window)
            if name:self.session.send(('add_layer',name))
            return
        selection=self.layers.curselection()
        if not selection:return
        identity,name,visible,locked=self.scene.layers[-1-selection[0]]
        if op=='set_layer':self.session.send(('set_layer',self.pen.get(),identity));return
        if op in {'up','down'}:
            index=len(self.scene.layers)-1-selection[0]+(1 if op=='up' else -1)
            if not 0<=index<len(self.scene.layers):return
            op,value='move_layer',index
        elif op=='rename_layer':
            value=askstring('图层','新名字',initialvalue=name,parent=self.window)
            if value is None:return
        else:value=not (visible if op=='layer_visible' else locked)
        self.session.send(('layer',op,identity,value))

    def close(self):
        if self.is_closed:return
        self.is_closed=True;self.session.closed.set()
        if self.render_task is not None:self.window.after_cancel(self.render_task);self.render_task=None
        def descendants(widget):
            yield widget
            for child in widget.winfo_children():yield from descendants(child)
        widgets=list(descendants(self.window))
        self.window.destroy()
        # Tk Variable finalizers must run here, not during a later worker GC.
        for variable in (self.mode,self.pen,self.color,self.width,self.grid):
            variable.__del__();variable._tk=None
        # Destroyed Python widget wrappers may outlive the view (e.g. a probe).
        # Detach their Tcl interpreter references on its owning main thread.
        self.root._zzy_retired_widgets.extend(widgets)

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
        x,y=self.logical(e)
        state=next((state for name,state in self.scene.pens if name==self.pen.get()),None) if self.scene else None
        hint=' · 画笔摸鱼中' if state is not None and not state.down else ''
        self.label.config(text=f'({x:.2f}, {y:.2f}) · {self.zoom:.2f}× · {self.mode.get()}{hint}')

    def history_action(self,op):
        self.session.send(('history',op))
        if op=='undo' and self.scene is not None and self.scene.history_length:
            self.label.config(text='这一笔先回去进修')

    def press(self,e,button=1):
        self.area.focus_set()
        self.session.send(('callback','click',*self.logical(e),button))
        if self.mode.get() in {'select','move','copy','erase'}:
            self.session.send(('object','select',*self.logical(e),0.,0.))
        self.points=[self.logical(e)];self.pan_start=(e.x,e.y)

    def drag(self,e,button=1):
        self.session.send(('callback','drag',*self.logical(e),button))
        if self.mode.get() in {'callbacks','select','copy','erase'}:return
        if self.mode.get()=='pan':
            self.offset[0]+=e.x-self.pan_start[0];self.offset[1]+=e.y-self.pan_start[1]
            self.pan_start=(e.x,e.y);self.draw();return
        if len(self.points)>=10000:self.session.fail('sketch.batch_points',10000,10001);return
        self.points.append(self.logical(e))
        self.area.delete('preview')
        if len(self.points)>1:self.area.create_line(*(v for p in self.points for v in self.screen(p)),fill=self.color.get(),tags='preview')

    def release(self,e,button=1):
        self.session.send(('callback','release',*self.logical(e),button))
        mode=self.mode.get()
        if mode in {'callbacks','select'}:self.points=[];return
        if mode in {'move','copy','erase'} and self.points:
            a,b=self.points[0],self.logical(e)
            op={'move':'translate_object','copy':'copy_object','erase':'delete_object'}[mode]
            self.session.send(('object',op,*b,b[0]-a[0],b[1]-a[1]));self.points=[];return
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
        old=self.scene
        if self.scene is None and any(k in scene.input_callbacks for k in ('click','drag','release')):self.mode.set('callbacks')
        self.scene=scene;self.window.title(scene.title)
        self.seek.config(to=scene.history_length)
        self.seek.set(scene.playback_position if scene.playback_position>=0 else scene.history_length)
        previous=self.layers.curselection()
        self.layers.delete(0,'end')
        for identity,name,visible,locked in reversed(scene.layers):
            self.layers.insert('end',f'{name} {"隐藏" if not visible else ""} {"锁定" if locked else ""}')
        if previous and previous[0]<len(scene.layers):self.layers.selection_set(previous[0])
        prefix=old is not None and all(a is b for a,b in zip(old.geometries,scene.geometries))
        if self.render_complete and prefix and (old.width,old.height,old.background,old.layers)==(scene.width,scene.height,scene.background,scene.layers):
            self.start_paint(self.paint_delta(old,scene))
        else:self.draw()

    def draw(self):
        if self.scene is not None:self.start_paint(self.paint())

    def start_paint(self,iterator):
        if self.render_task is not None:self.window.after_cancel(self.render_task);self.render_task=None
        self.render_version+=1;self.render_complete=False
        self.paint_batch(iterator,self.render_version)

    def paint_batch(self,iterator,version):
        self.render_task=None
        if version!=self.render_version or self.session.closed.is_set():return
        until=time.perf_counter()+.008
        try:
            for _ in range(200):
                next(iterator)
                if time.perf_counter()>=until:break
        except StopIteration:
            self.render_complete=True;self.area.tag_raise('mask');return
        self.area.tag_raise('mask')
        self.render_task=self.window.after(1,lambda:self.paint_batch(iterator,version))

    def item(self,kind,*coords,**options):
        if self.item_count>=200000:
            self.session.fail('sketch.render_items',200000,self.item_count+1)
            return None
        self.item_count+=1
        return getattr(self.area,'create_'+kind)(*coords,**options)

    def remove_items(self,tag):
        self.item_count-=len(self.area.find_withtag(tag));self.area.delete(tag)

    def paint_fill(self,boundary,color,tag):
        # Tk 8.6 Windows polygon uses winding fill. Rasterize parity explicitly
        # at pixel centers; only filled spans are painted, preserving lower layers.
        starts={};last=0;limit=self.area.winfo_height()
        for i,(a,b) in enumerate(zip(boundary,(*boundary[1:],boundary[0]))):
            a,b=self.screen(a),self.screen(b)
            if a[1]>b[1]:a,b=b,a
            if a[1]!=b[1]:
                start=max(0,math.ceil(a[1]-.5));end=min(limit,math.ceil(b[1]-.5))
                if start<end:
                    slope=(b[0]-a[0])/(b[1]-a[1])
                    starts.setdefault(start,[]).append((end,a[0]+(start+.5-a[1])*slope,slope,start))
                    last=max(last,end)
            if i%200==0:yield
        active=[];width=self.area.winfo_width()
        for y in range(min(starts,default=0),last):
            active=[e for e in active if e[0]>y];active.extend(starts.get(y,()))
            crossings=sorted(x+(y-start)*slope for end,x,slope,start in active)
            for left,right in zip(crossings[::2],crossings[1::2]):
                x0=max(0,math.ceil(left-.5));x1=min(width,math.ceil(right-.5))
                if x0<x1:self.item('rectangle',x0,y,x1,y+1,fill=color,outline='',tags=tag)
            yield

    def paint_geometry(self,root):
        a=self.area;tag='object:'+str(root.id)
        for g in root.children if root.kind=='group' else (root,):
            if g.boundary:yield from self.paint_fill(g.boundary,rgb(g.fill),tag)
            if g.kind=='dot':
                x,y=self.screen(g.center);radius=g.diameter*self.zoom/2
                self.item('oval',x-radius,y-radius,x+radius,y+radius,fill=rgb(g.fill),outline='',tags=tag)
            if g.kind=='text':
                x,y=self.screen(g.center)
                self.item('text',x,y,text=g.text,fill=rgb(g.fill),font=(g.font if g.font!='sans-serif' else 'Arial',-max(1,round(g.size*self.zoom))),anchor={'left':'w','center':'center','right':'e'}[g.align],angle=g.angle,tags=tag)
            for stroke in g.strokes:
                self.item('line',*(v for p in stroke.points for v in self.screen(p)),fill=rgb(stroke.color),width=stroke.width*self.zoom,capstyle='round',joinstyle='round',tags=tag)
            yield

    def paint_cursors(self,scene):
        self.remove_items('cursor')
        for name,state in scene.pens:
            if state.cursor:
                theta=math.radians(state.heading);x,y=state.position
                pts=[(x+8*math.cos(theta),y+8*math.sin(theta)),(x+5*math.cos(theta+2.5),y+5*math.sin(theta+2.5)),(x+5*math.cos(theta-2.5),y+5*math.sin(theta-2.5))]
                self.item('polygon',*(v for p in pts for v in self.screen(p)),fill=rgb(state.color),outline='white',tags='cursor')
            yield

    def paint_delta(self,old,scene):
        for g in old.geometries[len(scene.geometries):]:self.remove_items('object:'+str(g.id));yield
        for g in scene.geometries[len(old.geometries):]:yield from self.paint_geometry(g)
        yield from self.paint_cursors(scene)

    def paint(self):
        a=self.area;s=self.scene;a.delete('all');self.item_count=0
        x0,y0=self.screen((-s.width/2,s.height/2));x1,y1=self.screen((s.width/2,-s.height/2))
        self.item('rectangle',x0,y0,x1,y1,fill=rgb(s.background),outline='')
        width,height=a.winfo_width(),a.winfo_height()
        for box in ((0,0,width,y0),(0,y1,width,height),(0,y0,x0,y1),(x1,y0,width,y1)):
            if box[2]>box[0] and box[3]>box[1]:self.item('rectangle',*box,fill='#dddddd',outline='',tags='mask')
        if self.grid.get():
            step=max(20,20/self.zoom)
            for x in range(math.ceil(-s.width/2/step),math.floor(s.width/2/step)+1):
                self.item('line',*self.screen((x*step,s.height/2)),*self.screen((x*step,-s.height/2)),fill='#eeeeee');yield
            for y in range(math.ceil(-s.height/2/step),math.floor(s.height/2/step)+1):
                self.item('line',*self.screen((-s.width/2,y*step)),*self.screen((s.width/2,y*step)),fill='#eeeeee');yield
        for root in s.geometries:yield from self.paint_geometry(root)
        yield from self.paint_cursors(s)


def run_gui(program,output,*,probe=None):
    if current_thread() is not main_thread():raise RuntimeError('Tk requires main thread')
    try:
        import tkinter as tk
        root=tk.Tk();root.withdraw();root._zzy_retired_widgets=[]
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
                if not view.is_closed:view.close()
                views.remove(view);continue
            try:view.render(view.session.take_render())
            except Empty:pass
        if thread.is_alive():root.after(16,poll)
        else:root.quit()
    thread.start();root.after(0,poll)
    try:root.mainloop()
    finally:
        if thread.is_alive():output.meter.cancellation.cancel()
        if bridge.active:bridge.active.closed.set()
        thread.join()
        for view in views:view.close()
        views.clear()
        for timer in root.tk.call('after','info'):root.after_cancel(timer)
        root.report_callback_exception=None
        root.destroy()
        for widget in root._zzy_retired_widgets:widget.tk=None
        root._zzy_retired_widgets.clear()
        root.tk=None
    if failures:raise failures[0]
