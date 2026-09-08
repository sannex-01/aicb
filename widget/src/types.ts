export interface ResponseButton {
  id: string;
  title: string;
  kind: "action" | "url";
  url?: string | null;
}

export interface ProductCard {
  id: number;
  title: string;
  description?: string | null;
  price: number;
  currency: string;
  image_url?: string | null;
  buy_action_id: string;
}

export interface BotResponse {
  text: string;
  buttons: ResponseButton[];
  product_cards: ProductCard[];
  quick_replies: string[];
  checkout_url?: string | null;
  end_session: boolean;
  /** Widget-only: tells the panel to render a structured form instead of
   * just text+buttons. Telegram/WhatsApp never send this (they collect the
   * same data via free-text chat turns instead). */
  requires_widget_form?: "address" | null;
}

export interface WidgetConfig {
  business_name: string;
  welcome_message: string;
  profile_collection_mode: "upfront" | "checkout";
}

export type ChatMessage =
  | { role: "user"; text: string }
  | { role: "bot"; response: BotResponse };
