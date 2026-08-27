"""행성 표면 텍스처 생성.

출력: 1024x512 등장방형(equirectangular) JPEG.
구체에 감기므로 좌우가 이어져야 한다. 노이즈 격자의 마지막 열을 첫 열로
복제해서 이음새를 없앴다.

좌표를 인자로 받는 샘플러(sample/fbm)를 쓰기 때문에 좌표 자체를 다른
노이즈로 밀어서(domain warping) 소용돌이를 만들 수 있다. 목성 띠의
난류가 이 방식이다.

조명은 3D 엔진이 계산한다. 여기서는 반사율(albedo)만 다루고
음영은 굽지 않는다.

    python3 generate_textures.py [출력디렉터리]
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

W, H = 1024, 512
OUT = sys.argv[1] if len(sys.argv) > 1 else "textures"

# u는 경도(0~1, 순환), v는 위도(0=북극, 1=남극)
U = np.tile(np.linspace(0, 1, W, endpoint=False), (H, 1))
V = np.tile(np.linspace(0, 1, H)[:, None], (1, W))
LAT = 1 - 2 * V                      # +1 북극 ~ -1 남극


def make_grid(cx, cy, gen):
    g = gen.random((cy + 1, cx))
    return np.concatenate([g, g[:, :1]], axis=1)      # 경도 이음새 제거


def sample(g, x, y, cx, cy):
    """격자를 실수 좌표에서 이중선형 보간. x는 순환, y는 고정."""
    x = np.mod(x, cx)
    y = np.clip(y, 0, cy)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    fx = x - x0
    fy = y - y0
    fx = fx * fx * (3 - 2 * fx)                       # smoothstep
    fy = fy * fy * (3 - 2 * fy)
    x1 = x0 + 1
    y1 = np.minimum(y0 + 1, cy)
    a = g[y0, x0]; b = g[y0, x1]
    c = g[y1, x0]; d = g[y1, x1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(u, v, base=4, octaves=6, gain=0.5, aspect=0.5, seed=0):
    """aspect가 크면 위도 방향 셀이 많아져 가로로 늘어진 무늬가 된다."""
    gen = np.random.default_rng(90210 + seed)
    out = np.zeros_like(u)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        cx = int(base * 2 ** o)
        cy = max(2, int(base * aspect * 2 ** o))
        out += amp * sample(make_grid(cx, cy, gen), u * cx, v * cy, cx, cy)
        norm += amp
        amp *= gain
    return out / norm


def ramp(t, stops):
    """0~1 값을 색 구간표로 변환."""
    pos = [s[0] for s in stops]
    cols = np.array([s[1] for s in stops], dtype=float) / 255
    out = np.zeros(t.shape + (3,))
    out[t <= pos[0]] = cols[0]
    out[t >= pos[-1]] = cols[-1]
    for i in range(len(stops) - 1):
        lo, hi = pos[i], pos[i + 1]
        m = (t > lo) & (t < hi)
        if m.any():
            f = ((t[m] - lo) / (hi - lo))[:, None]
            out[m] = cols[i] * (1 - f) + cols[i + 1] * f
    return out


def wrap_dist(cx, cy, r_scale=1.0):
    """중심에서의 거리. 경도 방향은 순환하고, 위도가 높을수록 가로로 늘어난다."""
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    dx = np.minimum(np.abs(xx - cx), W - np.abs(xx - cx))
    stretch = 1.0 / np.maximum(np.cos((cy / H - 0.5) * np.pi * 0.86), 0.25)
    return np.sqrt((dx / stretch) ** 2 + (yy - cy) ** 2) / r_scale


def craters(img, count, seed, rmin=3, rmax=44, depth=0.4, rays=0):
    """분화구. 크기 분포는 멱법칙 — 작은 것이 압도적으로 많다."""
    gen = np.random.default_rng(seed)
    picks = []
    for _ in range(count):
        cx = gen.integers(0, W)
        cy = int(np.clip(gen.normal(H / 2, H / 3.2), 10, H - 10))
        r = rmin + (rmax - rmin) * gen.random() ** 3.4
        picks.append((cx, cy, r))
    picks.sort(key=lambda p: -p[2])                   # 큰 것부터 그려 겹침이 자연스럽게

    for idx, (cx, cy, r) in enumerate(picks):
        d = wrap_dist(cx, cy, r)
        if not (d < 1.2).any():
            continue
        k = min(1.0, r / 24.0)
        shade = np.zeros((H, W))
        floor = d < 0.88
        shade[floor] = -depth * k * (1 - (d[floor] / 0.88) ** 2) ** 0.55
        rim = (d >= 0.88) & (d < 1.02)
        shade[rim] += depth * k * 0.26 * np.cos((d[rim] - 0.95) * 22)
        # 큰 분화구 몇 개는 방사상 분출물을 남긴다
        if idx < rays and r > rmax * 0.55:
            yy, xx = np.mgrid[0:H, 0:W].astype(float)
            ang = np.arctan2(yy - cy, np.mod(xx - cx + W / 2, W) - W / 2)
            spokes = fbm(np.mod(ang / (2 * np.pi) + 0.5, 1.0), np.clip(d / 4, 0, 1),
                         base=7, octaves=3, aspect=0.6, seed=70 + idx)
            band = (d > 1.0) & (d < 3.2)
            fall = np.clip((3.2 - d) / 2.2, 0, 1) ** 1.8
            shade[band] += (0.15 * k * spokes * fall)[band]
        img += shade[:, :, None] * 0.44
    return img


def oval(img, cx, cy, rx, ry, color, strength=1.0, swirl=0.0):
    """타원형 소용돌이. 목성의 대적점과 백색 타원용."""
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    dx = np.mod(xx - cx + W / 2, W) - W / 2
    dy = yy - cy
    if swirl:
        a = np.arctan2(dy, dx) + swirl * np.exp(-((dx / rx) ** 2 + (dy / ry) ** 2))
        rr = np.sqrt(dx ** 2 + dy ** 2)
        dx, dy = rr * np.cos(a), rr * np.sin(a)
    d = np.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
    m = (np.clip(1 - d, 0, 1) ** 0.75 * strength)[:, :, None]
    return img * (1 - m) + np.array(color, dtype=float) / 255 * m


def polar_fade(img, amount=0.28, power=3.0, tint=(0.62, 0.66, 0.74)):
    """극지방을 살짝 눌러 구체감을 준다."""
    k = (np.abs(LAT) ** power * amount)[:, :, None]
    return img * (1 - k) + np.array(tint) * k * 0.9


def save(img, name):
    a = np.clip(img, 0, 1) ** (1 / 1.03)              # 아주 약한 감마 보정
    im = Image.fromarray((a * 255).astype(np.uint8), "RGB")
    im = im.filter(ImageFilter.GaussianBlur(0.35))
    path = os.path.join(OUT, name)
    im.save(path, quality=90, optimize=True, subsampling=1)
    lum = (0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]).mean()
    print(f"{name:14s} {im.size[0]}x{im.size[1]}  평균 밝기 {lum * 100:.0f}%  "
          f"{os.path.getsize(path) / 1024:.0f}KB")


os.makedirs(OUT, exist_ok=True)

# ---------------- 달 ----------------
# 밝은 고지대에 어두운 현무암 바다가 얹히고, 그 위를 분화구가 덮는다.
n = fbm(U, V, base=3, octaves=7, seed=1)
img = ramp(n, [(0.00, (128, 124, 118)), (0.42, (168, 164, 156)),
               (0.68, (200, 195, 186)), (1.00, (228, 223, 214))])
maria = fbm(U, V, base=2, octaves=4, seed=20)
m = np.clip((0.48 - maria) / 0.16, 0, 1) ** 1.1
img *= (1 - 0.4 * m)[:, :, None]
img += (fbm(U, V, base=30, octaves=3, seed=2)[:, :, None] - 0.5) * 0.045
img = craters(img, 190, seed=11, rmin=3, rmax=48, depth=0.3, rays=4)
img = polar_fade(img, 0.2, 3.2)
save(img, "moon.jpg")

# ---------------- 화성 ----------------
# 바람에 쓸린 먼지 무늬 위에 어두운 알베도 지대, 협곡, 극관.
streak = fbm(U, V, base=4, octaves=6, aspect=2.6, seed=3)
fine = fbm(U, V, base=9, octaves=5, aspect=1.4, seed=31)
t = np.clip(streak * 0.7 + fine * 0.3, 0, 1)
img = ramp(t, [(0.00, (128, 68, 46)), (0.34, (176, 96, 62)),
               (0.58, (212, 132, 88)), (0.80, (234, 170, 124)),
               (1.00, (246, 202, 164))])
dark = fbm(U, V, base=2, octaves=5, seed=4)
img *= (0.66 + 0.34 * np.clip((dark - 0.34) / 0.26, 0, 1))[:, :, None]
# 어두운 알베도 지역 (시르티스 메이저 같은)
img = oval(img, 620, 250, 130, 84, (104, 58, 42), 0.5)
img = oval(img, 130, 330, 96, 58, (118, 66, 46), 0.4)
img = oval(img, 860, 356, 74, 46, (112, 62, 44), 0.34)
# 대협곡: 적도 남쪽을 가로지르며 위도가 조금씩 흔들린다
drift = (fbm(U, V, base=3, octaves=3, aspect=0.4, seed=34) - 0.5) * 0.05
canyon = np.exp(-(((V - 0.545 + drift) * H / 20) ** 2))
canyon *= 0.5 + 0.5 * fbm(U, V, base=14, octaves=4, aspect=3.0, seed=32)
canyon *= np.clip(np.sin(U * np.pi * 1.05 - 0.15) * 1.5, 0, 1)
img *= (1 - 0.4 * canyon)[:, :, None]
# 밝은 화산 고지
img = oval(img, 250, 205, 105, 62, (240, 198, 160), 0.42)
img = craters(img, 110, seed=12, rmin=3, rmax=26, depth=0.22)
# 극관: 경계를 노이즈로 흩어 자연스럽게
edge = (fbm(U, V, base=11, octaves=4, aspect=1.0, seed=5) - 0.5) * 0.07
cap = np.clip((np.abs(LAT) + edge - 0.945) / 0.045, 0, 1) ** 0.85 * 0.94
img = img * (1 - cap[:, :, None]) + np.array([0.93, 0.94, 0.96]) * cap[:, :, None]
save(img, "mars.jpg")

# ---------------- 목성 ----------------
# 좌표를 노이즈로 밀어 띠를 일그러뜨린다(domain warping).
warp_u = U + (fbm(U, V, base=3, octaves=5, aspect=2.2, seed=6) - 0.5) * 0.06
warp_v = V + (fbm(U, V, base=4, octaves=6, aspect=2.8, seed=7) - 0.5) * 0.035
lat_w = 1 - 2 * warp_v
# 위도별로 띠 간격이 다르게 보이도록 비선형 왜곡
band_axis = lat_w + 0.2 * np.sin(lat_w * np.pi * 2.0)
band = 0.5 + 0.5 * np.sin(band_axis * np.pi * 9.0)
# 노이즈는 더하기로 섞는다. 가중평균으로 섞으면 대비가 죽는다.
band = np.clip(band + (fbm(warp_u, warp_v, base=6, octaves=6, aspect=3.2, seed=8) - 0.5) * 0.5, 0, 1)
img = ramp(band, [(0.00, (110, 66, 40)), (0.20, (162, 106, 62)),
                  (0.40, (206, 158, 108)), (0.58, (236, 206, 164)),
                  (0.76, (250, 234, 208)), (0.90, (254, 245, 230)),
                  (1.00, (255, 252, 246))])
# 폭풍: 대적점과 백색 타원들
img = oval(img, 700, 318, 118, 54, (198, 88, 54), 0.92, swirl=0.5)
img = oval(img, 700, 318, 64, 27, (168, 66, 42), 0.7, swirl=0.35)
img = oval(img, 236, 214, 56, 25, (255, 250, 242), 0.68, swirl=-0.3)
img = oval(img, 452, 372, 46, 21, (252, 244, 232), 0.58, swirl=0.28)
img = oval(img, 880, 168, 40, 18, (250, 238, 220), 0.52, swirl=-0.25)
# 극지방 후드
hood = np.clip((np.abs(LAT) - 0.56) / 0.44, 0, 1) ** 1.5
img = img * (1 - 0.46 * hood[:, :, None]) + np.array([0.46, 0.4, 0.38]) * (0.46 * hood)[:, :, None]
save(img, "jupiter.jpg")

# ---------------- 토성 ----------------
warp_v = V + (fbm(U, V, base=4, octaves=5, aspect=2.6, seed=9) - 0.5) * 0.03
lat_w = 1 - 2 * warp_v
band = np.clip(0.5 + 0.5 * np.sin(lat_w * np.pi * 5.0) * 0.55
               + fbm(U, warp_v, base=6, octaves=5, aspect=3.2, seed=10) * 0.24, 0, 1)
img = ramp(band, [(0.00, (192, 156, 104)), (0.34, (224, 196, 146)),
                  (0.62, (242, 224, 184)), (0.85, (250, 238, 210)),
                  (1.00, (254, 248, 232))])
hood = np.clip((np.abs(LAT) - 0.7) / 0.3, 0, 1) ** 1.4
img = img * (1 - 0.3 * hood[:, :, None]) + np.array([0.5, 0.52, 0.56]) * (0.3 * hood)[:, :, None]
save(img, "saturn.jpg")

# ---------------- 천왕성 ----------------
band = np.clip(0.5 + 0.5 * np.sin(LAT * np.pi * 2.6) * 0.16
               + (fbm(U, V, base=4, octaves=5, aspect=2.4, seed=11) - 0.5) * 0.2, 0, 1)
img = ramp(band, [(0.00, (118, 190, 202)), (0.45, (162, 218, 226)),
                  (0.78, (196, 234, 238)), (1.00, (218, 244, 246))])
img = polar_fade(img, 0.14, 2.6, (0.72, 0.86, 0.9))
save(img, "uranus.jpg")

# ---------------- 혜성 ----------------
n = fbm(U, V, base=4, octaves=7, seed=12)
img = ramp(n, [(0.00, (74, 76, 82)), (0.4, (116, 120, 128)),
               (0.72, (158, 166, 176)), (1.00, (206, 216, 226))])
patch = fbm(U, V, base=3, octaves=4, seed=33)
img *= (1 - 0.3 * np.clip((0.45 - patch) / 0.15, 0, 1))[:, :, None]
img = craters(img, 190, seed=13, rmin=3, rmax=34, depth=0.4, rays=3)
save(img, "comet.jpg")
