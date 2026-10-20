# Chrysalide

Chrysalide aide les analystes et les data scientists à rendre leurs scripts
Python et notebooks plus faciles à exécuter, comprendre et partager.

Chaque projet est différent. Chrysalide s'adapte au code fourni et évite les
changements inutiles : si le code fonctionne déjà bien, il le laisse autant que
possible tel quel.

Avec l'aide de modèles de langage, Chrysalide peut proposer des améliorations
pour rendre le code plus fiable et plus facile à transmettre. L'utilisateur
examine et valide chaque proposition.

## Comment ça marche

1. L'utilisateur fournit un notebook ou des fichiers Python.
2. Chrysalide repère les améliorations utiles et explique ses propositions.
3. L'utilisateur choisit les changements à appliquer.
4. Des vérifications aident à confirmer que le code fonctionne toujours.

## Inspecter un notebook

Après l'installation, lancer cette commande depuis le dossier du projet :

```powershell
python -m chrysalide inspect chemin\vers\notebook.ipynb
```

Si le notebook est dans un sous-dossier ou séparé de ses fichiers, indiquer le
dossier depuis lequel son code est habituellement exécuté :

```powershell
python -m chrysalide inspect mon-projet\notebooks\analyse.ipynb --project-dir mon-projet
```

Le chemin du notebook et celui du projet sont relatifs au dossier du terminal.
Sans `--project-dir`, le dossier du notebook reste la référence. Le dossier choisi
doit exister ; Chrysalide ne le crée pas et ne change pas le dossier du terminal.

Cette commande résume les types de cellules, les modules importés et les
références à des fichiers détectables dans le code, en plus des sorties
enregistrées. Les chemins construits à partir de variables sont présentés comme
des expressions de code ; les chemins littéraux ou construits simplement sont
vérifiés depuis le dossier de référence affiché. Ce dossier sert aussi à repérer
les modules locaux à sa racine. Cette présence est indicative, car le
dossier d'exécution peut être différent. Les imports sont séparés entre
bibliothèque standard, modules du projet repérés et autres imports à vérifier.
Le nom d'un module ne permet pas toujours de déduire le nom du paquet à installer ;
Chrysalide n'installe et ne génère aucune dépendance automatiquement.

Les cellules qui utilisent une syntaxe non Python standard sont signalées
lorsqu'elles ne peuvent pas être analysées. La commande ne lance pas le code du
notebook et ne modifie pas le fichier.

## Développement

Python 3.10 ou supérieur est nécessaire pour développer Chrysalide.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```
