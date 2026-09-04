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
}

export interface WidgetConfig {
  business_name: string;
  welcome_message: string;
}

export type ChatMessage =
  | { role: "user"; text: string }
  | { role: "bot"; response: BotResponse };
