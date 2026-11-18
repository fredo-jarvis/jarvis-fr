import json
import sys
import time

import pytest

from core import coffre

linux = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux seulement")


class Verrouille(Exception):
    pass


Verrouille.__name__ = "KeyringLocked"


class Faux:
    def __init__(self, donnees=None, mode="ok"):
        self.d = dict(donnees or {})
        self.mode = mode
        self.ecritures = 0

    def get_password(self, s, n):
        if self.mode == "verrouille":
            raise Verrouille()
        if self.mode == "lent":
            time.sleep(2)
        return self.d.get((s, n))

    def set_password(self, s, n, v):
        if self.mode == "verrouille":
            raise Verrouille()
        self.ecritures += 1
        if self.mode != "perd":
            self.d[(s, n)] = v


@pytest.fixture
def faux(monkeypatch):
    f = Faux()
    monkeypatch.setattr(coffre, "_backend", lambda: f)
    return f


@linux
def test_stockage_lecture_et_reference(faux):
    ref = coffre.chiffrer("s3cret", "gmail_mot_de_passe_app")
    assert ref == "keyring:jarvis-fr/gmail_mot_de_passe_app"
    assert faux.d[("jarvis-fr", "gmail_mot_de_passe_app")] == "s3cret"
    assert coffre.dechiffrer(ref) == "s3cret"


@linux
def test_idempotent_meme_valeur_pas_de_reecriture(faux):
    coffre.chiffrer("a"); coffre.chiffrer("a")
    assert faux.ecritures == 1


@linux
def test_conflit_jamais_d_ecrasement(faux):
    coffre.chiffrer("ancien")
    assert coffre.proteger("autre") == (None, "conflit")
    assert coffre.chiffrer("autre") is None
    assert faux.d[("jarvis-fr", coffre.NOM_DEFAUT)] == "ancien"


@linux
def test_trousseau_verrouille(monkeypatch):
    f = Faux(mode="verrouille")
    monkeypatch.setattr(coffre, "_backend", lambda: f)
    assert coffre.proteger("x") == (None, "verrouille")
    assert coffre.dechiffrer("keyring:jarvis-fr/gmail_mot_de_passe_app") is None


@linux
def test_attente_bornee(monkeypatch):
    monkeypatch.setattr(coffre, "_backend", lambda: Faux(mode="lent"))
    monkeypatch.setattr(coffre, "DELAI_S", 0.2)
    t = time.time()
    assert coffre.proteger("x") == (None, "verrouille")
    assert time.time() - t < 1.5


@linux
def test_trousseau_absent(monkeypatch):
    def pas_de_trousseau():
        raise coffre.CoffreErreur("indisponible")
    monkeypatch.setattr(coffre, "_backend", pas_de_trousseau)
    assert coffre.proteger("x") == (None, "indisponible")
    assert coffre.chiffrer("x") is None


@linux
def test_relecture_differente_refusee(monkeypatch):
    monkeypatch.setattr(coffre, "_backend", lambda: Faux(mode="perd"))
    assert coffre.proteger("x") == (None, "indisponible")


@linux
@pytest.mark.parametrize("ref", ["keyring:jarvis-fr/", "keyring:jarvis-fr/../x", "keyring:autre/x", "dpapi:AAAA", "en clair", ""])
def test_references_invalides_ou_dpapi_illisibles_sous_linux(faux, ref):
    assert coffre.dechiffrer(ref) is None


@linux
def test_nom_invalide(faux):
    assert coffre.proteger("x", "../etc") == (None, "invalide")


def _cfg(tmp_path, contenu):
    p = tmp_path / "api_keys.json"
    p.write_text(json.dumps(contenu), encoding="utf-8")
    return p


@linux
def test_migration_gmail_ok_puis_idempotente(faux, tmp_path, monkeypatch):
    from plugins import gmail_lire
    p = _cfg(tmp_path, {"gemini_api_key": "K", "gmail_mot_de_passe_app": "mdp"})
    monkeypatch.setattr(gmail_lire, "CONFIG", p)
    cfg = json.loads(p.read_text())
    assert gmail_lire._mot_de_passe(cfg) == "mdp"
    fin = json.loads(p.read_text())
    assert "gmail_mot_de_passe_app" not in fin and fin["gemini_api_key"] == "K"
    assert fin["gmail_mot_de_passe_app_chiffre"].startswith("keyring:jarvis-fr/")
    assert "mdp" not in p.read_text()
    assert oct(p.stat().st_mode & 0o777) == "0o600"
    assert gmail_lire._mot_de_passe(fin) == "mdp"
    assert faux.ecritures == 1


@linux
@pytest.mark.parametrize("mode", ["verrouille", "absent"])
def test_migration_trousseau_indisponible_garde_le_clair(tmp_path, monkeypatch, mode):
    from plugins import gmail_lire
    if mode == "verrouille":
        monkeypatch.setattr(coffre, "_backend", lambda: Faux(mode="verrouille"))
    else:
        def non():
            raise coffre.CoffreErreur("indisponible")
        monkeypatch.setattr(coffre, "_backend", non)
    p = _cfg(tmp_path, {"gmail_mot_de_passe_app": "mdp"})
    avant = p.read_text()
    monkeypatch.setattr(gmail_lire, "CONFIG", p)
    assert gmail_lire._mot_de_passe(json.loads(avant)) == "mdp"
    assert p.read_text() == avant


