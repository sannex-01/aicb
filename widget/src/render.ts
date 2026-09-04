import type { BotResponse, ProductCard, ResponseButton } from "./types";
import { PREFIX } from "./styles";

export interface RenderHandlers {
  onAction: (actionId: string) => void;
  onQuickReply: (text: string) => void;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

function renderButtons(buttons: ResponseButton[], handlers: RenderHandlers): HTMLElement | null {
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
      btn.onclick = () => handlers.onAction(b.id);
      row.appendChild(btn);
    }
  }
  return row;
}

function renderProductCard(card: ProductCard, handlers: RenderHandlers): HTMLElement {
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
  buyBtn.onclick = () => handlers.onAction(card.buy_action_id);

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

function renderQuickReplies(replies: string[], handlers: RenderHandlers): HTMLElement | null {
  if (!replies.length) return null;
  const row = el("div", `${PREFIX}-buttons`);
  for (const r of replies) {
    const btn = el("button", `${PREFIX}-btn`);
    btn.textContent = r;
    btn.onclick = () => handlers.onQuickReply(r);
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
 * fragment ready to append to the message list. */
export function renderBotResponse(resp: BotResponse, handlers: RenderHandlers): DocumentFragment {
  const frag = document.createDocumentFragment();

  if (resp.text) {
    const bubble = el("div", `${PREFIX}-bubble-msg bot`);
    bubble.textContent = resp.text;
    frag.appendChild(bubble);
  }

  if (resp.product_cards.length) {
    const cards = el("div", `${PREFIX}-cards`);
    for (const card of resp.product_cards) {
      cards.appendChild(renderProductCard(card, handlers));
    }
    frag.appendChild(cards);
  }

  // Product cards already carry their own Buy button — drop any button in the
  // flat list whose action a card already covers, so the two aren't shown
  // redundantly (this can still happen since FlowEngine populates both for
  // channels that don't render cards).
  const cardActionIds = new Set(resp.product_cards.map((c) => c.buy_action_id));
  const remainingButtons = resp.buttons.filter((b) => !cardActionIds.has(b.id));
  const buttonsRow = renderButtons(remainingButtons, handlers);
  if (buttonsRow) frag.appendChild(buttonsRow);

  const quickRepliesRow = renderQuickReplies(resp.quick_replies, handlers);
  if (quickRepliesRow) frag.appendChild(quickRepliesRow);

  return frag;
}
