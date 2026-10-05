import * as THREE from 'three';
import {RoomEnvironment} from 'three/addons/RoomEnvironment.js';

const DEPTH = 0.075;          // plate thickness, in "image widths" (assumed, not measured)
const EARS = [{x:.116,y:.821,ri:.03,ro:.072},{x:.596,y:.816,ri:.022,ro:.056}];

export async function loadOutline(){ return (await fetch('assets/bracket_outline.json')).json(); }

export function buildBracket(outline, tex, opts={}){
  const g = new THREE.Group();
  const S = new THREE.Shape(outline.outer.map(p=>new THREE.Vector2(p[0],p[1])));
  for(const h of outline.holes) S.holes.push(new THREE.Path(h.map(p=>new THREE.Vector2(p[0],p[1]))));
  const geo = new THREE.ExtrudeGeometry(S,{depth:DEPTH,bevelEnabled:true,bevelThickness:.004,bevelSize:.003,bevelSegments:2,steps:1,curveSegments:8});
  // group 0 = caps (first half back, second half front), group 1 = sides
  const g0 = geo.groups.find(x=>x.materialIndex===0), g1 = geo.groups.find(x=>x.materialIndex===1);
  const half = g0.count/2;
  geo.clearGroups();
  geo.addGroup(0,half,0); geo.addGroup(half,half,1); geo.addGroup(g1.start,g1.count,2);
  const anod = opts.anod ?? 0x0b0b0e;
  const back = new THREE.MeshStandardMaterial({color:anod,metalness:.7,roughness:.35});
  const front = new THREE.MeshStandardMaterial({map:tex,metalness:.35,roughness:.4});
  const side = new THREE.MeshStandardMaterial({color:anod,metalness:.8,roughness:.28});
  const body = new THREE.Mesh(geo,[back,front,side]); g.add(body);
  // bushing collars (chrome) front + back
  const chrome = new THREE.MeshStandardMaterial({color:0xdfe3ea,metalness:1,roughness:.12});
  for(const e of EARS){
    const R = new THREE.Shape(); R.absarc(0,0,e.ro,0,Math.PI*2);
    const H = new THREE.Path(); H.absarc(0,0,e.ri,0,Math.PI*2,true); R.holes.push(H);
    const cg = new THREE.ExtrudeGeometry(R,{depth:DEPTH+.05,bevelEnabled:true,bevelThickness:.004,bevelSize:.004,bevelSegments:3,curveSegments:48});
    const c = new THREE.Mesh(cg,chrome); c.position.set(e.x,e.y,-.025); g.add(c);
  }
  g.position.set(-.5,-.5,-DEPTH/2);
  const root = new THREE.Group(); root.add(g);
  return root;
}

export function makeScene(canvas, w, h, texUrl, opts={}){
  const r = new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,preserveDrawingBuffer:true});
  r.setPixelRatio(opts.dpr||2); r.setSize(w,h,false); r.setClearColor(0,0);
  r.toneMapping = THREE.ACESFilmicToneMapping; r.toneMappingExposure = 1.05;
  r.shadowMap.enabled = false;
  const scene = new THREE.Scene();
  const pm = new THREE.PMREMGenerator(r);
  scene.environment = pm.fromScene(new RoomEnvironment(),0.04).texture;
  const cam = new THREE.PerspectiveCamera(28,w/h,.1,20); cam.position.set(0,0,3.2);
  const key = new THREE.DirectionalLight(0xffffff,1.6); key.position.set(1.5,2,3); scene.add(key);
  const rim = new THREE.DirectionalLight(0x9db8ff,1.0); rim.position.set(-2,-1,-2); scene.add(rim);
  const tex = new THREE.TextureLoader().load(texUrl); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  return {r,scene,cam,tex,THREE};
}
