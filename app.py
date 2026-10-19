"""TiendaPlus — mini-ERP estilo app de supermercado (Flask + SQLite). INDEL 3.° Desarrollo de Software "B", 2026."""
import os, csv, json, re, sqlite3
from functools import wraps
from urllib.parse import quote_plus
from flask import Flask, g, redirect, render_template_string as render, request, session, url_for, flash, abort
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambiar-en-produccion")
BASE_DIR = os.path.dirname(__file__)
DB = os.path.join(BASE_DIR, "tiendaplus.db")
CATALOGO_CSV = os.path.join(BASE_DIR, "database", "catalogo_super_selectos.csv")
CATALOGO_VERSION = "super_selectos_v1"
IMAGENES_JSON = os.path.join(BASE_DIR, "database", "imagenes.json")
IMAGENES_VERSION = "off_v1"

def _cargar_imagenes():
    try:
        with open(IMAGENES_JSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

IMAGENES = _cargar_imagenes()

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(clave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS roles(id_rol INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS usuarios(id_usuario INTEGER PRIMARY KEY, nombre TEXT NOT NULL, usuario TEXT NOT NULL UNIQUE,
  clave_hash TEXT NOT NULL, id_rol INTEGER NOT NULL REFERENCES roles(id_rol), activo INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS categorias(id_categoria INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS productos(id_producto INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
  precio REAL NOT NULL CHECK(precio>=0), stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0),
  stock_minimo INTEGER NOT NULL DEFAULT 5 CHECK(stock_minimo>=0), imagen TEXT,
  id_categoria INTEGER NOT NULL REFERENCES categorias(id_categoria), activo INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS clientes(id_cliente INTEGER PRIMARY KEY, nombre TEXT NOT NULL, telefono TEXT);
CREATE TABLE IF NOT EXISTS ventas(id_venta INTEGER PRIMARY KEY, fecha TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  id_cliente INTEGER NOT NULL REFERENCES clientes(id_cliente), id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
  total REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS detalle_venta(id_detalle INTEGER PRIMARY KEY, id_venta INTEGER NOT NULL REFERENCES ventas(id_venta),
  id_producto INTEGER NOT NULL REFERENCES productos(id_producto), cantidad INTEGER NOT NULL CHECK(cantidad>0), precio REAL NOT NULL);
"""

EMOJI = {"Frutas": "🍎", "Verduras y hortalizas": "🥬", "Granos y cereales": "🌾", "Pastas y sopas": "🍝",
         "Aceites, condimentos y salsas": "🫙", "Enlatados y conservas": "🥫", "Panadería y repostería": "🍞",
         "Lácteos y huevos": "🥛", "Carnes, aves y pescados": "🥩", "Bebidas": "🥤", "Snacks y dulces": "🍫",
         "Higiene personal y baño": "🧼", "Cuidado del bebé": "🍼", "Limpieza del hogar": "🧽",
         "Hogar y ferretería ligera": "🔧", "Papelería y escolar": "✏️", "Mascotas": "🐾",
         "Farmacia y salud básica": "💊", "Comida preparada y deli": "🍗"}

PRECIOS = {"Frutas": (0.25, 1.75), "Verduras y hortalizas": (0.30, 1.75), "Granos y cereales": (0.75, 3.50),
           "Pastas y sopas": (0.45, 2.75), "Aceites, condimentos y salsas": (0.50, 7.50),
           "Enlatados y conservas": (0.85, 4.00), "Panadería y repostería": (0.20, 4.50),
           "Lácteos y huevos": (0.60, 5.00), "Carnes, aves y pescados": (1.50, 8.50), "Bebidas": (0.35, 6.50),
           "Snacks y dulces": (0.25, 3.50), "Higiene personal y baño": (0.80, 8.50), "Cuidado del bebé": (3.00, 20.00),
           "Limpieza del hogar": (0.60, 6.50), "Hogar y ferretería ligera": (0.50, 25.00),
           "Papelería y escolar": (0.20, 6.50), "Mascotas": (1.00, 25.00), "Farmacia y salud básica": (0.75, 10.00),
           "Comida preparada y deli": (0.75, 8.00)}

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def cerrar(_):
    c = g.pop("db", None)
    if c:
        c.close()

@app.before_request
def _refrescar_sesion():
    if session.get("uid"):
        u = db().execute("SELECT u.nombre, r.nombre AS rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=? AND u.activo=1",
                         (session["uid"],)).fetchone()
        if not u:
            session.clear()
        else:
            session["rol"] = u["rol"]
            session["nombre"] = u["nombre"]

def icono(nombre):
    return EMOJI.get(nombre, "🛍️")

def imagen_url(nombre):
    return IMAGENES.get(nombre) or ""

FONDO_DEF = "#dfe8e1"
SUPERFICIE_DEF = "#f4f7f4"
HEADER_DEF = "#00843d"
HEADER2_DEF = "#006b31"
COLORES_FONDO = ["#dfe8e1", "#f4f7f4", "#ffffff", "#eef2f7", "#fdf6e3", "#fdeef2",
                 "#e7f5ec", "#e8f0fe", "#fff3e0", "#eceff1", "#2a3b2f", "#15271c"]
COLORES_HEADER = ["#00843d", "#006b31", "#0b7285", "#1c7ed6", "#5c940d", "#f76707",
                  "#e03131", "#ae3ec9", "#d6336c", "#343a40", "#212529"]

def color_tema():
    if "tema_bg" not in g:
        r = db().execute("SELECT valor FROM meta WHERE clave='tema_bg'").fetchone()
        g.tema_bg = (r["valor"] if r and r["valor"] else "")
    return g.tema_bg

def color_header():
    if "tema_header" not in g:
        r = db().execute("SELECT valor FROM meta WHERE clave='tema_header'").fetchone()
        g.tema_header = (r["valor"] if r and r["valor"] else "")
    return g.tema_header

def oscurecer(color, factor=0.8):
    color = color.lstrip("#")
    r, gg, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % (int(r * factor), int(gg * factor), int(b * factor))

def cargar_catalogo(c):
    if not os.path.exists(CATALOGO_CSV):
        return
    c.execute("DELETE FROM detalle_venta")
    c.execute("DELETE FROM ventas")
    c.execute("DELETE FROM productos")
    c.execute("DELETE FROM categorias")
    ids = {}
    with open(CATALOGO_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cat = row["Categoría"].strip()
            if cat not in ids:
                c.execute("INSERT INTO categorias(nombre) VALUES(?)", (cat,))
                ids[cat] = c.execute("SELECT id_categoria FROM categorias WHERE nombre=?", (cat,)).fetchone()[0]
            prod = row["Producto"].strip()
            pres = row["Presentación"].strip()
            rid = int(row["ID"])
            nombre = f"{prod} — {pres}" if pres else prod
            lo, hi = PRECIOS.get(cat, (0.50, 5.00))
            precio = round(lo + ((rid * 37) % 100) / 100 * (hi - lo), 2)
            c.execute("INSERT INTO productos(nombre,precio,stock,stock_minimo,id_categoria,imagen) VALUES(?,?,?,?,?,?)",
                      (nombre, precio, 12 + (rid * 13) % 40, 5, ids[cat], imagen_url(nombre)))

def iniciar_bd():
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)
    if "imagen" not in [r[1] for r in c.execute("PRAGMA table_info(productos)").fetchall()]:
        c.execute("ALTER TABLE productos ADD COLUMN imagen TEXT")
    if not c.execute("SELECT 1 FROM roles").fetchone():
        c.executemany("INSERT INTO roles(nombre) VALUES(?)", [("Admin",), ("Cajero",)])
        c.executemany("INSERT INTO usuarios(nombre,usuario,clave_hash,id_rol) VALUES(?,?,?,?)", [
            ("Administrador", "admin", generate_password_hash("admin123"), 1),
            ("Cajero", "cajero", generate_password_hash("cajero123"), 2)])
        c.execute("INSERT INTO clientes(nombre) VALUES('Cliente general')")
    if c.execute("SELECT 1 FROM meta WHERE clave='admin_v1'").fetchone() is None:
        c.execute("UPDATE roles SET nombre='Admin' WHERE nombre='Dueño'")
        c.execute("UPDATE usuarios SET nombre='Administrador', usuario='admin', clave_hash=? WHERE usuario='dueno'",
                  (generate_password_hash("admin123"),))
        c.execute("INSERT OR REPLACE INTO meta(clave,valor) VALUES('admin_v1','1')")
    if c.execute("SELECT 1 FROM meta WHERE clave='catalogo'").fetchone() is None:
        cargar_catalogo(c)
        c.execute("INSERT OR REPLACE INTO meta(clave,valor) VALUES('catalogo',?)", (CATALOGO_VERSION,))
    if IMAGENES and c.execute("SELECT valor FROM meta WHERE clave='imagenes'").fetchone() != (IMAGENES_VERSION,):
        for pid, nombre in c.execute("SELECT id_producto,nombre FROM productos").fetchall():
            url = IMAGENES.get(nombre)
            if url:
                c.execute("UPDATE productos SET imagen=? WHERE id_producto=?", (url, pid))
        c.execute("INSERT OR REPLACE INTO meta(clave,valor) VALUES('imagenes',?)", (IMAGENES_VERSION,))
    c.commit()
    c.close()

def acceso(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if "uid" not in session:
                return redirect(url_for("login"))
            if roles and session["rol"] not in roles:
                flash("No tienes permiso para entrar ahí.", "err")
                return redirect(url_for("inicio"))
            return f(*a, **k)
        return w
    return deco

def rejilla(ps, volver):
    return render(GRID, ps=ps, volver=volver, icono=icono, admin=(session.get("rol") == "Admin"))

BASE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TiendaPlus</title><style>
:root{--green:#00843d;--green2:#006b31;--soft:#e9f2ea;--ink:#15271c;--muted:#6b7d70;--bg:{{tema_bg}};--surface:{{tema_surface}};--header:{{tema_header}};--header2:{{tema_header2}}}
*{box-sizing:border-box}
body{margin:0;font-family:Calibri,"Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--ink)}
.app{max-width:480px;margin:0 auto;min-height:100vh;background:var(--surface);padding-bottom:78px;box-shadow:0 0 24px #0002}
.topbar{position:sticky;top:0;z-index:15;background:linear-gradient(135deg,var(--header),var(--header2));color:#fff;padding:.65rem .8rem;display:flex;align-items:center;gap:.6rem}
.topbar .brand{font-weight:800;font-size:1.15rem;color:#fff;text-decoration:none;white-space:nowrap}
.search{flex:1;display:flex}.search input{width:100%;border:0;border-radius:20px;padding:.45rem .8rem;background:#ffffff26;color:#fff}
.search input::placeholder{color:#ffffffcc}
.cartbtn{position:relative;color:#fff;text-decoration:none;font-size:1.3rem;padding:0 .2rem}
.cartbtn .badge{position:absolute;top:-6px;right:-8px;background:#ffd100;color:#1a1a1a;border-radius:12px;font-size:.65rem;font-weight:800;padding:0 5px}
.layout{display:block}
.sidenav{display:none}
main{padding:.8rem}
.card{background:#fff;border-radius:14px;padding:.9rem;margin-bottom:.8rem;box-shadow:0 1px 6px #00000010}
h1{font-size:1.15rem;margin:.1rem 0 .7rem;color:var(--green2)}h2{font-size:1rem;margin:.2rem 0 .6rem;color:var(--green2)}
a{color:var(--green2)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:.7rem}
.pcard{background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 1px 6px #00000012;display:flex;flex-direction:column}
.pimg{position:relative;aspect-ratio:1;background:var(--soft);display:flex;align-items:center;justify-content:center}
.pimg .pfallback{font-size:2.6rem}
.pimg img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.pimg .delcard{position:absolute;top:4px;right:4px;z-index:3;margin:0}
.pimg .delcard button{background:#e5483a;color:#fff;border:0;border-radius:50%;width:26px;height:26px;padding:0;font-size:.85rem;font-weight:800;line-height:1;cursor:pointer;box-shadow:0 1px 4px #0006}
.pimg .edcard{position:absolute;top:4px;left:4px;z-index:3;margin:0;background:#fff;color:#22382b;border-radius:50%;width:26px;height:26px;line-height:1;display:flex;align-items:center;justify-content:center;font-size:.8rem;text-decoration:none;box-shadow:0 1px 4px #0006}
.pbody{padding:.5rem .6rem .7rem;display:flex;flex-direction:column;gap:.2rem;flex:1}
.pname{font-size:.82rem;font-weight:600;line-height:1.15;min-height:2.2em}
.pstock{font-size:.7rem;color:var(--muted)}.pstock.low{color:#d9480f;font-weight:700}
.pprice{color:var(--green);font-weight:800}
.addbtn{margin-top:.35rem;background:var(--green);color:#fff;border:0;border-radius:9px;padding:.42rem;font-weight:700;cursor:pointer;width:100%}
.addbtn:disabled{background:#c2d3c6;cursor:default}
.cats{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:.7rem}
.cattile{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.3rem;background:#fff;border-radius:14px;padding:1rem;text-decoration:none;color:var(--ink);box-shadow:0 1px 6px #00000012;min-height:104px;text-align:center;position:relative}
.cattile .ico{font-size:2rem}.cattile small{color:var(--muted)}
.cattile .editcat{position:absolute;top:6px;right:6px;z-index:3;background:#fff;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:.8rem;box-shadow:0 1px 4px #0006;cursor:pointer}
.stats{display:flex;gap:.6rem;flex-wrap:wrap}.stats div{flex:1;min-width:90px;background:var(--soft);border-radius:12px;padding:.6rem}
.stats strong{display:block;font-size:1.4rem;color:var(--green)}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #e2ebe4;padding:.45rem .4rem;text-align:left;font-size:.9rem}
th{color:var(--green2)}tr.bajo td{background:#ffe3e0}tr.grupo td{background:var(--soft);font-weight:800;color:var(--green2)}
input,select,button{font:inherit}
input,select{border:1px solid #c6d6ca;border-radius:9px;padding:.45rem .6rem;width:100%}
button{background:var(--green);color:#fff;border:0;border-radius:9px;padding:.45rem .8rem;cursor:pointer}
button.rojo{background:#e5483a}
.fila{display:flex;flex-direction:column;gap:.5rem}
.btn{display:inline-block;background:var(--green);color:#fff;text-decoration:none;border-radius:9px;padding:.45rem .8rem}
.btn.gris{background:#c9d6cd;color:#22382b}
.msg{padding:.6rem .8rem;border-radius:10px;margin-bottom:.7rem}.ok{background:#d6f2e0}.err{background:#ffe0dc}
.empty{grid-column:1/-1;color:var(--muted);text-align:center;padding:1rem}
.catbar{display:flex;gap:.4rem;overflow-x:auto;padding:.2rem 0 .5rem}
.catbar a{white-space:nowrap;background:#fff;border-radius:20px;padding:.3rem .7rem;text-decoration:none;color:var(--green2);font-size:.8rem;box-shadow:0 1px 4px #00000012}
.catbar a.on{background:var(--green);color:#fff}
.qty{display:flex;align-items:center;gap:.4rem}.qty button{padding:.15rem .55rem}
.row{display:flex;gap:.6rem;align-items:center;border-bottom:1px solid #e2ebe4;padding:.5rem 0}
.bottomnav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:480px;background:#fff;border-top:1px solid #dbe6de;display:flex;z-index:20;overflow-x:auto}
.bottomnav a{flex:1 1 0;min-width:60px;text-align:center;padding:.45rem 0 .5rem;color:#7a8b7f;text-decoration:none;font-size:.68rem;display:flex;flex-direction:column;gap:1px}
.bottomnav a .ni{font-size:1.3rem}.bottomnav a.on{color:var(--green);font-weight:800}
@media (min-width:820px){
.app{max-width:1080px;padding-bottom:0;background:var(--surface)}
.layout{display:flex;align-items:flex-start;gap:1rem;padding:1rem}
main{flex:1;min-width:0;padding:0}
.sidenav{display:flex;flex-direction:column;width:220px;flex:0 0 220px;position:sticky;top:76px;background:#fff;border-radius:14px;padding:.5rem;box-shadow:0 1px 6px #00000010}
.sidenav a{display:flex;align-items:center;gap:.6rem;padding:.6rem .8rem;border-radius:10px;text-decoration:none;color:#2a3b2f;font-weight:600}
.sidenav a.on{background:var(--green);color:#fff}
.sidenav .ni{font-size:1.15rem}
.bottomnav{display:none}
}
</style></head><body><div class="app">
{% macro navlinks() %}
<a href="/" class="{{'on' if nav=='inicio'}}"><span class="ni">🏠</span><span>Inicio</span></a>
{% if session.rol=='Admin' %}
<a href="/reportes" class="{{'on' if nav=='reportes'}}"><span class="ni">📊</span><span>Reportes</span></a>
<a href="/productos" class="{{'on' if nav=='productos'}}"><span class="ni">📦</span><span>Productos</span></a>
<a href="/gestion-categorias" class="{{'on' if nav=='categorias'}}"><span class="ni">🗂️</span><span>Categorías</span></a>
<a href="/usuarios" class="{{'on' if nav=='usuarios'}}"><span class="ni">🔑</span><span>Usuarios</span></a>
<a href="/configuracion" class="{{'on' if nav=='colores'}}"><span class="ni">🎨</span><span>Colores</span></a>
{% else %}
<a href="/categorias" class="{{'on' if nav=='cat'}}"><span class="ni">🗂️</span><span>Categorías</span></a>
{% endif %}
<a href="/carrito" class="{{'on' if nav=='cart'}}"><span class="ni">🛒</span><span>Carrito</span></a>
<a href="/clientes" class="{{'on' if nav=='clientes'}}"><span class="ni">👥</span><span>Clientes</span></a>
<a href="/cuenta" class="{{'on' if nav=='cuenta'}}"><span class="ni">👤</span><span>Cuenta</span></a>
{% endmacro %}
<header class="topbar"><a class="brand" href="/">TiendaPlus</a>
{% if session.uid %}<form class="search" action="/buscar" method="get"><input name="q" placeholder="Buscar productos..."></form>
<a class="cartbtn" href="/carrito">🛒{% if cart_count %}<span class="badge">{{cart_count}}</span>{% endif %}</a>{% endif %}</header>
<div class="layout">
{% if session.uid %}<nav class="sidenav">{{ navlinks() }}</nav>{% endif %}
<main>{% for cat,m in get_flashed_messages(with_categories=true) %}<div class="msg {{cat}}">{{m}}</div>{% endfor %}{{body|safe}}</main>
</div>
{% if session.uid %}<nav class="bottomnav">{{ navlinks() }}</nav>{% endif %}</div></body></html>"""

GRID = """<div class="grid">{% for p in ps %}
<div class="pcard"><div class="pimg"><span class="pfallback">{{icono(p.cat)}}</span>{% if p.imagen %}<img src="{{p.imagen}}" alt="" loading="lazy" onerror="this.style.display='none'">{% endif %}{% if admin %}<a class="edcard" href="/productos/{{p.id_producto}}" title="Editar">✏️</a><form method="post" action="/productos/{{p.id_producto}}/borrar" class="delcard" onsubmit="return confirm('¿Eliminar {{p.nombre}}?')"><input type="hidden" name="volver" value="{{volver}}"><button title="Eliminar">✕</button></form>{% endif %}</div>
<div class="pbody"><div class="pname">{{p.nombre}}</div>
<div class="pstock {{'low' if p.stock<=p.stock_minimo}}">{{'⚠ Quedan '~p.stock if p.stock<=p.stock_minimo else p.cat}}</div>
<div class="pprice">${{'%.2f'|format(p.precio)}}</div>
{% if p.stock>0 %}<form method="post" action="/carrito"><input type="hidden" name="accion" value="agregar"><input type="hidden" name="producto" value="{{p.id_producto}}"><input type="hidden" name="cantidad" value="1"><input type="hidden" name="volver" value="{{volver}}"><button class="addbtn">＋ Agregar</button></form>
{% else %}<button class="addbtn" disabled>Agotado</button>{% endif %}
</div></div>{% else %}<div class="empty">No hay productos por aquí.</div>{% endfor %}</div>"""

def pagina(cuerpo, nav="", **ctx):
    cnt = sum(session.get("carrito", {}).values()) if session.get("uid") else 0
    ctx.setdefault("icono", icono)
    fondo = color_tema() or FONDO_DEF
    head = color_header()
    return render(BASE, body=render(cuerpo, **ctx), nav=nav, cart_count=cnt,
                  tema_bg=fondo, tema_surface=(fondo if color_tema() else SUPERFICIE_DEF),
                  tema_header=(head or HEADER_DEF), tema_header2=(oscurecer(head) if head else HEADER2_DEF))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT u.*, r.nombre AS rol FROM usuarios u JOIN roles r USING(id_rol) WHERE usuario=? AND activo=1",
                         (request.form["usuario"].strip(),)).fetchone()
        if u and check_password_hash(u["clave_hash"], request.form["clave"]):
            session.clear()
            session.update(uid=u["id_usuario"], nombre=u["nombre"], rol=u["rol"], carrito={})
            return redirect(url_for("inicio"))
        flash("Usuario o contraseña incorrectos.", "err")
    return pagina("""<div class="card" style="max-width:360px;margin:1.5rem auto">
<div style="text-align:center;font-size:2.4rem">🛒</div><h1 style="text-align:center">TiendaPlus</h1>
<form method="post" class="fila"><label>Usuario<input name="usuario" required autofocus></label>
<label>Contraseña<input name="clave" type="password" required></label><button>Entrar</button></form>
<p class="pstock" style="text-align:center;margin-top:.6rem">Demo: admin/admin123 · cajero/cajero123</p></div>""")

@app.route("/salir")
def salir():
    session.clear()
    return redirect(url_for("login"))

def _mosaico(d):
    return d.execute("""SELECT c.id_categoria, c.nombre, COUNT(p.id_producto) n
                        FROM categorias c LEFT JOIN productos p ON p.id_categoria=c.id_categoria AND p.activo=1
                        GROUP BY c.id_categoria ORDER BY c.nombre""").fetchall()

@app.route("/")
@acceso()
def inicio():
    d = db()
    cats = _mosaico(d)
    destacados = d.execute("""SELECT p.*, c.nombre cat FROM productos p JOIN categorias c USING(id_categoria)
                              WHERE p.activo=1 AND p.stock>0 ORDER BY RANDOM() LIMIT 8""").fetchall()
    hoy = bajo = None
    if session["rol"] == "Admin":
        hoy = d.execute("SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM ventas WHERE date(fecha)=date('now','localtime')").fetchone()
        bajo = d.execute("SELECT COUNT(*) n FROM productos WHERE activo=1 AND stock<=stock_minimo").fetchone()
    return pagina("""{% if hoy %}<div class="card"><div class="stats">
<div>Ventas de hoy<strong>${{'%.2f'|format(hoy.t)}}</strong></div><div>N.º de ventas<strong>{{hoy.n}}</strong></div>
<div>Stock bajo<strong>{{bajo.n}}</strong></div></div></div>{% endif %}
<div class="card"><h2>Categorías</h2><div class="cats">
{% for c in cats %}<a class="cattile" href="/categoria/{{c.id_categoria}}"><span class="ico">{{icono(c.nombre)}}</span>{{c.nombre}}<small>{{c.n}} productos</small>{% if session.rol=='Admin' %}<span class="editcat" data-name="{{c.nombre}}" title="Cambiar nombre" onclick="return renCat(this,event,{{c.id_categoria}})">✏️</span>{% endif %}</a>{% endfor %}
</div>{% if session.rol=='Admin' %}<form id="renF" method="post" style="display:none"><input type="hidden" name="nombre"><input type="hidden" name="volver" value="/"></form>
<script>function renCat(el,e,id){e.preventDefault();e.stopPropagation();var n=prompt('Nuevo nombre de la categoría:',el.getAttribute('data-name'));if(n&&n.trim()){var f=document.getElementById('renF');f.action='/categorias/'+id+'/renombrar';f.querySelector('[name=nombre]').value=n.trim();f.submit()}return false}</script>{% endif %}</div>
<div class="card"><h2>Recomendados</h2><div class="grid">
{% for p in destacados %}<div class="pcard"><div class="pimg"><span class="pfallback">{{icono(p.cat)}}</span>{% if p.imagen %}<img src="{{p.imagen}}" alt="" loading="lazy" onerror="this.style.display='none'">{% endif %}{% if session.rol=='Admin' %}<a class="edcard" href="/productos/{{p.id_producto}}" title="Editar">✏️</a><form method="post" action="/productos/{{p.id_producto}}/borrar" class="delcard" onsubmit="return confirm('¿Eliminar {{p.nombre}}?')"><input type="hidden" name="volver" value="/"><button title="Eliminar">✕</button></form>{% endif %}</div>
<div class="pbody"><div class="pname">{{p.nombre}}</div><div class="pstock">{{p.cat}}</div><div class="pprice">${{'%.2f'|format(p.precio)}}</div>
<form method="post" action="/carrito"><input type="hidden" name="accion" value="agregar"><input type="hidden" name="producto" value="{{p.id_producto}}"><input type="hidden" name="cantidad" value="1"><input type="hidden" name="volver" value="/"><button class="addbtn">＋ Agregar</button></form>
</div></div>{% else %}<div class="empty">Sin productos.</div>{% endfor %}</div></div>""",
                  nav="inicio", cats=cats, destacados=destacados, hoy=hoy, bajo=bajo)

@app.route("/categorias")
@acceso()
def categorias():
    cats = _mosaico(db())
    return pagina("""<div class="card"><h1>Categorías</h1><div class="cats">
{% for c in cats %}<a class="cattile" href="/categoria/{{c.id_categoria}}"><span class="ico">{{icono(c.nombre)}}</span>{{c.nombre}}<small>{{c.n}} productos</small></a>{% endfor %}
</div></div>""", nav="cat", cats=cats)

@app.route("/categoria/<int:cid>")
@acceso()
def categoria(cid):
    d = db()
    cat = d.execute("SELECT * FROM categorias WHERE id_categoria=?", (cid,)).fetchone()
    if not cat:
        flash("Esa categoría no existe.", "err")
        return redirect(url_for("categorias"))
    ps = d.execute("""SELECT p.*, c.nombre cat FROM productos p JOIN categorias c USING(id_categoria)
                      WHERE p.activo=1 AND p.id_categoria=? ORDER BY p.nombre""", (cid,)).fetchall()
    cats = _mosaico(d)
    return pagina("""<div class="card"><h1>{{icono(cat.nombre)}} {{cat.nombre}}</h1>
<div class="catbar"><a class="on" href="/categoria/{{cat.id_categoria}}">{{cat.nombre}}</a>
{% for c in cats if c.id_categoria!=cat.id_categoria %}<a href="/categoria/{{c.id_categoria}}">{{c.nombre}}</a>{% endfor %}</div>
{{rejilla(ps, request.path)|safe}}</div>""", nav="cat", cat=cat, cats=cats, rejilla=rejilla, ps=ps)

@app.route("/buscar")
@acceso()
def buscar():
    q = request.args.get("q", "").strip()
    d = db()
    ps = d.execute("""SELECT p.*, c.nombre cat FROM productos p JOIN categorias c USING(id_categoria)
                      WHERE p.activo=1 AND p.nombre LIKE ? ORDER BY p.nombre""", (f"%{q}%",)).fetchall() if q else []
    return pagina("""<div class="card"><h1>Buscar «{{q}}»</h1>{{rejilla(ps, request.path)|safe}}</div>""",
                  nav="", q=q, ps=ps, rejilla=rejilla)

@app.route("/carrito", methods=["GET", "POST"])
@acceso()
def carrito():
    d = db()
    cart = session.setdefault("carrito", {})
    if request.method == "POST":
        accion = request.form.get("accion")
        if accion in ("agregar", "mas", "menos", "quitar"):
            pid = request.form.get("producto")
            if accion == "agregar":
                cart[pid] = cart.get(pid, 0) + max(int(request.form.get("cantidad") or 1), 1)
            elif accion == "mas":
                cart[pid] = cart.get(pid, 0) + 1
            elif accion == "menos":
                n = cart.get(pid, 0) - 1
                (cart.pop(pid, None) if n <= 0 else cart.__setitem__(pid, n))
            elif accion == "quitar":
                cart.pop(pid, None)
            session.modified = True
            volver = request.form.get("volver", "")
            return redirect(volver if volver.startswith("/") else url_for("carrito"))
        if accion == "cobrar" and cart:
            try:
                d.execute("BEGIN")
                vid = d.execute("INSERT INTO ventas(id_cliente,id_usuario) VALUES(?,?)", (request.form["cliente"], session["uid"])).lastrowid
                total = 0
                for pid, cant in cart.items():
                    p = d.execute("SELECT nombre,precio FROM productos WHERE id_producto=?", (pid,)).fetchone()
                    if d.execute("UPDATE productos SET stock=stock-? WHERE id_producto=? AND stock>=?", (cant, pid, cant)).rowcount == 0:
                        raise ValueError(f"Stock insuficiente para {p['nombre']}.")
                    d.execute("INSERT INTO detalle_venta(id_venta,id_producto,cantidad,precio) VALUES(?,?,?,?)", (vid, pid, cant, p["precio"]))
                    total += cant * p["precio"]
                d.execute("UPDATE ventas SET total=? WHERE id_venta=?", (total, vid))
                d.commit()
                cart.clear()
                flash(f"Venta #{vid} registrada. Total: ${total:.2f}", "ok")
            except ValueError as e:
                d.rollback()
                flash(str(e), "err")
        session.modified = True
        return redirect(url_for("carrito"))
    items, total = [], 0
    for pid, cant in list(cart.items()):
        p = d.execute("""SELECT p.*, c.nombre cat FROM productos p JOIN categorias c USING(id_categoria)
                         WHERE p.id_producto=?""", (pid,)).fetchone()
        if not p:
            cart.pop(pid, None); continue
        items.append((p, cant, cant * p["precio"])); total += cant * p["precio"]
    cs = d.execute("SELECT * FROM clientes ORDER BY id_cliente").fetchall()
    return pagina("""<div class="card"><h1>Mi carrito 🛒</h1>
{% for p,c,s in items %}<div class="row"><div style="font-size:1.8rem">{{icono(p.cat)}}</div>
<div style="flex:1"><div class="pname">{{p.nombre}}</div><div class="pstock">${{'%.2f'|format(p.precio)}} c/u</div></div>
<form method="post" class="qty"><input type="hidden" name="accion" value="menos"><input type="hidden" name="producto" value="{{p.id_producto}}"><button>−</button></form>
<strong>{{c}}</strong>
<form method="post" class="qty"><input type="hidden" name="accion" value="mas"><input type="hidden" name="producto" value="{{p.id_producto}}"><button>＋</button></form>
<div style="width:64px;text-align:right;font-weight:800">${{'%.2f'|format(s)}}</div>
<form method="post"><input type="hidden" name="accion" value="quitar"><input type="hidden" name="producto" value="{{p.id_producto}}"><button class="rojo">🗑</button></form></div>
{% else %}<div class="empty">Tu carrito está vacío. Agrega productos del catálogo.</div>{% endfor %}
{% if items %}<div class="stats" style="margin-top:.8rem"><div>Total<strong>${{'%.2f'|format(total)}}</strong></div></div>
<form method="post" class="fila" style="margin-top:.6rem"><input type="hidden" name="accion" value="cobrar">
<label>Cliente<select name="cliente">{% for c in cs %}<option value="{{c.id_cliente}}">{{c.nombre}}</option>{% endfor %}</select></label>
<button>💳 Cobrar ${{'%.2f'|format(total)}}</button></form>{% endif %}
<a class="btn gris" href="/" style="margin-top:.6rem">Seguir comprando</a></div>""",
                  nav="cart", items=items, total=total, cs=cs)

@app.route("/ventas")
@acceso()
def ventas():
    return redirect(url_for("carrito"))

@app.route("/cuenta")
@acceso()
def cuenta():
    return pagina("""<div class="card"><div style="text-align:center"><div style="font-size:3rem">👤</div>
<h1 style="margin-bottom:.1rem">{{session.nombre}}</h1><div class="pstock">Rol: {{session.rol}}</div></div></div>
<div class="card"><h2>Opciones</h2><div class="fila">
{% if session.rol=='Admin' %}<a class="btn" href="/reportes">📊 Reportes y dashboard</a>
<a class="btn" href="/productos">📦 Gestionar productos</a>
<a class="btn" href="/gestion-categorias">🗂️ Gestionar categorías</a>
<a class="btn" href="/usuarios">🔑 Gestionar usuarios</a>
<a class="btn" href="/configuracion">🎨 Personalización</a>{% endif %}
<a class="btn" href="/clientes">👥 Clientes</a>
<a class="btn" style="background:#e5483a;text-align:center" href="/salir">Cerrar sesión</a></div></div>""",
                  nav="cuenta")

@app.route("/reportes")
@acceso("Admin")
def reportes():
    d = db()
    hoy = d.execute("SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM ventas WHERE date(fecha)=date('now','localtime')").fetchone()
    top = d.execute("""SELECT p.nombre, SUM(x.cantidad) u FROM detalle_venta x JOIN productos p USING(id_producto)
                       GROUP BY p.nombre ORDER BY u DESC LIMIT 5""").fetchall()
    bajo = d.execute("SELECT nombre, stock, stock_minimo FROM productos WHERE activo=1 AND stock<=stock_minimo").fetchall()
    return pagina("""<div class="card"><h1>Reportes</h1><div class="stats">
<div>Ventas de hoy<strong>${{'%.2f'|format(hoy.t)}}</strong></div><div>N.º de ventas<strong>{{hoy.n}}</strong></div>
<div>Stock bajo<strong>{{bajo|length}}</strong></div></div></div>
<div class="card"><h2>Top 5 más vendidos</h2><table><tr><th>Producto</th><th>Unidades</th></tr>
{% for r in top %}<tr><td>{{r.nombre}}</td><td>{{r.u}}</td></tr>{% else %}<tr><td colspan="2">Aún no hay ventas.</td></tr>{% endfor %}</table></div>
<div class="card"><h2>Alertas de stock bajo</h2><table><tr><th>Producto</th><th>Stock</th><th>Mínimo</th></tr>
{% for r in bajo %}<tr class="bajo"><td>{{r.nombre}}</td><td>{{r.stock}}</td><td>{{r.stock_minimo}}</td></tr>
{% else %}<tr><td colspan="3">Todo el inventario está bien.</td></tr>{% endfor %}</table></div>""",
                  nav="reportes", hoy=hoy, top=top, bajo=bajo)

@app.route("/productos")
@acceso("Admin")
def productos():
    d = db()
    cat_sel = request.args.get("cat", type=int)
    cats = _mosaico(d)
    sql = "SELECT p.*, c.nombre cat FROM productos p JOIN categorias c USING(id_categoria) WHERE p.activo=1"
    params = ()
    if cat_sel:
        sql += " AND p.id_categoria=?"; params = (cat_sel,)
    ps = d.execute(sql + " ORDER BY c.nombre, p.nombre", params).fetchall()
    return pagina("""<div class="card"><h1>Productos</h1><p><a class="btn" href="/productos/0">＋ Nuevo producto</a></p>
<div class="catbar"><a class="{{'on' if not cat_sel}}" href="/productos">Todos</a>
{% for c in cats %}<a class="{{'on' if cat_sel==c.id_categoria}}" href="/productos?cat={{c.id_categoria}}">{{c.nombre}} ({{c.n}})</a>{% endfor %}</div>
<table><tr><th>Producto</th><th>Precio</th><th>Stock</th><th></th></tr>
{% set ns = namespace(cat='') %}
{% for p in ps %}{% if p.cat != ns.cat %}{% set ns.cat = p.cat %}<tr class="grupo"><td colspan="4">{{icono(p.cat)}} {{p.cat}}</td></tr>{% endif %}
<tr class="{{'bajo' if p.stock<=p.stock_minimo}}"><td>{{p.nombre}}</td>
<td>${{'%.2f'|format(p.precio)}}</td><td>{{p.stock}}{% if p.stock<=p.stock_minimo %} ⚠{% endif %}</td>
<td style="text-align:right;white-space:nowrap"><a href="/productos/{{p.id_producto}}">Editar</a>
<form method="post" action="/productos/{{p.id_producto}}/borrar" style="display:inline;margin-left:.4rem" onsubmit="return confirm('¿Eliminar este producto?')"><input type="hidden" name="volver" value="{{volver}}"><button class="rojo" style="padding:.2rem .5rem">Eliminar</button></form></td></tr>
{% else %}<tr><td colspan="4">Sin productos.</td></tr>{% endfor %}</table></div>""",
                  nav="productos", ps=ps, cats=cats, cat_sel=cat_sel, volver=request.full_path.rstrip("?"))

@app.route("/productos/<int:pid>/borrar", methods=["POST"])
@acceso("Admin")
def borrar_producto(pid):
    d = db()
    p = d.execute("SELECT id_producto FROM productos WHERE id_producto=?", (pid,)).fetchone()
    if p:
        try:
            d.execute("DELETE FROM productos WHERE id_producto=?", (pid,))
            d.commit()
            flash("Producto eliminado.", "ok")
        except sqlite3.IntegrityError:
            d.execute("UPDATE productos SET activo=0 WHERE id_producto=?", (pid,))
            d.commit()
            flash("El producto tiene ventas registradas; se desactivó en vez de eliminarse.", "err")
    destino = request.form.get("volver", "")
    return redirect(destino if destino.startswith("/") else url_for("productos"))

@app.route("/productos/<int:pid>", methods=["GET", "POST"])
@acceso("Admin")
def producto(pid):
    d = db()
    if request.method == "POST":
        f = request.form
        try:
            datos = (f["nombre"].strip(), float(f["precio"]), int(f["stock"]), int(f["stock_minimo"]),
                     int(f["id_categoria"]), f.get("imagen", "").strip() or imagen_url(f["nombre"].strip()))
            if pid:
                d.execute("UPDATE productos SET nombre=?,precio=?,stock=?,stock_minimo=?,id_categoria=?,imagen=? WHERE id_producto=?", datos + (pid,))
                if f.get("desactivar"):
                    d.execute("UPDATE productos SET activo=0 WHERE id_producto=?", (pid,))
            else:
                d.execute("INSERT INTO productos(nombre,precio,stock,stock_minimo,id_categoria,imagen) VALUES(?,?,?,?,?,?)", datos)
            d.commit()
            flash("Producto guardado.", "ok")
            return redirect(url_for("productos"))
        except (ValueError, sqlite3.IntegrityError):
            flash("Revisa los datos: precio y stock deben ser números no negativos.", "err")
    p = d.execute("SELECT * FROM productos WHERE id_producto=?", (pid,)).fetchone()
    cats = d.execute("SELECT * FROM categorias ORDER BY nombre").fetchall()
    return pagina("""<div class="card"><h1>{{'Editar' if p else 'Nuevo'}} producto</h1><form method="post" class="fila">
<label>Nombre<input name="nombre" required value="{{p.nombre if p}}"></label>
<label>Precio ($)<input name="precio" type="number" step="0.01" min="0" required value="{{p.precio if p}}"></label>
<label>Stock<input name="stock" type="number" min="0" required value="{{p.stock if p else 0}}"></label>
<label>Stock mínimo<input name="stock_minimo" type="number" min="0" required value="{{p.stock_minimo if p else 5}}"></label>
<label>Categoría<select name="id_categoria">{% for c in cats %}<option value="{{c.id_categoria}}" {{'selected' if p and p.id_categoria==c.id_categoria}}>{{c.nombre}}</option>{% endfor %}</select></label>
<label>Imagen (URL)<input name="imagen" placeholder="https://..." value="{{p.imagen if p}}"></label>
{% if p %}<label><input type="checkbox" name="desactivar" value="1" style="width:auto"> Desactivar</label>{% endif %}
<button>Guardar</button><a class="btn gris" href="/productos" style="text-align:center">Volver</a></form></div>""",
                  nav="productos", p=p, cats=cats)

@app.route("/gestion-categorias", methods=["GET", "POST"])
@acceso("Admin")
def gestionar_categorias():
    d = db()
    if request.method == "POST":
        accion = request.form.get("accion")
        nombre = request.form.get("nombre", "").strip()
        try:
            if accion == "crear" and nombre:
                d.execute("INSERT INTO categorias(nombre) VALUES(?)", (nombre,))
                flash(f"Categoría «{nombre}» creada.", "ok")
            elif accion == "renombrar" and nombre:
                d.execute("UPDATE categorias SET nombre=? WHERE id_categoria=?", (nombre, request.form["id_categoria"]))
                flash("Categoría actualizada.", "ok")
            elif accion == "borrar":
                cid = request.form["id_categoria"]
                if d.execute("SELECT 1 FROM productos WHERE id_categoria=?", (cid,)).fetchone():
                    flash("No se puede borrar: la categoría tiene productos.", "err")
                else:
                    d.execute("DELETE FROM categorias WHERE id_categoria=?", (cid,))
                    flash("Categoría borrada.", "ok")
            d.commit()
        except sqlite3.IntegrityError:
            flash("Ya existe una categoría con ese nombre.", "err")
        return redirect(url_for("gestionar_categorias"))
    cs = d.execute("""SELECT c.*, COUNT(p.id_producto) n FROM categorias c
                      LEFT JOIN productos p ON p.id_categoria=c.id_categoria GROUP BY c.id_categoria ORDER BY c.nombre""").fetchall()
    return pagina("""<div class="card"><h1>Categorías</h1>
<form method="post" class="fila"><input type="hidden" name="accion" value="crear">
<label>Nueva categoría<input name="nombre" required placeholder="Ej. Congelados"></label><button>Crear</button></form></div>
<div class="card"><table><tr><th>Categoría</th><th>Productos</th><th></th></tr>
{% for c in cs %}<tr><td>{{icono(c.nombre)}} {{c.nombre}}</td><td>{{c.n}}</td>
<td style="text-align:right"><form method="post" style="display:flex;gap:.3rem;justify-content:flex-end"><input type="hidden" name="accion" value="renombrar"><input type="hidden" name="id_categoria" value="{{c.id_categoria}}">
<input name="nombre" value="{{c.nombre}}" style="width:130px"><button>Guardar</button></form>
<form method="post" style="margin-top:.3rem"><input type="hidden" name="accion" value="borrar"><input type="hidden" name="id_categoria" value="{{c.id_categoria}}"><button class="rojo">Borrar</button></form></td></tr>
{% endfor %}</table></div>""", nav="categorias", cs=cs)

@app.route("/categorias/<int:cid>/renombrar", methods=["POST"])
@acceso("Admin")
def renombrar_categoria(cid):
    d = db()
    nombre = request.form.get("nombre", "").strip()
    if nombre:
        try:
            d.execute("UPDATE categorias SET nombre=? WHERE id_categoria=?", (nombre, cid))
            d.commit()
            flash(f"Categoría renombrada a «{nombre}».", "ok")
        except sqlite3.IntegrityError:
            flash("Ya existe una categoría con ese nombre.", "err")
    volver = request.form.get("volver", "/")
    return redirect(volver if volver.startswith("/") else "/")

@app.route("/usuarios", methods=["GET", "POST"])
@acceso("Admin")
def usuarios():
    d = db()
    if request.method == "POST":
        accion = request.form.get("accion")
        if accion == "crear":
            try:
                d.execute("INSERT INTO usuarios(nombre,usuario,clave_hash,id_rol) VALUES(?,?,?,?)",
                          (request.form["nombre"].strip(), request.form["usuario"].strip(),
                           generate_password_hash(request.form["clave"]), int(request.form["id_rol"])))
                d.commit()
                flash("Usuario creado.", "ok")
            except (sqlite3.IntegrityError, ValueError):
                flash("No se pudo crear: el usuario ya existe o los datos son inválidos.", "err")
        elif accion == "borrar":
            uid = int(request.form["id_usuario"])
            u = d.execute("SELECT u.*, r.nombre rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=?", (uid,)).fetchone()
            admins = d.execute("SELECT COUNT(*) n FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre='Admin' AND u.activo=1").fetchone()["n"]
            if uid == session["uid"]:
                flash("No puedes eliminar tu propia cuenta.", "err")
            elif u and u["rol"] == "Admin" and admins <= 1:
                flash("Debe quedar al menos un administrador activo.", "err")
            elif u:
                try:
                    d.execute("DELETE FROM usuarios WHERE id_usuario=?", (uid,))
                    d.commit()
                    flash("Usuario eliminado.", "ok")
                except sqlite3.IntegrityError:
                    d.execute("UPDATE usuarios SET activo=0 WHERE id_usuario=?", (uid,))
                    d.commit()
                    flash("Ese usuario tiene ventas registradas; se desactivó la cuenta.", "err")
        elif accion == "activar":
            d.execute("UPDATE usuarios SET activo=1 WHERE id_usuario=?", (int(request.form["id_usuario"]),))
            d.commit()
            flash("Usuario reactivado.", "ok")
        return redirect(url_for("usuarios"))
    rs = d.execute("SELECT * FROM roles ORDER BY id_rol").fetchall()
    us = d.execute("SELECT u.*, r.nombre rol FROM usuarios u JOIN roles r USING(id_rol) ORDER BY u.activo DESC, r.nombre, u.nombre").fetchall()
    return pagina("""<div class="card"><h1>Usuarios</h1>
<form method="post" class="fila"><input type="hidden" name="accion" value="crear">
<label>Nombre<input name="nombre" required></label>
<label>Usuario<input name="usuario" required></label>
<label>Contraseña<input name="clave" type="password" required></label>
<label>Rol<select name="id_rol">{% for r in rs %}<option value="{{r.id_rol}}">{{r.nombre}}</option>{% endfor %}</select></label>
<button>Agregar usuario</button></form></div>
<div class="card"><table><tr><th>Nombre</th><th>Usuario</th><th>Rol</th><th>Estado</th><th></th></tr>
{% for u in us %}<tr><td>{{u.nombre}}</td><td>{{u.usuario}}</td><td>{{u.rol}}</td>
<td>{{'Activo' if u.activo else 'Inactivo'}}</td>
<td style="text-align:right">
{% if not u.activo %}<form method="post" style="display:inline"><input type="hidden" name="accion" value="activar"><input type="hidden" name="id_usuario" value="{{u.id_usuario}}"><button>Reactivar</button></form>
{% elif u.id_usuario != session.uid %}<form method="post" style="display:inline" onsubmit="return confirm('¿Eliminar este usuario?')"><input type="hidden" name="accion" value="borrar"><input type="hidden" name="id_usuario" value="{{u.id_usuario}}"><button class="rojo">Eliminar</button></form>{% endif %}
</td></tr>{% endfor %}</table></div>""", nav="usuarios", rs=rs, us=us)

@app.route("/configuracion", methods=["GET", "POST"])
@acceso("Admin")
def configuracion():
    d = db()
    if request.method == "POST":
        if request.form.get("accion") == "reset":
            d.execute("DELETE FROM meta WHERE clave IN ('tema_bg','tema_header')")
            d.commit()
            flash("Colores restablecidos.", "ok")
            return redirect(url_for("configuracion"))
        cambios = []
        for campo, clave, nombre in (("tema_bg", "tema_bg", "fondo"),
                                     ("tema_header", "tema_header", "encabezado")):
            c = request.form.get(campo, "").strip()
            if re.fullmatch(r"#[0-9a-fA-F]{6}", c):
                d.execute("INSERT OR REPLACE INTO meta(clave,valor) VALUES(?,?)", (clave, c))
                cambios.append(nombre)
            else:
                flash(f"Color de {nombre} inválido.", "err")
        d.commit()
        if cambios:
            flash("Guardado: " + ", ".join(cambios) + ".", "ok")
        return redirect(url_for("configuracion"))
    return pagina("""<div class="card"><h1>🎨 Personalización</h1>
<p class="pstock">Elige los colores de la tienda. Se aplican a toda la aplicación.</p>
<form method="post" class="fila">
<label>Color de fondo
<input type="color" name="tema_bg" value="{{actual}}" oninput="verFondo(this.value)" style="height:46px;padding:.2rem;max-width:150px">
</label>
<div class="catbar">{% for c in colores_fondo %}<a href="#" title="{{c}}" onclick="verFondo('{{c}}');return false" style="background:{{c}};min-width:34px;height:34px;border-radius:50%;box-shadow:inset 0 0 0 1px #0003;padding:0"></a>{% endfor %}</div>
<label>Color del encabezado (barra superior)
<input type="color" name="tema_header" value="{{actual_h}}" oninput="verHead(this.value)" style="height:46px;padding:.2rem;max-width:150px">
</label>
<div class="catbar">{% for c in colores_head %}<a href="#" title="{{c}}" onclick="verHead('{{c}}');return false" style="background:{{c}};min-width:34px;height:34px;border-radius:50%;box-shadow:inset 0 0 0 1px #0003;padding:0"></a>{% endfor %}</div>
<button>Guardar cambios</button></form>
<form method="post" style="margin-top:.7rem"><input type="hidden" name="accion" value="reset"><button style="background:#c9d6cd;color:#22382b">Restablecer todo</button></form>
<p class="pstock" style="margin-top:.6rem">¿Buscas agregar o editar productos? Ve a <a href="/productos">📦 Gestionar productos</a>.</p></div>
<script>
function verFondo(v){document.documentElement.style.setProperty('--bg',v);document.documentElement.style.setProperty('--surface',v);var i=document.querySelector('[name=tema_bg]');if(i)i.value=v;}
function verHead(v){var n=parseInt(v.slice(1,3),16),g=parseInt(v.slice(3,5),16),b=parseInt(v.slice(5,7),16);var d='#'+[n,g,b].map(function(x){return ('0'+Math.round(x*0.8).toString(16)).slice(-2)}).join('');document.documentElement.style.setProperty('--header',v);document.documentElement.style.setProperty('--header2',d);var i=document.querySelector('[name=tema_header]');if(i)i.value=v;}
</script>""",
                  nav="colores", actual=(color_tema() or FONDO_DEF), actual_h=(color_header() or HEADER_DEF),
                  colores_fondo=COLORES_FONDO, colores_head=COLORES_HEADER)

@app.route("/clientes", methods=["GET", "POST"])
@acceso()
def clientes():
    d = db()
    if request.method == "POST" and request.form["nombre"].strip():
        d.execute("INSERT INTO clientes(nombre,telefono) VALUES(?,?)", (request.form["nombre"].strip(), request.form["telefono"].strip()))
        d.commit()
        flash("Cliente registrado.", "ok")
        return redirect(url_for("clientes"))
    cs = d.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    return pagina("""<div class="card"><h1>Clientes</h1><form method="post" class="fila">
<label>Nombre<input name="nombre" required></label><label>Teléfono<input name="telefono"></label><button>Registrar</button></form></div>
<div class="card"><table><tr><th>Nombre</th><th>Teléfono</th></tr>
{% for c in cs %}<tr><td>{{c.nombre}}</td><td>{{c.telefono or ''}}</td></tr>{% endfor %}</table></div>""",
                  nav="clientes", cs=cs)

iniciar_bd()

if __name__ == "__main__":
    app.run(debug=True)
