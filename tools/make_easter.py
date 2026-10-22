#!/usr/bin/env python3
"""Gera a arte hachurada do easter egg "Ludens" a partir de `Bring icon.png`.

A geometria vem inteiramente da imagem de referência fornecida pelo usuário:
1. recorta o quadro escuro onde está o símbolo;
2. isola os traços claros (as linhas da estrela);
3. separa as regiões fechadas internas;
4. redesenha tudo em linguagem de nanquim: traços engrossados, cada região
   interna com hachura em um ângulo, a região central com hachura cruzada
   e um pontilhado que se dissolve em volta.

Saída (PNG com transparência, uma por tema):
  lurdens/resources/easter/ludens-hatch-light.png   tinta clara (tema escuro)
  lurdens/resources/easter/ludens-hatch-dark.png    tinta escura (tema claro)

Requer Pillow, NumPy e SciPy só para gerar (não são dependências do app).
Uso: python3 tools/make_easter.py ["caminho/Bring icon.png"]
"""

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "lurdens" / "resources" / "easter"
SIZE = 1200
INKS = {"light": (236, 230, 216), "dark": (22, 20, 18)}


def crop_symbol(img: Image.Image) -> Image.Image:
    """Recorta o quadro escuro que contém o símbolo (a captura tem bordas)."""
    rgb = np.asarray(img.convert("RGB")).astype(int)
    dark = rgb.sum(axis=2) < 45
    rows, cols = np.where(dark)
    if rows.size < 1000:
        return img.convert("RGB")       # já é só o símbolo
    return img.convert("RGB").crop((cols.min(), rows.min(), cols.max() + 1, rows.max() + 1))


def line_mask(sym: Image.Image) -> np.ndarray:
    big = sym.convert("L").resize((SIZE, SIZE), Image.LANCZOS)
    a = np.asarray(big)
    return a > 110


def hatch(size, angle_deg, spacing, width, rnd, jitter=1.2):
    """Camada de hachura: linhas paralelas levemente irregulares."""
    layer = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(layer)
    a = math.radians(angle_deg)
    dx, dy = math.cos(a), math.sin(a)
    nx, ny = -dy, dx
    diag = size * 1.5
    c = size / 2
    k = -diag
    while k < diag:
        off = k + rnd.uniform(-jitter, jitter)
        x0, y0 = c + nx * off - dx * diag, c + ny * off - dy * diag
        x1, y1 = c + nx * off + dx * diag, c + ny * off + dy * diag
        d.line([(x0, y0), (x1, y1)], fill=255, width=width)
        k += spacing
    return np.asarray(layer) > 0


def compose(src: Path) -> np.ndarray:
    rnd = random.Random(1213)
    sym = crop_symbol(Image.open(src))
    lines = line_mask(sym)

    # traços engrossados, como contorno de nanquim
    strokes = ndimage.binary_dilation(lines, iterations=2)

    # regiões: o que não é traço; a que toca a borda é o exterior
    labels, n = ndimage.label(~strokes)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])))
    regions = []
    for i in range(1, n + 1):
        if i in border:
            continue
        m = labels == i
        area = int(m.sum())
        if area < 400:
            continue
        cy, cx = ndimage.center_of_mass(m)
        regions.append((area, cx, cy, m))
    regions.sort(key=lambda r: math.hypot(r[1] - SIZE / 2, r[2] - SIZE / 2))

    out = np.zeros((SIZE, SIZE), dtype=float)
    for idx, (area, cx, cy, m) in enumerate(regions):
        # ângulo da hachura segue a direção da região a partir do centro
        ang = math.degrees(math.atan2(cy - SIZE / 2, cx - SIZE / 2)) + 90
        if idx == 0:   # região central: hachura cruzada densa
            h = hatch(SIZE, 45, 9, 3, rnd) | hatch(SIZE, -45, 9, 3, rnd)
            out[m & h] = 1.0
        else:
            spacing = 11 if area > 8000 else 9
            out[m & hatch(SIZE, ang, spacing, 3, rnd)] = 0.92

    out[strokes] = 1.0

    # pontilhado em volta, mais denso perto da estrela
    exterior = np.isin(labels, list(border)) & ~strokes
    dist = ndimage.distance_transform_edt(~strokes)
    dots = Image.new("L", (SIZE, SIZE), 0)
    dd = ImageDraw.Draw(dots)
    for _ in range(15000):
        x, y = rnd.randrange(SIZE), rnd.randrange(SIZE)
        if not exterior[y, x]:
            continue
        p = math.exp(-dist[y, x] / 70.0)
        if rnd.random() < p * 0.9:
            r = rnd.uniform(1.2, 2.6)
            dd.ellipse([x - r, y - r, x + r, y + r], fill=255)
    out = np.maximum(out, np.asarray(dots) / 255.0 * 0.75)

    # vinheta suave para a arte "sumir" nas bordas da janela
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    rr = np.hypot(xx - SIZE / 2, yy - SIZE / 2) / (SIZE / 2)
    out *= np.clip(1.25 - rr * 0.55, 0, 1)
    return out


def save(alpha: np.ndarray, ink, path: Path):
    a = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    img = Image.new("RGBA", (SIZE, SIZE), ink + (0,))
    img.putalpha(a)
    img.save(path, optimize=True)


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "Bring icon.png"
    if not src.exists():
        sys.exit(f"Imagem de referência não encontrada: {src}")
    OUT.mkdir(parents=True, exist_ok=True)
    alpha = compose(src)
    for name, ink in INKS.items():
        save(alpha, ink, OUT / f"ludens-hatch-{name}.png")
    print("arte gerada em", OUT)


if __name__ == "__main__":
    main()
