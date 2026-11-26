"""Recognize sampled oblongs without substituting arbitrary custom copper."""
import math


def native_oval(fields: list[str]) -> list[str]:
    """Return a native OVAL only when vertices and edges fit within 0.001 mm.

    This preserves an electrical pad (number, mask/paste generation and size),
    rather than replacing the copper by an unnumbered region plus small hotspot.
    """
    if len(fields) < 16 or fields[1] != 'POLYGON':
        raise ValueError('多边形焊盘数据不完整')
    try:
        cx, cy, width, height = map(float, fields[2:6])
        radius_hole = float(fields[9] or '0')
        rotation = float(fields[11] or '0')
        values = [float(v) for v in fields[10].split()]
    except ValueError as exc:
        raise ValueError('多边形焊盘坐标无效') from exc
    if any(not math.isfinite(v) or abs(v) > 1e8 for v in [cx,cy,width,height,radius_hole,rotation]+values):
        raise ValueError('多边形焊盘坐标超出范围')
    if radius_hole != 0 or fields[6] not in ('1', '2'):
        raise ValueError('暂不支持带孔或非表层自定义焊盘')
    if min(width, height) <= 0 or rotation % 90 or len(values) < 8 or len(values) % 2 or len(values) > 8192:
        raise ValueError('该自定义焊盘无法准确还原为原生椭圆焊盘')
    theta = math.radians(rotation)
    cosine, sine = math.cos(theta), math.sin(theta)
    points = [((x-cx)*cosine+(y-cy)*sine, -(x-cx)*sine+(y-cy)*cosine) for x,y in zip(values[::2],values[1::2])]
    if points[0] == points[-1]:
        points.pop()
    radius = min(width, height)/2
    half_segment = abs(height-width)/2
    tolerance = min(0.001/0.254, radius*0.005)

    def deviation(point):
        x, y = point
        along, across = (y, x) if height >= width else (x, y)
        return abs(math.hypot(across, max(abs(along)-half_segment, 0)) - radius)

    def minimum_spine_distance(a, b):
        # Exact minimum on each of the three projection intervals, rather than
        # sampling the midpoint (which can miss the worst part of a long edge).
        au, av = (a[1], a[0]) if height >= width else a
        bu, bv = (b[1], b[0]) if height >= width else b
        du, dv = bu-au, bv-av
        cuts = [0.0, 1.0]
        if du:
            cuts += [t for endpoint in (-half_segment,half_segment) if 0 < (t:=(endpoint-au)/du) < 1]
        cuts.sort()
        minimum = float('inf')
        for left,right in zip(cuts,cuts[1:]):
            middle = au+du*(left+right)/2
            center = half_segment if middle > half_segment else -half_segment
            u0, ud = (0,0) if abs(middle) <= half_segment else (au-center,du)
            denom = ud*ud+dv*dv
            t = max(left,min(right,-(u0*ud+av*dv)/denom)) if denom else left
            minimum = min(minimum,math.hypot(u0+ud*t,av+dv*t))
        return minimum

    # Vertices alone would accept crossed paths or large chords cutting corners.
    edges = list(zip(points, points[1:]+points[:1]))
    for a, b in edges:
        if deviation(a) > tolerance or abs(minimum_spine_distance(a,b)-radius) > tolerance:
            raise ValueError('暂不支持该自定义多边形焊盘：轮廓与原生椭圆不一致')
    signed_area = sum(a[0]*b[1]-b[0]*a[1] for a,b in edges)/2
    direction = 1 if signed_area > 0 else -1
    winding = sum((direction*(math.atan2(b[1],b[0])-math.atan2(a[1],a[0]))) % (2*math.pi) for a,b in edges)
    if not math.isclose(winding, 2*math.pi, abs_tol=1e-6):
        raise ValueError('自定义焊盘轮廓交叉或顶点顺序无效')
    expected_area = 4*half_segment*radius + math.pi*radius*radius
    perimeter = 4*half_segment+2*math.pi*radius
    if abs(abs(signed_area)-expected_area) > perimeter*tolerance:
        raise ValueError('自定义焊盘面积与原生椭圆不一致')
    result = fields.copy()
    result[1] = 'OVAL'
    return result
