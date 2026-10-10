import api from './api';

export interface Event {
  id: string;
  title: string;
  description: string | null;
  start_date: string;
  end_date: string;
  location: string | null;
  max_participants: number | null;
  created_by: string;
  assigned_user_id: string | null;
  assigned_user_ids: string[];
  status: string;
  created_at: string;
  updated_at: string;
  participant_count: number;
}

export interface CreateEventRequest {
  title: string;
  description?: string;
  start_date: string;
  end_date: string;
  location?: string;
  max_participants?: number;
  // Full set of users to assign; empty array => public event.
  assigned_user_ids?: string[];
}

export interface UpdateEventRequest {
  title?: string;
  description?: string;
  start_date?: string;
  end_date?: string;
  location?: string;
  max_participants?: number;
  // Full replacement set; send [] to clear all assignments (make public).
  assigned_user_ids?: string[];
}

export const eventService = {
  async listEvents(): Promise<Event[]> {
    const response = await api.get('/events');
    return response.data.events;
  },

  async createEvent(data: CreateEventRequest): Promise<void> {
    await api.post('/events', data);
  },

  async updateEvent(eventId: string, data: UpdateEventRequest): Promise<void> {
    await api.put(`/events/${eventId}`, data);
  },

  async deleteEvent(eventId: string): Promise<void> {
    await api.put(`/events/${eventId}/cancel`);
  },
};
