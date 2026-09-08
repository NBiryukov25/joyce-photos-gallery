export const ANGLES = {
  FRONT: 'Front', LEFT_3Q: 'Left three-quarter', RIGHT_3Q: 'Right three-quarter',
  PROFILE_LEFT: 'Left profile', PROFILE_RIGHT: 'Right profile',
  REAR_3Q_LEFT: 'Rear three-quarter left', REAR_3Q_RIGHT: 'Rear three-quarter right',
  REAR: 'Rear', HIGH: 'High', LOW: 'Low', OVERHEAD: 'Overhead', EYE_LEVEL: 'Eye level', CUSTOM: 'Custom',
};
export const FRAMINGS = { FACE: 'Face', HEAD_SHOULDERS: 'Head & shoulders', CHEST: 'Chest-up', WAIST: 'Waist-up', THREE_QUARTER: 'Three-quarter body', FULL_BODY: 'Full body', WIDE: 'Wide / full available frame' };
export const PRESERVATIONS = ['FACE', 'BODY', 'HAIR', 'OUTFIT', 'ACCESSORIES', 'BACKGROUND', 'LIGHTING', 'PHOTO_STYLE'];
// Attribute Combine takes each of these from one named reference.
export const ATTRIBUTES = {
  FACE: 'Face and identity', HAIR: 'Hair', OUTFIT: 'Outfit', ACCESSORIES: 'Accessories',
  BODY: 'Body and proportions', POSE: 'Pose', BACKGROUND: 'Background and scene',
  LIGHTING: 'Lighting', PHOTO_STYLE: 'Photographic style', COLOR: 'Colour grade',
};
// One table drives the schema, the prompt builder and the browser controls.
//   generative        reaches the provider at all (Crop Zoom never does)
//   usesAngle         the angle preset selects a camera position
//   subject           how the references relate to each other
//   minReferences     photographs the operation cannot work without
//   requiresDirection each output needs its own written instruction
//   requiresAttributes each output needs at least two attribute sources
//   requiresModels    distinct models the session must span
//   requiresReferenceInput the operation is defined by the reference
//                     photographs, so a text-only endpoint cannot perform it
export const MODES = {
  CROP_ZOOM: {label:'Crop Zoom', blurb:'Frame existing pixels · no API cost', generative:false, usesAngle:false, subject:'same', minReferences:1,
    note:'Local crop only. No new pixels or camera angles are generated. All API calls are bypassed.'},
  OUTPAINT_ZOOM: {label:'Outpaint Zoom', blurb:'Reconstruct beyond the original edges', generative:true, usesAngle:false, subject:'same', minReferences:1, requiresReferenceInput:true,
    note:'Generatively expands the photograph beyond its edges. Uses all references for continuity.'},
  GENERATIVE_ANGLE: {label:'Generative Angle', blurb:'Move the virtual camera around the subject', generative:true, usesAngle:true, subject:'same', minReferences:1,
    note:'A new camera viewpoint inferred from all references. Left and right refer to the subject\u2019s own sides.'},
  MULTI_REFERENCE: {label:'Multi-Reference', blurb:'One subject, every reference as evidence', generative:true, usesAngle:true, subject:'same', minReferences:2, requiresReferenceInput:true,
    note:'Synthesises one new photograph of the same subject from all references at once. Add a written direction to steer it.'},
  COMBINED_IMAGES: {label:'Combined Images', blurb:'Different subjects in one photograph', generative:true, usesAngle:true, subject:'distinct', minReferences:2, requiresDirection:true, requiresReferenceInput:true,
    note:'The references show different subjects, objects or scenes. Describe how they belong together in one photograph.'},
  ATTRIBUTE_COMBINE: {label:'Attribute Combine', blurb:'Take each attribute from a named reference', generative:true, usesAngle:true, subject:'attributes', minReferences:2, requiresAttributes:true, requiresReferenceInput:true,
    note:'Assign at least two attributes, each to the reference it should come from. Nothing else is taken from those references.'},
  MODEL_COMPARISON: {label:'Model Comparison', blurb:'The same shot across several models', generative:true, usesAngle:true, subject:'same', minReferences:1, requiresModels:2,
    note:'Every output shares one instruction and runs on a different model, so the results are directly comparable. LIVE charges one request per model.'},
};
export const MODE_KEYS = Object.keys(MODES);
export const DEFAULT_PRESERVATION = Object.fromEntries(PRESERVATIONS.map(k => [k, 'HIGH']));
export function autoPack(count, represented = []) {
  const order = ['LEFT_3Q', 'RIGHT_3Q', 'PROFILE_RIGHT', 'REAR_3Q_LEFT', 'HIGH', 'LOW', 'REAR_3Q_RIGHT', 'PROFILE_LEFT', 'REAR', 'OVERHEAD', 'FRONT'];
  const ranked = [...order.filter(k => !represented.includes(k)), ...order.filter(k => represented.includes(k))];
  const families = k => k.startsWith('PROFILE') ? 'profile' : k.startsWith('REAR_3Q') ? 'rear-quarter' : ['HIGH', 'LOW', 'OVERHEAD'].includes(k) ? 'elevation' : k;
  const chosen = [], used = new Set();
  for (const k of ranked) if (!used.has(families(k))) { chosen.push(k); used.add(families(k)); if (chosen.length === count) break; }
  return chosen.map(angle => ({ angle, framing: ['HIGH','LOW','REAR_3Q_LEFT','REAR_3Q_RIGHT','REAR'].includes(angle) ? 'FULL_BODY' : 'THREE_QUARTER', custom: '', sourceIndex: 0 }));
}
// Model Comparison: one shot list entry per model, identical in every other
// respect so the only variable left is the model that renders it.
export function comparisonPack(models, base = {}) {
  const shared = { angle: 'LEFT_3Q', framing: 'THREE_QUARTER', custom: '', sourceIndex: 0, expansion: 1.6, attributes: [], ...base };
  return [...new Set(models)].slice(0, 5).map(model => ({ ...shared, model }));
}
export function defaultCrop(framing) {
  const sizes = { FACE: [.34,.23], HEAD_SHOULDERS: [.56,.36], CHEST: [.68,.48], WAIST: [.8,.62], THREE_QUARTER: [.9,.82], FULL_BODY: [1,1], WIDE: [1,1] };
  const [w,h] = sizes[framing]; return { x: (1-w)/2, y: h === 1 ? 0 : .03, w, h };
}
