# Ajouté à la version française (phrases françaises et dossiers ajoutés).
# ==============================================================================
# JARVIS Plugin — Screenshot & Annotate
# Brand: Gemind
# Author: upgraderguy777 (https://github.com/upgraderguy777/jarvis-plugins)
# License: MIT License
# Notice: Vibecoded with precision for free-tier users.
# ==============================================================================

"""
JARVIS plugin — Screenshot & Annotate (visual "here's where" teaching).
Takes a screenshot, identifies UI controls via Gemini 2.5 Flash, circles them
with numbered tags, and displays the image directly to the user.
"""

import io
import json
import re
from datetime import datetime
from pathlib import Path

PLUGIN = {
    "name": "screenshot_annotate",
    "version": "1.0.0",
    "author": "Gemind (upgraderguy777)",
    "license": "MIT",
    "repository": "https://github.com/upgraderguy777/jarvis-plugins",
    "description": (
        "Takes a SCREENSHOT of the user's current screen and answers a "
        "'where is / how do I / I can't find X' question by circling the "
        "relevant button/menu/icon directly on the screenshot (numbered in "
        "order if there are multiple steps), describing out loud where it "
        "is, saving the marked-up image, and opening it automatically. Use "
        "for: 'where is the export button', 'how do I turn on dark mode', "
        "'show me how to do X', 'circle the search bar', 'analyze my screen "
        "and help me, I can't find the button', 'ekranda ayarlar nerede', "
        "'bana X'i göster', and in French: 'où est le bouton…', 'montre-moi où cliquer', "
        "'je ne trouve pas…', 'comment je fais pour…', 'entoure…'. This is for VISUALLY POINTING at things on "
        "screen for teaching/how-to purposes, including when the user is "
        "just stuck and asks for general help finding something — use "
        "screen_process instead if the user just wants the screen content "
        "read or explained in words with no drawing. Pass the user's exact "
        "question in 'query'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The user's exact question about the screen, verbatim, in their own language.",
            }
        },
        "required": ["query"],
    },
}

# 2.5-flash n'est plus ouvert aux nouveaux comptes (vu le 2026-10-25) : on essaie
# les modèles récents dans l'ordre, et on passe au suivant si l'un refuse.
_MODELES           = ("gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest",
                      "gemini-3.1-flash-lite")   # 3.5 d'abord : le plus rapide et le plus dispo (testé)
_MAX_UPLOAD_WIDTH  = 1400
_CIRCLE_COLOR      = (255, 90, 40)
_CIRCLE_WIDTH      = 4
_LABEL_BG          = (255, 90, 40)
_LABEL_FG          = (255, 255, 255)


def _get_api_key() -> str:
    try:
        from memory.config_manager import get_gemini_key
        key = get_gemini_key()
        if key:
            return key
    except Exception:
        pass
    try:
        base_dir = Path(__file__).resolve().parent.parent
        cfg = json.loads((base_dir / "config" / "api_keys.json").read_text(encoding="utf-8"))
        return cfg.get("gemini_api_key", "")
    except Exception:
        return ""


def _grab_screenshot():
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(mon)
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except ImportError:
        pass
    except Exception:
        return None
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        return img.convert("RGB")
    except Exception:
        return None


def _output_dir() -> Path:
    dossier = Path.home() / "Pictures" / "Screenshots"   # bouton CAPTURES de l'écran Iron Man
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        essai = dossier / ".essai_jarvis"
        essai.write_text("x")
        essai.unlink()
        return dossier
    except Exception:
        # Dossier refusé par Windows : on range dans le dossier de Jarvis.
        secours = Path(__file__).resolve().parent.parent / "enregistrements"
        secours.mkdir(parents=True, exist_ok=True)
        return secours


def _safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", (name or "").strip()) or "screenshot"
    return name[:50]


def _open_file(path: Path) -> bool:
    import os as _os
    import platform
    import subprocess
    try:
        system = platform.system()
        if system == "Windows":
            _os.startfile(str(path))
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception:
        return False


