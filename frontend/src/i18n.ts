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
  inputPrivacyUnconfirmed: string;
  inputPrivacyLocal: string;
  inputPrivacyProvider: string;
  characters: string;
  requestFailed: string;
  extractiveMode: string;
  providerMode: string;
  collaborationModeLabel: string;
  verifiedModeLabel: string;
  workflowMode: string;
  standardWorkflow: string;
  collaborationWorkflow: string;
  verifiedWorkflow: string;
  collaborationHint: string;
  verifiedHint: string;
  workflowTrace: string;
  grounded: string;
  notGrounded: string;
  completed: string;
  blocked: string;
  runId: string;
  exportRun: string;
  exportPrivacy: string;
  copyAnswer: string;
  copySources: string;
  copyAnswerSuccess: string;
  copySourcesSuccess: string;
  copyFailure: string;
  footer: string;
};

export const messages: Record<Locale, Messages> = {
  en: {
    language: "Language",
    projectLabel: "OPEN-SOURCE AI AGENT TWIN",
    title: "Distill yourself into an AI Agent Twin.",
    intro:
      "Ask an AI Twin grounded in reviewable personal knowledge, then inspect its evidence, agent decisions, critique, and verification.",
    formLabel: "Ask the example knowledge base",
    placeholder: "How does the example agent plan a project?",
    searching: "Searching…",
    ask: "Ask",
    answer: "Answer",
    groundingSources: "Grounding sources",
    noSources: "No matching source excerpts were found.",
    inputPrivacyUnconfirmed:
      "External provider use is not confirmed. Questions may be forwarded to a configured provider.",
    inputPrivacyLocal:
      "Questions are processed by this deployment and are not sent to an external model provider.",
    inputPrivacyProvider:
      "Questions, recent conversation history, and retrieved context are forwarded to the configured model provider.",
    characters: "characters",
    requestFailed: "Request failed",
    extractiveMode: "extractive",
    providerMode: "provider",
    collaborationModeLabel: "role-based multi-agent",
    verifiedModeLabel: "verified multi-agent",
    workflowMode: "Workflow",
    standardWorkflow: "Standard Q&A",
    collaborationWorkflow: "Role-based multi-agent",
    verifiedWorkflow: "Verified multi-agent",
    collaborationHint:
      "Runs planner, researcher, critic, and writer roles with typed, inspectable handoffs.",
    verifiedHint:
      "Adds a final verifier that checks citation paths and answer metadata, blocking output when invariants fail.",
    workflowTrace: "Collaboration trace",
    grounded: "Grounded",
    notGrounded: "Insufficient evidence",
    completed: "Completed",
    blocked: "Blocked",
    runId: "Run ID",
    exportRun: "Download sanitized run JSON",
    exportPrivacy: "Exports only the completed collaboration response. It excludes your question, profile, provider settings, and hidden browser state.",
    copyAnswer: "Copy answer",
    copySources: "Copy sources",
    copyAnswerSuccess: "Answer copied to clipboard.",
    copySourcesSuccess: "Sources copied to clipboard.",
    copyFailure: "Copy failed. Select and copy the text manually.",
    footer:
      "Prompts are untrusted input. Review your documents before publishing and never commit secrets.",
  },
  "zh-CN": {
    language: "语言",
    projectLabel: "开源参考实现",
    title: "检查可审计的 RAG 工作流。",
    intro:
      "运行本地检索，或检查包含类型化交接、证据来源、审查与验证的角色工作流。",
    formLabel: "向示例知识库提问",
    placeholder: "示例 Agent 如何规划一个项目？",
    searching: "正在检索…",
    ask: "提问",
    answer: "回答",
    groundingSources: "依据来源",
    noSources: "未找到匹配的来源片段。",
    inputPrivacyUnconfirmed: "尚未确认是否使用外部模型服务；问题可能会转发给已配置的服务。",
    inputPrivacyLocal: "问题由当前部署处理，不会发送给外部模型服务。",
    inputPrivacyProvider: "问题、近期对话历史和检索到的上下文会转发给当前配置的模型服务。",
    characters: "字符",
    requestFailed: "请求失败",
    extractiveMode: "本地抽取",
    providerMode: "模型服务",
    collaborationModeLabel: "基于角色的多 Agent",
    verifiedModeLabel: "已验证多 Agent",
    workflowMode: "工作流",
    standardWorkflow: "标准问答",
    collaborationWorkflow: "基于角色的多 Agent",
    verifiedWorkflow: "已验证多 Agent",
    collaborationHint: "依次运行规划、研究、审查和写作角色，并展示类型化、可检查的交接记录。",
    verifiedHint: "增加最终验证器，检查引用路径和回答元数据；验证失败时阻止输出。",
    workflowTrace: "协作轨迹",
    grounded: "已有依据",
    notGrounded: "依据不足",
    completed: "已完成",
    blocked: "已阻止",
    runId: "运行 ID",
    exportRun: "下载脱敏运行记录 JSON",
    exportPrivacy: "仅导出已完成的协作响应，不包含你的问题、个人资料、模型服务设置或浏览器隐藏状态。",
    copyAnswer: "复制回答",
    copySources: "复制来源",
    copyAnswerSuccess: "回答已复制到剪贴板。",
    copySourcesSuccess: "来源已复制到剪贴板。",
    copyFailure: "复制失败，请手动选择并复制文本。",
    footer: "提示词是不可信输入。发布前请检查文档，切勿提交任何密钥。",
  },
  "zh-TW": {
    language: "語言",
    projectLabel: "開源參考實作",
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
    inputPrivacyUnconfirmed: "尚未確認是否使用外部模型服務；問題可能會轉送給已設定的服務。",
    inputPrivacyLocal: "問題由目前部署處理，不會傳送給外部模型服務。",
    inputPrivacyProvider: "問題、近期對話記錄和檢索到的內容會轉送給目前設定的模型服務。",
    characters: "字元",
    requestFailed: "請求失敗",
    extractiveMode: "本機擷取",
    providerMode: "模型服務",
    collaborationModeLabel: "角色式多 Agent",
    verifiedModeLabel: "已驗證多 Agent",
    workflowMode: "工作流程",
    standardWorkflow: "標準問答",
    collaborationWorkflow: "角色式多 Agent",
    verifiedWorkflow: "已驗證多 Agent",
    collaborationHint: "依序執行規劃、研究、審查與寫作角色，並顯示具型別且可檢查的交接紀錄。",
    verifiedHint: "加入最終驗證器，檢查引用路徑與回答中繼資料；驗證失敗時阻擋輸出。",
    workflowTrace: "協作軌跡",
    grounded: "已有依據",
    notGrounded: "依據不足",
    completed: "已完成",
    blocked: "已阻擋",
    runId: "執行 ID",
    exportRun: "下載已清理的執行記錄 JSON",
    exportPrivacy: "只匯出已完成的協作回應，不包含你的問題、個人資料、模型服務設定或瀏覽器隱藏狀態。",
    copyAnswer: "複製回答",
    copySources: "複製來源",
    copyAnswerSuccess: "回答已複製到剪貼簿。",
    copySourcesSuccess: "來源已複製到剪貼簿。",
    copyFailure: "複製失敗，請手動選取並複製文字。",
    footer: "提示詞是不受信任的輸入。發布前請檢查文件，切勿提交任何密鑰。",
  },
  ja: {
    language: "言語",
    projectLabel: "オープンソース参照実装",
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
    inputPrivacyUnconfirmed:
      "外部モデルプロバイダーの使用は未確認です。質問が設定済みプロバイダーに転送される場合があります。",
    inputPrivacyLocal:
      "質問はこのデプロイで処理され、外部モデルプロバイダーには送信されません。",
    inputPrivacyProvider:
      "質問、最近の会話履歴、取得したコンテキストは、設定済みのモデルプロバイダーに転送されます。",
    characters: "文字",
    requestFailed: "リクエストに失敗しました",
    extractiveMode: "ローカル抽出",
    providerMode: "モデルプロバイダー",
    collaborationModeLabel: "ロールベース・マルチエージェント",
    verifiedModeLabel: "検証付きマルチエージェント",
    workflowMode: "ワークフロー",
    standardWorkflow: "標準 Q&A",
    collaborationWorkflow: "ロールベース・マルチエージェント",
    verifiedWorkflow: "検証付きマルチエージェント",
    collaborationHint:
      "プランナー、リサーチャー、批評者、ライターを順に実行し、型付きの引き継ぎを表示します。",
    verifiedHint:
      "最後に検証役を追加し、引用パスと回答メタデータを確認して、不変条件に違反する出力をブロックします。",
    workflowTrace: "協働トレース",
    grounded: "根拠あり",
    notGrounded: "根拠不足",
    completed: "完了",
    blocked: "ブロック済み",
    runId: "実行 ID",
    exportRun: "サニタイズ済み実行 JSON をダウンロード",
    exportPrivacy: "完了した協働レスポンスのみを出力し、質問、プロフィール、プロバイダー設定、非表示のブラウザー状態は含みません。",
    copyAnswer: "回答をコピー",
    copySources: "ソースをコピー",
    copyAnswerSuccess: "回答をクリップボードにコピーしました。",
    copySourcesSuccess: "ソースをクリップボードにコピーしました。",
    copyFailure: "コピーに失敗しました。テキストを選択して手動でコピーしてください。",
    footer:
      "プロンプトは信頼できない入力です。公開前に文書を確認し、秘密情報をコミットしないでください。",
  },
  ko: {
    language: "언어",
    projectLabel: "오픈 소스 참조 구현",
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
    inputPrivacyUnconfirmed:
      "외부 모델 공급자 사용 여부가 확인되지 않았습니다. 질문이 구성된 공급자에게 전달될 수 있습니다.",
    inputPrivacyLocal: "질문은 이 배포 환경에서 처리되며 외부 모델 공급자에게 전송되지 않습니다.",
    inputPrivacyProvider:
      "질문, 최근 대화 기록 및 검색된 컨텍스트가 구성된 모델 공급자에게 전달됩니다.",
    characters: "자",
    requestFailed: "요청 실패",
    extractiveMode: "로컬 추출",
    providerMode: "모델 공급자",
    collaborationModeLabel: "역할 기반 멀티 에이전트",
    verifiedModeLabel: "검증된 멀티 에이전트",
    workflowMode: "워크플로",
    standardWorkflow: "표준 Q&A",
    collaborationWorkflow: "역할 기반 멀티 에이전트",
    verifiedWorkflow: "검증된 멀티 에이전트",
    collaborationHint:
      "계획자, 조사자, 비평가, 작성자 역할을 순서대로 실행하고 형식화된 인계 기록을 표시합니다.",
    verifiedHint:
      "마지막 검증자가 인용 경로와 답변 메타데이터를 확인하고 불변 조건을 위반한 출력을 차단합니다.",
    workflowTrace: "협업 추적",
    grounded: "근거 있음",
    notGrounded: "근거 부족",
    completed: "완료",
    blocked: "차단됨",
    runId: "실행 ID",
    exportRun: "정리된 실행 JSON 다운로드",
    exportPrivacy: "완료된 협업 응답만 내보내며 질문, 프로필, 공급자 설정 및 숨겨진 브라우저 상태는 제외합니다.",
    copyAnswer: "답변 복사",
    copySources: "출처 복사",
    copyAnswerSuccess: "답변이 클립보드에 복사되었습니다.",
    copySourcesSuccess: "출처가 클립보드에 복사되었습니다.",
    copyFailure: "복사에 실패했습니다. 텍스트를 직접 선택해 복사하세요.",
    footer:
      "프롬프트는 신뢰할 수 없는 입력입니다. 게시 전에 문서를 검토하고 비밀 정보를 커밋하지 마세요.",
  },
  es: {
    language: "Idioma",
    projectLabel: "IMPLEMENTACIÓN DE REFERENCIA",
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
    inputPrivacyUnconfirmed:
      "No se ha confirmado el uso de un proveedor externo. Las preguntas pueden reenviarse a un proveedor configurado.",
    inputPrivacyLocal:
      "Las preguntas se procesan en este despliegue y no se envían a un proveedor de modelos externo.",
    inputPrivacyProvider:
      "Las preguntas, el historial reciente y el contexto recuperado se reenvían al proveedor de modelos configurado.",
    characters: "caracteres",
    requestFailed: "La solicitud ha fallado",
    extractiveMode: "extractivo local",
    providerMode: "proveedor",
    collaborationModeLabel: "multiagente basado en roles",
    verifiedModeLabel: "multiagente verificado",
    workflowMode: "Flujo de trabajo",
    standardWorkflow: "Preguntas y respuestas",
    collaborationWorkflow: "Multiagente basado en roles",
    verifiedWorkflow: "Multiagente verificado",
    collaborationHint:
      "Ejecuta los roles de planificación, investigación, crítica y redacción con entregas tipadas e inspeccionables.",
    verifiedHint:
      "Añade un verificador final que comprueba rutas de citas y metadatos, bloqueando salidas que incumplan las invariantes.",
    workflowTrace: "Traza de colaboración",
    grounded: "Fundamentado",
    notGrounded: "Evidencia insuficiente",
    completed: "Completado",
    blocked: "Bloqueado",
    runId: "ID de ejecución",
    exportRun: "Descargar JSON de ejecución depurado",
    exportPrivacy: "Exporta solo la respuesta de colaboración terminada; excluye la pregunta, el perfil, la configuración del proveedor y el estado oculto del navegador.",
    copyAnswer: "Copiar respuesta",
    copySources: "Copiar fuentes",
    copyAnswerSuccess: "Respuesta copiada al portapapeles.",
    copySourcesSuccess: "Fuentes copiadas al portapapeles.",
    copyFailure: "No se pudo copiar. Selecciona y copia el texto manualmente.",
    footer:
      "Los prompts son entradas no confiables. Revisa tus documentos antes de publicarlos y nunca confirmes secretos.",
  },
  fr: {
    language: "Langue",
    projectLabel: "IMPLÉMENTATION DE RÉFÉRENCE",
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
    inputPrivacyUnconfirmed:
      "L’utilisation d’un fournisseur externe n’est pas confirmée. Les questions peuvent être transmises à un fournisseur configuré.",
    inputPrivacyLocal:
      "Les questions sont traitées par ce déploiement et ne sont pas envoyées à un fournisseur de modèle externe.",
    inputPrivacyProvider:
      "Les questions, l’historique récent et le contexte récupéré sont transmis au fournisseur de modèle configuré.",
    characters: "caractères",
    requestFailed: "Échec de la requête",
    extractiveMode: "extraction locale",
    providerMode: "fournisseur",
    collaborationModeLabel: "multi-agent par rôles",
    verifiedModeLabel: "multi-agent vérifié",
    workflowMode: "Flux de travail",
    standardWorkflow: "Questions-réponses standard",
    collaborationWorkflow: "Multi-agent par rôles",
    verifiedWorkflow: "Multi-agent vérifié",
    collaborationHint:
      "Exécute les rôles de planification, recherche, critique et rédaction avec des transmissions typées et inspectables.",
    verifiedHint:
      "Ajoute un vérificateur final pour les chemins de citation et les métadonnées, puis bloque toute sortie non conforme.",
    workflowTrace: "Trace de collaboration",
    grounded: "Fondé sur les sources",
    notGrounded: "Preuves insuffisantes",
    completed: "Terminé",
    blocked: "Bloqué",
    runId: "ID d’exécution",
    exportRun: "Télécharger le JSON d’exécution épuré",
    exportPrivacy: "Exporte uniquement la réponse de collaboration terminée, sans la question, le profil, les réglages du fournisseur ni l’état caché du navigateur.",
    copyAnswer: "Copier la réponse",
    copySources: "Copier les sources",
    copyAnswerSuccess: "Réponse copiée dans le presse-papiers.",
    copySourcesSuccess: "Sources copiées dans le presse-papiers.",
    copyFailure: "Échec de la copie. Sélectionnez et copiez le texte manuellement.",
    footer:
      "Les prompts sont des entrées non fiables. Vérifiez vos documents avant publication et ne validez jamais de secrets.",
  },
  de: {
    language: "Sprache",
    projectLabel: "OPEN-SOURCE-REFERENZIMPLEMENTIERUNG",
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
    inputPrivacyUnconfirmed:
      "Die Nutzung eines externen Modellanbieters ist nicht bestätigt. Fragen können an einen konfigurierten Anbieter weitergeleitet werden.",
    inputPrivacyLocal:
      "Fragen werden in dieser Bereitstellung verarbeitet und nicht an einen externen Modellanbieter gesendet.",
    inputPrivacyProvider:
      "Fragen, der letzte Gesprächsverlauf und abgerufener Kontext werden an den konfigurierten Modellanbieter weitergeleitet.",
    characters: "Zeichen",
    requestFailed: "Anfrage fehlgeschlagen",
    extractiveMode: "lokale Extraktion",
    providerMode: "Modellanbieter",
    collaborationModeLabel: "rollenbasierter Multi-Agent",
    verifiedModeLabel: "verifiziertes Multi-Agent-System",
    workflowMode: "Arbeitsablauf",
    standardWorkflow: "Standard-Q&A",
    collaborationWorkflow: "Rollenbasierter Multi-Agent",
    verifiedWorkflow: "Verifiziertes Multi-Agent-System",
    collaborationHint:
      "Führt Planer, Recherche, Kritik und Redaktion mit typisierten, prüfbaren Übergaben aus.",
    verifiedHint:
      "Ergänzt einen abschließenden Prüfer für Zitatpfade und Antwortmetadaten und blockiert Ausgaben bei verletzten Invarianten.",
    workflowTrace: "Zusammenarbeitsprotokoll",
    grounded: "Quellengestützt",
    notGrounded: "Unzureichende Belege",
    completed: "Abgeschlossen",
    blocked: "Blockiert",
    runId: "Lauf-ID",
    exportRun: "Bereinigten Lauf als JSON herunterladen",
    exportPrivacy: "Exportiert nur die abgeschlossene Kollaborationsantwort; Frage, Profil, Anbieter-Einstellungen und verborgener Browserstatus werden ausgeschlossen.",
    copyAnswer: "Antwort kopieren",
    copySources: "Quellen kopieren",
    copyAnswerSuccess: "Antwort in die Zwischenablage kopiert.",
    copySourcesSuccess: "Quellen in die Zwischenablage kopiert.",
    copyFailure: "Kopieren fehlgeschlagen. Text bitte manuell markieren und kopieren.",
    footer:
      "Prompts sind nicht vertrauenswürdige Eingaben. Prüfe Dokumente vor der Veröffentlichung und committe niemals Geheimnisse.",
  },
  "pt-BR": {
    language: "Idioma",
    projectLabel: "IMPLEMENTAÇÃO DE REFERÊNCIA",
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
    inputPrivacyUnconfirmed:
      "O uso de provedor externo não foi confirmado. As perguntas podem ser encaminhadas a um provedor configurado.",
    inputPrivacyLocal:
      "As perguntas são processadas nesta implantação e não são enviadas a um provedor de modelo externo.",
    inputPrivacyProvider:
      "As perguntas, o histórico recente e o contexto recuperado são encaminhados ao provedor de modelo configurado.",
    characters: "caracteres",
    requestFailed: "Falha na solicitação",
    extractiveMode: "extração local",
    providerMode: "provedor",
    collaborationModeLabel: "multiagente baseado em papéis",
    verifiedModeLabel: "multiagente verificado",
    workflowMode: "Fluxo de trabalho",
    standardWorkflow: "Perguntas e respostas",
    collaborationWorkflow: "Multiagente baseado em papéis",
    verifiedWorkflow: "Multiagente verificado",
    collaborationHint:
      "Executa os papéis de planejamento, pesquisa, crítica e redação com transferências tipadas e inspecionáveis.",
    verifiedHint:
      "Adiciona um verificador final para caminhos de citação e metadados, bloqueando saídas que violem as invariantes.",
    workflowTrace: "Rastro de colaboração",
    grounded: "Fundamentado",
    notGrounded: "Evidências insuficientes",
    completed: "Concluído",
    blocked: "Bloqueado",
    runId: "ID da execução",
    exportRun: "Baixar JSON sanitizado da execução",
    exportPrivacy: "Exporta somente a resposta de colaboração concluída; exclui a pergunta, o perfil, as configurações do provedor e o estado oculto do navegador.",
    copyAnswer: "Copiar resposta",
    copySources: "Copiar fontes",
    copyAnswerSuccess: "Resposta copiada para a área de transferência.",
    copySourcesSuccess: "Fontes copiadas para a área de transferência.",
    copyFailure: "Falha ao copiar. Selecione e copie o texto manualmente.",
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
