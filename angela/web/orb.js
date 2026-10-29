import * as THREE from './vendor/three.module.js';
const host=document.getElementById('scene');
const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(innerWidth,innerHeight);renderer.setClearColor(0x000000,0);host.appendChild(renderer.domElement);
const scene=new THREE.Scene();scene.fog=new THREE.FogExp2(0x020509,.065);
const camera=new THREE.PerspectiveCamera(45,innerWidth/innerHeight,.1,100);camera.position.set(0,0,12.6);
const root=new THREE.Group();scene.add(root);
const gold=new THREE.Color(0xff8c00), pale=new THREE.Color(0xffe7a0);
const stateColors={starting:0xff3030,ready:0x2495ff,speaking:0xff9a17,listening:0x29f46b,processing:0xff9a17};
let currentState='starting';
let voiceLevel=0, micLevel=0, motionLevel=0, heardLevel=0;
const tintables=[];
const displayColor=new THREE.Color(stateColors.starting);
const targetColor=new THREE.Color(stateColors.starting);
let speakingMix=0, listeningMix=0, currentScale=1, currentCoreScale=1, currentGlowScale=1;
window.angelaSetVoiceLevel=(value)=>{voiceLevel=Math.max(0,Math.min(1,Number(value)||0));};
window.angelaSetMicLevel=(value)=>{micLevel=Math.max(0,Math.min(1,Number(value)||0));};
function applyState(state){
 if(!(state in stateColors)) return false;
 currentState=state;
 targetColor.setHex(stateColors[state]);
 return true;
}
function line(points,opacity=.9,color=gold){const geo=new THREE.BufferGeometry().setFromPoints(points);const mat=new THREE.LineBasicMaterial({color,transparent:true,opacity:Math.min(1,opacity*1.8),depthWrite:false,blending:THREE.NormalBlending});const l=new THREE.Line(geo,mat);tintables.push(mat);root.add(l);return l}
function orbit(radius,axis,phase,segments=240,opacity=.4){const pts=[];for(let i=0;i<=segments;i++){const a=i/segments*Math.PI*2+phase;let x=radius*Math.cos(a),y=radius*Math.sin(a),z=0;if(axis===1)[x,z]=[z,x];if(axis===2)[y,z]=[z,y];pts.push(new THREE.Vector3(x,y,z))}return line(pts,opacity)}
// Estrutura externa: latitudes e meridianos interrompidos, com aparência de circuitos.
const rng=(seed)=>()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296};const rand=rng(74218);
function spherePoint(r,theta,phi){return new THREE.Vector3(r*Math.sin(theta)*Math.cos(phi),r*Math.cos(theta),r*Math.sin(theta)*Math.sin(phi))}
for(let j=0;j<90;j++){const theta=.12+rand()*(Math.PI-.24),r=3.0+(rand()-.5)*.36,start=rand()*Math.PI*2,span=.10+rand()*1.9;const pts=[];for(let i=0;i<35;i++)pts.push(spherePoint(r,theta,start+span*i/34));line(pts,.48+rand()*.48,rand()>.5?pale:gold)}
for(let j=0;j<105;j++){const phi=rand()*Math.PI*2,r=2.8+rand()*.45,start=.1+rand()*2.5,span=.05+rand()*.8;const pts=[];for(let i=0;i<25;i++)pts.push(spherePoint(r,start+span*i/24,phi));line(pts,.4+rand()*.5)}
for(let j=0;j<1300;j++){const theta=rand()*Math.PI,phi=rand()*Math.PI*2,r=2.7+rand()*.6,p=spherePoint(r,theta,phi);const d=spherePoint(r+.025+rand()*.18,theta+.01,phi+.005);line([p,d],.40+rand()*.57)}
// Anéis internos em planos diferentes.
for(let j=0;j<15;j++){const ring=new THREE.Group(),r=.65+j*.12;const pts=[];for(let i=0;i<=200;i++){const a=i*Math.PI*2/200;pts.push(new THREE.Vector3(r*Math.cos(a),r*Math.sin(a),0))}const l=line(pts,.5+(j%3)*.14,j%4===0?pale:gold);l.rotation.set(rand()*Math.PI,rand()*Math.PI,rand()*Math.PI)}
for(let j=0;j<14;j++)orbit(1.1+rand()*1.6,j%3,rand()*6.28,200,.45+rand()*.35);
// Partículas luminosas no volume esférico.
const count=2600,pos=new Float32Array(count*3);for(let i=0;i<count;i++){const r=1.1+Math.cbrt(rand())*2.05,theta=Math.acos(2*rand()-1),phi=rand()*Math.PI*2,p=spherePoint(r,theta,phi);pos.set([p.x,p.y,p.z],i*3)}
const pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.BufferAttribute(pos,3));const particles=new THREE.Points(pg,new THREE.PointsMaterial({color:0xffbf55,size:.04,transparent:true,opacity:1,depthWrite:false,blending:THREE.AdditiveBlending}));root.add(particles);tintables.push(particles.material);
const core=new THREE.Mesh(new THREE.IcosahedronGeometry(.35,2),new THREE.MeshBasicMaterial({color:0xffa900,wireframe:true,transparent:true,opacity:1}));root.add(core);tintables.push(core.material);
const glow=new THREE.Sprite(new THREE.SpriteMaterial({map:(()=>{const cv=document.createElement('canvas');cv.width=cv.height=128;const ctx=cv.getContext('2d'),g=ctx.createRadialGradient(64,64,0,64,64,64);g.addColorStop(0,'rgba(255,235,175,.85)');g.addColorStop(.15,'rgba(255,166,38,.35)');g.addColorStop(1,'rgba(255,140,0,0)');ctx.fillStyle=g;ctx.fillRect(0,0,128,128);return new THREE.CanvasTexture(cv)})(),transparent:true,blending:THREE.AdditiveBlending,depthWrite:false}));glow.scale.set(2.8,2.8,1);root.add(glow);
tintables.push(glow.material);
applyState('starting');
const rotX=.16, rotY=0;
renderer.domElement.style.pointerEvents='none';
const clock=new THREE.Clock();
function animate(){
 requestAnimationFrame(animate);
 const dt=Math.min(.05,clock.getDelta());
 const t=clock.elapsedTime;
 // Interpolate both color and motion: state changes never snap.
 const blend=1-Math.exp(-dt*5.5);
 const audioBlend=1-Math.exp(-dt*14);
 displayColor.lerp(targetColor,blend);
 for(const material of tintables) material.color.copy(displayColor);
 speakingMix+=((currentState==='speaking'?1:0)-speakingMix)*blend;
 listeningMix+=((currentState==='listening'?1:0)-listeningMix)*blend;
 motionLevel+=(voiceLevel-motionLevel)*audioBlend;
 heardLevel+=((currentState==='listening'?micLevel:0)-heardLevel)*audioBlend;
 // Orange: outward movement from TTS. Green: inward pressure from actual mic RMS.
 const targetScale=1+.29*motionLevel*speakingMix-(.035+.31*heardLevel)*listeningMix;
 currentScale+=(targetScale-currentScale)*blend;
 root.scale.setScalar(currentScale);
 const targetCore=1+.68*motionLevel*speakingMix-(.025+.24*heardLevel)*listeningMix;
 currentCoreScale+=(targetCore-currentCoreScale)*blend;
 core.scale.setScalar(currentCoreScale);
 particles.material.size=.04*(1+.72*motionLevel*speakingMix);
 const targetGlow=1+.38*motionLevel*speakingMix-(.02+.26*heardLevel)*listeningMix;
 currentGlowScale+=(targetGlow-currentGlowScale)*blend;
 root.rotation.y=rotY+t*.07;
 root.rotation.x=rotX+Math.sin(t*.22)*.08;
 core.rotation.y=t*.23;core.rotation.x=t*.16;
 glow.scale.set(2.8*currentGlowScale,2.8*currentGlowScale,1);
 glow.material.opacity=.7+Math.sin(t*1.8)*.15;
 renderer.render(scene,camera);
}
animate();
addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight)});
// Estado mantido para futuras reações visuais, sem mostrar textos na tela.
window.angelaSetState=applyState;
window.angelaGetState=()=>currentState;
window.angelaChatAdd=(item)=>{
 const log=document.getElementById('angela-chat-log');
 if(!log)return;
 const entry=document.createElement('div');entry.className='chat-entry';
 const by=document.createElement('span');by.className='by';by.textContent=item.role==='user'?'Você (reconhecido)':'Ângela';
 const content=document.createElement('div');content.textContent=String(item.text||'').slice(0,600);
 entry.append(by,content);log.appendChild(entry);
 while(log.children.length>7)log.firstElementChild.remove();
 const feedback=document.getElementById('angela-feedback');
 if(feedback)feedback.style.display=item.feedback?'block':'none';
};
window.angelaFeedbackSaved=()=>{const el=document.getElementById('angela-feedback');if(el)el.style.display='none';};
// Painel de texto com DOM simples: sem canvas adicional e sem HTML gerado por IA.
let panelTimer=null;
window.angelaShowPanel=(data)=>{
 const panel=document.getElementById('angela-panel');
 const items=Array.isArray(data?.items)?data.items.slice(0,80):[];
 document.getElementById('panel-title').textContent=String(data?.title||'Informações').slice(0,80);
 document.getElementById('panel-count').textContent=items.length+' pastas encontradas';
 const ul=document.getElementById('panel-list');ul.replaceChildren();
 items.slice(0,15).forEach(name=>{
   const li=document.createElement('li');li.textContent=String(name).slice(0,100);ul.appendChild(li);
 });
 document.getElementById('panel-more').textContent=items.length>15?('+'+(items.length-15)+' pastas adicionais'):'';
 panel.classList.add('visible');
 if(panelTimer)clearTimeout(panelTimer);
 panelTimer=setTimeout(()=>{panel.classList.remove('visible');panelTimer=null;},30000);
};
