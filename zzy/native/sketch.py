"""Owned headless geometry. No UI, filesystem, history or public reflection.

Paths are immutable, uniformly flattened logical-coordinate polylines. A whole
call prepares its state, geometry and accounting before publishing anything.
"""
from dataclasses import dataclass, replace
import math
from threading import get_ident
from types import MappingProxyType

from ..diagnostics import Phase, ResourceExceeded
from ..values import NULL, Value
from .sketch_metadata import TYPES

LIMITS = MappingProxyType(dict(coordinate_abs=1_000_000, angle_abs=1_000_000,
    canvas_dimension=32768, style_size=10000, batch_points=10000,
    curve_segments=65536, path_segments=1_000_000, objects=100000, pens=256, layers=256))
CURVE_ERROR = 0.25  # Maximum logical-unit chord deviation; shared by all renderers.


def capacity(runtime, node, key, count):
    runtime.meter.cancellation.check()
    limit = LIMITS[key]
    if count > limit:
        raise ResourceExceeded('sketch.' + key, limit, count, Phase.EXECUTION,
                               runtime.location(node), node.token.span)


def number(runtime, node, value, key='coordinate_abs', positive=False):
    if value.kind not in {'Int', 'Float'}:
        runtime.error(node, 'E201', 'sketch 数值不接受 Bool 或其他类型')
    # Check huge Int before float conversion, including host-injected infinities.
    if not -LIMITS[key] <= value.data <= LIMITS[key] or positive and value.data <= 0:
        runtime.error(node, 'E208', 'sketch 数值超出 ' + key + ' 范围')
    return float(value.data)


def point(runtime, node, x, y):
    if not all(math.isfinite(n) and abs(n) <= LIMITS['coordinate_abs'] for n in (x, y)):
        runtime.error(node, 'E208', 'sketch 派生坐标超范围')
    return (float(x), float(y))


@dataclass(frozen=True)
class PenState:
    position: tuple = (0.0, 0.0)
    heading: float = 0.0
    down: bool = True
    color: tuple = (0, 0, 0)
    fill: tuple = (0, 0, 0)
    width: float = 1.0
    cursor: bool = True
    font: str = "sans-serif"
    align: str = "left"


@dataclass(frozen=True)
class Stroke:
    points: tuple
    color: tuple
    width: float


@dataclass(frozen=True)
class Geometry:
    id: int
    kind: str
    strokes: tuple = ()
    boundary: tuple = ()
    fill: tuple | None = None
    center: tuple | None = None
    diameter: float = 0.0
    fill_rule: str = 'evenodd'
    layer: int = 0
    text: str = ''
    font: str = 'sans-serif'
    align: str = 'left'
    size: float = 12.0


class Block:
    """One accounted immutable geometry payload; future history may share it."""
    def __init__(self, geometry, segments, reservation):
        self.geometry, self.segments, self.reservation = geometry, segments, reservation

    def __del__(self):
        self.reservation.release()


class Handle(Value):
    def __init__(self, name, runtime, node, slots=0, payload=0):
        super().__init__('sketch.' + name, None, runtime.reserve(node,
                         runtime_objects=1, runtime_slots=slots, runtime_payload_bytes=payload))
        self.native_type = TYPES[name]
        self.context = runtime.native_context
        self.thread = get_ident()
        self.frozen = False

    def freeze_native(self, runtime, node):
        guard(runtime, node, self)
        self.frozen = True


class Layer(Handle):
    def __init__(self, canvas, runtime, node, name="default", identity=0):
        super().__init__('Layer', runtime, node, slots=1, payload=4 * len(name))
        self.canvas, self.name, self.locked, self.visible = canvas, name, False, True
        self.id = identity


