<div align="center">

# Agent-Me

**Créez un agent de réponse transparent et fondé sur les connaissances que vous maîtrisez.**

Une base open source respectueuse de la vie privée, avec un backend FastAPI typé, une interface React, une recherche locale dans les documents et un fournisseur compatible OpenAI facultatif.

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> Ceci est la traduction française de la présentation du projet. Le [README anglais](../../README.md) et les documents du dossier <code>docs/</code> constituent la spécification technique de référence.

## Présentation

Agent-Me est un framework compact et auditable qui permet de publier un agent de questions-réponses fondé sur des documents Markdown.

- Le **mode d'extraction local** fonctionne sans modèle externe ni clé API.
- Le **mode fournisseur** transmet uniquement le contexte récupéré et la conversation récente au service compatible OpenAI que vous configurez.
- Les réponses peuvent inclure les extraits de documents utilisés comme sources.

Le dépôt public ne contient que du code réutilisable. Il ne contient aucune base de données de production, mémoire privée, donnée analytique, information d'identification ou secret de déploiement.

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
