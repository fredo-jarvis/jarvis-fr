r"""
Pose la fenêtre de la galaxie sur le bon écran (ajouté le 04/11/2026).

Pourquoi : un écran de gauche peut ne pas avoir la même échelle que l'autre. Les coordonnées de Qt et de Chrome
ne correspondent donc pas, et --window-position envoie la fenêtre ailleurs. On demande à Windows
le rectangle exact de l'écran voulu, par son nom, et on y pose la vraie fenêtre.
"""
import ctypes
import time
from ctypes import wintypes

TITRES = ("J.A.R.V.I.S", "localhost:4719", "Galaxie")
SW_RESTORE, SW_MAXIMIZE = 9, 3
SWP_NOZORDER, SWP_SHOWWINDOW = 0x0004, 0x0040


def choisir_moniteur(moniteurs: list[dict], coin: tuple[int, int] | None) -> dict | None:
    """Le moniteur dont le coin haut-gauche est celui-là, sinon le principal, sinon le premier.
    Qt et Windows ne donnent pas le même nom d'écran (« Nom du moniteur » contre « DISPLAY2 ») : on compare le coin."""
    for m in moniteurs:
        if coin and (m["mx"], m["my"]) == tuple(coin):
            return m
    return next((m for m in moniteurs if m["principal"]), moniteurs[0] if moniteurs else None)


def titre_convient(titre: str) -> bool:
    return any(t in titre for t in TITRES)


class _MONITORINFOEX(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]


def lister_moniteurs() -> list[dict]:
    user32 = ctypes.windll.user32
    resultat = []
    rappel = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def chaque(h, _dc, _r, _l):
        info = _MONITORINFOEX()
        info.cbSize = ctypes.sizeof(_MONITORINFOEX)
        user32.GetMonitorInfoW(h, ctypes.byref(info))
        z, e = info.rcWork, info.rcMonitor
        resultat.append({"nom": info.szDevice, "principal": bool(info.dwFlags & 1), "mx": e.left, "my": e.top,
                         "x": z.left, "y": z.top, "l": z.right - z.left, "h": z.bottom - z.top})
        return True
    user32.EnumDisplayMonitors(None, None, rappel(chaque), 0)
    return resultat


def trouver_fenetre():
    user32 = ctypes.windll.user32
    trouvee = []
    rappel = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def chaque(h, _l):
        if not user32.IsWindowVisible(h):
            return True
        classe, titre = ctypes.create_unicode_buffer(64), ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, classe, 64)
        user32.GetWindowTextW(h, titre, 256)
        if classe.value.startswith("Chrome_WidgetWin") and titre_convient(titre.value):
            trouvee.append(h)
            return False
        return True
    user32.EnumWindows(rappel(chaque), 0)
    return trouvee[0] if trouvee else None


def poser(coin: tuple[int, int] | None, delai_s: float = 15.0) -> dict | None:
    """Attend la fenêtre, la pose et l'agrandit sur l'écran voulu. Rend l'écran utilisé, ou None si pas de fenêtre."""
    user32 = ctypes.windll.user32
    fin = time.time() + delai_s
    while time.time() < fin:
        h = trouver_fenetre()
        if h:
            cible = choisir_moniteur(lister_moniteurs(), coin)
            if cible is None:
                return None
            user32.ShowWindow(h, SW_RESTORE)
            user32.SetWindowPos(h, None, cible["x"] + 40, cible["y"] + 40, 900, 600, SWP_NOZORDER | SWP_SHOWWINDOW)
            user32.ShowWindow(h, SW_MAXIMIZE)
            user32.SetForegroundWindow(h)
            return cible
        time.sleep(0.25)
    return None


class Fenetre:
    """La fenêtre posée, suivie par Windows : Chrome garde son propre programme, on ne suit donc que la fenêtre."""
    WM_CLOSE = 0x0010

    def __init__(self, h):
        self.h = h
        self.u = ctypes.windll.user32

    def ouverte(self) -> bool:
        return bool(self.u.IsWindow(self.h))

    def attendre(self) -> None:
        while self.ouverte():
            time.sleep(1)

    def fermer(self) -> None:
        if self.ouverte():
            self.u.PostMessageW(self.h, self.WM_CLOSE, 0, 0)


def fermer_fenetre_jarvis() -> None:
    """Ferme la fenêtre de la galaxie, si elle est là. Ne lève jamais d'erreur : on est en train de s'éteindre."""
    try:
        h = trouver_fenetre()
        if h:
            Fenetre(h).fermer()
    except Exception:
        pass


def titre_de_connexion(titre: str) -> bool:
    return any(m in titre for m in ("Connexion", "Sign in", "comptes Google", "Google Accounts"))


def amener_devant(titre_voulu=titre_de_connexion, delai_s: float = 8.0) -> bool:
    """Passe devant la galaxie la fenêtre de navigateur qui vient de s'ouvrir (la connexion Google restait cachée, 04/11)."""
    user32 = ctypes.windll.user32
    rappel = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    fin = time.time() + delai_s
    while time.time() < fin:
        trouvees = []

        def chaque(h, _l):
            titre = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, titre, 256)
            if user32.IsWindowVisible(h) and titre_voulu(titre.value) and not titre_convient(titre.value):
                trouvees.append(h)
                return False
            return True
        user32.EnumWindows(rappel(chaque), 0)
        if trouvees:
            h = trouvees[0]
            user32.ShowWindow(h, SW_RESTORE)
            # Passer un instant « toujours devant » : Windows refuse souvent le simple passage au premier plan.
            user32.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
            user32.SetWindowPos(h, -2, 0, 0, 0, 0, 0x0001 | 0x0002)
            user32.SetForegroundWindow(h)
            return True
        time.sleep(0.3)
    return False
