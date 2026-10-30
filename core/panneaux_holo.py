"""
Les grandes vitres de l'écran HUD (demande de l'utilisateur, 2026-10-28, d'après une image de
panneaux holographiques) : les boutons sont rangés dans trois grandes vitres de verre penchées
en 3D (PROGRAMMES en haut, DOSSIERS à gauche, SITES INTERNET à droite), reliées à Jarvis par des
lignes de lumière où court une goutte. Chaque bouton a une icône ronde en verre ; les vrais logos
sont redessinés en lumière bleu-blanc. Utilisé par core/iron_hud.py en mode hologramme.
"""
from __future__ import annotations

import math
import time

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPolygonF, QRadialGradient, QTransform)

PLUS = QPainter.CompositionMode.CompositionMode_Plus
NORMAL = QPainter.CompositionMode.CompositionMode_SourceOver
hud = None   # core.iron_hud, branché par brancher() (évite l'import circulaire)


def brancher(module) -> None:
    global hud
    hud = module


def coul(r, g, b, a):
    return QColor(int(r), int(g), int(b), int(max(0, min(255, a))))


_cache = {}


def logo_holo(pm):
    """Le vrai logo transformé en hologramme : sa forme, en lumière bleu-blanc."""
    k = pm.cacheKey()
    if k in _cache:
        return _cache[k]
    im = pm.toImage().scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = im.width(), im.height()
    ptr = im.constBits(); ptr.setsize(im.sizeInBytes())
    a = np.frombuffer(ptr, np.uint8).reshape(h, im.bytesPerLine())[:, :w * 4].reshape(h, w, 4).astype(float) / 255
    opaque = a[..., 3] > 0.5
    # couleur dominante du logo (souvent le fond du logo) : elle devient un voile léger,
    # tout ce qui s'en distingue (le dessin) devient de la lumière
    q = (a[..., :3][opaque] * 7).round().astype(int)
    codes, nb = np.unique(q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2], return_counts=True)
    dom = codes[nb.argmax()]; dom = np.array([dom // 64, dom // 8 % 8, dom % 8]) / 7
    ecart = np.clip(np.sqrt(((a[..., :3] - dom) ** 2).sum(-1)) * 1.6, 0, 1)
    al = a[..., 3]
    gx = np.abs(np.diff(al, axis=1, prepend=al[:, :1])); gy = np.abs(np.diff(al, axis=0, prepend=al[:1]))
    bord = np.clip((gx + gy) * 2.5, 0, 1)
    v = np.clip(0.35 + 0.65 * ecart + bord, 0, 1)
    alpha = al * np.clip(0.18 + 0.82 * ecart + bord, 0, 1)
    out = np.zeros((h, w, 4))
    out[..., 0] = (90 + 165 * v) * alpha
    out[..., 1] = (200 + 55 * v) * alpha
    out[..., 2] = 255 * alpha
    out[..., 3] = 255 * alpha
    buf = np.ascontiguousarray(out.astype(np.uint8))
    img = QImage(buf.data, w, h, w * 4, QImage.Format.Format_RGBA8888_Premultiplied).copy()
    _cache[k] = img
    return img


def picto(p, nom, r: QRectF, col):
    """Pictogrammes en traits de lumière pour ce qui n'a pas de logo."""
    w, h, x, y = r.width(), r.height(), r.left(), r.top()
    P = lambda u, v: QPointF(x + u * w, y + v * h)
    p.setPen(QPen(col, max(1.2, w * 0.07), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if nom in ("dossier", "FICHIERS", "BUREAU", "DOCUMENTS"):
        p.drawPolygon(QPolygonF([P(.08, .25), P(.42, .25), P(.5, .35), P(.92, .35), P(.92, .82), P(.08, .82)]))
        if nom == "DOCUMENTS":
            p.drawLine(P(.25, .52), P(.75, .52)); p.drawLine(P(.25, .66), P(.6, .66))
    elif nom == "TÉLÉCHARGEMENTS":
        p.drawLine(P(.5, .12), P(.5, .62)); p.drawPolyline(QPolygonF([P(.3, .45), P(.5, .65), P(.7, .45)]))
        p.drawPolyline(QPolygonF([P(.12, .68), P(.12, .86), P(.88, .86), P(.88, .68)]))
    elif nom in ("CERVEAU", "cerveau"):
        p.drawEllipse(P(.36, .45), w * .2, h * .25); p.drawEllipse(P(.64, .45), w * .2, h * .25)
        p.drawLine(P(.5, .25), P(.5, .72)); p.drawLine(P(.5, .72), P(.5, .88))
    elif nom == "PRODUCTIONS":
        p.drawRect(QRectF(x + w * .1, y + h * .3, w * .8, h * .55))
        p.drawPolyline(QPolygonF([P(.1, .3), P(.2, .14), P(.9, .14), P(.9, .3)]))
        p.drawLine(P(.3, .14), P(.22, .3)); p.drawLine(P(.55, .14), P(.47, .3))
    elif nom == "CAPTURES":
        p.drawRoundedRect(QRectF(x + w * .08, y + h * .3, w * .84, h * .55), 3, 3)
        p.drawEllipse(P(.5, .57), w * .17, h * .17); p.drawLine(P(.32, .3), P(.4, .18)); p.drawLine(P(.4, .18), P(.6, .18)); p.drawLine(P(.6, .18), P(.68, .3))
    elif nom == "IMAGES":
        p.drawRect(QRectF(x + w * .08, y + h * .18, w * .84, h * .66))
        p.drawPolyline(QPolygonF([P(.12, .78), P(.4, .48), P(.6, .66), P(.72, .55), P(.88, .72)]))
        p.drawEllipse(P(.7, .34), w * .06, h * .06)
    elif nom == "MUSIQUE":
        p.drawLine(P(.38, .72), P(.38, .18)); p.drawLine(P(.38, .18), P(.82, .1)); p.drawLine(P(.82, .1), P(.82, .64))
        p.drawEllipse(P(.28, .74), w * .11, h * .09); p.drawEllipse(P(.72, .66), w * .11, h * .09)
    elif nom == "VIDÉOS":
        p.drawRoundedRect(QRectF(x + w * .08, y + h * .25, w * .6, h * .5), 3, 3)
        p.drawPolygon(QPolygonF([P(.68, .42), P(.92, .28), P(.92, .72), P(.68, .58)]))
    elif nom == "JARVIS":
        p.drawEllipse(P(.5, .5), w * .38, h * .38); p.drawEllipse(P(.5, .5), w * .14, h * .14)
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(QPointF(r.center().x() + math.cos(a) * w * .2, r.center().y() + math.sin(a) * h * .2),
                       QPointF(r.center().x() + math.cos(a) * w * .32, r.center().y() + math.sin(a) * h * .32))
    elif nom in ("youtube", "YOUTUBE", "MA CHAÎNE"):
        p.drawRoundedRect(QRectF(x + w * .06, y + h * .2, w * .88, h * .6), w * .15, h * .15)
        p.drawPolygon(QPolygonF([P(.42, .36), P(.42, .64), P(.65, .5)]))
    elif nom in ("GMAIL",):
        p.drawRect(QRectF(x + w * .08, y + h * .22, w * .84, h * .56)); p.drawPolyline(QPolygonF([P(.08, .22), P(.5, .55), P(.92, .22)]))
    elif nom in ("AGENDA",):
        p.drawRect(QRectF(x + w * .1, y + h * .2, w * .8, h * .68)); p.drawLine(P(.1, .38), P(.9, .38))
        p.drawLine(P(.3, .1), P(.3, .26)); p.drawLine(P(.7, .1), P(.7, .26))
        for u in (.3, .5, .7):
            p.drawPoint(P(u, .55)); p.drawPoint(P(u, .72))
    elif nom == "MÉTÉO":
        p.drawEllipse(P(.38, .38), w * .16, h * .16)
        path = QPainterPath(P(.25, .8)); path.cubicTo(P(.05, .8), P(.1, .52), P(.35, .58)); path.cubicTo(P(.42, .4), P(.75, .42), P(.75, .6))
        path.cubicTo(P(.95, .6), P(.95, .8), P(.78, .8)); path.closeSubpath(); p.drawPath(path)
    elif nom == "SUNO":
        for i, hh in enumerate((.3, .6, .9, .5, .75, .35)):
            u = .15 + i * .14; p.drawLine(P(u, .5 - hh / 2.4), P(u, .5 + hh / 2.4))
    elif nom == "TRADUCTION":
        p.drawRoundedRect(QRectF(x + w * .08, y + h * .12, w * .55, h * .5), 3, 3)
        p.drawRoundedRect(QRectF(x + w * .38, y + h * .4, w * .55, h * .5), 3, 3)
        p.drawLine(P(.22, .48), P(.35, .22)); p.drawLine(P(.35, .22), P(.48, .48))
    elif nom == "WIKIPÉDIA":
        p.drawEllipse(P(.5, .5), w * .4, h * .4)
        p.drawPolyline(QPolygonF([P(.25, .35), P(.37, .68), P(.5, .42), P(.63, .68), P(.75, .35)]))
    else:   # url / globe
        p.drawEllipse(P(.5, .5), w * .4, h * .4); p.drawEllipse(P(.5, .5), w * .17, h * .4)
        p.drawLine(P(.1, .5), P(.9, .5))


def bouton_rond(p, canvas, cle, c, R, survol, graine):
    """Bouton rond en verre : halo, verre sombre, reflet en haut, liseré lumineux, icône en lumière."""
    t = time.monotonic()
    lum = 1.0 if survol else 0.8                      # pas de pulsation : l'icône reste fixe
    p.setCompositionMode(PLUS); p.setPen(Qt.PenStyle.NoPen)
    g = QRadialGradient(c, R * 1.8)
    g.setColorAt(0.5, coul(40, 200, 255, 70 * lum)); g.setColorAt(1.0, coul(40, 200, 255, 0))
    p.setBrush(QBrush(g)); p.drawEllipse(c, R * 1.8, R * 1.8)
    p.setCompositionMode(NORMAL)
    g = QRadialGradient(QPointF(c.x(), c.y() + R * 0.3), R * 1.2)
    g.setColorAt(0.0, coul(20, 90, 110, 200)); g.setColorAt(1.0, coul(4, 24, 36, 210))
    p.setBrush(QBrush(g)); p.drawEllipse(c, R, R)
    # reflet du verre
    hl = QLinearGradient(0, c.y() - R, 0, c.y())
    hl.setColorAt(0.0, coul(200, 250, 255, 90)); hl.setColorAt(1.0, coul(200, 250, 255, 0))
    p.setBrush(QBrush(hl)); p.drawEllipse(QPointF(c.x(), c.y() - R * 0.45), R * 0.75, R * 0.45)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setCompositionMode(PLUS)
    p.setPen(QPen(coul(120, 235, 255, 230 * lum), 1.6)); p.drawEllipse(c, R, R)
    p.setPen(QPen(coul(120, 235, 255, 70 * lum), 1)); p.drawEllipse(c, R * 0.8, R * 0.8)
    # un arc qui tourne doucement sur le bord (il est « vivant »)
    p.setPen(QPen(coul(220, 252, 255, 230), 2.4))
    a = (graine * 90) % 360                          # l'arc ne tourne plus (fixe)
    p.drawArc(QRectF(c.x() - R, c.y() - R, 2 * R, 2 * R), int(a * 16), int(50 * 16))
    inner = QRectF(c.x() - R * 0.55, c.y() - R * 0.55, R * 1.1, R * 1.1)
    pm = hud._icone(canvas, cle) if canvas is not None else None
    if pm is not None:
        p.setOpacity(lum)
        holo = logo_holo(pm); p.drawImage(inner, holo, QRectF(holo.rect())); p.setOpacity(1.0)
    else:
        picto(p, cle, inner, coul(170, 240, 255, 255 * lum))
    p.setCompositionMode(NORMAL)


def quad(flat_w, flat_h, pts):
    t = QTransform()
    ok = QTransform.quadToQuad(QPolygonF([QPointF(0, 0), QPointF(flat_w, 0), QPointF(flat_w, flat_h), QPointF(0, flat_h)]),
                               QPolygonF([QPointF(*p) for p in pts]), t)
    return t


def flot(t, graine):
    return 0.0          # les vitres et leurs icônes ne bougent pas (demande de l'utilisateur, 28/10)


def vitre(p, w, h, titre, t, sous_titre=""):
    """La grande vitre : verre bleu, bord épais qui luit, reflet, coins en équerre, titre."""
    r = QRectF(0, 0, w, h)
    ch = QPainterPath(); ch.addRoundedRect(r, 16, 16)
    puls = 0.92                                      # bord de la vitre : lueur constante
    p.setCompositionMode(PLUS); p.setBrush(Qt.BrushStyle.NoBrush)
    for e, a in ((22, 10), (12, 22), (6, 45)):
        p.setPen(QPen(coul(40, 200, 255, a * puls), e)); p.drawPath(ch)
    p.setCompositionMode(NORMAL)
    g = QLinearGradient(0, 0, w * 0.3, h)
    g.setColorAt(0.0, coul(40, 150, 180, 105)); g.setColorAt(0.5, coul(10, 60, 90, 95)); g.setColorAt(1.0, coul(4, 30, 50, 120))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawPath(ch)
    # reflet en diagonale
    refl = QPainterPath(); refl.moveTo(w * 0.05, 0); refl.lineTo(w * 0.35, 0); refl.lineTo(w * 0.12, h * 0.6); refl.lineTo(0, h * 0.6); refl.closeSubpath()
    lg = QLinearGradient(0, 0, 0, h * 0.6)
    lg.setColorAt(0, coul(220, 250, 255, 40)); lg.setColorAt(1, coul(220, 250, 255, 0))
    p.setBrush(QBrush(lg)); p.drawPath(refl.intersected(ch))
    p.setPen(QPen(coul(150, 240, 255, 230 * puls), 2)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(ch)
    # équerres lumineuses aux coins
    p.setPen(QPen(coul(220, 252, 255, 255), 3))
    for (x, y, dx, dy) in ((8, 8, 1, 1), (w - 8, 8, -1, 1), (w - 8, h - 8, -1, -1), (8, h - 8, 1, -1)):
        p.drawLine(QPointF(x, y), QPointF(x + 22 * dx, y)); p.drawLine(QPointF(x, y), QPointF(x, y + 22 * dy))
    # titre
    hud._texte(p, 24, 12, w - 48, 34, titre, 22, hud.BLANC)
    if sous_titre:
        hud._texte(p, 24, 14, w - 48, 30, sous_titre, 12, hud.TEXTE_INFO, nom="Consolas", align=Qt.AlignmentFlag.AlignRight)
    p.setPen(QPen(coul(120, 220, 255, 140), 1)); p.drawLine(QPointF(24, 50), QPointF(w - 24, 50))
    p.fillRect(QRectF(24, 49, 90, 3), coul(120, 230, 255, 220))


def ligne_entree(p, canvas, r, cle, nom, d, graine, t, barre=True, taille=15):
    if d:
        ch = QPainterPath(); ch.addRoundedRect(r, 10, 10)
        p.setBrush(QBrush(coul(60, 190, 230, 70))); p.setPen(QPen(coul(150, 240, 255, 200), 1.2)); p.drawPath(ch)
    R = min(20.0, r.height() * 0.36)
    bouton_rond(p, canvas, cle, QPointF(r.left() + R + 8, r.center().y()), R, d, graine)
    x0 = r.left() + 2 * R + 20
    hud._texte(p, x0, r.top(), r.width() - (x0 - r.left()) - 8, r.height() * (0.62 if barre else 1), nom, taille,
               hud.CYAN_CLAIR if d else hud.BLANC)
    if barre:   # petite jauge vivante sous le nom
        y = r.top() + r.height() * 0.70
        lw = r.right() - x0 - 14
        p.fillRect(QRectF(x0, y, lw, 3), coul(80, 180, 220, 60))
        v = 0.35 + 0.55 * (0.5 + 0.5 * math.sin(t * 0.6 + graine * 2.3))
        p.fillRect(QRectF(x0, y, lw * v, 3), coul(120, 230, 255, 200))


class Panneau:
    def __init__(self, w, h, pts, graine):
        self.w, self.h, self.pts, self.graine = w, h, pts, graine

    def tf(self, t):
        dy = flot(t, self.graine)
        return quad(self.w, self.h, [(x, y + dy) for x, y in self.pts])

    def local(self, tf, s):
        if s is None:
            return None
        inv, ok = tf.inverted()
        return inv.map(s) if ok else None

    def bord(self, tf, cote):
        u, v = {"droite": (self.w, self.h / 2), "gauche": (0, self.h / 2), "bas": (self.w / 2, self.h)}[cote]
        return tf.map(QPointF(u, v))


class ZoneVitre:
    """Zone cliquable penchée : le rectangle du bouton vu à travers la perspective de la vitre."""
    def __init__(self, tf, r: QRectF):
        self.poly = tf.map(QPolygonF(r))

    def contains(self, pt) -> bool:
        return self.poly.containsPoint(pt, Qt.FillRule.OddEvenFill)


GAUCHE = Panneau(440, 560, [(50, 180), (500, 225), (500, 700), (50, 770)], 0.0)
DROITE = Panneau(400, 520, [(1430, 255), (1870, 215), (1870, 775), (1430, 710)], 1.7)
HAUT = Panneau(1060, 168, [(470, 14), (1450, 14), (1490, 176), (430, 176)], 3.1)
NOEUDS = {"g": QPointF(720, 470), "d": QPointF(1300, 470), "h": QPointF(1110, 215)}


def proche(s) -> bool:
    """La souris approche d'une vitre : on les fait apparaître."""
    return s is not None and (s.x() < 560 or s.y() < 200 or s.x() > 1400)


def dessiner(p, canvas, survol, zones) -> None:
    t = time.monotonic()
    # ── gauche : dossiers
    tf = GAUCHE.tf(t); loc = GAUCHE.local(tf, survol)
    p.save(); p.setTransform(tf, True)
    vitre(p, GAUCHE.w, GAUCHE.h, "DOSSIERS", t, f"{len(hud.DOSSIERS)} ACCÈS")
    for i, (nom, chemin) in enumerate(hud.DOSSIERS):
        col, lig = i % 2, i // 2
        r = QRectF(20 + col * 205, 66 + lig * 96, 195, 84)
        ligne_entree(p, None, r, nom, nom, loc is not None and r.contains(loc), i * 0.7, t,
                     taille=13 if len(nom) < 12 else 10)
        zones.append((ZoneVitre(tf, r), ("ouvrir", ("dossier", chemin))))
    p.restore()
    # ── droite : sites
    tf2 = DROITE.tf(t); loc = DROITE.local(tf2, survol)
    p.save(); p.setTransform(tf2, True)
    vitre(p, DROITE.w, DROITE.h, "SITES INTERNET", t, "EN LIGNE")
    for i, (nom, url) in enumerate(hud.SITES):
        r = QRectF(20, 62 + i * 56, DROITE.w - 40, 50)
        ligne_entree(p, None, r, nom, nom, loc is not None and r.contains(loc), i * 0.9, t, taille=14)
        zones.append((ZoneVitre(tf2, r), ("ouvrir", ("url", url))))
    p.restore()
    # ── haut : programmes et raccourcis
    tf3 = HAUT.tf(t); loc = HAUT.local(tf3, survol)
    p.save(); p.setTransform(tf3, True)
    vitre(p, HAUT.w, HAUT.h, "PROGRAMMES", t, "SYSTÈMES OPÉRATIONNELS")
    for i, (nom, icone, action) in enumerate(hud.GRANDS):
        r = QRectF(18 + i * 172, 58, 164, 56)
        ligne_entree(p, canvas, r, icone, nom, loc is not None and r.contains(loc), i * 1.3, t, barre=False, taille=15)
        zones.append((ZoneVitre(tf3, r), ("ouvrir", action)))
    for i, (nom, icone, action) in enumerate(hud.PETITS):
        r = QRectF(18 + i * 206, 120, 196, 38)
        cle = {"CERVEAU 3D": "CERVEAU"}.get(nom, icone if icone != "url" else nom)
        ligne_entree(p, canvas, r, cle, nom, loc is not None and r.contains(loc), i * 0.8 + 5, t, barre=False, taille=12)
        zones.append((ZoneVitre(tf3, r), ("ouvrir", action)))
    p.restore()
    # ── lignes de lumière qui relient les vitres à Jarvis
    p.setCompositionMode(PLUS)
    for pan, cote, cle, k in ((GAUCHE, "droite", "g", 0), (DROITE, "gauche", "d", 1), (HAUT, "bas", "h", 2)):
        a = pan.bord(pan.tf(t), cote); b = NOEUDS[cle]
        coude = QPointF(b.x(), a.y()) if cle == "h" else QPointF((a.x() + b.x()) / 2, a.y())
        chemin = [a, coude, b]
        for e, al in ((6, 30), (1.5, 170)):
            p.setPen(QPen(coul(110, 220, 255, al), e)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(QPolygonF(chemin))
        for q_ in (a, b):
            p.setPen(QPen(coul(170, 240, 255, 220), 1.5)); p.setBrush(QBrush(coul(60, 180, 255, 120)))
            p.drawEllipse(q_, 5, 5)
        L1 = math.dist((a.x(), a.y()), (coude.x(), coude.y())); L2 = math.dist((coude.x(), coude.y()), (b.x(), b.y()))
        u = ((t * 0.45 + k * 0.33) % 1.0) * (L1 + L2)
        pt = a + (coude - a) * (u / max(L1, 1)) if u < L1 else coude + (b - coude) * ((u - L1) / max(L2, 1))
        g = QRadialGradient(pt, 14); g.setColorAt(0, coul(230, 252, 255, 255)); g.setColorAt(1, coul(80, 200, 255, 0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(pt, 14, 14)
    p.setCompositionMode(NORMAL)
