# Notebook-uri

| Fișier | Cine îl editează | Ce conține |
| --- | --- | --- |
| `analiza.ipynb` | responsabilul datelor și notebook-ului (un singur editor) | notebook-ul echipei, construit din șablonul cursului; rulează de la zero și produce figurile din `report/figures/` |
| `<utilizator>-explorare.ipynb` | fiecare membru, al său | explorările proprii (un grafic, o verificare, o idee), salvate din Colab cu *File > Save a copy in GitHub* pe o ramură proprie și aduse prin pull request |

Reguli:

- Datele se citesc prin URL raw din acest depozit (`https://raw.githubusercontent.com/<utilizator>/<depozit>/main/data/<fisier>.csv`), nu din Drive și nu prin upload manual.
- Înainte de commit: *Edit > Clear all outputs* dacă notebook-ul depășește 2 MB; figurile se salvează ca PNG în `report/figures/`, nu se lasă doar încorporate.
- Nicio cheie, parolă sau cale locală în celule.
- Workflow-ul `notebook-check.yml` rulează `analiza.ipynb` de la zero la fiecare push; dacă pică, jurnalul arată celula problemă.
