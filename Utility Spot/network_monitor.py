#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
network_monitor.py — Monitoraggio connettività sedi remote
Ignazio Rusconi-Clerici

Controlla la raggiungibilità delle sedi remote (Gignese, CCM, Punta Ala)
tramite ping agli IP fissi e invia notifiche email in caso di problemi.

Uso:
    python3 network_monitor.py                    # Esegue controllo una volta
    python3 network_monitor.py --test-email      # Invia email di test
    python3 network_monitor.py --status          # Mostra stato attuale
    python3 network_monitor.py --gui             # Apre interfaccia grafica

Struttura file:
    - Config/State: ~/Dropbox/Documenti_IRC/Python/_Config/
    - Log: ~/Dropbox/Documenti_IRC/Python/_Config/Logs/
"""

import json
import os
import sys
import subprocess
import smtplib
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

# --- IRC shared bootstrap ---
import sys as _sys
from pathlib import Path as _Path
if not getattr(_sys, 'frozen', False):
    _shared = _Path.home() / "Library/CloudStorage/Dropbox/Documenti_IRC/Python/shared"
    if str(_shared) not in _sys.path:
        _sys.path.insert(0, str(_shared))
# --- end IRC shared bootstrap ---

from irc_paths import app_config_dir

APP_NAME = "NetworkMonitor"

# Percorsi via irc_paths (usa _Config maiuscolo, cross-machine)
APP_SUPPORT_DIR = app_config_dir(APP_NAME)
LOG_DIR         = APP_SUPPORT_DIR / "Logs"

# Crea le cartelle se non esistono
LOG_DIR.mkdir(parents=True, exist_ok=True)

# File di configurazione e stato
CONFIG_FILE = APP_SUPPORT_DIR / "config.json"
STATE_FILE  = APP_SUPPORT_DIR / "state.json"
LOG_FILE    = LOG_DIR / "network_monitor.log"


def carica_config() -> dict:
    """Carica la configurazione da file JSON."""
    if not CONFIG_FILE.exists():
        print(f"ERRORE: File configurazione non trovato: {CONFIG_FILE}")
        sys.exit(1)
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def salva_stato(stato: dict):
    """Salva lo stato corrente (per notifica solo su cambiamenti)."""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(stato, f, indent=2, ensure_ascii=False)


def carica_stato() -> dict:
    """Carica lo stato precedente."""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def ping_host(ip: str, timeout: int = 10, tentativi: int = 3) -> Tuple[bool, float]:
    """
    Esegue ping a un host.
    Ritorna: (raggiungibile, tempo_medio_ms)
    """
    if not ip:
        return False, 0.0
    
    # Comando ping per macOS
    cmd = ['ping', '-c', str(tentativi), '-t', str(timeout), ip]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout * tentativi + 5
        )
        
        if result.returncode == 0:
            # Estrai tempo medio dal output
            # Esempio: "round-trip min/avg/max/stddev = 10.123/15.456/20.789/3.210 ms"
            for line in result.stdout.split('\n'):
                if 'avg' in line or 'media' in line:
                    parts = line.split('=')
                    if len(parts) >= 2:
                        times = parts[1].strip().split('/')
                        if len(times) >= 2:
                            try:
                                avg_time = float(times[1])
                                return True, avg_time
                            except ValueError:
                                pass
            return True, 0.0
        else:
            return False, 0.0
            
    except subprocess.TimeoutExpired:
        return False, 0.0
    except Exception as e:
        print(f"  Errore ping {ip}: {e}")
        return False, 0.0


def controlla_sedi(config: dict) -> Dict[str, dict]:
    """Controlla tutte le sedi attive."""
    risultati = {}
    
    timeout = config['controllo'].get('ping_timeout_secondi', 10)
    tentativi = config['controllo'].get('ping_tentativi', 3)
    
    for nome, sede in config['sedi'].items():
        if not sede.get('attivo', False):
            print(f"  {nome}: SKIP (non attivo)")
            continue
        
        ip = sede.get('ip', '')
        if not ip:
            print(f"  {nome}: SKIP (IP non configurato)")
            continue
        
        print(f"  {nome} ({ip})...", end=" ", flush=True)
        raggiungibile, tempo_ms = ping_host(ip, timeout, tentativi)
        
        risultati[nome] = {
            'ip': ip,
            'raggiungibile': raggiungibile,
            'tempo_ms': tempo_ms,
            'timestamp': datetime.now().isoformat(),
            'descrizione': sede.get('descrizione', '')
        }
        
        if raggiungibile:
            print(f"OK ({tempo_ms:.1f} ms)")
        else:
            print("NON RAGGIUNGIBILE ❌")
    
    return risultati


def invia_email(config: dict, oggetto: str, corpo: str) -> bool:
    """Invia email tramite Gmail SMTP."""
    email_cfg = config['email']
    
    try:
        msg = MIMEMultipart()
        msg['From'] = email_cfg['mittente']
        msg['To'] = email_cfg['destinatario']
        msg['Subject'] = oggetto
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        with smtplib.SMTP(email_cfg['smtp_server'], email_cfg['smtp_port']) as server:
            server.starttls()
            server.login(email_cfg['mittente'], email_cfg['password'])
            server.send_message(msg)
        
        return True
        
    except Exception as e:
        print(f"ERRORE invio email: {e}")
        return False


def genera_report(risultati: Dict[str, dict], problemi_nuovi: list, problemi_risolti: list) -> str:
    """Genera il corpo dell'email di report."""
    ora = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    linee = [
        f"Report Monitoraggio Rete - {ora}",
        "=" * 50,
        ""
    ]
    
    # Problemi nuovi
    if problemi_nuovi:
        linee.append("⚠️  NUOVI PROBLEMI:")
        for sede in problemi_nuovi:
            info = risultati.get(sede, {})
            linee.append(f"   • {sede} ({info.get('ip', '?')}) - NON RAGGIUNGIBILE")
        linee.append("")
    
    # Problemi risolti
    if problemi_risolti:
        linee.append("✅ PROBLEMI RISOLTI:")
        for sede in problemi_risolti:
            info = risultati.get(sede, {})
            linee.append(f"   • {sede} ({info.get('ip', '?')}) - Tornato online")
        linee.append("")
    
    # Stato completo
    linee.append("STATO ATTUALE:")
    for nome, info in risultati.items():
        stato = "✅ OK" if info['raggiungibile'] else "❌ OFFLINE"
        tempo = f" ({info['tempo_ms']:.1f} ms)" if info['raggiungibile'] and info['tempo_ms'] > 0 else ""
        linee.append(f"   • {nome}: {stato}{tempo}")
    
    linee.extend([
        "",
        "-" * 50,
        f"Monitoraggio automatico da {os.uname().nodename}"
    ])
    
    return "\n".join(linee)


