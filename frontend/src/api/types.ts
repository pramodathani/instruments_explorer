/** One of the project's own stores and whether it answered. */
export interface StoreStatus {
  name: string;
  reachable: boolean;
  detail: string;
}

/** Whether the chat assistant has an API key, and which model it uses. */
export interface AssistantStatus {
  configured: boolean;
  model: string;
}

/** The answer of /api/status. */
export interface StatusDocument {
  stores: StoreStatus[];
  assistant: AssistantStatus;
}
