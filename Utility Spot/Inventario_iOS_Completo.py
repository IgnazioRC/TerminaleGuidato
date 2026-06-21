#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inventario_iOS_Completo_1.1
Analisi completa di iPhone/iPad collegati via USB (libimobiledevice)
Output: file Excel con hardware, software, rete, app e backup info.
Autore: Ignazio Rusconi-Clerici
Data: 2026-04-08
"""

import os
import sys
import plistlib
import shlex
import getpass
import subprocess
from datetime import datetime
import pandas as pd

# --- Impostazioni base ---
BASE_DOWNLOAD_DIR = os.path.expanduser("~/Documents/download")
BASE_LOG_DIR = os.path.expanduser("~/Documents/log")
TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def make_output_paths(device_name: str):
    """Costruisce i percorsi di output usando il nome del dispositivo."""
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in device_name).strip()
    safe_name = safe_name or "iOS_Device"
    base = f"{safe_name}_{TIMESTAMP}"
    return (os.path.join(BASE_DOWNLOAD_DIR, f"{base}.xlsx"),
            os.path.join(BASE_LOG_DIR,      f"{base}.log"))

# --- Utility di sistema ---
def find_tool(name):
    """Cerca un tool nel PATH e nei percorsi noti di Homebrew (Apple Silicon e Intel).
    Necessario perché i tool lanciati da app/script non ereditano il PATH completo della shell.
    Restituisce il path completo o None."""
    import shutil
    found = shutil.which(name)
    if found:
        return found
    for prefix in ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]:
        candidate = f"{prefix}/{name}"
        from pathlib import Path as _P
        if _P(candidate).is_file():
            return candidate
    return None

def cmd_exists(cmd):
    return find_tool(cmd) is not None

def run(cmd, timeout=30):
    """Esegue un comando shell e ritorna (rc, out, err) in stringa.
    Risolve automaticamente i tool nel PATH Homebrew anche da ambienti senza PATH completo."""
    if isinstance(cmd, list) and cmd:
        resolved = find_tool(cmd[0])
        if resolved:
            cmd = [resolved] + cmd[1:]
    try:
        p = subprocess.run(
            cmd if isinstance(cmd, list) else shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Timeout dopo {timeout}s"

def need_tools_or_exit():
    missing = []
    for tool in ["idevice_id", "ideviceinfo", "idevicediagnostics", "ideviceinstaller"]:
        if not cmd_exists(tool):
            missing.append(tool)
    if missing:
        print("❌ Mancano strumenti:", ", ".join(missing))
        print("Installa con:")
        print("  brew install libimobiledevice")
        print("  brew install ideviceinstaller")
        print("Nota: ifuse non è richiesto per questa procedura su macOS.")
        sys.exit(1)

def parse_keyval(text):
    """Converte blocchi 'Chiave: Valore' in dict."""
    d = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
    return d

def safe_get(d, *keys, default=""):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default

def friendly_bytes(n):
    try:
        n = int(n)
    except Exception:
        return ""
    gb = n / (1024 ** 3)
    return f"{gb:.2f} GB"

def ensure_output_dirs():
    os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(BASE_LOG_DIR, exist_ok=True)

def write_text_log(lines, path):
    ensure_output_dirs()
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

# --- Raccolta dispositivi ---
def list_devices():
    rc, out, err = run(["idevice_id", "-l"])
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]

def check_trust_problem(stderr_text):
    hints = ["Could not connect", "No device found", "Please unlock", "Pairing failed", "InvalidHostID"]
    return any(h in stderr_text for h in hints)

# --- Info generali + storage ---
def collect_general_info(udid):
    rc, out, err = run(["ideviceinfo", "-u", udid])
    data = parse_keyval(out) if rc == 0 else {}

    if not any(k in data for k in ["TotalDiskCapacity", "TotalDataCapacity"]):
        for section in ["com.apple.disk_usage", "com.apple.mobile.storage"]:
            rc2, out2, err2 = run(["ideviceinfo", "-u", udid, "-q", section])
            if rc2 == 0 and out2.strip():
                data.update(parse_keyval(out2))

    if not data.get("Language") or not data.get("Locale"):
        rc3, out3, err3 = run(["ideviceinfo", "-u", udid, "-q", "com.apple.mobile.internal"])
        if rc3 == 0 and out3.strip():
            data.update(parse_keyval(out3))
    return data, err

def collect_battery(udid):
    rc, out, err = run(["ideviceinfo", "-u", udid, "-q", "com.apple.mobile.battery"])
    if rc != 0:
        return {}, err
    return parse_keyval(out), ""

# --- App installate ---
def _parse_apps_from_plist(xml_text, udid):
    apps = []
    parsed = plistlib.loads(xml_text.encode("utf-8"))
    if isinstance(parsed, dict):
        candidate_lists = []
        if "apps" in parsed and isinstance(parsed["apps"], list):
            candidate_lists.append(parsed["apps"])
        for value in parsed.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                candidate_lists.append(value)
        if not candidate_lists:
            candidate_lists.append([])
        raw_apps = candidate_lists[0]
    elif isinstance(parsed, list):
        raw_apps = parsed
    else:
        raw_apps = []

    for app in raw_apps:
        if not isinstance(app, dict):
            continue
        apps.append({
            "UDID": udid,
            "BundleID": app.get("CFBundleIdentifier", ""),
            "Versione": app.get("CFBundleShortVersionString", app.get("CFBundleVersion", "")),
            "NomeApp": app.get("CFBundleDisplayName", app.get("CFBundleName", "")),
        })
    return apps

def _parse_apps_from_text(text, udid):
    apps = []
    for line in text.splitlines():
        line = line.strip()
        if not line or " - " not in line:
            continue
        parts = [p.strip() for p in line.split(" - ")]
        apps.append({
            "UDID": udid,
            "BundleID": parts[0] if len(parts) > 0 else "",
            "Versione": parts[1] if len(parts) > 1 else "",
            "NomeApp": parts[2] if len(parts) > 2 else "",
        })
    return apps

def list_apps(udid):
    """
    Recupera elenco app con versione e nome.
    Prova prima la sintassi nuova di ideviceinstaller 1.2.x, poi fallback legacy.
    """
    commands = [
        ["ideviceinstaller", "-u", udid, "list", "--xml"],
        ["ideviceinstaller", "-u", udid, "list"],
        ["ideviceinstaller", "-u", udid, "-l", "-o", "xml"],
        ["ideviceinstaller", "-u", udid, "-l"],
    ]

    errors = []
    for cmd in commands:
        rc, out, err = run(cmd, timeout=120)
        if rc != 0 or not out.strip():
            if err:
                errors.append(f"{' '.join(cmd)} -> {err}")
            continue
        try:
            if "--xml" in cmd or ("-o" in cmd and "xml" in cmd):
                apps = _parse_apps_from_plist(out, udid)
            else:
                apps = _parse_apps_from_text(out, udid)
            if apps:
                return apps, ""
        except Exception as ex:
            errors.append(f"{' '.join(cmd)} -> Errore parsing: {ex}")

    return [], " | ".join(errors) if errors else "Nessuna app rilevata"

# --- Pipeline per dispositivo ---
def harvest_for_device(udid):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gen, gen_err = collect_general_info(udid)
    if gen_err and check_trust_problem(gen_err):
        raise RuntimeError("Problema di autorizzazione/trust. Sblocca il dispositivo e tocca 'Autorizza'.")

    bat, bat_err = collect_battery(udid)
    apps, apps_err = list_apps(udid)

    tot = safe_get(gen, "TotalDiskCapacity", "TotalDataCapacity", default="")
    free = safe_get(gen, "TotalDataAvailable", default="")
    try:
        tot_f = float(tot)
        free_f = float(free)
        perc = round(100 * (1 - free_f / tot_f), 1) if tot_f else ""
    except Exception:
        perc = ""

    device_row = {
        "UDID": udid,
        "NomeDispositivo": safe_get(gen, "DeviceName"),
        "TipoProdotto": safe_get(gen, "ProductType"),
        "Modello": safe_get(gen, "ProductType"),
        "Versione_iOS": safe_get(gen, "ProductVersion"),
        "Build": safe_get(gen, "BuildVersion"),
        "NumeroModello": safe_get(gen, "ModelNumber"),
        "NumeroSerie": safe_get(gen, "SerialNumber"),
        "CapacitaTotale": friendly_bytes(tot),
        "SpazioDisponibile": friendly_bytes(free),
        "Occupato_%": perc,
        "Configurato": safe_get(gen, "ActivationState"),
        "DataRilevazione": now_str,
        "UtenteMac": getpass.getuser(),
    }

    battery_row = {
        "UDID": udid,
        "BatteryLevel(%)": safe_get(bat, "BatteryCurrentCapacity"),
        "StateCarica": safe_get(bat, "BatteryIsCharging"),
        "EsternoCollegato": safe_get(bat, "ExternalConnected"),
        "CapacitaMassima?": safe_get(bat, "FullyCharged"),
        "DataRilevazione": now_str,
    }

    storage_row = {
        "UDID": udid,
        "Totale": friendly_bytes(tot),
        "Disponibile": friendly_bytes(free),
        "Occupato_%": perc,
        "FileSystem": safe_get(gen, "FileSystemType", "FileSystem"),
        "DataRilevazione": now_str,
    }

    network_row = {
        "UDID": udid,
        "WiFiAddress": safe_get(gen, "WiFiAddress"),
        "BluetoothAddress": safe_get(gen, "BluetoothAddress"),
        "BasebandVersion": safe_get(gen, "BasebandVersion"),
        "CarrierBundleVersion": safe_get(gen, "CarrierBundleVersion"),
        "DataRilevazione": now_str,
    }

    backup_row = {
        "UDID": udid,
        "iTunesStoreAccountHash": safe_get(gen, "iTunesStoreAccountHash"),
        "iTunesHasConnected": safe_get(gen, "iTunesHasConnected"),
        "InternationalMobileEquipmentIdentity": safe_get(gen, "InternationalMobileEquipmentIdentity"),
        "TimeZone": safe_get(gen, "TimeZone"),
        "Language": safe_get(gen, "Language"),
        "Locale": safe_get(gen, "Locale"),
        "DataRilevazione": now_str,
    }

    return (
        [device_row], [battery_row], [storage_row], [network_row], [backup_row], apps,
        {"general_err": gen_err, "battery_err": bat_err, "apps_err": apps_err}
    )

# --- Excel ---
def write_excel(sheets_dict, path):
    ensure_output_dirs()
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        for sheet_name, df in sheets_dict.items():
            if df is None or df.empty:
                pd.DataFrame({"(vuoto)": []}).to_excel(writer, index=False, sheet_name=sheet_name)
            else:
                df.to_excel(writer, index=False, sheet_name=sheet_name)
        for sheet_name, df in sheets_dict.items():
            ws = writer.sheets[sheet_name]
            try:
                columns = df.columns if df is not None and not df.empty else ["(vuoto)"]
                for i, col in enumerate(columns):
                    width = 12
                    if df is not None and not df.empty and col in df.columns:
                        width = min(50, max(12, int(df[col].astype(str).str.len().quantile(0.9)) + 2))
                    ws.set_column(i, i, width)
            except Exception:
                pass

# --- Main ---
def main():
    print("🔎 Inventario iOS 1.1 — avvio...")
    print("📱 Assicurati che il dispositivo iOS sia:")
    print("   • collegato via USB")
    print("   • sbloccato (schermata Home visibile)")
    print("   • che abbia già confermato 'Autorizza questo computer' in passato")
    print()
    need_tools_or_exit()
    ensure_output_dirs()

    print("🔍 Ricerca dispositivi connessi...", flush=True)
    devices = list_devices()
    if not devices:
        print("⚠️ Nessun dispositivo iOS rilevato.")
        print("   Verifica che il cavo sia collegato e il telefono sbloccato.")
        sys.exit(2)

    print(f"✅ Dispositivi rilevati: {len(devices)}")

    all_device_rows = []
    all_battery_rows = []
    all_storage_rows = []
    all_network_rows = []
    all_backup_rows = []
    all_apps_rows = []
    errs = []

    # Nome dispositivo per il file di output (usa il primo dispositivo trovato)
    first_name = "iOS_Device"
    if devices:
        try:
            import subprocess as _sp
            _rc, _out, _ = run(["ideviceinfo", "-u", devices[0]])
            for _line in _out.splitlines():
                if _line.startswith("DeviceName:"):
                    first_name = _line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass
    OUTPUT_XLSX, OUTPUT_LOG = make_output_paths(first_name)

    log_lines = [
        "Inventario_iOS_Completo_1.1",
        f"Data esecuzione: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Utente Mac: {getpass.getuser()}",
        f"Excel output: {OUTPUT_XLSX}",
        f"Log output: {OUTPUT_LOG}",
        "",
        f"Dispositivi rilevati: {len(devices)}",
    ]

    for udid in devices:
        print(f"→ Raccolgo dati per UDID: {udid}", flush=True)
        log_lines.append(f"UDID: {udid}")
        try:
            print("   📋 Info generali e storage...", flush=True)
            print("   🔋 Batteria...", flush=True)
            print("   📱 App installate (può richiedere qualche secondo)...", flush=True)
            d, b, s, n, bk, apps, e = harvest_for_device(udid)
            all_device_rows.extend(d)
            all_battery_rows.extend(b)
            all_storage_rows.extend(s)
            all_network_rows.extend(n)
            all_backup_rows.extend(bk)
            all_apps_rows.extend(apps)

            for k, v in e.items():
                if v:
                    errs.append({"UDID": udid, "Sezione": k, "Messaggio": v})
                    log_lines.append(f"  ERRORE [{k}] {v}")

            log_lines.append(f"  App rilevate: {len(apps)}")
        except Exception as ex:
            errs.append({"UDID": udid, "Sezione": "generale", "Messaggio": str(ex)})
            log_lines.append(f"  ERRORE [generale] {ex}")

    print("💾 Scrittura report Excel...", flush=True)
    sheets = {
        "Dispositivi": pd.DataFrame(all_device_rows),
        "Batteria": pd.DataFrame(all_battery_rows),
        "Storage": pd.DataFrame(all_storage_rows),
        "Rete": pd.DataFrame(all_network_rows),
        "BackupSync": pd.DataFrame(all_backup_rows),
        "AppInstallate": pd.DataFrame(all_apps_rows),
        "LogErrori": pd.DataFrame(errs),
    }

    write_excel(sheets, OUTPUT_XLSX)
    write_text_log(log_lines, OUTPUT_LOG)

    print(f"📄 File Excel generato: {OUTPUT_XLSX}")
    print(f"📝 File log generato: {OUTPUT_LOG}")

    if errs:
        print("⚠️ Alcune sezioni hanno riportato errori:")
        for e in errs:
            print(f"   - {e['UDID']} | {e['Sezione']} | {e['Messaggio']}")
        print("Vedi anche il foglio LogErrori nel file Excel.")
    print("✅ Completato.")
    import subprocess
    subprocess.run(["open", OUTPUT_XLSX])

if __name__ == "__main__":
    main()
