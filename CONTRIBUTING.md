# Reguli de lucru în depozitul echipei

Aceste reguli sunt evaluate: verificările automate din `.github/workflows/` și scriptul titularului citesc istoricul depozitului, pull request-urile și revizuirile.

## 1. Ramuri

- `main` este protejată: nu se face `push` direct, doar prin pull request cu cel puțin o aprobare.
- Fiecare sarcină se lucrează pe o ramură proprie: `feature/<utilizator>-<scop>`, de exemplu `feature/ana-plan`, `feature/mihai-figura-2`.
- Înainte de a crea o ramură nouă: `git switch main` și `git pull`.
- După îmbinare, ramura se șterge (butonul *Delete branch* din pull request).

## 2. Commit-uri

- Un commit = o modificare cu sens (o secțiune, o figură, o corectură), nu „tot ce am făcut azi”.
- Mesajul: prima linie la imperativ, sub 50 de caractere, în engleză, de exemplu `Add introduction draft`, `Fix axis labels in figure 1`; detalii opționale în corp, după o linie goală.
- Commit-urile se fac cu numele și adresa de e-mail configurate în Git identice cu cele de pe GitHub, altfel nu se atribuie contribuția.

## 3. Pull request-uri

- Titlu clar, descriere din șablon (ce s-a schimbat, cum se verifică), `Closes #<nr>` pentru issue-ul rezolvat.
- Cel puțin un revizor din echipă, altul decât autorul; revizorul lasă cel puțin un comentariu și aprobă sau cere modificări.
- Autorul îmbină după aprobare și după ce verificările automate sunt verzi.
- Un pull request nu depășește, de regulă, 300 de linii modificate; dacă este mai mare, se împarte.

## 4. Issues și Planner

- Sarcinile care ating fișiere din depozit sunt issues în GitHub, asignate unei persoane, cu etichetă (`raport`, `notebook`, `date`, `pagina`, `organizare`).
- Sarcinile organizatorice (întâlniri, minute, prezentare) rămân în tabla Planner a echipei.

## 5. Ce nu se pune în depozit

- Fișiere peste 5 MB, arhive, fișiere generate (`.ipynb_checkpoints`, `__pycache__`, `.aux`, `.log`).
- Parole, chei API, fișiere `.env`, date personale ale colegilor sau ale altor persoane.
- Notebook-uri cu rezultate mari (imagini încorporate multe): dimensiunea unui notebook rămâne sub 2 MB.

## 6. Notebook-uri

- `notebooks/analiza.ipynb` are un singur editor la un moment dat (responsabilul datelor); ceilalți propun modificări prin issues sau prin propriul notebook `notebooks/<utilizator>-explorare.ipynb`.
- Notebook-ul echipei trebuie să ruleze de la zero (*Runtime > Run all*) pe un runtime nou; datele se citesc prin URL raw din acest depozit.

## 7. Raport

- Raportul se scrie în Overleaf, în perechi: proprietarul (responsabilul raportului) și un colaborator cu drept de editare; planul gratuit permite un singur colaborator. Ceilalți citesc prin link-ul de vizualizare și propun modificări prin issues cu eticheta `raport`.
- Proiectul Overleaf pornește din șablonul disciplinei, `raport-dctc.zip`, din depozitul `cursuri-inf/DCTC`.
- La fiecare livrabil, PDF-ul exportat se commit-uiește în `report/raport.pdf`, iar la T4 și la final sursele se pun în `report/src/`.

## 8. Instrumente AI

Politica disciplinei se aplică integral: explicațiile sunt permise, textul sau codul generat se declară în raport și în descrierea pull request-ului, nedeclararea este abatere de integritate academică.
