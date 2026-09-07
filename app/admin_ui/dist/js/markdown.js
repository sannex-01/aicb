export function parseMarkdown(text) {
  if (!text) return '';
  let html = text;

  html = html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Bold (**text**)
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Bold (*text*) -> common in telegram/whatsapp markdown
  html = html.replace(/\*(.*?)\*/g, '<strong>$1</strong>');

  // Italic (_text_)
  html = html.replace(/_(.*?)_/g, '<em>$1</em>');

  // Strikethrough (~text~)
  html = html.replace(/~(.*?)~/g, '<del>$1</del>');

  // Inline code (`text`)
  html = html.replace(/`(.*?)`/g, '<code class="bg-black/10 dark:bg-white/20 px-1 py-0.5 rounded text-[13px] font-mono dark:text-gray-200">$1</code>');

  // Code blocks (```text```)
  html = html.replace(/```([\s\S]*?)```/g, '<pre class="bg-black/5 dark:bg-white/10 p-3 rounded-lg overflow-x-auto text-[13px] font-mono my-2 border border-subtle dark:text-gray-200"><code>$1</code></pre>');

  // Links ([text](url))
  html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-brand hover:underline">$1</a>');

  // Line breaks
  html = html.replace(/\n/g, '<br>');

  return html;
}