def _locate(image, query: str, api_key: str) -> dict:
    from google import genai
    from google.genai import types as gtypes

    w, h = image.size
    upload_img = image
    if w > _MAX_UPLOAD_WIDTH:
        scale = _MAX_UPLOAD_WIDTH / w
        upload_img = image.resize((int(w * scale), int(h * scale)))

    buf = io.BytesIO()
    upload_img.save(buf, format="JPEG", quality=85)
    jpg_bytes = buf.getvalue()

    prompt = (
        "You are looking at a screenshot of the user's computer screen. The "
        f'user asked (respond in the SAME language as this): "{query}"\n'
        "Find the UI element(s) — button, menu item, icon, field — needed to "
        "answer the question, IF they are visible in this screenshot.\n"
        "IMPORTANT: the box must tightly bound ONLY the actual interactive "
        "element that matches the instruction (a button, icon, or field — "
        "usually has its own border/background/label) — not a nearby "
        "heading, file name, thumbnail, or unrelated icon that merely "
        "relates to the same topic.\n"
        "Return ONLY minified JSON, no markdown fences, no extra text, with keys:\n"
        ' "found": true if at least one relevant element is visible in this '
        "screenshot right now, false otherwise,\n"
        ' "spoken_summary": 1-2 short conversational sentences in the user\'s '
        "language that actually DESCRIBE the location in words,\n"
        ' "steps": ordered array of step objects the user should follow, each with:\n'
        '   "instruction": short text describing this step, in the user\'s language,\n'
        '   "box_2d": [ymin,xmin,ymax,xmax] normalized 0-1000 over THIS image, '
        "tightly around the element for this step, IF it is visible in this "
        "screenshot — otherwise null.\n"
        "Keep steps short (max 6)."
    )

    client = genai.Client(api_key=api_key)
    resp = _generer(client, [
        gtypes.Part.from_bytes(data=jpg_bytes, mime_type="image/jpeg"),
        prompt,
    ])
    text = (resp.text or "").strip()
    if "{" in text and "}" in text:
        text = text[text.find("{"): text.rfind("}") + 1]
    spec = json.loads(text)
    spec["_upload_size"] = upload_img.size
    return spec


def _generer(client, contents):
    derniere = None
    for modele in _MODELES:
        try:
            return client.models.generate_content(model=modele, contents=contents)
        except Exception as e:      # modèle absent (404) ou quota épuisé (429)
            derniere = e
    raise derniere


def _norm_box_to_px(box_2d, img_w, img_h):
    ymin, xmin, ymax, xmax = [float(v) for v in box_2d]
    return ((xmin / 1000.0) * img_w, (ymin / 1000.0) * img_h,
             (xmax / 1000.0) * img_w, (ymax / 1000.0) * img_h)


def _refine_box(image_full, approx_px_box: tuple, instruction: str, api_key: str) -> tuple:
    x1, y1, x2, y2 = approx_px_box
    bw, bh = max(x2 - x1, 1), max(y2 - y1, 1)
    pad_x, pad_y = max(bw * 2.0, 160), max(bh * 2.0, 160)
    full_w, full_h = image_full.size

    cx1, cy1 = max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y))
    cx2, cy2 = min(full_w, int(x2 + pad_x)), min(full_h, int(y2 + pad_y))
    if cx2 - cx1 < 20 or cy2 - cy1 < 20:
        return approx_px_box

    crop = image_full.crop((cx1, cy1, cx2, cy2))
    orig_crop_w, orig_crop_h = crop.size
    send_crop = crop
    if max(orig_crop_w, orig_crop_h) < 700:
        scale = 700 / max(orig_crop_w, orig_crop_h)
        send_crop = crop.resize((int(orig_crop_w * scale), int(orig_crop_h * scale)))

    buf = io.BytesIO()
    send_crop.save(buf, format="JPEG", quality=90)
    jpg_bytes = buf.getvalue()

    prompt = (
        "This is a ZOOMED-IN crop of a larger screenshot, centered on "
        f'roughly where this should be: "{instruction}".\n'
        "Find the EXACT clickable element that matches.\n"
        'Return ONLY minified JSON: {"visible": true/false, "box_2d": '
        "[ymin,xmin,ymax,xmax] normalized 0-1000 over THIS crop, tightly "
        "around just that element — or null if it isn't actually in this crop}."
    )

    try:
        from google import genai
        from google.genai import types as gtypes
        client = genai.Client(api_key=api_key)
        resp = _generer(client, [gtypes.Part.from_bytes(data=jpg_bytes, mime_type="image/jpeg"), prompt])
        text = (resp.text or "").strip()
        if "{" in text and "}" in text:
            text = text[text.find("{"): text.rfind("}") + 1]
        refined = json.loads(text)
    except Exception:
        return approx_px_box

    rbox = refined.get("box_2d")
    if not refined.get("visible") or not (isinstance(rbox, (list, tuple)) and len(rbox) == 4):
        return approx_px_box

    try:
        rx1, ry1, rx2, ry2 = _norm_box_to_px(rbox, send_crop.size[0], send_crop.size[1])
    except (TypeError, ValueError):
        return approx_px_box

    back_x = orig_crop_w / send_crop.size[0]
    back_y = orig_crop_h / send_crop.size[1]
    return (cx1 + rx1 * back_x, cy1 + ry1 * back_y,
            cx1 + rx2 * back_x, cy1 + ry2 * back_y)


