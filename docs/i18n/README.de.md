<div align="center">

# Agent-Me

**Erstelle einen transparenten, belegten Antwort-Agenten mit Wissen, das du kontrollierst.**

Eine datenschutzorientierte Open-Source-Basis mit typisiertem FastAPI-Backend, React-Oberfläche, lokaler Dokumentsuche und optionalem OpenAI-kompatiblem Anbieter.

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> Dies ist die deutsche Übersetzung der Projektübersicht. Die technische Referenz bilden die [englische README](../../README.md) und die Dokumente unter <code>docs/</code>.

## Überblick

Agent-Me ist ein kleines, prüfbares Framework zur Veröffentlichung eines Frage-Antwort-Agenten auf Grundlage von Markdown-Dokumenten.

- Der **lokale Extraktionsmodus** funktioniert ohne externes Modell und ohne API-Schlüssel.
- Der **Anbietermodus** sendet nur den gefundenen Kontext und den jüngsten Gesprächsverlauf an den von dir konfigurierten OpenAI-kompatiblen Endpunkt.
- Antworten können die verwendeten Dokumentauszüge als Quellen enthalten.

Das öffentliche Repository enthält ausschließlich wiederverwendbaren Code – keine Produktionsdatenbank, privaten Erinnerungen, Analysedaten, Zugangsdaten oder Deployment-Geheimnisse.

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
