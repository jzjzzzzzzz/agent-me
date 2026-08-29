<div align="center">

# Agent-Me

**직접 관리하는 지식으로 투명하고 근거 있는 답변 에이전트를 구축하세요.**

타입이 적용된 FastAPI 백엔드, React UI, 로컬 문서 검색, 선택 가능한 OpenAI 호환 공급자를 제공하는 개인정보 보호 중심 오픈 소스 기반입니다.

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> 이 문서는 프로젝트 개요의 한국어 번역입니다. 전체 기술 사양은 [영문 README](../../README.md)와 <code>docs/</code>를 기준으로 합니다.

## 무료 실습 중심 강좌

Agent-Me는 8개 수업으로 구성된 체계적인 강좌를 우선합니다. 선수 지식, 원리, 소스 코드 읽기 순서, 실행 가능한 실습, 연습 문제, 이해도 질문, 포트폴리오 최종 프로젝트를 포함합니다. 전체 강좌는 현재 [영어](../../course/README.md)와 [중국어 간체](../../course/translations/zh-CN/README.md)로 제공됩니다. 번역 기여를 환영하며, 미완성 범위는 [언어 지원 표](../../course/LANGUAGES.md)에 명확히 표시합니다.

## 개요

Agent-Me는 Markdown 문서를 기반으로 Q&A 에이전트를 공개하기 위한 작고 감사 가능한 프레임워크입니다.

- **로컬 추출 모드**는 외부 모델이나 API 키 없이 작동합니다.
- **공급자 모드**는 검색된 컨텍스트와 최근 대화만 설정한 OpenAI 호환 엔드포인트로 전송합니다.
- 답변과 함께 근거가 된 문서 일부를 반환할 수 있습니다.

공개 저장소에는 재사용 가능한 코드만 있으며 운영 데이터베이스, 비공개 메모리, 분석 기록, 자격 증명 또는 배포 비밀 정보가 없습니다.

## 주요 기능

| 영역 | 제공 기능 |
| --- | --- |
| 지식 소스 | 검토하고 버전 관리할 수 있는 Markdown |
| 검색 | 결정론적 로컬 검색과 근거 발췌 |
| 생성 | 선택 가능한 OpenAI 호환 공급자 |
| 백엔드 | FastAPI, 엄격한 요청 스키마와 입력 제한 |
| 프론트엔드 | React, 안전한 텍스트 렌더링, 반응형 UI |
| 국제화 | 브라우저 언어 자동 감지와 9개 언어 |
| 품질 | Docker Compose, CI, 테스트, Lint, 타입 검사 |

## 빠른 시작

Docker와 Compose 플러그인이 필요합니다.

~~~bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
cp .env.example .env
docker compose up --build
~~~

웹 UI는 <http://localhost:5173>, API 문서는 <http://localhost:8000/docs>에서 확인할 수 있습니다. 기본 로컬 추출 모드는 API 키가 필요하지 않습니다.

## 사용자 지정

1. <code>knowledge/example-profile.md</code>를 사용 권한이 있는 Markdown 문서로 교체합니다.
2. 로컬 <code>.env</code>에서 앱 이름과 설명을 설정합니다.
3. 로컬 추출 모드를 유지하거나 OpenAI 호환 공급자를 설정합니다.
4. 공개 전에 답변의 출처를 검토하고 지식 문서를 조정합니다.
5. 운영 비밀 정보는 호스팅 플랫폼의 Secret Manager에 보관합니다.

## 국제화

UI는 9개 언어를 지원합니다. 첫 방문에는 브라우저 로캘을 사용하며, 수동 선택은 브라우저에만 저장됩니다. 지원하지 않는 언어는 영어로 대체됩니다. 자세한 내용은 [현지화 가이드](../LOCALIZATION.md)를 확인하세요.

## 보안 및 개인정보 보호

- 프롬프트와 지식 파일은 신뢰할 수 없는 입력으로 취급합니다.
- UI는 원시 HTML이 아닌 텍스트로 응답을 렌더링합니다.
- 로컬 추출 모드는 질문이나 문서를 외부 모델로 전송하지 않습니다.
- 이 스타터는 기본적으로 채팅이나 분석 데이터를 영구 저장하지 않습니다.
- 비밀 정보, 개인 통신, 규제 대상 데이터 또는 민감한 개인정보를 지식 디렉터리에 넣지 마세요.

취약점은 공개 Issue 대신 [SECURITY.md](../../SECURITY.md)의 절차로 비공개 보고해 주세요.

## 문서·기여·라이선스

[API](../API.md), [아키텍처](../ARCHITECTURE.md), [배포](../DEPLOYMENT.md), [기여 가이드](../../CONTRIBUTING.md)를 참고하세요.

관련 프로젝트: [Human API](https://github.com/jzjzzzzzzz/human-api). 이 프로젝트는 [MIT License](../../LICENSE)를 따릅니다.
