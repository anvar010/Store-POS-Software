"""Auto-update support: version check, download and self-replace.

Designed to work both as a plain script (development) and inside a
PyInstaller one-file/one-folder build (``sys.frozen``). The startup version
check fails silently on any network/parse error; the download step (which is
user-initiated) reports errors normally.
"""

import os
import sys
import threading
import subprocess

import config

# Tk virtual event fired (thread-safely) on the main window when an update
# is found. The newer version string is stashed on the widget first.
UPDATE_EVENT = "<<UpdateAvailable>>"


# --------------------------------------------------------------------------
# Version helpers
# --------------------------------------------------------------------------
def _parse(version):
    """Turn '1.2.3' into a comparable tuple (1, 2, 3); junk -> 0."""
    parts = []
    for chunk in str(version).strip().split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts) or (0,)


def is_newer(latest, current):
    return _parse(latest) > _parse(current)


def fetch_latest_version(timeout=5):
    """Fetch version.txt from GitHub. Returns a version string or None.

    Any failure (no internet, 404, bad content, requests missing) -> None.
    """
    try:
        import requests
        resp = requests.get(config.UPDATE_VERSION_URL, timeout=timeout)
        resp.raise_for_status()
        text = resp.text.strip()
        # accept only sane version strings like 1.0 / 1.2.3
        if text and all(c.isdigit() or c == "." for c in text):
            return text
    except Exception:
        return None
    return None


# --------------------------------------------------------------------------
# Startup check (background thread, thread-safe UI notification)
# --------------------------------------------------------------------------
def start_check(widget, current_version=None):
    """Check for an update in a daemon thread; never blocks the UI.

    When a newer version is found, store it on ``widget.latest_version`` and
    fire the ``UPDATE_EVENT`` virtual event on ``widget`` (thread-safe).
    """
    current_version = current_version or config.APP_VERSION

    def worker():
        latest = fetch_latest_version()
        if latest and is_newer(latest, current_version):
            try:
                widget.latest_version = latest
                widget.event_generate(UPDATE_EVENT, when="tail")
            except Exception:
                # widget may be gone, or Tk shutting down — stay silent
                pass

    threading.Thread(target=worker, daemon=True, name="update-check").start()


# --------------------------------------------------------------------------
# Frozen-exe awareness
# --------------------------------------------------------------------------
def is_frozen():
    return bool(getattr(sys, "frozen", False))


def current_exe_path():
    """Path to the running .exe when frozen, else None (dev/script mode)."""
    return os.path.abspath(sys.executable) if is_frozen() else None


# --------------------------------------------------------------------------
# Download + apply
# --------------------------------------------------------------------------
def download_update(progress=None, timeout=60):
    """Download the new .exe next to the current one.

    progress: optional callback(downloaded_bytes, total_bytes).
    Returns the path to the downloaded file. Raises on failure.
    """
    import requests

    exe = current_exe_path()
    if exe:
        target_dir = os.path.dirname(exe)
        stem = os.path.splitext(os.path.basename(exe))[0]
    else:
        # dev mode: just drop it in the project folder
        target_dir = config.BASE_DIR
        stem = "FreshMart_Billing"
    new_path = os.path.join(target_dir, f"{stem}_new.exe")

    with requests.get(config.UPDATE_EXE_URL, stream=True,
                      timeout=timeout) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done = 0
        with open(new_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    return new_path


def apply_update_and_restart(new_path):
    """Swap the running .exe with the downloaded one and relaunch.

    Windows cannot overwrite a running .exe, so we hand off to a tiny batch
    script that waits for this process to exit, replaces the file and starts
    the new version. This function does not return on success (it exits).
    """
    exe = current_exe_path()
    if not exe:
        raise RuntimeError(
            "Self-replace only works in the packaged .exe build. "
            f"Downloaded the new version to:\n{new_path}")

    bat_path = os.path.join(os.path.dirname(exe), "_apply_update.bat")
    # ping is used as a portable 'sleep'; the delete loop waits until this
    # process has released the old .exe.
    script = (
        "@echo off\r\n"
        "ping 127.0.0.1 -n 2 >nul\r\n"
        ":retry\r\n"
        f'del "{exe}" >nul 2>&1\r\n'
        f'if exist "{exe}" (\r\n'
        "  ping 127.0.0.1 -n 2 >nul\r\n"
        "  goto retry\r\n"
        ")\r\n"
        f'move /y "{new_path}" "{exe}" >nul\r\n'
        f'start "" "{exe}"\r\n'
        'del "%~f0" >nul 2>&1\r\n'
    )
    with open(bat_path, "w") as fh:
        fh.write(script)

    flags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(["cmd", "/c", bat_path], close_fds=True,
                     creationflags=flags)
    # Hard-exit so the batch can replace the file immediately.
    os._exit(0)
