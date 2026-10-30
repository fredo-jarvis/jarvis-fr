"""
Le « Jarvis vivant » de l'écran HUD en mode hologramme (demande de l'utilisateur, 2026-10-28).

l'utilisateur trouvait l'écran « bureautique » et le réacteur pas beau. Ici, l'armure respire et
flotte, des étincelles montent, des anneaux tournent à ses pieds, le nouveau cœur (réacteur
Arc à 10 bobines) bat, les yeux s'allument quand l'utilisateur parle, des lignes de lumière parcourent
l'armure quand il réfléchit, une onde sort de la poitrine et ses paroles s'écrivent mot à mot
quand il répond. Les boutons sont cachés et apparaissent quand la souris approche d'un bord.
Aperçu validé par l'utilisateur : enregistrements/vivant/jarvis-vivant-apercu.mp4.

Les sous-titres viennent de main.py (canvas._st_jarvis / _st_user, mis à jour au fil de la
transcription). La voix de Jarvis ne change pas : tout ceci n'est que du dessin.
"""
from __future__ import annotations

import math
import random
import time

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPixmap, QPolygonF, QRadialGradient)

PLUS = QPainter.CompositionMode.CompositionMode_Plus
NORMAL = QPainter.CompositionMode.CompositionMode_SourceOver
VITESSE_LECTURE = 15.0   # caractères par seconde : les sous-titres suivent à peu près la voix

random.seed(7)
PARTICULES = [(random.uniform(-260, 260), random.uniform(0, 1), random.uniform(25, 70),
               random.uniform(1.0, 2.6), random.random() < 0.3) for _ in range(90)]


def coul(r, g, b, a):
    return QColor(int(r), int(g), int(b), int(max(0, min(255, a))))


def _vers(v, cible, dt, vitesse):
    return v + (cible - v) * min(1.0, dt * vitesse)


# ── État animé (gardé sur le canevas) ───────────────────────────────────────

class Etat:
    def __init__(self):
        self.t0 = time.monotonic()
        self.dernier = self.t0
        self.eveil = 0.0          # 0 = veille, 1 = réveillé
        self.boutons = 0.0        # 0 = cachés, 1 = visibles
        self.ecoute = 0.0
        self.reflexion = 0.0
        self.parle = 0.0
        self.st_texte = ""
        self.st_vu = 0.0
        self.st_fin = 0.0
        self.glitch_prochain = self.t0 + random.uniform(20, 40)
        self.glitch_fin = 0.0


def etat(canvas) -> Etat:
    e = canvas.__dict__.get("_vivant")
    if e is None:
        e = canvas.__dict__["_vivant"] = Etat()
    return e


def maj(canvas, survol_virtuel) -> tuple[Etat, float]:
    e = etat(canvas)
    now = time.monotonic()
    dt = min(0.1, max(0.0, now - e.dernier))
    e.dernier = now
    dort = canvas.muted or canvas.state in ("SLEEPING", "INITIALISING")
    e.eveil = _vers(e.eveil, 0.0 if dort else 1.0, dt, 1.6)
    s = survol_virtuel
    proche = s is not None and (s.x() < 560 or s.y() < 200 or s.x() > 1400)   # là où sont les vitres
    e.boutons = _vers(e.boutons, 1.0 if proche else 0.0, dt, 5.0 if proche else 2.5)
    user_parle = now - getattr(canvas, "_st_user_t", 0.0) < 1.4 and not canvas.speaking
    e.ecoute = _vers(e.ecoute, 1.0 if user_parle else 0.0, dt, 6.0)
    pense = canvas.state in ("THINKING", "PROCESSING") and not canvas.speaking
    e.reflexion = _vers(e.reflexion, 1.0 if pense else 0.0, dt, 5.0)
    e.parle = _vers(e.parle, 1.0 if canvas.speaking else 0.0, dt, 6.0)
    # sous-titres de Jarvis : révélés à la vitesse de la voix, seulement pendant qu'il parle
    txt = getattr(canvas, "_st_jarvis", "") or ""
    if txt != e.st_texte:
        if not txt.startswith(e.st_texte[:20]) or not e.st_texte:
            e.st_vu = 0.0
        e.st_texte = txt
    if canvas.speaking:
        e.st_vu = min(len(txt), e.st_vu + dt * VITESSE_LECTURE)
        e.st_fin = now + 2.5
    elif now > e.st_fin:
        e.st_vu = 0.0
    if now > e.glitch_prochain:
        e.glitch_fin = now + random.uniform(0.07, 0.13)
        e.glitch_prochain = now + random.uniform(25, 50)
    return e, now - e.t0


