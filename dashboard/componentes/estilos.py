"""CSS del prototipo (dashboard/prototipo.html) adaptado a Streamlit, con tema claro y oscuro."""
from dashboard.componentes.ui import css_icono, estilo

TEMAS = {
    "dark": {
        "color-scheme": "dark",
        "--bg": "#0A0F1E",
        "--bg-grad": "radial-gradient(1100px 620px at 85% -15%,rgba(124,140,255,.12),transparent 60%),"
                     "radial-gradient(900px 520px at -10% 115%,rgba(183,148,246,.08),transparent 60%)",
        "--side": "#0C1224", "--card": "#10172E", "--card-2": "#141C36", "--card-3": "#1A2342",
        "--hover": "rgba(148,163,210,.06)", "--border": "rgba(148,163,210,.10)", "--border-2": "rgba(148,163,210,.18)",
        "--text": "#E8ECF6", "--muted": "#97A2BC", "--faint": "#5F6A86",
        "--accent": "#8C9EFF", "--accent-2": "#B79CFF", "--accent-soft": "rgba(140,158,255,.13)",
        "--bajo": "#5FBF95", "--medio": "#E5B85C", "--alto": "#F07178", "--sindato": "#3E4866",
        "--info": "#74A9FF", "--adv": "#E5B85C", "--crit": "#F07178", "--ok": "#5FBF95", "--insp": "#B79CFF",
        "--shadow": "0 1px 0 rgba(255,255,255,.03) inset,0 14px 34px -18px rgba(0,0,0,.6)",
        "--on-accent": "#0B1020",
    },
    "light": {
        "color-scheme": "light",
        "--bg": "#F3F5FA",
        "--bg-grad": "radial-gradient(1100px 620px at 85% -15%,rgba(91,108,240,.09),transparent 60%),"
                     "radial-gradient(900px 520px at -10% 115%,rgba(139,92,246,.06),transparent 60%)",
        "--side": "#FFFFFF", "--card": "#FFFFFF", "--card-2": "#F6F8FC", "--card-3": "#EDF0F7",
        "--hover": "rgba(30,41,80,.035)", "--border": "rgba(30,41,80,.08)", "--border-2": "rgba(30,41,80,.14)",
        "--text": "#141A2E", "--muted": "#5C6680", "--faint": "#9AA3B8",
        "--accent": "#5B6CF0", "--accent-2": "#8B5CF6", "--accent-soft": "rgba(91,108,240,.10)",
        "--bajo": "#2E9E6E", "--medio": "#C98A1B", "--alto": "#E0525C", "--sindato": "#C3CADB",
        "--info": "#3B7DF0", "--adv": "#C98A1B", "--crit": "#E0525C", "--ok": "#2E9E6E", "--insp": "#8B5CF6",
        "--shadow": "0 1px 2px rgba(20,26,46,.04),0 14px 34px -20px rgba(20,26,46,.22)",
        "--on-accent": "#FFFFFF",
    },
}

