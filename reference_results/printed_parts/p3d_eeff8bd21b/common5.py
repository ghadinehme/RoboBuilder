import cadquery as cq

def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))

def prism_xz(pts, y0, y1):
    w = cq.Workplane("XZ").polyline(pts).close().extrude(-(y1 - y0))
    return w.translate((0, y0, 0))

AX_Y = 28.0
MX, MZ = 24.0, 21.6           # driven middle axles (56145c01 + L motor direct)
EX, EZ = 157.8, 24.6          # chain-driven end axles (56145c01, raised 3 mm)
JOIN_X = (104.0, 112.0)
JOIN_Z = (38.4, 48.0)
PLOW_DX = -18.0
PLOW_PINS = ((192.0 + PLOW_DX, 28.8), (192.0 + PLOW_DX, 44.8))
