<div align="center">

# Agent-Me

**Crea un agente de respuestas transparente y fundamentado con el conocimiento que controlas.**

Una base de código abierto centrada en la privacidad, con backend tipado en FastAPI, interfaz React, recuperación local de documentos y un proveedor opcional compatible con OpenAI.

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> Esta es la traducción al español de la descripción general. La [documentación en inglés](../../README.md) y <code>docs/</code> constituyen la especificación técnica canónica.

## Descripción

Agent-Me es un framework pequeño y auditable para publicar un agente de preguntas y respuestas basado en documentos Markdown.

- El **modo extractivo local** funciona sin modelos externos ni claves de API.
- El **modo proveedor** envía únicamente el contexto recuperado y la conversación reciente al endpoint compatible con OpenAI que configures.
- Las respuestas pueden incluir los fragmentos de documentos utilizados como fuentes.

El repositorio público contiene solo código reutilizable. No incluye bases de datos de producción, memoria privada, analítica, credenciales ni secretos de despliegue.

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
