'use strict';
/* Motor del tour guiado (vanilla JS, sin librerías ni CDN).
   Corre dentro del iframe del componente y dibuja overlay, spotlight y recuadro en la página de Streamlit
   (window.parent, mismo origen). Python decide el paso y la hora simulada; aquí solo se pinta y se mandan eventos:
   siguiente | anterior | salir | repetir | iniciar | tick. */

/* ---------- protocolo de componentes de Streamlit (v1), igual que mapa3d ---------- */
const Streamlit = {
  enviar(type, extra){ window.parent.postMessage(Object.assign({isStreamlitMessage:true, type}, extra), '*'); },
  listo(){ this.enviar('streamlit:componentReady', {apiVersion:1}); },
  valor(v){ this.enviar('streamlit:setComponentValue', {value:v, dataType:'json'}); },
  alto(h){ this.enviar('streamlit:setFrameHeight', {height:h}); },
};

const P = window.parent, PD = P.document;
const G = P.__bgiTour || (P.__bgiTour = {n:0, auto:false, teclado:false, intervalo:0, clave:null, desde:0, scroll:null});
const VISTO = 'bgi_tour_visto';
const PAD = 8, MARGEN = 16, SEP = 14;
let A = {activo:false};
let reloj = 0;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const limitar = (v, a, b) => Math.max(a, Math.min(b, v));

function visto(){ try { return localStorage.getItem(VISTO) !== null; } catch(e){ return false; } }
function marcarVisto(){ try { localStorage.setItem(VISTO, '1'); } catch(e){} }

function enviar(accion, extra){
  G.n += 1;
  Streamlit.valor(Object.assign({accion, n:`${Date.now()}-${G.n}`}, extra || {}));
}

/* ---------- acciones del recuadro y del teclado ---------- */
function accion(a){
  if(!A.activo || G.ocupado) return;
  if(A.error) a = 'salir';
  if(a === 'siguiente' && A.buscando) return;
  if(a === 'siguiente' && A.paso >= A.total - 1) a = 'salir';
  if(a === 'anterior' && A.paso <= 0) return;
  if(a === 'salir' || a === 'repetir') marcarVisto();
  G.ocupado = true;
  PD.querySelectorAll('#bgi-tour .bgi-box button').forEach(b => b.disabled = true);
  setTimeout(() => { G.ocupado = false; }, 1500);      // por si el siguiente dibujo no llega
  enviar(a);
}

function tecla(e){
  if(!A.activo) return;
  const k = e.key;
  let a = null;
  if(k === 'ArrowRight' || k === 'Enter' || k === ' ' || k === 'PageDown') a = 'siguiente';
  else if(k === 'ArrowLeft' || k === 'PageUp') a = 'anterior';
  else if(k === 'Escape') a = 'salir';
  if(!a) return;
  e.preventDefault(); e.stopPropagation();
  accion(a);
}

/* El documento padre llama siempre a las funciones del iframe vivo (Streamlit puede recrear el iframe). */
G.accion = accion; G.tecla = tecla; G.reubicar = reubicar;
if(!G.teclado){
  G.teclado = true;
  P.addEventListener('keydown', e => { try { G.tecla(e); } catch(err){} }, true);
  P.addEventListener('resize', () => { try { G.reubicar(); } catch(err){} });
  PD.addEventListener('scroll', () => { try { G.reubicar(); } catch(err){} }, true);
}

/* ---------- DOM del overlay ---------- */
function asegurarCss(){
  if(PD.getElementById('bgi-tour-css')) return;
  const l = PD.createElement('link');
  l.id = 'bgi-tour-css'; l.rel = 'stylesheet'; l.href = new URL('tour.css', location.href).href;
  PD.head.appendChild(l);
}

function raiz(){
  let r = PD.getElementById('bgi-tour');
  if(r) return r;
  r = PD.createElement('div');
  r.id = 'bgi-tour';
  r.innerHTML = '<div class="bgi-bloqueo"></div><div class="bgi-spot"></div>'
              + '<div class="bgi-box" role="dialog" aria-modal="true" aria-live="polite" tabindex="-1"></div>';
  r.querySelector('.bgi-box').addEventListener('click', e => {
    const b = e.target.closest('button[data-a]');
    if(b && !b.disabled) G.accion(b.dataset.a);
  });
  r.querySelector('.bgi-bloqueo').addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); });
  PD.body.appendChild(r);
  return r;
}

function quitar(){
  PD.getElementById('bgi-tour')?.remove();
  if(G.intervalo){ P.clearInterval(G.intervalo); G.intervalo = 0; }
  G.clave = null;
}

function contenido(){
  if(A.error){
    return '<div class="bgi-n">Tour guiado</div><h2>No se puede iniciar el tour</h2>'
         + `<p>${esc(A.error)}</p><div class="bgi-btns"><span></span><button data-a="salir" class="pri">Cerrar</button></div>`;
  }
  const ultimo = A.paso >= A.total - 1;
  const estado = A.buscando
    ? `<div class="bgi-busca"><span class="bgi-giro"></span>Avanzando simulación… <b>${esc(A.reloj)}</b></div>`
    : (A.reloj ? `<div class="bgi-reloj">${esc(A.reloj)}</div>` : '');
  const botones = ultimo
    ? '<button data-a="repetir">Ver de nuevo</button><span></span><button data-a="salir" class="pri">Terminar</button>'
    : '<button data-a="salir" class="lnk">Saltar tour</button><span></span>'
      + `<button data-a="anterior" ${A.paso === 0 ? 'disabled' : ''}>Anterior</button>`
      + `<button data-a="siguiente" class="pri" ${A.buscando ? 'disabled' : ''}>Siguiente</button>`;
  return `<div class="bgi-prog"><i style="width:${(A.paso + 1) / A.total * 100}%"></i></div>`
       + `<div class="bgi-n">${A.paso + 1} / ${A.total}</div><h2>${esc(A.titulo)}</h2><p>${esc(A.texto)}</p>`
       + `${estado}<div class="bgi-btns">${botones}</div>`;
}

