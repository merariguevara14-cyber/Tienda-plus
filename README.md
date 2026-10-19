# TiendaPlus

Mini-ERP con interfaz de **app de supermercado para teléfono y web** (tema verde, responsive): catálogo, carrito, clientes y dashboard, con roles de administrador (admin) y cajero.
Proyecto innovador · INDEL 3.° Desarrollo de Software "B" · 2026.

## Cómo correrlo

```bash
pip install -r requirements.txt
python app.py
```

Abre http://127.0.0.1:5000. La base de datos (`tiendaplus.db`, SQLite) se crea sola la primera vez.

## Usuarios de prueba

| Rol          | Usuario | Contraseña |
|--------------|---------|------------|
| Administrador| admin   | admin123   |
| Cajero       | cajero  | cajero123  |

Cambia estas contraseñas antes de usar el sistema con datos reales.

## Qué incluye

- Interfaz **responsive**: en teléfono usa barra de navegación inferior; en pantalla grande (web/escritorio) muestra un menú lateral y una cuadrícula más amplia.
- Tema verde, barra superior con **buscador** y carrito siempre visible (con contador).
- Catálogo tipo supermercado con **19 categorías y 1001 productos** (basado en una lista estilo Super Selectos): Frutas, Verduras y hortalizas, Granos y cereales, Pastas y sopas, Aceites/condimentos/salsas, Enlatados y conservas, Panadería y repostería, Lácteos y huevos, Carnes/aves/pescados, Bebidas, Snacks y dulces, Higiene personal y baño, Cuidado del bebé, Limpieza del hogar, Hogar y ferretería ligera, Papelería y escolar, Mascotas, Farmacia y salud básica, y Comida preparada y deli.
- Inicio con mosaico de categorías y productos recomendados en **tarjetas** con precio y botón Agregar.
- **Carrito** con sumar/quitar cantidades y cobro: al cobrar descuenta el inventario y rechaza ventas sin stock suficiente.
- Módulo **Cuenta**: reportes/dashboard, gestión de productos (agregar, editar y **eliminar** —ordenados por categoría—, con imagen por URL), gestión de categorías, **gestión de usuarios** (crear, eliminar y reactivar), **personalización de colores** (fondo y encabezado) y clientes (según el rol).

## Catálogo e imágenes

El catálogo se importa automáticamente desde `database/catalogo_super_selectos.csv` la primera vez que se crea la base de datos. Los precios son de ejemplo (variados por categoría); edítalos desde *Cuenta → Gestionar productos*.

Los productos **no incluyen fotos** de forma predeterminada; cada tarjeta muestra un icono según su categoría. Si quieres una foto, pega una URL en el campo **Imagen (URL)** de cada producto en *Cuenta → Gestionar productos*.

## Estructura

- `app.py`: aplicación completa (rutas, base de datos y pantallas).
- `database/catalogo_super_selectos.csv`: lista de productos y categorías que se importa al iniciar.
- `database/tiendaplus.sql` y `docs/`: diseño físico y lógico (versión SQL Server).
