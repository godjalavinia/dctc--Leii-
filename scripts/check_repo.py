#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificări automate pentru depozitul echipei (DCTC, UTCN CUNBM).

Utilizare:
    python scripts/check_repo.py                 # verificările de bază
    python scripts/check_repo.py --stage all     # de bază + T3, T4, T5, T6 și versiunea finală (avertismente)
    python scripts/check_repo.py --stage T5 --strict   # T5 ca eșec, nu ca avertisment
    python scripts/check_repo.py --stage all --json rezultat.json

Verificările de bază (structură, fișiere mari, secrete) opresc întotdeauna workflow-ul.
Verificările pe livrabile sunt avertismente, ca echipa să vadă ce mai lipsește; scriptul
titularului (dctc-grader) le rulează cu --strict la termen și adaugă ce se vede doar prin
API (pull request-uri, revizuiri, starea GitHub Pages).

Scriptul folosește doar biblioteca standard Python 3.8+ și, opțional, `git` și `pdftotext`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

MB = 1024 * 1024
LIMITA_FISIER = 5 * MB
LIMITA_NOTEBOOK = 2_000_000  # ca în notebook-check.yml și în verificarea titularului

FISIERE_OBLIGATORII = [
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    ".gitignore",
    "data/README.md",
    "notebooks/README.md",
    "report/README.md",
    "docs/index.md",
    "docs/_config.yml",
]

TIPARE_SECRETE = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "cheie AWS"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "cheie privată"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "token GitHub"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "token GitHub"),
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}"), "cheie API (sk-...)"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{30,}"), "cheie Google API"),
    (re.compile(r"(?i)\b(?:password|parola|passwd|api[_-]?key|secret[_-]?key|token)\b\s*[:=]\s*['\"][^'\"\s]{6,}['\"]"), "parolă sau cheie în clar"),
]

FISIERE_INTERZISE = [
    re.compile(r"(^|/)\.env(\..*)?$"),
    re.compile(r"\.pem$"),
    re.compile(r"\.key$"),
    re.compile(r"(^|/)\.ipynb_checkpoints/"),
    re.compile(r"(^|/)__pycache__/"),
]
FISIERE_NEDORITE = [re.compile(r"(^|/)\.DS_Store$"), re.compile(r"(^|/)Thumbs\.db$")]

PLACEHOLDER = re.compile(r"<[^<>\n]{0,60}[A-Za-zăâîșțĂÂÎȘȚ][^<>\n]{0,300}>")


class Raport:
    def __init__(self) -> None:
        self.rezultate: list[dict] = []

    def adauga(self, etapa: str, ok: bool, mesaj: str, sever: bool) -> None:
        self.rezultate.append({"etapa": etapa, "ok": ok, "mesaj": mesaj, "sever": sever})

    def afiseaza(self) -> None:
        in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        etapa_curenta = None
        for r in self.rezultate:
            if r["etapa"] != etapa_curenta:
                etapa_curenta = r["etapa"]
                print(f"\n== {etapa_curenta} ==")
            if r["ok"]:
                semn = "OK  "
            elif r["sever"]:
                semn = "EROARE"
            else:
                semn = "LIPSĂ"
            print(f"  [{semn}] {r['mesaj']}")
            if in_actions and not r["ok"]:
                nivel = "error" if r["sever"] else "warning"
                print(f"::{nivel}::[{r['etapa']}] {r['mesaj']}")

    def esec(self) -> bool:
        return any(not r["ok"] and r["sever"] for r in self.rezultate)


def fisiere_urmarite(radacina: Path) -> list[str]:
    """Fișierele din depozit: din `git ls-files` dacă există git, altfel din sistemul de fișiere."""
    if shutil.which("git") and (radacina / ".git").exists():
        try:
            iesire = subprocess.run(
                ["git", "ls-files", "-z"], cwd=radacina, capture_output=True, check=True
            ).stdout.decode("utf-8", "replace")
            return [f for f in iesire.split("\0") if f]
        except subprocess.CalledProcessError:
            pass
    rezultat = []
    for cale in radacina.rglob("*"):
        if cale.is_file() and ".git" not in cale.parts:
            rezultat.append(str(cale.relative_to(radacina)).replace(os.sep, "/"))
    return rezultat


