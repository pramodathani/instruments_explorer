import { LiveSocket } from './liveSocket';
import { QuoteStore } from './quoteStore';

export const quoteStore = new QuoteStore();
export const liveSocket = new LiveSocket(quoteStore);
