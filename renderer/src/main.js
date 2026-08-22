import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { ProceduralInterpreter } from './interpreter.js';

// DOM Elements
const canvas = document.getElementById('webgl-canvas');
const exampleSelect = document.getElementById('example-select');
const fileUpload = document.getElementById('file-upload');
const applyBtn = document.getElementById('apply-btn');
const jsonEditor = document.getElementById('json-editor');
const objectCountEl = document.getElementById('object-count');
const operationCountEl = document.getElementById('operation-count');
const statusBadge = document.getElementById('status-badge');
const statusPanel = document.getElementById('status-panel');

// Three.js Core Setup
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(canvas.clientWidth, canvas.clientHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0f172a);
scene.fog = new THREE.FogExp2(0x0f172a, 0.04);

const camera = new THREE.PerspectiveCamera(50, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
camera.position.set(4, 3, 5);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.maxPolarAngle = Math.PI / 2 - 0.01; // Don't go below floor

// Lighting Setup
const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
scene.add(ambientLight);

const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
dirLight.position.set(5, 8, 5);
dirLight.castShadow = true;
dirLight.shadow.mapSize.width = 2048;
dirLight.shadow.mapSize.height = 2048;
dirLight.shadow.bias = -0.0001;
scene.add(dirLight);

const fillLight = new THREE.DirectionalLight(0x90b0ff, 0.6);
fillLight.position.set(-5, 4, -5);
scene.add(fillLight);

// Floor & Grid Helper
const gridHelper = new THREE.GridHelper(20, 20, 0x334155, 0x1e293b);
gridHelper.position.y = -0.01;
scene.add(gridHelper);

const floorGeo = new THREE.PlaneGeometry(30, 30);
const floorMat = new THREE.ShadowMaterial({ opacity: 0.3 });
const floorMesh = new THREE.Mesh(floorGeo, floorMat);
floorMesh.rotation.x = -Math.PI / 2;
floorMesh.position.y = -0.01;
floorMesh.receiveShadow = true;
scene.add(floorMesh);

// Procedural Interpreter Instance
const interpreter = new ProceduralInterpreter(scene);

// Embedded fallback examples to guarantee offline & instant loading
const EMBEDDED_EXAMPLES = {
  "cube.json": {
    "schema_version": "1.0",
    "scene": { "name": "simple_cube", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "create_box",
        "parameters": { "id": "cube_01", "width": 1, "height": 1, "depth": 1 }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 1, "expected_operation_count": 1 }
  },
  "translated_cube.json": {
    "schema_version": "1.0",
    "scene": { "name": "translated_cube", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "create_box",
        "parameters": { "id": "box_01", "width": 1, "height": 1, "depth": 1 }
      },
      {
        "id": "op_002",
        "type": "translate",
        "target": "box_01",
        "parameters": { "target": "box_01", "offset": [2.0, 1.0, 0.0] }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 1, "expected_operation_count": 2 }
  },
  "repeated_boxes.json": {
    "schema_version": "1.0",
    "scene": { "name": "repeated_boxes", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "create_box",
        "parameters": { "id": "box_base", "width": 0.8, "height": 0.8, "depth": 0.8 }
      },
      {
        "id": "op_002",
        "type": "repeat",
        "target": "box_base",
        "parameters": { "target": "box_base", "count": 4, "offset": [1.5, 0.0, 0.0] }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 1, "expected_operation_count": 2 }
  },
  "sphere.json": {
    "schema_version": "1.0",
    "scene": { "name": "simple_sphere", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "create_sphere",
        "parameters": { "id": "sphere_01", "radius": 1 }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 1, "expected_operation_count": 1 }
  },
  "cylinder.json": {
    "schema_version": "1.0",
    "scene": { "name": "simple_cylinder", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "create_cylinder",
        "parameters": { "id": "cyl_01", "radius": 0.5, "height": 2.0 }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 1, "expected_operation_count": 1 }
  },
  "cone.json": {
    "schema_version": "1.0",
    "scene": { "name": "simple_cone", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "create_cone",
        "parameters": { "id": "cone_01", "radius": 1.0, "height": 2.0 }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 1, "expected_operation_count": 1 }
  },
  "rotated_cube.json": {
    "schema_version": "1.0",
    "scene": { "name": "rotated_cube", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "create_box",
        "parameters": { "id": "box_01", "width": 1.0, "height": 1.0, "depth": 1.0 }
      },
      {
        "id": "op_002",
        "type": "rotate",
        "target": "box_01",
        "parameters": { "target": "box_01", "rotation": [0, 45, 0] }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 1, "expected_operation_count": 2 }
  },
  "scaled_cube.json": {
    "schema_version": "1.0",
    "scene": { "name": "scaled_cube", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "create_box",
        "parameters": { "id": "box_01", "width": 1.0, "height": 1.0, "depth": 1.0 }
      },
      {
        "id": "op_002",
        "type": "scale",
        "target": "box_01",
        "parameters": { "target": "box_01", "factor": [2.0, 0.5, 1.0] }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 1, "expected_operation_count": 2 }
  },
  "duplicated_cube.json": {
    "schema_version": "1.0",
    "scene": { "name": "duplicated_cube", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "create_box",
        "parameters": { "id": "box_orig", "width": 1.0, "height": 1.0, "depth": 1.0 }
      },
      {
        "id": "op_002",
        "type": "duplicate",
        "target": "box_orig",
        "parameters": { "target": "box_orig", "new_id": "box_copy" }
      },
      {
        "id": "op_003",
        "type": "translate",
        "target": "box_copy",
        "parameters": { "target": "box_copy", "offset": [1.5, 0.0, 0.0] }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 2, "expected_operation_count": 3 }
  },
  "table.json": {
    "schema_version": "1.0",
    "scene": { "name": "procedural_table", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "create_box",
        "parameters": { "id": "table_top", "width": 1.5, "height": 0.05, "depth": 0.8 }
      },
      {
        "id": "op_002",
        "type": "translate",
        "target": "table_top",
        "parameters": { "target": "table_top", "offset": [0.0, 0.75, 0.0] }
      },
      {
        "id": "op_003",
        "type": "create_cylinder",
        "parameters": { "id": "leg_1", "radius": 0.04, "height": 0.75 }
      },
      {
        "id": "op_004",
        "type": "translate",
        "target": "leg_1",
        "parameters": { "target": "leg_1", "offset": [-0.65, 0.375, -0.3] }
      },
      {
        "id": "op_005",
        "type": "duplicate",
        "target": "leg_1",
        "parameters": { "target": "leg_1", "new_id": "leg_2" }
      },
      {
        "id": "op_006",
        "type": "translate",
        "target": "leg_2",
        "parameters": { "target": "leg_2", "offset": [1.3, 0.0, 0.0] }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 3, "expected_operation_count": 6 }
  },
  "invalid_unknown_object": {
    "schema_version": "1.0",
    "scene": { "name": "invalid_test", "units": "meters" },
    "operations": [
      {
        "id": "op_001",
        "type": "translate",
        "target": "non_existent_object_99",
        "parameters": { "target": "non_existent_object_99", "offset": [1.0, 0.0, 0.0] }
      }
    ],
    "constraints": [],
    "validation": { "expected_object_count": 0, "expected_operation_count": 1 }
  }
};

/**
 * Executes JSON scene with Procedural Interpreter and updates UI.
 */
function loadAndExecuteScene(jsonObj) {
  jsonEditor.value = JSON.stringify(jsonObj, null, 2);

  try {
    const result = interpreter.execute(jsonObj);

    objectCountEl.textContent = result.registry.size;
    operationCountEl.textContent = result.executedOperations;

    statusBadge.textContent = "Scene Loaded";
    statusBadge.className = "badge badge-success";

    statusPanel.innerHTML = `<div class="status-success">✓ Executed ${result.executedOperations} operations successfully. ${result.registry.size} object(s) registered in 3D scene.</div>`;

    // Center camera frame around scene bounding box
    fitCameraToScene();
  } catch (err) {
    objectCountEl.textContent = interpreter.registry.size;
    operationCountEl.textContent = 0;

    statusBadge.textContent = "Error";
    statusBadge.className = "badge badge-error";

    statusPanel.innerHTML = `<div class="status-error">✕ ${err.message}</div>`;
    console.error(err);
  }
}

/**
 * Adjusts camera position to bound and center scene objects nicely.
 */
function fitCameraToScene() {
  const box = new THREE.Box3().setFromObject(interpreter.rootGroup);
  if (box.isEmpty()) return;

  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 1.5);

  controls.target.copy(center);

  const distance = maxDim * 2.5;
  camera.position.set(center.x + distance * 0.7, center.y + distance * 0.6, center.z + distance * 0.9);
  camera.lookAt(center);
  controls.update();
}

