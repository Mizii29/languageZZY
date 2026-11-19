#pragma once
#include <chrono>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <windowsx.h>
#include <shobjidl.h>

namespace zzy::sketch {
using Clock=std::chrono::steady_clock;
enum class Message {click,drag,release,key,command};
struct Input {
    Message kind;
    int button=0;
    XY position{};
    std::string key;
};
enum Menu {undo=100,redo,grid,zoom_in,zoom_out,pan_left,pan_right,pan_up,pan_down,
    replay_play,replay_step,replay_first,replay_last,svg,project,pen,rectangle,circle,polygon,erase,red,blue,thin,thick,open_project,select,move_to_front,
    new_layer,toggle_layer,lock_layer,layer_first=500,pen_first=900};

class Window {
    static constexpr wchar_t window_class[]=L"ZZYNativeSketchWindow";
    static constexpr UINT refresh=WM_APP+1;
    std::thread worker;
    std::mutex mutex;
    std::condition_variable ready;
    std::deque<Input> input;
    const Document* scene=nullptr;
    HWND hwnd=nullptr;
    IFileDialog* dialog=nullptr;
    int button=0,pan_x=0,pan_y=0;
    double zoom=1;
    bool grid=false,started=false;
    std::wstring title;
    std::wstring caption_pending;
    static constexpr std::size_t queue_limit=4096;
    void choose_file(HWND window,int command) {
        // Only one file event can be pending. Its UTF-8 buffer is prepaid separately.
        {const std::lock_guard<std::mutex> lock(mutex);
            if(dialog||std::any_of(input.begin(),input.end(),[](const Input& e){
                return e.kind==Message::command&&(e.button==svg||e.button==project||e.button==open_project);
            }))return;
        }
        const bool save=command!=open_project,svg_file=command==svg;
        IFileDialog* raw=nullptr;
        if(FAILED(CoCreateInstance(save?CLSID_FileSaveDialog:CLSID_FileOpenDialog,nullptr,
            CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&raw))))throw std::runtime_error("native file dialog unavailable");
        const auto release=[](auto* p){if(p)p->Release();};
        const std::unique_ptr<IFileDialog,decltype(release)> options(raw,release);
        FILEOPENDIALOGOPTIONS flags{};
        const COMDLG_FILTERSPEC types[2]={{svg_file?L"SVG":L"ZZY Sketch",svg_file?L"*.svg":L"*.zzysketch"},
            {L"All files",L"*.*"}};
        if(FAILED(raw->GetOptions(&flags))||
            FAILED(raw->SetOptions(flags|FOS_NOCHANGEDIR|FOS_FORCEFILESYSTEM|FOS_PATHMUSTEXIST|
                (save?FOS_OVERWRITEPROMPT:FOS_FILEMUSTEXIST)))||
            FAILED(raw->SetFileTypes(2,types))||FAILED(raw->SetDefaultExtension(svg_file?L"svg":L"zzysketch")))
            throw std::runtime_error("cannot configure native file dialog");
        dialog=raw;
        const auto chosen=raw->Show(window);
        dialog=nullptr;
        if(SUCCEEDED(chosen)&&!closed) {
            IShellItem* selected=nullptr;
            if(FAILED(raw->GetResult(&selected)))throw std::runtime_error("cannot read selected file");
            const std::unique_ptr<IShellItem,decltype(release)> item(selected,release);
            PWSTR path=nullptr;
            if(FAILED(selected->GetDisplayName(SIGDN_FILESYSPATH,&path)))throw std::runtime_error("cannot resolve selected file");
            const std::unique_ptr<wchar_t,decltype(&CoTaskMemFree)> storage(path,&CoTaskMemFree);
            if(std::wcslen(path)>32767)throw std::runtime_error("selected path exceeds Windows path limit");
            const std::lock_guard<std::mutex> lock(mutex);
            queue({Message::command,command,{},narrow(path)});
        } else if(FAILED(chosen)&&chosen!=HRESULT_FROM_WIN32(ERROR_CANCELLED)&&!closed) {
            throw std::runtime_error("native file dialog failed");
        }
        if(closed)PostMessageW(window,WM_CLOSE,0,0);
    }
    static COLORREF rgb(RGB color) {
        return RGB(static_cast<BYTE>(color[0]),static_cast<BYTE>(color[1]),static_cast<BYTE>(color[2]));
    }
    struct View {
        double x,y,scale;
        POINT point(XY p) const {
            return {static_cast<LONG>(std::lround(x+scale*p[0])),static_cast<LONG>(std::lround(y-scale*p[1]))};
        }
    };
    View view(const RECT& rect) const {
        const auto scale=std::max(.01,std::min(static_cast<double>(rect.right)/static_cast<double>(scene->width),
            static_cast<double>(rect.bottom)/static_cast<double>(scene->height)))*zoom;
        return {rect.right/2.+pan_x,rect.bottom/2.+pan_y,scale};
    }
    static std::string key_name(WPARAM key,LPARAM data) {
        switch(key) {
        case VK_ESCAPE:return "escape";case VK_RETURN:return "return";case VK_SPACE:return "space";
        case VK_LEFT:return "left";case VK_RIGHT:return "right";case VK_UP:return "up";case VK_DOWN:return "down";
        case VK_BACK:return "backspace";case VK_DELETE:return "delete";case VK_TAB:return "tab";
        default:break;
        }
        if(key>='A'&&key<='Z')return std::string(1,static_cast<char>(key-'A'+'a'));
        wchar_t name[80]{};
        if(GetKeyNameTextW(static_cast<LONG>(data),name,80)>0) {
            std::wstring result(name);
            for(auto& ch:result)if(ch>=L'A'&&ch<=L'Z')ch+=L'a'-L'A';
            return narrow(result);
        }
        return "";
    }
    void queue(Input event) {
        if(closed)return;
        if(input.size()>=queue_limit) {overflow=true;closed=true;}
        else input.push_back(std::move(event));
        ready.notify_all();
    }
    void paint(HDC dc,const RECT& bounds) {
        FillRect(dc,&bounds,GetSysColorBrush(COLOR_APPWORKSPACE));
        if(!scene)return;
        const auto mapping=view(bounds);
        const auto a=mapping.point({-static_cast<double>(scene->width)/2,static_cast<double>(scene->height)/2});
        const auto b=mapping.point({static_cast<double>(scene->width)/2,-static_cast<double>(scene->height)/2});
        const RECT canvas{a.x,a.y,b.x,b.y};
        const auto previous=SaveDC(dc);
        if(!previous)return;
        IntersectClipRect(dc,canvas.left,canvas.top,canvas.right,canvas.bottom);
        if(auto brush=CreateSolidBrush(rgb(scene->background))) {FillRect(dc,&canvas,brush);DeleteObject(brush);}
        if(grid) {
            for(auto x=static_cast<LONG>(mapping.x);x<canvas.right;x+=32)
                if(x>=canvas.left){MoveToEx(dc,x,canvas.top,nullptr);LineTo(dc,x,canvas.bottom);}
            for(auto x=static_cast<LONG>(mapping.x)-32;x>=canvas.left;x-=32)
                if(x<canvas.right){MoveToEx(dc,x,canvas.top,nullptr);LineTo(dc,x,canvas.bottom);}
            for(auto y=static_cast<LONG>(mapping.y);y<canvas.bottom;y+=32)
                if(y>=canvas.top){MoveToEx(dc,canvas.left,y,nullptr);LineTo(dc,canvas.right,y);}
            for(auto y=static_cast<LONG>(mapping.y)-32;y>=canvas.top;y-=32)
                if(y<canvas.bottom){MoveToEx(dc,canvas.left,y,nullptr);LineTo(dc,canvas.right,y);}
        }
        const auto shape=[&](const Geometry& geometry) {
            if(!geometry.boundary.empty()||geometry.kind=="dot") {
                const auto brush=CreateSolidBrush(rgb(geometry.fill));
                if(!brush)return;
                const auto old_brush=SelectObject(dc,brush),old_pen=SelectObject(dc,GetStockObject(NULL_PEN));
                if(geometry.kind=="dot") {
                    const auto p=mapping.point(geometry.center);
                    const auto r=std::max<LONG>(1,static_cast<LONG>(std::lround(mapping.scale*geometry.diameter/2)));
                    Ellipse(dc,p.x-r,p.y-r,p.x+r,p.y+r);
                } else {
                    std::vector<POINT> polygon;
                    polygon.reserve(geometry.boundary.size());
                    for(auto p:geometry.boundary)polygon.push_back(mapping.point(p));
                    SetPolyFillMode(dc,ALTERNATE);
                    Polygon(dc,polygon.data(),static_cast<int>(polygon.size()));
                }
                SelectObject(dc,old_brush);SelectObject(dc,old_pen);DeleteObject(brush);
            }
            for(const auto& stroke:geometry.strokes) {
                const auto width=std::max<DWORD>(1,static_cast<DWORD>(std::lround(stroke.width*mapping.scale)));
                const LOGBRUSH color{BS_SOLID,rgb(stroke.color),0};
                const auto pen=ExtCreatePen(PS_GEOMETRIC|PS_SOLID|PS_ENDCAP_ROUND|PS_JOIN_ROUND,width,&color,0,nullptr);
                if(!pen)continue;
                const auto old=SelectObject(dc,pen);
                auto p=mapping.point(stroke.points.front());
                MoveToEx(dc,p.x,p.y,nullptr);
                for(std::size_t i=1;i<stroke.points.size();++i) {
                    p=mapping.point(stroke.points[i]);LineTo(dc,p.x,p.y);
                }
                SelectObject(dc,old);DeleteObject(pen);
            }
            if(geometry.kind=="text") {
                const auto text=widen(geometry.text),font=widen(geometry.font);
                const auto size=std::max<int>(1,static_cast<int>(std::lround(geometry.size*mapping.scale)));
                const auto angle=static_cast<int>(std::lround(heading(geometry.angle)*10));
                const auto face=CreateFontW(-size,0,angle,angle,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
                    OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,DEFAULT_QUALITY,DEFAULT_PITCH,font.c_str());
                const auto old=face?SelectObject(dc,face):nullptr;
                SetBkMode(dc,TRANSPARENT);
                SetTextColor(dc,rgb(geometry.fill));
                SetTextAlign(dc,TA_BASELINE|(geometry.align=="center"?TA_CENTER:geometry.align=="right"?TA_RIGHT:TA_LEFT));
                const auto p=mapping.point(geometry.center);
                TextOutW(dc,p.x,p.y+size/3,text.data(),static_cast<int>(text.size()));
                if(face){SelectObject(dc,old);DeleteObject(face);}
            }
        };
        for(auto id:scene->order)if(scene->layers.at(id).visible) {
            for(const auto& block:scene->objects)if(block->value.layer==id)
                for(const auto* leaf:leaves(block->value))shape(*leaf);
        }
        for(const auto& [name,p]:scene->pens) {
            (void)name;
            if(!p.state.cursor||!scene->layers.at(p.layer).visible)continue;
            const auto center=mapping.point(p.state.position);
            const auto angle=radians(p.state.heading);
            const auto marker=CreatePen(PS_SOLID,1,rgb(p.state.color));
            if(!marker)continue;
            const auto old=SelectObject(dc,marker);
            MoveToEx(dc,center.x,center.y,nullptr);
            LineTo(dc,center.x+static_cast<int>(12*std::cos(angle)),center.y-static_cast<int>(12*std::sin(angle)));
            SelectObject(dc,old);DeleteObject(marker);
        }
        RestoreDC(dc,previous);
    }
    LRESULT dispatch(HWND window,UINT msg,WPARAM w,LPARAM l) {
        if(msg==WM_CLOSE) {
            closed=true;
            ready.notify_all();
            if(dialog)dialog->Close(HRESULT_FROM_WIN32(ERROR_CANCELLED));
            else DestroyWindow(window);
            return 0;
        }
        if(msg==WM_DESTROY){PostQuitMessage(0);return 0;}
        if(msg==WM_PRINTCLIENT) {
            RECT rect{};GetClientRect(window,&rect);
            const std::lock_guard<std::mutex> lock(mutex);
            paint(reinterpret_cast<HDC>(w),rect);
            return 0;
        }
        if(msg==WM_PAINT) {
            PAINTSTRUCT props{};auto dc=BeginPaint(window,&props);
            struct End {HWND window;PAINTSTRUCT& props;~End(){EndPaint(window,&props);}} end{window,props};
            RECT rect{};GetClientRect(window,&rect);
            const std::lock_guard<std::mutex> lock(mutex);
            paint(dc,rect);
            return 0;
        }
        if(msg==refresh) {
            std::wstring caption;
            {const std::lock_guard<std::mutex> lock(mutex);caption.swap(caption_pending);}
            if(!caption.empty())SetWindowTextW(window,caption.c_str());
            InvalidateRect(window,nullptr,FALSE);
            return 0;
        }
        if(msg==WM_SIZE){InvalidateRect(window,nullptr,FALSE);return 0;}
        if(msg==WM_INITMENUPOPUP) {
            const auto menu=reinterpret_cast<HMENU>(w);
            const auto main=GetMenu(window);
            const auto rebuild=[&](int permanent) {
                while(GetMenuItemCount(menu)>permanent)DeleteMenu(menu,static_cast<UINT>(permanent),MF_BYPOSITION);
            };
            const std::lock_guard<std::mutex> lock(mutex);
            if(scene&&menu==GetSubMenu(main,5)) {
                rebuild(4);
                for(std::size_t i=0;i<scene->order.size();++i) {
                    const auto& layer=scene->layers.at(scene->order[i]);
                    const auto label=widen(layer.name)+(layer.locked?L" [锁定]":L"")+(layer.visible?L"":L" [隐藏]");
                    AppendMenuW(menu,MF_STRING,layer_first+i,label.c_str());
                }
            } else if(scene&&menu==GetSubMenu(main,2)) {
                rebuild(8);
                std::size_t i=0;
                for(const auto& x:scene->pens) {
                    const auto label=L"选择 · "+widen(x.first);
                    AppendMenuW(menu,MF_STRING,pen_first+i++,label.c_str());
                }
            }
        }
        if(msg==WM_COMMAND) {
            const auto command=LOWORD(w);
            if(command==svg||command==project||command==open_project)choose_file(window,command);
            else if(command>=Menu::grid&&command<=pan_down) {
                switch(command) {
                case Menu::grid:grid=!grid;break;
                case zoom_in:zoom=std::min(16.,zoom*1.25);break;
                case zoom_out:zoom=std::max(.125,zoom/1.25);break;
                case pan_left:pan_x=std::max(-100000,pan_x-48);break;
                case pan_right:pan_x=std::min(100000,pan_x+48);break;
                case pan_up:pan_y=std::max(-100000,pan_y-48);break;
                case pan_down:pan_y=std::min(100000,pan_y+48);break;
                }
                InvalidateRect(window,nullptr,FALSE);
            } else {
                const std::lock_guard<std::mutex> lock(mutex);
                queue({Message::command,command,{},{}});
            }
            return 0;
        }
        if(msg==WM_KEYDOWN) {
            const auto key=key_name(w,l);
            if(!key.empty()) {const std::lock_guard<std::mutex> lock(mutex);queue({Message::key,0,{},key});}
            return 0;
        }
        const bool press=msg==WM_LBUTTONDOWN||msg==WM_MBUTTONDOWN||msg==WM_RBUTTONDOWN;
        const bool release=msg==WM_LBUTTONUP||msg==WM_MBUTTONUP||msg==WM_RBUTTONUP;
        if(press||release||msg==WM_MOUSEMOVE) {
            const int selected=(msg==WM_LBUTTONDOWN||msg==WM_LBUTTONUP)?1:
                (msg==WM_MBUTTONDOWN||msg==WM_MBUTTONUP)?2:3;
            if(press){button=selected;SetCapture(window);}
            if(button) {
                RECT rect{};GetClientRect(window,&rect);
                const std::lock_guard<std::mutex> lock(mutex);
                if(scene) {
                    const auto mapping=view(rect);
                    const XY p{(GET_X_LPARAM(l)-mapping.x)/mapping.scale,(mapping.y-GET_Y_LPARAM(l))/mapping.scale};
                    queue({press?Message::click:release?Message::release:Message::drag,release?selected:button,p,{}});
                }
            }
            if(release){button=0;ReleaseCapture();}
            return 0;
        }
        if(msg==WM_CAPTURECHANGED){button=0;return 0;}
        return DefWindowProcW(window,msg,w,l);
    }
    static LRESULT CALLBACK route(HWND window,UINT msg,WPARAM w,LPARAM l) {
        if(msg==WM_NCCREATE) {
            const auto* create=reinterpret_cast<const CREATESTRUCTW*>(l);
            SetWindowLongPtrW(window,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(create->lpCreateParams));
            return DefWindowProcW(window,msg,w,l);
        }
        auto* self=reinterpret_cast<Window*>(GetWindowLongPtrW(window,GWLP_USERDATA));
        if(!self)return DefWindowProcW(window,msg,w,l);
        try {return self->dispatch(window,msg,w,l);}
        catch(...) {self->failed=true;self->closed=true;self->ready.notify_all();PostMessageW(window,WM_CLOSE,0,0);return 0;}
    }
    static HMENU menus() {
        const auto bar=CreateMenu();
        if(!bar)return nullptr;
        const auto section=[&](const wchar_t* title,std::initializer_list<std::pair<UINT,const wchar_t*>> items) {
            const auto menu=CreatePopupMenu();
            if(!menu)return;
            for(const auto& item:items)AppendMenuW(menu,MF_STRING,item.first,item.second);
            if(!AppendMenuW(bar,MF_POPUP,reinterpret_cast<UINT_PTR>(menu),title))DestroyMenu(menu);
        };
        section(L"文件",{{svg,L"导出 SVG"},{project,L"保存项目"},{open_project,L"打开项目"}});
        section(L"编辑",{{undo,L"撤销"},{redo,L"重做"},{select,L"选择并移动"},{erase,L"擦除对象"},{move_to_front,L"当前层置顶"}});
        section(L"画笔",{{pen,L"自由画笔"},{rectangle,L"矩形"},{circle,L"圆"},{polygon,L"三角形"},
            {red,L"红色"},{blue,L"蓝色"},{thin,L"细线"},{thick,L"粗线"}});
        section(L"视图",{{Menu::grid,L"网格"},{zoom_in,L"放大"},{zoom_out,L"缩小"},
            {pan_left,L"左移"},{pan_right,L"右移"},{pan_up,L"上移"},{pan_down,L"下移"}});
        section(L"回放",{{replay_play,L"播放 / 暂停"},{replay_step,L"单步"},{replay_first,L"定位到起点"},{replay_last,L"定位到终点"}});
        auto layer_menu=CreatePopupMenu();
        if(layer_menu) {
            AppendMenuW(layer_menu,MF_STRING,new_layer,L"新增图层并选中");
            AppendMenuW(layer_menu,MF_STRING,toggle_layer,L"切换当前图层显示");
            AppendMenuW(layer_menu,MF_STRING,lock_layer,L"切换当前图层锁定");
            AppendMenuW(layer_menu,MF_SEPARATOR,0,nullptr);
            if(!AppendMenuW(bar,MF_POPUP,reinterpret_cast<UINT_PTR>(layer_menu),L"图层"))DestroyMenu(layer_menu);
        }
        return bar;
    }
    void loop() {
        const auto apartment=CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED|COINIT_DISABLE_OLE1DDE);
        struct ComCleanup {HRESULT result;~ComCleanup(){if(SUCCEEDED(result))CoUninitialize();}} com{apartment};
        const auto instance=GetModuleHandleW(nullptr);
        WNDCLASSW cls{};
        cls.hInstance=instance;cls.lpszClassName=window_class;cls.lpfnWndProc=route;
        cls.hCursor=LoadCursorW(nullptr,MAKEINTRESOURCEW(32512));cls.style=CS_HREDRAW|CS_VREDRAW;
        const bool registered=SUCCEEDED(apartment)&&RegisterClassW(&cls)!=0;
        auto menu=registered?menus():nullptr;
        const auto window=menu?CreateWindowExW(0,window_class,title.c_str(),WS_OVERLAPPEDWINDOW,
            CW_USEDEFAULT,CW_USEDEFAULT,820,620,nullptr,menu,instance,this):nullptr;
        {
            const std::lock_guard<std::mutex> lock(mutex);
            hwnd=window;
            started=true;
        }
        ready.notify_all();
        if(window) {
            ShowWindow(window,SW_SHOW);
            MSG message{};
            int status;
            while((status=GetMessageW(&message,nullptr,0,0))>0){TranslateMessage(&message);DispatchMessageW(&message);}
            if(status<0)failed=true;
            if(IsWindow(window))DestroyWindow(window);
        } else {if(menu)DestroyMenu(menu);failed=true;}
        if(registered)UnregisterClassW(window_class,instance);
        closed=true;
        ready.notify_all();
    }
