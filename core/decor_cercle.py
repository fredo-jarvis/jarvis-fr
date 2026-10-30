"""
Décor « grand cercle bleu » de l'écran Jarvis (demande de l'utilisateur, 2026-10-30, d'après une image de
bureau bleu qu'il aime : grand cercle à gauche, graphiques du PC en haut à droite, lignes de circuit
au milieu, cadrans en bas). Même disposition et même esprit, dessin fait maison.

Règles de l'utilisateur : plus de vitres 3D, tous les raccourcis sont DANS l'image (couronne du cercle,
boutons du haut, liste des sites) ; les lignes partent du cœur et réagissent à Jarvis (écoute,
réponse, réflexion) ; écritures nettes sans traits ; net en 4K (tout est vectoriel) ; rien qui
bouge le corps de l'image (nausée) : seules des petites lumières circulent dans les lignes.
Réglages dans memory/interface.json : "decor": "cercle" (défaut) ou "armure".
"""
from __future__ import annotations

import math
import platform
import random
import time
from collections import deque

import psutil
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainterPath, QPen, QPolygonF,
                         QRadialGradient)

BLEU = QColor(30, 130, 255)
CYAN = QColor(70, 210, 255)
PALE = QColor(190, 235, 255)
BLANC = QColor(245, 250, 255)
NUIT = QColor(2, 12, 40)
VW, VH = 1920.0, 1080.0
C = QPointF(491.0, 556.0)     # centre du grand cercle
R = 365.0                     # rayon extérieur
HAUT_Y, BAS_Y = 374.0, 743.0  # les deux grands faisceaux horizontaux


def _q(col: QColor, a: float) -> QColor:
    x = QColor(col); x.setAlphaF(max(0.0, min(1.0, a))); return x


SANS_TEXTE = [False]


def texte(p, x, y, w, h, txt, px, col=PALE, nom="Bahnschrift", gras=False,
          align=Qt.AlignmentFlag.AlignLeft, espace=0.0) -> None:
    """Écriture nette : une seule couche pleine, aucun halo, aucun trait."""
    if SANS_TEXTE[0]:
        return
    f = QFont(nom); f.setPixelSize(max(6, int(px))); f.setBold(gras)
    if espace:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, espace)
    p.save(); p.setFont(f); p.setPen(QPen(col, 1))
    p.drawText(QRectF(x, y, w, h), align | Qt.AlignmentFlag.AlignVCenter, txt)
    p.restore()


def _droite(p, x, y, w, h, txt, px, col=PALE, nom="Consolas", gras=False) -> None:
    texte(p, x, y, w, h, txt, px, col, nom, gras, Qt.AlignmentFlag.AlignRight)


# ── Capteurs du PC ───────────────────────────────────────────────────────────

