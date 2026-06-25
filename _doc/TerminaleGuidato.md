# Terminale Guidato

**`terminale_guidato.py` — Documentazione tecnica**

---

## Descrizione

Terminale Guidato è un'interfaccia grafica macOS per l'esecuzione guidata di comandi da terminale. Trasforma comandi complessi in operazioni parametrizzate con anteprima, conferma e log automatico.

Nasce per risolvere tre problemi concreti:
- comandi difficili da ricordare e da digitare correttamente
- rischio elevato di errori su operazioni distruttive
- nessuna tracciabilità delle operazioni eseguite

---

## Requisiti

Nessuna dipendenza esterna oltre alla libreria standard Python. Richiede `path_widgets.py` dal modulo condiviso IRC:

```
~/Library/CloudStorage/Dropbox/Documenti_IRC/Python/shared/path_widgets.py
```

Per lanciare:

```bash
pystable
python3 ".../Terminale guidato/terminale_guidato.py"
```

---

## Architettura

```
Terminale guidato/
├── terminale_guidato.py        ← applicativo principale
├── _Config/TerminaleGuidato/
│   ├── config.json             ← indice dei file comandi
│   ├── state.json              ← stato persistente (ultima cartella, ultimi Combobox)
│   └── Commands/
│       ├── 01_cerca_e_lista.json
│       ├── 02_cartelle_e_navigazione.json
│       ├── 03_operazioni_file_cartelle.json
│       ├── 04_cancellazioni_try_delete.json
│       ├── 05_python_e_venv.json
│       ├── 06_git.json
│       ├── 07_git_remoto.json
│       └── 08_rete_e_remoto.json
└── _doc/
    └── TerminaleGuidato.md     ← questo file
```

### Filosofia

- **codice** → logica dell'applicativo
- **JSON** → configurazione dei comandi (nessuna modifica al codice per aggiungere comandi)
- **UI** → esecuzione guidata e sicura

---

## Configurazione

### config.json

Indice modulare dei file comandi. Formato:

```json
{
  "version": "0.3.9",
  "config_format": "modular",
  "commands_dir": "Commands",
  "command_files": [
    "01_cerca_e_lista.json",
    "06_git.json",
    "07_git_remoto.json"
  ]
}
```

Per aggiungere una nuova categoria: creare il file JSON in `Commands/` e aggiungere il nome alla lista `command_files`.

### Struttura di un file comandi

```json
{
  "nome": "Nome categoria",
  "comandi": [
    {
      "id": "identificativo_unico",
      "titolo": "Titolo visualizzato",
      "descrizione": "Breve descrizione",
      "rischio": "basso | medio | alto",
      "man": "comando_unix",
      "ambito": "contesto operativo",
      "template": "comando {parametro1} {parametro2}",
      "parametri": [...],
      "help": {...}
    }
  ]
}
```

---

## Tipi di parametro

| Tipo | Widget | Uso |
|------|--------|-----|
| `testo` | Campo di testo libero | Stringhe brevi, pattern, nomi file |
| `testo_lungo` | Area di testo multiriga con scrollbar | Messaggi commit, testi lunghi |
| `path_cartella` | Campo + pulsante Sfoglia | Percorsi cartella |
| `path_file` | Campo + pulsante Scegli | Percorsi file |
| `booleano` | Checkbox | Flag on/off |
| `scelta` | Menu a tendina (Combobox) | Lista di opzioni predefinite nel JSON |
| `scelta_dinamica` | Menu a tendina popolato a runtime | Valori noti solo a runtime (es. IP Tailscale) |

### Esempio parametro `scelta`

```json
{
  "nome": "percorso_repo",
  "label": "Repo",
  "tipo": "scelta",
  "default": "_iot_casa/Letture Consumi Energia Elettrica",
  "obbligatorio": true,
  "opzioni": [
    "_finance/SpeseFamiglia.CLD",
    "_photo/PhotoComposer.CLD",
    "_utility/Terminale guidato"
  ]
}
```

### Esempio parametro `scelta_dinamica`

```json
{
  "nome": "ip_remoto",
  "label": "IP Tailscale del Mac remoto",
  "tipo": "scelta_dinamica",
  "sorgente": "tailscale_peers",
  "obbligatorio": true
}
```

Prima che la sorgente sia disponibile, il campo mostra un testo libero con avviso arancione. Dopo l'esecuzione del comando di inizializzazione, il Combobox si popola automaticamente.

---

## Livelli di rischio

| Livello | Comportamento |
|---------|--------------|
| `basso` | Esecuzione diretta senza conferma |
| `medio` | Finestra di conferma prima dell'esecuzione |
| `alto` | Flusso TRY → DELETE obbligatorio |

---

## Flusso TRY / DELETE

Per i comandi distruttivi (cancellazioni, sovrascritture) è disponibile un flusso a due fasi:

1. **TRY** — esegue il comando in modalità simulazione, mostra l'elenco degli elementi che verrebbero impattati senza toccare nulla
2. **DELETE** — esegue realmente l'operazione, disponibile solo dopo un TRY con gli stessi parametri

Protezioni:
- il DELETE è bloccato se i parametri sono cambiati dopo il TRY
- firma dei parametri verificata prima di ogni DELETE
- conferma testuale opzionale per i comandi più critici

Output TRY:
```
[TRY completato: 15 trovati su 320 analizzati]
```

