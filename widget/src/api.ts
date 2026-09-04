import type { BotResponse, WidgetConfig } from "./types";

export class WidgetAPI {
  constructor(private baseUrl: string) {}

  async getConfig(): Promise<WidgetConfig> {
    const res = await fetch(`${this.baseUrl}/api/v1/widget/config`);
    return res.json();
  }

  async dispatchAction(actionId: string, sessionId: string, userInput?: string): Promise<BotResponse> {
    const res = await fetch(`${this.baseUrl}/api/v1/widget/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId, session_id: sessionId, user_input: userInput }),
    });
    return res.json();
  }

  /** One-shot submission of the upfront profile form (or a skip). */
  async submitProfile(
    sessionId: string,
    profile: { name?: string; email?: string; phone?: string } | null
  ): Promise<void> {
    await fetch(`${this.baseUrl}/api/v1/widget/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        skipped: !profile,
        name: profile?.name,
        email: profile?.email,
        phone: profile?.phone,
      }),
    });
  }

  /**
   * Streams a free-text chat message via SSE-over-POST. Native EventSource
   * doesn't support POST bodies, so this hand-rolls SSE parsing over
   * fetch + ReadableStream instead.
   */
  async streamChat(
    message: string,
    sessionId: string,
    onTextChunk: (chunk: string) => void,
    onFinal: (resp: BotResponse) => void
  ): Promise<void> {
    const res = await fetch(`${this.baseUrl}/api/v1/widget/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    if (!res.body) return;
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const dataStr = line.slice(6).trim();
        if (dataStr === "[DONE]") continue;

        try {
          const parsed = JSON.parse(dataStr);
          if (typeof parsed.content === "string") {
            onTextChunk(parsed.content);
          } else if (parsed.final) {
            onFinal(parsed.final as BotResponse);
          }
        } catch {
          // ignore partial/incomplete chunk
        }
      }
    }
  }
}
