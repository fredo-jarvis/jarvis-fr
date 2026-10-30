"""
Écran « HUD » du mode épuré, version 4 (demande de l'utilisateur, 2026-10-25).

Copie la mise en page du thème que l'utilisateur a montré : une vraie image d'armure en
hologramme au centre (assets/hologramme-detoure.png, découpée dans la photo
qu'il a donnée), une rangée de grands onglets de programmes en haut, de petits
onglets au-dessus, une grille de dossiers à gauche, une colonne de sites à
droite, la date en grand en haut à droite, l'horloge en bas à droite, le badge
J.A.R.V.I.S en bas à gauche. Le réacteur de l'armure s'allume quand Jarvis parle.

Tout est dessiné sur une feuille virtuelle de 1920 x 1080 mise à l'échelle de
l'écran. Les parties fixes sont dessinées une fois dans une image en cache.
"""
from __future__ import annotations

import ctypes
import json
import math
import os
import random
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import psutil
from PyQt6.QtCore import QFileInfo, QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient)
from PyQt6.QtWidgets import QFileIconProvider

from core import jarvis_vivant as viv
from core import panneaux_holo as vitres
from core import decor_cercle as decor

BASE = Path(__file__).resolve().parent.parent
ASSETS = BASE / "assets"
ICONES = ASSETS / "raccourcis"
VW, VH = 1920.0, 1080.0

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DAVINCI = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"
TASKMGR = r"C:\Windows\System32\Taskmgr.exe"
PERSO = Path.home()
from plugins._cerveau_commun import CERVEAU   # chemin du cerveau à un seul endroit (audit du 26/10)

# Petits onglets tout en haut.
PETITS = [
    ("EXCEL", "url", ("url", "https://www.office.com/launch/excel")),
    ("GMAIL", "url", ("url", "https://mail.google.com")),
    ("AGENDA", "url", ("url", "https://calendar.google.com")),
    ("GESTIONNAIRE", "exe:" + TASKMGR, ("exe", TASKMGR)),
]
# Grands onglets : les programmes.
GRANDS = [
    ("EDGE", "exe:" + EDGE, ("exe", EDGE)),
    ("OUTLOOK", "png:outlook.png",
     ("app", "Microsoft.OutlookForWindows_8wekyb3d8bbwe!Microsoft.OutlookforWindows")),
    ("CLAUDE", "png:claude.png", ("app", "Claude_pzs8sxrjxfjjc!Claude")),
    ("YT STUDIO", "youtube", ("url", "https://studio.youtube.com")),
    ("DAVINCI", "exe:" + DAVINCI, ("exe", DAVINCI)),
    ("FICHIERS", "dossier", ("exe", r"C:\Windows\explorer.exe")),
]
# Grille de gauche : les dossiers.
DOSSIERS = [
    ("TÉLÉCHARGEMENTS", r"D:\téléchargement"), ("CERVEAU", str(CERVEAU)),
    ("PRODUCTIONS", str(CERVEAU / "productions")), ("CAPTURES", str(PERSO / "Pictures" / "Screenshots")),
    ("DOCUMENTS", str(PERSO / "Documents")), ("IMAGES", str(PERSO / "Pictures")),
    ("MUSIQUE", str(PERSO / "Music")), ("VIDÉOS", str(PERSO / "Videos")),
    ("BUREAU", str(PERSO / "Desktop")), ("JARVIS", str(BASE)),
]
# Colonne de droite : les sites.
SITES = [
    ("YOUTUBE", "https://www.youtube.com"),
    ("GMAIL", "https://mail.google.com"),
    ("AGENDA", "https://calendar.google.com"),
    ("MÉTÉO", "https://www.google.com/search?q=m%C3%A9t%C3%A9o"),
    ("SUNO", "https://suno.com"),
    ("TRADUCTION", "https://translate.google.fr"),
    ("WIKIPÉDIA", "https://fr.wikipedia.org"),
]

JOURS = ("LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE")
MOIS = ("JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET", "AOÛT",
        "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE")

CYAN = QColor("#3fd6ff")
CYAN_CLAIR = QColor("#bdf3ff")
BLEU = QColor("#1e9bff")
BLANC = QColor("#eef8ff")
TEXTE_INFO = QColor("#8fe3ff")
FOND = QColor("#010710")
BOUTON_H = QColor(20, 62, 82, 235)
BOUTON_B = QColor(8, 28, 40, 235)

# Hologramme : hauteur affichée et position (le réacteur est mesuré sur l'image).
HOLO_H = 990.0
HOLO_CX = 1010.0
HOLO_Y = 70.0
HOLO_REACTEUR = (605.0, 490.0)   # en pixels de l'image d'origine (1046 x 1034)
FILM_REACTEUR = (548.0, 321.0)
FILM_YEUX = ((525.0, 153.0), (578.0, 157.0))

# Mode « vrai hologramme » (demande de l'utilisateur, 2026-10-26) : fond transparent, le bureau de
# Windows se voit derrière, l'armure flotte et scintille. Réglé par "holo" dans memory/interface.json.
INTERFACE = BASE / "memory" / "interface.json"


def decor_cercle() -> bool:
    """Décor « grand cercle bleu » : le seul décor de cette version partagée."""
    return True


LIEU = {"ville": "Paris", "lat": 48.857, "lon": 2.352}


def _lieu() -> dict:
    """Ville de la météo : réglages "ville", "latitude", "longitude" de memory/interface.json."""
    try:
        r = json.loads(INTERFACE.read_text(encoding="utf-8"))
        return {"ville": r.get("ville", "Paris"), "lat": float(r.get("latitude", 48.857)),
                "lon": float(r.get("longitude", 2.352))}
    except Exception:
        return dict(LIEU)


def mode_holo() -> bool:
    try:
        return bool(json.loads(INTERFACE.read_text(encoding="utf-8")).get("holo", True))
    except Exception:
        return False


# ── Données : météo, PC, corbeille ───────────────────────────────────────────

class _Donnees:
    def __init__(self):
        self.meteo = None
        self._meteo_t = 0.0
        self.pc = {"cpu": 0.0, "ram": 0.0}
        self._pc_t = 0.0
        self.corbeille = (0.0, 0)
        self._corb_t = 0.0
        try:
            psutil.cpu_percent(None)
            self.demarrage = psutil.boot_time()
        except Exception:
            self.demarrage = time.time()

    def maj(self):
        now = time.time()
        if now - self._pc_t > 2.0:
            self._pc_t = now
            try:
                self.pc["cpu"] = psutil.cpu_percent(None)
                self.pc["ram"] = psutil.virtual_memory().percent
            except Exception:
                pass
        if now - self._corb_t > 15.0:
            self._corb_t = now
            self.corbeille = _taille_corbeille()
        if now - self._meteo_t > 1800:
            self._meteo_t = now
            threading.Thread(target=self._charger_meteo, daemon=True).start()

    def _charger_meteo(self):
        LIEU.update(_lieu())
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={LIEU['lat']}&longitude={LIEU['lon']}"
               "&current=temperature_2m,weather_code&timezone=Europe%2FParis")
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                self.meteo = json.loads(r.read().decode("utf-8"))
        except Exception:
            self._meteo_t = time.time() - 1500