/* ---------- posición del spotlight y del recuadro ---------- */
function objetivo(){
  if(A.error || !A.target) return null;
  let el = null;
  try { el = PD.querySelector(A.target); } catch(e){ return null; }
  if(el && A.cerca) el = el.closest(A.cerca) || el;
  if(!el) return null;
  const r = el.getBoundingClientRect();
  return (r.width < 2 && r.height < 2) ? null : {el, r};
}

function colocarBox(box, x, y, w, h, vw, vh){
  const bw = box.offsetWidth, bh = box.offsetHeight;
  const lados = [
    {ok: vh - (y + h) >= bh + SEP + MARGEN, left: x + w / 2 - bw / 2, top: y + h + SEP},
    {ok: y >= bh + SEP + MARGEN,            left: x + w / 2 - bw / 2, top: y - SEP - bh},
    {ok: vw - (x + w) >= bw + SEP + MARGEN, left: x + w + SEP,        top: y + h / 2 - bh / 2},
    {ok: x >= bw + SEP + MARGEN,            left: x - SEP - bw,       top: y + h / 2 - bh / 2},
  ];
  const l = lados.find(o => o.ok) || {left: x + w - bw - MARGEN, top: y + h - bh - MARGEN};   // no cabe afuera: esquina interior
  box.style.left = limitar(l.left, MARGEN, vw - bw - MARGEN) + 'px';
  box.style.top = limitar(l.top, MARGEN, vh - bh - MARGEN) + 'px';
}

function reubicar(){
  const r = PD.getElementById('bgi-tour');
  if(!r || !A.activo) return;
  const spot = r.querySelector('.bgi-spot'), box = r.querySelector('.bgi-box'), bloqueo = r.querySelector('.bgi-bloqueo');
  const vw = P.innerWidth, vh = P.innerHeight;
  let o = objetivo();
  if(o && G.scroll !== G.clave && (o.r.top < 0 || o.r.bottom > vh)){
    G.scroll = G.clave;
    const lento = !P.matchMedia('(prefers-reduced-motion: reduce)').matches;
    o.el.scrollIntoView({block: o.r.height < vh - 2 * MARGEN ? 'center' : 'start', behavior: lento ? 'smooth' : 'auto'});
    o = objetivo();
  }
  const esperando = !o && A.target && !A.error && Date.now() - G.desde < (A.espera_ms || 2000);
  r.classList.toggle('sin-target', !o);
  box.style.visibility = esperando ? 'hidden' : 'visible';
  if(!o){
    bloqueo.style.clipPath = 'none';
    box.style.left = Math.max(MARGEN, (vw - box.offsetWidth) / 2) + 'px';
    box.style.top = Math.max(MARGEN, (vh - box.offsetHeight) / 2) + 'px';
    return;
  }
  let x = o.r.left - PAD, y = o.r.top - PAD;
  const x2 = Math.min(vw - 4, x + o.r.width + 2 * PAD), y2 = Math.min(vh - 4, y + o.r.height + 2 * PAD);
  x = Math.max(4, x); y = Math.max(4, y);
  const w = Math.max(0, x2 - x), h = Math.max(0, y2 - y);
  Object.assign(spot.style, {left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px'});
  bloqueo.style.clipPath = A.permitir
    ? `polygon(evenodd, 0 0, 100% 0, 100% 100%, 0 100%, 0 0, ${x}px ${y}px, ${x + w}px ${y}px, ${x + w}px ${y + h}px, ${x}px ${y + h}px, ${x}px ${y}px)`
    : 'none';
  colocarBox(box, x, y, w, h, vw, vh);
}

/* ---------- dibujo con los args de Python ---------- */
function render(args){
  A = args || {activo:false};
  G.ocupado = false;
  clearTimeout(reloj);
  if(!A.activo){
    quitar();
    if(A.auto && !G.auto){ G.auto = true; if(!visto()) enviar('iniciar', {auto:true}); }
  } else {
    asegurarCss();
    const r = raiz(), box = r.querySelector('.bgi-box');
    const clave = A.error ? 'error' : `${A.paso}`;
    const nuevo = clave !== G.clave;
    if(nuevo){ G.clave = clave; G.desde = Date.now(); }
    const html = contenido();
    if(box.innerHTML !== html) box.innerHTML = html;
    if(nuevo) box.focus({preventScroll:true});
    reubicar();
    if(!G.intervalo) G.intervalo = P.setInterval(() => { try { G.reubicar(); } catch(err){} }, 250);
  }
  if(A.tick_ms > 0) reloj = setTimeout(() => enviar('tick'), A.tick_ms);
}

window.addEventListener('message', e => {
  const m = e.data;
  if(!m || m.type !== 'streamlit:render') return;
  render(m.args);
});
Streamlit.listo();
Streamlit.alto(0);
