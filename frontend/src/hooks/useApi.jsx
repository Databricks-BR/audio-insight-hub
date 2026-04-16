const BASE = '/api';

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API Error');
  }
  const contentType = res.headers.get('content-type');
  if (contentType?.includes('application/pdf')) return res.blob();
  return res.json();
}

export function useApi() {
  const fetchStats = () => apiFetch('/dashboard/stats');
  const fetchCategories = () => apiFetch('/categories');
  const createCategory = (data) => apiFetch('/categories', { method: 'POST', body: JSON.stringify(data) });
  const updateCategory = (id, data) => apiFetch(`/categories/${id}`, { method: 'PUT', body: JSON.stringify(data) });
  const deleteCategory = (id) => apiFetch(`/categories/${id}`, { method: 'DELETE' });

  const uploadAudio = (file, categoryIds, onProgress) => {
    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('category_ids', (categoryIds || []).join(','));
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${BASE}/audio/upload`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
        else { try { reject(new Error(JSON.parse(xhr.responseText).detail)); } catch { reject(new Error('Upload failed')); } }
      };
      xhr.onerror = () => reject(new Error('Network error'));
      xhr.send(formData);
    });
  };

  const listVolumeFiles = (path) => apiFetch(`/volume/list?path=${encodeURIComponent(path)}`);
  const processBatch = (volumePath, categoryIds) =>
    apiFetch('/audio/batch', { method: 'POST', body: JSON.stringify({ volume_path: volumePath, category_ids: categoryIds || [] }) });
  const getAudioStreamUrl = (path) => `${BASE}/audio/stream?path=${encodeURIComponent(path)}`;

  const fetchAnalyses = (params = {}) => {
    const qs = new URLSearchParams();
    if (params.category_id) qs.set('category_id', params.category_id);
    if (params.sentiment) qs.set('sentiment', params.sentiment);
    if (params.search) qs.set('search', params.search);
    return apiFetch(`/analyses?${qs.toString()}`);
  };
  const fetchAnalysis = (id) => apiFetch(`/analyses/${id}`);
  const deleteAnalysis = (id) => apiFetch(`/analyses/${id}`, { method: 'DELETE' });
  const deleteAllAnalyses = () => apiFetch('/analyses', { method: 'DELETE' });

  const exportPdf = (id) => apiFetch(`/export/pdf/${id}`);
  const exportAllPdf = () => apiFetch('/export/pdf/all');

  const fetchModels = () => apiFetch('/models');
  const fetchSettings = () => apiFetch('/settings');
  const updateSetting = (key, value) => apiFetch('/settings', { method: 'PUT', body: JSON.stringify({ key, value }) });

  return {
    fetchStats, fetchCategories, createCategory, updateCategory, deleteCategory,
    uploadAudio, listVolumeFiles, processBatch, getAudioStreamUrl,
    fetchAnalyses, fetchAnalysis, deleteAnalysis, deleteAllAnalyses,
    exportPdf, exportAllPdf, fetchModels, fetchSettings, updateSetting,
  };
}