class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("i64Size", ctypes.c_int64),
                ("i64NumItems", ctypes.c_int64)]


def _taille_corbeille() -> tuple[float, int]:
    try:
        info = _SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(info)
        ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        return info.i64Size / 2**20, int(info.i64NumItems)
    except Exception:
        return 0.0, 0


DONNEES = _Donnees()


def _meteo_mot(code: int) -> str:
    if code == 0:
        return "ENSOLEILLÉ"
    if code in (1, 2):
        return "ÉCLAIRCIES"
    if code == 3:
        return "COUVERT"
    if code in (45, 48):
        return "BROUILLARD"
    if code in (71, 73, 75, 77, 85, 86):
        return "NEIGE"
    if code in (95, 96, 99):
        return "ORAGE"
    if code >= 51:
        return "PLUIE"
    return "NUAGEUX"


# ── Actions ──────────────────────────────────────────────────────────────────

def _ouvrir(action) -> None:
    genre, cible = action
    try:
        if genre == "exe":
            subprocess.Popen([cible])
        elif genre == "app":
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{cible}"])
        elif genre == "shell":
            subprocess.Popen(["explorer.exe", cible])
        elif genre == "holo":
            from plugins.cerveau_hologramme import run as holo
            threading.Thread(target=holo, args=({"action": cible},), daemon=True).start()
        else:
            os.startfile(cible)
    except Exception as e:
        print(f"[Iron HUD] ouverture impossible : {cible} ({e})")


def _touche(vk: int) -> None:
    try:
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
    except Exception:
        pass


# ── Outils de dessin ─────────────────────────────────────────────────────────

def _c(col: QColor, a: float) -> QColor:
    q = QColor(col)
    q.setAlphaF(max(0.0, min(1.0, a)))
    return q


def _police(taille, nom="Bahnschrift", gras=True) -> QFont:
    f = QFont(nom)
    f.setPixelSize(max(6, int(taille)))
    f.setBold(gras)
    return f


def _texte(p, x, y, w, h, txt, taille, col=BLANC, nom="Bahnschrift", gras=True,
           align=Qt.AlignmentFlag.AlignLeft):
    if mode_holo() and not decor_cercle():
        return _texte_holo(p, x, y, w, h, txt, taille, col, nom, gras, align)
    p.setFont(_police(taille, nom, gras))
    p.setPen(QPen(col, 1))
    p.drawText(QRectF(x, y, w, h), align | Qt.AlignmentFlag.AlignVCenter, txt)


def _texte_holo(p, x, y, w, h, txt, taille, col, nom, gras, align):
    """Écriture d'hologramme : lettres espacées, halo bleu, léger dédoublement des couleurs
    (comme une projection) et lettres en dégradé blanc → cyan, coupées de fines lignes."""
    if not txt:
        return
    f = _police(taille, nom, gras)
    titre = nom == "Bahnschrift"
    if titre:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(0.8, taille * 0.09))
    fm = QFontMetricsF(f)
    largeur = fm.horizontalAdvance(txt)
    # mot trop long pour son bouton : on resserre les lettres, puis on rapetisse
    while titre and largeur > w - 12 and f.pixelSize() > 8:
        if f.letterSpacing() > 0.3:
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.3)
        else:
            f.setPixelSize(f.pixelSize() - 1)
        fm = QFontMetricsF(f)
        largeur = fm.horizontalAdvance(txt)
    if align & Qt.AlignmentFlag.AlignRight:
        tx = x + w - largeur
    elif align & Qt.AlignmentFlag.AlignHCenter:
        tx = x + (w - largeur) / 2
    else:
        tx = x
    base = y + (h + fm.ascent() - fm.descent()) / 2
    chemin = QPainterPath()
    chemin.addText(QPointF(tx, base), f, txt)
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    # halo
    rayon = 2.2 if titre else 1.4
    for dx, dy in ((rayon, 0), (-rayon, 0), (0, rayon), (0, -rayon),
                   (rayon * .7, rayon * .7), (-rayon * .7, -rayon * .7),
                   (rayon * .7, -rayon * .7), (-rayon * .7, rayon * .7)):
        p.fillPath(chemin.translated(dx, dy), QColor(40, 170, 255, 26))
    # dédoublement des couleurs (aberration de projection)
    p.fillPath(chemin.translated(-0.6, 0), QColor(30, 110, 255, 60))   # dédoublement très léger : lettres nettes
    p.fillPath(chemin.translated(0.5, 0), QColor(140, 255, 255, 35))
    # lettres : dégradé blanc → couleur demandée
    g = QLinearGradient(0, base - fm.ascent(), 0, base)
    g.setColorAt(0.0, QColor(255, 255, 255, 250))
    g.setColorAt(1.0, _c(col if col != BLANC else CYAN_CLAIR, 0.95))
    p.fillPath(chemin, QBrush(g))
    # (les fines lignes dans les lettres ont été enlevées le 28/10 : l'utilisateur trouvait ça moins beau)
    p.restore()


def _poly(pts) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in pts])


def _icone(canvas, cle: str):
    cache = canvas.__dict__.setdefault("_iron_icones", {})
    if cle in cache:
        return cache[cle]
    pm = None
    try:
        if cle.startswith("png:"):
            pm = QPixmap(str(ICONES / cle[4:]))
        elif cle.startswith("exe:") and Path(cle[4:]).exists():
            pm = QFileIconProvider().icon(QFileInfo(cle[4:])).pixmap(128, 128)   # net en 4K
        if pm is not None and pm.isNull():
            pm = None
    except Exception:
        pm = None
    cache[cle] = pm
    return pm


