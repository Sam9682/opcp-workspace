import api from './api';

export interface Task {
  id: string;
  title: string;
  description?: string;
  start_date: string;
  end_date: string;
  location?: string;
  owner_id: string;
  assigned_user_ids?: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CreateTaskRequest {
  title: string;
  description?: string;
  start_date: string;
  end_date: string;
  location?: string;
  // Mandatory owner; when omitted the backend defaults it to the creator.
  owner_id?: string;
  // Full set of users to assign; empty array keeps the task private to owner + admins.
  assigned_user_ids?: string[];
}

export interface UpdateTaskRequest {
  title?: string;
  description?: string;
  start_date?: string;
  end_date?: string;
  location?: string;
  owner_id?: string;
  // Full replacement set; send [] to clear all assignments.
  assigned_user_ids?: string[];
}

export const taskService = {
  async listTasks(): Promise<Task[]> {
    const response = await api.get('/tasks');
    return response.data.tasks;
  },

  async createTask(data: CreateTaskRequest): Promise<void> {
    await api.post('/tasks', data);
  },

  async updateTask(taskId: string, data: UpdateTaskRequest): Promise<void> {
    await api.put(`/tasks/${taskId}`, data);
  },

  async deleteTask(taskId: string): Promise<void> {
    await api.put(`/tasks/${taskId}/cancel`);
  },
};
