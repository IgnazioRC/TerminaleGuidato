#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Terminale Guidato 0.1.5

Esecutore guidato di comandi Terminale.

Novità 0.1.5:
- versione completa, non patch
- output pulito al cambio comando
- intestazione output con nome comando / rischio / comando tecnico
- intestazione RUN con nome comando
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
import threading
import signal
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ---------------------------------------------------------------------
# Import moduli condivisi
#
# path_widgets.py vive nella posizione canonica:
#   ~/Library/CloudStorage/Dropbox/Documenti_IRC/Python/shared/path_widgets.py
#
# Caso script normale:
#   __file__ è dentro Python/stable o Python/work, quindi si può risalire.
#
# Caso app PyInstaller:
#   __file__ è dentro il bundle .app, quindi NON si può risalire alla
#   cartella Python. Serve un fallback esplicito sul percorso canonico.
# ---------------------------------------------------------------------
import sys

SCRIPT_DIR = Path(__file__).resolve().parent

CANONICAL_PYTHON_ROOT = (
    Path.home()
    / "Library"
    / "CloudStorage"
    / "Dropbox"
    / "Documenti_IRC"
    / "Python"
)

PYTHON_ROOT_CANDIDATES = [
    SCRIPT_DIR.parent.parent,
    SCRIPT_DIR.parent,
    CANONICAL_PYTHON_ROOT,
]

for candidate in PYTHON_ROOT_CANDIDATES:
    shared_candidate = candidate / "shared" / "path_widgets.py"
    if shared_candidate.exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

try:
    from shared.path_widgets import PathVar, PathEntry, log_path
except Exception as exc:
    searched = "\n".join(str(p / "shared" / "path_widgets.py") for p in PYTHON_ROOT_CANDIDATES)
    raise RuntimeError(
        "Modulo path_widgets non trovato.\n\n"
        "Percorsi cercati:\n"
        f"{searched}\n\n"
        "Verifica che esista:\n"
        "~/Library/CloudStorage/Dropbox/Documenti_IRC/Python/shared/path_widgets.py"
    ) from exc


APP_NAME = "Terminale Guidato"
APP_VERSION = "0.3.8"
VERSION = "0.3.8"

HOME = Path.home()
DROPBOX = HOME / "Library" / "CloudStorage" / "Dropbox"
DOC_IRC = DROPBOX / "Documenti_IRC"
PYTHON_ROOT = DOC_IRC / "Python"
CONFIG_DIR = PYTHON_ROOT / "_Config" / "TerminaleGuidato"
CONFIG_PATH = CONFIG_DIR / "config.json"
STATE_PATH = CONFIG_DIR / "state.json"
LOG_DIR = HOME / "Documents" / "log"
DOWNLOAD_DIR = HOME / "Documents" / "download"


def expand_path(value: str | Path) -> str:
    if value is None:
        return ""
    return os.path.expandvars(os.path.expanduser(str(value)))


def shell_quote(value: str) -> str:
    return shlex.quote(expand_path(value))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


class TerminaleGuidatoApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1500x780")
        self.root.minsize(1250, 680)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

        self.config_path = self.find_config()
        self.config = load_json(self.config_path)
        self.state = self.load_state()
        self.categories = self.load_categories_from_config(self.config)
        self.current_command = None
        self.param_vars: dict[str, PathVar | tk.StringVar | tk.BooleanVar] = {}
        self.last_try_signature = None
        self.current_process = None
        self.current_process_label = None
        self.process_stop_requested = False
        self.last_dir = self.state.get("last_dir", str(DOC_IRC))

        self.build_ui()
        self.populate_categories()

    def find_config(self) -> Path:
        candidates = [
            CONFIG_PATH,
            Path.cwd() / "config.json",
            Path.cwd() / "config_TerminaleGuidato_v0_1.json",
        ]
        for p in candidates:
            if p.exists():
                return p

        msg = "Config non trovato.\n\nCercato:\n" + "\n".join(str(p) for p in candidates)
        messagebox.showerror("Config non trovato", msg)
        raise SystemExit(1)

    def load_state(self) -> dict:
        try:
            if STATE_PATH.exists():
                return load_json(STATE_PATH)
        except Exception:
            pass
        return {}

    def save_state(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(
                json.dumps({"last_dir": self.last_dir}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def load_categories_from_config(self, config: dict) -> list[dict]:
        """Carica le categorie dei comandi.

        Supporta:
        - config monolitico: {"categorie": [...]}
        - config modulare: {"commands_dir": "Commands", "command_files": [...]}

        Ogni file modulo contiene:
        {"categoria": "...", "comandi": [...]}
        """
        if "categorie" in config:
            return config.get("categorie", [])

        commands_dir_name = config.get("commands_dir", "Commands")
        command_files = config.get("command_files", [])
        base_dir = self.config_path.parent
        commands_path = base_dir / commands_dir_name

        categories = []
        errors = []

        for fname in command_files:
            fpath = commands_path / fname
            try:
                data = load_json(fpath)
                if "nome" in data and "comandi" in data:
                    categories.append(data)
                else:
                    categories.append({
                        "nome": data.get("categoria", Path(fname).stem),
                        "comandi": data.get("comandi", [])
                    })
            except Exception as exc:
                errors.append(f"{fname}: {exc}")

        if errors:
            messagebox.showwarning(
                "Config comandi parziale",
                "Alcuni file comandi non sono stati caricati:\n\n" + "\n".join(errors)
            )

        return categories


    def build_ui(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 8))

        title = ttk.Label(header, text=APP_NAME, font=("Helvetica", 22, "bold"))
        title.pack(anchor="w")

        cfg = ttk.Label(header, text=f"Config: {self.config_path}", foreground="#555")
        cfg.pack(anchor="w", pady=(4, 0))

        main = ttk.PanedWindow(outer, orient="horizontal")
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main, padding=(0, 0, 10, 0))
        main.add(left, weight=1)

        ttk.Label(left, text="Categoria").pack(anchor="w")
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(left, textvariable=self.category_var, state="readonly")
        self.category_combo.pack(fill="x", pady=(2, 12))
        self.category_combo.bind("<<ComboboxSelected>>", self.on_category_changed)

        ttk.Label(left, text="Comando").pack(anchor="w")
        self.command_list = tk.Listbox(left, height=18, exportselection=False)
        self.command_list.pack(fill="both", expand=True)
        self.command_list.bind("<<ListboxSelect>>", self.on_command_selected)
        self.command_list.bind("<Double-Button-1>", self.on_command_double_click)
        self.command_list.bind("<Return>", self.on_command_return)

        self.right = ttk.Frame(main, padding=(10, 0, 0, 0))
        main.add(self.right, weight=4)

        top_row = ttk.Frame(self.right)
        top_row.pack(fill="x")

        self.cmd_title = ttk.Label(top_row, text="Seleziona un comando", font=("Helvetica", 18, "bold"))
        self.cmd_title.pack(side="left", anchor="w")

        ttk.Button(top_row, text="Help comando", command=self.show_help).pack(side="right")
        ttk.Button(top_row, text="Manuale tecnico", command=self.show_man_page).pack(side="right", padx=(0, 8))

        self.cmd_desc = ttk.Label(self.right, text="", wraplength=900)
        self.cmd_desc.pack(anchor="w", pady=(6, 8))

        self.cmd_risk = ttk.Label(self.right, text="")
        self.cmd_risk.pack(anchor="w", pady=(0, 10))

        self.params_container = ttk.LabelFrame(self.right, text="Parametri", padding=10)
        self.params_container.pack(fill="x", pady=(0, 10))

        cmd_box = ttk.LabelFrame(self.right, text="Comando", padding=10)
        cmd_box.pack(fill="x", pady=(0, 10))

        # Anteprima comando su una riga dedicata:
        # così i bottoni non vengono tagliati quando la finestra è stretta.
        cmd_row = ttk.Frame(cmd_box)
        cmd_row.pack(fill="x")
        self.preview_var = tk.StringVar()
        self.preview_entry = ttk.Entry(cmd_row, textvariable=self.preview_var, state="readonly")
        self.preview_entry.pack(side="left", fill="x", expand=True)

        cmd_buttons = ttk.Frame(cmd_box)
        cmd_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(cmd_buttons, text="Aggiorna anteprima", command=self.update_preview).pack(side="left")
        ttk.Button(cmd_buttons, text="Copia comando", command=self.copy_command).pack(side="left", padx=(8, 0))

        # Bottoni operativi: stanno SOPRA l'output, così non spariscono
        # se la finestra viene ridimensionata.
        buttons = ttk.Frame(self.right)
        buttons.pack(fill="x", pady=(0, 10))

        self.run_button = ttk.Button(buttons, text="Esegui", command=self.run_current)
        self.run_button.pack(side="left")

        self.try_button = ttk.Button(buttons, text="TRY", command=self.run_try)
        self.try_button.pack(side="left", padx=(8, 0))

        self.delete_button = ttk.Button(buttons, text="DELETE", command=self.run_delete)
        self.delete_button.pack(side="left", padx=(8, 0))

        self.stop_button = ttk.Button(buttons, text="STOP", command=self.stop_current_process)
        self.stop_button.pack(side="left", padx=(8, 0))
        self.stop_button.configure(state="disabled")

        ttk.Button(buttons, text="Copia output", command=self.copy_output).pack(side="left", padx=(16, 0))
        ttk.Button(buttons, text="Salva output…", command=self.save_output).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Pulisci output", command=lambda: self.output.delete("1.0", "end")).pack(side="left", padx=(8, 0))

        ttk.Button(buttons, text="Esci", command=self.safe_exit).pack(side="right")

        output_box = ttk.LabelFrame(self.right, text="Output / log esecuzione", padding=10)
        output_box.pack(fill="both", expand=True)

        self.output = tk.Text(output_box, wrap="none", font=("Menlo", 11), height=12)
        self.output.pack(side="left", fill="both", expand=True)

        yscroll = ttk.Scrollbar(output_box, orient="vertical", command=self.output.yview)
        yscroll.pack(side="right", fill="y")
        self.output.configure(yscrollcommand=yscroll.set)

        # Stili output/log: rendono più leggibile la separazione
        # fra intestazione, comando e risultato.
        self.output.tag_configure("run_header", font=("Menlo", 11, "bold"))
        self.output.tag_configure("command", font=("Menlo", 11, "italic"))
        self.output.tag_configure("separator", font=("Menlo", 11))
        self.output.tag_configure("status", font=("Menlo", 11, "bold"))
        self.output.tag_configure("stderr", font=("Menlo", 11, "italic"))

    def populate_categories(self):
        names = [c.get("nome", "Senza categoria") for c in self.categories]
        self.category_combo["values"] = names
        if names:
            self.category_var.set(names[0])
            self.populate_commands(0)

    def on_category_changed(self, event=None):
        self.populate_commands(self.category_combo.current())

    def populate_commands(self, category_idx: int):
        self.command_list.delete(0, "end")
        commands = self.categories[category_idx].get("comandi", [])
        for cmd in commands:
            self.command_list.insert("end", cmd.get("titolo", cmd.get("id", "Senza titolo")))
        if commands:
            self.command_list.selection_set(0)
            self.on_command_selected()

    def on_command_double_click(self, event=None):
        """Doppio clic su un comando = esegui.

        La sicurezza resta gestita da run_current():
        - basso: esecuzione diretta
        - medio / medio-basso: conferma
        - alto: conferma oggi, TRY/DELETE in futuro
        """
        self.on_command_selected()
        self.run_current()

    def on_command_return(self, event=None):
        """Tasto Invio sulla lista comandi = esegui comando selezionato."""
        self.on_command_selected()
        self.run_current()

    def on_command_selected(self, event=None):
        cat_idx = self.category_combo.current()
        sel = self.command_list.curselection()
        if cat_idx < 0 or not sel:
            return

        self.current_command = self.categories[cat_idx]["comandi"][sel[0]]
        self.param_vars.clear()

        self.cmd_title.configure(text=self.current_command.get("titolo", ""))
        self.cmd_desc.configure(text=self.current_command.get("descrizione", ""))
        self.cmd_risk.configure(text=f"Rischio: {self.current_command.get('rischio', 'n/d')}")

        for child in self.params_container.winfo_children():
            child.destroy()

        params = self.current_command.get("parametri", [])
        if not params:
            ttk.Label(self.params_container, text="Nessun parametro.").pack(anchor="w")
        else:
            for row_idx, p in enumerate(params):
                self.add_param_widget(self.params_container, p, row_idx)

        self.last_try_signature = None
        self.update_preview()
        self.reset_output_for_current_command()
        self.update_action_buttons()

    def reset_output_for_current_command(self):
        self.output.delete("1.0", "end")
        if not self.current_command:
            return

        titolo = self.current_command.get("titolo", "")
        descrizione = self.current_command.get("descrizione", "")
        rischio = self.current_command.get("rischio", "n/d")
        man = self.current_command.get("man", "")
        tecnico = man if man else "n/d"
        ambito = self.current_command.get("ambito", "")

        self.output.insert("end", f"=== {titolo} ===\n", "run_header")
        self.output.insert("end", f"Rischio: {rischio}\n")
        self.output.insert("end", f"Comando tecnico principale: {tecnico}\n")
        if ambito:
            self.output.insert("end", f"Ambito: {ambito}\n")
        if descrizione:
            self.output.insert("end", f"Descrizione: {descrizione}\n")
        self.output.insert("end", "\n")

    def add_param_widget(self, parent, param: dict, row_idx: int):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)

        ttk.Label(row, text=param.get("label", param.get("nome", "Parametro")), width=24).pack(side="left")

        name = param["nome"]
        tipo = param.get("tipo", "testo")
        default = expand_path(param.get("default", ""))

        if tipo == "path_cartella":
            value = default or self.last_dir or str(DOC_IRC)
            # Se esiste una cartella usata di recente, la preferiamo al default del singolo comando.
            if self.last_dir and Path(expand_path(self.last_dir)).exists():
                value = self.last_dir
            var = PathVar(value=value)
            self.param_vars[name] = var
            entry = PathEntry(row, var)
            entry.pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Sfoglia…", command=lambda v=var: self.browse_directory(v)).pack(side="left", padx=(8, 0))
            ttk.Button(row, text="Documenti_IRC", command=lambda v=var: self.set_to_doc_irc(v)).pack(side="left", padx=(8, 0))

        elif tipo == "path_file":
            value = default or str(DOWNLOAD_DIR)
            var = PathVar(value=value)
            self.param_vars[name] = var
            entry = PathEntry(row, var)
            entry.pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Scegli…", command=lambda v=var: self.browse_file(v)).pack(side="left", padx=(8, 0))

        elif tipo == "booleano":
            var = tk.BooleanVar(value=bool(param.get("default", False)))
            self.param_vars[name] = var
            ttk.Checkbutton(row, variable=var, command=self.update_preview).pack(side="left")

        else:
            var = tk.StringVar(value=str(param.get("default", "")))
            self.param_vars[name] = var
            ent = ttk.Entry(row, textvariable=var)
            ent.pack(side="left", fill="x", expand=True)
            ent.bind("<KeyRelease>", lambda e: self.update_preview())

    def browse_directory(self, var: PathVar):
        initial = var.get() or self.last_dir or str(DOC_IRC)
        if not Path(expand_path(initial)).exists():
            initial = str(DOC_IRC)

        selected = filedialog.askdirectory(title="Scegli cartella", initialdir=expand_path(initial), mustexist=True)
        if selected:
            var.set(selected)
            self.last_dir = selected
            self.save_state()
            self.update_preview()

    def browse_file(self, var: PathVar):
        initial = var.get() or self.last_dir or str(DOWNLOAD_DIR)
        initial_path = Path(expand_path(initial))
        initialdir = initial_path if initial_path.is_dir() else initial_path.parent
        selected = filedialog.askopenfilename(title="Scegli file", initialdir=str(initialdir))
        if selected:
            var.set(selected)
            self.last_dir = str(Path(selected).parent)
            self.save_state()
            self.update_preview()

    def set_to_doc_irc(self, var: PathVar):
        var.set(str(DOC_IRC))
        self.last_dir = str(DOC_IRC)
        self.save_state()
        self.update_preview()

    def is_try_delete_command(self) -> bool:
        if not self.current_command:
            return False
        return "modalita" in self.current_command and "try" in self.current_command.get("modalita", {}) and "delete" in self.current_command.get("modalita", {})

    def current_signature(self) -> str:
        """Firma del comando corrente e dei parametri.

        Serve per impedire DELETE se dopo il TRY sono stati cambiati cartella,
        pattern o altri parametri.
        """
        if not self.current_command:
            return ""
        values = []
        for name in sorted(self.param_vars.keys()):
            var = self.param_vars[name]
            values.append(f"{name}={var.get()}")
        return self.current_command.get("id", "") + "|" + "|".join(values)

    def update_action_buttons(self):
        """Abilita/disabilita bottoni in base al tipo comando."""
        if not hasattr(self, "run_button"):
            return

        if self.current_process is not None:
            self.run_button.configure(state="disabled")
            self.try_button.configure(state="disabled")
            self.delete_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            return

        self.stop_button.configure(state="disabled")

        if self.is_try_delete_command():
            self.run_button.configure(state="disabled")
            self.try_button.configure(state="normal")
            self.delete_button.configure(state="disabled")
        else:
            self.run_button.configure(state="normal")
            self.try_button.configure(state="disabled")
            self.delete_button.configure(state="disabled")

    def validate_parameters(self) -> bool:
        """Controlla i parametri prima dell'esecuzione.

        Serve a evitare errori pericolosi o fuorvianti, per esempio:
        - passare una cartella a un comando che richiede un file;
        - passare un file a un comando che richiede una cartella;
        - lasciare vuoti campi obbligatori.
        """
        if not self.current_command:
            return False

        params = self.current_command.get("parametri", [])
        for p in params:
            name = p.get("nome")
            tipo = p.get("tipo", "testo")
            label = p.get("label", name)
            obbligatorio = p.get("obbligatorio", True)

            var = self.param_vars.get(name)
            if var is None:
                continue

            value = var.get().strip() if hasattr(var, "get") else ""
            expanded = Path(expand_path(value)) if value else None

            if obbligatorio and not value:
                messagebox.showerror("Parametro mancante", f"Il campo '{label}' è obbligatorio.")
                return False

            if tipo == "path_cartella":
                if not expanded.exists():
                    messagebox.showerror("Cartella non trovata", f"La cartella indicata non esiste:\n\n{value}")
                    return False
                if not expanded.is_dir():
                    messagebox.showerror("Parametro non valido", f"Il campo '{label}' richiede una cartella, ma hai selezionato un file:\n\n{value}")
                    return False

            if tipo == "path_file":
                if not expanded.exists():
                    messagebox.showerror("File non trovato", f"Il file indicato non esiste:\n\n{value}")
                    return False
                if expanded.is_dir():
                    messagebox.showerror(
                        "Parametro non valido",
                        f"Hai selezionato una cartella.\n\n"
                        f"Il comando richiede un file, per esempio un .command, .sh o script:\n\n{value}"
                    )
                    return False
                if not expanded.is_file():
                    messagebox.showerror("Parametro non valido", f"Il campo '{label}' richiede un file valido:\n\n{value}")
                    return False

        return True

    def values_for_template(self) -> dict[str, str]:
        values = {}
        for name, var in self.param_vars.items():
            raw_value = var.get()
            values[name] = shell_quote(raw_value)
        return values

    def build_command(self, mode: str | None = None) -> str:
        if not self.current_command:
            return ""

        if mode:
            modalita = self.current_command.get("modalita", {})
            template = modalita.get(mode, "")
        else:
            template = self.current_command.get("template", "")

        return template.format(**self.values_for_template())

    def build_count_command(self) -> str:
        """Comando opzionale per contare gli elementi analizzati.

        Usato soprattutto nei TRY/DELETE per mostrare:
        "15 trovati su 320 analizzati".
        """
        if not self.current_command:
            return ""

        conteggio = self.current_command.get("conteggio", {})
        template = conteggio.get("analizzati", "")
        if not template:
            return ""

        return template.format(**self.values_for_template())

    def update_preview(self):
        try:
            if self.is_try_delete_command():
                self.preview_var.set(self.build_command("try"))
            else:
                self.preview_var.set(self.build_command())
        except Exception as exc:
            self.preview_var.set(f"ERRORE ANTEPRIMA: {exc}")

    def copy_command(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.preview_var.get())

    def run_current(self):
        self.run_command(mode=None, label="RUN")

    def run_try(self):
        self.run_command(mode="try", label="TRY")

    def run_delete(self):
        if not self.current_command or not self.is_try_delete_command():
            return

        if not self.validate_parameters():
            return

        sig = self.current_signature()
        if self.last_try_signature != sig:
            messagebox.showerror(
                "DELETE bloccato",
                "Prima devi eseguire TRY con gli stessi parametri.\n\n"
                "Se hai cambiato cartella o filtro dopo il TRY, ripeti TRY."
            )
            return

        ok = messagebox.askyesno(
            "Conferma DELETE",
            "ATTENZIONE: questa operazione cancella davvero i file/cartelle trovati.\n\n"
            "Hai controllato l'elenco prodotto da TRY?\n\n"
            "Procedere con DELETE?"
        )
        if not ok:
            return

        self.run_command(mode="delete", label="DELETE")

    def run_command(self, mode: str | None = None, label: str = "RUN"):
        if self.current_process is not None:
            messagebox.showinfo("Comando in corso", "C'è già un comando in esecuzione. Usa STOP oppure attendi la fine.")
            return

        if not self.current_command:
            return

        if not self.validate_parameters():
            return

        try:
            cmd = self.build_command(mode)
        except Exception as exc:
            messagebox.showerror("Comando non valido", str(exc))
            return

        if not cmd or cmd.startswith("ERRORE"):
            messagebox.showerror("Comando non valido", cmd or "Comando vuoto")
            return

        rischio = self.current_command.get("rischio", "basso")
        if mode is None:
            if rischio in ("medio", "medio-basso"):
                if not messagebox.askyesno("Conferma", "Il comando modifica o crea file/cartelle. Eseguire?"):
                    return
            if rischio in ("alto", "pericoloso"):
                if not messagebox.askyesno("Conferma", "Comando ad alto rischio. Eseguire?"):
                    return

        started = time.time()
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        titolo = self.current_command.get("titolo", "")

        self.output.insert("end", "\n" + "─" * 72 + "\n", "separator")
        self.output.insert("end", f"[{stamp}] {label} — {titolo}\n", "run_header")
        self.output.insert("end", "$ " + cmd + "\n", "command")
        self.output.insert("end", "─" * 72 + "\n", "separator")
        self.output.insert("end", "[IN CORSO... output live attivo]\n", "status")
        self.output.see("end")
        self.root.update_idletasks()

        self.process_stop_requested = False
        self.current_process_label = label
        self.update_action_buttons()

        # Snapshot dati comando: se l'utente cambia selezione mentre il processo gira,
        # il thread deve comunque chiudere il comando corretto.
        command_snapshot = dict(self.current_command)
        signature_snapshot = self.current_signature()
        count_cmd = self.build_count_command()

        thread = threading.Thread(
            target=self._run_process_worker,
            args=(cmd, mode, label, started, command_snapshot, signature_snapshot, count_cmd),
            daemon=True,
        )
        thread.start()

    def _run_process_worker(self, cmd: str, mode: str | None, label: str, started: float, command_snapshot: dict, signature_snapshot: str, count_cmd: str = ""):
        stdout_chunks = []
        stderr_chunks = []
        returncode = None
        analyzed_count = None

        try:
            if count_cmd and mode in ("try", "delete"):
                self.root.after(0, self._append_output, "[Conteggio elementi analizzati...]\n", "status")
                try:
                    count_result = subprocess.run(
                        count_cmd,
                        shell=True,
                        cwd=str(DOC_IRC),
                        capture_output=True,
                        text=True,
                    )
                    raw_count = (count_result.stdout or "").strip()
                    if raw_count.isdigit():
                        analyzed_count = int(raw_count)
                except Exception:
                    analyzed_count = None

            # start_new_session=True crea un gruppo di processo separato.
            # Così STOP può terminare anche pipeline tipo "find ... | sort".
            proc = subprocess.Popen(
                cmd,
                shell=True,
                cwd=str(DOC_IRC),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            self.current_process = proc
            self.root.after(0, self.update_action_buttons)

            def read_stream(stream, tag, chunks):
                try:
                    for line in iter(stream.readline, ""):
                        chunks.append(line)
                        self.root.after(0, self._append_output, line, tag)
                finally:
                    try:
                        stream.close()
                    except Exception:
                        pass

            t_out = threading.Thread(target=read_stream, args=(proc.stdout, None, stdout_chunks), daemon=True)
            t_err = threading.Thread(target=read_stream, args=(proc.stderr, "stderr", stderr_chunks), daemon=True)
            t_out.start()
            t_err.start()

            returncode = proc.wait()
            t_out.join(timeout=1)
            t_err.join(timeout=1)

        except Exception as exc:
            self.root.after(0, self._append_output, f"\n[ERRORE] {exc}\n", "status")
            returncode = -999
        finally:
            elapsed = time.time() - started
            stdout = "".join(stdout_chunks)
            stderr = "".join(stderr_chunks)

            class SimpleResult:
                def __init__(self, stdout, stderr, returncode):
                    self.stdout = stdout
                    self.stderr = stderr
                    self.returncode = returncode

            result = SimpleResult(stdout, stderr, returncode)

            self.root.after(
                0,
                self._finish_process_ui,
                cmd,
                result,
                elapsed,
                mode,
                label,
                command_snapshot,
                signature_snapshot,
                analyzed_count,
            )

    def _append_output(self, text: str, tag: str | None = None):
        if tag:
            self.output.insert("end", text, tag)
        else:
            self.output.insert("end", text)
        self.output.see("end")

    def count_output_items(self, stdout: str) -> int:
        """Conta righe utili di stdout.

        Per i comandi basati su find, ogni riga corrisponde normalmente
        a un file o a una cartella trovata/cancellata.
        """
        if not stdout:
            return 0
        return len([line for line in stdout.splitlines() if line.strip()])

    def _finish_process_ui(self, cmd, result, elapsed, mode, label, command_snapshot, signature_snapshot, analyzed_count=None):
        stopped = self.process_stop_requested

        if result.returncode not in (0, None):
            if stopped:
                self.output.insert("end", f"\n[STOP: comando interrotto | exit={result.returncode} | {elapsed:.2f}s]\n", "status")
            else:
                self.output.insert("end", f"\n[ERRORE: exit={result.returncode} | {elapsed:.2f}s]\n", "status")

        # Log tecnico completo.
        self.write_log_for_command(command_snapshot, cmd, result, elapsed)

        item_count = self.count_output_items(result.stdout or "")

        analyzed_txt = ""
        if analyzed_count is not None:
            analyzed_txt = f" su {analyzed_count} analizzati"

        if mode == "try" and result.returncode == 0 and not stopped:
            self.last_try_signature = signature_snapshot
            self.delete_button.configure(state="normal")
            if item_count == 0:
                self.output.insert("end", f"\n[TRY completato: nessun elemento trovato{analyzed_txt}. DELETE non necessario]\n", "status")
                self.delete_button.configure(state="disabled")
            elif item_count == 1:
                self.output.insert("end", f"\n[TRY completato: 1 elemento trovato{analyzed_txt}. Se l'elenco è corretto, ora puoi usare DELETE]\n", "status")
            else:
                self.output.insert("end", f"\n[TRY completato: {item_count} elementi trovati{analyzed_txt}. Se l'elenco è corretto, ora puoi usare DELETE]\n", "status")

        if mode == "delete" and not stopped:
            self.last_try_signature = None
            self.delete_button.configure(state="disabled")
            if item_count == 0:
                self.output.insert("end", f"\n[DELETE completato: nessun elemento cancellato{analyzed_txt}]\n", "status")
            elif item_count == 1:
                self.output.insert("end", f"\n[DELETE completato: 1 elemento operato/cancellato{analyzed_txt}]\n", "status")
            else:
                self.output.insert("end", f"\n[DELETE completato: {item_count} elementi operati/cancellati{analyzed_txt}]\n", "status")

        if result.returncode == 0 and not stopped and mode not in ("try", "delete"):
            if item_count > 0:
                self.output.insert("end", f"\n[Comando completato: {item_count} righe di output]\n", "status")
            else:
                self.output.insert("end", "\n[Comando completato]\n", "status")

        self.current_process = None
        self.current_process_label = None
        self.process_stop_requested = False
        self.update_action_buttons()
        self.output.see("end")

    def stop_current_process(self):
        if self.current_process is None:
            return

        self.process_stop_requested = True
        self.output.insert("end", "\n[STOP richiesto: interrompo il comando in corso...]\n", "status")
        self.output.see("end")

        try:
            # Interrompe il gruppo di processo: utile per pipeline shell.
            os.killpg(os.getpgid(self.current_process.pid), signal.SIGTERM)
        except Exception:
            try:
                self.current_process.terminate()
            except Exception:
                pass

    def write_log(self, cmd: str, result: subprocess.CompletedProcess, elapsed: float):
        self.write_log_for_command(self.current_command or {}, cmd, result, elapsed)

    def write_log_for_command(self, command_data: dict, cmd: str, result, elapsed: float):
        ts = time.strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"TerminaleGuidato_{ts}.log"
        content = [
            f"Terminale Guidato {APP_VERSION}",
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Comando: {command_data.get('titolo', '')}",
            f"Rischio: {command_data.get('rischio', '')}",
            "",
            "$ " + cmd,
            "",
            "--- STDOUT ---",
            result.stdout or "",
            "--- STDERR ---",
            result.stderr or "",
            f"exit={result.returncode}",
            f"elapsed={elapsed:.2f}s",
        ]
        log_file.write_text("\n".join(content), encoding="utf-8")

    def show_help(self):
        if not self.current_command:
            return

        help_data = self.current_command.get("help", {})
        win = tk.Toplevel(self.root)
        win.title(f"Help — {self.current_command.get('titolo', '')}")
        win.geometry("820x620")

        text = tk.Text(win, wrap="word", font=("Helvetica", 13), padx=14, pady=14)
        text.pack(fill="both", expand=True)

        def add_heading(s):
            text.insert("end", s + "\n", ("h",))

        def add_body(s):
            if s:
                text.insert("end", s.strip() + "\n\n")

        text.tag_configure("h", font=("Helvetica", 16, "bold"))
        text.tag_configure("code", font=("Menlo", 12))

        add_heading(self.current_command.get("titolo", "Comando"))
        add_body(self.current_command.get("descrizione", ""))

        add_heading("Cosa fa")
        add_body(help_data.get("cosa_fa", "Help semplice non ancora compilato per questo comando."))

        add_heading("Quando usarlo")
        add_body(help_data.get("quando_usarlo", ""))

        add_heading("Attenzione")
        add_body(help_data.get("attenzione", ""))

        spiegazione = help_data.get("spiegazione_comando", [])
        if spiegazione:
            add_heading("Comando spiegato")
            for item in spiegazione:
                pezzo = item.get("pezzo", "")
                significato = item.get("significato", "")
                text.insert("end", f"• {pezzo}\n", ("code",))
                text.insert("end", f"  {significato}\n\n")

        esempi = help_data.get("esempi", [])
        if esempi:
            add_heading("Esempi")
            for ex in esempi:
                text.insert("end", f"• {ex}\n")
            text.insert("end", "\n")

        add_heading("Comando attuale")
        self.update_preview()
        text.insert("end", self.preview_var.get() + "\n", ("code",))
        text.configure(state="disabled")

    def show_man_page(self):
        if not self.current_command:
            return

        man_cmd = self.current_command.get("man")
        if not man_cmd:
            tmpl = self.current_command.get("template", "").strip()
            man_cmd = tmpl.split(" ", 1)[0] if tmpl else ""

        if not man_cmd:
            messagebox.showinfo("Manuale tecnico", "Nessun comando tecnico associato.")
            return

        cmd = f"man {shlex.quote(man_cmd)} | col -b"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        win = tk.Toplevel(self.root)
        win.title(f"Manuale tecnico — {man_cmd}")
        win.geometry("900x700")

        text = tk.Text(win, wrap="none", font=("Menlo", 11), padx=10, pady=10)
        text.pack(fill="both", expand=True)
        text.insert("end", result.stdout or result.stderr or f"Nessun manuale trovato per {man_cmd}")
        text.configure(state="disabled")


    def safe_exit(self):
        """Chiusura ordinata dell'applicazione.

        Per ora la pulizia consiste in:
        - svuotare la clipboard solo se non necessario? NO: la lasciamo intatta.
        - forzare aggiornamento UI
        - chiudere tutte le finestre figlie
        - distruggere root

        I log delle esecuzioni sono già stati scritti a ogni run.
        """
        try:
            for win in list(self.root.winfo_children()):
                # Non serve cancellare i widget singoli: distruggere root basta.
                pass
            self.save_state()
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            try:
                self.root.quit()
            except Exception:
                pass

    def copy_output(self):
        txt = self.output.get("1.0", "end").strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)

    def save_output(self):
        default = DOWNLOAD_DIR / f"TerminaleGuidato_output_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        path = filedialog.asksaveasfilename(
            title="Salva output",
            initialdir=str(DOWNLOAD_DIR),
            initialfile=default.name,
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
        )
        if path:
            Path(path).write_text(self.output.get("1.0", "end"), encoding="utf-8")


def main():
    root = tk.Tk()
    app = TerminaleGuidatoApp(root)
    root.protocol("WM_DELETE_WINDOW", app.safe_exit)
    root.mainloop()


if __name__ == "__main__":
    main()