def _draw_annotations(image, steps: list):
    from PIL import ImageDraw, ImageFont

    img = image.copy()
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arialbd.ttf", 28)
    except Exception:
        font = ImageFont.load_default()

    drawn = 0
    for i, step in enumerate(steps, start=1):
        px_box = step.get("_px_box")
        if not px_box:
            continue
        x1, y1, x2, y2 = px_box
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        rx, ry = max((x2 - x1) / 2, 22), max((y2 - y1) / 2, 22)

        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                      outline=_CIRCLE_COLOR, width=_CIRCLE_WIDTH)

        label = str(i)
        try:
            text_w = draw.textlength(label, font=font)
        except Exception:
            text_w = 16
        lx = max(0, cx - rx - 4)
        ly = max(0, cy - ry - 34)
        draw.ellipse([lx, ly, lx + text_w + 20, ly + 32], fill=_LABEL_BG)
        draw.text((lx + 10, ly + 3), label, fill=_LABEL_FG, font=font)
        drawn += 1

    return img, drawn


# ── Repérage par grille (ajouté par Claude Code le 2026-10-25) ─────────────
# Les coordonnées « box_2d » données par Gemini tombaient à côté (500 px d'écart
# sur l'écran 4K de l'utilisateur). On dessine plutôt une grille numérotée sur la capture,
# on demande dans quelle case est le bouton, puis on zoome sur cette case avec une
# grille plus fine. Testé : 30 px d'écart sur le bouton Démarrer.
_LETTRES = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _avec_grille(img, cols, rows, w_max):
    from PIL import ImageDraw, ImageFont
    W, H = img.size
    s = min(1.0, w_max / W)
    im = img.resize((int(W * s), int(H * s))).convert("RGB")
    d = ImageDraw.Draw(im)
    w, h = im.size
    try:
        f = ImageFont.truetype("arialbd.ttf", max(12, int(h / rows / 4)))
    except Exception:
        f = ImageFont.load_default()
    for c in range(cols + 1):
        d.line([(c * w / cols, 0), (c * w / cols, h)], fill=(255, 0, 255), width=1)
    for r in range(rows + 1):
        d.line([(0, r * h / rows), (w, r * h / rows)], fill=(255, 0, 255), width=1)
    for c in range(cols):
        for r in range(rows):
            d.text((c * w / cols + 2, r * h / rows + 1), f"{_LETTRES[c]}{r + 1}", fill=(255, 0, 255), font=f)
    return im