---

## Categorie di comandi disponibili

| File | Contenuto |
|------|-----------|
| `01_cerca_e_lista.json` | Ricerca file, grep, lista file recenti/vecchi, duplicati |
| `02_cartelle_e_navigazione.json` | Dimensioni cartelle, apertura Finder, albero directory |
| `03_operazioni_file_cartelle.json` | Zip, chmod, copia, creazione cartelle, rsync |
| `04_cancellazioni_try_delete.json` | Cancellazioni sicure TRY→DELETE (file `._*`, backup `.bak.*`, ecc.) |
| `05_python_e_venv.json` | Gestione venv, pip, esecuzione script Python |
| `06_git.json` | Comandi Git locali (status, log, commit, push, reset) |
| `07_git_remoto.json` | Commit e push su iMac BdS via SSH remoto |
| `08_rete_e_remoto.json` | Ping, SSH, Tailscale, rete |

---

## Categoria Git remoto (07_git_remoto.json)

Categoria dedicata alle operazioni Git su iMac BdS da MacBook o Gignese. Tutti i comandi si connettono via SSH a `ignazio@100.127.196.96` (Tailscale) e stampano `hostname` come prima istruzione per conferma visiva della macchina remota.

### Prerequisito

La chiave SSH del Mac locale deve essere registrata su BdS. Configurata su MacBook il 24/06/2026 con:

```bash
ssh-keygen -t ed25519 -C "ignazio@macbook"
cat ~/.ssh/id_ed25519.pub | ssh ignazio@100.127.196.96 \
  "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### Comandi disponibili

| Comando | Descrizione | Rischio |
|---------|-------------|---------|
| **Status remoto** | `git status` sul repo selezionato | basso |
| **Log remoto** | Ultimi N commit in formato compatto | basso |
| **Commit + Push remoto** | `git add + commit + push` in un solo comando | medio |

### Flusso consigliato a fine sessione

1. **Status remoto** → verificare cosa è modificato
2. **Commit + Push remoto** → selezionare repo, specificare file e messaggio
3. **Log remoto** → confermare che il commit è arrivato

### Perché SSH e non operare direttamente

I file sono su Dropbox, quindi fisicamente identici su tutti i Mac. Il repo Git però esiste **solo su iMac BdS** (con `.git` escluso da Dropbox tramite `com.dropbox.ignored`). Il commit deve quindi essere eseguito da BdS — SSH è il modo per farlo senza aprire lo schermo condiviso, che con connessioni lente (es. Punta Ala) sarebbe troppo lento.

### Note operative

- Il parametro **Repo** è un menu a tendina con tutti i 21 repo dell'ecosistema IRC
- Il parametro **File** accetta `.` per aggiungere tutto il modificato, o nomi specifici separati da spazio
- Il messaggio commit non può contenere apici singoli `'`
- Per sessioni che toccano più repo: ripetere il comando Commit + Push una volta per repo

---

## Categoria Rete e Mac remoti (08_rete_e_remoto.json)

Categoria per operazioni di rete e accesso remoto via Tailscale. Usa il tipo `scelta_dinamica` per i parametri IP — il Combobox si popola automaticamente dopo aver eseguito **Stato Tailscale**.

### Flusso obbligatorio

1. **Stato Tailscale** → rileva i Mac online e popola i Combobox IP di tutti gli altri comandi
2. Selezionare il Mac dal Combobox ed eseguire il comando desiderato

### Comandi disponibili

| Comando | Descrizione | Rischio |
|---------|-------------|---------|
| **Stato Tailscale** | Lista Mac connessi con IP e stato | basso |
| **Connetti via SSH** | Apre sessione SSH sul Mac selezionato | medio |
| **Copia file config** | Copia un file locale su Mac remoto via SCP | medio-basso |
| **Ping Mac remoto** | Verifica raggiungibilità | basso |

### Note operative

- Solo i Mac con sistema operativo macOS appaiono nel Combobox — iPad e iPhone vengono esclusi automaticamente perché iOS blocca SSH e ping
- Il MacBook Pro locale appare nella lista ma connettersi a se stessi via SSH è inutile
- Se Tailscale non è attivo o il comando fallisce, i parametri IP restano come campo testo libero con avviso arancione

---

## Output e log

Ogni esecuzione produce:
- output live nella finestra dell'applicativo
- intestazione con nome comando, rischio e comando tecnico eseguito
- file di log in `~/Documents/log/TerminaleGuidato/<timestamp>.log`

Il log contiene: comando eseguito, stdout, stderr, exit code, tempo di esecuzione.

---

## Build come applicativo macOS

| Campo AppBuilder | Valore |
|------------------|--------|
| Cartella script | `…/Terminale guidato/` |
| Python builder | `~/Python_venv/stable/bin/python3` |
| Installa in | `/Applications/Python Apps` |
| Hidden imports | — |
| Windowed | ✅ |

---

## Note e limitazioni

- `grep` non legge file PDF
- Spotlight dipende dall'indice macOS, può essere incompleto su volumi esterni
- I conteggi rallentano su cartelle con molti file (decine di migliaia)
- Il comando SSH remoto richiede che iMac BdS sia acceso e raggiungibile via Tailscale
- Su connessioni lente (es. Punta Ala) l'output SSH può avere latenza — normale, non è un errore