class _Capteurs:
    def __init__(self):
        self.cpu = [deque([0.0] * 60, maxlen=60) for _ in range(4)]
        self.noyaux = [0.0] * 4
        self.coeurs: list[float] = []
        self.tot = deque([0.0] * 120, maxlen=120)
        self.mem = deque([0.0] * 120, maxlen=120)
        self.haut = deque([0.0] * 60, maxlen=60)
        self.bas = deque([0.0] * 120, maxlen=120)
        self.moy = self.ram = self.disque_c = self.disque_d = 0.0
        self.ram_go = (0.0, 0.0)
        self.freq = 0.0
        self.envoye = self.recu = 0.0
        self.t = 0.0
        self._net = None
        self.machine = platform.node().upper()
        self._temps = None             # derniers temps des cœurs (mesure faite ici, pas par psutil)
        try:
            self._temps = psutil.cpu_times(percpu=True)
            self._net = psutil.net_io_counters()
        except Exception:
            pass

    def _charge_coeurs(self) -> list[float]:
        """Charge de chaque cœur depuis la dernière mesure, calculée ici même : cpu_percent()
        partage un état global avec le reste de Jarvis et rendait 0 % (test du 30/10)."""
        nouveaux = psutil.cpu_times(percpu=True)
        anciens, self._temps = self._temps, nouveaux
        if not anciens or len(anciens) != len(nouveaux):
            return [0.0] * len(nouveaux)
        charges = []
        for a, b in zip(anciens, nouveaux):
            total = sum(b) - sum(a)
            repos = b.idle - a.idle
            charges.append(max(0.0, min(100.0, 100.0 * (1 - repos / total))) if total > 0 else 0.0)
        return charges

    def maj(self) -> None:
        now = time.monotonic()
        if now - self.t < 1.0:
            return
        dt = (now - self.t) if self.t else 1.0
        self.t = now
        try:
            v = self._charge_coeurs() or [0.0]
            n = len(v)
            self.coeurs = v
            for i in range(4):
                part = v[i * n // 4:(i + 1) * n // 4] or [0.0]
                self.noyaux[i] = sum(part) / len(part); self.cpu[i].append(self.noyaux[i])
            self.moy = sum(v) / n; self.tot.append(self.moy)
            vm = psutil.virtual_memory()
            self.ram = vm.percent; self.mem.append(vm.percent)
            self.ram_go = (vm.used / 2 ** 30, vm.total / 2 ** 30)
            f = psutil.cpu_freq()
            self.freq = (f.current / 1000) if f else 0.0
            if int(now) % 10 == 0 or not self.disque_c:
                self.disque_c = psutil.disk_usage("C:\\").percent
                try:
                    self.disque_d = psutil.disk_usage("D:\\").percent
                except Exception:
                    self.disque_d = 0.0
            net = psutil.net_io_counters()
            if self._net is not None:
                self.haut.append(max(0.0, (net.bytes_sent - self._net.bytes_sent) / dt / 1024))
                self.bas.append(max(0.0, (net.bytes_recv - self._net.bytes_recv) / dt / 1024))
            self._net = net
            self.envoye, self.recu = net.bytes_sent / 2 ** 30, net.bytes_recv / 2 ** 30
        except Exception:
            pass


CAPT = _Capteurs()


# ── Briques de dessin ────────────────────────────────────────────────────────

def _arc(p, c, r, debut, etendue, col, larg) -> None:
    p.setPen(QPen(col, larg, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), int(debut * 16), int(etendue * 16))


def _lueur_arc(p, c, r, debut, etendue, col, larg) -> None:
    _arc(p, c, r, debut, etendue, _q(col, 0.18), larg * 4)
    _arc(p, c, r, debut, etendue, _q(col, 0.95), larg)


def _sur_cercle(c, r, a_deg) -> QPointF:
    a = math.radians(a_deg)
    return QPointF(c.x() + r * math.cos(a), c.y() - r * math.sin(a))


def _boite(p, r: QRectF, fond=0.12) -> None:
    """Panneau de verre : dégradé, reflet en haut, liseré et coins lumineux."""
    g = QLinearGradient(0, r.top(), 0, r.bottom())
    g.setColorAt(0.0, _q(QColor(60, 150, 255), fond + 0.14)); g.setColorAt(0.5, _q(BLEU, fond * 0.6))
    g.setColorAt(1.0, _q(QColor(10, 60, 180), fond + 0.08))
    p.setPen(QPen(_q(CYAN, 0.55), 1.1)); p.setBrush(QBrush(g)); p.drawRect(r)
    p.fillRect(QRectF(r.left() + 1, r.top() + 1, r.width() - 2, 2), _q(PALE, 0.35))
    p.setPen(QPen(_q(BLANC, 0.95), 2))
    L = 10
    for x, y, sx, sy in ((r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
                         (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1)):
        p.drawLine(QPointF(x, y), QPointF(x + sx * L, y)); p.drawLine(QPointF(x, y), QPointF(x, y + sy * L))


def _courbe(p, r: QRectF, valeurs, maxi) -> None:
    n = len(valeurs)
    pts = [QPointF(r.left() + r.width() * i / (n - 1), r.bottom() - r.height() * min(1.0, v / maxi))
           for i, v in enumerate(valeurs)]
    zone = QPolygonF([QPointF(r.left(), r.bottom())] + pts + [QPointF(r.right(), r.bottom())])
    g = QLinearGradient(0, r.top(), 0, r.bottom())
    g.setColorAt(0.0, _q(CYAN, 0.65)); g.setColorAt(1.0, _q(BLEU, 0.10))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawPolygon(zone)
    p.setPen(QPen(_q(PALE, 0.95), 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolyline(QPolygonF(pts))


def _point_lumineux(p, q: QPointF, r: float, a: float) -> None:
    g = QRadialGradient(q, r)
    g.setColorAt(0.0, _q(BLANC, a)); g.setColorAt(0.35, _q(CYAN, 0.7 * a)); g.setColorAt(1.0, _q(CYAN, 0))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(q, r, r)


# ── Lignes de circuit (elles partent du cercle) ──────────────────────────────

class _Ligne:
    def __init__(self, pts):
        self.pts = pts
        self.cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(b.x() - a.x(), b.y() - a.y()))

    def point(self, f: float) -> QPointF:
        d = f * self.cum[-1]
        for i in range(1, len(self.pts)):
            if d <= self.cum[i]:
                a, b = self.pts[i - 1], self.pts[i]
                k = (d - self.cum[i - 1]) / max(1e-6, self.cum[i] - self.cum[i - 1])
                return QPointF(a.x() + (b.x() - a.x()) * k, a.y() + (b.y() - a.y()) * k)
        return self.pts[-1]


def _faire_lignes() -> tuple[list[_Ligne], list[QPointF]]:
    rnd = random.Random(5)
    lignes, noeuds = [], []
    for k in range(10):
        yb = C.y() + (k - 4.5) * 5.0                   # faisceau qui sort du cercle
        y = 462.0 + k * 21.0                           # couloir de chaque ligne
        x = 1240.0 + abs(k - 4.5) * 7
        pts = [QPointF(C.x() + R * 0.99, yb), QPointF(x, yb)]
        x += abs(y - yb); pts.append(QPointF(x, y))
        while x < VW - 40:
            x += rnd.uniform(60, 150); pts.append(QPointF(min(x, VW), y))
            if x < VW - 80 and rnd.random() < 0.5:
                dy = rnd.choice((-21.0, 21.0))
                if 455 <= y + dy <= 660:
                    x += 21; y += dy; pts.append(QPointF(x, y))
            if rnd.random() < 0.3:
                noeuds.append(pts[-1])
        lignes.append(_Ligne(pts))
    return lignes, noeuds


LIGNES, NOEUDS = _faire_lignes()
RAYONS = [_Ligne([_sur_cercle(C, R * 0.13, a), _sur_cercle(C, R * 0.40, a)]) for a in range(0, 360, 30)]


def _activite(e, amp) -> float:
    """0,15 au repos ; monte quand l'utilisateur parle, quand Jarvis réfléchit ou répond."""
    return max(0.15, 0.6 * e.ecoute, e.parle * (0.5 + 0.5 * min(1.0, amp * 2)), 0.8 * e.reflexion)


def _impulsions(p, lignes, t, act, nb, taille) -> None:
    vitesse = 0.05 + 0.40 * act
    for i, li in enumerate(lignes):
        for j in range(nb):
            f = (t * vitesse + i * 0.137 + j / nb) % 1.0
            _point_lumineux(p, li.point(f), taille, (0.35 + 0.65 * act) * (1 - f * 0.5))


# ── Le grand cercle ──────────────────────────────────────────────────────────

def _segment(c, r1, r2, a, ext) -> QPainterPath:
    ro = QRectF(c.x() - r2, c.y() - r2, 2 * r2, 2 * r2)
    ri = QRectF(c.x() - r1, c.y() - r1, 2 * r1, 2 * r1)
    ch = QPainterPath(); ch.arcMoveTo(ro, a); ch.arcTo(ro, a, ext); ch.arcTo(ri, a + ext, -ext)
    ch.closeSubpath(); return ch


def _raccourcis_couronne(hud) -> list[tuple[str, tuple]]:
    court = {"GESTIONNAIRE": "TÂCHES", "TÉLÉCHARGEMENTS": "TÉLÉCHARG.", "PRODUCTIONS": "PRODUC."}
    liste = [(n, a) for n, _i, a in hud.GRANDS] + [(n, a) for n, _i, a in hud.PETITS]
    liste += [(n, ("dossier", ch)) for n, ch in hud.DOSSIERS[:5]]
    return [(court.get(n, n), a) for n, a in liste]


def _grand_cercle(p, t, act, survol, zones, hud) -> None:
    c = C
    # halo
    g = QRadialGradient(c, R * 1.2)
    g.setColorAt(0.0, QColor(20, 90, 220, int(60 + 50 * act))); g.setColorAt(0.6, QColor(15, 60, 180, 30))
    g.setColorAt(1.0, QColor(10, 40, 160, 0))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(c, R * 1.2, R * 1.2)

    # grands blocs translucides tout autour
    for a, ext, al in ((95, 70, .20), (172, 26, .12), (205, 50, .22), (262, 22, .10), (292, 48, .17),
                       (350, 40, .13), (52, 30, .10)):
        _arc(p, c, R * 0.86, a, ext, _q(BLEU, al), R * 0.2)
    _arc(p, c, R * 0.98, 0, 360, _q(PALE, 0.45), 1.2)
    _arc(p, c, R * 0.755, 0, 360, _q(PALE, 0.35), 1.0)
    for a, ext in ((28, 52), (118, 40), (196, 62), (300, 34)):
        _lueur_arc(p, c, R * 1.02, a, ext, PALE, 2)

    # anneau de petits chiffres et anneau de points, tout autour
    for i in range(0, 360, 10):
        q = _sur_cercle(c, R * 1.075, i)
        p.save(); p.translate(q); p.rotate(90 - i if math.sin(math.radians(i)) >= 0 else -90 - i)
        texte(p, -16, -6, 32, 12, f"{(90 - i) % 360:03d}", 8.5, _q(PALE, 0.7), "Consolas", False,
              Qt.AlignmentFlag.AlignHCenter)
        p.restore()
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(180):
        q = _sur_cercle(c, R * 1.125, i * 2)
        p.setBrush(QBrush(_q(PALE, 0.75 if i % 15 == 0 else 0.3)))
        rr = 2.2 if i % 15 == 0 else 1.1
        p.drawEllipse(q, rr, rr)
    for a0 in (40, 130, 220, 310):
        _lueur_arc(p, c, R * 1.16, a0, 22, CYAN, 3)

    # pastilles des disques et de la mémoire
    for ang, lettre, val in ((158, "C", CAPT.disque_c), (202, "D", CAPT.disque_d),
                             (22, "M", CAPT.ram), (338, "P", CAPT.moy)):
        q = _sur_cercle(c, R * 0.875, ang)
        p.setBrush(QBrush(NUIT)); p.setPen(QPen(BLANC, 2)); p.drawEllipse(q, 19, 19)
        texte(p, q.x() - 19, q.y() - 12, 38, 24, lettre, 18, BLANC, "Bahnschrift", True, Qt.AlignmentFlag.AlignHCenter)
        texte(p, q.x() - 50, q.y() + 20, 100, 16, f"{val:.1f} %", 12, PALE, "Consolas", False,
              Qt.AlignmentFlag.AlignHCenter)

    # couronne des raccourcis (cliquables)
    rac = _raccourcis_couronne(hud)
    n = len(rac)
    r1, r2 = R * 0.585, R * 0.715
    pas = 360.0 / n
    for i, (nom, action) in enumerate(rac):
        a = 90 - (i + 1) * pas                   # en partant du haut, dans le sens des aiguilles
        ch = _segment(c, r1, r2, a + 1.0, pas - 2.0)
        dedans = survol is not None and ch.contains(survol)
        p.setPen(QPen(_q(PALE, 0.75), 1.2))
        p.setBrush(QBrush(_q(CYAN, 0.75) if dedans else _q(BLEU, 0.38 + 0.15 * act)))
        p.drawPath(ch)
        mil = a + pas / 2
        q = _sur_cercle(c, (r1 + r2) / 2, mil)
        p.save(); p.translate(q)
        p.rotate(90 - mil if math.sin(math.radians(mil)) >= 0 else -90 - mil)
        texte(p, -48, -9, 96, 18, nom, 11.5, BLANC, "Bahnschrift", True, Qt.AlignmentFlag.AlignHCenter, 0.6)
        p.restore()
        zones.append((ch, ("ouvrir", action)))

    # graduations
    for i in range(120):
        a = i * 3
        long = i % 5 == 0
        p.setPen(QPen(_q(PALE, 0.85 if long else 0.45), 1.5 if long else 1.0))
        p.drawLine(_sur_cercle(c, R * 0.55 - (10 if long else 5), a), _sur_cercle(c, R * 0.55, a))

    # bande à rayures obliques blanches et noires
    rb, lb = R * 0.475, 26.0
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(4, 10, 26))); p.drawEllipse(c, rb + lb / 2, rb + lb / 2)
    p.setBrush(QBrush(BLEU)); p.drawEllipse(c, rb - lb / 2, rb - lb / 2)
    nd = 72
    p.setBrush(QBrush(_q(QColor(150, 200, 245), 0.75)))
    for i in range(nd):
        a0 = math.radians(i * 360.0 / nd); da = math.radians(360.0 / nd * 0.5); dec = math.radians(2.2)
        ri, ro = rb - lb / 2 + 2, rb + lb / 2 - 2
        pts = [QPointF(c.x() + ri * math.cos(a0), c.y() - ri * math.sin(a0)),
               QPointF(c.x() + ri * math.cos(a0 + da), c.y() - ri * math.sin(a0 + da)),
               QPointF(c.x() + ro * math.cos(a0 + da + dec), c.y() - ro * math.sin(a0 + da + dec)),
               QPointF(c.x() + ro * math.cos(a0 + dec), c.y() - ro * math.sin(a0 + dec))]
        p.drawPolygon(QPolygonF(pts))
    _arc(p, c, rb + lb / 2 + 2, 0, 360, _q(PALE, 0.6), 1.2)
    _arc(p, c, rb - lb / 2 - 2, 0, 360, _q(PALE, 0.6), 1.2)

    # disque intérieur : bleu lumineux
    p.setPen(Qt.PenStyle.NoPen)
    g2 = QRadialGradient(c, R * 0.44)
    g2.setColorAt(0.0, QColor(60, 150, 240, int(140 + 70 * act)))
    g2.setColorAt(0.5, QColor(25, 105, 220, int(150 + 50 * act)))
    g2.setColorAt(1.0, QColor(10, 50, 170, 220))
    p.setBrush(QBrush(g2)); p.drawEllipse(c, R * 0.44, R * 0.44)

    # anneau bleu épais en blocs (les mesures du PC le remplissent)
    r_bl, ep = R * 0.385, 20.0
    for i in range(24):
        al = 0.85 if (i * 15) % 360 < 360 * CAPT.moy / 100.0 + 15 else 0.35
        _arc(p, c, r_bl, 90 - i * 15 - 1.5, -12.0, _q(QColor(70, 160, 240), al * 0.8), ep)
    # petits repères et pourcentages
    for k, ang in enumerate((45, 135, 225, 315)):
        q = _sur_cercle(c, R * 0.325, ang)
        texte(p, q.x() - 22, q.y() - 8, 44, 16, f"{(CAPT.moy, CAPT.ram, CAPT.disque_c, CAPT.disque_d)[k]:.0f}%",
              11, BLANC, "Consolas", True, Qt.AlignmentFlag.AlignHCenter)
    for i in range(48):
        q = _sur_cercle(c, R * 0.355, i * 7.5)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(_q(BLANC, 0.7 if i % 6 == 0 else 0.3)))
        p.drawEllipse(q, 1.6 if i % 6 == 0 else 1.0, 1.6 if i % 6 == 0 else 1.0)
    p.setBrush(QBrush(BLANC))
    m = _sur_cercle(c, R * 0.30, 270)
    p.drawPolygon(QPolygonF([QPointF(m.x(), m.y() - 7), QPointF(m.x() - 6, m.y() + 4), QPointF(m.x() + 6, m.y() + 4)]))

    # anneau sombre avec arcs bleus cassés
    p.setBrush(QBrush(QColor(4, 18, 56, 235))); p.drawEllipse(c, R * 0.275, R * 0.275)
    for a0, ext, rr, w, al in ((10, 110, 0.245, 10, .9), (150, 70, 0.245, 10, .6), (240, 95, 0.245, 10, .85),
                               (60, 80, 0.205, 6, .7), (190, 120, 0.205, 6, .5), (320, 30, 0.205, 6, .9)):
        _arc(p, c, R * rr, a0, ext, _q(QColor(80, 190, 255), al * (0.7 + 0.3 * act)), w)
    _lueur_arc(p, c, R * 0.17, 90, -360 * CAPT.ram / 100.0, CYAN, 3)

    # rayons du cœur : des lumières montent du cœur vers la couronne

    # cœur : petit cercle noir, anneau blanc, viseur et lumière qui bat
    rc0 = R * 0.10
    pulse = 0.6
    gc = QRadialGradient(c, rc0 * 2.2)
    gc.setColorAt(0.0, _q(BLANC, 0.6)); gc.setColorAt(0.5, _q(CYAN, 0.25 + 0.5 * act * pulse + 0.1 * pulse))
    gc.setColorAt(1.0, _q(CYAN, 0))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(gc)); p.drawEllipse(c, rc0 * 2.2, rc0 * 2.2)
    p.setBrush(QBrush(QColor(2, 6, 16))); p.setPen(QPen(BLANC, 2.4)); p.drawEllipse(c, rc0, rc0)
    _arc(p, c, rc0 * 0.72, 100, 250, _q(PALE, 0.85), 1.6)
    p.setPen(QPen(_q(BLANC, 0.9), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(c.x() - rc0 * 0.35, c.y() - rc0 * 0.25), QPointF(c.x() + rc0 * 0.15, c.y() - rc0 * 0.25))
    p.drawLine(QPointF(c.x() + rc0 * 0.15, c.y() - rc0 * 0.25), QPointF(c.x() + rc0 * 0.15, c.y() + rc0 * 0.35))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(_q(CYAN, 0.5 + 0.5 * pulse)))
    p.drawRoundedRect(QRectF(c.x() + rc0 * 1.3, c.y() - 7, 6, 14), 2, 2)


