import { apiClient } from '@/api/client';
import { HealthResponse } from '@/types/api';

export const healthApi = {
  async getHealth(): Promise<HealthResponse> {
    const response = await apiClient.get<HealthResponse>('/api/health');
    return response.data;
  },
};