# ── Les dessins ─────────────────────────────────────────────────────────────

def coeur(p, c, t, force, battement, vitesse):
    """Le nouveau réacteur : halo, rayons, couronne de 10 bobines, triangle et noyau qui bat."""
    r = 30.0 * (1 + 0.10 * battement)
    p.setCompositionMode(PLUS)
    p.setPen(Qt.PenStyle.NoPen)
    g = QRadialGradient(c, r * 5)
    g.setColorAt(0.0, coul(150, 225, 255, 150 * force * (0.7 + 0.5 * battement)))
    g.setColorAt(0.25, coul(40, 150, 255, 60 * force))
    g.setColorAt(1.0, coul(0, 60, 255, 0))
    p.setBrush(QBrush(g)); p.drawEllipse(c, r * 5, r * 5)
    p.save(); p.translate(c); p.rotate(t * 6)
    for i in range(12):
        p.rotate(30)
        lg = QLinearGradient(0, 0, r * 4.2, 0)
        lg.setColorAt(0.0, coul(190, 240, 255, (55 + 60 * battement) * force))
        lg.setColorAt(1.0, coul(60, 160, 255, 0))
        p.setBrush(QBrush(lg))
        large = 3.5 if i % 2 else 1.8
        p.drawPolygon(QPolygonF([QPointF(r * 0.6, -large), QPointF(r * (3.4 + (i % 3) * 0.4), 0),
                                 QPointF(r * 0.6, large)]))
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)
    pen = QPen(coul(120, 210, 255, 150 * force), 1.4, Qt.PenStyle.CustomDashLine)
    pen.setDashPattern([2, 4]); pen.setDashOffset(-t * 8 * vitesse); p.setPen(pen)
    p.drawEllipse(c, r * 2.25, r * 2.25)
    p.setPen(QPen(coul(170, 235, 255, 190 * force), 1.6))
    base = (t * 40 * vitesse) % 360
    for i in range(3):
        p.drawArc(QRectF(c.x() - r * 1.85, c.y() - r * 1.85, r * 3.7, r * 3.7),
                  int((base + i * 120) * 16), int(70 * 16))
    p.save(); p.translate(c); p.rotate(-t * 12 * vitesse)
    for i in range(10):
        p.rotate(36)
        lum = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t * 3 * vitesse + i * 0.63))
        poly = QPolygonF([QPointF(-r * 0.20, -r * 1.02), QPointF(r * 0.20, -r * 1.02),
                          QPointF(r * 0.27, -r * 1.48), QPointF(-r * 0.27, -r * 1.48)])
        p.setPen(QPen(coul(200, 245, 255, 220 * force * lum), 1.2))
        p.setBrush(QBrush(coul(60, 170, 255, 90 * force * lum)))
        p.drawPolygon(poly)
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(coul(150, 225, 255, 210 * force), 2.2)); p.drawEllipse(c, r * 1.55, r * 1.55)
    p.setPen(QPen(coul(200, 245, 255, 230 * force), 1.4)); p.drawEllipse(c, r * 0.95, r * 0.95)
    p.save(); p.translate(c); p.rotate(t * 20 * vitesse)
    p.setPen(QPen(coul(220, 250, 255, 200 * force), 1.5))
    p.drawPolygon(QPolygonF([QPointF(0, -r * 0.78), QPointF(r * 0.675, r * 0.39), QPointF(-r * 0.675, r * 0.39)]))
    p.restore()
    n = r * (0.42 + 0.16 * battement + 0.03 * math.sin(t * 2.4))
    g = QRadialGradient(c, n * 1.8)
    g.setColorAt(0.0, coul(255, 255, 255, 255 * force))
    g.setColorAt(0.45, coul(200, 245, 255, 230 * force))
    g.setColorAt(1.0, coul(60, 170, 255, 0))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(c, n * 1.8, n * 1.8)
    p.setCompositionMode(NORMAL)