@linux
def test_migration_ecriture_interrompue_conserve_l_original(faux, tmp_path, monkeypatch):
    from plugins import gmail_lire
    p = _cfg(tmp_path, {"gmail_mot_de_passe_app": "mdp"})
    avant = p.read_text()
    monkeypatch.setattr(gmail_lire, "CONFIG", p)
    monkeypatch.setattr(coffre.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("coupure")))
    assert gmail_lire._mot_de_passe(json.loads(avant)) == "mdp"
    assert p.read_text() == avant
    assert [f.name for f in tmp_path.iterdir()] == ["api_keys.json"]     # pas de .tmp orphelin
    monkeypatch.undo()
    monkeypatch.setattr(coffre, "_backend", lambda: faux)
    monkeypatch.setattr(gmail_lire, "CONFIG", p)
    assert gmail_lire._mot_de_passe(json.loads(avant)) == "mdp"          # reprise : même valeur, pas de conflit
    assert "keyring:" in p.read_text()


@linux
def test_migration_conflit_garde_le_clair(faux, tmp_path, monkeypatch):
    from plugins import gmail_lire
    faux.d[("jarvis-fr", coffre.NOM_DEFAUT)] = "autre"
    p = _cfg(tmp_path, {"gmail_mot_de_passe_app": "mdp"})
    avant = p.read_text()
    monkeypatch.setattr(gmail_lire, "CONFIG", p)
    assert gmail_lire._mot_de_passe(json.loads(avant)) == "mdp"
    assert p.read_text() == avant and faux.d[("jarvis-fr", coffre.NOM_DEFAUT)] == "autre"


@linux
def test_reference_existante_trousseau_ferme_pas_de_remplacement(monkeypatch, tmp_path):
    from plugins import gmail_lire
    monkeypatch.setattr(coffre, "_backend", lambda: Faux(mode="verrouille"))
    ref = "keyring:jarvis-fr/gmail_mot_de_passe_app"
    p = _cfg(tmp_path, {"gmail_mot_de_passe_app_chiffre": ref})
    avant = p.read_text()
    monkeypatch.setattr(gmail_lire, "CONFIG", p)
    assert gmail_lire._mot_de_passe(json.loads(avant)) is None
    assert p.read_text() == avant


def test_dpapi_windows_inchange(monkeypatch):
    # Sous Windows : mêmes préfixes, mêmes appels, jamais le trousseau.
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(coffre, "_backend", lambda: pytest.fail("trousseau appelé sous Windows"))
    assert coffre.disponible() is True and coffre.PREFIXE == "dpapi:"
    assert coffre.dechiffrer("keyring:jarvis-fr/x") is None            # pas de lecture trousseau
    assert coffre.dechiffrer("pas dpapi") is None
    monkeypatch.setattr(coffre, "chiffrer", lambda t, n="x": "dpapi:ZZ")
    assert coffre.proteger("t") == ("dpapi:ZZ", "disponible")


def test_hors_linux_hors_windows_pas_de_trousseau(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert coffre.chiffrer("x") is None
    assert coffre.dechiffrer("keyring:jarvis-fr/gmail_mot_de_passe_app") is None


# ── disponible() / etat() ───────────────────────────────────────────────────

def _linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")


def test_disponible_windows_sans_toucher_au_trousseau(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(coffre, "_backend", lambda: pytest.fail("trousseau sondé sous Windows"))
    assert coffre.etat() == "disponible" and coffre.disponible() is True and coffre._dpapi() is True


def test_disponible_linux_trousseau_ok_sans_rien_ecrire(monkeypatch, faux):
    _linux(monkeypatch)
    assert coffre.etat() == "disponible" and coffre.disponible() is True
    assert faux.ecritures == 0 and faux.d == {}            # la sonde ne crée rien
    assert coffre._dpapi() is False                        # Linux ne passe jamais par DPAPI


def test_disponible_linux_trousseau_absent(monkeypatch):
    _linux(monkeypatch)

    def absent():
        raise coffre.CoffreErreur("indisponible", "aucun trousseau")
    monkeypatch.setattr(coffre, "_backend", absent)
    assert coffre.etat() == "indisponible" and coffre.disponible() is False


def test_disponible_linux_trousseau_verrouille(monkeypatch, faux):
    _linux(monkeypatch)
    faux.mode = "verrouille"
    assert coffre.etat() == "verrouille" and coffre.disponible() is False


def test_disponible_linux_sans_reponse_borne_par_le_delai(monkeypatch, faux):
    _linux(monkeypatch)
    faux.mode = "lent"
    monkeypatch.setattr(coffre, "DELAI_S", 0.2)
    t = time.monotonic()
    assert coffre.etat() == "verrouille"
    assert time.monotonic() - t < 1.5


def test_etat_coherent_avec_proteger(monkeypatch, faux):
    _linux(monkeypatch)
    for mode in ("ok", "verrouille"):
        faux.mode = mode
        attendu = coffre.etat()
        assert coffre.proteger("x", "n")[1] == ("disponible" if attendu == "disponible" else attendu)
    monkeypatch.setattr(coffre, "_backend", lambda: (_ for _ in ()).throw(coffre.CoffreErreur("indisponible")))
    assert coffre.etat() == coffre.proteger("x", "n")[1] == "indisponible"


def test_systeme_non_pris_en_charge(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert coffre.etat() == "indisponible" and coffre.disponible() is False
