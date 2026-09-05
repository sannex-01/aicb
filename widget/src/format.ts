/**
 * Renders the backend's lightweight markdown (the same bold/italic/bullet
 * convention already used for Telegram — see app/flows/definitions.py and
 * engine.py's response text) into safe HTML for the widget's message
 * bubbles. Escapes all raw text first, then re-introduces only the specific
 * tags this produces — never trusts backend text as HTML directly.
 */
export function formatMessageHtml(text: string): string {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  let html = escaped
    // *bold* -> <strong>, but not a lone "*" (e.g. multiplication-ish usage)
    .replace(/\*([^*\n]+)\*/g, "<strong>$1</strong>")
    // _italic_
    .replace(/_([^_\n]+)_/g, "<em>$1</em>")
    // `code`
    .replace(/`([^`\n]+)`/g, "<code>$1</code>");

  // Turn "• " / "- " list lines into an actual <ul>, line breaks elsewhere
  // become <br> so paragraph spacing still reads naturally.
  const lines = html.split("\n");
  const out: string[] = [];
  let inList = false;

  for (const line of lines) {
    const bulletMatch = line.match(/^\s*[•\-]\s+(.*)$/);
    if (bulletMatch) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${bulletMatch[1]}</li>`);
    } else {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push(line.length ? line : "<br>");
    }
  }
  if (inList) out.push("</ul>");

  return out.join("\n").replace(/\n(?!<\/?(ul|li))/g, "<br>");
}
