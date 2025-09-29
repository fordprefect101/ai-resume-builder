/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// tslint:disable:organize-imports
// tslint:disable:ban-malformed-import-paths
// tslint:dsiable:no-new-decorators

import {LitElement, css, html} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {Analyser} from './Analyser';

import * as THREE from 'three';
import {EXRLoader} from 'three/examples/jsm/loaders/EXRLoader.js';
import {EffectComposer} from 'three/examples/jsm/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/examples/jsm/postprocessing/RenderPass.js';
import {ShaderPass} from 'three/examples/jsm/postprocessing/ShaderPass.js';
import {UnrealBloomPass} from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import {FXAAShader} from 'three/examples/jsm/shaders/FXAAShader.js';
// import {fs as backdropFS, vs as backdropVS} from '../shaders/backdrop';
import {vs as sphereVS} from '../shaders/sphere';

/**
 * Modern 3D live audio visualizer with gradient theme.
 */
@customElement('gdm-live-audio-visuals-3d')
export class GdmLiveAudioVisuals3D extends LitElement {
  private inputAnalyser!: Analyser;
  private outputAnalyser!: Analyser;
  private camera!: THREE.PerspectiveCamera;
  private backdrop!: THREE.Mesh;
  private composer!: EffectComposer;
  private sphere!: THREE.Mesh;
  private prevTime = 0;
  private rotation = new THREE.Vector3(0, 0, 0);
  private renderer!: THREE.WebGLRenderer;
  private fxaaPass!: ShaderPass;
  private scene!: THREE.Scene;

  private _outputNode!: AudioNode;

  @property()
  set outputNode(node: AudioNode) {
    this._outputNode = node;
    this.outputAnalyser = new Analyser(this._outputNode);
  }

  get outputNode() {
    return this._outputNode;
  }

  private _inputNode!: AudioNode;

  @property()
  set inputNode(node: AudioNode) {
    this._inputNode = node;
    this.inputAnalyser = new Analyser(this._inputNode);
  }

  get inputNode() {
    return this._inputNode;
  }

  private canvas!: HTMLCanvasElement;

  static styles = css`
    canvas {
      width: 100% !important;
      height: 100% !important;
      position: absolute;
      image-rendering: auto;
      background: transparent;
    }
  `;

  connectedCallback() {
    super.connectedCallback();
  }