class Canvas(Handle):
    def __init__(self, width, height, title, runtime, node):
        super().__init__('Canvas', runtime, node, slots=2, payload=4 * len(title) + 32)
        self.width, self.height, self.title = width, height, title
        self.background = (255, 255, 255)
        self.pens, self.objects = {}, []
        self.segments, self.next_id = 0, 1
        self.draft = None
        self.alive = True
        self.layer = Layer(self, runtime, node)
        self.layers = [self.layer]
        self.next_layer = 1
        self.history=[];self.redo_history=[];self.group=None;self.group_label=""
        self.history_bytes=0;self.history_count=0;self.interval_ms=40
        runtime.native_canvases.add(self)

    def cleanup(self):
        if self.draft is not None:
            self.draft.pen.state = self.draft.before
            self.draft = None
        self.group=None;self.history.clear();self.redo_history.clear()
        self.alive = False


class Pen(Handle):
    def __init__(self, canvas, name, runtime, node):
        super().__init__('Pen', runtime, node, slots=3, payload=4 * len(name) + 128)
        self.canvas, self.layer, self.name = canvas, canvas.layer, name
        self.state = PenState()


class Draft:
    def __init__(self, pen, runtime, node):
        self.pen, self.before, self.color = pen, pen.state, pen.state.fill
        self.blocks = []
        self.segments = 0
        self.reservation = runtime.reserve(node, runtime_objects=1, runtime_slots=3, runtime_payload_bytes=128)

    def __del__(self):
        self.reservation.release()


def guard(runtime, node, handle, write=False):
    canvas = handle if handle.kind == 'sketch.Canvas' else handle.canvas
    if (handle.context is not runtime.native_context or handle.thread != get_ident()
            or not canvas.alive):
        runtime.error(node, 'E203', 'sketch 句柄不属于当前执行上下文/线程')
    if isinstance(handle, Pen) and handle.layer.canvas is not canvas:
        runtime.error(node, 'E203', '画笔和图层不属于同一画布')
    if write and (handle.frozen or canvas.frozen
                  or isinstance(handle, Pen) and (handle.layer.frozen or handle.layer.locked)):
        runtime.error(node, 'E203', 'sketch 画布、画笔或图层只读')
    return canvas


def ready(runtime, node, canvas, pen=None, allowed=False):
    if canvas.draft is not None and not (allowed and canvas.draft.pen is pen):
        runtime.error(node, 'E214', '活动填充只允许当前画笔的连续路径、转向和描边样式')


def prepare_block(runtime, node, canvas, strokes=(), *, boundary=(), fill=None,
                  kind='path', center=None, diameter=0.0, layer=0, text='', font='sans-serif', align='left', size=12.0):
    segments = sum(max(0, len(s.points) - 1) for s in strokes)
    if kind in {'dot', 'text'}:
        segments = 1
    pending = canvas.draft.segments if canvas.draft else 0
    capacity(runtime, node, 'path_segments', canvas.segments + pending + segments)
    capacity(runtime, node, 'objects', len(canvas.objects) + 1)
    points = sum(len(s.points) for s in strokes) + len(boundary)
    owner = runtime.reserve(node, runtime_objects=1,
        runtime_slots=4 + len(strokes) + points,
        runtime_payload_bytes=128 + 48 * len(strokes) + 16 * points + 4 * (len(text) + len(font)))
    try:
        geometry = Geometry(canvas.next_id, kind, strokes, boundary, fill, center, diameter, layer=layer, text=text, font=font, align=align, size=size)
        return Block(geometry, segments, owner)
    except BaseException:
        owner.release()
        raise


def publish(runtime, node, pen, state, points=()):
    canvas = pen.canvas
    block = None
    if len(points) > 1 and pen.state.down:
        stroke = Stroke(tuple(points), pen.state.color, pen.state.width)
        block = prepare_block(runtime, node, canvas, (stroke,), layer=pen.layer.id)
    runtime.meter.cancellation.check()
    if block is not None:
        if canvas.draft is not None:
            count = canvas.draft.segments + block.segments
            canvas.draft.blocks.append(block)
            canvas.draft.segments = count
        else:
            count, next_id = canvas.segments + block.segments, canvas.next_id + 1
            canvas.objects.append(block)
            canvas.segments, canvas.next_id = count, next_id
    pen.state = state