def coeur_triangle(p, c, t, force, battement, vitesse):
    """Le réacteur du film (HUD Mark VI) : un triangle pointe en bas, blanc-bleu, qui pulse doucement.

    Dessiné par-dessus le triangle de l'image : halo, bords lumineux, noyau qui bat. Pas de pièces qui tournent.
    """
    r = 27.0 * (1 + 0.06 * battement)
    pulse = 0.78 + 0.22 * math.sin(t * 2.2 * vitesse) + 0.25 * battement
    p.setCompositionMode(PLUS); p.setPen(Qt.PenStyle.NoPen)
    g = QRadialGradient(c, r * 3.6)
    g.setColorAt(0.0, coul(200, 240, 255, 170 * force * pulse))
    g.setColorAt(0.3, coul(80, 170, 255, 70 * force * pulse))
    g.setColorAt(1.0, coul(20, 90, 255, 0))
    p.setBrush(QBrush(g)); p.drawEllipse(c, r * 3.6, r * 3.6)
    tri = QPolygonF([QPointF(c.x() - r, c.y() - r * 0.72), QPointF(c.x() + r, c.y() - r * 0.72),
                     QPointF(c.x(), c.y() + r * 0.95)])
    p.setBrush(QBrush(coul(215, 245, 255, 120 * force * pulse))); p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(tri)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(coul(235, 250, 255, 210 * force * pulse), 2.0)); p.drawPolygon(tri)
    p.setPen(QPen(coul(120, 200, 255, 110 * force), 1.2))
    p.drawPolygon(QPolygonF([QPointF(c.x() - r * 1.35, c.y() - r * 0.97), QPointF(c.x() + r * 1.35, c.y() - r * 0.97),
                             QPointF(c.x(), c.y() + r * 1.3)]))
    p.setCompositionMode(NORMAL)


def yeux(p, points, force):
    p.setCompositionMode(PLUS); p.setPen(Qt.PenStyle.NoPen)
    for e in points:
        g = QRadialGradient(e, 34)
        g.setColorAt(0.0, coul(240, 252, 255, 255 * force))
        g.setColorAt(0.18, coul(150, 225, 255, 200 * force))
        g.setColorAt(1.0, coul(30, 120, 255, 0))
        p.setBrush(QBrush(g)); p.drawEllipse(e, 34, 34)
        lg = QLinearGradient(e.x() - 70, 0, e.x() + 70, 0)
        for x, a in ((0.0, 0), (0.5, 160 * force), (1.0, 0)):
            lg.setColorAt(x, coul(170, 235, 255, a))
        p.setBrush(QBrush(lg)); p.drawEllipse(e, 70, 3)
    p.setCompositionMode(NORMAL)


def anneaux_sol(p, sol, t, force):
    p.setCompositionMode(PLUS); p.setBrush(Qt.BrushStyle.NoBrush)
    for i, (rx, vit, a) in enumerate(((150, 30, 170), (215, -18, 120), (290, 10, 80))):
        p.setPen(QPen(coul(90, 200, 255, a * force), 2 if i == 0 else 1.4))
        rect = QRectF(sol.x() - rx, sol.y() - rx * 0.16, rx * 2, rx * 0.32)
        nb = 6 if i == 1 else 4
        base = (t * vit) % 360
        for j in range(nb):
            p.drawArc(rect, int((base + j * 360 / nb) * 16), int(55 * 16))
    g = QRadialGradient(QPointF(0, 0), 260)
    g.setColorAt(0.0, coul(80, 190, 255, 70 * force)); g.setColorAt(1.0, coul(80, 190, 255, 0))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g))
    p.save(); p.translate(sol); p.scale(1, 0.18); p.drawEllipse(QPointF(0, 0), 260, 260); p.restore()
    p.setCompositionMode(NORMAL)