// Load default example
function loadSelectedExample() {
  const selectedName = exampleSelect.value;
  if (EMBEDDED_EXAMPLES[selectedName]) {
    loadAndExecuteScene(EMBEDDED_EXAMPLES[selectedName]);
  } else {
    // Attempt fetch from /examples/
    fetch(`/examples/${selectedName}`)
      .then(res => res.json())
      .then(json => loadAndExecuteScene(json))
      .catch(err => {
        statusPanel.innerHTML = `<div class="status-error">Failed to fetch example file '${selectedName}': ${err.message}</div>`;
      });
  }
}

// Event Listeners
exampleSelect.addEventListener('change', loadSelectedExample);

applyBtn.addEventListener('click', () => {
  try {
    const parsed = JSON.parse(jsonEditor.value);
    loadAndExecuteScene(parsed);
  } catch (e) {
    statusBadge.textContent = "JSON Syntax Error";
    statusBadge.className = "badge badge-error";
    statusPanel.innerHTML = `<div class="status-error">Invalid JSON syntax: ${e.message}</div>`;
  }
});

fileUpload.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (event) => {
    try {
      const parsed = JSON.parse(event.target.result);
      loadAndExecuteScene(parsed);
    } catch (err) {
      statusBadge.textContent = "File Error";
      statusBadge.className = "badge badge-error";
      statusPanel.innerHTML = `<div class="status-error">Error reading file: ${err.message}</div>`;
    }
  };
  reader.readAsText(file);
});

// Window Resize Handler
window.addEventListener('resize', () => {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
});

// Initial Load
loadSelectedExample();

// Animation Loop
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();
