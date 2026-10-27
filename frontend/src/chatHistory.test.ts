import { expect, it } from "vitest";
import { chatHistory, type ConversationTurn } from "./chatHistory";

const turn = (question: string, answer: string): ConversationTurn => ({
  question, response: { answer, mode: "openai-compatible", sources: [] },
});

it("bounds long answers without splitting Unicode or dropping the latest question", () => {
  const result = chatHistory([turn("Old topic", "Old reply"), turn("Why?", "🙂".repeat(9000))], 10, 8);
  expect(result).toEqual([
    { role: "user", content: "Why?" },
    { role: "assistant", content: "🙂".repeat(6) },
  ]);
});

it("keeps recent exchanges in order and within the API's 20-message limit", () => {
  const history = chatHistory(Array.from({ length: 12 }, (_, i) => turn(`q${i}`, `a${i}`)), 24000, 8000);
  expect(history).toHaveLength(20);
  expect(history[0]).toEqual({ role: "user", content: "q2" });
  expect(history.at(-1)).toEqual({ role: "assistant", content: "a11" });
});
