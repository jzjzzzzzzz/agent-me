<div align="center">

# Agent-Me

**Construisez, inspectez et évaluez des systèmes RAG multi-agents auditables.**

Agent-Me est une implémentation de référence open source pour des workflows RAG multi-agents auditables et fondés sur des rôles, accompagnée d’un cursus d’ingénierie pratique bilingue.

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> Ceci est la traduction française de la présentation du projet. Le [README anglais](../../README.md) et les documents du dossier <code>docs/</code> constituent la spécification technique de référence.

## Ce qu’est Agent-Me

L’implémentation exécutable FastAPI + React orchestre séquentiellement Planner, Researcher, Critic, Writer et, en option, Verifier dans un seul processus. Elle expose les transferts typés, les preuves retrouvées, les décisions de blocage, les traces opérationnelles sûres et l’évaluation déterministe. Le parcours local principal ne nécessite aucune API de modèle payante.

## Ce que Agent-Me n’est pas

Ce n’est actuellement ni un runtime multi-agent distribué, ni un SDK généraliste pour agents, ni une plateforme d’entreprise hébergée. Le vérificateur contrôle des invariants mécaniques de sortie, pas la vérité factuelle.

## Cursus d’ingénierie

Le cursus explique et reconstruit la même architecture que l’implémentation de référence. Il est complet en [anglais](../../course/README.md) et en [chinois simplifié](../../course/translations/zh-CN/README.md).

## Fonctionnalités

| Domaine | Inclus |
| --- | --- |
| Connaissances | Documents Markdown vérifiables et versionnés |
| Recherche | Recherche locale déterministe et extraits de sources |
| Génération | Fournisseur compatible OpenAI facultatif |
| Backend | FastAPI, schémas stricts et limites d'entrée |
| Frontend | React, rendu texte sécurisé, interface adaptative |
| Langues | Détection automatique et 9 langues d'interface |
| Qualité | Docker Compose, CI, tests, lint et typage |

## Démarrage rapide

Docker avec le plugin Compose est nécessaire.

~~~bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
cp .env.example .env
docker compose up --build
~~~

Ouvrez <http://localhost:5173>. La documentation de l'API est disponible sur <http://localhost:8000/docs>. Le mode d'extraction local est activé par défaut et ne nécessite aucune clé API.

## Personnalisation

1. Remplacez <code>knowledge/example-profile.md</code> par des documents Markdown que vous êtes autorisé à utiliser.
2. Configurez le nom et la description dans votre fichier <code>.env</code> local.
3. Conservez le mode local ou configurez un fournisseur compatible OpenAI.
4. Vérifiez les sources avant publication.
5. Placez les secrets de production dans le gestionnaire de secrets de votre hébergeur, jamais dans Git.

## Internationalisation

L'interface prend en charge neuf langues. La première visite suit la langue du navigateur ; le choix manuel reste enregistré uniquement dans le navigateur. Une langue inconnue revient à l'anglais. Consultez le [guide de localisation](../LOCALIZATION.md).

## Sécurité et vie privée

- Considérez les prompts et documents comme des entrées non fiables.
- L'interface affiche du texte et n'insère pas de HTML brut.
- Le mode local ne transmet ni questions ni documents à un fournisseur.
- Cette base ne conserve pas les conversations et n'active pas l'analytique par défaut.
- Ne publiez aucun secret, échange privé, donnée réglementée ou information personnelle sensible.

Signalez les vulnérabilités en privé selon [SECURITY.md](../../SECURITY.md).

## Documentation, contribution et licence

Consultez l'[API](../API.md), l'[architecture](../ARCHITECTURE.md), le [déploiement](../DEPLOYMENT.md) et le [guide de contribution](../../CONTRIBUTING.md).

Projet associé : [Human API](https://github.com/jzjzzzzzzz/human-api). Licence : [MIT](../../LICENSE).