# Reglas del prototipo (sin cambios salvo los selectores de tema).
PROTOTIPO = """
*{box-sizing:border-box}
.ic{flex:none;display:block}
.muted{color:var(--muted)} .faint{color:var(--faint)} .small{font-size:12.5px} .tiny{font-size:11.5px}
.spacer{flex:1}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.between{justify-content:space-between}
.stack{display:flex;flex-direction:column;gap:18px;min-width:0}
.num{font-variant-numeric:tabular-nums}
.brand{display:flex;align-items:center;gap:12px;padding:0 8px}
.brand .name{font-weight:700;font-size:15.5px;letter-spacing:-.01em;color:var(--text)}
.brand .sub{color:var(--muted);font-size:12px}
.nav-t{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);padding:0 12px 6px;font-weight:600}
.side-foot{padding:14px;border-radius:16px;background:var(--card-2);border:1px solid var(--border)}
.top h1{font-size:23px;margin:0;padding:0;font-weight:700;letter-spacing:-.02em;color:var(--text);line-height:1.3}
.top .sub{color:var(--muted);font-size:13px;margin-top:2px}
.clock{display:flex;align-items:center;gap:12px;padding:8px 14px;border-radius:14px;background:var(--card);border:1px solid var(--border);box-shadow:var(--shadow);width:max-content;margin-left:auto}
.clock .t{font-size:18px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.01em;line-height:1.3}
.clock .d{font-size:12px;color:var(--muted);line-height:1.3}
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:20px;box-shadow:var(--shadow);min-width:0}
.card-hd{display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.card h3,.h3{margin:0;padding:0;font-size:15px;font-weight:650;letter-spacing:-.01em;color:var(--text);line-height:1.4}
.card .sub,.sub{color:var(--muted);font-size:12.5px}
.sec{font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--faint);font-weight:650;margin:18px 0 10px}
.ico-box{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;flex:none;color:var(--c,var(--accent));background:color-mix(in srgb,var(--c,var(--accent)) 14%,transparent)}
.ico-box.sm{width:32px;height:32px;border-radius:10px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap;
  background:color-mix(in srgb,var(--c,var(--muted)) 13%,transparent);color:color-mix(in srgb,var(--c,var(--muted)) 88%,var(--text))}
.chip .d{width:6px;height:6px;border-radius:50%;background:var(--c,var(--muted))}
.chip.pulse .d{animation:pulse 1.6s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--c) 60%,transparent)}70%{box-shadow:0 0 0 6px transparent}100%{box-shadow:0 0 0 0 transparent}}
.c-bajo{--c:var(--bajo)} .c-medio{--c:var(--medio)} .c-alto{--c:var(--alto)} .c-sindato{--c:var(--faint)}
.c-info{--c:var(--info)} .c-advertencia{--c:var(--adv)} .c-critica{--c:var(--crit)}
.c-ok{--c:var(--ok)} .c-primary{--c:var(--accent)} .c-insp{--c:var(--insp)} .c-mute{--c:var(--faint)}
.bar{height:6px;background:var(--card-3);border-radius:999px;overflow:hidden}
.bar>i{display:block;height:100%;background:var(--c,var(--accent));border-radius:999px;transition:width .4s}
.empty{text-align:center;padding:46px 20px;color:var(--muted)}
.empty .ico-box{margin:0 auto 12px;width:48px;height:48px;border-radius:14px}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:32px;margin-bottom:26px}
.kpi{display:flex;flex-direction:column;gap:12px;padding:0}
.kpi .v{font-size:30px;font-weight:700;letter-spacing:-.02em;line-height:1;font-variant-numeric:tabular-nums;color:var(--text)}
.kpi .l{color:var(--muted);font-size:12.5px;font-weight:550}
.kpi .d{font-size:12px;color:var(--faint)}
.kpi .d b{color:var(--text);font-weight:600}
.kpi .spark{height:30px;width:96px}
.bcard{text-align:left;padding:12px 0 0;border-top:2px solid var(--border);display:flex;flex-direction:column;gap:10px;transition:.18s}
.bcard b{font-size:13.5px;color:var(--text)}
.bcard .alarm{width:8px;height:8px;border-radius:50%;background:var(--crit);box-shadow:0 0 0 3px color-mix(in srgb,var(--crit) 22%,transparent)}
.bcard.on{border-top-color:var(--accent)}
.mini{display:grid;grid-template-columns:repeat(12,1fr);gap:2px}
.mini i{height:7px;border-radius:2px;display:block}
.bmeta{display:flex;justify-content:space-between;gap:8px;white-space:nowrap;font-size:11.5px;color:var(--muted)}
.robot-pos{padding:0;margin-bottom:16px}
.robot-pos .v{font-size:21px;font-weight:700;letter-spacing:-.01em;color:var(--text)}
.stats2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.stat{padding:12px;border-radius:14px;background:var(--card-2);border:1px solid var(--border)}
.pano .stat{background:transparent;border:0;padding:0}
.stat .l{font-size:11.5px;color:var(--muted);display:flex;gap:6px;align-items:center}
.stat .v{font-size:18px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums;color:var(--text)}
.rank-i{display:grid;grid-template-columns:minmax(0,1fr) 70px 44px;gap:12px;align-items:center;padding:9px 0;border-radius:11px;transition:background .15s}
.rank-i .p{text-align:right;font-weight:650;font-size:12.5px;font-variant-numeric:tabular-nums}
.gauge-card{display:grid;grid-template-columns:1.25fr 1fr;gap:12px;margin-top:18px}
.gauge{padding:16px;border-radius:16px;background:var(--card-2);border:1px solid var(--border);display:flex;flex-direction:column;align-items:center}
.gauge .v{font-size:28px;font-weight:750;margin-top:-48px;margin-bottom:14px;letter-spacing:-.02em}
.gauge .l{font-size:12px;color:var(--muted);text-align:center}
.factores{display:flex;flex-direction:column;gap:8px}
.factor{display:flex;gap:12px;align-items:center;padding:10px 12px;border-radius:13px;background:var(--card-2);border:1px solid var(--border);font-size:13px}
.factor b{font-weight:650}
.chart{width:100%;height:auto;display:block}
.chart text{font-family:var(--font)}
.leyenda{display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:var(--muted);margin-top:6px}
.leyenda i{display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle;margin-right:6px}
.tl{position:relative;padding-left:22px}
.tl::before{content:"";position:absolute;left:6px;top:6px;bottom:6px;width:2px;background:var(--border-2);border-radius:2px}
.tl .ev{position:relative;padding:0 0 14px}
.tl .ev::before{content:"";position:absolute;left:-21px;top:5px;width:10px;height:10px;border-radius:50%;background:var(--c,var(--muted));box-shadow:0 0 0 4px var(--card)}
.tl .ev .h{font-size:11.5px;color:var(--faint);font-variant-numeric:tabular-nums}
.tl .ev .t{font-weight:600;font-size:13px}
.acard-h{display:flex;gap:14px;align-items:center;padding:14px 16px}
.acard .tt,.acard-h .tt{font-weight:650;font-size:13.5px;color:var(--text)}
.acard-h .meta{font-size:12px;color:var(--muted);margin-top:2px}
.msg{margin:0 0 4px;font-size:13.5px;color:var(--muted);line-height:1.55}
.acol-hd{display:flex;gap:14px;align-items:center;padding:16px 18px;border-radius:16px;background:color-mix(in srgb,var(--c) 7%,var(--card));border:1px solid color-mix(in srgb,var(--c) 22%,var(--border))}
.acol-hd h3{margin:0;padding:0;font-size:15.5px;font-weight:700;letter-spacing:-.01em;color:var(--text)}
.acol-hd .sub{color:var(--muted);font-size:12.5px}
.acol-n{text-align:right}
.acol-n .v{font-size:26px;font-weight:750;line-height:1;letter-spacing:-.02em;color:var(--text)}
.newdot{width:8px;height:8px;border-radius:50%;background:var(--c);flex:none}
.chev{color:var(--faint);transition:transform .2s}
.chev.open{transform:rotate(180deg)}
.pipe{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:0;position:relative}
.pipe-i{display:flex;flex-direction:column;align-items:center;gap:8px;position:relative;padding:4px 6px;text-align:center}
.pipe-i::before{content:"";position:absolute;top:21px;left:-50%;right:50%;height:2px;background:var(--border-2);z-index:0}
.pipe-i:first-child::before{display:none}
.pipe-i .n{width:44px;height:44px;border-radius:14px;display:grid;place-items:center;font-weight:750;font-size:16px;position:relative;z-index:1;
  background:color-mix(in srgb,var(--c) 14%,var(--card));color:var(--c);border:1px solid color-mix(in srgb,var(--c) 30%,transparent)}
.pipe-i .l{font-size:12px;color:var(--muted);font-weight:550}
.trow{display:grid;grid-template-columns:48px minmax(130px,1.3fr) 50px 84px minmax(140px,1fr) 56px 72px 104px;gap:0;align-items:center;border-bottom:1px solid var(--border);font-variant-numeric:tabular-nums;font-size:13px;min-width:700px}
.trow>span{padding:11px 10px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.trow.th>span{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);font-weight:650;padding:10px}
.trow.sel{background:var(--accent-soft)}
.vgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.vcard{padding:14px;border-radius:15px;background:var(--card-2);border:1px solid var(--border);display:flex;flex-direction:column;gap:8px}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.tile .v{font-size:28px;font-weight:750;letter-spacing:-.02em;margin:12px 0 2px;font-variant-numeric:tabular-nums}
.tile .l{font-weight:600;font-size:13px}
.tile .d{font-size:12px;color:var(--muted);margin-top:4px}
.hbar{display:grid;grid-template-columns:120px minmax(0,1fr) 36px;gap:12px;align-items:center;font-size:12.5px;padding:5px 0}
.hbar .bar{height:8px}
.toast-t{font-weight:650;font-size:13.5px;margin-bottom:2px}
@media (max-width:1100px){.kpis,.grid4{grid-template-columns:repeat(2,minmax(0,1fr))}.grid2{grid-template-columns:minmax(0,1fr)}}
@media (max-width:900px){.pipe{grid-template-columns:repeat(3,minmax(0,1fr));row-gap:14px}}
@media (max-width:560px){.kpis,.grid4{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px}.kpi .v{font-size:24px}.kpi .spark{display:none}.clock .d{display:none}.top h1{font-size:19px}.gauge-card{grid-template-columns:1fr}}
"""

