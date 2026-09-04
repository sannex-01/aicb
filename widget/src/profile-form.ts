import { PREFIX } from "./styles";

export interface ProfileFormResult {
  name: string;
  email: string;
  phone: string;
}

function field(
  label: string,
  inputName: string,
  autocomplete: AutoFill,
  type: string
): { wrap: HTMLDivElement; input: HTMLInputElement } {
  const wrap = document.createElement("div");
  wrap.className = `${PREFIX}-profile-field`;
  const lbl = document.createElement("label");
  lbl.textContent = label;
  const id = `${PREFIX}-field-${inputName}`;
  lbl.htmlFor = id;
  const input = document.createElement("input");
  input.id = id;
  input.name = inputName;
  input.type = type;
  input.autocomplete = autocomplete;
  input.required = true;
  wrap.appendChild(lbl);
  wrap.appendChild(input);
  return { wrap, input };
}

/**
 * A native <form> shown immediately on panel open so the browser's own
 * autofill (name/email/tel heuristics via `autocomplete`) can populate it in
 * one shot, rather than asking for each field one-by-one over chat turns.
 * Resolves with the submitted values, or null if the visitor skips.
 */
export function renderProfileForm(
  businessName: string,
  onDone: (result: ProfileFormResult | null) => void
): HTMLFormElement {
  const form = document.createElement("form");
  form.className = `${PREFIX}-profile-form`;
  form.autocomplete = "on";

  const heading = document.createElement("h3");
  heading.textContent = "Before we get started";
  const sub = document.createElement("p");
  sub.textContent = `Share your details so ${businessName} can send receipts and track your orders.`;
  form.appendChild(heading);
  form.appendChild(sub);

  const nameField = field("Full name", "name", "name", "text");
  const emailField = field("Email", "email", "email", "email");
  const phoneField = field("Phone number", "tel", "tel", "tel");
  form.appendChild(nameField.wrap);
  form.appendChild(emailField.wrap);
  form.appendChild(phoneField.wrap);

  const actions = document.createElement("div");
  actions.className = `${PREFIX}-profile-actions`;
  const skipBtn = document.createElement("button");
  skipBtn.type = "button";
  skipBtn.className = `${PREFIX}-profile-skip`;
  skipBtn.textContent = "Skip for now";
  skipBtn.onclick = () => onDone(null);
  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.className = `${PREFIX}-profile-submit`;
  submitBtn.textContent = "Continue";
  actions.appendChild(skipBtn);
  actions.appendChild(submitBtn);
  form.appendChild(actions);

  form.onsubmit = (e) => {
    e.preventDefault();
    const name = nameField.input.value.trim();
    const email = emailField.input.value.trim();
    const phone = phoneField.input.value.trim();
    if (!name || !email || !phone) return;
    onDone({ name, email, phone });
  };

  return form;
}
