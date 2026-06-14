import { API_BASE_URL } from './config';

async function handleResponse(response) {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData.detail || `Request failed with status ${response.status}`;
    throw new Error(errorMessage);
  }
  return response.json();
}

export const api = {
  // ── Sessions ──────────────────────────────────────────────────────────
  async getSessions(limit = 100, offset = 0) {
    const response = await fetch(`${API_BASE_URL}/sessions/?limit=${limit}&offset=${offset}`);
    return handleResponse(response);
  },

  async getSession(id) {
    const response = await fetch(`${API_BASE_URL}/sessions/${id}`);
    return handleResponse(response);
  },

  async createSession(companyName, website, objective) {
    const response = await fetch(`${API_BASE_URL}/sessions/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        company_name: companyName,
        website: website,
        objective: objective,
      }),
    });
    return handleResponse(response);
  },

  async deleteSession(id) {
    const response = await fetch(`${API_BASE_URL}/sessions/${id}`, {
      method: 'DELETE',
    });
    return handleResponse(response);
  },

  // ── Workflows ──────────────────────────────────────────────────────────
  async runWorkflow(id, forceRerun = false) {
    const response = await fetch(`${API_BASE_URL}/workflows/run/${id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        force_rerun: forceRerun,
      }),
    });
    return handleResponse(response);
  },

  async resumeWorkflow(id) {
    const response = await fetch(`${API_BASE_URL}/workflows/resume/${id}`, {
      method: 'POST',
    });
    return handleResponse(response);
  },

  async getWorkflowStatus(id) {
    const response = await fetch(`${API_BASE_URL}/workflows/status/${id}`);
    return handleResponse(response);
  },

  // ── Chat ──────────────────────────────────────────────────────────────
  async getChatHistory(id) {
    const response = await fetch(`${API_BASE_URL}/chat/${id}`);
    return handleResponse(response);
  },

  async sendChatMessage(id, message) {
    const response = await fetch(`${API_BASE_URL}/chat/${id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
      }),
    });
    return handleResponse(response);
  },

  async clearChatHistory(id) {
    const response = await fetch(`${API_BASE_URL}/chat/${id}`, {
      method: 'DELETE',
    });
    return handleResponse(response);
  },
};
