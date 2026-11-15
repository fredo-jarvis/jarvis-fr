"""Revue de sécurité 1.1.2 (signalement de la communauté, 2026-11-15).

1. desktop.py n'exécute PLUS JAMAIS de code Python écrit par Gemini (l'ancien exec() dans un
   « bac à sable » du même processus se contournait en une ligne).
2. dev_agent et code_helper ne lancent un programme qu'après la confirmation de l'utilisateur à
   l'écran (core/confirm.py) ; la commande de lancement et les dépendances sont vérifiées ;
   aucune bibliothèque devinée n'est installée automatiquement.
3. Plus aucun shell=True (VS Code, luminosité Linux, pare-feu du tableau de bord).
"""
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

# Gemini n'est pas nécessaire pour ces tests : on le remplace par un module vide.
sys.modules.setdefault("core.gemini", types.SimpleNamespace(call=mock.Mock(), SMART="smart", FAST="fast"))

from actions import desktop, dev_agent, code_helper  # noqa: E402
from core import confirm  # noqa: E402

EVASION = "[c for c in ().__class__.__base__.__subclasses__() if c.__name__ == 'BuiltinImporter']"


class DesktopNExecutePlusDeCode(unittest.TestCase):
    def test_plus_aucun_exec_dans_desktop(self):
        source = (RACINE / "actions" / "desktop.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"\bexec\s*\(")
        self.assertNotRegex(source, r"\beval\s*\(")
        self.assertNotIn("_execute_generated_code", source)

    def test_une_tache_libre_est_redirigee_sans_rien_executer(self):
        with mock.patch("builtins.exec") as faux_exec:
            for params in ({"action": "task", "task": EVASION},
                           {"action": "inconnue_" + EVASION},
                           {"task": "supprime tout le bureau"}):
                res = desktop.desktop_control(params)
                self.assertIn("named tools", res)
            faux_exec.assert_not_called()

    def test_les_actions_nommees_marchent_toujours(self):
        with mock.patch.object(desktop, "get_desktop_stats", return_value="stats ok"), \
                mock.patch.object(desktop, "list_desktop", return_value="liste ok"):
            self.assertEqual(desktop.desktop_control({"action": "stats"}), "stats ok")
            self.assertEqual(desktop.desktop_control({"action": "list"}), "liste ok")


class CommandeDeLancementVerifiee(unittest.TestCase):
    def setUp(self):
        self.projet = Path("C:/projets/demo") if sys.platform == "win32" else Path("/tmp/projets/demo")

    def test_commandes_simples_acceptees(self):
        for cmd in ("python main.py", "python3 src/app.py --port 8000", "node index.js"):
            parts = dev_agent._safe_run_command(cmd, self.projet)
            self.assertIsNotNone(parts, cmd)

    def test_commandes_dangereuses_refusees(self):
        for cmd in ("powershell -c Remove-Item C:\\ -Recurse", "python ../../Windows/evil.py",
                    "python main.py & del *", "cmd /c calc", "python -c import_os", "bash run.sh",
                    "python main.exe", "python main.py ;whoami", ""):
            self.assertIsNone(dev_agent._safe_run_command(cmd, self.projet), cmd)


class DependancesVerifiees(unittest.TestCase):
    def test_noms_valides_et_suspects(self):
        ok, refuses = dev_agent._safe_dependencies(
            ["requests", "flask>=2.0", "uvicorn[standard]", "numpy==1.26.4",
             "--index-url=http://pirate", "git+https://x/y.git", "../paquet", "a b"])
        self.assertEqual(ok, ["requests", "flask>=2.0", "uvicorn[standard]", "numpy==1.26.4"])
        self.assertEqual(len(refuses), 4)

    def test_pas_d_installation_d_un_nom_devine(self):
        with mock.patch.object(dev_agent.subprocess, "run") as run:
            self.assertFalse(dev_agent._try_auto_install("No module named 'cv2'", Path("."), allowed=["requests"]))
            run.assert_not_called()
            run.return_value = types.SimpleNamespace(returncode=0)
            self.assertTrue(dev_agent._try_auto_install("No module named 'requests'", Path("."), allowed=["requests>=2"]))
            run.assert_called_once()


class VSCodeSansShell(unittest.TestCase):
    def test_chemin_piege_refuse(self):
        with mock.patch.object(dev_agent.subprocess, "Popen") as popen:
            self.assertFalse(dev_agent._open_vscode(Path("C:/projets/x & calc")))
            popen.assert_not_called()

    def test_jamais_de_shell(self):
        with mock.patch.object(dev_agent.subprocess, "Popen") as popen, \
                mock.patch.object(dev_agent.shutil, "which", return_value=__file__), \
                mock.patch.object(dev_agent.time, "sleep"):
            self.assertTrue(dev_agent._open_vscode(Path("C:/projets/demo")))
            self.assertFalse(popen.call_args.kwargs.get("shell"))


class ExecutionApresConfirmationSeulement(unittest.TestCase):
    def setUp(self):
        self.show, self.hide = mock.Mock(), mock.Mock()
        confirm.bind(self.show, self.hide)
        confirm._pending = None

    def tearDown(self):
        confirm._pending = None

    def test_code_helper_run_attend_la_confirmation(self):
        with mock.patch.object(code_helper, "_run_file") as run_file:
            res = code_helper.code_helper({"action": "run", "file_path": __file__})
            self.assertIn("CONFIRMATION_PENDING", res)
            run_file.assert_not_called()                 # rien n'a tourné
            self.show.assert_called_once()
            confirm.resolve(False)                       # l'utilisateur refuse
            run_file.assert_not_called()

    def test_code_helper_build_attend_la_confirmation(self):
        with mock.patch.object(code_helper, "_build") as build:
            res = code_helper.code_helper({"action": "build", "description": "une calculatrice"})
            self.assertIn("CONFIRMATION_PENDING", res)
            build.assert_not_called()

    def test_dev_agent_n_execute_rien_avant_confirmation(self):
        plan = {"project_name": "demo", "files": [{"path": "main.py"}], "entry_point": "main.py",
                "run_command": "python main.py", "dependencies": ["requests"]}
        with mock.patch.object(dev_agent, "_plan_project", return_value=plan), \
                mock.patch.object(dev_agent, "_execute_project") as execute:
            res = dev_agent.dev_agent({"description": "demo"})
            self.assertIn("CONFIRMATION_PENDING", res)
            execute.assert_not_called()
            titre, detail = self.show.call_args.args
            self.assertIn("EXÉCUTER", titre)
            self.assertIn("requests", detail)            # l'utilisateur voit ce qui sera installé

    def test_dev_agent_refuse_une_commande_piegee(self):
        plan = {"project_name": "demo", "files": [], "run_command": "powershell -c evil"}
        with mock.patch.object(dev_agent, "_plan_project", return_value=plan):
            res = dev_agent.dev_agent({"description": "demo"})
            self.assertIn("refused", res)
            self.show.assert_not_called()


class PlusAucunShellTrue(unittest.TestCase):
    def test_aucun_shell_true_dans_le_code(self):
        fautifs = []
        for f in list((RACINE / "actions").glob("*.py")) + list((RACINE / "dashboard").glob("*.py")) + \
                list((RACINE / "core").glob("*.py")):
            for i, ligne in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                code = ligne.split("#", 1)[0]
                if re.search(r"shell\s*=\s*True", code):
                    fautifs.append(f"{f.name}:{i}")
        self.assertEqual(fautifs, [])


if __name__ == "__main__":
    unittest.main()
