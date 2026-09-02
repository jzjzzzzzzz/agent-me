<div align="center">

# Agent-Me

**Prüfbare Multi-Agent-RAG-Systeme entwickeln, untersuchen und evaluieren.**

Agent-Me ist eine Open-Source-Referenzimplementierung für prüfbare, rollenbasierte Multi-Agent-RAG-Abläufe mit einem zweisprachigen praxisorientierten Engineering-Curriculum.

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> Dies ist die deutsche Übersetzung der Projektübersicht. Die technische Referenz bilden die [englische README](../../README.md) und die Dokumente unter <code>docs/</code>.

## Was Agent-Me ist

Die ausführbare FastAPI- und React-Implementierung führt Planner, Researcher, Critic, Writer und optional Verifier nacheinander in einem Prozess aus. Typisierte Übergaben, abgerufene Belege, Sperrentscheidungen, sichere Ablaufspuren und deterministische Evaluation bleiben sichtbar. Der lokale Kernpfad benötigt keine kostenpflichtige Modell-API.

## Was Agent-Me nicht ist

Agent-Me ist derzeit keine verteilte Multi-Agent-Laufzeit, kein allgemeines Agent-SDK und keine gehostete Unternehmensplattform. Der Verifier prüft mechanische Ausgabeinvarianten, nicht die faktische Wahrheit.

## Engineering-Curriculum

Das Curriculum erklärt und rekonstruiert dieselbe Architektur wie die Referenzimplementierung. Die vollständige Fassung ist auf [Englisch](../../course/README.md) und [vereinfachtem Chinesisch](../../course/translations/zh-CN/README.md) verfügbar.

## Funktionen

| Bereich | Enthalten |
| --- | --- |
| Wissensquelle | Prüfbare und versionierbare Markdown-Dateien |
| Suche | Deterministische lokale Suche mit Quellenauszügen |
| Generierung | Optionaler OpenAI-kompatibler Anbieter |
| Backend | FastAPI, strenge Schemas und Eingabegrenzen |
| Frontend | React, sichere Textdarstellung, responsives Design |
| Sprachen | Automatische Erkennung und 9 UI-Sprachen |
| Qualität | Docker Compose, CI, Tests, Linting, Typprüfung |

## Schnellstart

Benötigt werden Docker und das Compose-Plugin.

~~~bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
cp .env.example .env
docker compose up --build
~~~

Öffne <http://localhost:5173>. Die API-Dokumentation ist unter <http://localhost:8000/docs> verfügbar. Der lokale Modus ist voreingestellt und benötigt keinen API-Schlüssel.

## Anpassen

1. Ersetze <code>knowledge/example-profile.md</code> durch Markdown-Inhalte, die du verwenden darfst.
2. Lege Name und Beschreibung in deiner lokalen <code>.env</code> fest.
3. Nutze den lokalen Modus oder konfiguriere einen OpenAI-kompatiblen Anbieter.
4. Prüfe die Quellen vor der Veröffentlichung.
5. Speichere Produktionsgeheimnisse im Secret Manager deiner Plattform, niemals in Git.

## Internationalisierung

Die Oberfläche unterstützt neun Sprachen. Beim ersten Besuch wird die Browsersprache verwendet; eine manuelle Auswahl wird nur im Browser gespeichert. Unbekannte Sprachen fallen auf Englisch zurück. Siehe [Lokalisierungsleitfaden](../LOCALIZATION.md).

## Sicherheit und Datenschutz

- Behandle Prompts und Wissensdateien als nicht vertrauenswürdige Eingaben.
- Die Oberfläche zeigt Text an und fügt kein unbearbeitetes HTML ein.
- Der lokale Modus überträgt keine Fragen oder Dokumente an einen Anbieter.
- Chats und Analysedaten werden standardmäßig nicht gespeichert.
- Veröffentliche keine Geheimnisse, private Kommunikation, regulierten Daten oder sensiblen personenbezogenen Informationen.

Sicherheitslücken bitte gemäß [SECURITY.md](../../SECURITY.md) vertraulich melden.

## Dokumentation, Mitwirkung und Lizenz

Siehe [API](../API.md), [Architektur](../ARCHITECTURE.md), [Deployment](../DEPLOYMENT.md) und [Beitragsleitfaden](../../CONTRIBUTING.md).

Verwandtes Projekt: [Human API](https://github.com/jzjzzzzzzz/human-api). Lizenz: [MIT](../../LICENSE).
