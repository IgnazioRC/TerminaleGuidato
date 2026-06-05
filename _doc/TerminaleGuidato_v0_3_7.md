# Terminale Guidato — v0.3.7 (Stable)

<!-- ChatGPT -->

## 1. Visione del progetto

Terminale Guidato nasce per risolvere un problema concreto:

❌ uso frammentato del terminale  
❌ dipendenza da copia/incolla (iClip)  
❌ comandi difficili da ricordare  
❌ rischio elevato di errori

✔ Soluzione:
interfaccia guidata → comandi strutturati → sicurezza → log

---

## 2. Obiettivi

- rendere il terminale **usabile senza memoria**
- trasformare i comandi in **operazioni parametrizzate**
- garantire **sicurezza operativa**
- mantenere **tracciabilità completa**

---

## 3. Architettura

### Struttura progetto

TerminaleGuidato/
- terminale_guidato.py
- config.json
- state.json
- build.json
- Commands/

### Filosofia

- codice → logica
- json → configurazione
- UI → esecuzione guidata

---

## 4. Interfaccia

### Flusso

1. selezione comando
2. inserimento parametri
3. anteprima
4. esecuzione
5. log

---

## 5. Sistema sicurezza

### Livelli

- basso → esecuzione diretta
- medio → conferma
- alto → TRY / DELETE

---

## 6. TRY / DELETE

### Flusso corretto

TRY:
- mostra elenco

DELETE:
- esegue realmente

### Protezioni

- firma parametri
- blocco DELETE senza TRY
- conferma finale

---

## 7. Conteggi avanzati

Output:

[TRY completato: 15 trovati su 320 analizzati]

Significato:

- trovati → impatto reale
- analizzati → scala operazione

---

## 8. Gestione processi

- subprocess.Popen
- thread dedicato
- STOP disponibile
- kill pipeline

---

## 9. Output

- separatori visivi
- comando evidenziato
- output live
- stato finale

---

## 10. Log

Salvati in:

~/Documents/log

Contengono:

- comando
- output
- errori
- tempo
- exit code

---

## 11. Comandi disponibili

### Analisi

- lista file
- ricerca
- conteggi
- file recenti/vecchi

### Navigazione

- apertura Finder
- dimensioni cartelle

### Operazioni

- zip
- chmod
- creazione cartelle

### Sicurezza

- cancellazioni TRY/DELETE

---

## 12. Limitazioni

- grep non legge PDF
- Spotlight dipende da indice
- conteggi rallentano su cartelle grandi

---

## 13. Filosofia finale

Terminale Guidato NON sostituisce Finder  
ma aggiunge:

✔ controllo  
✔ sicurezza  
✔ ripetibilità  

---

## 14. Stato

✔ stabile  
✔ utilizzabile  
✔ estendibile  

---

## 15. Ripartenza progetto

Per riprendere:

- questo file
- codice Python
- Commands/
- config.json

---

## 16. Tag

TerminaleGuidato macOS Python sicurezza TRY DELETE ChatGPT
