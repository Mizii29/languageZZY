"""Sketch ABI metadata only; importing this never constructs a document or GUI."""
from types import MappingProxyType
from .metadata import NativeFunction, NativeType

ABI = '1.0'
TYPES = MappingProxyType({name: NativeType('sketch.' + name, mutable, ownership, equality)
    for name, mutable, ownership, equality in (
        ('Canvas', True, 'ExecutionContext', 'identity'),
        ('Pen', True, 'ExecutionContext', 'identity'),
        ('Layer', True, 'ExecutionContext', 'identity'),
        ('Color', False, 'value', 'rgb'),
        ('Drawing', False, 'ExecutionContext', 'identity'))})
_SPEC = {
    'canvas': ('width height title', 'Int Int String', 'sketch.Canvas'),
    'pen': ('canvas name', 'sketch.Canvas String', 'sketch.Pen'),
    'rgb': ('r g b', 'Int Int Int', 'sketch.Color'),
    'background': ('canvas color', 'sketch.Canvas sketch.Color', 'Null'),
    'clear': ('canvas', 'sketch.Canvas', 'Null'),
    'begin_group': ('canvas label', 'sketch.Canvas String', 'Null'),
    'end_group': ('canvas', 'sketch.Canvas', 'Null'),
    'undo': ('canvas', 'sketch.Canvas', 'Bool'),
    'redo': ('canvas', 'sketch.Canvas', 'Bool'),
    'clear_history': ('canvas', 'sketch.Canvas', 'Null'),
    'frame_interval': ('canvas duration', 'sketch.Canvas Quantity', 'Null'),
    'capture': ('canvas', 'sketch.Canvas', 'sketch.Drawing'),
    'stamp': ('canvas drawing x y scale angle', 'sketch.Canvas sketch.Drawing Int|Float Int|Float Int|Float Int|Float', 'Int'),
    'drawing_text': ('drawing', 'sketch.Drawing', 'Result'),
    'drawing_from_json': ('content', 'String', 'Result'),
    'save_function': ('drawing path name', 'sketch.Drawing String String', 'Result'),
    'pick': ('canvas x y', 'sketch.Canvas Int|Float Int|Float', 'Int|Null'),
    'translate_object': ('canvas id dx dy', 'sketch.Canvas Int Int|Float Int|Float', 'Null'),
    'copy_object': ('canvas id', 'sketch.Canvas Int', 'Int'),
    'delete_object': ('canvas id', 'sketch.Canvas Int', 'Null'),
    'on_click': ('canvas handler', 'sketch.Canvas Function', 'Null'),
    'on_drag': ('canvas handler', 'sketch.Canvas Function', 'Null'),
    'on_release': ('canvas handler', 'sketch.Canvas Function', 'Null'),
    'on_key': ('canvas handler', 'sketch.Canvas Function', 'Null'),
    'every': ('canvas duration handler', 'sketch.Canvas Quantity Function', 'Int'),
    'cancel_timer': ('canvas id', 'sketch.Canvas Int', 'Bool'),
    'save_project': ('canvas path', 'sketch.Canvas String', 'Result'),
    'load_project': ('path', 'String', 'Result'),
    'save_png': ('canvas path', 'sketch.Canvas String', 'Result'),
    'show': ('canvas', 'sketch.Canvas', 'Result'),
    'add_layer': ('canvas name', 'sketch.Canvas String', 'sketch.Layer'),
    'set_layer': ('pen layer', 'sketch.Pen sketch.Layer', 'Null'),
    'layer_visible': ('layer visible', 'sketch.Layer Bool', 'Null'),
    'lock_layer': ('layer locked', 'sketch.Layer Bool', 'Null'),
    'rename_layer': ('layer name', 'sketch.Layer String', 'Null'),
    'move_layer': ('layer index', 'sketch.Layer Int', 'Null'),
    'layer_info': ('canvas', 'sketch.Canvas', 'Array'),
    'font': ('pen family', 'sketch.Pen String', 'Null'),
    'text_align': ('pen alignment', 'sketch.Pen String', 'Null'),
    'text': ('pen content size', 'sketch.Pen String Int|Float', 'Null'),
    'svg_text': ('canvas', 'sketch.Canvas', 'Result'),
    'save_svg': ('canvas path', 'sketch.Canvas String', 'Result'),
    'color': ('pen color', 'sketch.Pen sketch.Color', 'Null'),
    'fill_color': ('pen color', 'sketch.Pen sketch.Color', 'Null'),
    'width': ('pen width', 'sketch.Pen Int|Float', 'Null'),
    'position': ('pen', 'sketch.Pen', 'sketch.Position'),
    'heading': ('pen', 'sketch.Pen', 'Float'),
    'forward': ('pen distance', 'sketch.Pen Int|Float', 'Null'),
    'backward': ('pen distance', 'sketch.Pen Int|Float', 'Null'),
    'left': ('pen angle', 'sketch.Pen Int|Float', 'Null'),
    'right': ('pen angle', 'sketch.Pen Int|Float', 'Null'),
    'set_heading': ('pen angle', 'sketch.Pen Int|Float', 'Null'),
    'move_to': ('pen x y', 'sketch.Pen Int|Float Int|Float', 'Null'),
    'jump_to': ('pen x y', 'sketch.Pen Int|Float Int|Float', 'Null'),
    'circle': ('pen radius extent', 'sketch.Pen Int|Float Int|Float', 'Null'),
    'polyline': ('pen points', 'sketch.Pen Array', 'Null'),
    'bezier_to': ('pen c1x c1y c2x c2y x y', 'sketch.Pen ' + ' '.join(['Int|Float'] * 6), 'Null'),
    'dot': ('pen diameter', 'sketch.Pen Int|Float', 'Null'),
}
for _name in ('pen_up', 'pen_down', 'show_cursor', 'hide_cursor', 'home',
              'begin_fill', 'end_fill', 'cancel_fill'):
    _SPEC[_name] = ('pen', 'sketch.Pen', 'Null')
FUNCTIONS = MappingProxyType({ 'sketch.' + name: NativeFunction(
    'sketch.' + name, tuple(params.split()), returns,
    ('io',) if name in {'save_svg','save_project','load_project','save_function','save_png'} else
    ('callback',) if name == 'show' else
    ('read','allocate') if name in {'position','heading','svg_text','layer_info','capture','drawing_text','pick'} else
    ('allocate',) if name in {'canvas','pen','rgb','drawing_from_json'} else ('mutation',),
    ('E201', 'E202', 'E203', 'E204', 'E208', 'E211', 'E214'),
    tuple(tuple(t.split('|')) for t in kinds.split()))
    for name, (params, kinds, returns) in _SPEC.items()})
