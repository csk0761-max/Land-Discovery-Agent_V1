import { supabase } from './supabaseClient';

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/+$/, '');
const API_TOKEN = import.meta.env.VITE_AUXILIUM_API_TOKEN || '';
const ADMIN_TOKEN = import.meta.env.VITE_AUXILIUM_ADMIN_TOKEN || '';

export function apiUrl(path) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

export async function getAuthToken() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token || API_TOKEN;
}

export function authHeaders() {
  // Note: Since this is synchronous and used in many places, 
  // we might need to handle token refresh differently if using real Supabase Auth.
  // For now, we'll try to get it from local storage directly for sync use, 
  // or use the static token as fallback.
  const supabaseProjectRef = import.meta.env.VITE_SUPABASE_URL?.split('//')[1]?.split('.')[0];
  const sessionKey = supabaseProjectRef ? `sb-${supabaseProjectRef}-auth-token` : null;
  let token = API_TOKEN;
  if (sessionKey) {
    try {
      const sessionStr = localStorage.getItem(sessionKey);
      if (!sessionStr) {
        return token ? { Authorization: `Bearer ${token}` } : {};
      }
      const session = JSON.parse(sessionStr);
      token = session.access_token || API_TOKEN;
    } catch {
      // Fall back to the static token if local session parsing fails.
    }
  }
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function adminHeaders() {
  const headers = authHeaders();
  if (!headers.Authorization && ADMIN_TOKEN) {
    headers.Authorization = `Bearer ${ADMIN_TOKEN}`;
  }
  return headers;
}

export { API_BASE_URL };