def _case(client, img, question):
    from google.genai import types as gtypes
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    resp = _generer(client, [gtypes.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"), question])
    text = (resp.text or "").strip()
    text = text[text.find("{"): text.rfind("}") + 1]
    code = (json.loads(text).get("cell") or "").strip().upper()
    if not code or code[0] not in _LETTRES or not code[1:].isdigit():
        return None
    return _LETTRES.index(code[0]), int(code[1:]) - 1


def _localiser_grille(image, element: str, api_key: str):
    """Centre (x, y) en pixels de l'élément décrit, ou None."""
    from google import genai
    client = genai.Client(api_key=api_key, http_options={"timeout": 30000})
    W, H = image.size
    cols, rows = 16, 9
    q1 = (f'The user is looking for: "{element}". The screenshot has a magenta grid; each cell '
          "is labelled (letter = column, number = row). Which cell contains the CENTER of that "
          'UI element? Reply only JSON {"cell":"B9"}, or {"cell":""} if it is not visible.')
    c = _case(client, _avec_grille(image, cols, rows, 1600), q1)
    if not c:
        return None
    x0 = max(0.0, (c[0] - 1) * W / cols)
    y0 = max(0.0, (c[1] - 1) * H / rows)
    x1 = min(float(W), (c[0] + 2) * W / cols)
    y1 = min(float(H), (c[1] + 2) * H / rows)
    zoom = image.crop((int(x0), int(y0), int(x1), int(y1)))
    q2 = (f'This is a zoomed part of the screen. The user is looking for: "{element}". Which grid '
          'cell contains the CENTER of that element? Reply only JSON {"cell":"C3"}.')
    c2 = _case(client, _avec_grille(zoom, 10, 6, 1200), q2)
    if not c2:
        return ((x0 + x1) / 2, (y0 + y1) / 2)
    return (x0 + (c2[0] + 0.5) * (x1 - x0) / 10, y0 + (c2[1] + 0.5) * (y1 - y0) / 6)


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Version rapide (2026-10-25) : 2 questions à Google au lieu de 7.
    1) la capture avec une grille : « où est-ce et comment l'expliquer ? »
    2) un zoom sur la case trouvée, pour placer le cercle précisément."""
    import time as _time
    query = (parameters.get("query") or "").strip()
    if not query:
        return "What are you trying to find on screen?"
    try:
        import mss  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return "I need mss and Pillow to annotate the screen."
    api_key = _get_api_key()
    if not api_key:
        return "I can't analyze the screen — no API key is configured."

    def _log(msg: str) -> None:
        if player:
            try:
                player.write_log(msg)
            except Exception:
                pass

    shot = _grab_screenshot()
    if shot is None:
        return "I couldn't capture a screenshot, sorry."
    _log("JARVIS: je regarde l'écran…")
    t0 = _time.time()

    from google import genai
    from google.genai import types as gtypes
    client = genai.Client(api_key=api_key, http_options={"timeout": 30000})
    W, H = shot.size
    cols, rows = 16, 9
    q1 = (f'The user asks (answer in the SAME language): "{query}". The screenshot has a '
          "magenta grid; each cell is labelled (letter = column, number = row). Find the UI "
          "element (button, menu item, icon, field, date, link…) that answers the question. "
          'Reply ONLY minified JSON: {"found": true/false, "cell": "B9" (cell containing the '
          'CENTER of that element, or "" if not visible), "spoken": "1 or 2 short sentences '
          'describing where it is, in the language of the user, never mentioning the grid or cell names"}.')
    try:
        img = _avec_grille(shot, cols, rows, 1600)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        resp = _generer(client, [gtypes.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"), q1])
        txt = (resp.text or "").strip()
        spec = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    except Exception as e:
        return f"I couldn't work out where that is: {e}"

    spoken = (spec.get("spoken") or "").strip() or (
        "Here's what I found." if spec.get("found") else "I couldn't find that on your current screen.")
    code = (spec.get("cell") or "").strip().upper()
    centre = None
    if spec.get("found") and code and code[0] in _LETTRES and code[1:].isdigit():
        c, r = _LETTRES.index(code[0]), int(code[1:]) - 1
        # Zone de zoom large (2 cases de chaque côté) : une petite erreur au 1er coup est rattrapée.
        x0, y0 = max(0.0, (c - 2) * W / cols), max(0.0, (r - 2) * H / rows)
        x1, y1 = min(float(W), (c + 3) * W / cols), min(float(H), (r + 3) * H / rows)
        centre = ((x0 + x1) / 2, (y0 + y1) / 2)
        try:
            zoom = shot.crop((int(x0), int(y0), int(x1), int(y1)))
            q2 = (f'This is a zoomed part of the screen. The user asked: "{query}". Which grid cell '
                  'contains the CENTER of the element that answers it? Reply only JSON {"cell":"C3"}.')
            c2 = _case(client, _avec_grille(zoom, 15, 10, 1400), q2)
            if c2:
                centre = (x0 + (c2[0] + 0.5) * (x1 - x0) / 15, y0 + (c2[1] + 0.5) * (y1 - y0) / 10)
        except Exception:
            pass

    path = None
    opened = False
    if centre:
        rayon = max(28.0, W / 1920 * 30)
        cx, cy = centre
        annotated, _n = _draw_annotations(shot, [{"_px_box": (cx - rayon, cy - rayon, cx + rayon, cy + rayon)}])
        # Image allégée (1920 px de large, JPEG) : elle s'ouvre tout de suite.
        if annotated.size[0] > 1920:
            k = 1920 / annotated.size[0]
            annotated = annotated.resize((1920, int(annotated.size[1] * k)))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            path = _output_dir() / f"{_safe_name(query[:40])}_{stamp}.jpg"
            annotated.convert("RGB").save(path, quality=88)
            opened = _open_file(path)
        except Exception:
            path = None

    _log(f"JARVIS: écran analysé en {_time.time() - t0:.0f} s"
         + (" — image ouverte." if opened else "."))
    if path and opened:
        spoken += " I've circled it and opened the picture."
    elif path:
        spoken += f" I've saved the circled picture as {path.name}."
    return spoken