# ── Les autres morceaux de l'image ───────────────────────────────────────────

def fond(p, W: float, H: float) -> None:
    g = QRadialGradient(W * 0.3, H * 0.5, W * 0.85)
    g.setColorAt(0.0, QColor(4, 30, 88)); g.setColorAt(0.5, QColor(2, 15, 52)); g.setColorAt(1.0, QColor(1, 5, 20))
    p.fillRect(QRectF(0, 0, W, H), QBrush(g))


def _decor_fond(p) -> None:
    # bande centrale plus claire avec des chiffres binaires très pâles
    g = QLinearGradient(0, HAUT_Y, 0, BAS_Y)
    g.setColorAt(0.0, QColor(8, 45, 130, 50)); g.setColorAt(0.5, QColor(12, 60, 160, 60)); g.setColorAt(1.0, QColor(8, 45, 130, 50))
    p.fillRect(QRectF(C.x(), HAUT_Y, VW - C.x(), BAS_Y - HAUT_Y), QBrush(g))
    rnd = random.Random(3)
    f = QFont("Consolas"); f.setPixelSize(22); p.setFont(f); p.setPen(QPen(_q(BLEU, 0.12), 1))
    for y in range(int(HAUT_Y) + 110, int(BAS_Y) - 20, 30):
        p.drawText(QPointF(1300, y), "".join(rnd.choice("01") for _ in range(46)))
    # rayons de lumière derrière le cercle (en haut à gauche)
    for k, (a1, a2, al) in enumerate(((100, 112, .07), (118, 126, .05), (131, 146, .08), (150, 156, .04))):
        poly = QPolygonF([C, _sur_cercle(C, 1400, a1), _sur_cercle(C, 1400, a2)])
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(_q(BLEU, al * 0.6))); p.drawPolygon(poly)
    # deux grands faisceaux horizontaux
    for y in (HAUT_Y, BAS_Y):
        p.fillRect(QRectF(0, y - 4, VW, 8), _q(BLEU, 0.08))
        p.fillRect(QRectF(0, y - 1, VW, 2.0), _q(QColor(90, 170, 240), 0.6))