def particules(p, sol, t, force):
    p.setCompositionMode(PLUS); p.setPen(Qt.PenStyle.NoPen)
    for dx, ph, vit, taille, orr in PARTICULES:
        prog = (ph + t * vit / 900) % 1.0
        y = sol.y() - prog * 900
        x = sol.x() + dx * (1 - prog * 0.35) + 10 * math.sin(t + ph * 20)
        a = 200 * force * math.sin(prog * math.pi)
        p.setBrush(QBrush(coul(255, 200, 110, a) if orr else coul(140, 225, 255, a)))
        p.drawEllipse(QPointF(x, y), taille, taille)
    p.setCompositionMode(NORMAL)


def circuits(masque: QImage, t, force) -> QImage:
    """Lignes de lumière qui montent sur l'armure (et seulement sur l'armure)."""
    calque = QImage(masque.size(), QImage.Format.Format_ARGB32_Premultiplied)
    calque.fill(Qt.GlobalColor.transparent)
    q = QPainter(calque)
    hh = calque.height()
    for i in range(5):
        y = hh - ((t * 520 * hh / 990 + i * hh / 5) % (hh * 1.2))
        e = 20 * hh / 990
        g = QLinearGradient(0, y - e, 0, y + 4)
        g.setColorAt(0.0, coul(120, 220, 255, 0)); g.setColorAt(0.85, coul(170, 240, 255, 230 * force))
        g.setColorAt(1.0, coul(255, 255, 255, 0))
        q.fillRect(QRectF(0, y - e, calque.width(), e + 4), QBrush(g))
    q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    q.drawImage(0, 0, masque)
    q.end()
    return calque


def onde_poitrine(p, c, t, amp):
    p.setCompositionMode(PLUS); p.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(4):
        prog = (t * 0.9 + i / 4) % 1.0
        rr = 40 + prog * 420
        p.setPen(QPen(coul(150, 225, 255, (1 - prog) * 170 * (0.35 + amp)), 2.5 * (1 - prog) + 0.5))
        p.drawEllipse(c, rr, rr)
    p.setCompositionMode(NORMAL)


def anneau_ecoute(p, c, t, force):
    p.setCompositionMode(PLUS); p.setBrush(Qt.BrushStyle.NoBrush)
    amp = 0.5 + 0.5 * math.sin(t * 9)
    for i in range(3):
        rr = 70 + amp * 40 + i * 16
        p.setPen(QPen(coul(255, 200, 100, (230 - i * 60) * force), 3 - i * 0.7))
        p.drawEllipse(c, rr, rr)
    p.setCompositionMode(NORMAL)


def sous_titre(p, texte, col: QColor, qui: str):
    mots = texte.split()
    if not mots:
        return
    lignes, cur = [], ""
    for m in mots:
        if len(cur) + len(m) > 48:
            lignes.append(cur.strip()); cur = ""
        cur += m + " "
    lignes.append(cur.strip())
    lignes = lignes[-2:]
    y0 = 842
    bande = QLinearGradient(0, 0, 1920, 0)
    for x, a in ((0.22, 0), (0.38, 150), (0.67, 150), (0.83, 0)):
        bande.setColorAt(x, coul(0, 8, 20, a))
    p.fillRect(QRectF(0, y0 - 34, 1920, 52 + 44 * len(lignes)), QBrush(bande))
    p.setFont(QFont("Consolas", 15))
    p.setPen(coul(col.red(), col.green(), col.blue(), 200))
    p.drawText(QRectF(560, y0 - 30, 900, 24), Qt.AlignmentFlag.AlignHCenter, qui)
    f = QFont("Bahnschrift", 30); f.setWeight(QFont.Weight.DemiBold)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
    for i, l in enumerate(lignes):
        ch = QPainterPath(); ch.addText(QPointF(0, 0), f, l)
        br = ch.boundingRect(); ch.translate(1010 - br.width() / 2 - br.left(), y0 + 34 + i * 44)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for e, a in ((7, 40), (3, 90)):
            p.setPen(QPen(coul(col.red(), col.green(), col.blue(), a), e)); p.drawPath(ch)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(coul(245, 252, 255, 255))); p.drawPath(ch)


def texte_jarvis_visible(e: Etat) -> str:
    """Le texte déjà « prononcé », coupé au dernier mot entier."""
    n = int(e.st_vu)
    if n <= 0:
        return ""
    if n >= len(e.st_texte):
        return e.st_texte
    morceau = e.st_texte[:n]
    return morceau[:morceau.rfind(" ")] if " " in morceau else ""
