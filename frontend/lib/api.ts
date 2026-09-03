import axios from "axios";
import type { AxiosProgressEvent } from "axios";

import { API_BASE_URL } from "@/lib/config";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60_000,
  headers: {
    "Content-Type": "application/json",
  },
});

export type HealthResponse = {
  status: string;
  app: string;
};

export type IngestResponse = {
  source: string;
  document_count: number;
  chunk_count: number;
  snippets: string[];
  collection_name: string;
  stored_count: number;
};

export type ApiError = {
  message: string;
  statusCode?: number;
  details?: string[];
};

export type IngestFilePayload = {
  file: File;
  collectionName: string;
  onProgress?: (progress: number) => void;
};

export type IngestUrlPayload = {
  url: string;
  collectionName: string;
};

function normalizeDetails(detail: unknown): string[] {
  if (Array.isArray(detail)) {
    return detail.map((item) => String(item));
  }
  if (typeof detail === "string") {
    return [detail];
  }
  return [];
}

export function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const responseDetail = error.response?.data?.detail;
    const details = normalizeDetails(responseDetail);
    return {
      message:
        details[0] ??
        error.message ??
        "The request failed due to an unexpected network error.",
      statusCode: error.response?.status,
      details,
    };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return { message: "An unknown error occurred." };
}

/** Call FastAPI ``GET /health`` and return the typed payload. */
export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>("/health");
  return data;
}

/** Upload a PDF or CSV into a Chroma-backed collection. */
export async function ingestFile(
  payload: IngestFilePayload,
): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append("file", payload.file);
  formData.append("collection_name", payload.collectionName);

  const { data } = await apiClient.post<IngestResponse>(
    "/api/v1/ingest/file",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      onUploadProgress: (event: AxiosProgressEvent) => {
        if (!payload.onProgress || !event.total) {
          return;
        }
        const progress = Math.min(
          95,
          Math.round((event.loaded / event.total) * 100),
        );
        payload.onProgress(progress);
      },
    },
  );
  return data;
}

/** Submit a public URL for parsing, chunking, and indexing. */
export async function ingestUrl(
  payload: IngestUrlPayload,
): Promise<IngestResponse> {
  const { data } = await apiClient.post<IngestResponse>(
    "/api/v1/ingest/url",
    {
      url: payload.url,
      collection_name: payload.collectionName,
    },
  );
  return data;
}
