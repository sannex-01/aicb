import { PREFIX } from "./styles";
import { WidgetAPI } from "./api";
import { renderBotResponse, renderUserMessage, type RenderHandlers } from "./render";
import type { BotResponse } from "./types";

function getOrCreateSessionId(): string {
  const key = "aicb_widget_session_id";
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}

export class WidgetPanel {
  readonly el: HTMLDivElement;
  private messagesEl: HTMLDivElement;
  private inputEl: HTMLInputElement;
  private sendBtn: HTMLButtonElement;
  private sessionId = getOrCreateSessionId();
  private api: WidgetAPI;
  private handlers: RenderHandlers;

  constructor(baseUrl: string) {
    this.api = new WidgetAPI(baseUrl);
    this.handlers = {
      onAction: (actionId) => this.dispatchAction(actionId),
      onQuickReply: (text) => this.sendMessage(text),
    };

    this.el = document.createElement("div");
    this.el.className = `${PREFIX}-panel`;
    this.el.hidden = true;

    const header = document.createElement("div");
    header.className = `${PREFIX}-header`;
    const title = document.createElement("span");
    title.textContent = "Chat with us";
    const closeBtn = document.createElement("button");
    closeBtn.textContent = "✕";
    closeBtn.setAttribute("aria-label", "Close chat");
    closeBtn.onclick = () => this.hide();
    header.appendChild(title);
    header.appendChild(closeBtn);
    this.headerTitleEl = title;

    this.messagesEl = document.createElement("div");
    this.messagesEl.className = `${PREFIX}-messages`;

    const inputRow = document.createElement("div");
    inputRow.className = `${PREFIX}-input-row`;
    this.inputEl = document.createElement("input");
    this.inputEl.type = "text";
    this.inputEl.placeholder = "Type a message...";
    this.inputEl.onkeydown = (e) => {
      if (e.key === "Enter") this.handleSend();
    };
    this.sendBtn = document.createElement("button");
    this.sendBtn.textContent = "Send";
    this.sendBtn.onclick = () => this.handleSend();
    inputRow.appendChild(this.inputEl);
    inputRow.appendChild(this.sendBtn);

    this.el.appendChild(header);
    this.el.appendChild(this.messagesEl);
    this.el.appendChild(inputRow);
  }

  private headerTitleEl: HTMLSpanElement;
  private initialized = false;

  async show(): Promise<void> {
    this.el.hidden = false;
    if (!this.initialized) {
      this.initialized = true;
      try {
        const config = await this.api.getConfig();
        this.headerTitleEl.textContent = config.business_name;
        this.appendBotResponse({
          text: config.welcome_message,
          buttons: [],
          product_cards: [],
          quick_replies: [],
          checkout_url: null,
          end_session: false,
        });
      } catch {
        this.appendBotResponse({
          text: "Hi! How can we help you today?",
          buttons: [],
          product_cards: [],
          quick_replies: [],
          checkout_url: null,
          end_session: false,
        });
      }
    }
  }

  hide(): void {
    this.el.hidden = true;
  }

  // Mirrors the fast_path_triggers list in the Telegram/WhatsApp webhooks:
  // deterministic menu/cart/checkout intents are routed to FlowEngine (0 LLM
  // tokens, works even if no LLM key is configured) instead of the AI chat
  // stream, which only handles free-form questions.
  private static readonly FAST_PATH_TRIGGERS = [
    "menu", "start", "/start", "help", "cart", "/cart", "checkout", "clear cart",
  ];

  private static isFastPath(text: string): boolean {
    const t = text.toLowerCase().trim();
    return (
      WidgetPanel.FAST_PATH_TRIGGERS.includes(t) ||
      t.startsWith("cart_") ||
      t.startsWith("flow_")
    );
  }

  private handleSend(): void {
    const text = this.inputEl.value.trim();
    if (!text) return;
    this.inputEl.value = "";

    if (WidgetPanel.isFastPath(text)) {
      this.appendUserMessage(text);
      this.dispatchAction(text);
    } else {
      this.sendMessage(text);
    }
  }

  private async dispatchAction(actionId: string): Promise<void> {
    this.setBusy(true);
    try {
      const resp = await this.api.dispatchAction(actionId, this.sessionId);
      this.appendBotResponse(resp);
      this.maybeOpenCheckout(resp);
    } finally {
      this.setBusy(false);
    }
  }

  private async sendMessage(text: string): Promise<void> {
    this.appendUserMessage(text);
    this.setBusy(true);

    const streamingBubble = document.createElement("div");
    streamingBubble.className = `${PREFIX}-bubble-msg bot`;
    this.messagesEl.appendChild(streamingBubble);
    this.scrollToBottom();

    try {
      await this.api.streamChat(
        text,
        this.sessionId,
        (chunk) => {
          streamingBubble.textContent += chunk;
          this.scrollToBottom();
        },
        (finalResp) => {
          // Streamed text already rendered incrementally above; only append
          // structured extras (product cards / buttons) from the final event.
          if (finalResp.product_cards.length || finalResp.buttons.length || finalResp.quick_replies.length) {
            const extras = renderBotResponse(
              { ...finalResp, text: "" },
              this.handlers
            );
            this.messagesEl.appendChild(extras);
          }
          this.maybeOpenCheckout(finalResp);
        }
      );
    } finally {
      this.setBusy(false);
      this.scrollToBottom();
    }
  }

  /**
   * When a turn produces a checkout_url (e.g. after "Checkout Now"), open it
   * in a new tab rather than an iframe: hosted payment pages commonly set
   * X-Frame-Options/frame-ancestors, and 3-D Secure redirects routinely
   * refuse to render inside any iframe — doubly so nested (widget iframe
   * inside an arbitrary third-party host page). This is the only reliable
   * approach across Paystack/Flutterwave/Monnify/Stripe without
   * gateway-specific handling.
   */
  private maybeOpenCheckout(resp: BotResponse): void {
    if (resp.checkout_url) {
      window.open(resp.checkout_url, "_blank", "noopener,noreferrer");
    }
  }

  private appendUserMessage(text: string): void {
    this.messagesEl.appendChild(renderUserMessage(text));
    this.scrollToBottom();
  }

  private appendBotResponse(resp: BotResponse): void {
    this.messagesEl.appendChild(renderBotResponse(resp, this.handlers));
    this.scrollToBottom();
  }

  private setBusy(busy: boolean): void {
    this.sendBtn.disabled = busy;
    this.inputEl.disabled = busy;
  }

  private scrollToBottom(): void {
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }
}
