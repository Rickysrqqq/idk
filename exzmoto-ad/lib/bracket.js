import * as THREE from 'three';
import {RoomEnvironment} from 'three/addons/RoomEnvironment.js';

const MM = 1/120;             // 1 mm in bracket-photo units (assumes bracket is ~120 mm wide, estimated from rotor size)
export const DEPTH = 15*MM;   // bracket thickness: 15 mm
const GUARD_D = 3*MM;         // rotor guard plate thickness (assumed 3 mm)
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
  const front = new THREE.MeshBasicMaterial({map:tex,toneMapped:false});
  const side = new THREE.MeshStandardMaterial({color:anod,metalness:.8,roughness:.28});
  const body = new THREE.Mesh(geo,[back,front,side]); g.add(body);
  // bushing collars (chrome) front + back
  const chrome = new THREE.MeshStandardMaterial({color:opts.collar??0xdfe3ea,metalness:1,roughness:opts.collar?0.3:.12});
  for(const e of EARS){
    const R = new THREE.Shape(); R.absarc(0,0,e.ro,0,Math.PI*2);
    const H = new THREE.Path(); H.absarc(0,0,e.ri,0,Math.PI*2,true); R.holes.push(H);
    const cg = new THREE.ExtrudeGeometry(R,{depth:DEPTH+.05,bevelEnabled:true,bevelThickness:.004,bevelSize:.004,bevelSegments:3,curveSegments:48});
    const c = new THREE.Mesh(cg,chrome); c.position.set(e.x,e.y,-.025); g.add(c);
  }
  if(opts.raw) return g;
  g.position.set(-.5,-.5,-DEPTH/2);
  const root = new THREE.Group(); root.add(g);
  return root;
}

export function makeScene(canvas, w, h, texUrl, opts={}){
  const r = new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,preserveDrawingBuffer:true});
  r.setPixelRatio(opts.dpr||2); r.setSize(w,h,false); r.setClearColor(0,0);
  r.toneMapping = THREE.ACESFilmicToneMapping; r.toneMappingExposure = 1.0;
  r.shadowMap.enabled = false;
  const scene = new THREE.Scene();
  const pm = new THREE.PMREMGenerator(r);
  scene.environment = pm.fromScene(new RoomEnvironment(),0.04).texture;
  const cam = new THREE.PerspectiveCamera(28,w/h,.1,20); cam.position.set(0,0,3.2);
  const key = new THREE.DirectionalLight(0xffffff,.5); key.position.set(1.5,2,3); scene.add(key);
  const rim = new THREE.DirectionalLight(0x9db8ff,.35); rim.position.set(-2,-1,-2); scene.add(rim);
  const tex = new THREE.TextureLoader().load(texUrl); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  return {r,scene,cam,tex,THREE};
}


export async function loadJSON(u){ return (await fetch(u)).json(); }

// Rotor guard (3 mm plate, silhouette from the product photo) + 15 mm bracket stacked on it,
// positioned using the photo-to-photo registration in reg.json.
export function buildAssembly(outline8, guard, reg, texBr, texG, opts={}){
  const root = new THREE.Group();
  // guard
  const S = new THREE.Shape(guard.outer.map(p=>new THREE.Vector2(p[0],p[1])));
  for(const h of guard.holes) S.holes.push(new THREE.Path(h.map(p=>new THREE.Vector2(p[0],p[1]))));
  const k = reg.A[0][0]*reg.W8/reg.W11;
  const gd = GUARD_D*k;
  const geo = new THREE.ExtrudeGeometry(S,{depth:gd,bevelEnabled:true,bevelThickness:.0015,bevelSize:.0012,bevelSegments:2,steps:1,curveSegments:8});
  const g0 = geo.groups.find(x=>x.materialIndex===0), g1 = geo.groups.find(x=>x.materialIndex===1);
  const half = g0.count/2; geo.clearGroups();
  geo.addGroup(0,half,0); geo.addGroup(half,half,1); geo.addGroup(g1.start,g1.count,2);
  texG.repeat.set(1, guard.W/guard.H);
  const metal = opts.guardSide ?? 0xc9cdd5;
  const guardMesh = new THREE.Mesh(geo,[
    new THREE.MeshStandardMaterial({color:metal,metalness:.9,roughness:.3}),
    new THREE.MeshBasicMaterial({map:texG,toneMapped:false,alphaTest:.5}),
    new THREE.MeshStandardMaterial({color:metal,metalness:.95,roughness:.22})]);
  root.add(guardMesh);
  // bracket
  const br = buildBracket(outline8, texBr, {raw:true, anod:opts.anod, collar:opts.collar});
  const A = reg.A, W8=reg.W8,H8=reg.H8,W11=reg.W11,H11=reg.H11;
  const m = new THREE.Matrix4().set(
    A[0][0]*W8/W11, -(A[0][1]*H8/W11), 0, (A[0][1]*H8+A[0][2])/W11,
    -(A[1][0]*W8/W11), A[1][1]*H8/W11, 0, (H11-A[1][1]*H8-A[1][2])/W11,
    0,0,k, gd,
    0,0,0,1);
  br.matrixAutoUpdate=false; br.matrix.copy(m);
  root.add(br);
  const hh = H11/W11;
  root.position.set(-.5,-hh/2,-(gd+DEPTH*k)/2);
  const wrap = new THREE.Group(); wrap.add(root);
  // helper: bracket-photo point -> wrapper space
  wrap.userData.bracketPoint = (x8,y8)=> new THREE.Vector3(x8,y8,DEPTH).applyMatrix4(m).add(root.position);
  wrap.userData.k = k;
  return wrap;
}
