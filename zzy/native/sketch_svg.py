"""Headless SVG from canonical geometry; no renderer or font dependency."""
from . import files


def rgb(color):
    return '#%02x%02x%02x' % color


def number(value):
    # repr preserves the model's finite double; SVG accepts exponent notation.
    return '0' if value == 0 else repr(value)


def escaped(text):
    for char in text:
        cp = ord(char)
        if not (cp in (9, 10, 13) or 32 <= cp <= 0xd7ff or 0xe000 <= cp <= 0xfffd or 0x10000 <= cp <= 0x10ffff):
            raise ValueError('SVG text contains a character forbidden by XML 1.0')
        yield {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;', '\r': '&#13;'}.get(char, char)


def path(points, closed=False):
    for i, (x, y) in enumerate(points):
        yield ('M' if i == 0 else ' L') + number(x) + ' ' + number(-y)
    if closed:
        yield ' Z'


def fragments(canvas):
    w, h = canvas.width, canvas.height
    yield f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n<title>'
    yield from escaped(canvas.title)
    yield '</title>\n'
    yield f'<defs><clipPath id="canvas-clip"><rect width="{w}" height="{h}"/></clipPath></defs>\n'
    yield f'<rect width="{w}" height="{h}" fill="{rgb(canvas.background)}"/>\n'
    yield f'<g clip-path="url(#canvas-clip)"><g transform="translate({number(w / 2)} {number(h / 2)})">\n'
    for block in canvas.objects:
        g = block.geometry
        yield f'<g id="object-{g.id}">'
        if g.boundary:
            yield '<path d="'
            yield from path(g.boundary, True)
            yield f'" fill="{rgb(g.fill)}" fill-rule="evenodd" stroke="none"/>'
        if g.kind == 'dot':
            yield f'<circle cx="{number(g.center[0])}" cy="{number(-g.center[1])}" r="{number(g.diameter / 2)}" fill="{rgb(g.fill)}"/>'
        for s in g.strokes:
            yield '<path d="'
            yield from path(s.points)
            yield f'" fill="none" stroke="{rgb(s.color)}" stroke-width="{number(s.width)}" stroke-linecap="round" stroke-linejoin="round"/>'
        yield '</g>\n'
    yield '</g></g>\n</svg>\n'


def export(runtime, node, canvas, target=None):
    # Fragment checks precede accumulation. Account list references and text,
    # then hold scratch through the joined String allocation and publication.
    chunks, owners = [], []
    count = size = 0
    try:
        for part in fragments(canvas):
            runtime.meter.cancellation.check()
            count += len(part)
            size += len(part.encode('utf-8'))
            runtime.check('text_codepoints', count, node)
            runtime.check('io_payload_bytes', size, node)
            owners.append(runtime.reserve(node, runtime_slots=2, runtime_payload_bytes=4 * len(part)))
            chunks.append(part)
        with runtime.reserve(node, runtime_payload_bytes=4 * count):
            value = runtime.scalar('String', ''.join(chunks), node)
        if target is not None:
            return files.invoke(runtime, 'io.write_atomic', [target, value], node)
        return runtime.result(True, value, node)
    except (ValueError, UnicodeError) as error:
        return runtime.result(False, runtime.scalar('String', str(error), node), node)
    finally:
        for owner in owners:
            owner.release()