def arc(runtime, node, state, radius, extent):
    center = point(runtime, node,
        state.position[0] - math.sin(math.radians(state.heading)) * radius,
        state.position[1] + math.cos(math.radians(state.heading)) * radius)
    angle = math.copysign(1, radius) * extent
    # Stable sagitta formula avoids acos(1 - epsilon) cancellation.
    step = min(math.pi / 2, 4 * math.asin(min(1.0, math.sqrt(CURVE_ERROR / (2 * abs(radius))))))
    count = max(1, math.ceil(abs(math.radians(angle)) / step))
    capacity(runtime, node, 'curve_segments', count)
    with runtime.reserve(node, runtime_slots=count + 1, runtime_payload_bytes=16 * (count + 1)):
        start = state.position
        dx, dy = start[0] - center[0], start[1] - center[1]
        points = [start]
        for i in range(1, count + 1):
            runtime.meter.cancellation.check()
            theta = math.radians(angle * i / count)
            points.append(point(runtime, node, center[0] + dx * math.cos(theta) - dy * math.sin(theta),
                                center[1] + dx * math.sin(theta) + dy * math.cos(theta)))
        full = extent % 360 == 0
        if full:
            points[-1] = start
        new = replace(state, position=points[-1], heading=state.heading if full else (state.heading + angle) % 360)
        # Caller must retain scratch until its own geometry allocation is complete.
        return tuple(points), new


def chord_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length)) if length else 0.0
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def bezier(runtime, node, start, c1, c2, end):
    pending = [(start, c1, c2, end, 0)]
    points = [start]
    while pending:
        runtime.meter.cancellation.check()
        a, b, c, d, depth = pending.pop()
        if max(chord_distance(b, a, d), chord_distance(c, a, d)) <= CURVE_ERROR:
            capacity(runtime, node, 'curve_segments', len(points))
            points.append(d)
        else:
            if depth == 24:
                raise ResourceExceeded('sketch.curve_depth', 24, 25, Phase.EXECUTION,
                                       runtime.location(node), node.token.span)
            def mid(p, q):
                return ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            ab, bc, cd = mid(a, b), mid(b, c), mid(c, d)
            abc, bcd = mid(ab, bc), mid(bc, cd)
            middle = mid(abc, bcd)
            pending.extend(((middle, bcd, cd, d, depth + 1), (a, ab, abc, middle, depth + 1)))
    return tuple(points)


