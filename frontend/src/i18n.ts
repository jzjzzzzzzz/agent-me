export const supportedLocales = [
  { code: "en", label: "English" },
  { code: "zh-CN", label: "简体中文" },
  { code: "zh-TW", label: "繁體中文" },
  { code: "ja", label: "日本語" },
  { code: "ko", label: "한국어" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" },
  { code: "pt-BR", label: "Português (Brasil)" },
] as const;

export type Locale = (typeof supportedLocales)[number]["code"];

type Messages = {
  language: string;
  projectLabel: string;
  title: string;
  intro: string;
  formLabel: string;
  placeholder: string;
  searching: string;
  ask: string;
  answer: string;
  groundingSources: string;
  noSources: string;
  inputPrivacy: string;
  characters: string;
  requestFailed: string;
  extractiveMode: string;
  providerMode: string;
  footer: string;
};

export const messages: Record<Locale, Messages> = {
  en: {
    language: "Language",
    projectLabel: "OPEN-SOURCE STARTER",
    title: "Build an answer agent from knowledge you control.",
    intro:
      "Add Markdown documents, choose an OpenAI-compatible provider—or run local extractive mode—and ship a transparent, grounded Q&A experience.",
    formLabel: "Ask the example knowledge base",
    placeholder: "How does the example agent plan a project?",
    searching: "Searching…",
    ask: "Ask",
    answer: "Answer",
    groundingSources: "Grounding sources",
    noSources: "No matching source excerpts were found.",
    inputPrivacy: "Questions are sent only to this deployment.",
    characters: "characters",
    requestFailed: "Request failed",
    extractiveMode: "extractive",
    providerMode: "provider",
    footer:
      "Prompts are untrusted input. Review your documents before publishing and never commit secrets.",
  },
  "zh-CN": {
    language: "语言",
    projectLabel: "开源启动框架",
    title: "用你掌控的知识构建问答 Agent。",
    intro:
      "添加 Markdown 文档，选择 OpenAI 兼容服务，或使用本地抽取模式，构建透明且有来源依据的问答体验。",
    formLabel: "向示例知识库提问",
    placeholder: "示例 Agent 如何规划一个项目？",
    searching: "正在检索…",
    ask: "提问",
    answer: "回答",
    groundingSources: "依据来源",
    noSources: "未找到匹配的来源片段。",
    inputPrivacy: "问题只会发送到当前部署。",
    characters: "字符",
    requestFailed: "请求失败",
    extractiveMode: "本地抽取",
    providerMode: "模型服务",
    footer: "提示词是不可信输入。发布前请检查文档，切勿提交任何密钥。",
  },
  "zh-TW": {
    language: "語言",
    projectLabel: "開源起始框架",
    title: "用你掌控的知識建立問答 Agent。",
    intro:
      "加入 Markdown 文件，選擇 OpenAI 相容服務，或使用本機擷取模式，建立透明且有來源依據的問答體驗。",
    formLabel: "向範例知識庫提問",
    placeholder: "範例 Agent 如何規劃一個專案？",
    searching: "正在搜尋…",
    ask: "提問",
    answer: "回答",
    groundingSources: "依據來源",
    noSources: "找不到相符的來源片段。",
    inputPrivacy: "問題只會傳送到目前的部署。",
    characters: "字元",
    requestFailed: "請求失敗",
    extractiveMode: "本機擷取",
    providerMode: "模型服務",
    footer: "提示詞是不受信任的輸入。發布前請檢查文件，切勿提交任何密鑰。",
  },
  ja: {
    language: "言語",
    projectLabel: "オープンソース・スターター",
    title: "自分で管理する知識から回答エージェントを構築。",
    intro:
      "Markdown 文書を追加し、OpenAI 互換プロバイダーまたはローカル抽出モードを選んで、根拠が明確な Q&A を公開できます。",
    formLabel: "サンプル知識ベースに質問",
    placeholder: "サンプルエージェントはプロジェクトをどう計画しますか？",
    searching: "検索中…",
    ask: "質問する",
    answer: "回答",
    groundingSources: "根拠となるソース",
    noSources: "一致するソース抜粋は見つかりませんでした。",
    inputPrivacy: "質問はこのデプロイ先にのみ送信されます。",
    characters: "文字",
    requestFailed: "リクエストに失敗しました",
    extractiveMode: "ローカル抽出",
    providerMode: "モデルプロバイダー",
    footer:
      "プロンプトは信頼できない入力です。公開前に文書を確認し、秘密情報をコミットしないでください。",
  },
  ko: {
    language: "언어",
    projectLabel: "오픈 소스 스타터",
    title: "직접 관리하는 지식으로 답변 에이전트를 구축하세요.",
    intro:
      "Markdown 문서를 추가하고 OpenAI 호환 공급자 또는 로컬 추출 모드를 선택해 근거가 투명한 Q&A를 제공하세요.",
    formLabel: "예제 지식 베이스에 질문하기",
    placeholder: "예제 에이전트는 프로젝트를 어떻게 계획하나요?",
    searching: "검색 중…",
    ask: "질문하기",
    answer: "답변",
    groundingSources: "근거 출처",
    noSources: "일치하는 근거 출처를 찾지 못했습니다.",
    inputPrivacy: "질문은 현재 배포 환경에만 전송됩니다.",
    characters: "자",
    requestFailed: "요청 실패",
    extractiveMode: "로컬 추출",
    providerMode: "모델 공급자",
    footer:
      "프롬프트는 신뢰할 수 없는 입력입니다. 게시 전에 문서를 검토하고 비밀 정보를 커밋하지 마세요.",
  },
  es: {
    language: "Idioma",
    projectLabel: "PLANTILLA DE CÓDIGO ABIERTO",
    title: "Crea un agente de respuestas con el conocimiento que controlas.",
    intro:
      "Añade documentos Markdown, elige un proveedor compatible con OpenAI o usa el modo extractivo local para ofrecer respuestas transparentes y fundamentadas.",
    formLabel: "Pregunta a la base de conocimiento de ejemplo",
    placeholder: "¿Cómo planifica un proyecto el agente de ejemplo?",
    searching: "Buscando…",
    ask: "Preguntar",
    answer: "Respuesta",
    groundingSources: "Fuentes de respaldo",
    noSources: "No se encontraron fragmentos de fuentes coincidentes.",
    inputPrivacy: "Las preguntas solo se envían a este despliegue.",
    characters: "caracteres",
    requestFailed: "La solicitud ha fallado",
    extractiveMode: "extractivo local",
    providerMode: "proveedor",
    footer:
      "Los prompts son entradas no confiables. Revisa tus documentos antes de publicarlos y nunca confirmes secretos.",
  },
  fr: {
    language: "Langue",
    projectLabel: "KIT DE DÉMARRAGE OPEN SOURCE",
    title: "Créez un agent de réponse à partir des connaissances que vous maîtrisez.",
    intro:
      "Ajoutez des documents Markdown, choisissez un fournisseur compatible OpenAI ou le mode d'extraction local, puis proposez des réponses transparentes et sourcées.",
    formLabel: "Interroger la base de connaissances d'exemple",
    placeholder: "Comment l'agent d'exemple planifie-t-il un projet ?",
    searching: "Recherche…",
    ask: "Interroger",
    answer: "Réponse",
    groundingSources: "Sources de référence",
    noSources: "Aucun extrait de source correspondant n’a été trouvé.",
    inputPrivacy: "Les questions sont envoyées uniquement à ce déploiement.",
    characters: "caractères",
    requestFailed: "Échec de la requête",
    extractiveMode: "extraction locale",
    providerMode: "fournisseur",
    footer:
      "Les prompts sont des entrées non fiables. Vérifiez vos documents avant publication et ne validez jamais de secrets.",
  },
  de: {
    language: "Sprache",
    projectLabel: "OPEN-SOURCE-STARTER",
    title: "Erstelle einen Antwort-Agenten mit Wissen, das du kontrollierst.",
    intro:
      "Füge Markdown-Dokumente hinzu, wähle einen OpenAI-kompatiblen Anbieter oder den lokalen Extraktionsmodus und veröffentliche transparente, belegte Antworten.",
    formLabel: "Die Beispiel-Wissensbasis fragen",
    placeholder: "Wie plant der Beispiel-Agent ein Projekt?",
    searching: "Suche läuft…",
    ask: "Fragen",
    answer: "Antwort",
    groundingSources: "Belegquellen",
    noSources: "Es wurden keine passenden Quellenauszüge gefunden.",
    inputPrivacy: "Fragen werden nur an diese Bereitstellung gesendet.",
    characters: "Zeichen",
    requestFailed: "Anfrage fehlgeschlagen",
    extractiveMode: "lokale Extraktion",
    providerMode: "Modellanbieter",
    footer:
      "Prompts sind nicht vertrauenswürdige Eingaben. Prüfe Dokumente vor der Veröffentlichung und committe niemals Geheimnisse.",
  },
  "pt-BR": {
    language: "Idioma",
    projectLabel: "PROJETO INICIAL DE CÓDIGO ABERTO",
    title: "Crie um agente de respostas com o conhecimento que você controla.",
    intro:
      "Adicione documentos Markdown, escolha um provedor compatível com OpenAI ou use o modo extrativo local para oferecer respostas transparentes e fundamentadas.",
    formLabel: "Pergunte à base de conhecimento de exemplo",
    placeholder: "Como o agente de exemplo planeja um projeto?",
    searching: "Pesquisando…",
    ask: "Perguntar",
    answer: "Resposta",
    groundingSources: "Fontes de referência",
    noSources: "Nenhum trecho de fonte correspondente foi encontrado.",
    inputPrivacy: "As perguntas são enviadas apenas para esta implantação.",
    characters: "caracteres",
    requestFailed: "Falha na solicitação",
    extractiveMode: "extração local",
    providerMode: "provedor",
    footer:
      "Prompts são entradas não confiáveis. Revise os documentos antes de publicar e nunca faça commit de segredos.",
  },
};

const storageKey = "agent-me-locale";

export function resolveLocale(value: string | null | undefined): Locale {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) return "en";
  if (normalized === "zh-tw" || normalized === "zh-hk" || normalized.startsWith("zh-hant")) {
    return "zh-TW";
  }
  if (normalized.startsWith("zh")) return "zh-CN";
  if (normalized.startsWith("pt")) return "pt-BR";
  const exact = supportedLocales.find(
    ({ code }) => code.toLowerCase() === normalized || normalized.startsWith(code.toLowerCase() + "-"),
  );
  return exact?.code ?? "en";
}

export function initialLocale(): Locale {
  try {
    const stored = window.localStorage.getItem(storageKey);
    if (stored && supportedLocales.some(({ code }) => code === stored)) return stored as Locale;
  } catch {
    // Storage may be unavailable in privacy-restricted browser contexts.
  }
  return resolveLocale(window.navigator.language);
}

export function persistLocale(locale: Locale): void {
  document.documentElement.lang = locale;
  try {
    window.localStorage.setItem(storageKey, locale);
  } catch {
    // The selected locale still applies for the current page session.
  }
}
