#!/usr/bin/env python3
"""Gera o ícone do Lurdens (SVG + PNGs) a partir de uma única geometria.

A geometria reproduz a referência "lurdens icon": quatro lâminas angulosas
em X, cada uma com cabeça larga e furos perto do centro, haste escalonada e
uma agulha vertical fina no alto. Para tamanhos pequenos (≤ 32 px) há uma
variante simplificada, sem furos, com traços mais grossos.

Requer Pillow apenas para gerar os PNGs (não é dependência do aplicativo).
Uso: python3 tools/make_icons.py
"""

import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "lurdens" / "resources" / "icons"

INK = "#151311"
PAPER = "#EFE8DA"
SIZE = 256
CENTER = (126.0, 142.0)
GLOBAL = 0.80

# Lâmina em coordenadas locais: x aponta do centro para fora, y é perpendicular.
HEAD = [(24, -10), (30, -24), (64, -28), (72, -20), (72, 18), (54, 22), (50, 16), (30, 12)]
STEP = [(70, -14), (96, -14), (98, 10), (70, 11)]
SHAFT = [(102, -9), (150, -8), (146, 6), (102, 7)]
HOLES = [(38, -6, 5.6), (52, -14, 4.0), (49, 5, 4.6)]

# Ângulos e escalas medidos na referência (a lâmina superior direita é mais longa e plana).
BLADES = [(-136, 0.86, 1), (-32, 0.92, -1), (137, 0.74, -1), (41, 0.76, 1)]
NEEDLE = [(126.5, 30), (131.5, 30), (128.5, 112), (124.5, 112)]


def transform(points, angle_deg, scale, flip):
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for x, y in points:
        y *= flip
        x, y = x * scale * GLOBAL, y * scale * GLOBAL
        out.append((CENTER[0] + x * ca - y * sa, CENTER[1] + x * sa + y * ca))
    return out


def shapes(simple: bool):
    polys, holes = [], []
    for angle, scale, flip in BLADES:
        if simple:
            # cabeça e haste fundidas, mais grossas, sem furos
            polys.append(transform([(20, -8), (30, -28), (70, -28), (70, 24), (26, 24)], angle, scale, flip))
            polys.append(transform([(62, -16), (156, -15), (150, 15), (62, 16)], angle, scale, flip))
        else:
            polys.append(transform(HEAD, angle, scale, flip))
            polys.append(transform(STEP, angle, scale, flip))
            polys.append(transform(SHAFT, angle, scale, flip))
            for hx, hy, r in HOLES:
                (cx, cy), = transform([(hx, hy)], angle, scale, flip)
                holes.append((cx, cy, r * scale * GLOBAL))
    needle = NEEDLE if not simple else [(121, 34), (135, 34), (132, 110), (122, 110)]
    polys.append(needle)
    return polys, holes


def stipple_points(seed=7):
    rnd = random.Random(seed)
    pts = []
    for _ in range(420):
        x, y = rnd.uniform(26, 226), rnd.uniform(26, 226)
        # densidade cresce para as bordas (como na faixa pontilhada da referência)
        d = max(abs(x - 128), abs(y - 128)) / 100
        if rnd.random() < d ** 3:
            pts.append((x, y, rnd.uniform(0.9, 1.7)))
    return pts


def fmt(p):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in p)


def svg(simple=False, tile=True, color=INK, stipple=True):
    polys, holes = shapes(simple)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}">',
             "<title>Lurdens</title>"]
    if tile:
        parts.append(f'<rect x="22" y="24" width="222" height="222" rx="44" fill="{INK}"/>')
        parts.append(f'<rect x="14" y="14" width="222" height="222" rx="44" fill="{PAPER}" stroke="{INK}" stroke-width="10"/>')
        if stipple and not simple:
            parts.append(f'<g fill="{INK}" opacity="0.55">')
            for x, y, r in stipple_points():
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}"/>')
            parts.append("</g>")
    if holes:
        parts.append('<defs><mask id="holes" maskUnits="userSpaceOnUse" x="0" y="0" width="256" height="256">'
                     '<rect width="256" height="256" fill="#fff"/>')
        for cx, cy, r in holes:
            parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="#000"/>')
        parts.append("</mask></defs>")
        parts.append(f'<g fill="{color}" mask="url(#holes)">')
    else:
        parts.append(f'<g fill="{color}">')
    for p in polys:
        parts.append(f'<polygon points="{fmt(p)}"/>')
    parts.append("</g></svg>")
    return "\n".join(parts) + "\n"


def png(size, simple, tile=True, color=INK):
    from PIL import Image, ImageDraw
    ss = 8
    big = SIZE * ss // 1
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = ss

    def sc(p):
        return [(x * k, y * k) for x, y in p]

    def hexrgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)

    ink, paper, col = hexrgb(INK), hexrgb(PAPER), hexrgb(color)
    if tile:
        d.rounded_rectangle([22 * k, 24 * k, 244 * k, 246 * k], radius=44 * k, fill=ink)
        d.rounded_rectangle([14 * k, 14 * k, 236 * k, 236 * k], radius=44 * k, fill=paper,
                            outline=ink, width=(10 if size > 32 else 14) * k)
        if not simple and size >= 128:
            dot = ink[:3] + (140,)
            for x, y, r in stipple_points():
                d.ellipse([(x - r) * k, (y - r) * k, (x + r) * k, (y + r) * k], fill=dot)
    polys, holes = shapes(simple)
    layer = Image.new("L", (big, big), 0)
    ld = ImageDraw.Draw(layer)
    for p in polys:
        ld.polygon(sc(p), fill=255)
    for cx, cy, r in holes:
        ld.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], fill=0)
    fg = Image.new("RGBA", (big, big), col)
    img.paste(fg, (0, 0), layer)
    return img.resize((size, size), Image.LANCZOS)


def placeholder_cover(size=640):
    """Capa alternativa: emblema sobre pontilhado, no estilo nanquim."""
    from PIL import Image, ImageDraw
    rnd = random.Random(11)
    img = Image.new("RGB", (size, size), (29, 27, 24))
    d = ImageDraw.Draw(img)
    for _ in range(9000):
        x, y = rnd.uniform(0, size), rnd.uniform(0, size)
        dist = math.hypot(x - size / 2, y - size / 2) / (size * 0.7)
        if rnd.random() < dist ** 1.6:
            r = rnd.uniform(0.6, 1.8)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(206, 199, 184))
    emblem = png(size // 2, simple=False, tile=False, color="#E9E3D6")
    img.paste(emblem, (size // 4, size // 4 - size // 40), emblem)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lurdens.svg").write_text(svg(), encoding="utf-8")
    (OUT / "lurdens-small.svg").write_text(svg(simple=True), encoding="utf-8")
    (OUT / "lurdens-emblem.svg").write_text(svg(tile=False), encoding="utf-8")
    for s in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        png(s, simple=s <= 32).save(OUT / f"lurdens-{s}.png")
    cover = placeholder_cover()
    cover.save(ROOT / "lurdens" / "resources" / "placeholder-cover.png")
    print("ícones gerados em", OUT)


if __name__ == "__main__":
    main()
