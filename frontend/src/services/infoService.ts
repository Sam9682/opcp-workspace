import api from './api';

export interface Stats {
  total_users: number;
  total_events: number;
  total_topics: number;
}

export const infoService = {
  async getStats(): Promise<Stats> {
    const response = await api.get('/info/stats');
    return response.data;
  },
};
