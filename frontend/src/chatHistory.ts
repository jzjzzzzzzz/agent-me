import type { ChatResponse, ChatTurn } from "./api";

export type ConversationTurn = { question: string; response: ChatResponse };

export function chatHistory(
  conversation: ConversationTurn[],
  maxChars: number,
  maxTurnChars: number,
): ChatTurn[] {
  const result: ChatTurn[] = [];
  let remaining = maxChars;
  // Keep recent complete exchanges; the API accepts at most 20 history messages.
  for (const turn of conversation.slice(-10).reverse()) {
    const question = Array.from(turn.question);
    if (question.length > maxTurnChars || question.length + 1 > remaining) break;
    const answer = Array.from(turn.response.answer)
      .slice(0, Math.min(maxTurnChars, remaining - question.length));
    if (!answer.length) break;
    result.unshift(
      { role: "user", content: turn.question },
      { role: "assistant", content: answer.join("") },
    );
    remaining -= question.length + answer.length;
  }
  return result;
}
