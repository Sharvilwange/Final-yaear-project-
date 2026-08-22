import * as THREE from 'three';

const COLOR_PALETTE = [
  0x3b82f6, // Vibrant Blue
  0x10b981, // Emerald Green
  0xf59e0b, // Amber / Warm Yellow
  0xef4444, // Bright Red
  0x8b5cf6, // Purple
  0xec4899, // Pink
  0x06b6d4, // Cyan
  0x84cc16, // Lime
  0xf97316, // Orange
  0x6366f1  // Indigo
];

let colorIndex = 0;
const materialCache = new Map();

/**
 * Returns a visually appealing THREE.MeshStandardMaterial for a given object.
 * Uses object ID to deterministically assign colors unless custom parameters exist.
 */
export function getMaterialForObject(id, options = {}) {
  if (materialCache.has(id)) {
    return materialCache.get(id);
  }

  // Calculate color deterministically from ID string hash
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = id.charCodeAt(i) + ((hash << 5) - hash);
  }
  const paletteIndex = Math.abs(hash) % COLOR_PALETTE.length;
  const baseColor = options.color ? new THREE.Color(options.color) : COLOR_PALETTE[paletteIndex];

  const material = new THREE.MeshStandardMaterial({
    color: baseColor,
    roughness: options.roughness ?? 0.35,
    metalness: options.metalness ?? 0.15,
    side: THREE.DoubleSide,
    shadowSide: THREE.DoubleSide
  });

  materialCache.set(id, material);
  return material;
}

/**
 * Clears the material cache when resetting scene.
 */
export function resetMaterialCache() {
  materialCache.clear();
  colorIndex = 0;
}
