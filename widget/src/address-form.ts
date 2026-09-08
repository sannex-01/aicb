import { PREFIX } from "./styles";

export interface AddressFormResult {
  street: string;
  city: string;
  state: string;
  zip: string;
  country: string;
}

// Mirrors app/commerce/address.py's NIGERIAN_STATES/SUPPORTED_COUNTRIES —
// the widget gets real <select> dropdowns (no free-text parsing needed,
// unlike Telegram/WhatsApp's one-message flow), so keep this list in sync
// with the backend's if that ever changes.
const NIGERIAN_STATES = [
  "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
  "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
  "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi",
  "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun",
  "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara",
];
const SUPPORTED_COUNTRIES = ["Nigeria", "Ghana", "Kenya", "South Africa"];

function textField(
  label: string,
  inputName: string,
  autocomplete: AutoFill
): { wrap: HTMLDivElement; input: HTMLInputElement } {
  const wrap = document.createElement("div");
  wrap.className = `${PREFIX}-profile-field`;
  const lbl = document.createElement("label");
  lbl.textContent = label;
  const id = `${PREFIX}-addr-${inputName}`;
  lbl.htmlFor = id;
  const input = document.createElement("input");
  input.id = id;
  input.name = inputName;
  input.type = "text";
  input.autocomplete = autocomplete;
  input.required = true;
  wrap.appendChild(lbl);
  wrap.appendChild(input);
  return { wrap, input };
}

function selectField(
  label: string,
  inputName: string,
  options: string[]
): { wrap: HTMLDivElement; select: HTMLSelectElement } {
  const wrap = document.createElement("div");
  wrap.className = `${PREFIX}-profile-field`;
  const lbl = document.createElement("label");
  lbl.textContent = label;
  const id = `${PREFIX}-addr-${inputName}`;
  lbl.htmlFor = id;
  const select = document.createElement("select");
  select.id = id;
  select.name = inputName;
  select.required = true;
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = `Select ${label.toLowerCase()}...`;
  placeholder.disabled = true;
  placeholder.selected = true;
  select.appendChild(placeholder);
  for (const opt of options) {
    const o = document.createElement("option");
    o.value = opt;
    o.textContent = opt;
    select.appendChild(o);
  }
  wrap.appendChild(lbl);
  wrap.appendChild(select);
  return { wrap, select };
}

/**
 * A native <form> shown before checkout when the cart contains at least one
 * item needing delivery (see FlowEngine.cart_requires_shipping /
 * BotResponse.requires_widget_form === "address"). Unlike Telegram/WhatsApp's
 * single free-text message (parsed and cross-checked against a country/state
 * list — see app/commerce/address.py), the widget gets real structured
 * fields since a proper form is available here. Resolves with the submitted
 * address, or null if the visitor cancels back to the cart.
 */
export function renderAddressForm(
  onDone: (result: AddressFormResult | null) => void
): HTMLFormElement {
  const form = document.createElement("form");
  form.className = `${PREFIX}-profile-form`;
  form.autocomplete = "on";

  const heading = document.createElement("h3");
  heading.textContent = "Delivery address";
  const sub = document.createElement("p");
  sub.textContent = "This order needs to be shipped — where should we send it?";
  form.appendChild(heading);
  form.appendChild(sub);

  const streetField = textField("Street address", "street", "street-address");
  const cityField = textField("City", "city", "address-level2");
  const stateField = selectField("State", "state", NIGERIAN_STATES);
  const zipField = textField("Zip / Postal code", "zip", "postal-code");
  const countryField = selectField("Country", "country", SUPPORTED_COUNTRIES);
  countryField.select.value = "Nigeria";

  form.appendChild(streetField.wrap);
  form.appendChild(cityField.wrap);
  form.appendChild(stateField.wrap);
  form.appendChild(zipField.wrap);
  form.appendChild(countryField.wrap);

  const actions = document.createElement("div");
  actions.className = `${PREFIX}-profile-actions`;
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = `${PREFIX}-profile-skip`;
  cancelBtn.textContent = "Back to Cart";
  cancelBtn.onclick = () => onDone(null);
  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.className = `${PREFIX}-profile-submit`;
  submitBtn.textContent = "Continue to Checkout";
  actions.appendChild(cancelBtn);
  actions.appendChild(submitBtn);
  form.appendChild(actions);

  form.onsubmit = (e) => {
    e.preventDefault();
    const street = streetField.input.value.trim();
    const city = cityField.input.value.trim();
    const state = stateField.select.value.trim();
    const zip = zipField.input.value.trim();
    const country = countryField.select.value.trim();
    if (!street || !city || !state || !zip || !country) return;
    onDone({ street, city, state, zip, country });
  };

  return form;
}
