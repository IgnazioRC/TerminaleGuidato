# TerminaleGuidato — configurazioni migliorate

Data: 2026-05-07

Contenuto:
- 01_cerca_e_lista.json
- 02_cartelle_e_navigazione.json
- 03_operazioni_file_cartelle.json
- 04_cancellazioni_try_delete.json
- 05_python_e_venv.json

Modifiche principali:
- ottimizzati i comandi lenti con `find ... -ls` al posto di `find ... -exec ls ...`
- aggiunti comandi per duplicati per nome, grep semplice, spazio disco, albero cartelle limitato
- aggiunti comandi rapidi per aprire Dropbox IRC, download e log
- aggiunto comando rsync prudente senza `--delete`
- aggiunte cancellazioni TRY→DELETE per file `._*` e backup Python `*.bak.*`
- aggiunto `conferma_testuale: true` ai comandi distruttivi
- aggiunto nuovo file `05_python_e_venv.json`

Nota:
Questi JSON sono pronti da copiare nella cartella di configurazione di TerminaleGuidato.