def _globe(p, c: QPointF, r: float) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(_q(PALE, 0.55), 1))
    p.drawEllipse(c, r, r)
    for k in range(1, 6):
        rx = r * math.cos(math.radians(k * 15))
        p.drawEllipse(c, rx, r)
    for k in range(-5, 6):
        y = c.y() + r * k / 6
        w = math.sqrt(max(0.0, r * r - (y - c.y()) ** 2))
        p.drawLine(QPointF(c.x() - w, y), QPointF(c.x() + w, y))


def _barre_haut(p, canvas, survol, zones, hud, etat: str) -> None:
    x = 8.0
    for txt, vk in (("⏮ PRÉC.", 0xB1), ("⏯ LECTURE", 0xB3), ("⏭ SUIV.", 0xB0), ("VOL −", 0xAE), ("VOL +", 0xAF)):
        w = 92.0 if "VOL" not in txt else 70.0
        r = QRectF(x, 8, w, 24)
        dedans = survol is not None and r.contains(survol)
        poly = QPolygonF([QPointF(r.left() + 8, r.top()), QPointF(r.right(), r.top()),
                          QPointF(r.right() - 8, r.bottom()), QPointF(r.left(), r.bottom())])
        p.setPen(QPen(_q(PALE, 0.6), 1)); p.setBrush(QBrush(_q(CYAN, 0.55) if dedans else QColor(10, 24, 50, 220)))
        p.drawPolygon(poly)
        texte(p, r.left(), r.top(), r.width(), r.height(), txt, 12, BLANC, "Segoe UI Symbol", False,
              Qt.AlignmentFlag.AlignHCenter)
        zones.append((r, ("touche", vk)))
        x += w + 4
    # champ d'état (comme une barre d'adresse)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(4, 20, 56, 220))); p.drawRect(QRectF(8, 38, 430, 26))
    texte(p, 16, 38, 420, 26, etat, 14, PALE, "Bahnschrift")
    # dossiers restants
    x = 8.0
    for nom, ch in hud.DOSSIERS[5:]:
        f = QFont("Bahnschrift"); f.setPixelSize(12); f.setBold(True)
        from PyQt6.QtGui import QFontMetricsF
        w = QFontMetricsF(f).horizontalAdvance(nom) + 20
        r = QRectF(x, 70, w, 22)
        dedans = survol is not None and r.contains(survol)
        p.setPen(QPen(_q(PALE, 0.5), 1)); p.setBrush(QBrush(_q(CYAN, 0.55) if dedans else _q(BLEU, 0.18)))
        p.drawRect(r)
        texte(p, r.left(), r.top(), r.width(), r.height(), nom, 12, BLANC, "Bahnschrift", True, Qt.AlignmentFlag.AlignHCenter)
        zones.append((r, ("ouvrir", ("dossier", ch))))
        x += w + 5