def citeste_text(cale: Path, limita: int = MB) -> str:
    try:
        if cale.stat().st_size > limita:
            return ""
        return cale.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def fara_diacritice(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower()


# ---------------------------------------------------------------------------
# Verificările de bază
# ---------------------------------------------------------------------------

def verifica_baza(radacina: Path, fisiere: list[str], rap: Raport) -> None:
    etapa = "Bază: structură, dimensiuni, secrete"
    for nume in FISIERE_OBLIGATORII:
        exista = (radacina / nume).is_file()
        rap.adauga(etapa, exista, f"fișierul obligatoriu {nume}" + ("" if exista else " lipsește"), True)

    readme = citeste_text(radacina / "README.md")
    rap.adauga(etapa, len(readme.strip()) >= 200, "README.md are conținut (cel puțin 200 de caractere)", True)
    nr_placeholder = len(PLACEHOLDER.findall(readme))
    rap.adauga(etapa, nr_placeholder == 0,
               "README.md fără câmpuri necompletate de forma <...>" if nr_placeholder == 0
               else f"README.md mai are {nr_placeholder} câmpuri de completat de forma <...>", False)

    mari = []
    notebooks_mari = []
    interzise = []
    nedorite = []
    secrete = []
    acest_script = "scripts/check_repo.py"
    for f in fisiere:
        cale = radacina / f
        if not cale.is_file():
            continue
        dim = cale.stat().st_size
        if dim > LIMITA_FISIER:
            mari.append(f"{f} ({dim / MB:.1f} MB)")
        if f.endswith(".ipynb") and dim > LIMITA_NOTEBOOK:
            notebooks_mari.append(f"{f} ({dim / MB:.1f} MB)")
        if any(t.search(f) for t in FISIERE_INTERZISE):
            interzise.append(f)
        if any(t.search(f) for t in FISIERE_NEDORITE):
            nedorite.append(f)
        if f == acest_script or dim > MB:
            continue
        if cale.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".pptx", ".docx", ".xlsx"}:
            continue
        text = citeste_text(cale)
        for tipar, nume in TIPARE_SECRETE:
            if tipar.search(text):
                secrete.append(f"{f}: {nume}")
                break

    rap.adauga(etapa, not mari, "niciun fișier peste 5 MB" if not mari else "fișiere peste 5 MB: " + ", ".join(mari), True)
    rap.adauga(etapa, not notebooks_mari, "notebook-urile au sub 2 MB" if not notebooks_mari
               else "notebook-uri peste 2 MB (curățați rezultatele): " + ", ".join(notebooks_mari), True)
    rap.adauga(etapa, not interzise, "niciun fișier interzis (.env, .pem, .key, checkpoints)" if not interzise
               else "fișiere interzise în depozit: " + ", ".join(interzise), True)
    rap.adauga(etapa, not secrete, "niciun secret detectat în fișierele text" if not secrete
               else "posibile secrete în: " + ", ".join(secrete) + " (ștergeți-le și schimbați cheia)", True)
    rap.adauga(etapa, not nedorite, "fără fișiere de sistem (.DS_Store, Thumbs.db)" if not nedorite
               else "fișiere de sistem urmărite: " + ", ".join(nedorite), False)


# ---------------------------------------------------------------------------
# Livrabile
# ---------------------------------------------------------------------------

def verifica_t3(radacina: Path, fisiere: list[str], rap: Raport, sever: bool) -> None:
    etapa = "T3: depozitul echipei"
    readme = citeste_text(radacina / "README.md")
    randuri = [l for l in readme.splitlines() if l.startswith("|")]
    membri = []
    for l in randuri:
        celule = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(celule) >= 4 and celule[2].upper() in {"MI", "INF"}:
            membri.append(l)
    membri_completi = [l for l in membri if not PLACEHOLDER.search(l)]
    rap.adauga(etapa, len(membri_completi) >= 3,
               f"tabelul membrilor din README are {len(membri_completi)} rânduri completate (minimum 3)", sever)
    plan = citeste_text(radacina / "docs/plan.md")
    sectiuni = [l for l in plan.splitlines() if l.startswith("## ")]
    sectiuni_completate = [s for s in sectiuni if not PLACEHOLDER.search(s)]
    ramase = len(PLACEHOLDER.findall(plan))
    rap.adauga(etapa, len(sectiuni_completate) >= 4 and ramase == 0,
               f"docs/plan.md: {len(sectiuni_completate)} secțiuni completate, {ramase} câmpuri de completat rămase", sever)
    rap.adauga(etapa, True, "pull request-urile, revizuirile și issues se verifică de scriptul titularului prin API", False)


