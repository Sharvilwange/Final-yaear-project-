import * as THREE from 'three';
import { getMaterialForObject, resetMaterialCache } from './materials.js';

export class ProceduralInterpreter {
  constructor(scene) {
    this.scene = scene; // THREE.Scene instance
    this.registry = new Map(); // Object ID -> THREE.Object3D (Mesh or Group)
    this.rootGroup = new THREE.Group();
    this.rootGroup.name = "ProceduralSceneRoot";
    this.scene.add(this.rootGroup);
  }

  reset() {
    this.scene.remove(this.rootGroup);
    this.rootGroup = new THREE.Group();
    this.rootGroup.name = "ProceduralSceneRoot";
    this.scene.add(this.rootGroup);
    this.registry.clear();
    resetMaterialCache();
  }

  getObjectOrThrow(id, opId, opType) {
    if (!this.registry.has(id)) {
      throw new Error(`[Interpreter Error] Unknown object '${id}' referenced in operation '${opId}' (${opType}). Object does not exist in registry.`);
    }
    return this.registry.get(id);
  }

  execute(jsonScene) {
    this.reset();

    if (!jsonScene || !Array.isArray(jsonScene.operations)) {
      throw new Error("[Interpreter Error] Invalid procedural JSON: missing 'operations' array.");
    }

    const operations = jsonScene.operations;
    const executedOps = [];

    for (const op of operations) {
      const { id: opId, type: opType, target, parameters = {} } = op;

      switch (opType) {
        case 'create_box': {
          const objId = parameters.id;
          if (!objId) throw new Error(`[Interpreter Error] Operation '${opId}' (create_box) missing 'id' parameter.`);
          const width = parameters.width ?? 1;
          const height = parameters.height ?? 1;
          const depth = parameters.depth ?? 1;

          const geometry = new THREE.BoxGeometry(width, height, depth);
          const material = getMaterialForObject(objId, parameters);
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = objId;
          mesh.castShadow = true;
          mesh.receiveShadow = true;

          this.registry.set(objId, mesh);
          this.rootGroup.add(mesh);
          break;
        }

        case 'create_sphere': {
          const objId = parameters.id;
          if (!objId) throw new Error(`[Interpreter Error] Operation '${opId}' (create_sphere) missing 'id' parameter.`);
          const radius = parameters.radius ?? 1;

          const geometry = new THREE.SphereGeometry(radius, 32, 16);
          const material = getMaterialForObject(objId, parameters);
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = objId;
          mesh.castShadow = true;
          mesh.receiveShadow = true;

          this.registry.set(objId, mesh);
          this.rootGroup.add(mesh);
          break;
        }

        case 'create_cylinder': {
          const objId = parameters.id;
          if (!objId) throw new Error(`[Interpreter Error] Operation '${opId}' (create_cylinder) missing 'id' parameter.`);
          const radius = parameters.radius ?? 0.5;
          const height = parameters.height ?? 1;

          const geometry = new THREE.CylinderGeometry(radius, radius, height, 32);
          const material = getMaterialForObject(objId, parameters);
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = objId;
          mesh.castShadow = true;
          mesh.receiveShadow = true;

          this.registry.set(objId, mesh);
          this.rootGroup.add(mesh);
          break;
        }

        case 'create_cone': {
          const objId = parameters.id;
          if (!objId) throw new Error(`[Interpreter Error] Operation '${opId}' (create_cone) missing 'id' parameter.`);
          const radius = parameters.radius ?? 1;
          const height = parameters.height ?? 1;

          const geometry = new THREE.ConeGeometry(radius, height, 32);
          const material = getMaterialForObject(objId, parameters);
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = objId;
          mesh.castShadow = true;
          mesh.receiveShadow = true;

          this.registry.set(objId, mesh);
          this.rootGroup.add(mesh);
          break;
        }

        case 'create_plane': {
          const objId = parameters.id;
          if (!objId) throw new Error(`[Interpreter Error] Operation '${opId}' (create_plane) missing 'id' parameter.`);
          const width = parameters.width ?? 1;
          const height = parameters.height ?? 1;

          const geometry = new THREE.PlaneGeometry(width, height);
          const material = getMaterialForObject(objId, parameters);
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = objId;
          mesh.castShadow = true;
          mesh.receiveShadow = true;

          this.registry.set(objId, mesh);
          this.rootGroup.add(mesh);
          break;
        }

        case 'create_torus': {
          const objId = parameters.id;
          if (!objId) throw new Error(`[Interpreter Error] Operation '${opId}' (create_torus) missing 'id' parameter.`);
          const radius = parameters.radius ?? 1;
          const tube = parameters.tube ?? 0.4;

          const geometry = new THREE.TorusGeometry(radius, tube, 16, 100);
          const material = getMaterialForObject(objId, parameters);
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = objId;
          mesh.castShadow = true;
          mesh.receiveShadow = true;

          this.registry.set(objId, mesh);
          this.rootGroup.add(mesh);
          break;
        }

        case 'translate': {
          const targetId = target || parameters.target;
          const obj = this.getObjectOrThrow(targetId, opId, opType);
          const offset = parameters.offset || [0, 0, 0];
          obj.position.x += offset[0] || 0;
          obj.position.y += offset[1] || 0;
          obj.position.z += offset[2] || 0;
          break;
        }

        case 'rotate': {
          const targetId = target || parameters.target;
          const obj = this.getObjectOrThrow(targetId, opId, opType);
          const rotation = parameters.rotation || [0, 0, 0]; // Degrees
          obj.rotation.x += THREE.MathUtils.degToRad(rotation[0] || 0);
          obj.rotation.y += THREE.MathUtils.degToRad(rotation[1] || 0);
          obj.rotation.z += THREE.MathUtils.degToRad(rotation[2] || 0);
          break;
        }

        case 'scale': {
          const targetId = target || parameters.target;
          const obj = this.getObjectOrThrow(targetId, opId, opType);
          const factor = parameters.factor;

          if (typeof factor === 'number') {
            obj.scale.multiplyScalar(factor);
          } else if (Array.isArray(factor) && factor.length === 3) {
            obj.scale.x *= factor[0];
            obj.scale.y *= factor[1];
            obj.scale.z *= factor[2];
          } else {
            throw new Error(`[Interpreter Error] Operation '${opId}' (scale) invalid 'factor' parameter.`);
          }
          break;
        }

        case 'duplicate': {
          const targetId = target || parameters.target;
          const obj = this.getObjectOrThrow(targetId, opId, opType);
          const newId = parameters.new_id;
          if (!newId) throw new Error(`[Interpreter Error] Operation '${opId}' (duplicate) missing 'new_id' parameter.`);

          const clone = obj.clone(true);
          clone.name = newId;

          if (clone.isMesh) {
            clone.material = getMaterialForObject(newId);
          }

          this.registry.set(newId, clone);
          if (obj.parent) {
            obj.parent.add(clone);
          } else {
            this.rootGroup.add(clone);
          }
          break;
        }

        case 'repeat': {
          const targetId = target || parameters.target;
          const obj = this.getObjectOrThrow(targetId, opId, opType);
          const count = parameters.count ?? 1;
          const offset = parameters.offset || [0, 0, 0];

          for (let i = 1; i < count; i++) {
            const clone = obj.clone(true);
            const cloneId = `${targetId}_repeat_${i}`;
            clone.name = cloneId;
            clone.position.x += offset[0] * i;
            clone.position.y += offset[1] * i;
            clone.position.z += offset[2] * i;

            if (clone.isMesh) {
              clone.material = getMaterialForObject(cloneId);
            }

            this.registry.set(cloneId, clone);
            if (obj.parent) {
              obj.parent.add(clone);
            } else {
              this.rootGroup.add(clone);
            }
          }
          break;
        }

        case 'mirror': {
          const targetId = target || parameters.target;
          const obj = this.getObjectOrThrow(targetId, opId, opType);
          const axis = parameters.axis;

          if (typeof axis === 'string') {
            const cleanAxis = axis.toLowerCase().replace(/^[+-]/, '');
            if (cleanAxis === 'x') obj.scale.x *= -1;
            else if (cleanAxis === 'y') obj.scale.y *= -1;
            else if (cleanAxis === 'z') obj.scale.z *= -1;
            else throw new Error(`[Interpreter Error] Operation '${opId}' (mirror) invalid string axis '${axis}'.`);
          } else if (Array.isArray(axis) && axis.length === 3) {
            if (axis[0] !== 0) obj.scale.x *= -1;
            if (axis[1] !== 0) obj.scale.y *= -1;
            if (axis[2] !== 0) obj.scale.z *= -1;
          } else {
            throw new Error(`[Interpreter Error] Operation '${opId}' (mirror) missing or invalid 'axis' parameter.`);
          }
          break;
        }

        case 'group': {
          const groupId = parameters.id;
          if (!groupId) throw new Error(`[Interpreter Error] Operation '${opId}' (group) missing 'id' parameter.`);
          const objectIds = parameters.objects || [];

          const group = new THREE.Group();
          group.name = groupId;

          for (const memberId of objectIds) {
            const memberObj = this.getObjectOrThrow(memberId, opId, opType);
            group.add(memberObj);
          }

          this.registry.set(groupId, group);
          this.rootGroup.add(group);
          break;
        }

        default: {
          throw new Error(`[Interpreter Error] Unsupported or unknown operation type '${opType}' in op '${opId}'.`);
        }
      }

      executedOps.push(opId);
    }

    return {
      success: true,
      executedOperations: executedOps.length,
      registry: this.registry,
      rootGroup: this.rootGroup
    };
  }
}
