"""Flatten closed EasyEDA circular-arc regions, bounded to 1 micrometre sagitta.

Input units are 10 mil (0.254 mm). Unsupported geometry is rejected, never
filtered into an apparently valid polygon. Copper/paste layers are retained.
"""
import math
import re

TOKEN = re.compile(r'[MLHVAZ]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?')
TOLERANCE = 0.001 / 0.254


def flatten_region(path: str) -> list[tuple[float, float]]:
    if len(path) > 50000:
        raise ValueError('区域路径过长')
    tokens, end = [], 0
    for match in TOKEN.finditer(path):
        if path[end:match.start()].strip(' ,\t\r\n'):
            raise ValueError('区域包含尚未支持的曲线指令')
        tokens.append(match.group())
        end = match.end()
    if path[end:].strip(' ,\t\r\n'):
        raise ValueError('区域路径含无效数据')
    points, index, command, closed = [], 0, '', False

    def numbers(count):
        nonlocal index
        if index + count > len(tokens):
            raise ValueError('区域指令参数不完整')
        try:
            values = [float(t) for t in tokens[index:index+count]]
        except ValueError as exc:
            raise ValueError('区域指令参数无效') from exc
        if any(not math.isfinite(v) or abs(v) > 1e8 for v in values):
            raise ValueError('区域坐标超出范围')
        index += count
        return values

    while index < len(tokens):
        if tokens[index] in {'M', 'L', 'H', 'V', 'A', 'Z'}:
            command = tokens[index]
            index += 1
        if closed:
            raise ValueError('暂不支持多个轮廓或区域内孔')
        if command == 'M':
            if points:
                raise ValueError('暂不支持多个轮廓或区域内孔')
            points.append(tuple(numbers(2)))
            command = 'L'
        elif not points:
            raise ValueError('区域必须从 M 指令开始')
        elif command == 'L':
            points.append(tuple(numbers(2)))
        elif command == 'H':
            points.append((numbers(1)[0], points[-1][1]))
        elif command == 'V':
            points.append((points[-1][0], numbers(1)[0]))
        elif command == 'A':
            rx, ry, rotation, large, sweep, ex, ey = numbers(7)
            if large not in (0, 1) or sweep not in (0, 1):
                raise ValueError('圆弧方向标志无效')
            if rx < 0 or ry < 0 or not math.isclose(rx, ry, abs_tol=1e-9) or rotation % 360:
                raise ValueError('暂不支持椭圆弧或旋转曲线区域')
            sx, sy = points[-1]
            if rx == 0:
                points.append((ex, ey))
                continue
            if (sx, sy) == (ex, ey):
                continue
            dx, dy = (sx-ex)/2, (sy-ey)/2
            distance2 = dx*dx + dy*dy
            radius = max(rx, math.sqrt(distance2))
            factor = math.sqrt(max(0, radius*radius/distance2 - 1))
            if large == sweep:
                factor = -factor
            cx, cy = (sx+ex)/2 + factor*dy, (sy+ey)/2 - factor*dx
            start = math.atan2(sy-cy, sx-cx)
            delta = (math.atan2(ey-cy, ex-cx) - start) % (2*math.pi)
            if not sweep:
                delta -= 2*math.pi
            step = min(math.pi/12, 2*math.acos(max(-1, 1-min(TOLERANCE/radius, 2))))
            segments = max(1, math.ceil(abs(delta)/max(step, 1e-9)))
            if segments > 10000:
                raise ValueError('圆弧过大，无法满足转换精度')
            for i in range(1, segments):
                angle = start + delta*i/segments
                points.append((cx+radius*math.cos(angle), cy+radius*math.sin(angle)))
            points.append((ex, ey))
        elif command == 'Z':
            if points[-1] != points[0]:
                points.append(points[0])
            closed = True
        else:
            raise ValueError('区域指令无效')
        if len(points) > 20000:
            raise ValueError('区域顶点过多')
    if not closed or len(set(points)) < 3:
        raise ValueError('区域轮廓未闭合或顶点不足')
    return points
