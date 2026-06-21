#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inventario_obsoleti.py — Inventario file obsoleti sotto Python e Python/work
Produce un report Markdown sul Desktop. Non tocca nulla.

Categorie cercate:
  - Backup migrazione:  *.migbak, *.cfgbak, *.fixbak, *.fixbak2, *.fixbak3, *.fixbak_*
  - Copie script:       * copy.py, *_copy.py, * copy *.py
  - Cartelle Old/:      qualsiasi cartella chiamata "Old" o "old"
  - Cartelle _bak:      *_bak, *_Config_bak, *_config_bak
  - File .mdbak:        *.mdbak
"""

# --- IRC shared bootstrap ---
# Rende disponibili i moduli in Python/shared/ senza dipendere da PYTHONPATH.
# Saltato se eseguito da bundle PyInstaller (sys.frozen=True): in quel caso
# i moduli sono gia' inclusi nel bundle.
import sys as _sys
from pathlib import Path as _Path
if not getattr(_sys, 'frozen', False):
    _shared = _Path.home() / "Library/CloudStorage/Dropbox/Documenti_IRC/Python/shared"
    if str(_shared) not in _sys.path:
        _sys.path.insert(0, str(_shared))
# --- end IRC shared bootstrap ---

APP_NAME = "InventarioObsoleti"
VERSION  = "1.1.0"

from irc_paths import PYTHON_ROOT, app_output_dir
from irc_logging import setup_app_logger

from pathlib import Path
from datetime import datetime

log = setup_app_logger(APP_NAME, also_to_console=True)

RADICI = [PYTHON_ROOT / "stable", PYTHON_ROOT / "work"]

# ─── Pattern ─────────────────────────────────────────────────────────────────

def è_backup_migrazione(p: Path) -> bool:
    s = p.suffix.lower()
    n = p.name.lower()
    return any([
        s in ('.migbak', '.cfgbak', '.mdbak'),
        '.fixbak' in n,
    ])

def è_copia_script(p: Path) -> bool:
    if p.suffix.lower() != '.py':
        return False
    n = p.stem.lower()
    return (n.endswith(' copy') or
            n.endswith('_copy') or
            ' copy ' in n or
            n.endswith('.copy'))

def è_cartella_old(p: Path) -> bool:
    return p.is_dir() and p.name.lower() == 'old'

def è_cartella_bak(p: Path) -> bool:
    return p.is_dir() and ('_bak' in p.name.lower())

def è_in_venv(p: Path) -> bool:
    return '.venv' in p.parts or '__pycache__' in p.parts

def size_str(p: Path) -> str:
    try:
        b = p.stat().st_size
        if b < 1024: return f"{b} B"
        if b < 1024**2: return f"{b//1024} KB"
        return f"{b//1024**2} MB"
    except:
        return "?"

def mod_str(p: Path) -> str:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m/%Y")
    except:
        return "?"

# ─── Raccolta ─────────────────────────────────────────────────────────────────

backup_migrazione = []
copie_script = []
cartelle_old = []
cartelle_bak = []

log.info(f"Avviato v{VERSION}")

for radice in RADICI:
    if not radice.exists():
        continue
    for p in sorted(radice.rglob("*")):
        if è_in_venv(p):
            continue
        if p.is_file():
            if è_backup_migrazione(p):
                backup_migrazione.append(p)
            elif è_copia_script(p):
                copie_script.append(p)
        elif p.is_dir():
            if è_cartella_old(p):
                cartelle_old.append(p)
            elif è_cartella_bak(p):
                cartelle_bak.append(p)

# ─── Report ──────────────────────────────────────────────────────────────────

def rel(p: Path) -> str:
    try:
        return str(p.relative_to(PYTHON_ROOT))
    except:
        return str(p)

lines = []
now = datetime.now().strftime("%d/%m/%Y %H:%M")
lines.append(f"# Inventario file obsoleti — {now}\n")
lines.append(f"**Radice:** `{PYTHON_ROOT}`\n")

totale = len(backup_migrazione) + len(copie_script) + len(cartelle_old) + len(cartelle_bak)
lines.append(f"**Totale elementi trovati:** {totale}\n")
lines.append("---\n")

# 1. Backup migrazione
lines.append(f"## 1. Backup migrazione ({len(backup_migrazione)} file)\n")
lines.append("File `.migbak`, `.cfgbak`, `.fixbak*`, `.mdbak` — creati dai script di migrazione.\n")
lines.append("**Eliminabili** dopo aver verificato che le app funzionano.\n")
if backup_migrazione:
    lines.append("| File | Dimensione | Data |")
    lines.append("|---|---|---|")
    for p in backup_migrazione:
        lines.append(f"| `{rel(p)}` | {size_str(p)} | {mod_str(p)} |")
else:
    lines.append("*(nessuno)*")
lines.append("")

# 2. Copie script
lines.append(f"## 2. Copie script ({len(copie_script)} file)\n")
lines.append("File `.py` con ` copy` o `_copy` nel nome — copie di sicurezza manuali.\n")
lines.append("**Verificare** se sono ancora utili o se la versione principale è aggiornata.\n")
if copie_script:
    lines.append("| File | Dimensione | Data |")
    lines.append("|---|---|---|")
    for p in copie_script:
        lines.append(f"| `{rel(p)}` | {size_str(p)} | {mod_str(p)} |")
else:
    lines.append("*(nessuno)*")
lines.append("")

# 3. Cartelle Old
lines.append(f"## 3. Cartelle Old/ ({len(cartelle_old)} cartelle)\n")
lines.append("Contengono versioni precedenti degli script.\n")
lines.append("**Verificare** il contenuto prima di eliminare — alcune potrebbero avere varianti utili.\n")
if cartelle_old:
    for p in cartelle_old:
        # Conta i file dentro
        try:
            figli = list(p.rglob("*"))
            n_file = sum(1 for f in figli if f.is_file())
        except:
            n_file = "?"
        lines.append(f"- `{rel(p)}/` — {n_file} file")
else:
    lines.append("*(nessuno)*")
lines.append("")

# 4. Cartelle _bak
lines.append(f"## 4. Cartelle _bak ({len(cartelle_bak)} cartelle)\n")
lines.append("Vecchie cartelle `_Config` rinominate dalla migrazione.\n")
lines.append("**Eliminabili** dopo aver verificato che tutte le app leggono la nuova `_config/`.\n")
if cartelle_bak:
    for p in cartelle_bak:
        try:
            figli = list(p.rglob("*"))
            n_file = sum(1 for f in figli if f.is_file())
        except:
            n_file = "?"
        lines.append(f"- `{rel(p)}/` — {n_file} file")
else:
    lines.append("*(nessuno)*")
lines.append("")

lines.append("---\n")
lines.append("## Comandi di pulizia\n")
lines.append("Dopo aver verificato, esegui solo le sezioni che vuoi eliminare:\n")
lines.append("```bash")
lines.append("# 1. Backup migrazione")
lines.append("find ~/Library/CloudStorage/Dropbox/Documenti_IRC/Python \\")
lines.append("     -name '*.migbak' -o -name '*.cfgbak' -o -name '*.mdbak' \\")
lines.append("     -o -name '*.fixbak*' | xargs rm -f")
lines.append("")
lines.append("# 4. Cartelle _bak (ATTENZIONE: irreversibile)")
for p in cartelle_bak:
    lines.append(f'rm -rf "{p}"')
lines.append("```")

# ─── Scrivi ───────────────────────────────────────────────────────────────────

dest = app_output_dir(APP_NAME) / "inventario_obsoleti.md"
dest.write_text("\n".join(lines), encoding="utf-8")
log.info(f"Report salvato: {dest}")
print(f"Report salvato in: {dest}")
print(f"\nRiepilogo:")
print(f"  Backup migrazione: {len(backup_migrazione)} file")
print(f"  Copie script:      {len(copie_script)} file")
print(f"  Cartelle Old/:     {len(cartelle_old)}")
print(f"  Cartelle _bak:     {len(cartelle_bak)}")
import subprocess
subprocess.run(["open", str(dest)])

if __name__ == "__main__":
    pass
