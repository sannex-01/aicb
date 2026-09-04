const PREFIX = "aicb-widget";

/** Injects scoped styles via JS rather than a linked stylesheet, so a
 * single <script> tag is genuinely self-contained on an arbitrary
 * third-party page (no separate CSS request, no class-name collisions). */
export function injectStyles(): void {
  if (document.getElementById(`${PREFIX}-styles`)) return;

  const style = document.createElement("style");
  style.id = `${PREFIX}-styles`;
  style.textContent = `
.${PREFIX}-bubble {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #008060;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0,0,0,0.25);
  z-index: 2147483000;
  border: none;
  font-size: 26px;
  line-height: 1;
}
.${PREFIX}-bubble:hover { filter: brightness(1.08); }

.${PREFIX}-panel {
  position: fixed;
  bottom: 88px;
  right: 20px;
  width: 360px;
  max-width: calc(100vw - 32px);
  height: 520px;
  max-height: calc(100vh - 120px);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.28);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 2147483000;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 14px;
  color: #1a1a1a;
}
.${PREFIX}-panel[hidden] { display: none; }

.${PREFIX}-header {
  background: #008060;
  color: #fff;
  padding: 14px 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.${PREFIX}-header button {
  background: none;
  border: none;
  color: #fff;
  cursor: pointer;
  font-size: 18px;
  opacity: 0.85;
}

.${PREFIX}-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #f7f8fa;
}

.${PREFIX}-bubble-msg {
  max-width: 85%;
  padding: 9px 12px;
  border-radius: 12px;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
}
.${PREFIX}-bubble-msg.user {
  align-self: flex-end;
  background: #008060;
  color: #fff;
  border-bottom-right-radius: 3px;
}
.${PREFIX}-bubble-msg.bot {
  align-self: flex-start;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-bottom-left-radius: 3px;
}

.${PREFIX}-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}
.${PREFIX}-btn {
  border: 1px solid #008060;
  color: #008060;
  background: #fff;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12.5px;
  cursor: pointer;
  text-decoration: none;
}
.${PREFIX}-btn:hover { background: #f0faf6; }

.${PREFIX}-cards {
  display: flex;
  align-items: flex-start;
  flex-shrink: 0;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.${PREFIX}-card {
  flex: 0 0 auto;
  width: 150px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}
.${PREFIX}-card img, .${PREFIX}-card-placeholder {
  width: 100%;
  height: 100px;
  object-fit: cover;
  background: #eef1f4;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9aa1a9;
  font-size: 11px;
}
.${PREFIX}-card-body { padding: 8px; }
.${PREFIX}-card-title { font-weight: 600; font-size: 12.5px; margin-bottom: 2px; }
.${PREFIX}-card-price { color: #008060; font-weight: 700; font-size: 12.5px; margin-bottom: 6px; }
.${PREFIX}-card-buy {
  width: 100%;
  background: #008060;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px;
  font-size: 12px;
  cursor: pointer;
}

.${PREFIX}-input-row {
  display: flex;
  gap: 8px;
  padding: 10px;
  border-top: 1px solid #e5e7eb;
  background: #fff;
}
.${PREFIX}-input-row input {
  flex: 1;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13.5px;
  outline: none;
}
.${PREFIX}-input-row input:focus { border-color: #008060; }
.${PREFIX}-input-row button {
  background: #008060;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 13px;
}
.${PREFIX}-input-row button:disabled { opacity: 0.5; cursor: not-allowed; }
`;
  document.head.appendChild(style);
}

export { PREFIX };