# Streamlit: fondo, márgenes, barra lateral, botones, diálogo y elementos ocultos.
STREAMLIT = """
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--bg)!important;color:var(--text);font-family:var(--font)!important;-webkit-font-smoothing:antialiased}
.stApp{font-size:14px;line-height:1.5}
.stApp{background-image:var(--bg-grad)!important;background-attachment:fixed!important}
[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:transparent!important}
.stApp *{font-family:var(--font)}
.stApp p,.stApp li{color:inherit}
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],
#MainMenu,footer,[data-testid="stSidebarHeader"],[data-testid="stSidebarCollapseButton"],[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarNav"]{display:none!important}
[data-testid="stMainBlockContainer"]{padding:0 32px 48px!important;max-width:none!important}
.stElementContainer:has(>.stMarkdown style:only-child),.stElementContainer:has(style.solo){display:none}
[data-testid="stMarkdownContainer"]{color:var(--text);font-size:14px;line-height:1.5;margin-bottom:0!important}
[data-testid="stMarkdownContainer"] p{margin:0}
[data-testid="stVerticalBlock"]{gap:14px}
[data-testid="stSidebar"]{background:color-mix(in srgb,var(--side) 82%,transparent)!important;backdrop-filter:blur(16px);border-right:1px solid var(--border);width:248px!important;min-width:248px!important;max-width:248px!important}
[data-testid="stSidebar"]>div:first-child{background:transparent;width:248px!important}
[data-testid="stSidebarContent"]{padding:24px 6px 18px;position:relative;height:100vh}
[data-testid="stSidebarUserContent"]>div{padding:0!important}
[data-testid="stSidebarUserContent"]{padding:0!important}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:4px}
.st-key-brand{margin-bottom:26px}
.st-key-pie{position:absolute!important;left:6px;width:216px!important;bottom:18px}
.st-key-nav-t,.nav-t{margin-top:0}
.st-key-pie [data-testid="stVerticalBlock"]{gap:10px}
.st-key-nav [data-testid="stVerticalBlock"]{gap:4px}
.st-key-nav button{display:flex;align-items:center;justify-content:flex-start;gap:12px;padding:10px 12px!important;border-radius:12px;color:var(--muted);font-weight:550;width:100%;text-align:left;background:transparent;border:0;transition:background .15s,color .15s;min-height:0;box-shadow:none}
.st-key-nav button>div{flex:0 1 auto;justify-content:flex-start;text-align:left}.st-key-nav button p{text-align:left;font-size:14px!important;font-weight:550!important;line-height:21px!important}
.st-key-nav button:hover{background:var(--hover);color:var(--text);border:0}
.st-key-nav button:focus:not(:active),.st-key-nav button:focus-visible{border:0;box-shadow:none;color:var(--muted)}
.st-key-nav button::after{margin-left:auto;min-width:22px;height:20px;padding:0 7px;border-radius:999px;font-size:11.5px;font-weight:650;display:inline-grid;place-items:center;background:var(--card-3);color:var(--muted)}
.stButton>button,.stDownloadButton>button{font:inherit}
[data-testid^="stBaseButton-"]{min-height:0;line-height:1.5}
button [data-testid="stMarkdownContainer"],[data-baseweb="select"] [data-testid="stMarkdownContainer"]{font-size:inherit!important;line-height:inherit!important}
[data-testid^="stBaseButton-"] p{font-size:inherit!important;font-weight:inherit!important;margin:0;line-height:inherit}
[data-testid="stBaseButton-secondary"]{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:11px;background:var(--card-2);border:1px solid var(--border);font-weight:600;font-size:13px;color:var(--text);transition:.15s}
[data-testid="stBaseButton-secondary"]:hover{border-color:var(--border-2);background:var(--card-3);color:var(--text)}
[data-testid="stBaseButton-secondary"]:focus:not(:active){border-color:var(--border);color:var(--text)}
[data-testid="stBaseButton-primary"]{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:11px;background:var(--accent);border:1px solid transparent;color:var(--on-accent);font-weight:600;font-size:13px;transition:.15s}
[data-testid="stBaseButton-primary"]:hover{filter:brightness(1.07);background:var(--accent);border-color:transparent;color:var(--on-accent)}
[data-testid="stBaseButton-primary"]:focus:not(:active){color:var(--on-accent);border-color:transparent}
[data-testid="stBaseButton-tertiary"]{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:11px;background:transparent;border:1px solid transparent;color:var(--muted);font-weight:600;font-size:13px}
[data-testid="stBaseButton-tertiary"]:hover{color:var(--text);background:var(--hover)}
[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-tertiary"]{font-size:13px!important;font-weight:600!important;padding:8px 14px!important;line-height:19.5px!important}
[class*="st-key-seg_"]{display:inline-flex!important;flex-direction:row!important;width:max-content!important;max-width:100%;flex-wrap:wrap;background:var(--card-2);border:1px solid var(--border);border-radius:12px;padding:3px;gap:2px!important}
[class*="st-key-seg_"]>.stElementContainer{width:auto!important;flex:0 0 auto!important}
[class*="st-key-seg_"] button{border-radius:9px!important;padding:6px 12px!important;color:var(--muted)!important;font-weight:600;font-size:12.5px!important;background:transparent!important;border:0!important;box-shadow:none!important;filter:none!important}
[class*="st-key-seg_"] button:hover{color:var(--text)!important}
[class*="st-key-seg_"] [data-testid="stBaseButton-primary"]{background:var(--card)!important;color:var(--text)!important;box-shadow:0 1px 3px rgba(0,0,0,.18),0 0 0 1px var(--border-2)!important}
.stLayoutWrapper:has(>[class*="st-key-seg_"]),[class*="st-key-seg_"]{flex:0 0 auto!important}
[class*="st-key-card_"]{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:20px;box-shadow:var(--shadow);min-width:0}
[class*="st-key-filtros"]{padding:14px 16px}
[class*="st-key-clk_"]{position:relative;gap:0!important}
.st-key-tblwrap,.st-key-tblwrap [data-testid="stVerticalBlock"]{gap:0!important}
[class*="st-key-btn_"]{position:absolute!important;inset:0;z-index:3;margin:0!important;width:auto!important;height:auto!important}
[class*="st-key-btn_"] .stButton,[class*="st-key-btn_"] .stButton>div,[class*="st-key-btn_"] button{width:100%!important;height:100%!important;min-height:0;opacity:0;padding:0;border:0;cursor:pointer}
[class*="st-key-clk_rank"]:hover,[class*="st-key-clk_trow"]:hover,[class*="st-key-clk_dpos"]:hover{background:var(--hover);border-radius:11px}
[class*="st-key-clk_bcard"]:hover .bcard{border-top-color:var(--border-2)}
[class*="st-key-clk_bcard"]:hover .bcard.on{border-top-color:var(--accent)}
[class*="st-key-acard_"]{background:var(--card);border:1px solid var(--border);border-radius:16px;box-shadow:var(--shadow);overflow:hidden;gap:0!important}
[class*="st-key-acard_"].nueva,[class*="st-key-acard_n"]{border-color:color-mix(in srgb,var(--c) 35%,var(--border))}
[class*="st-key-clk_ah"]:hover{background:var(--hover)}
[class*="st-key-ab_"]{padding:0 16px 16px 68px;gap:14px!important}
[class*="st-key-acc_"]{gap:10px!important;align-items:center}
.st-key-celular button{width:100%;justify-content:center}.st-key-celular button>div{flex:0 0 auto!important}
[data-testid="stSelectbox"] label{display:none}
[data-testid="stSelectbox"] [data-baseweb="select"] div{background:transparent!important;border-color:transparent!important}
[data-testid="stSelectbox"] [data-baseweb="select"]{background:var(--card-2)!important;border-radius:11px}
[data-testid="stSelectbox"] [data-baseweb="select"]>div{background:var(--card-2)!important;border:1px solid var(--border)!important;border-radius:11px!important;color:var(--text)!important;font-size:13px;font-weight:550;min-height:0}
[data-testid="stSelectbox"] [data-baseweb="select"] *{color:var(--text)!important;font-size:13px!important;font-weight:550}
[data-baseweb="popover"] [role="listbox"],[data-baseweb="popover"] ul{background:var(--card)!important;border:1px solid var(--border-2);border-radius:12px}
[data-baseweb="popover"] li{color:var(--text)!important;font-size:13px}
[data-baseweb="popover"] li:hover,[data-baseweb="popover"] li[aria-selected="true"]{background:var(--hover)!important}
[data-testid="stDialog"]>div{width:min(560px,calc(100vw - 24px))!important;max-width:none!important;margin:12px;height:calc(100% - 24px);border-radius:22px;overflow:hidden;border:1px solid var(--border-2);box-shadow:0 30px 80px -20px rgba(0,0,0,.55)}
[data-testid="stDialog"] [role="dialog"]{width:100%!important;max-width:none!important;background:var(--card)!important;color:var(--text);border:0!important;border-radius:0!important}
[data-testid="stDialog"] [role="dialog"]>button{position:absolute;right:24px;top:24px;z-index:5;width:40px;height:40px;border-radius:12px;background:var(--card);border:1px solid var(--border);color:var(--muted)}
[data-testid="stDialog"] [role="dialog"]>h2{display:none}
.drawer .drawer-t{margin:2px 0 0;font-size:24px;letter-spacing:-.02em;color:var(--text);font-weight:700;padding:0}
[data-testid="stToast"]{background:var(--card)!important;border:1px solid var(--border-2);border-radius:16px!important;color:var(--text)!important;box-shadow:0 20px 50px -18px rgba(0,0,0,.55)}
[data-testid="stToast"] *{color:var(--text)}
iframe{color-scheme:normal;background:transparent!important}[data-testid="stCustomComponentV1"],iframe[title*="mapa3d"]{border:0;display:block}
.st-key-top{padding:28px 0 26px}
.st-key-top [data-testid="stHorizontalBlock"]{align-items:center}
.st-key-boton_tema button,.st-key-campana button{width:40px;height:40px;padding:0!important;justify-content:center;border-radius:12px!important;background:var(--card)!important;border:1px solid var(--border)!important;color:var(--muted)!important;box-shadow:var(--shadow);position:relative}
.st-key-boton_tema button p,.st-key-campana button p{display:none}
.st-key-boton_tema button:hover,.st-key-campana button:hover{color:var(--text)!important;border-color:var(--border-2)!important}
.st-key-campana.dot button::after,.campana-dot .st-key-campana button::after{content:"";position:absolute;top:8px;right:9px;width:8px;height:8px;border-radius:50%;background:var(--crit);box-shadow:0 0 0 2px var(--card)}
[class*="st-key-chip_"] button{padding:3px 10px!important;border-radius:999px!important;font-size:12px!important;font-weight:600;border:0!important;background:color-mix(in srgb,var(--adv) 13%,transparent)!important;color:color-mix(in srgb,var(--adv) 88%,var(--text))!important}
.st-key-chips{gap:6px!important}
.st-key-pano_side{gap:0!important}
.st-key-bloques{margin-top:28px}
@media (max-width:1280px){.st-key-finca>[data-testid="stHorizontalBlock"]{flex-direction:column}.st-key-finca [data-testid="stColumn"]{width:100%!important;flex:1 1 100%!important}}
@media (max-width:1100px){.st-key-bloques [data-testid="stHorizontalBlock"]{flex-wrap:wrap}.st-key-bloques [data-testid="stColumn"]{min-width:calc(50% - 16px)!important;flex:1 1 calc(50% - 16px)!important}
  .st-key-acols>[data-testid="stHorizontalBlock"],.st-key-incs>[data-testid="stHorizontalBlock"],.st-key-vent>[data-testid="stHorizontalBlock"]{flex-direction:column}
  .st-key-acols [data-testid="stColumn"],.st-key-incs [data-testid="stColumn"],.st-key-vent [data-testid="stColumn"]{width:100%!important;flex:1 1 100%!important}}
@media (max-width:900px){
  [data-testid="stSidebar"]{position:fixed!important;inset:auto 0 0 0!important;top:auto!important;width:100%!important;min-width:0!important;max-width:none!important;height:auto!important;transform:none!important;visibility:visible!important;z-index:999990;border-right:0;border-top:1px solid var(--border)}
  [data-testid="stSidebarContent"]{padding:6px 8px;height:auto}
  .st-key-brand,.st-key-pie,.nav-t{display:none!important}
  .st-key-nav{flex-direction:row!important;justify-content:space-around;gap:0!important}
  .st-key-nav>.stElementContainer:first-child{display:none!important}
  .st-key-nav>.stElementContainer{flex:1 1 0!important;width:auto!important;min-width:0}
  .st-key-nav button{flex-direction:column;gap:3px;padding:7px 4px!important;font-size:10.5px;align-items:center;justify-content:center}
  .st-key-nav button::after{display:none}
  .st-key-nav button p{white-space:nowrap;font-size:10.5px!important;overflow:hidden;text-overflow:ellipsis}
  [data-testid="stMainBlockContainer"]{padding:0 16px 96px!important}
  .st-key-top [data-testid="stHorizontalBlock"]{flex-wrap:wrap}
}
"""


def variables(tema: str) -> str:
    """Bloque :root con las variables del tema."""
    t = TEMAS.get(tema, TEMAS["dark"])
    cuerpo = ";".join(f"{k}:{v}" for k, v in t.items())
    return (f":root{{{cuerpo};--r:18px;--r-sm:12px;"
            '--font:"Inter","SF Pro Text",system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}')


ICONOS_FIJOS = [("tema_dark", "sun", 18), ("tema_light", "moon", 18), ("campana", "bell", 18),
                ("celular", "phone", 15), ("csv", "download", 15)]


def inyectar(tema: str) -> None:
    """CSS completo de la página para el tema elegido."""
    iconos = "".join(css_icono(k, n, s) for k, n, s in ICONOS_FIJOS if not k.startswith("tema_"))
    iconos += css_icono("boton_tema", "sun" if tema == "dark" else "moon", 18)
    estilo(variables(tema) + PROTOTIPO + STREAMLIT + iconos)
