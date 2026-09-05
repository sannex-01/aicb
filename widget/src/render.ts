import type { BotResponse, ProductCard, ResponseButton } from "./types";
import { PREFIX } from "./styles";
import { formatMessageHtml } from "./format";

export interface RenderHandlers {
  onAction: (actionId: string) => void;
  onQuickReply: (text: string) => void;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

/** Removes every button/quick-reply from a rendered turn once one of them
 * is clicked (matches Telegram editing its inline keyboard away after a
 * tap) so a customer can't re-trigger a stale action from an earlier point
 * in the conversation — e.g. tapping "Buy" twice on a product shown three
 * messages ago. Plain button/quick-reply rows are removed entirely since
 * nothing useful is left in them; a product card keeps its image/title/
 * price and only its Buy button is removed. */
function removeTurnButtons(turnEl: HTMLElement): void {
  turnEl.querySelectorAll(`.${PREFIX}-buttons`).forEach((row) => row.remove());
  turnEl.querySelectorAll(`.${PREFIX}-card-buy`).forEach((btn) => btn.remove());
}

function renderButtons(buttons: ResponseButton[], handlers: RenderHandlers, turnEl: HTMLElement): HTMLElement | null {
  if (!buttons.length) return null;
  const row = el("div", `${PREFIX}-buttons`);
  for (const b of buttons) {
    if (b.kind === "url" && b.url) {
      const a = el("a", `${PREFIX}-btn`);
      a.textContent = b.title;
      a.href = b.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      row.appendChild(a);
    } else {
      const btn = el("button", `${PREFIX}-btn`);
      btn.textContent = b.title;
      btn.onclick = () => {
        removeTurnButtons(turnEl);
        handlers.onAction(b.id);
      };
      row.appendChild(btn);
    }
  }
  return row;
}

function renderProductCard(card: ProductCard, handlers: RenderHandlers, turnEl: HTMLElement): HTMLElement {
  const wrap = el("div", `${PREFIX}-card`);

  if (card.image_url) {
    const img = el("img");
    img.src = card.image_url;
    img.alt = card.title;
    img.onerror = () => {
      img.replaceWith(placeholderImage());
    };
    wrap.appendChild(img);
  } else {
    wrap.appendChild(placeholderImage());
  }

  const body = el("div", `${PREFIX}-card-body`);
  const title = el("div", `${PREFIX}-card-title`);
  title.textContent = card.title;
  const price = el("div", `${PREFIX}-card-price`);
  price.textContent = `${card.price.toLocaleString()} ${card.currency}`;
  const buyBtn = el("button", `${PREFIX}-card-buy`);
  buyBtn.textContent = "Buy";
  buyBtn.onclick = () => {
    removeTurnButtons(turnEl);
    handlers.onAction(card.buy_action_id);
  };

  body.appendChild(title);
  body.appendChild(price);
  body.appendChild(buyBtn);
  wrap.appendChild(body);
  return wrap;
}

function placeholderImage(): HTMLElement {
  const ph = el("div", `${PREFIX}-card-placeholder`);
  ph.textContent = "No image";
  return ph;
}

function renderQuickReplies(replies: string[], handlers: RenderHandlers, turnEl: HTMLElement): HTMLElement | null {
  if (!replies.length) return null;
  const row = el("div", `${PREFIX}-buttons`);
  for (const r of replies) {
    const btn = el("button", `${PREFIX}-btn`);
    btn.textContent = r;
    btn.onclick = () => {
      removeTurnButtons(turnEl);
      handlers.onQuickReply(r);
    };
    row.appendChild(btn);
  }
  return row;
}

/** Renders a user's own text message. */
export function renderUserMessage(text: string): HTMLElement {
  const bubble = el("div", `${PREFIX}-bubble-msg user`);
  bubble.textContent = text;
  return bubble;
}

/** Renders a bot turn (text, product cards, buttons, quick replies) as a
 * single wrapping element ready to append to the message list. Wrapped
 * (rather than a bare DocumentFragment) so its own buttons can be found
 * and removed once clicked — matching Telegram's inline keyboard being
 * edited away after a tap, so a customer can't re-trigger a stale action
 * from earlier in the conversation. */
export function renderBotResponse(resp: BotResponse, handlers: RenderHandlers): HTMLElement {
  const turnEl = el("div", `${PREFIX}-turn`);

  if (resp.text) {
    const bubble = el("div", `${PREFIX}-bubble-msg bot`);
    bubble.innerHTML = formatMessageHtml(resp.text);
    turnEl.appendChild(bubble);
  }

  if (resp.product_cards.length) {
    const cards = el("div", `${PREFIX}-cards`);
    for (const card of resp.product_cards) {
      cards.appendChild(renderProductCard(card, handlers, turnEl));
    }
    turnEl.appendChild(cards);
  }

  // Product cards already carry their own Buy button — drop any button in the
  // flat list whose action a card already covers, so the two aren't shown
  // redundantly (this can still happen since FlowEngine populates both for
  // channels that don't render cards).
  const cardActionIds = new Set(resp.product_cards.map((c) => c.buy_action_id));
  const remainingButtons = resp.buttons.filter((b) => !cardActionIds.has(b.id));
  const buttonsRow = renderButtons(remainingButtons, handlers, turnEl);
  if (buttonsRow) turnEl.appendChild(buttonsRow);

  const quickRepliesRow = renderQuickReplies(resp.quick_replies, handlers, turnEl);
  if (quickRepliesRow) turnEl.appendChild(quickRepliesRow);

  return turnEl;
}
