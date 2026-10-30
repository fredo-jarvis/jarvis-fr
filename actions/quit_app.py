"""Close (quit) a specific application by name.

The bundled ``computer_settings`` action only presses Alt+F4, which closes the
*foreground* window. When the user names an app ("close PMDG OC3", "ferme
Chrome") that is unreliable, so this action finds the matching process and
terminates it instead.
"""

import re

import psutil


def quit_app(parameters=None, response=None, player=None, session_memory=None) -> str:
    app_name = ((parameters or {}).get("app_name") or "").strip()
    if not app_name:
        return "No application name provided."

    if player:
        player.write_log(f"[quit_app] {app_name}")

    tokens = [t for t in re.split(r"[^a-z0-9]+", app_name.lower()) if t]
    if not tokens:
        return f"Could not parse application name: {app_name}"

    # Always match the first token (most distinctive) plus any token of 4+ chars.
    match_tokens = [tokens[0]] + [t for t in tokens[1:] if len(t) >= 4]

    matched = []
    for proc in psutil.process_iter(["name", "pid"]):
        pname = (proc.info.get("name") or "").lower()
        if not pname:
            continue
        if any(t in pname for t in match_tokens):
            matched.append(proc)

    if not matched:
        return (
            f"No running process matched '{app_name}'. "
            f"Check the exact name, or it may already be closed."
        )

    results = []
    for proc in matched:
        name = proc.info.get("name") or "?"
        pid = proc.info.get("pid")
        try:
            proc.terminate()
            results.append(f"{name} (pid {pid})")
        except Exception as e:
            try:
                proc.kill()
                results.append(f"{name} (pid {pid}, force)")
            except Exception as e2:
                results.append(f"{name} (pid {pid}) FAILED: {e2}")

    return "Closed: " + ", ".join(results)


TOOL = {
    "name": "quit_app",
    "description": (
        "Closes/quits a specific application by name — finds its running process "
        "and terminates it. Use this whenever the user asks to close, quit, stop "
        "or kill a NAMED app (e.g. 'close PMDG OC3', 'ferme Chrome', 'arrête Spotify'). "
        "Do NOT use it to close the currently focused window; use close_app for that."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": "Name of the application to close (e.g. 'PMDG OC3', 'Chrome', 'Spotify')."
            }
        },
        "required": ["app_name"],
    },
    "handler": quit_app,
}