def scrivi_log(config: dict, messaggio: str):
    """Scrive nel file di log."""
    max_righe = config['log'].get('max_righe', 1000)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{timestamp}] {messaggio}\n"
    
    # Leggi log esistente
    righe = []
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            righe = f.readlines()
    
    # Aggiungi nuova riga e tronca se necessario
    righe.append(linea)
    if len(righe) > max_righe:
        righe = righe[-max_righe:]
    
    # Scrivi
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.writelines(righe)


def esegui_controllo(config: dict, forza_notifica: bool = False):
    """Esegue il controllo completo."""
    print(f"\n{'='*50}")
    print(f"Controllo connettività - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print('='*50)
    
    # Controlla sedi
    risultati = controlla_sedi(config)
    
    if not risultati:
        print("Nessuna sede attiva da controllare.")
        return
    
    # Carica stato precedente
    stato_precedente = carica_stato()
    
    # Identifica cambiamenti
    problemi_nuovi = []
    problemi_risolti = []
    
    for nome, info in risultati.items():
        era_ok = stato_precedente.get(nome, {}).get('raggiungibile', True)
        ora_ok = info['raggiungibile']
        
        if era_ok and not ora_ok:
            problemi_nuovi.append(nome)
        elif not era_ok and ora_ok:
            problemi_risolti.append(nome)
    
    # Salva nuovo stato
    salva_stato(risultati)
    
    # Log
    sedi_ok = sum(1 for r in risultati.values() if r['raggiungibile'])
    sedi_tot = len(risultati)
    scrivi_log(config, f"Controllo: {sedi_ok}/{sedi_tot} sedi online" + 
               (f" | Nuovi problemi: {problemi_nuovi}" if problemi_nuovi else "") +
               (f" | Risolti: {problemi_risolti}" if problemi_risolti else ""))
    
    # Notifica email
    notifica_solo_cambiamenti = config['controllo'].get('notifica_solo_cambiamenti', True)
    
    deve_notificare = forza_notifica or problemi_nuovi or problemi_risolti
    if notifica_solo_cambiamenti and not deve_notificare:
        print("\nNessun cambiamento, email non inviata.")
        return
    
    if problemi_nuovi or problemi_risolti or forza_notifica:
        print("\nInvio notifica email...", end=" ")
        
        if problemi_nuovi:
            oggetto = f"⚠️ RETE: {', '.join(problemi_nuovi)} non raggiungibile"
        elif problemi_risolti:
            oggetto = f"✅ RETE: {', '.join(problemi_risolti)} tornato online"
        else:
            oggetto = f"📊 Report rete: {sedi_ok}/{sedi_tot} sedi online"
        
        corpo = genera_report(risultati, problemi_nuovi, problemi_risolti)
        
        if invia_email(config, oggetto, corpo):
            print("OK ✓")
            scrivi_log(config, f"Email inviata: {oggetto}")
        else:
            print("ERRORE ✗")
            scrivi_log(config, "ERRORE invio email")


def test_email(config: dict):
    """Invia un'email di test."""
    print("Invio email di test...", end=" ", flush=True)
    
    oggetto = "🧪 Test Network Monitor"
    corpo = f"""Questo è un messaggio di test dal Network Monitor.

Data/ora: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
Eseguito da: {os.uname().nodename}

Se ricevi questa email, la configurazione è corretta!

Sedi configurate:
"""
    config_data = carica_config()
    for nome, sede in config_data['sedi'].items():
        stato = "attivo" if sede.get('attivo') else "non attivo"
        corpo += f"  • {nome}: {sede.get('ip', 'N/A')} ({stato})\n"
    
    if invia_email(config, oggetto, corpo):
        print("OK ✓")
        print("Controlla la tua casella email!")
    else:
        print("ERRORE ✗")


def mostra_stato(config: dict):
    """Mostra lo stato attuale senza inviare notifiche."""
    print("\nStato attuale delle sedi:")
    print("-" * 40)
    
    stato = carica_stato()
    
    if not stato:
        print("Nessun controllo ancora eseguito.")
        print("Esegui: python3 network_monitor.py")
        return
    
    for nome, info in stato.items():
        stato_txt = "✅ Online" if info.get('raggiungibile') else "❌ Offline"
        tempo = info.get('tempo_ms', 0)
        tempo_txt = f" ({tempo:.1f} ms)" if tempo > 0 else ""
        ultimo = info.get('timestamp', 'N/A')
        if ultimo != 'N/A':
            try:
                dt = datetime.fromisoformat(ultimo)
                ultimo = dt.strftime("%d/%m %H:%M")
            except:
                pass
        
        print(f"  {nome}: {stato_txt}{tempo_txt} - ultimo check: {ultimo}")


def gui_monitor(config: dict):
    """Interfaccia grafica semplice per il monitor."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        print("ERRORE: tkinter non disponibile")
        return
    
    class NetworkMonitorGUI:
        def __init__(self, config):
            self.config = config
            self.root = tk.Tk()
            self.root.title("Network Monitor")
            self.root.geometry("500x400")
            self.setup_ui()
        
        def setup_ui(self):
            # Frame principale
            main_frame = ttk.Frame(self.root, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Titolo
            ttk.Label(main_frame, text="Monitoraggio Sedi Remote", 
                     font=('Helvetica', 16, 'bold')).pack(pady=(0, 10))
            
            # Frame sedi
            self.sedi_frame = ttk.LabelFrame(main_frame, text="Stato Sedi", padding="10")
            self.sedi_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            self.labels_stato = {}
            for nome, sede in self.config['sedi'].items():
                frame = ttk.Frame(self.sedi_frame)
                frame.pack(fill=tk.X, pady=2)
                
                ttk.Label(frame, text=f"{nome}:", width=12).pack(side=tk.LEFT)
                
                ip = sede.get('ip', 'N/A')
                attivo = sede.get('attivo', False)
                
                if attivo and ip:
                    stato_label = ttk.Label(frame, text="⏳ In attesa...", width=20)
                else:
                    stato_label = ttk.Label(frame, text="⚪ Non attivo", width=20)
                stato_label.pack(side=tk.LEFT)
                
                ttk.Label(frame, text=f"({ip})" if ip else "(N/A)").pack(side=tk.LEFT)
                
                self.labels_stato[nome] = stato_label
            
            # Pulsanti
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=10)
            
            ttk.Button(btn_frame, text="🔄 Controlla Ora", 
                      command=self.controlla).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="📧 Test Email", 
                      command=self.test_email).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="📋 Apri Log", 
                      command=self.apri_log).pack(side=tk.LEFT, padx=5)
            
            # Stato
            self.status_var = tk.StringVar(value="Pronto")
            ttk.Label(main_frame, textvariable=self.status_var).pack(pady=5)
        
        def controlla(self):
            self.status_var.set("Controllo in corso...")
            self.root.update()
            
            risultati = controlla_sedi(self.config)
            
            for nome, info in risultati.items():
                if nome in self.labels_stato:
                    if info['raggiungibile']:
                        tempo = info.get('tempo_ms', 0)
                        self.labels_stato[nome].config(
                            text=f"✅ Online ({tempo:.0f}ms)")
                    else:
                        self.labels_stato[nome].config(text="❌ Offline")
            
            self.status_var.set(f"Ultimo controllo: {datetime.now().strftime('%H:%M:%S')}")
        
        def test_email(self):
            self.status_var.set("Invio email di test...")
            self.root.update()
            test_email(self.config)
            self.status_var.set("Email di test inviata")
        
        def apri_log(self):
            if LOG_FILE.exists():
                subprocess.run(['open', str(LOG_FILE)])
            else:
                messagebox.showinfo("Log", "Nessun file di log ancora creato")
        
        def run(self):
            self.root.mainloop()
    
    app = NetworkMonitorGUI(config)
    app.run()


def main():
    parser = argparse.ArgumentParser(
        description="Monitoraggio connettività sedi remote",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python3 network_monitor.py                 # Esegue controllo
  python3 network_monitor.py --test-email    # Invia email di test
  python3 network_monitor.py --status        # Mostra stato
  python3 network_monitor.py --gui           # Interfaccia grafica
        """
    )
    
    parser.add_argument('--test-email', action='store_true',
                       help='Invia email di test per verificare configurazione')
    parser.add_argument('--status', action='store_true',
                       help='Mostra stato attuale delle sedi')
    parser.add_argument('--gui', action='store_true',
                       help='Apri interfaccia grafica')
    parser.add_argument('--forza-notifica', action='store_true',
                       help='Invia notifica anche senza cambiamenti')
    
    args = parser.parse_args()
    
    # Carica configurazione
    config = carica_config()
    
    if args.test_email:
        test_email(config)
    elif args.status:
        mostra_stato(config)
    elif args.gui:
        gui_monitor(config)
    else:
        esegui_controllo(config, forza_notifica=args.forza_notifica)


if __name__ == "__main__":
    main()
