<div align="center">

# Agent-Me

**Crie um agente de respostas transparente e fundamentado com o conhecimento que você controla.**

Uma base de código aberto focada em privacidade, com backend FastAPI tipado, interface React, recuperação local de documentos e um provedor opcional compatível com OpenAI.

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> Esta é a tradução para português do Brasil da visão geral do projeto. O [README em inglês](../../README.md) e os documentos em <code>docs/</code> são a especificação técnica canônica.

## Curso prático e gratuito

O Agent-Me agora é organizado primeiro como um curso estruturado de 8 lições: pré-requisitos, teoria, percursos de leitura do código, laboratórios executáveis, exercícios, perguntas de compreensão e um projeto final para portfólio. O curso completo está disponível atualmente em [inglês](../../course/README.md) e [chinês simplificado](../../course/translations/zh-CN/README.md). Traduções são bem-vindas; a [cobertura de idiomas](../../course/LANGUAGES.md) identifica claramente o conteúdo incompleto.

## Visão geral

Agent-Me é um framework pequeno e auditável para publicar um agente de perguntas e respostas baseado em documentos Markdown.

- O **modo extrativo local** funciona sem modelo externo ou chave de API.
- O **modo de provedor** envia somente o contexto recuperado e a conversa recente ao endpoint compatível com OpenAI configurado por você.
- As respostas podem incluir os trechos de documentos usados como fontes.

O repositório público contém apenas código reutilizável. Ele não inclui banco de dados de produção, memória privada, registros analíticos, credenciais ou segredos de implantação.

## Recursos

| Área | Incluído |
| --- | --- |
| Conhecimento | Markdown revisável e versionado |
| Recuperação | Busca local determinística e trechos de fontes |
| Geração | Provedor opcional compatível com OpenAI |
| Backend | FastAPI, esquemas rigorosos e limites de entrada |
| Frontend | React, renderização segura de texto, design responsivo |
| Idiomas | Detecção automática e 9 idiomas de interface |
| Qualidade | Docker Compose, CI, testes, lint e tipos |

## Início rápido

É necessário ter Docker com o plugin Compose.

~~~bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
cp .env.example .env
docker compose up --build
~~~

Abra <http://localhost:5173>. A documentação da API está em <http://localhost:8000/docs>. O modo extrativo local vem habilitado e não exige chave de API.

## Personalização

1. Substitua <code>knowledge/example-profile.md</code> por Markdown que você tenha permissão para usar.
2. Configure nome e descrição no arquivo <code>.env</code> local.
3. Mantenha o modo local ou configure um provedor compatível com OpenAI.
4. Revise as fontes antes de publicar.
5. Guarde segredos de produção no gerenciador de segredos da plataforma, nunca no Git.

## Internacionalização

A interface oferece nove idiomas. Na primeira visita, segue o idioma do navegador; a seleção manual fica armazenada apenas no navegador. Idiomas desconhecidos usam inglês. Consulte o [guia de localização](../LOCALIZATION.md).

## Segurança e privacidade

- Trate prompts e documentos como entradas não confiáveis.
- A interface renderiza texto e não insere HTML bruto.
- O modo local não transmite perguntas nem documentos a um provedor.
- Este projeto não persiste conversas nem habilita análises por padrão.
- Não publique segredos, comunicações privadas, dados regulamentados ou informações pessoais sensíveis.

Relate vulnerabilidades de forma privada conforme [SECURITY.md](../../SECURITY.md).

## Documentação, contribuição e licença

Consulte [API](../API.md), [arquitetura](../ARCHITECTURE.md), [implantação](../DEPLOYMENT.md) e [guia de contribuição](../../CONTRIBUTING.md).

Projeto relacionado: [Human API](https://github.com/jzjzzzzzzz/human-api). Licença: [MIT](../../LICENSE).
