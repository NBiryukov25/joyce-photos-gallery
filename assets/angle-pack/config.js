// The only production backend URL. No keys or passwords go here.
export const ANGLE_PACK_API_BASE = 'https://angle-pack.onrender.com';
export function apiBase(hostname=globalThis.location?.hostname){
  return ['localhost','127.0.0.1'].includes(hostname) ? 'http://127.0.0.1:3210' : ANGLE_PACK_API_BASE;
}