def _invoke(runtime, name, args, node):
    if runtime.native_thread != get_ident():
        runtime.error(node, 'E203', 'sketch 原生调用不属于当前执行线程')
    op = name.removeprefix('sketch.')
    if op == 'rgb':
        if any(not 0 <= arg.data <= 255 for arg in args):
            runtime.error(node, 'E208', 'RGB 分量必须为 0..255')
        result = Value('sketch.Color', tuple(a.data for a in args),
                       runtime.reserve(node, runtime_objects=1, runtime_payload_bytes=3))
        result.native_type, result.frozen = TYPES['Color'], True
        return result
    if op == 'canvas':
        if any(not 1 <= arg.data <= LIMITS['canvas_dimension'] for arg in args[:2]):
            runtime.error(node, 'E208', '画布宽高必须为 1..32768')
        return Canvas(args[0].data, args[1].data, args[2].data, runtime, node)
    handle = args[0]
    canvas = guard(runtime, node, handle, write=op not in {'position', 'heading', 'svg_text', 'save_svg', 'layer_info', 'show'})
    pen = handle if isinstance(handle, Pen) else None
    if op in {'position', 'heading'}:
        if op == 'heading':
            return runtime.scalar('Float', pen.state.heading, node)
        definition = runtime.field(runtime.lookup('sketch', node).value, 'Position', node)
        owner = runtime.reserve(node, runtime_objects=1, runtime_slots=3)
        try:
            fields = dict(x=runtime.scalar('Float', pen.state.position[0], node),
                          y=runtime.scalar('Float', pen.state.position[1], node))
            result = Value('Shape', (definition, fields), owner)
            result.frozen = True
            return result
        except BaseException:
            owner.release()
            raise
    permitted = op in {'forward', 'backward', 'left', 'right', 'set_heading', 'move_to',
                       'home', 'circle', 'polyline', 'bezier_to', 'color', 'width', 'end_fill', 'cancel_fill'}
    ready(runtime, node, canvas, pen, permitted)
    if op in {'svg_text', 'save_svg'}:
        from .sketch_history import idle
        idle(runtime,canvas,node)
        from .sketch_svg import export
        return export(runtime, node, canvas, args[1] if op == 'save_svg' else None)
    if op in {'add_layer', 'set_layer', 'layer_visible', 'lock_layer', 'rename_layer', 'move_layer', 'layer_info', 'font', 'text_align', 'text'}:
        from .sketch_layers import invoke as layer_call
        return layer_call(runtime, op, args, node, canvas, pen)
    if op == 'pen':
        label = args[1].data
        if not label or label in canvas.pens:
            runtime.error(node, 'E208', '画笔名必须非空且唯一')
        capacity(runtime, node, 'pens', len(canvas.pens) + 1)
        created = Pen(canvas, label, runtime, node)
        canvas.pens[label] = created
        return created
    if op == 'background':
        canvas.background = args[1].data
        return NULL
    if op == 'clear':
        if any(layer.frozen or layer.locked for layer in canvas.layers):
            runtime.error(node, 'E203', '图层只读')
        canvas.objects.clear()
        canvas.segments = 0
        return NULL
    state = pen.state
    if op == 'begin_fill':
        if not state.down:
            runtime.error(node, 'E214', '填充要求落笔')
        canvas.draft = Draft(pen, runtime, node)
        return NULL
    if op in {'end_fill', 'cancel_fill'}:
        draft = canvas.draft
        if draft is None:
            runtime.error(node, 'E214', '没有配对的 begin_fill')
        if op == 'cancel_fill':
            pen.state, canvas.draft = draft.before, None
            return NULL
        # Only retain three distinct vertices to validate the minimum; do not
        # allocate an unaccounted set proportional to the whole contour.
        vertices = set()
        for block in draft.blocks:
            for p in block.geometry.strokes[0].points:
                runtime.meter.cancellation.check()
                vertices.add(p)
                if len(vertices) == 3:
                    break
            if len(vertices) == 3:
                break
        if len(vertices) < 3:
            runtime.error(node, 'E214', '填充至少需要三个不同顶点')
        size = sum(len(b.geometry.strokes[0].points) for b in draft.blocks)
        with runtime.reserve(node, runtime_slots=size + len(draft.blocks), runtime_payload_bytes=16 * size):
            strokes = tuple(b.geometry.strokes[0] for b in draft.blocks)
            boundary = tuple(p for i, s in enumerate(strokes) for p in s.points[(1 if i else 0):])
            # Draft counts are replaced, not added twice, at commit.
            capacity(runtime, node, 'path_segments', canvas.segments + draft.segments)
            owner = runtime.reserve(node, runtime_objects=1, runtime_slots=4 + size + len(strokes),
                                    runtime_payload_bytes=128 + 48 * len(strokes) + 32 * size)
            try:
                block = Block(Geometry(canvas.next_id, 'fill', strokes, boundary, draft.color, layer=pen.layer.id), draft.segments, owner)
                count, next_id = canvas.segments + draft.segments, canvas.next_id + 1
                runtime.meter.cancellation.check()
                canvas.objects.append(block)
            except BaseException:
                owner.release()
                raise
        canvas.segments, canvas.next_id, canvas.draft = count, next_id, None
        return NULL
    if op in {'color', 'fill_color', 'width', 'pen_up', 'pen_down', 'show_cursor', 'hide_cursor'}:
        if op == 'color': new = replace(state, color=args[1].data)
        elif op == 'fill_color': new = replace(state, fill=args[1].data)
        elif op == 'width': new = replace(state, width=number(runtime, node, args[1], 'style_size', True))
        elif op in {'pen_up', 'pen_down'}: new = replace(state, down=op == 'pen_down')
        else: new = replace(state, cursor=op == 'show_cursor')
        publish(runtime, node, pen, new)
        return NULL
    if op in {'left', 'right', 'set_heading'}:
        angle = number(runtime, node, args[1], 'angle_abs')
        heading = angle if op == 'set_heading' else state.heading + (angle if op == 'left' else -angle)
        publish(runtime, node, pen, replace(state, heading=heading % 360))
        return NULL
    if op == 'dot':
        diameter = number(runtime, node, args[1], 'style_size', True)
        x, y = state.position
        point(runtime, node, x - diameter / 2, y - diameter / 2)
        point(runtime, node, x + diameter / 2, y + diameter / 2)
        block = prepare_block(runtime, node, canvas, kind='dot', center=state.position,
                              diameter=diameter, fill=state.color, layer=pen.layer.id)
        count, next_id = canvas.segments + 1, canvas.next_id + 1
        runtime.meter.cancellation.check()
        canvas.objects.append(block)
        canvas.segments, canvas.next_id = count, next_id
        return NULL
    if op == 'circle':
        radius, extent = number(runtime, node, args[1]), number(runtime, node, args[2], 'angle_abs')
        if not radius:
            runtime.error(node, 'E208', '圆弧半径不能为零')
        if not extent:
            return NULL
    if op == 'polyline' and not args[1].data:
        return NULL
    # Curve scratch is bounded before allocation and retained through publish.
    scratch = LIMITS['curve_segments'] + 1 if op in {'circle', 'bezier_to'} else 0
    if op == 'polyline':
        capacity(runtime, node, 'batch_points', len(args[1].data))
        scratch = len(args[1].data) + 1
    with runtime.reserve(node, runtime_slots=scratch + 32, runtime_payload_bytes=16 * scratch + 2048):
        if op in {'forward', 'backward'}:
            distance = number(runtime, node, args[1]) * (-1 if op == 'backward' else 1)
            theta = math.radians(state.heading)
            end = point(runtime, node, state.position[0] + distance * math.cos(theta),
                        state.position[1] + distance * math.sin(theta))
            points, new = (state.position, end), replace(state, position=end)
        elif op in {'move_to', 'jump_to', 'home'}:
            end = (0.0, 0.0) if op == 'home' else tuple(number(runtime, node, v) for v in args[1:])
            points = () if op == 'jump_to' else (state.position, end)
            new = replace(state, position=end, heading=0.0 if op == 'home' else state.heading)
        elif op == 'circle':
            points, new = arc(runtime, node, state, radius, extent)
        elif op == 'polyline':
            points = [state.position]
            for pair in args[1].data:
                runtime.meter.cancellation.check()
                if pair.kind != 'Array' or len(pair.data) != 2:
                    runtime.error(node, 'E201', '折线点必须是两个数值的 Array')
                points.append(tuple(number(runtime, node, v) for v in pair.data))
            if len(points) == 1:
                return NULL
            new = replace(state, position=points[-1])
        elif op == 'bezier_to':
            coords = [number(runtime, node, v) for v in args[1:]]
            c1, c2, end = tuple(coords[:2]), tuple(coords[2:4]), tuple(coords[4:])
            points = bezier(runtime, node, state.position, c1, c2, end)
            new = replace(state, position=end)
        else:
            raise AssertionError('unimplemented sketch ABI: ' + name)
        publish(runtime, node, pen, new, points)
    return NULL


_READ = {'position','heading','svg_text','save_svg','layer_info','show'}
_NO_HISTORY = _READ | {'canvas','pen','rgb','begin_fill','cancel_fill','show_cursor','hide_cursor'}

def invoke(runtime,name,args,node):
    op=name.removeprefix('sketch.')
    if op in _NO_HISTORY:
        return _invoke(runtime,name,args,node)
    from .sketch_history import Edit, operate, interval
    c=guard(runtime,node,args[0],write=op!='frame_interval')
    if op in {'begin_group','end_group','undo','redo','clear_history'}:
        return operate(runtime,c,node,op,args)
    if op=='frame_interval':
        guard(runtime,node,args[0],write=True)
        ready(runtime,node,c)
        c.interval_ms=interval(runtime,node,args[1]);return NULL
    edit=Edit(runtime,c,node,op,args[0]) if c.draft is None or op=='end_fill' else None
    result=_invoke(runtime,name,args,node)
    if edit is not None:edit.finish()
    return result
