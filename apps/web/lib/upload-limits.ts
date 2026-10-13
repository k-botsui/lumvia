'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from './api';

export function useUploadLimits() {
  const query = useQuery({
    queryKey: ['upload-limits'],
    queryFn: () => api<{ max_upload_bytes: number; max_duration_ms: number }>('/media/upload-limits'),
  });
  return query.data ?? { max_upload_bytes: 2 * 1024 ** 3, max_duration_ms: 3600000 };
}
