#pragma once
#include "core_hosts.hpp"
namespace zzy {
inline constexpr CoreHost sketch_hosts[]={
    {"sketch.canvas",3,{"Int","Int","String"}}, {"sketch.pen",2,{"sketch.Canvas","String"}},
    {"sketch.rgb",3,{"Int","Int","Int"}}, {"sketch.background",2,{"sketch.Canvas","sketch.Color"}},
    {"sketch.clear",1,{"sketch.Canvas"}}, {"sketch.begin_group",2,{"sketch.Canvas","String"}},
    {"sketch.end_group",1,{"sketch.Canvas"}}, {"sketch.undo",1,{"sketch.Canvas"}},
    {"sketch.redo",1,{"sketch.Canvas"}}, {"sketch.clear_history",1,{"sketch.Canvas"}},
    {"sketch.save_png",2,{"sketch.Canvas","String"}}, {"sketch.show",1,{"sketch.Canvas"}},
    {"sketch.add_layer",2,{"sketch.Canvas","String"}}, {"sketch.set_layer",2,{"sketch.Pen","sketch.Layer"}},
    {"sketch.layer_visible",2,{"sketch.Layer","Bool"}}, {"sketch.lock_layer",2,{"sketch.Layer","Bool"}},
    {"sketch.rename_layer",2,{"sketch.Layer","String"}}, {"sketch.move_layer",2,{"sketch.Layer","Int"}},
    {"sketch.layer_info",1,{"sketch.Canvas"}}, {"sketch.font",2,{"sketch.Pen","String"}},
    {"sketch.text_align",2,{"sketch.Pen","String"}}, {"sketch.text",3,{"sketch.Pen","String","Int|Float"}},
    {"sketch.svg_text",1,{"sketch.Canvas"}}, {"sketch.save_svg",2,{"sketch.Canvas","String"}},
    {"sketch.color",2,{"sketch.Pen","sketch.Color"}}, {"sketch.fill_color",2,{"sketch.Pen","sketch.Color"}},
    {"sketch.width",2,{"sketch.Pen","Int|Float"}}, {"sketch.position",1,{"sketch.Pen"}},
    {"sketch.heading",1,{"sketch.Pen"}}, {"sketch.forward",2,{"sketch.Pen","Int|Float"}},
    {"sketch.backward",2,{"sketch.Pen","Int|Float"}}, {"sketch.left",2,{"sketch.Pen","Int|Float"}},
    {"sketch.right",2,{"sketch.Pen","Int|Float"}}, {"sketch.set_heading",2,{"sketch.Pen","Int|Float"}},
    {"sketch.move_to",3,{"sketch.Pen","Int|Float","Int|Float"}}, {"sketch.jump_to",3,{"sketch.Pen","Int|Float","Int|Float"}},
    {"sketch.circle",3,{"sketch.Pen","Int|Float","Int|Float"}}, {"sketch.polyline",2,{"sketch.Pen","Array"}},
    {"sketch.bezier_to",7,{"sketch.Pen","Int|Float","Int|Float","Int|Float","Int|Float","Int|Float","Int|Float"}},
    {"sketch.dot",2,{"sketch.Pen","Int|Float"}}, {"sketch.pen_up",1,{"sketch.Pen"}},
    {"sketch.pen_down",1,{"sketch.Pen"}}, {"sketch.show_cursor",1,{"sketch.Pen"}},
    {"sketch.hide_cursor",1,{"sketch.Pen"}}, {"sketch.home",1,{"sketch.Pen"}},
    {"sketch.begin_fill",1,{"sketch.Pen"}}, {"sketch.end_fill",1,{"sketch.Pen"}},
    {"sketch.cancel_fill",1,{"sketch.Pen"}},
};
}