  private init() {
    this.scene = new THREE.Scene();
    this.scene.background = null; // Transparent background

    // Use canvas client dimensions for initial setup
    const initialWidth = this.canvas.clientWidth;
    const initialHeight = this.canvas.clientHeight;

    this.camera = new THREE.PerspectiveCamera(
      75,
      initialWidth / initialHeight,
      0.1,
      1000,
    );
    this.camera.position.set(0, 0, 50);

    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      premultipliedAlpha: false,
    });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.setSize(initialWidth, initialHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);

    // Add lighting to the scene
    const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
    this.scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(10, 10, 5);
    this.scene.add(directionalLight);

    // Create floating particles
    // this.createParticles();

    // Create central orb
    this.createCentralOrb();

    const onWindowResize = () => {
      if (!this.canvas) return;
      const w = this.canvas.clientWidth;
      const h = this.canvas.clientHeight;

      if (this.camera) {
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
      }

      if (this.renderer) {
        this.renderer.setSize(w, h);
      }
    }
    
    const boundOnWindowResize = onWindowResize.bind(this);
    window.addEventListener('resize', boundOnWindowResize);
    
    this.animation();
  }

  private createParticles() {
    const particleCount = 200;
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount; i++) {
      // Random positions in a sphere
      const radius = 20 + Math.random() * 30;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);
      
      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);

      // Gradient colors (blue to purple)
      const colorMix = Math.random();
      colors[i * 3] = 0.4 + colorMix * 0.3; // Blue component
      colors[i * 3 + 1] = 0.2 + colorMix * 0.4; // Green component  
      colors[i * 3 + 2] = 0.6 + colorMix * 0.4; // Purple component
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: 2,
      vertexColors: true,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
    });

    const particles = new THREE.Points(geometry, material);
    this.scene.add(particles);
  }

  private createCentralOrb() {
    const geometry = new THREE.SphereGeometry(20, 32, 32);

    const pmremGenerator = new THREE.PMREMGenerator(this.renderer);
    pmremGenerator.compileEquirectangularShader();
    
    const sphereMaterial = new THREE.MeshStandardMaterial({
        color: 0x667eea,       // Blue color matching your landing page
        metalness: 0.3,        // Less metallic for better color visibility
        roughness: 0.2,        // Slightly rough for better light interaction
        emissive: 0x667eea,    // Self-emission for glow effect
        emissiveIntensity: 0.3, // Moderate glow intensity
    });

    sphereMaterial.onBeforeCompile = (shader) => {
      shader.uniforms.time = {value: 0};
      shader.uniforms.inputData = {value: new THREE.Vector4()};
      shader.uniforms.outputData = {value: new THREE.Vector4()};

      sphereMaterial.userData.shader = shader;

      shader.vertexShader = sphereVS;
    };

    const sphereMesh = new THREE.Mesh(geometry, sphereMaterial);
    this.scene.add(sphereMesh);
    sphereMesh.visible = true;

    this.sphere = sphereMesh;
  }

  private animation() {
    requestAnimationFrame(() => this.animation());

    if (!this.inputAnalyser || !this.outputAnalyser) return; 

    this.inputAnalyser.update();
    this.outputAnalyser.update();

    const t = performance.now();
    const dt = (t - this.prevTime) / (1000 / 60);
    this.prevTime = t;

    if (this.sphere && this.sphere.material instanceof THREE.MeshStandardMaterial && this.sphere.material.userData.shader) {
      const inputMagnitude = this.inputAnalyser.data.reduce((sum, value) => sum + value, 0) / this.inputAnalyser.data.length;
      const outputMagnitude = this.outputAnalyser.data.reduce((sum, value) => sum + value, 0) / this.outputAnalyser.data.length;

      // Scale the sphere based on audio
      this.sphere.scale.setScalar(
        1 + (0.2 * (inputMagnitude + outputMagnitude)) / 255
      );

      // 3D movement animations
      const f = 0.001;
      this.rotation.x += (dt * f * 0.5 * this.outputAnalyser.data[1]) / 255;
      this.rotation.z += (dt * f * 0.5 * this.inputAnalyser.data[1]) / 255;
      this.rotation.y += (dt * f * 0.25 * this.inputAnalyser.data[2]) / 255;
      this.rotation.y += (dt * f * 0.25 * this.outputAnalyser.data[2]) / 255;

      // Move camera around the sphere
      const euler = new THREE.Euler(
        this.rotation.x,
        this.rotation.y,
        this.rotation.z,
      );
      const quaternion = new THREE.Quaternion().setFromEuler(euler);
      const vector = new THREE.Vector3(0, 0, 50);
      vector.applyQuaternion(quaternion);
      this.camera.position.copy(vector);
      this.camera.lookAt(this.sphere.position);

      // Update shader uniforms for visual effects
      this.sphere.material.userData.shader.uniforms.time.value +=
        (dt * 0.1 * this.outputAnalyser.data[0]) / 255;
      this.sphere.material.userData.shader.uniforms.inputData.value.set(
        (1 * this.inputAnalyser.data[0]) / 255,
        (0.1 * this.inputAnalyser.data[1]) / 255,
        (10 * this.inputAnalyser.data[2]) / 255,
        0,
      );
      this.sphere.material.userData.shader.uniforms.outputData.value.set(
        (2 * this.outputAnalyser.data[0]) / 255,
        (0.1 * this.outputAnalyser.data[1]) / 255,
        (10 * this.outputAnalyser.data[2]) / 255,
        0,
      );
    }

    // Render the scene
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  protected firstUpdated() {
    this.canvas = this.shadowRoot!.querySelector('canvas') as HTMLCanvasElement;
    if (this._inputNode && !this.inputAnalyser) {
        this.inputAnalyser = new Analyser(this._inputNode);
    }
    if (this._outputNode && !this.outputAnalyser) {
        this.outputAnalyser = new Analyser(this._outputNode);
    }
    
    this.init();
  }

  protected render() {
    return html`<canvas></canvas>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'gdm-live-audio-visuals-3d': GdmLiveAudioVisuals3D;
  }
}