public:
    std::atomic<bool> closed{false},overflow{false},failed{false};
    Window(std::wstring label,const Document* initial):scene(initial),title(std::move(label)) {}
    ~Window() {
        if(worker.joinable()) {
            if(hwnd)PostMessageW(hwnd,WM_CLOSE,0,0);
            worker.join();
        }
    }
    bool start() {
        worker=std::thread([this]{loop();});
        std::unique_lock<std::mutex> lock(mutex);
        ready.wait(lock,[&]{return started;});
        return hwnd!=nullptr;
    }
    void publish(Document& current,Document updated) {
        const std::lock_guard<std::mutex> lock(mutex);
        current=std::move(updated);
        PostMessageW(hwnd,refresh,0,0);
    }
    std::deque<Input> receive(Clock::time_point deadline) {
        std::unique_lock<std::mutex> lock(mutex);
        ready.wait_until(lock,deadline,[&]{return closed||!input.empty();});
        std::deque<Input> next;
        next.swap(input);
        return next;
    }
    void caption(const std::wstring& status) {
        const std::lock_guard<std::mutex> lock(mutex);
        caption_pending=title+L"  |  "+status;
        if(!closed)PostMessageW(hwnd,refresh,0,0);
    }
};
}

namespace zzy {
inline Value SketchHost::show_native(Doc& d,const Value& canvas_handle) const {
    using namespace std::chrono_literals;
    using sketch::Clock;
    using sketch::Menu;
    using sketch::Message;
    if(c.sketch_showing)error("E214","sketch.show cannot be called from a callback");
    auto scene=projection(d);
    auto queue_storage=reserve({0,4096,4096*128+2*32768*4});
    sketch::Window window(L"ZZY Sketch — "+widen(d.title),&scene);
    const auto restore=[&]{c.heap.state->sketch_closed=nullptr;c.sketch_showing=false;clear_events(d);};
    if(!window.start()) {restore();return failure("GUI unavailable: native window could not be created");}
    const auto pending=c.tasks.size(),frames=c.calls.size(),query_count=c.query_items.size();
    const auto saved_frame=c.frame;
    const auto saved_current=c.current;
    std::map<Id,Clock::time_point> deadlines;
    std::unique_ptr<SketchReplay> replay;
    std::optional<XY> start;
    std::vector<XY> samples;
    Lease sample_space;
    Value tool_pen;
    Doc* editing=&d;
    Value edit_canvas=canvas_handle;
    int tool=0;
    bool playing=false;
    auto frame_at=Clock::now();
    const auto call=[&](const char* name,const std::vector<Value>& args){return invoke(std::string("sketch.")+name,args);};
    const auto callback=[&](Handle fn,std::vector<Value> args) {
        std::vector<NodeId> sites(args.size(),site);
        c.call(pin(fn),std::move(args),site,[](Value){},std::move(sites));
        while(c.tasks.size()>pending) {
            c.point();
            auto task=std::move(c.tasks.back());
            c.tasks.pop_back();
            task.action();
        }
        c.heap.collect();
    };
    const auto publish=[&] {
        const auto& source=replay?replay->scene():*editing;
        window.publish(scene,projection(source));
        const auto state=replay?L"回放 "+std::to_wstring(replay->position())+L"/"+std::to_wstring(replay->size()):
            std::to_wstring(source.order.size())+L" 层 · "+std::to_wstring(source.objects.size())+L" 个对象";
        window.caption(state);
    };
    const auto exit_replay=[&]{replay.reset();playing=false;};
    const auto selected_pen=[&] {
        if(tool_pen)return tool_pen;
        for(const auto& [name,pen]:editing->pens)if(!layer_locked(*editing,pen.layer)){(void)name;return pin(pen.handle);}
        std::string name="window";
        while(editing->pens.count(name))name+="_";
        tool_pen=call("pen",{edit_canvas,string(name)});
        return tool_pen;
    };
    const auto begin_samples=[&](XY first) {
        samples.clear();sample_space.release();
        sample_space=reserve({0,0,0});
        start=first;
    };
    const auto feedback=[&](const Value& result) {
        if(c.object(result).kind=="Result"&&!c.object(result).flag)
            window.caption(widen(text(pin(c.object(result).edges[0]))));
    };
    const auto layer_value=[&](Id id) {
        auto& layer=editing->layers.at(id);
        if(layer.handle.owner)return pin(layer.handle);
        const auto owner=c.heap.native<sketch::CanvasRef>(edit_canvas,site).doc;
        const auto v=c.heap.native("sketch.Layer",std::make_shared<sketch::LayerRef>(sketch::LayerRef{owner,id}),{1,0,0},site);
        link(v,edit_canvas);link(edit_canvas,v);
        layer.handle=v.ref();
        return v;
    };
    const auto current_layer=[&] {
        const auto& pen=c.heap.native<sketch::PenRef>(selected_pen(),site);
        const auto id=editing->pens.at(pen.name).layer;
        return std::make_pair(layer_value(id),id);
    };
    const auto builtin=[&](const sketch::Input& event) {
        if(event.kind==Message::command) {
            const auto command=event.button;
            if(command>=Menu::replay_play&&command<=Menu::replay_last) {
                if(!replay)replay=std::make_unique<SketchReplay>(*this,*editing);
                if(command==Menu::replay_play) {
                    if(replay->position()==replay->size())replay->seek(0);
                    playing=!playing;frame_at=Clock::now();
                } else {
                    playing=false;
                    replay->seek(command==Menu::replay_first?0:command==Menu::replay_last?replay->size():replay->position()+1);
                }
                publish();return;
            }
            if(command==Menu::svg||command==Menu::project) {
                feedback(call(command==Menu::svg?"save_svg":"save_project",{edit_canvas,string(event.key)}));
                return;
            }
            exit_replay();
            if(command==Menu::open_project) {
                const auto result=call("load_project",{string(event.key)});
                if(!c.object(result).flag){feedback(result);return;}
                edit_canvas=decode_json(result);
                editing=c.heap.native<sketch::CanvasRef>(edit_canvas,site).doc.get();
                tool_pen={};
            } else if(command==Menu::undo||command==Menu::redo)call(command==Menu::undo?"undo":"redo",{edit_canvas});
            else if(command>=Menu::pen&&command<=Menu::erase)tool=command;
            else if(command==Menu::select)tool=command;
            else if(command==Menu::red||command==Menu::blue)
                call("color",{selected_pen(),make_color(command==Menu::red?RGB{204,43,62}:RGB{38,95,201})});
            else if(command==Menu::thin||command==Menu::thick)
                call("width",{selected_pen(),integer(command==Menu::thin?2:8)});
            else if(command==Menu::move_to_front) {
                const auto& pen=c.heap.native<sketch::PenRef>(selected_pen(),site);
                const auto id=editing->pens.at(pen.name).layer;
                if(id)call("move_layer",{pin(editing->layers.at(id).handle),integer(static_cast<Id>(editing->order.size()-1))});
            } else if(command==Menu::new_layer) {
                auto pen=selected_pen();
                auto layer=call("add_layer",{edit_canvas,string("Layer "+std::to_string(editing->next_layer))});
                call("set_layer",{pen,layer});
                tool_pen=pen;
            } else if(command==Menu::toggle_layer||command==Menu::lock_layer) {
                const auto [layer,id]=current_layer();
                const auto& item=editing->layers.at(id);
                call(command==Menu::toggle_layer?"layer_visible":"lock_layer",
                    {layer,boolean(command==Menu::toggle_layer?!item.visible:!item.locked)});
            } else if(command>=Menu::pen_first) {
                const auto index=static_cast<std::size_t>(command-Menu::pen_first);
                if(index<editing->pens.size()) {
                    auto it=editing->pens.begin();
                    std::advance(it,static_cast<std::ptrdiff_t>(index));
                    tool_pen=pin(it->second.handle);
                }
            } else if(command>=Menu::layer_first) {
                const auto index=static_cast<std::size_t>(command-Menu::layer_first);
                if(index<editing->order.size())call("set_layer",{selected_pen(),layer_value(editing->order[index])});
            }
            publish();return;
        }
        if(!tool||event.button!=1)return;
        if(event.kind==Message::click) {exit_replay();begin_samples(event.position);return;}
        if(!start)return;
        if(event.kind==Message::drag&&tool==Menu::pen) {
            capacity("batch_points",samples.size()+2,10000);
            sample_space.grow({0,1,sizeof(XY)},site);
            samples.push_back(event.position);
        }
        if(event.kind!=Message::release)return;
        const auto initial=*start;
        start.reset();
        const auto pos=event.position;
        if(tool==Menu::select||tool==Menu::erase) {
            const auto result=call("pick",{edit_canvas,real(initial[0]),real(initial[1])});
            if(c.object(result).kind=="Int") {
                if(tool==Menu::erase)call("delete_object",{edit_canvas,result});
                else call("translate_object",{edit_canvas,result,real(pos[0]-initial[0]),real(pos[1]-initial[1])});
            }
        } else {
            const auto pen=selected_pen();
            call("begin_group",{edit_canvas,string("window stroke")});
            call("jump_to",{pen,real(initial[0]),real(initial[1])});
            if(tool==Menu::circle) {
                const double radius=std::hypot(pos[0]-initial[0],pos[1]-initial[1]);
                if(radius>0)call("circle",{pen,real(radius),integer(360)});
            } else {
                if(tool==Menu::rectangle)samples={XY{pos[0],initial[1]},pos,XY{initial[0],pos[1]},initial};
                else if(tool==Menu::polygon)samples={XY{pos[0],initial[1]},XY{(pos[0]+initial[0])/2,pos[1]},initial};
                else samples.push_back(pos);
                std::vector<Value> points;
                for(const auto p:samples)points.push_back(point_array(p));
                call("polyline",{pen,array(points)});
            }
            call("end_group",{edit_canvas});
        }
        samples.clear();sample_space.release();publish();
    };
    c.sketch_showing=true;
    c.heap.state->sketch_closed=&window.closed;
    try {
        for(;;) {
            c.point();
            auto now=Clock::now();
            auto next=now+25ms;
            for(auto it=deadlines.begin();it!=deadlines.end();) {
                if(!d.timers.count(it->first))it=deadlines.erase(it);else ++it;
            }
            for(const auto& [id,timer]:d.timers) {
                const auto [it,inserted]=deadlines.emplace(id,now+std::chrono::milliseconds(timer.interval));
                (void)inserted;
                next=std::min(next,it->second);
            }
            if(playing)next=std::min(next,frame_at);
            for(const auto& event:window.receive(next)) {
                c.point();
                const char* name=event.kind==Message::click?"click":event.kind==Message::drag?"drag":
                    event.kind==Message::release?"release":event.kind==Message::key?"key":"";
                const auto registered=d.callbacks.find(name);
                if(registered!=d.callbacks.end()) {
                    exit_replay();
                    const auto fn=registered->second.callback;
                    if(event.kind==Message::key)callback(fn,{string(event.key)});
                    else callback(fn,{real(event.position[0]),real(event.position[1]),integer(event.button)});
                    publish();
                } else {
                    try {builtin(event);}
                    catch(const RuntimeError& e) {
                        if(e.code!="E203"&&e.code!="E204"&&e.code!="E208")throw;
                        if(editing->group)call("end_group",{edit_canvas});
                        window.caption(widen(e.what()));
                    }
                }
            }
            now=Clock::now();
            for(auto& [id,at]:deadlines)if(at<=now) {
                const auto entry=d.timers.find(id);
                if(entry==d.timers.end())continue;
                const auto timer=entry->second;
                exit_replay();
                callback(timer.callback,{});
                at=Clock::now()+std::chrono::milliseconds(timer.interval);
                publish();
            }
            if(playing&&now>=frame_at) {
                replay->seek(replay->position()+1);
                playing=replay->position()<replay->size();
                frame_at=now+std::chrono::milliseconds(editing->interval_ms);
                publish();
            }
        }
    } catch(const SketchSessionClosed&) {
        restore();
        for(std::size_t i=frames;i<c.calls.size();++i)if(c.calls[i]->lazy) {
            auto& lazy=c.object(c.calls[i]->function);lazy.state="NEW";lazy.failure.reset();
        }
        c.tasks.resize(pending);c.calls.resize(frames);c.query_items.resize(query_count);
        c.frame=saved_frame;c.current=saved_current;c.flow.clear();c.returned={};c.return_site=no_node;
        if(d.draft) {d.pens.at(d.draft->pen).state=std::move(d.draft->before);d.draft.reset();}
        if(d.group)call("end_group",{canvas_handle});
        if(editing!=&d&&editing->group)call("end_group",{edit_canvas});
        if(window.overflow)limited("event_queue",4096,4097);
        if(window.failed)return failure("GUI unavailable: native event loop failed");
        return success(c.null_);
    } catch(...) {
        restore();
        throw;
    }
}
}
