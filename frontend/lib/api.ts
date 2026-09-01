import axios from "axios";

import { API_BASE_URL } from "@/lib/config";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: {
    "Content-Type": "application/json",
  },
});

export type HealthResponse = {
  status: string;
  app: string;
};

/** Call FastAPI ``GET /health`` and return the typed payload. */
export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>("/health");
  return data;
}
