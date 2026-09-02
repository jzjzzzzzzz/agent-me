<div align="center">

# Agent-Me

**Construye, inspecciona y evalúa sistemas RAG multiagente auditables.**

Agent-Me es una implementación de referencia de código abierto para flujos RAG multiagente auditables y basados en roles, acompañada de un currículo práctico bilingüe de ingeniería.

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> Esta es la traducción al español de la descripción general. La [documentación en inglés](../../README.md) y <code>docs/</code> constituyen la especificación técnica canónica.

## Qué es Agent-Me

La implementación ejecutable con FastAPI y React coordina secuencialmente Planner, Researcher, Critic, Writer y, de forma opcional, Verifier en un solo proceso. Expone entregas tipadas, evidencia recuperada, decisiones de bloqueo, trazas operativas seguras y evaluación determinista. La ruta local principal no requiere una API de modelo de pago.

## Qué no es Agent-Me

Actualmente no es un runtime multiagente distribuido, un SDK general de agentes ni una plataforma empresarial alojada. El verificador comprueba invariantes mecánicas de salida; no garantiza la verdad factual.

## Currículo de ingeniería

El currículo explica y reconstruye la misma arquitectura de la implementación de referencia. Está completo en [inglés](../../course/README.md) y [chino simplificado](../../course/translations/zh-CN/README.md).

## Capacidades

| Área | Incluido |
| --- | --- |
| Conocimiento | Markdown revisable y versionado |
| Recuperación | Búsqueda local determinista y fragmentos de fuentes |
| Generación | Proveedor opcional compatible con OpenAI |
| Backend | FastAPI, esquemas estrictos y límites de entrada |
| Frontend | React, texto seguro y diseño adaptable |
| Idiomas | Detección automática y 9 idiomas de interfaz |
| Calidad | Docker Compose, CI, pruebas, lint y tipos |

## Inicio rápido

Necesitas Docker con el complemento Compose.

~~~bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
cp .env.example .env
docker compose up --build
~~~

Abre <http://localhost:5173>. La documentación de la API está en <http://localhost:8000/docs>. El modo extractivo local viene activado y no necesita una clave de API.

## Personalización

1. Sustituye <code>knowledge/example-profile.md</code> por Markdown que tengas permiso para utilizar.
2. Configura el nombre y la descripción en tu archivo <code>.env</code> local.
3. Mantén el modo extractivo o configura un proveedor compatible con OpenAI.
4. Revisa las fuentes antes de publicar.
5. Guarda los secretos de producción en el gestor de secretos de tu plataforma, nunca en Git.

## Internacionalización

La interfaz admite nueve idiomas. En la primera visita sigue el idioma del navegador; la selección manual se guarda solo en el navegador. Los idiomas desconocidos vuelven al inglés. Consulta la [guía de localización](../LOCALIZATION.md).

## Seguridad y privacidad

- Trata los prompts y documentos como entradas no confiables.
- La interfaz muestra texto y no inserta HTML sin procesar.
- El modo local no transmite preguntas ni documentos a un proveedor.
- Esta plantilla no persiste chats ni activa analítica de forma predeterminada.
- No publiques secretos, comunicaciones privadas, datos regulados ni información personal sensible.

Informa de vulnerabilidades de forma privada según [SECURITY.md](../../SECURITY.md).

## Documentación, contribución y licencia

Consulta [API](../API.md), [arquitectura](../ARCHITECTURE.md), [despliegue](../DEPLOYMENT.md) y [contribución](../../CONTRIBUTING.md).

Proyecto relacionado: [Human API](https://github.com/jzjzzzzzzz/human-api). Licencia: [MIT](../../LICENSE).
