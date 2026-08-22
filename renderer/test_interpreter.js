import * as THREE from 'three';
import { ProceduralInterpreter } from './src/interpreter.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const examplesDir = path.join(__dirname, '..', 'examples');

console.log("==========================================");
console.log("PROCEDURAL INTERPRETER NODE SUITE TEST");
console.log("==========================================");

const dummyScene = new THREE.Scene();
const interpreter = new ProceduralInterpreter(dummyScene);

const filesToTest = [
  'cube.json',
  'translated_cube.json',
  'repeated_boxes.json',
  'sphere.json',
  'cylinder.json',
  'cone.json',
  'rotated_cube.json',
  'scaled_cube.json',
  'duplicated_cube.json',
  'table.json'
];

let passed = 0;
let failed = 0;

for (const fileName of filesToTest) {
  const filePath = path.join(examplesDir, fileName);
  if (!fs.existsSync(filePath)) {
    console.error(`[FAIL] File missing: ${fileName}`);
    failed++;
    continue;
  }

  const rawJson = fs.readFileSync(filePath, 'utf-8');
  const sceneJson = JSON.parse(rawJson);

  try {
    const result = interpreter.execute(sceneJson);
    console.log(`[PASS] ${fileName} -> Executed ${result.executedOperations} ops, Registry Size: ${result.registry.size}`);
    passed++;
  } catch (err) {
    console.error(`[FAIL] ${fileName} -> Error: ${err.message}`);
    failed++;
  }
}

// ---------------------------------------------------------
// TEST: Reference Unknown Object Error Handling (Requirement 6)
// ---------------------------------------------------------
console.log("\n--- Testing Unknown Object Error Handling ---");
const invalidJson = {
  "schema_version": "1.0",
  "scene": { "name": "invalid_test", "units": "meters" },
  "operations": [
    {
      "id": "op_001",
      "type": "translate",
      "target": "missing_ghost_object",
      "parameters": { "target": "missing_ghost_object", "offset": [1, 0, 0] }
    }
  ]
};

try {
  interpreter.execute(invalidJson);
  console.error("[FAIL] Unknown object test failed to throw an error!");
  failed++;
} catch (err) {
  if (err.message.includes("Unknown object 'missing_ghost_object'")) {
    console.log(`[PASS] Unknown object error correctly caught: "${err.message}"`);
    passed++;
  } else {
    console.error(`[FAIL] Unknown object test threw unexpected error: ${err.message}`);
    failed++;
  }
}

// ---------------------------------------------------------
// TEST: Create Torus and Plane Operations
// ---------------------------------------------------------
console.log("\n--- Testing Torus, Plane & Mirror Operations ---");
const torusPlaneJson = {
  "schema_version": "1.0",
  "scene": { "name": "torus_plane_test", "units": "meters" },
  "operations": [
    {
      "id": "op_001",
      "type": "create_torus",
      "parameters": { "id": "torus_01", "radius": 1.2, "tube": 0.3 }
    },
    {
      "id": "op_002",
      "type": "create_plane",
      "parameters": { "id": "plane_01", "width": 5.0, "height": 5.0 }
    },
    {
      "id": "op_003",
      "type": "mirror",
      "target": "torus_01",
      "parameters": { "target": "torus_01", "axis": "x" }
    },
    {
      "id": "op_004",
      "type": "group",
      "parameters": { "id": "combined_group", "objects": ["torus_01", "plane_01"] }
    }
  ]
};

try {
  const result = interpreter.execute(torusPlaneJson);
  console.log(`[PASS] Torus/Plane/Mirror/Group -> Executed ${result.executedOperations} ops, Registry Size: ${result.registry.size}`);
  passed++;
} catch (err) {
  console.error(`[FAIL] Torus/Plane test failed: ${err.message}`);
  failed++;
}

console.log("\n==========================================");
console.log(`SUMMARY: ${passed} PASSED, ${failed} FAILED`);
console.log("==========================================");

if (failed > 0) {
  process.exit(1);
}
