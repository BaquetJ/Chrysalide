# Chrysalide

Chrysalide aide les analystes et les data scientists à rendre leurs scripts et
notebooks plus faciles à exécuter, reprendre et transmettre.

L'outil doit s'adapter au projet, pas lui imposer une architecture uniforme :
si le code est déjà clair et fiable, il doit proposer peu ou pas de changements.
Les propositions d'un LLM restent lisibles et soumises à la validation de
l'utilisateur.

## Objectif du premier parcours

À partir d'un notebook ou d'un ou plusieurs fichiers Python, aider l'utilisateur
à :

1. comprendre l'organisation et les conditions d'exécution du projet ;
2. repérer les améliorations utiles sans réécrire inutilement le code ;
3. appliquer ou refuser les propositions ;
4. vérifier que le projet reste exécutable et plus facile à reprendre.

## Principes

- Préserver autant que possible le comportement et le style du travail initial.
- Adapter l'ampleur des changements à l'état réel du projet.
- Garder l'utilisateur aux commandes : aucune modification silencieuse.
- Distinguer les contrôles déterministes des suggestions du LLM.
- Expliquer les changements et rendre les résultats vérifiables.
- Ne jamais ajouter de données métier non partageables au dépôt.

## Périmètre initial

Le premier parcours sera défini à partir d'un cas d'usage partageable fourni
par l'utilisateur. Les choix de fournisseur LLM, d'interface et de packaging
seront faits lorsque le besoin sera établi, plutôt que présupposés.

## Développement

Le dépôt utilise `main` pour les versions stables et `dev` pour l'intégration
des petites briques. Chaque brique doit avoir un objectif clair, des commits
ciblés et des vérifications adaptées.

### Environnement de développement

Python 3.10 ou supérieur est requis.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Les commandes de test et de qualité seront ajoutées avec les premières
fonctionnalités qu'elles couvrent.