def numara_intrari_bib(text: str) -> int:
    return len([m for m in re.finditer(r"@(\w+)\s*[{(]", text) if m.group(1).lower() not in {"comment", "preamble", "string"}])


def text_pdf(cale: Path) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    try:
        return subprocess.run(["pdftotext", "-layout", str(cale), "-"], capture_output=True, check=True,
                              timeout=60).stdout.decode("utf-8", "replace")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def verifica_t4(radacina: Path, fisiere: list[str], rap: Raport, sever: bool) -> None:
    etapa = "T4: raportul"
    pdf = radacina / "report/raport.pdf"
    rap.adauga(etapa, pdf.is_file() and pdf.stat().st_size > 20 * 1024,
               "report/raport.pdf există și are peste 20 KB", sever)
    bib = citeste_text(radacina / "report/refs.bib")
    n = numara_intrari_bib(bib)
    rap.adauga(etapa, n >= 4, f"report/refs.bib are {n} intrări (minimum 4)", sever)
    surse = [f for f in fisiere if f.startswith("report/src/") and f.endswith(".tex")]
    rap.adauga(etapa, len(surse) >= 1, f"report/src/ conține {len(surse)} fișiere .tex (sursele Overleaf)", sever)
    if pdf.is_file():
        text = text_pdf(pdf)
        if text is None:
            rap.adauga(etapa, True, "pdftotext nu este instalat; secțiunile PDF-ului se verifică de scriptul titularului", False)
        else:
            # pdfLaTeX cu fontenc T1 compune ș și ț din literă și virgulă; pdftotext le scrie „s,” și „t,”
            text = re.sub(r"([sStT]),\s?(?=[a-zăâîșț])", r"\1", text)
            plat = fara_diacritice(text)
            lipsa = [s for s in ("introducere", "bibliografie", "declaratie") if s not in plat]
            rap.adauga(etapa, not lipsa, "PDF-ul conține Introducere, Bibliografie și Declarația AI" if not lipsa
                       else "în PDF lipsesc: " + ", ".join(lipsa), sever)
            cuvinte = len(plat.split())
            rap.adauga(etapa, cuvinte >= 400, f"PDF-ul are {cuvinte} cuvinte (minimum 400 la T4)", sever)
            m = re.search(r"(?m)^\s*1\s+Introducere\s*$", text)
            corp = ""
            if m:
                sf = re.search(r"(?m)^\s*2\s+\S", text[m.end():])
                corp = text[m.end():m.end() + sf.start()] if sf else text[m.end():]
                corp = re.sub(r"\[[^\[\]]*[A-Za-zăâîșțĂÂÎȘȚ][^\[\]]{12,}\]", " ", corp, flags=re.S)
            n_intro = len([w for w in corp.split() if re.search(r"[A-Za-zăâîșțĂÂÎȘȚ]", w)])
            citate = {int(x) for c in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", corp) for x in re.split(r"\s*,\s*", c)}
            rap.adauga(etapa, n_intro >= 200 and len(citate) >= 2,
                       f"Introducerea are {n_intro} cuvinte și {len(citate)} surse citate (minimum 200 și 2)", sever)
            decl = plat.split("declaratie privind utilizarea instrumentelor ai")[-1][:300] if "declaratie privind" in plat else ""
            rap.adauga(etapa, bool(decl.strip()) and "<instrument>" not in decl and not decl.strip().startswith("["),
                       "Declarația privind utilizarea AI este completată", sever)


def verifica_t5(radacina: Path, fisiere: list[str], rap: Raport, sever: bool) -> None:
    etapa = "T5: notebook-ul"
    nb = radacina / "notebooks/analiza.ipynb"
    if not nb.is_file():
        rap.adauga(etapa, False, "notebooks/analiza.ipynb lipsește", sever)
        return
    rap.adauga(etapa, nb.stat().st_size <= LIMITA_NOTEBOOK, "notebooks/analiza.ipynb are sub 2 MB", sever)
    try:
        date = json.loads(nb.read_text(encoding="utf-8"))
        celule = date.get("cells", [])
    except (json.JSONDecodeError, UnicodeDecodeError):
        rap.adauga(etapa, False, "notebooks/analiza.ipynb nu este un JSON valid de notebook", sever)
        return
    md = ["".join(c.get("source", [])) for c in celule if c.get("cell_type") == "markdown"]
    cod = ["".join(c.get("source", [])) for c in celule if c.get("cell_type") == "code"]
    rap.adauga(etapa, any("$" in s for s in md), "o celulă text conține o formulă LaTeX ($...$)", sever)
    rap.adauga(etapa, any(("plt." in s) or (".plot(" in s) for s in cod), "o celulă de cod desenează un grafic (matplotlib)", sever)
    surse_raw = re.findall(r"raw\.githubusercontent\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+)/", "\n".join(cod))
    depozit = os.environ.get("GITHUB_REPOSITORY", "").lower()  # în Actions: proprietar/depozit
    url_raw = any(not depozit or f"{o}/{r}".lower() == depozit for o, r in surse_raw)
    generate = any(re.search(r'^\s*TEMA\s*=\s*["\'](collatz|prime|monte_carlo|newton_bisectie)["\']', s, re.M) for s in cod)
    rap.adauga(etapa, url_raw or generate,
               "datele se citesc prin URL raw din acest depozit (temele 1-6) sau se generează în notebook (temele 7-10)", sever)
    rap.adauga(etapa, any("savefig" in s for s in cod), "figurile se salvează cu savefig", sever)
    figuri = [f for f in fisiere if f.startswith("report/figures/") and f.lower().endswith(".png")]
    rap.adauga(etapa, len(figuri) >= 2, f"report/figures/ are {len(figuri)} PNG (minimum 2)", sever)
    readme = citeste_text(radacina / "README.md")
    badge = bool(re.search(r"colab\.research\.google\.com/github/[^/<>\s)]+/[^/<>\s)]+/blob/[^\s)]*analiza\.ipynb", readme))
    rap.adauga(etapa, badge, "README are butonul Open in Colab cu adresa depozitului completată", sever)
    explorari = [f for f in fisiere if re.match(r"notebooks/[^/]+-explorare\.ipynb$", f)]
    membri = max(3, membri_din_readme(readme))
    rap.adauga(etapa, len(explorari) >= membri,
               f"{len(explorari)} notebook-uri de explorare, câte unul pentru fiecare membru (echipa are {membri})", sever)


def membri_din_readme(readme: str) -> int:
    """Numărul de rânduri din tabelul „Echipa” al README-ului (fără antet), adică numărul membrilor."""
    parte = readme.split("## Echipa", 1)[1] if "## Echipa" in readme else ""
    randuri = []
    for linie in parte.splitlines()[1:]:
        if linie.startswith("## "):
            break
        if linie.strip().startswith("|") and not re.match(r"^\|\s*-", linie.strip()):
            randuri.append(linie)
    return max(0, len(randuri) - 1)


def verifica_t6(radacina: Path, fisiere: list[str], rap: Raport, sever: bool) -> None:
    etapa = "T6: pagina proiectului"
    index = citeste_text(radacina / "docs/index.md")
    ramase = len(PLACEHOLDER.findall(index))
    rap.adauga(etapa, index.strip() != "" and ramase == 0,
               f"docs/index.md completat ({ramase} câmpuri de completat rămase)", sever)
    imagini = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", index)
    imagini_existente = [i for i in imagini if (radacina / "docs" / i).is_file()]
    rap.adauga(etapa, len(imagini_existente) >= 1,
               f"pagina are {len(imagini_existente)} imagini prezente în docs/ (minimum 1)", sever)
    rap.adauga(etapa, "raport.pdf" in index, "pagina are link către raportul PDF", sever)
    rap.adauga(etapa, "colab.research.google.com" in index or "analiza.ipynb" in index,
               "pagina are link către notebook", sever)
    config = citeste_text(radacina / "docs/_config.yml")
    rap.adauga(etapa, not PLACEHOLDER.search(config), "docs/_config.yml are titlul completat", sever)
    rap.adauga(etapa, True, "publicarea efectivă (Pages activ, HTTPS) se verifică de scriptul titularului prin API", False)


def verifica_final(radacina: Path, fisiere: list[str], rap: Raport, sever: bool) -> None:
    """Lista versiunii finale (laboratorul 7): fișierele fără câmpuri de completat, raportul, notebook-ul, pagina, eticheta v1.0."""
    etapa = "Versiunea finală"
    licenta = citeste_text(radacina / "LICENSE")
    rap.adauga(etapa, bool(licenta.strip()) and not PLACEHOLDER.search(licenta),
               "LICENSE are anul și numele echipei completate", sever)
    readme = citeste_text(radacina / "README.md")
    ramase = PLACEHOLDER.findall(readme)
    rap.adauga(etapa, readme.strip() != "" and not ramase,
               f"README.md fără câmpuri de completat ({len(ramase)} rămase)", sever)
    pagini = [m for m in re.findall(r"https://([A-Za-z0-9-]+)\.github\.io/", readme) if m.lower() != "utilizator"]
    rap.adauga(etapa, bool(pagini), "README.md are adresa paginii proiectului (https://….github.io/…/)", sever)
    date = citeste_text(radacina / "data/README.md")
    ramase = PLACEHOLDER.findall(date)
    rap.adauga(etapa, date.strip() != "" and not ramase,
               f"data/README.md completat: sursa, data, licența sau modul de generare ({len(ramase)} câmpuri rămase)", sever)
    pdf = radacina / "report/raport.pdf"
    surse = [f for f in fisiere if f.startswith("report/src/") and f.endswith(".tex")]
    rap.adauga(etapa, pdf.is_file() and bool(surse), "raportul final: report/raport.pdf și sursele din report/src/", sever)
    rap.adauga(etapa, (radacina / "notebooks/analiza.ipynb").is_file(), "notebooks/analiza.ipynb există", sever)
    index = citeste_text(radacina / "docs/index.md")
    rap.adauga(etapa, index.strip() != "" and not PLACEHOLDER.search(index) and "De completat de autor" not in index,
               "docs/index.md complet, cu paragraful fiecărui membru", sever)
    etichete = subprocess.run(["git", "tag", "--list", "v1.*"], cwd=radacina, capture_output=True, text=True) if shutil.which("git") else None
    are_v1 = bool(etichete and etichete.returncode == 0 and etichete.stdout.strip())
    rap.adauga(etapa, are_v1, "eticheta v1.0 există (se creează la final, cu release-ul)" if are_v1
               else "eticheta v1.0 lipsește: se creează la final, cu release-ul (Releases > Draft a new release)", False)


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Verificări automate pentru depozitul echipei DCTC.")
    parser.add_argument("--stage", default="base", choices=["base", "T3", "T4", "T5", "T6", "final", "all"],
                        help="ce se verifică (implicit: base)")
    parser.add_argument("--strict", action="store_true", help="livrabilele devin erori, nu avertismente")
    parser.add_argument("--json", metavar="FISIER", help="scrie rezultatele și în JSON")
    parser.add_argument("--root", default=".", help="rădăcina depozitului (implicit: directorul curent)")
    args = parser.parse_args()

    radacina = Path(args.root).resolve()
    fisiere = fisiere_urmarite(radacina)
    rap = Raport()

    verifica_baza(radacina, fisiere, rap)
    etape = {"T3": verifica_t3, "T4": verifica_t4, "T5": verifica_t5, "T6": verifica_t6, "final": verifica_final}
    de_rulat = list(etape) if args.stage == "all" else ([args.stage] if args.stage in etape else [])
    for e in de_rulat:
        etape[e](radacina, fisiere, rap, args.strict)

    rap.afiseaza()
    if args.json:
        Path(args.json).write_text(json.dumps(rap.rezultate, ensure_ascii=False, indent=2), encoding="utf-8")

    nr_erori = sum(1 for r in rap.rezultate if not r["ok"] and r["sever"])
    nr_lipsa = sum(1 for r in rap.rezultate if not r["ok"] and not r["sever"])
    print(f"\nRezumat: {nr_erori} erori, {nr_lipsa} elemente lipsă (avertismente).")
    return 1 if rap.esec() else 0


if __name__ == "__main__":
    sys.exit(main())