def _dessin_icone(p, canvas, cle, r: QRectF):
    pm = _icone(canvas, cle)
    if pm is not None:
        p.drawPixmap(r, pm, QRectF(pm.rect()))
        return
    w, h = r.width(), r.height()
    if cle == "youtube":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#ff2a2a")))
        p.drawRoundedRect(r.adjusted(0, h * 0.18, 0, -h * 0.18), 4, 4)
        p.setBrush(QBrush(BLANC))
        m, k = r.center(), w * 0.16
        p.drawPolygon(QPolygonF([QPointF(m.x() - k, m.y() - k * 1.1), QPointF(m.x() - k, m.y() + k * 1.1),
                                 QPointF(m.x() + k * 1.3, m.y())]))
    elif cle == "url":
        p.setPen(QPen(CYAN, 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(r.center(), w * 0.42, h * 0.42)
        p.drawEllipse(r.center(), w * 0.18, h * 0.42)
        p.drawLine(QPointF(r.left() + w * 0.08, r.center().y()), QPointF(r.right() - w * 0.08, r.center().y()))
    else:   # dossier
        p.setPen(QPen(QColor("#ffc54a"), 1.2))
        p.setBrush(QBrush(QColor(255, 197, 74, 120)))
        p.drawPolygon(_poly([(r.left(), r.top() + h * 0.2), (r.left() + w * 0.4, r.top() + h * 0.2),
                             (r.left() + w * 0.5, r.top() + h * 0.32), (r.right(), r.top() + h * 0.32),
                             (r.right(), r.bottom() - h * 0.1), (r.left(), r.bottom() - h * 0.1)]))


def _verre(col: QColor, alpha_holo: int) -> QColor:
    """En mode hologramme, les fonds deviennent du verre bleu presque transparent."""
    if not mode_holo():
        return col
    c = QColor(col)
    c.setAlpha(alpha_holo)
    return c


def _lueur(p, poly, col: QColor, dedans: bool):
    """Bord lumineux d'hologramme : un trait large et pâle, puis un trait fin et vif."""
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(_c(col, 0.22 if not dedans else 0.4), 5))
    p.drawPolygon(poly)
    p.setPen(QPen(_c(CYAN_CLAIR, 0.85 if dedans else 0.6), 1.3))
    p.drawPolygon(poly)


def _bouton(p, r: QRectF, dedans: bool, biseau=10.0):
    """Bouton bleu-gris en biseau, comme ceux du thème (DOWNLOADS, FACEBOOK…)."""
    pts = [(r.left(), r.top()), (r.right() - biseau, r.top()), (r.right(), r.top() + biseau),
           (r.right(), r.bottom()), (r.left() + biseau, r.bottom()), (r.left(), r.bottom() - biseau)]
    g = QLinearGradient(r.topLeft(), r.bottomLeft())
    if mode_holo():
        g.setColorAt(0.0, QColor(90, 210, 255, 70 if dedans else 34))
        g.setColorAt(1.0, QColor(30, 140, 255, 40 if dedans else 14))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawPolygon(_poly(pts))
        _lueur(p, _poly(pts), CYAN, dedans)
        return
    g.setColorAt(0.0, QColor(46, 120, 150, 240) if dedans else BOUTON_H)
    g.setColorAt(1.0, QColor(16, 60, 82, 240) if dedans else BOUTON_B)
    p.setBrush(QBrush(g))
    p.setPen(QPen(_c(CYAN_CLAIR if dedans else CYAN, 0.9 if dedans else 0.35), 1.2))
    p.drawPolygon(_poly(pts))
    p.setPen(QPen(_c(BLANC, 0.12), 1))
    p.drawLine(QPointF(r.left() + 2, r.top() + 2), QPointF(r.right() - biseau, r.top() + 2))


# ── Couche fixe ──────────────────────────────────────────────────────────────

def _fond(p):
    g = QRadialGradient(VW * 0.55, VH * 0.45, VW * 0.65)
    g.setColorAt(0.0, QColor(12, 46, 78))
    g.setColorAt(0.45, QColor(4, 20, 38))
    g.setColorAt(1.0, FOND)
    p.fillRect(QRectF(0, 0, VW, VH), QBrush(g))
    rnd = random.Random(11)
    for _ in range(260):   # étoiles
        x, y = rnd.uniform(0, VW), rnd.uniform(0, VH)
        p.setPen(QPen(QColor(120, 190, 255, rnd.randint(30, 150)), rnd.choice((1, 1, 1, 2))))
        p.drawPoint(QPointF(x, y))
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(14):    # petites lumières floues
        x, y, r = rnd.uniform(200, 1700), rnd.uniform(80, 1000), rnd.uniform(6, 16)
        b = QRadialGradient(x, y, r)
        b.setColorAt(0.0, QColor(60, 140, 255, 120))
        b.setColorAt(1.0, QColor(60, 140, 255, 0))
        p.setBrush(QBrush(b))
        p.drawEllipse(QPointF(x, y), r, r)
    for i in range(5):     # panneaux flous en perspective derrière
        x = 470 + i * 46
        g2 = QLinearGradient(x, 0, x + 30, 0)
        g2.setColorAt(0.0, QColor(90, 160, 220, 0))
        g2.setColorAt(0.5, QColor(90, 160, 220, 26))
        g2.setColorAt(1.0, QColor(90, 160, 220, 0))
        p.fillRect(QRectF(x, 220 + i * 20, 30, 500 - i * 40), QBrush(g2))


def _holo_geo(pm_w: float, pm_h: float):
    w = pm_w * HOLO_H / pm_h
    return HOLO_CX - w * 0.56, HOLO_Y, w, HOLO_H / pm_h


def _hologramme(p):
    pm = QPixmap(str(ASSETS / "hologramme-detoure.png"))
    if pm.isNull():
        return
    x, y, w, _k = _holo_geo(pm.width(), pm.height())
    g = QRadialGradient(x + w * 0.56, y + HOLO_H * 0.48, w * 0.55)
    g.setColorAt(0.0, QColor(30, 120, 255, 70))
    g.setColorAt(1.0, QColor(30, 120, 255, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(x + w * 0.56, y + HOLO_H * 0.48), w * 0.55, HOLO_H * 0.5)
    p.drawPixmap(QRectF(x, y, w, HOLO_H), pm, QRectF(pm.rect()))
    # Deuxième passage en mode « addition » : l'armure brille comme un hologramme.
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    p.setOpacity(0.35)
    p.drawPixmap(QRectF(x, y, w, HOLO_H), pm, QRectF(pm.rect()))
    p.setOpacity(1.0)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)


def _cadre(p):
    col = _c(CYAN, 0.55)
    p.setPen(QPen(col, 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolyline(_poly([(70, 76), (40, 106), (40, 300), (60, 320), (60, 560), (40, 580), (40, 1030), (70, 1060)]))
    p.setPen(QPen(_c(CYAN, 0.25), 8))
    p.drawLine(QPointF(30, 130), QPointF(30, 280))
    p.setPen(QPen(col, 2))
    p.drawPolyline(_poly([(1700, 20), (1880, 20), (1900, 40), (1900, 230), (1880, 250)]))
    p.drawPolyline(_poly([(1880, 300), (1880, 760), (1862, 778)]))
    p.setBrush(QBrush(_c(CYAN, 0.7)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(_poly([(1866, 520), (1858, 532), (1874, 532)]))
    p.drawPolygon(_poly([(1866, 600), (1858, 588), (1874, 588)]))
    g = QLinearGradient(1200, 960, 1200, 1060)
    g.setColorAt(0.0, _verre(QColor(30, 90, 120, 200), 50))
    g.setColorAt(1.0, _verre(QColor(6, 24, 36, 220), 30))
    p.setBrush(QBrush(g))
    p.setPen(QPen(_c(CYAN, 0.6), 1.5))
    p.drawPolygon(_poly([(1180, 1060), (1260, 960), (1880, 960), (1900, 940), (1900, 1060)]))
    p.drawPolygon(_poly([(110, 1030), (150, 920), (590, 920), (620, 960), (590, 1030)]))


def _reglette(p):
    _texte(p, 18, 430, 90, 18, "RAM", 13, TEXTE_INFO, nom="Consolas")
    x, y = 112.0, 500.0
    for i in range(20):
        v = (100, 80, 60, 40, 20)[i % 5]
        yy = y + i * 20
        _texte(p, x - 8, yy - 9, 34, 18, str(v), 11, _c(TEXTE_INFO, 0.75), nom="Consolas",
               align=Qt.AlignmentFlag.AlignRight)
        p.setPen(QPen(_c(CYAN, 0.5), 1))
        p.drawLine(QPointF(x + 30, yy), QPointF(x + 40, yy))
    p.setPen(QPen(_c(CYAN, 0.5), 1))
    p.drawLine(QPointF(x + 40, y), QPointF(x + 40, y + 19 * 20))


def _hologramme_transparent(p):
    """L'armure sans fond noir (assets/hologramme-transparent.png), qui brille sur le bureau."""
    # Armure en couleurs, sinon la version bleue
    for nom in ("hologramme-couleur-hd.png", "hologramme-transparent-hd.png", "hologramme-transparent.png"):
        if (ASSETS / nom).exists():
            pm = QPixmap(str(ASSETS / nom))
            break
    if pm.isNull():
        return _hologramme(p)
    x, y, w, _k = _holo_geo(pm.width(), pm.height())
    g = QRadialGradient(x + w * 0.56, y + HOLO_H * 0.48, w * 0.6)
    g.setColorAt(0.0, QColor(255, 90, 40, 45))     # lueur chaude derrière l'armure rouge et or
    g.setColorAt(1.0, QColor(255, 90, 40, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(x + w * 0.56, y + HOLO_H * 0.48), w * 0.6, HOLO_H * 0.52)
    p.setOpacity(0.92)
    p.drawPixmap(QRectF(x, y, w, HOLO_H), pm, QRectF(pm.rect()))
    p.setOpacity(1.0)


def _voile_holo(p):
    """Voile sombre très léger : le bureau reste visible, les textes restent lisibles."""
    g = QRadialGradient(VW * 0.5, VH * 0.5, VW * 0.75)
    g.setColorAt(0.0, QColor(0, 12, 28, 70))     # voile léger : le fond d'écran se voit (sans flou, 28/10)
    g.setColorAt(1.0, QColor(0, 6, 16, 150))
    p.fillRect(QRectF(0, 0, VW, VH), QBrush(g))


def _couche_fixe(W, H, s, ox, oy, dpr=1.0) -> QPixmap:
    # Dessinée en VRAIS pixels de l'écran (dpr = 2 sur un écran 4K) : sinon l'image est agrandie et floue.
    pm = QPixmap(int(W * dpr), int(H * dpr))
    pm.setDevicePixelRatio(dpr)
    if mode_holo():
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(ox, oy)
        p.scale(s, s)
        _voile_holo(p)   # l'armure, le cadre et la réglette sont dessinés vivants (jarvis_vivant, 28/10)
        p.end()
        return pm
    pm.fill(FOND)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.translate(ox, oy)
    p.scale(s, s)
    _fond(p)
    _hologramme(p)
    _cadre(p)
    _reglette(p)
    p.end()
    return pm


# ── Couche vivante ───────────────────────────────────────────────────────────

def _infos(p):
    up = int(time.time() - DONNEES.demarrage)
    duree = f"{up // 3600:02d}:{up % 3600 // 60:02d}:{up % 60:02d}"
    for i, l in enumerate(("JARVIS ID : JARVIS", "SYSTÈME : WINDOWS 11 · 64 BITS", "AGENT : UTILISATEUR")):
        _texte(p, 70, 22 + i * 16, 330, 16, l, 13, TEXTE_INFO, nom="Consolas")
    for cx in (330, 356):
        p.setPen(QPen(_c(CYAN, 0.7), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, 34), 9, 9)
        p.drawEllipse(QPointF(cx, 34), 3, 3)
    for i, l in enumerate(("INFOS SYSTÈME :", "MEMBRE : UTILISATEUR", f"EN MARCHE : {duree}")):
        _texte(p, 380, 22 + i * 16, 290, 16, l, 13, TEXTE_INFO, nom="Consolas",
               align=Qt.AlignmentFlag.AlignRight)


def _petits_onglets(p, canvas, survol, zones):
    x = 700.0
    for nom, icone, action in PETITS:
        r = QRectF(x, 22, 140, 30)
        dedans = survol is not None and r.contains(survol)
        p.setBrush(QBrush(_verre(QColor(10, 40, 56, 220), 40) if not dedans else _verre(QColor(30, 100, 130, 230), 80)))
        p.setPen(QPen(_c(CYAN, 0.45), 1))
        p.drawPolygon(_poly([(r.left(), r.top()), (r.right() - 14, r.top()), (r.right(), r.bottom()),
                             (r.left(), r.bottom())]))
        p.fillRect(QRectF(r.left() + 40, r.bottom() - 3, r.width() - 40, 3), CYAN)
        p.fillRect(QRectF(r.left() + 4, r.top() + 4, 22, 22), QColor(255, 255, 255, 30))
        _dessin_icone(p, canvas, icone, QRectF(r.left() + 6, r.top() + 6, 18, 18))
        _texte(p, r.left() + 32, r.top(), r.width() - 40, r.height() - 3, nom, 13,
               CYAN_CLAIR if dedans else BLANC)
        zones.append((r, ("ouvrir", action)))
        x += 150


def _grands_onglets(p, canvas, survol, zones):
    x = 200.0
    for nom, icone, action in GRANDS:
        r = QRectF(x, 92, 168, 56)
        dedans = survol is not None and r.contains(survol)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        forme = _poly([(r.left(), r.top()), (r.right() - 22, r.top()), (r.right(), r.bottom() - 8),
                       (r.right(), r.bottom()), (r.left() + 8, r.bottom())])
        if mode_holo():
            g.setColorAt(0.0, QColor(90, 210, 255, 75 if dedans else 38))
            g.setColorAt(1.0, QColor(30, 140, 255, 45 if dedans else 12))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawPolygon(forme)
            _lueur(p, forme, CYAN, dedans)
        else:
            g.setColorAt(0.0, QColor("#5a6a74") if not dedans else QColor("#2f8fb2"))
            g.setColorAt(0.5, QColor("#26323a") if not dedans else QColor("#15546d"))
            g.setColorAt(1.0, QColor("#141b20"))
            p.setBrush(QBrush(g))
            p.setPen(QPen(_c(CYAN_CLAIR, 0.5), 1.2))
            p.drawPolygon(forme)
        p.fillRect(QRectF(r.left() + 30, r.bottom() + 2, r.width() - 10, 3), _c(CYAN, 0.9))
        p.fillRect(QRectF(r.left() - 6, r.top() + 4, 3, 10), _c(CYAN, 0.8))
        _dessin_icone(p, canvas, icone, QRectF(r.left() + 10, r.top() + 10, 34, 34))
        _texte(p, r.left() + 52, r.top(), r.width() - 56, r.height(), nom, 17,
               CYAN_CLAIR if dedans else BLANC)
        zones.append((r, ("ouvrir", action)))
        x += 196


def _grille(p, survol, zones):
    for i, (nom, chemin) in enumerate(DOSSIERS):
        col, lig = i % 2, i // 2
        r = QRectF(180 + col * 162, 232 + lig * 76, 142, 50)
        dedans = survol is not None and r.contains(survol)
        _bouton(p, r, dedans)
        _texte(p, r.left(), r.top(), r.width(), r.height(), nom, 15 if len(nom) < 12 else 13,
               CYAN_CLAIR if dedans else BLANC, align=Qt.AlignmentFlag.AlignHCenter)
        zones.append((r, ("ouvrir", ("dossier", chemin))))


def _colonne_sites(p, survol, zones):
    p.setPen(QPen(_c(CYAN, 0.5), 1.5))
    p.drawLine(QPointF(1592, 235), QPointF(1592, 640))   # en miroir des dossiers de gauche (26/10)
    for i, (nom, url) in enumerate(SITES):
        r = QRectF(VW - 180 - 132, 232 + i * 54, 132, 46)   # bord droit à 180 px, comme les dossiers à gauche
        dedans = survol is not None and r.contains(survol)
        _bouton(p, r, dedans, biseau=8)
        _texte(p, r.left(), r.top(), r.width(), r.height(), nom, 14,
               CYAN_CLAIR if dedans else BLANC, align=Qt.AlignmentFlag.AlignHCenter)
        zones.append((r, ("ouvrir", ("url", url))))


def _reacteur(p, canvas, cx, cy, r, amp, parle):
    lift = 0.6 + 0.4 * min(1.0, amp * 2 + (0.35 if parle else 0.0))
    g = QRadialGradient(cx, cy, r * 2.6)
    g.setColorAt(0.0, _c(CYAN_CLAIR, 0.75 * lift))
    g.setColorAt(0.3, _c(CYAN, 0.35 * lift))
    g.setColorAt(1.0, _c(BLEU, 0.0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(cx, cy), r * 2.6, r * 2.6)
    c = QRadialGradient(cx, cy, r)
    c.setColorAt(0.0, _c(BLANC, 1.0))
    c.setColorAt(0.6, _c(CYAN_CLAIR, 0.95))
    c.setColorAt(1.0, _c(CYAN, 0.6))
    p.setBrush(QBrush(c))
    p.drawEllipse(QPointF(cx, cy), r, r)
    t = getattr(canvas, "_core_phase", 0.0)
    p.setPen(QPen(_c(BLEU, 0.9), 3))
    p.setBrush(Qt.BrushStyle.NoBrush)
    base = (t * (160 if parle else 40)) % 360
    for k in range(3):
        p.drawArc(QRectF(cx - r * 0.62, cy - r * 0.62, r * 1.24, r * 1.24),
                  int((base + k * 120) * 16), int(80 * 16))


def _corbeille(p, survol, zones, cx, cy):
    taille, n = DONNEES.corbeille
    x0, y0 = cx + 70, cy - 30
    r = QRectF(x0, y0 - 4, 240, 58)
    dedans = survol is not None and r.contains(survol)
    _texte(p, x0, y0, 220, 22, "CORBEILLE", 18, CYAN_CLAIR if dedans else BLANC)
    _texte(p, x0 + 6, y0 + 24, 220, 14, f"Taille :  {taille:.1f} Mo", 11, BLANC, gras=False)
    _texte(p, x0 + 6, y0 + 38, 220, 14, f"Éléments :  {n}", 11, BLANC, gras=False)
    p.setPen(QPen(_c(BLANC, 0.7), 1))
    p.drawLine(QPointF(x0, y0 + 23), QPointF(x0 + 70, y0 + 23))
    zones.append((r, ("ouvrir", ("shell", "shell:RecycleBinFolder"))))


def _date(p):
    t = time.localtime()
    ch = QPainterPath()
    f = _police(110, "Bahnschrift Light Condensed", False)
    ch.addText(QPointF(0, 0), f, f"{t.tm_mday:02d}")
    br = ch.boundingRect()
    ch.translate(1858 - br.right(), 128 - br.bottom())
    if decor_cercle():
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(CYAN_CLAIR))
    else:
        p.setBrush(QBrush(_c(CYAN_CLAIR, 0.12))); p.setPen(QPen(CYAN_CLAIR, 3))
    p.drawPath(ch)
    p.fillRect(QRectF(1716, 142, 150, 24), _c(BLEU, 0.85))
    _texte(p, 1716, 142, 146, 24, MOIS[t.tm_mon - 1], 18, BLANC, align=Qt.AlignmentFlag.AlignRight)
    _texte(p, 1716, 166, 146, 20, JOURS[t.tm_wday], 15, TEXTE_INFO, nom="Consolas",
           align=Qt.AlignmentFlag.AlignRight)
    m = DONNEES.meteo
    txt = f"{LIEU['ville'].upper()}  ·  MÉTÉO…"
    if m:
        try:
            cur = m["current"]
            txt = f"{LIEU['ville'].upper()}  ·  {round(cur['temperature_2m'])}°  ·  {_meteo_mot(int(cur['weather_code']))}"
        except Exception:
            pass
    _texte(p, 1500, 192, 362, 20, txt, 14, TEXTE_INFO, nom="Consolas", align=Qt.AlignmentFlag.AlignRight)


def _horloge_musique(p, survol, zones):
    # Boutons de musique et volume (à la place de ÉTEINDRE / REDÉMARRER, par prudence).
    x = 1290.0
    for txt, vk in (("⏮  PRÉC.", 0xB1), ("⏯  LECTURE", 0xB3), ("⏭  SUIV.", 0xB0), ("VOL −", 0xAE), ("VOL +", 0xAF)):
        r = QRectF(x, 974, 98 if "VOL" not in txt else 70, 22)
        dedans = survol is not None and r.contains(survol)
        p.setBrush(QBrush(_verre(QColor(8, 24, 32, 230), 40) if not dedans else _verre(QColor(30, 100, 130, 230), 80)))
        p.setPen(QPen(_c(CYAN, 0.5), 1))
        p.drawPolygon(_poly([(r.left() + 6, r.top()), (r.right(), r.top()), (r.right() - 6, r.bottom()),
                             (r.left(), r.bottom())]))
        _texte(p, r.left(), r.top(), r.width(), r.height(), txt, 11, BLANC,
               align=Qt.AlignmentFlag.AlignHCenter, nom="Segoe UI Symbol")
        zones.append((r, ("touche", vk)))
        x += r.width() + 6
    _texte(p, 1600, 990, 252, 46, time.strftime("%H  %M"), 40, CYAN_CLAIR,
           nom="Bahnschrift Light Condensed", gras=False, align=Qt.AlignmentFlag.AlignRight)
    _texte(p, 1856, 994, 40, 20, time.strftime("%S"), 15, CYAN_CLAIR, nom="Consolas")
    _texte(p, 1590, 1036, 290, 16, "HEURE DE PARIS", 13, TEXTE_INFO, nom="Consolas",
           align=Qt.AlignmentFlag.AlignRight)


def _badge(p, canvas, amp, parle):
    cx, cy, r = 212.0, 975.0, 46.0
    t = getattr(canvas, "_core_phase", 0.0)
    g = QRadialGradient(cx, cy, r * 1.6)
    g.setColorAt(0.0, _c(CYAN, 0.35 + 0.3 * min(1.0, amp * 2)))
    g.setColorAt(1.0, _c(CYAN, 0.0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(cx, cy), r * 1.6, r * 1.6)
    p.setBrush(QBrush(_verre(QColor(2, 14, 22, 240), 60)))
    p.setPen(QPen(CYAN_CLAIR, 3))
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.setPen(QPen(_c(CYAN, 0.8), 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    base = (t * (120 if parle else 30)) % 360
    for k in range(2):
        p.drawArc(QRectF(cx - r * 0.82, cy - r * 0.82, r * 1.64, r * 1.64),
                  int((base + k * 180) * 16), int(120 * 16))
    _texte(p, cx - r, cy - 12, 2 * r, 24, "J.A.R.V.I.S", 14, BLANC, align=Qt.AlignmentFlag.AlignHCenter)
    _texte(p, 280, 948, 300, 26, _etat(canvas), 17, CYAN_CLAIR, gras=False)
    _texte(p, 280, 976, 300, 18, "MARK LV  ·  F2 ANCIEN ÉCRAN  ·  F11 FENÊTRE", 11, TEXTE_INFO,
           nom="Consolas")


def _etat(canvas) -> str:
    if canvas.muted:
        return "Micro coupé (F4)"
    if canvas.speaking:
        return "Jarvis vous répond…"
    if canvas.state in ("THINKING", "PROCESSING"):
        return "Jarvis réfléchit…"
    if canvas.state == "LISTENING":
        return "Je vous écoute."
    return "Jarvis se prépare…"


def _ram(p):
    _texte(p, 18, 448, 90, 22, f"{DONNEES.pc['ram']:.0f}%", 20, TEXTE_INFO, nom="Consolas")


# ── Point d'entrée ───────────────────────────────────────────────────────────

def _balayage_holo(p, s, ox, oy):
    """Lignes de projection et barre lumineuse qui descend sur l'armure, comme un hologramme."""
    hx, hy, w, _k = _holo_geo(1046.0, 1034.0)
    p.save()
    p.translate(ox, oy)
    p.scale(s, s)
    zone = QRectF(hx + w * 0.08, hy, w * 0.84, HOLO_H)
    # (les traits horizontaux sur l'armure ont été enlevés le 28/10 à la demande de l'utilisateur)
    t = time.monotonic()
    yb = zone.top() + (t * 120.0) % zone.height()
    g = QLinearGradient(0, yb - 40, 0, yb + 6)
    g.setColorAt(0.0, QColor(120, 230, 255, 0))
    g.setColorAt(1.0, QColor(160, 240, 255, 60 + int(20 * (1 + math.sin(t * 7)))))
    p.fillRect(QRectF(zone.left(), yb - 40, zone.width(), 46), QBrush(g))
    p.restore()


def paint(canvas, p: QPainter, W: float, H: float) -> None:
    DONNEES.maj()
    s = min(W / VW, H / VH)
    ox, oy = (W - VW * s) / 2, (H - VH * s) / 2
    dpr = canvas.devicePixelRatioF() if hasattr(canvas, "devicePixelRatioF") else 1.0
    cle = (int(W), int(H), dpr)
    if getattr(canvas, "_iron_fixe_cle", None) != cle:
        canvas._iron_fixe = _couche_fixe(W, H, s, ox, oy, dpr)
        canvas._iron_fixe_cle = cle
    p.drawPixmap(0, 0, canvas._iron_fixe)
    canvas._iron_tf = (s, ox, oy)
    if mode_holo():
        return _paint_vivant(canvas, p, s, ox, oy, dpr)

    survol = getattr(canvas, "_iron_survol", None)
    if survol is not None:
        survol = QPointF((survol.x() - ox) / s, (survol.y() - oy) / s)
    zones = []
    amp = getattr(canvas, "_amp_disp", 0.0)

    p.save()
    p.translate(ox, oy)
    p.scale(s, s)
    hx, hy, _w, k = _holo_geo(1046.0, 1034.0)
    rx, ry = hx + HOLO_REACTEUR[0] * k, hy + HOLO_REACTEUR[1] * k
    _reacteur(p, canvas, rx, ry, 30, amp, canvas.speaking)
    _infos(p)
    _petits_onglets(p, canvas, survol, zones)
    _grands_onglets(p, canvas, survol, zones)
    _grille(p, survol, zones)
    _colonne_sites(p, survol, zones)
    _corbeille(p, survol, zones, rx, ry)
    _date(p)
    _ram(p)
    _horloge_musique(p, survol, zones)
    _badge(p, canvas, amp, canvas.speaking)
    p.restore()
    canvas._iron_zones = zones


vitres.brancher(__import__("sys").modules[__name__])


_ARM = {"t": 0.0, "film": False}


def armure_film() -> bool:
    """Armure du film si le fichier existe, sauf réglage \"armure\": \"ancienne\" dans memory/interface.json."""
    now = time.monotonic()
    if now - _ARM["t"] > 1.0:
        _ARM["t"] = now
        try:
            choix = json.loads(INTERFACE.read_text(encoding="utf-8")).get("armure", "ancienne")
        except Exception:
            choix = "ancienne"
        _ARM["film"] = False
    return _ARM["film"]


def _armure_vivante(canvas, s, dpr):
    """L'armure en cache, déjà à la bonne taille en vrais pixels (dessin rapide à chaque image)."""
    film = armure_film()
    cle = (s, dpr, film)
    if getattr(canvas, "_viv_armure_cle", None) != cle:
        src = QPixmap()
        noms = ("hologramme-film.png",) if film else ("hologramme-couleur-hd.png", "hologramme-transparent-hd.png", "hologramme-transparent.png")
        for nom in noms:
            if (ASSETS / nom).exists():
                src = QPixmap(str(ASSETS / nom))
                break
        _x, _y, w, _k = _holo_geo(1046.0, 1034.0)
        if src.isNull():
            canvas._viv_armure, canvas._viv_masque = None, None
        else:
            pm = src.scaled(int(w * s * dpr), int(HOLO_H * s * dpr), Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            canvas._viv_armure = pm
            canvas._viv_masque = src.toImage().scaled(int(w * s), int(HOLO_H * s),
                                                      Qt.AspectRatioMode.IgnoreAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation)
        canvas._viv_armure_cle = cle
    return canvas._viv_armure, canvas._viv_masque


class _ZoneDecalee:
    """Zone cliquable d'un plan décalé par l'effet de profondeur : on retire le décalage avant de tester."""
    def __init__(self, zone, off):
        self.zone, self.off = zone, off

    def contains(self, pt) -> bool:
        return self.zone.contains(QPointF(pt.x() - self.off.x(), pt.y() - self.off.y()))


_PROF = {"t": 0.0, "actif": True, "force": 1.8, "x": 0.0, "y": 0.0, "dern": 0.0}


def _profondeur(survol, t):
    """Effet de profondeur (28/10, demande de l'utilisateur : un meilleur rendu « hologramme »).

    Trois plans se décalent à des vitesses différentes quand la souris bouge (et un peu tout seul, très
    lentement) : le fond (loin) presque pas, l'armure et le cœur (au milieu) un peu, les grandes vitres
    (devant) beaucoup. Le cerveau fait ainsi comme une fenêtre : les plans proches glissent plus vite.
    Réglages dans memory/interface.json : "profondeur": true/false, "profondeur_force": 1.8 par défaut (0 à 2,5).
    Renvoie (décalage loin, décalage milieu, décalage devant) en unités de l'écran virtuel 1920x1080.
    """
    now = time.monotonic()
    if now - _PROF["t"] > 1.0:
        _PROF["t"] = now
        try:
            r = json.loads(INTERFACE.read_text(encoding="utf-8"))
            _PROF["actif"] = bool(r.get("profondeur", True))
            _PROF["force"] = max(0.0, min(2.5, float(r.get("profondeur_force", 1.8))))
        except Exception:
            pass
    if not _PROF["actif"]:
        z = QPointF(0.0, 0.0)
        return z, z, z
    if survol is not None:
        cx = max(-1.0, min(1.0, (survol.x() - VW / 2) / (VW / 2)))
        cy = max(-1.0, min(1.0, (survol.y() - VH / 2) / (VH / 2)))
    else:
        cx = cy = 0.0
    cx = 0.7 * cx + 0.60 * math.sin(t * 0.33)
    cy = 0.7 * cy + 0.35 * math.sin(t * 0.21 + 1.0)
    dt = min(0.2, max(0.0, now - _PROF["dern"]))
    _PROF["dern"] = now
    k = 1.0 - math.exp(-dt * 4.0)                      # adoucissement : jamais de saccade
    _PROF["x"] += (cx - _PROF["x"]) * k
    _PROF["y"] += (cy - _PROF["y"]) * k
    f = _PROF["force"]
    vx, vy = _PROF["x"] * f, _PROF["y"] * f
    return QPointF(-vx * 3.5, -vy * 2.0), QPointF(-vx * 11.0, -vy * 7.0), QPointF(-vx * 30.0, -vy * 18.0)


_CALME = {"t": 0.0, "v": True}


def calme() -> bool:
    """Mode calme (30/10 : le mouvement donne la nausée à l'utilisateur) : rien ne bouge, sauf les lumières.
    Réglage "calme": false dans memory/interface.json pour redonner le flottement, la respiration et la profondeur."""
    now = time.monotonic()
    if now - _CALME["t"] > 1.0:
        _CALME["t"] = now
        try:
            _CALME["v"] = bool(json.loads(INTERFACE.read_text(encoding="utf-8")).get("calme", True))
        except Exception:
            _CALME["v"] = True
    return _CALME["v"]


def _respiration(p, pivot, sway, sy) -> None:
    """Le robot respire (grandit un peu de la tête) et se balance à peine, autour de ses pieds."""
    p.translate(pivot); p.rotate(sway); p.scale(1.0, sy); p.translate(-pivot.x(), -pivot.y())


def _paint_vivant(canvas, p, s, ox, oy, dpr) -> None:
    """Mode hologramme : le Jarvis vivant (core/jarvis_vivant.py, aperçu validé par l'utilisateur le 28/10)."""
    survol = getattr(canvas, "_iron_survol", None)
    if survol is not None:
        survol = QPointF((survol.x() - ox) / s, (survol.y() - oy) / s)
    e, t = viv.maj(canvas, survol)
    if decor_cercle():
        return _paint_cercle(canvas, p, s, ox, oy, e, t, survol)
    off_loin, off_milieu, off_devant = _profondeur(survol, t)
    if calme():
        off_loin = off_milieu = QPointF(0.0, 0.0)
    off_devant = QPointF(0.0, 0.0)          # les vitres et leurs icônes ne bougent pas (l'utilisateur, 28/10)
    amp = getattr(canvas, "_amp_disp", 0.0)
    now = time.monotonic()
    force = 0.25 + 0.75 * e.eveil
    glitch = now < e.glitch_fin
    hx, hy, w, k = _holo_geo(1046.0, 1034.0)
    dy = 6 * math.sin(t * 2 * math.pi / 5.5)                 # il flotte
    resp = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 4.2)       # il respire
    centre = QPointF(hx + w * 0.56, hy + HOLO_H * 0.5 + dy)
    film = armure_film()
    r0 = FILM_REACTEUR if film else HOLO_REACTEUR
    reacteur = QPointF(hx + r0[0] * k, hy + r0[1] * k + dy)
    if film:
        les_yeux = [QPointF(hx + x * k, hy + y * k + dy) for x, y in FILM_YEUX]
    else:
        les_yeux = [QPointF(hx + 525 * k, hy + 200.5 * k + dy), QPointF(hx + 583 * k, hy + 193 * k + dy)]
    sol = QPointF(hx + w * 0.56, hy + HOLO_H - 18)
    sway = 0.45 * math.sin(t * 2 * math.pi / 7.3)             # balancement (degrés)
    sy = 1.0 + 0.011 * resp                                   # respiration
    if calme():
        dy, sway, sy = 0.0, 0.0, 1.0                          # mode calme : le corps ne bouge pas

    p.save(); p.translate(ox, oy); p.scale(s, s); p.translate(off_loin.x(), off_loin.y())
    viv.anneaux_sol(p, sol, t, 0.3 + 0.7 * force)
    g = QRadialGradient(centre, w * 0.6)
    g.setColorAt(0.0, viv.coul(255, 90, 40, (35 + 20 * resp) * force))
    g.setColorAt(1.0, viv.coul(255, 90, 40, 0))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(centre, w * 0.6, HOLO_H * 0.52)
    p.restore()

    armure, masque = _armure_vivante(canvas, s, dpr)
    if armure is not None:
        x0, y0 = ox + (hx + off_milieu.x()) * s, oy + (hy + dy + off_milieu.y()) * s
        p.save()
        _respiration(p, QPointF(ox + (sol.x() + off_milieu.x()) * s, oy + (sol.y() + off_milieu.y()) * s), sway, sy)
        opac = 0.30 + 0.62 * e.eveil
        if glitch:
            opac *= random.uniform(0.45, 0.8)
            p.setOpacity(0.35)
            p.drawPixmap(QPointF(x0 - 9 * s, y0), armure)
            p.drawPixmap(QPointF(x0 + 7 * s, y0 + 2 * s), armure)
        p.setOpacity(opac)
        p.drawPixmap(QPointF(x0, y0), armure)
        p.setOpacity(1.0)
        if e.reflexion > 0.02 and masque is not None:
            p.setCompositionMode(viv.PLUS)
            p.drawImage(QPointF(x0, y0), viv.circuits(masque, t, e.reflexion))
            p.setCompositionMode(viv.NORMAL)
        p.restore()

    p.save(); p.translate(ox, oy); p.scale(s, s); p.translate(off_milieu.x(), off_milieu.y())
    p.save(); _respiration(p, sol, sway, sy)
    f_yeux = 0.35 + 0.65 * e.ecoute
    f_yeux = f_yeux * (1 - e.parle) + e.parle * (0.6 + 0.4 * min(1.0, amp * 2))
    f_yeux = f_yeux * (1 - e.reflexion) + e.reflexion * (0.55 + 0.25 * math.sin(t * 9))
    viv.yeux(p, les_yeux, f_yeux * (0.25 + 0.75 * e.eveil))
    batt = e.parle * min(1.0, amp * 2) + (1 - e.parle) * e.eveil * (0.25 + 0.25 * math.sin(t * 2 * math.pi / 1.1))
    if film:
        viv.coeur_triangle(p, reacteur, t, force, batt, 1 + 3.5 * e.reflexion + 1.5 * e.parle)
    else:
        viv.coeur(p, reacteur, t, force, batt, 1 + 3.5 * e.reflexion + 1.5 * e.parle)
    if e.ecoute > 0.02:
        viv.anneau_ecoute(p, reacteur, t, e.ecoute)
    if e.parle > 0.02:
        viv.onde_poitrine(p, reacteur, t, min(1.0, amp * 2) * e.parle)
    viv.particules(p, sol, t, force)

    p.restore()                                          # fin de la respiration
    p.translate(-off_milieu.x(), -off_milieu.y())        # retour au plan de l'écran
    zones = []
    if e.boutons > 0.01:
        # Les boutons sont rangés dans trois grandes vitres penchées en 3D (core/panneaux_holo.py, 28/10)
        p.setOpacity(e.boutons)
        p.save(); p.translate(off_devant.x(), off_devant.y())
        s_dev = None if survol is None else QPointF(survol.x() - off_devant.x(), survol.y() - off_devant.y())
        n0 = len(zones)
        vitres.dessiner(p, canvas, s_dev, zones)
        _corbeille(p, s_dev, zones, reacteur.x() + 90, reacteur.y())
        p.restore()
        zones[n0:] = [(_ZoneDecalee(r, off_devant), v) for r, v in zones[n0:]]
        p.setOpacity(1.0)
        if e.boutons < 0.3:
            zones = []          # pas de clic sur un bouton encore invisible
    p.setOpacity(0.35 + 0.65 * e.eveil)
    _date(p)
    _horloge_musique(p, survol, zones)
    _badge(p, canvas, amp, canvas.speaking)
    p.setOpacity(1.0)

    # (plus de sous-titres sous l'armure : l'utilisateur ne veut pas d'écriture quand il parle, 28/10)
    p.restore()
    canvas._iron_zones = zones


def _couche_cercle(canvas, W, H, s, ox, oy, dpr, e, amp, t):
    """Décor fixe rendu une fois par seconde, avec un effet néon (bloom) : la lumière irradie
    autour des anneaux, des lignes et du cœur, sans faire baver les écritures."""
    hud = __import__("sys").modules[__name__]
    zones = []
    pm = QImage(int(W * dpr), int(H * dpr), QImage.Format.Format_ARGB32_Premultiplied); pm.setDevicePixelRatio(dpr)
    q = QPainter(pm)
    q.setRenderHint(QPainter.RenderHint.Antialiasing); q.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    decor.fond(q, W, H)
    q.save(); q.translate(ox, oy); q.scale(s, s)
    decor.dessiner(q, e, amp, t, None, zones, hud, _etat(canvas))
    q.restore()
    # bloom : on redessine le décor sans texte en petit, on le floute en le réduisant encore,
    # puis on l'ajoute par-dessus en lumière (deux tailles : halo serré et halo large)
    cle_b = (int(W), int(H), dpr, int(time.time() // 20), round(decor._activite(e, amp) * 5) / 5)
    if getattr(canvas, "_bloom_cle", None) != cle_b:
        canvas._bloom = _halos(W, H, s, ox, oy, e, amp, t, hud)
        canvas._bloom_cle = cle_b
    for im, force in canvas._bloom:
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus); q.setOpacity(force)
        q.drawImage(QRectF(0, 0, W, H), im)
        q.setOpacity(1.0); q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    # vignette : les bords plus sombres, le regard va au centre
    g = QRadialGradient(W * 0.45, H * 0.5, W * 0.75)
    g.setColorAt(0.6, QColor(0, 0, 0, 0)); g.setColorAt(1.0, QColor(0, 0, 10, 150))
    q.fillRect(QRectF(0, 0, W, H), QBrush(g))
    q.end()
    return pm, zones


def _halos(W, H, s, ox, oy, e, amp, t, hud):
    """Le décor sans texte, en tout petit puis réduit encore : une fois agrandi, c'est un halo flou."""
    out = []
    for larg, force in ((480, 0.22), (160, 0.16)):
        h = int(larg * H / W)
        im = QImage(larg, h, QImage.Format.Format_ARGB32_Premultiplied); im.fill(Qt.GlobalColor.black)
        b = QPainter(im); b.setRenderHint(QPainter.RenderHint.Antialiasing)
        k = larg / W
        b.scale(k, k); b.translate(ox, oy); b.scale(s, s)
        decor.SANS_TEXTE[0] = True
        try:
            decor.dessiner(b, e, amp, t, None, [], hud, "")
        finally:
            decor.SANS_TEXTE[0] = False
        b.end()
        im = im.scaled(larg // 2, h // 2, transformMode=Qt.TransformationMode.SmoothTransformation)
        im = im.scaled(larg // 4, h // 4, transformMode=Qt.TransformationMode.SmoothTransformation)
        out.append((im.scaled(int(W / 2), int(H / 2), transformMode=Qt.TransformationMode.SmoothTransformation), force))
    return out


def _paint_cercle(canvas, p, s, ox, oy, e, t, survol) -> None:
    """Décor « grand cercle bleu » : tout est dans l'image, plus de vitres 3D (l'utilisateur, 30/10)."""
    amp = getattr(canvas, "_amp_disp", 0.0)
    W, H = ox * 2 + VW * s, oy * 2 + VH * s
    dpr = canvas.devicePixelRatioF() if hasattr(canvas, "devicePixelRatioF") else 1.0
    act = round(decor._activite(e, amp) * 5) / 5
    cle = (int(W), int(H), dpr, int(time.time()), act)
    if getattr(canvas, "_cercle_pm", None) is None or canvas._cercle_pm.width() != int(W * dpr):
        canvas._cercle_pm, canvas._cercle_zones = _couche_cercle(canvas, W, H, s, ox, oy, dpr, e, amp, t)
        canvas._cercle_cle = cle
    elif canvas._cercle_cle != cle and not getattr(canvas, "_cercle_occupe", False):
        # le redessin (chiffres, heure) se fait à côté : l'image affichée ne s'arrête jamais
        canvas._cercle_occupe = True
        canvas._cercle_cle = cle

        def travail():
            try:
                canvas._cercle_pm, canvas._cercle_zones = _couche_cercle(canvas, W, H, s, ox, oy, dpr, e, amp, t)
            finally:
                canvas._cercle_occupe = False
        threading.Thread(target=travail, daemon=True).start()
    p.drawImage(QPointF(0, 0), canvas._cercle_pm)
    zones = canvas._cercle_zones
    p.save(); p.translate(ox, oy); p.scale(s, s)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    decor.vivant(p, e, amp, t, survol, zones)
    p.restore()
    canvas._iron_zones = zones


def click(canvas, pos) -> bool:
    s, ox, oy = getattr(canvas, "_iron_tf", (1.0, 0.0, 0.0))
    v = QPointF((pos.x() - ox) / s, (pos.y() - oy) / s)
    for r, (genre, val) in getattr(canvas, "_iron_zones", []):
        if r.contains(v):
            if genre == "ouvrir":
                _ouvrir(val)
            else:
                _touche(val)
            return True
    return False
