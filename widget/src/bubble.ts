import { PREFIX } from "./styles";

export function createBubble(onClick: () => void): HTMLButtonElement {
  const bubble = document.createElement("button");
  bubble.className = `${PREFIX}-bubble`;
  bubble.setAttribute("aria-label", "Open chat");
  bubble.textContent = "💬";
  bubble.onclick = onClick;
  return bubble;
}