def _cartes_cpu(p) -> None:
    for i in range(4):
        x0, y0 = 1000.0 + (i % 2) * 400, 27.0 + (i // 2) * 100
        rg = QRectF(x0, y0, 250, 58)
        _boite(p, rg, 0.08)
        _courbe(p, rg.adjusted(4, 6, -4, -2), CAPT.cpu[i], 100.0)
        texte(p, x0, y0 + 61, 250, 16, f"[ PROCESSEUR {i + 1} ]", 11, PALE, "Consolas")
        rs = QRectF(x0 + 262, y0, 112, 58)
        _boite(p, rs)
        texte(p, rs.left() + 8, y0 + 2, 100, 16, "CHARGE", 11, PALE, "Consolas")
        texte(p, rs.left() + 8, y0 + 18, 100, 24, f"{CAPT.noyaux[i]:03.0f} %", 20, BLANC, "Bahnschrift Light Condensed")
        texte(p, rs.left() + 8, y0 + 40, 100, 16, f"{CAPT.freq:.2f} GHz", 11, PALE, "Consolas")


def _date(p) -> None:
    t = time.localtime()
    texte(p, 1800, 14, 108, 72, f"{t.tm_mday:02d}", 72, BLANC, "Bahnschrift Light Condensed", False,
          Qt.AlignmentFlag.AlignRight)
    p.fillRect(QRectF(1800, 90, 108, 22), _q(BLEU, 0.9))
    _droite(p, 1800, 90, 104, 22, ("JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET", "AOÛT",
                                   "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE")[t.tm_mon - 1], 14, BLANC, "Bahnschrift", True)
    _droite(p, 1800, 114, 104, 18, ("LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE")[t.tm_wday],
            13, PALE)


def _panneaux_milieu(p, survol, zones, hud) -> None:
    # météo
    r = QRectF(1417, 257, 230, 84)
    dedans = survol is not None and r.contains(survol)
    _boite(p, r, 0.30 if dedans else 0.12)
    texte(p, r.left() + 10, r.top() + 4, 200, 18, f"MÉTÉO · {hud.LIEU['ville'].upper()}", 12, PALE, "Bahnschrift", True, espace=0.8)
    m, temp, mot = hud.DONNEES.meteo, "--", "…"
    if m:
        try:
            temp = f"{round(m['current']['temperature_2m'])}°"; mot = hud._meteo_mot(int(m['current']['weather_code']))
        except Exception:
            pass
    texte(p, r.left() + 10, r.top() + 24, 100, 54, temp, 42, BLANC, "Bahnschrift Light Condensed")
    texte(p, r.left() + 100, r.top() + 34, 125, 36, mot, 14, PALE, "Bahnschrift", True)
    zones.append((r, ("ouvrir", ("url", "https://www.google.com/search?q=m%C3%A9t%C3%A9o+" + hud.LIEU["ville"]))))
    # corbeille
    taille, n = hud.DONNEES.corbeille
    r = QRectF(1662, 257, 240, 84)
    dedans = survol is not None and r.contains(survol)
    _boite(p, r, 0.30 if dedans else 0.12)
    texte(p, r.left() + 10, r.top() + 4, 200, 18, "CORBEILLE", 12, PALE, "Bahnschrift", True, espace=0.8)
    texte(p, r.left() + 10, r.top() + 26, 220, 24, f"{taille:.1f} Mo", 22, BLANC, "Bahnschrift Light Condensed")
    texte(p, r.left() + 10, r.top() + 54, 220, 20, f"{n} éléments", 13, PALE, "Consolas")
    zones.append((r, ("ouvrir", ("shell", "shell:RecycleBinFolder"))))


def _reseau(p) -> None:
    for y, titre, hist, total in ((395.0, "RÉSEAU · ENVOI", CAPT.haut, CAPT.envoye),
                                  (673.0, "RÉSEAU · RÉCEPTION", list(CAPT.bas)[-60:], CAPT.recu)):
        rg = QRectF(860, y, 400, 56)
        _boite(p, rg, 0.10)
        _courbe(p, rg.adjusted(4, 18, -4, -2), hist, max(200.0, max(hist)))
        texte(p, rg.left() + 8, y + 1, 300, 16, titre, 11, PALE, "Consolas", True)
        rs = QRectF(1270, y, 108, 56)
        _boite(p, rs)
        texte(p, rs.left() + 8, y + 2, 100, 16, "TOTAL", 11, PALE, "Consolas")
        texte(p, rs.left() + 8, y + 18, 96, 20, f"{hist[-1]:.0f} Ko/s", 14, BLANC, "Bahnschrift", True)
        texte(p, rs.left() + 8, y + 37, 96, 16, f"{total:.2f} Go", 11, PALE, "Consolas")


def _circuits(p, t, act) -> None:
    for li in LIGNES:
        p.setPen(QPen(_q(PALE, 0.18), 5)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPolyline(QPolygonF(li.pts))
        p.setPen(QPen(_q(PALE, 0.8), 1.4)); p.drawPolyline(QPolygonF(li.pts))
    for k, q in enumerate(NOEUDS):
        _point_lumineux(p, q, 10, 0.5 + 0.4 * act)


def _bas(p, survol, zones, hud) -> None:
    # deux longs graphiques en bas à gauche
    for y, titre, hist, mx, txt in ((951.0, "PROCESSEUR · 2 MIN", CAPT.tot, 100.0, f"{CAPT.moy:.0f} %"),
                                    (1013.0, "MÉMOIRE · 2 MIN", CAPT.mem, 100.0, f"{CAPT.ram:.0f} %")):
        rg = QRectF(-2, y, 620, 54)
        _boite(p, rg, 0.08)
        _courbe(p, rg.adjusted(4, 16, -4, -2), hist, mx)
        texte(p, 8, y + 1, 300, 15, titre, 11, PALE, "Consolas", True)
        rs = QRectF(628, y, 100, 54)
        _boite(p, rs)
        texte(p, rs.left(), y + 8, 100, 38, txt, 24, BLANC, "Bahnschrift Light Condensed", False, Qt.AlignmentFlag.AlignHCenter)
    # petites boîtes d'infos au milieu
    up = int(time.time() - hud.DONNEES.demarrage)
    infos = (("PROCESSEUR", f"{CAPT.moy:.0f} %", f"{CAPT.freq:.2f} GHz"),
             ("MÉMOIRE", f"{CAPT.ram_go[0]:.1f} Go", f"sur {CAPT.ram_go[1]:.0f} Go"),
             ("DISQUES", f"C {CAPT.disque_c:.0f} %", f"D {CAPT.disque_d:.0f} %"),
             ("EN MARCHE", f"{up // 3600} h {up % 3600 // 60:02d}", f"{up // 86400} jour(s)"))
    for i, (titre, v1, v2) in enumerate(infos):
        r = QRectF(790 + (i % 2) * 140, 884 + (i // 2) * 76, 132, 68)
        _boite(p, r)
        texte(p, r.left() + 8, r.top() + 2, 120, 16, titre, 11, PALE, "Consolas", True)
        texte(p, r.left() + 8, r.top() + 19, 120, 26, v1, 20, BLANC, "Bahnschrift Light Condensed")
        texte(p, r.left() + 8, r.top() + 46, 120, 16, v2, 11, PALE, "Consolas")
    # barres des cœurs du processeur
    r = QRectF(1075, 884, 145, 144)
    _boite(p, r, 0.08)
    texte(p, r.left() + 8, r.top() + 2, 130, 16, "CŒURS", 11, PALE, "Consolas", True)
    v = CAPT.coeurs or [0.0]
    bw = (r.width() - 16) / len(v)
    for k, x in enumerate(v):
        h = (r.height() - 30) * min(1.0, x / 100.0)
        p.fillRect(QRectF(r.left() + 8 + k * bw + 1, r.bottom() - 6 - h, max(1.0, bw - 2), h), _q(CYAN, 0.85))
    # cadrans : l'heure et la mémoire
    for cx, titre, val, txt in ((1395.0, "HEURE", (time.localtime().tm_min / 60.0) * 100, time.strftime("%H:%M")),
                                (1590.0, "MÉMOIRE", CAPT.ram, f"{CAPT.ram:.0f} %")):
        c = QPointF(cx, 880)
        if titre == "HEURE":
            g = QRadialGradient(c, 80); g.setColorAt(0.0, _q(CYAN, 0.75)); g.setColorAt(1.0, _q(CYAN, 0.08))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(c, 72, 72)
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(_q(PALE, 0.6), 1.4)); p.drawEllipse(c, 82, 82)
        _arc(p, c, 76, 0, 360, _q(BLEU, 0.35), 7)
        _lueur_arc(p, c, 76, 90, -360 * min(1.0, val / 100.0), PALE, 5)
        texte(p, c.x() - 80, c.y() - 26, 160, 40, txt, 32, BLANC, "Bahnschrift Light Condensed", False, Qt.AlignmentFlag.AlignHCenter)
        texte(p, c.x() - 80, c.y() + 14, 160, 18, titre, 12, PALE, "Bahnschrift", True, Qt.AlignmentFlag.AlignHCenter, 1.2)
    # liste des sites (à droite)
    for i, (nom, url) in enumerate(hud.SITES):
        r = QRectF(1730, 770 + i * 20, 175, 19)
        dedans = survol is not None and r.contains(survol)
        _droite(p, r.left(), r.top(), r.width(), r.height(), nom, 13, CYAN if dedans else BLANC, "Bahnschrift", True)
        zones.append((r, ("ouvrir", ("url", url))))
    # grande horloge
    texte(p, 1690, 932, 180, 64, time.strftime("%H:%M"), 56, BLANC, "Bahnschrift Light Condensed", False,
          Qt.AlignmentFlag.AlignRight)
    texte(p, 1872, 950, 40, 30, time.strftime("%S"), 18, PALE, "Consolas")
    # barre d'infos tout en bas
    r = QRectF(1240, 1012, 672, 58)
    _boite(p, r, 0.18)
    texte(p, r.left() + 10, r.top() + 6, 660, 20,
          f"PC : {CAPT.machine}    SYSTÈME : WINDOWS 11    ÉTAT : CONNECTÉ    JARVIS : MARK LV", 12, PALE, "Consolas")
    texte(p, r.left() + 10, r.top() + 30, 660, 20,
          f"ENVOYÉ : {CAPT.envoye:.2f} Go    REÇU : {CAPT.recu:.2f} Go    HEURE DE PARIS", 12, PALE, "Consolas")


def dessiner(p, e, amp: float, t: float, survol, zones: list, hud, etat: str) -> None:
    """Le décor fixe (refait une fois par seconde), dans le repère virtuel 1920 x 1080."""
    CAPT.maj()
    act = _activite(e, amp)
    _decor_fond(p)
    _globe(p, QPointF(52, 214), 96)
    _circuits(p, t, act)
    _grand_cercle(p, t, act, None, zones, hud)
    _barre_haut(p, None, None, zones, hud, etat)
    _cartes_cpu(p)
    _date(p)
    _panneaux_milieu(p, None, zones, hud)
    _reseau(p)
    _bas(p, None, zones, hud)


def _eclat(p, q: QPointF, taille: float, a: float) -> None:
    """Éclat de lumière : point blanc, halo bleu et longue traînée horizontale."""
    _point_lumineux(p, q, taille, a)
    g = QLinearGradient(q.x() - taille * 7, 0, q.x() + taille * 7, 0)
    g.setColorAt(0.0, _q(CYAN, 0)); g.setColorAt(0.5, _q(BLANC, 0.75 * a)); g.setColorAt(1.0, _q(CYAN, 0))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g))
    p.drawRect(QRectF(q.x() - taille * 7, q.y() - 1.2, taille * 14, 2.4))


_SPRITE: list = []


def _sprite(p, q: QPointF, r: float, a: float) -> None:
    """Point lumineux tout prêt (beaucoup plus rapide qu'un dégradé refait à chaque fois)."""
    if not _SPRITE:
        from PyQt6.QtGui import QImage, QPainter
        im = QImage(96, 96, QImage.Format.Format_ARGB32_Premultiplied); im.fill(Qt.GlobalColor.transparent)
        b = QPainter(im); b.setRenderHint(QPainter.RenderHint.Antialiasing)
        _point_lumineux(b, QPointF(48, 48), 48, 1.0); b.end()
        _SPRITE.append(im)
    if a <= 0.01:
        return
    p.setOpacity(min(1.0, a))
    p.drawImage(QRectF(q.x() - r, q.y() - r, 2 * r, 2 * r), _SPRITE[0])


def vivant(p, e, amp: float, t: float, survol, zones: list) -> None:
    """Ce qui vit à chaque image : comètes dans les circuits, cœur, ondes, éclats, survol."""
    act = _activite(e, amp)
    # survol : la zone sous la souris s'allume
    if survol is not None:
        for forme, _v in zones:
            if forme.contains(survol):
                ch = forme if isinstance(forme, QPainterPath) else None
                p.setPen(QPen(_q(BLANC, 0.9), 1.6)); p.setBrush(QBrush(_q(CYAN, 0.38)))
                p.drawPath(ch) if ch is not None else p.drawRect(forme)
                break
    p.setCompositionMode(p.CompositionMode.CompositionMode_Plus)
    # comètes : une tête brillante et une traînée qui s'efface
    vitesse = 0.05 + 0.40 * act
    for lignes, nb, taille in ((LIGNES, 2, 10.0), (RAYONS, 1, 7.0)):
        for i, li in enumerate(lignes):
            for j in range(nb):
                f = (t * vitesse + i * 0.137 + j / nb) % 1.0
                fort = (0.25 + 0.45 * act) * (1 - f * 0.4)
                for k in range(5):
                    ff = f - k * 0.006 * (lignes is LIGNES and 1 or 3)
                    if ff < 0:
                        break
                    _sprite(p, li.point(ff), taille * (1 - k * 0.14), fort * (1 - k / 5) ** 1.5)
    # nœuds qui scintillent
    for k, q in enumerate(NOEUDS):
        _sprite(p, q, 7, 0.15 + 0.25 * act * (0.5 + 0.5 * math.sin(t * 1.7 + k * 1.3)))
    # cœur qui bat
    pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi * (0.5 + 1.4 * act))
    rc = R * 0.10
    g = QRadialGradient(C, rc * 3.2)
    g.setColorAt(0.0, _q(CYAN, 0.15 + 0.25 * pulse * (0.4 + act))); g.setColorAt(0.4, _q(CYAN, 0.2 + 0.3 * act * pulse))
    g.setColorAt(1.0, _q(CYAN, 0))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(C, rc * 3.2, rc * 3.2)
    # ondes qui sortent du cœur quand Jarvis écoute ou parle
    if act > 0.2:
        for k in range(3):
            f = (t * 0.45 + k / 3) % 1.0
            r = rc + f * R * 0.42
            _arc(p, C, r, 0, 360, _q(CYAN, (1 - f) * 0.55 * act), 3)
    p.setOpacity(1.0)
    # éclats où les faisceaux croisent le cercle
    for k, (x, y) in enumerate(((C.x() - 334, HAUT_Y), (C.x() + 334, HAUT_Y), (C.x() + 315, BAS_Y), (C.x() + R * 0.99, C.y()))):
        _eclat(p, QPointF(x, y), 7, 0.3 + 0.12 * math.sin(t * 0.9 + k * 2.1) + 0.15 * act)
    p.setCompositionMode(p.CompositionMode.CompositionMode_SourceOver)
