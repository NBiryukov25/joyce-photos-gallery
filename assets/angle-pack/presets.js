export const ANGLES = {
  FRONT: 'Front', LEFT_3Q: 'Left three-quarter', RIGHT_3Q: 'Right three-quarter',
  PROFILE_LEFT: 'Left profile', PROFILE_RIGHT: 'Right profile',
  REAR_3Q_LEFT: 'Rear three-quarter left', REAR_3Q_RIGHT: 'Rear three-quarter right',
  REAR: 'Rear', HIGH: 'High', LOW: 'Low', OVERHEAD: 'Overhead', EYE_LEVEL: 'Eye level', CUSTOM: 'Custom',
};
export const FRAMINGS = { FACE: 'Face', HEAD_SHOULDERS: 'Head & shoulders', CHEST: 'Chest-up', WAIST: 'Waist-up', THREE_QUARTER: 'Three-quarter body', FULL_BODY: 'Full body', WIDE: 'Wide / full available frame' };
export const PRESERVATIONS = ['FACE', 'BODY', 'HAIR', 'OUTFIT', 'ACCESSORIES', 'BACKGROUND', 'LIGHTING', 'PHOTO_STYLE'];
export const DEFAULT_PRESERVATION = Object.fromEntries(PRESERVATIONS.map(k => [k, 'HIGH']));
export function autoPack(count, represented = []) {
  const order = ['LEFT_3Q', 'RIGHT_3Q', 'PROFILE_RIGHT', 'REAR_3Q_LEFT', 'HIGH', 'LOW', 'REAR_3Q_RIGHT', 'PROFILE_LEFT', 'REAR', 'OVERHEAD', 'FRONT'];
  const ranked = [...order.filter(k => !represented.includes(k)), ...order.filter(k => represented.includes(k))];
  const families = k => k.startsWith('PROFILE') ? 'profile' : k.startsWith('REAR_3Q') ? 'rear-quarter' : ['HIGH', 'LOW', 'OVERHEAD'].includes(k) ? 'elevation' : k;
  const chosen = [], used = new Set();
  for (const k of ranked) if (!used.has(families(k))) { chosen.push(k); used.add(families(k)); if (chosen.length === count) break; }
  return chosen.map(angle => ({ angle, framing: ['HIGH','LOW','REAR_3Q_LEFT','REAR_3Q_RIGHT','REAR'].includes(angle) ? 'FULL_BODY' : 'THREE_QUARTER', custom: '', sourceIndex: 0 }));
}
export function defaultCrop(framing) {
  const sizes = { FACE: [.34,.23], HEAD_SHOULDERS: [.56,.36], CHEST: [.68,.48], WAIST: [.8,.62], THREE_QUARTER: [.9,.82], FULL_BODY: [1,1], WIDE: [1,1] };
  const [w,h] = sizes[framing]; return { x: (1-w)/2, y: h === 1 ? 0 : .03, w, h };
}
