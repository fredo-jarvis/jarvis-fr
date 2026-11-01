"""
Lire n'importe quel fichier déposé sur l'interface et répondre à la question de la personne
(bug d'un client, 01/11 : un PDF déposé, mais Jarvis ne le lisait pas et ne répondait pas à la question).

- Texte : PDF, Word, PowerPoint, Excel, CSV, texte, Markdown, JSON, XML, code, HTML, YAML...
- Image, et PDF scanné (sans texte) : les pages sont envoyées à Gemini comme images (il les lit).
- La question de la personne est toujours transmise à Gemini avec le contenu du fichier.
"""
from pathlib import Path

MAX_CARACTERES = 40000
MAX_PAGES_IMAGES = 6

EXT_IMAGES = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff"}
EXT_TEXTE = {"txt", "md", "rst", "log", "csv", "tsv", "json", "xml", "html", "htm", "css", "js", "ts",
             "py", "yaml", "yml", "toml", "ini", "cfg", "sql", "sh", "ps1", "bat", "java", "c", "cpp",
             "cs", "go", "rs", "rb", "php", "tex", "srt", "vtt", "rtf"}


def _decoder(octets: bytes) -> str:
    encodages = ["utf-8-sig"]
    if octets[:2] in (b"\xff\xfe", b"\xfe\xff"):      # utf-16 seulement si le fichier l'annonce
        encodages.append("utf-16")
    for enc in encodages + ["cp1252", "latin-1"]:
        try:
            return octets.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return octets.decode("utf-8", errors="ignore")


def _pdf(path: Path) -> str:
    texte = ""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                texte += (page.extract_text() or "") + "\n"
    except Exception:
        texte = ""
    if texte.strip():
        return texte
    try:
        import PyPDF2
        with open(path, "rb") as f:
            lecteur = PyPDF2.PdfReader(f)
            return "\n".join((p.extract_text() or "") for p in lecteur.pages)
    except Exception:
        return ""


def _docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    morceaux = [p.text for p in doc.paragraphs]
    for tableau in doc.tables:
        for ligne in tableau.rows:
            morceaux.append(" | ".join(c.text.strip() for c in ligne.cells))
    return "\n".join(morceaux)


def _pptx(path: Path) -> str:
    from pptx import Presentation
    morceaux = []
    for i, diapo in enumerate(Presentation(str(path)).slides, 1):
        morceaux.append(f"--- Diapo {i} ---")
        for forme in diapo.shapes:
            if getattr(forme, "has_text_frame", False) and forme.text_frame.text.strip():
                morceaux.append(forme.text_frame.text)
    return "\n".join(morceaux)


def _xlsx(path: Path) -> str:
    from openpyxl import load_workbook
    classeur = load_workbook(str(path), read_only=True, data_only=True)
    morceaux = []
    try:
        for feuille in classeur.worksheets:
            morceaux.append(f"--- Feuille « {feuille.title} » ---")
            for n, ligne in enumerate(feuille.iter_rows(values_only=True)):
                if n >= 2000:
                    morceaux.append("(… suite non lue)")
                    break
                if any(c is not None for c in ligne):
                    morceaux.append(" | ".join("" if c is None else str(c) for c in ligne))
    finally:
        classeur.close()          # sinon Windows garde le fichier verrouillé
    return "\n".join(morceaux)


def lire_texte(chemin) -> str:
    """Le texte du fichier, ou une chaîne vide si on n'en tire rien (PDF scanné, image, format inconnu)."""
    path = Path(chemin)
    ext = path.suffix.lower().lstrip(".")
    try:
        if ext == "pdf":
            texte = _pdf(path)
        elif ext == "docx":
            texte = _docx(path)
        elif ext == "pptx":
            texte = _pptx(path)
        elif ext in ("xlsx", "xlsm"):
            texte = _xlsx(path)
        elif ext in EXT_TEXTE or ext == "":
            texte = _decoder(path.read_bytes())
        elif ext in EXT_IMAGES:
            texte = ""
        else:                                    # format inconnu : on essaie quand même comme du texte
            brut = path.read_bytes()[:200000]
            texte = _decoder(brut) if b"\x00" not in brut[:4000] else ""
    except Exception as e:
        print(f"[Lecteur] {path.name} : {e}")
        texte = ""
    return texte.strip()


def images_du_fichier(chemin, max_pages: int = MAX_PAGES_IMAGES) -> list:
    """Images à envoyer à Gemini : le fichier lui-même si c'est une image, les premières pages si
    c'est un PDF (scanné ou sans texte)."""
    path = Path(chemin)
    ext = path.suffix.lower().lstrip(".")
    try:
        from PIL import Image
        if ext in EXT_IMAGES:
            return [Image.open(path).convert("RGB")]
        if ext == "pdf":
            import pdfplumber
            images = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages[:max_pages]:
                    images.append(page.to_image(resolution=110).original.convert("RGB"))
            return images
    except Exception as e:
        print(f"[Lecteur] images de {path.name} : {e}")
    return []


def construire_demande(chemin, question: str = "") -> list:
    """Le contenu à envoyer à Gemini : consigne, puis texte du fichier ou images. Liste vide si rien de lisible."""
    path = Path(chemin)
    consigne = (question or "").strip() or "Résume ce fichier de façon claire et utile."
    texte = lire_texte(path)
    if texte:
        coupe = " (début du fichier seulement)" if len(texte) > MAX_CARACTERES else ""
        return [f"Fichier : {path.name}{coupe}\n\nContenu :\n{texte[:MAX_CARACTERES]}\n\n"
                f"Demande de l'utilisateur : {consigne}\nRéponds en français, simplement, en t'appuyant "
                f"uniquement sur ce fichier."]
    images = images_du_fichier(path)
    if images:
        return [f"Fichier : {path.name} (pages en images).\nDemande de l'utilisateur : {consigne}\n"
                f"Lis le texte visible sur les images. Réponds en français, simplement, en t'appuyant "
                f"uniquement sur ce fichier."] + images
    return []


def en_parts_gemini(contenu: list) -> list:
    """Les images PIL deviennent des données JPEG que Gemini comprend. Sans ça, core/gemini.py les
    ignore et Gemini répond « aucun fichier n'a été fourni » (constaté avec le vrai Gemini, 01/11)."""
    import io
    from google.genai import types
    sortie = []
    for item in contenu:
        if isinstance(item, str):
            sortie.append(item)
        else:
            tampon = io.BytesIO()
            item.convert("RGB").save(tampon, format="JPEG", quality=88)
            sortie.append(types.Part.from_bytes(data=tampon.getvalue(), mime_type="image/jpeg"))
    return sortie


def repondre(chemin, question: str = "", appeler=None) -> str:
    """Lit le fichier et répond à la question. `appeler` sert aux tests (sinon Gemini)."""
    path = Path(chemin)
    if not path.is_file():
        return f"Je ne trouve pas le fichier {path.name}."
    demande = construire_demande(path, question)
    if not demande:
        return (f"Je n'arrive pas à lire le contenu de « {path.name} » "
                f"(format non pris en charge ou fichier vide).")
    if appeler is None:
        from core import gemini

        def appeler(contenu):
            rep = gemini.call(en_parts_gemini(contenu), tier=gemini.SMART, timeout_ms=90000)
            return rep.text if rep is not None else None
    try:
        reponse = appeler(demande)
    except Exception as e:
        return f"Je n'ai pas réussi à analyser « {path.name} » : {e}"
    if not reponse:
        return f"Je n'ai pas réussi à analyser « {path.name} » (Gemini n'a pas répondu)."
    return str(reponse).strip()
