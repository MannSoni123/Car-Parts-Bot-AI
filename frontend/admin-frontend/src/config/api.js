export const API_BASE_URL =
  import.meta.env.MODE === 'production'
    ? 'https://koncpt-ai.tech'
    : 'http://localhost:5000';

export const SSE_URL = `${API_BASE_URL}/events`;
