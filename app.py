#ULTIMO 14-jun con pdf
import streamlit as st
import pandas as pd
import os
import secrets
import logging
from datetime import datetime
import dateutil.relativedelta
import re
import urllib.parse
import bcrypt

import psycopg2
import psycopg2.extras
import requests
from io import BytesIO
from contextlib import contextmanager

# ── PostgreSQL / Supabase ────────────────────────────────────────────────────
@st.cache_resource
def _get_pg_dsn():
    db = st.secrets.get("database", {})
    dsn = (db.get("supabase_url") or db.get("url") or db.get("connection_string")
           or st.secrets.get("DATABASE_URL"))
    if not dsn:
        raise RuntimeError("Falta [database] supabase_url en secrets.toml")
    # Auto-convertir URL directa de Supabase → Transaction Pooler
    m = re.match(r'postgresql://([^:]+):([^@]+)@db\.([a-z0-9]+)\.supabase\.co(?::\d+)?/(\S+)', dsn)
    if m:
        user, password, ref, db_ = m.groups()
        if '.' not in user:
            user = f'postgres.{ref}'
        dsn = f'postgresql://{user}:{password}@aws-1-sa-east-1.pooler.supabase.com:6543/{db_}'
    elif ':5432/' in dsn:
        dsn = dsn.replace(':5432/', ':6543/')
    return dsn

@contextmanager
def _pg_conn():
    conn = psycopg2.connect(_get_pg_dsn(),
                            cursor_factory=psycopg2.extras.RealDictCursor,
                            connect_timeout=10)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _get_empresa_id(archivo_db: str):
    if not archivo_db or archivo_db == 'central.db':
        return None
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM empresas WHERE archivo_db = %s", (archivo_db,))
                row = cur.fetchone()
                return row["id"] if row else None
    except Exception as e:
        logging.error(f"_get_empresa_id: {e}")
        return None


# ── ReportLab: generación real de PDF ──
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable


def _rl_seccion_titulo(texto, color_texto, color_fondo, ancho):
    """Título de sección con fondo de color para el PDF."""
    data = [[Paragraph(texto, ParagraphStyle(
        "sec", fontSize=10, fontName="Helvetica-Bold",
        textColor=color_texto, leading=14,
    ))]]
    tbl = Table(data, colWidths=[ancho])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), color_fondo),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    return tbl


def generar_pdf_recibo(
    comprobante_nro, fecha_emision, periodo,
    locatario, propiedad,
    alquiler_desc, alquiler_monto,
    filas_servicios,   # lista de {"Concepto": str, "Monto": float}
    total, metodo_pago, nombre_empresa,
    observaciones="",
    es_reimpresion=False, fecha_original="", id_registro="",
):
    """Genera el PDF del recibo y devuelve bytes listos para st.download_button."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=18*mm, leftMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
    )

    AZUL_OSC  = colors.HexColor("#1a365d")
    AZUL_MED  = colors.HexColor("#2c5282")
    AZUL_CLAR = colors.HexColor("#edf2f7")
    GRIS_BG   = colors.HexColor("#f0f4f8")
    GRIS_TEXT = colors.HexColor("#4a5568")
    AMARILLO  = colors.HexColor("#fff3cd")
    AMARILLO_B= colors.HexColor("#ffc107")
    BLANCO    = colors.white

    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    def _p(text, size=10, bold=False, color=colors.black, align=TA_LEFT):
        return Paragraph(text, ParagraphStyle(
            "c", parent=normal, fontSize=size, leading=size * 1.45,
            textColor=color, alignment=align,
            fontName="Helvetica-Bold" if bold else "Helvetica",
        ))

    story = []

    # Badge reimpresión
    if es_reimpresion:
        bd = [[_p(f"🖨  REIMPRESIÓN — Documento original registrado el {fecha_original}",
                   size=9, color=colors.HexColor("#856404"))]]
        bt = Table(bd, colWidths=[doc.width])
        bt.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,-1), AMARILLO),
            ("BOX",        (0,0),(-1,-1), 0.5, AMARILLO_B),
            ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("LEFTPADDING",(0,0),(-1,-1), 8),
        ]))
        story += [bt, Spacer(1, 6)]

    # Encabezado
    meta = [
        f"<b>Comprobante N°:</b> {comprobante_nro}",
        f"<b>Fecha Emisión:</b> {fecha_emision}",
        f"<b>Período:</b> {periodo}",
    ]
    if es_reimpresion and id_registro:
        meta.append(f"<b>ID Registro:</b> #{id_registro}")
    hd = [[
        _p("RECIBO DE ALQUILER", size=20, bold=True, color=AZUL_OSC),
        _p("<br/>".join(meta), size=9.5, color=colors.HexColor("#555555"), align=TA_RIGHT),
    ]]
    ht = Table(hd, colWidths=[doc.width*0.5, doc.width*0.5])
    ht.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1),"BOTTOM"),
        ("LINEBELOW",     (0,0),(-1,-1), 2, AZUL_OSC),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
    ]))
    story += [ht, Spacer(1, 14)]

    # Datos del contrato
    story.append(_rl_seccion_titulo("Datos del Contrato", AZUL_MED, GRIS_BG, doc.width))
    story.append(Spacer(1, 6))
    dt = Table([[
        _p("<b>Locatario:</b>"), _p(locatario),
        _p("<b>Propiedad:</b>"), _p(propiedad),
    ]], colWidths=[doc.width*0.15, doc.width*0.35, doc.width*0.15, doc.width*0.35])
    dt.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))
    story += [dt, Spacer(1, 14)]

    # Desglose de conceptos
    story.append(_rl_seccion_titulo("Desglose de Conceptos Liquidados", AZUL_MED, GRIS_BG, doc.width))
    story.append(Spacer(1, 6))
    rows = [
        [_p("Descripción del Concepto", bold=True, color=BLANCO),
         _p("Subtotal", bold=True, color=BLANCO, align=TA_RIGHT)],
        [_p(alquiler_desc), _p(f"$ {alquiler_monto:,.2f}", align=TA_RIGHT)],
    ]
    for f in filas_servicios:
        if float(f.get("Monto", 0)) > 0:
            rows.append([_p(f["Concepto"]), _p(f"$ {float(f['Monto']):,.2f}", align=TA_RIGHT)])
    rows.append([
        _p("TOTAL CONSOLIDADO PERCIBIDO", bold=True, color=AZUL_OSC),
        _p(f"$ {total:,.2f}", bold=True, color=AZUL_OSC, align=TA_RIGHT),
    ])
    n = len(rows)
    it = Table(rows, colWidths=[doc.width*0.72, doc.width*0.28])
    it.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), AZUL_MED),
        ("BACKGROUND",    (0,n-1),(-1,n-1), AZUL_CLAR),
        ("LINEBELOW",     (0,1),(-1,n-2), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",    (0,0),(-1,-1), 8), ("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("LEFTPADDING",   (0,0),(-1,-1), 8), ("RIGHTPADDING", (0,0),(-1,-1),8),
        ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
    ]))
    story += [it, Spacer(1, 14)]

    # Método de pago
    story.append(_p(f"<b>Forma de Cancelación:</b> {metodo_pago}"))
    if observaciones and str(observaciones).strip():
        story += [Spacer(1,4), _p(f"<b>Observaciones:</b> {observaciones}")]

    # Firma
    story.append(Spacer(1, 30))
    ft = Table([["", _p(f"_________________________<br/><b>{nombre_empresa}</b>",
                         size=11, color=GRIS_TEXT, align=TA_CENTER)]],
               colWidths=[doc.width*0.55, doc.width*0.45])
    story.append(ft)

    # Pie
    story += [Spacer(1,20),
              HRFlowable(width=doc.width, thickness=0.5, color=colors.HexColor("#e2e8f0")),
              Spacer(1,6)]
    pie = ("Comprobante emitido de manera electrónica. Reimpresión autorizada — "
           f"Datos extraídos del registro original N° {id_registro}."
           if es_reimpresion and id_registro
           else "Comprobante emitido de manera electrónica. Documento de respaldo archivado de manera conforme.")
    story.append(_p(pie, size=9, color=colors.HexColor("#718096"), align=TA_CENTER))

    doc.build(story)
    return buffer.getvalue()




def _safe_float(val, default=0.0):
    """Convierte a float de forma segura — maneja None, NaN, strings vacíos."""
    if val is None:
        return default
    try:
        import math
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default

def _safe_int(val, default=0):
    """Convierte a int de forma segura."""
    try:
        return int(_safe_float(val, default))
    except (ValueError, TypeError):
        return default

# Configuración de logging (reemplaza los print() de depuración)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 🚀 AGREGAR AQUÍ (Única llamada en todo el script)
st.set_page_config(page_title="Gestión de Alquileres Pro", layout="wide")

# 2. Inyección de CSS para ocultar elementos
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# 1. Definimos qué columnas esperamos para cada tabla (puedes ampliarlo)
ESQUEMAS_VALIDOS = {
    "propiedades": ['alias_propiedad', 'calle', 'numero', 'departamento', 'propietario', 'ciudad', 'provincia', 'tipo', 'nis', 'cuenta_gas', 'finca', 'cuenta_ooss', 'nro_padron'],
    "inquilinos": ['apellidos', 'nombres', 'dni', 'telefono', 'email'],
    "contratos": [
        'alias_propiedad', 'dni_inquilino', 'estado', 'inicio_contrato', 'fin_contrato',
        'calc_duracion', 'act_contrato', 'indice', 'monto_inicial', 'alquiler',
        'prox_actualizacion', 'mes_contrato', 'mes_actualizacion_contrato', 'servicios',
        'honorarios', 'monto_honorarios', 'cuota_honorarios', 'honorarios_pagados',
        'tipo_de_garantie', 'monto_garantia', 'garantia', 'garantia_pagada',
        'imp_inmobiliario', 'expensas', 'edesal', 'gas', 'municipalidad',
        'ooss', 'servicios_total', 'cochera', 'alquiler_cobrado', 'total_pagado'
    ]
}

def crear_db_central():
    """En PostgreSQL las tablas ya existen en Supabase. No-op."""
    logging.info("PostgreSQL: tablas centrales gestionadas por Supabase.")

def limpiar_nombre_archivo(nombre_comercial):
    """Convierte 'Inmobiliaria Alvear S.A.' en 'Inmobiliaria_Alvear_SA.db'"""
    # Reemplazar espacios por guiones bajos
    nombre = nombre_comercial.replace(" ", "_")
    # Remover cualquier caracter que no sea letra, número o guion bajo
    nombre_limpio = re.sub(r'[^a-zA-Z0-9_]', '', nombre)
    return f"{nombre_limpio}.db"





# =====================================================================
# 1. BASE DE DATOS: CONFIGURACIÓN MULTI-TENANT Y ENRUTAMIENTO
# =====================================================================

def conectar_db_central():
    """Conexión PostgreSQL con RealDictCursor."""
    try:
        return psycopg2.connect(_get_pg_dsn(),
                                cursor_factory=psycopg2.extras.RealDictCursor,
                                connect_timeout=10)
    except psycopg2.OperationalError as e:
        raise RuntimeError(f"Error conectando a PostgreSQL: {e}")

def conectar_db():
    """Conexión PostgreSQL. Compatible con pd.read_sql_query y context manager."""
    try:
        return psycopg2.connect(_get_pg_dsn(),
                                cursor_factory=psycopg2.extras.RealDictCursor,
                                connect_timeout=10)
    except psycopg2.OperationalError as e:
        raise RuntimeError(f"Error conectando a PostgreSQL: {e}")

def inicializar_nueva_empresa(ruta_db):
    """En PostgreSQL no hay archivos físicos. No-op."""
    logging.info(f"PostgreSQL: empresa {ruta_db} — sin inicialización local.")

def crear_tablas_empresa(conn):
    """En PostgreSQL las tablas ya existen en Supabase. No-op."""
    logging.info("PostgreSQL: crear_tablas_empresa omitida.")


def obtener_todas_las_empresas():
    try:
        with conectar_db_central() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT nombre_empresa, archivo_db FROM usuarios_central")
                return cur.fetchall()
    except Exception:
        return []

def obtener_permisos_desde_db(username, ruta_db):
    try:
        eid = _get_empresa_id(ruta_db)
        if not eid:
            return []
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pestana FROM permisos_usuario WHERE username = %s",
                    (username,)
                )
                return [r["pestana"] for r in cur.fetchall()]
    except Exception:
        return []

def inicializar_tablas():
    """En PostgreSQL las migraciones las gestiona Supabase. No-op."""
    logging.info("PostgreSQL: inicializar_tablas omitida.")

# 🏢 EJECUTAR INICIALIZACIÓN AUTOMÁTICA (Creará central.db de manera segura sin romper)
inicializar_tablas()

# =====================================================================
# FUNCIONES AUXILIARES FALTANTES (PARA LA PESTAÑA DE CARGA)
# =====================================================================

def obtener_nombre_por_id(inquilino_id):
    """Obtiene el nombre completo de un inquilino por su ID"""
    if not inquilino_id:
        return None
    try:
        with conectar_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT apellidos, nombres FROM inquilinos WHERE id = %s", (inquilino_id,))
            resultado = cursor.fetchone()
        if resultado:
            return f"{resultado['apellidos']}, {resultado['nombres']}"
        return None
    except Exception:
        return None


def obtener_ultimo_contrato():
    """Obtiene el último contrato creado/modificado"""
    try:
        with conectar_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contratos ORDER BY codigo DESC LIMIT 1")
            resultado = cursor.fetchone()
            if resultado:
                return dict(resultado)
        return None
    except Exception:
        return None


def cargar_datos_iniciales_contrato(propiedad_id):
    """Carga los datos del último contrato de una propiedad"""
    try:
        with conectar_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM contratos 
                WHERE alias_propiedad = (SELECT alias_propiedad FROM propiedades WHERE id = %s AND empresa_id = %s)
                  AND empresa_id = %s
                ORDER BY codigo DESC LIMIT 1
            ''', (propiedad_id, st.session_state.get('empresa_id', 0), st.session_state.get('empresa_id', 0)))
            resultado = cursor.fetchone()
            if resultado:
                return dict(resultado)
        return None
    except Exception:
        return None


def buscar_inquilino_por_id(inquilino_id, lista_inquilinos, dict_inquilinos):
    """Encuentra el índice de un inquilino en la lista por su ID"""
    for idx, nombre in enumerate(lista_inquilinos):
        if dict_inquilinos.get(nombre) == inquilino_id:
            return idx
    return 0


def crear_formulario_editar_inquilino(id_inq_edit, datos_inq):
    """Crea un formulario de edición de inquilino"""
    with st.form(f"form_editar_inquilino_{id_inq_edit}"):
        st.markdown(f"**Editando ID Interno: {id_inq_edit}**")
        
        edit_apellido = st.text_input("Apellidos:", value=datos_inq["apellidos"] or "")
        edit_nombre = st.text_input("Nombres:", value=datos_inq["nombres"] or "")
        edit_dni = st.text_input("DNI / CUIT:", value=datos_inq["dni"] or "")
        edit_tel = st.text_input("Teléfono:", value=datos_inq["telefono"] or "")
        edit_email = st.text_input("Email:", value=datos_inq["email"] or "")
        
        if st.form_submit_button("💾 Guardar Cambios Inquilino", type="primary"):
            if not edit_apellido or not edit_nombre:
                st.error("Apellidos y Nombres son obligatorios.")
            else:
                conn = conectar_db()
                cursor = conn.cursor()
                try:
                    cursor.execute('''
                        UPDATE inquilinos 
                        SET apellidos = %s, nombres = %s, dni = %s, telefono = %s, email = %s
                        WHERE id = %s
                    ''', (edit_apellido, edit_nombre, edit_dni, edit_tel, edit_email, id_inq_edit))
                    
                    conn.commit()
                    st.success(f"✅ Inquilino actualizado correctamente!")
                    st.rerun()
                except psycopg2.errors.UniqueViolation as e:
                    st.error(f"Error de integridad de datos: {e}")
                except Exception as e:
                    st.error(f"Error al actualizar inquilino: {e}")
                finally:
                    conn.close()


def crear_formulario_editar_propiedad(id_prop_edit, datos_prop):
    """Crea un formulario de edición de propiedad"""
    with st.form(f"form_editar_propiedad_{id_prop_edit}"):
        st.markdown(f"**Editando ID Interno: {id_prop_edit}**")
        
        edit_alias = st.text_input("Alias de la Propiedad:", value=datos_prop["alias_propiedad"] or "")
        edit_calle = st.text_input("Calle / Av:", value=datos_prop["calle"] or "")
        edit_numero = st.text_input("Número:", value=datos_prop["numero"] or "")
        edit_depto = st.text_input("Departamento / Piso / Bloque (Opcional):", value=datos_prop["departamento"] or "")
        
        if st.form_submit_button("💾 Guardar Cambios Propiedad", type="primary"):
            if not edit_alias or not edit_calle or not edit_numero:
                st.error("Alias, Calle y Número son obligatorios.")
            else:
                conn = conectar_db()
                cursor = conn.cursor()
                try:
                    cursor.execute('''
                        UPDATE propiedades 
                        SET alias_propiedad = %s, calle = %s, numero = %s, departamento = %s
                        WHERE id = %s
                    ''', (edit_alias, edit_calle, edit_numero, edit_depto, id_prop_edit))
                    
                    conn.commit()
                    st.success(f"✅ Propiedad actualizada correctamente!")
                    st.rerun()
                except psycopg2.errors.UniqueViolation as e:
                    st.error(f"Error de integridad de datos: {e}")
                except Exception as e:
                    st.error(f"Error al actualizar propiedad: {e}")
                finally:
                    conn.close()

# =====================================================================
# 2. LÓGICA DE AUTENTICACIÓN (BCRYPT UNIFICADO)
# =====================================================================

def verificar_usuario(username, password):
    username_clean = username.strip()
    # Control 1: Superadmin en secrets.toml
    try:
        if username_clean == st.secrets["superadmin"]["username"]:
            stored_hash = st.secrets["superadmin"]["password_hash"].encode("utf-8")
            if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
                return {"nombre_empresa": "Panel de Control Global",
                        "archivo_db": "central.db", "rol": "superadmin"}
            return None
    except Exception:
        pass
    # Control 2: usuarios en PostgreSQL
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT password_hash, nombre_empresa, archivo_db, rol, propietario_filtro "
                    "FROM usuarios_central WHERE username = %s",
                    (username_clean,)
                )
                row = cur.fetchone()
        if row and bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
            return {
                "nombre_empresa":    row["nombre_empresa"],
                "archivo_db":        row["archivo_db"],
                "rol":               row["rol"],
                "propietario_filtro": row["propietario_filtro"] or ""
            }
    except Exception as e:
        logging.error(f"verificar_usuario: {e}")
    return None

# =====================================================================
# INITIALIZACIÓN DE SESIÓN E INTERFAZ DE LOGIN (CON SUPERADMIN MAESTRO)
# =====================================================================

# Homologamos las variables de sesión para que todo el script use las mismas
# Homologamos las variables de sesión para que todo el script use las mismas
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "nombre_empresa" not in st.session_state:
    st.session_state.nombre_empresa = ""
if "empresa_db" not in st.session_state:
    st.session_state.empresa_db = None
if "empresa_id" not in st.session_state:
    st.session_state.empresa_id = 0
if "rol" not in st.session_state:
    st.session_state.rol = "user"
if "propiedad_activa" not in st.session_state:
    st.session_state.propiedad_activa = None
if "datos_contrato" not in st.session_state:
    st.session_state.datos_contrato = None
if "permisos_usuario" not in st.session_state:
    st.session_state.permisos_usuario = []

# Forzar compatibilidad con los nombres viejos que usas en el resto del script
st.session_state.usuario_actual = st.session_state.username
st.session_state.empresa_actual_nombre = st.session_state.nombre_empresa
st.session_state.usuario_rol = st.session_state.rol

# Interfaz de Login si el usuario no está autenticado
if not st.session_state.autenticado:
    st.markdown("<br><br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("🔑 Control de Acceso ")
        
        user_input = st.text_input("Usuario:")
        pass_input = st.text_input("Contraseña:", type="password")
        
        # El botón DEBE estar dentro del contenedor para no generar conflictos de flujo
        if st.button("Ingresar", type="primary", use_container_width=True):
            if user_input and pass_input:
                
                # Todo se unifica aquí de manera segura usando Bcrypt
                datos_sesion = verificar_usuario(user_input, pass_input)
                
                if datos_sesion:
                    st.session_state.autenticado = True
                    st.session_state.username = user_input.strip()
                    st.session_state.rol = datos_sesion["rol"]
                    st.session_state.nombre_empresa = datos_sesion["nombre_empresa"]
                    st.session_state.empresa_db = datos_sesion["archivo_db"]

                    # Obtener empresa_id desde PostgreSQL
                    try:
                        _eid = _get_empresa_id(datos_sesion["archivo_db"])
                        if not _eid and datos_sesion["rol"] != "superadmin":
                            # Buscar por nombre de empresa como fallback
                            with _pg_conn() as _fc:
                                with _fc.cursor() as _cur:
                                    _cur.execute(
                                        "SELECT id FROM empresas WHERE nombre_comercial = %s",
                                        (datos_sesion["nombre_empresa"],)
                                    )
                                    _row = _cur.fetchone()
                                    _eid = _row["id"] if _row else None
                        st.session_state.empresa_id = _eid if _eid else 0
                    except RuntimeError as _e:
                        st.error(f"❌ Error de conexión a la BD: {_e}")
                        st.stop()
                    
                    # Sincronización de variables de UI
                    st.session_state.usuario_actual = user_input.strip()
                    st.session_state.empresa_actual_nombre = datos_sesion["nombre_empresa"]
                    st.session_state.usuario_rol = datos_sesion["rol"]
                    
                    st.session_state.permisos_usuario = obtener_permisos_desde_db(
                        user_input.strip(), 
                        datos_sesion["archivo_db"]
                    )
                    st.session_state.propietario_filtro = datos_sesion.get("propietario_filtro", "")

                    st.success(f"¡Bienvenido {user_input}!")
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")
            else:
                st.warning("⚠️ Por favor complete todos los campos")
        
        st.caption("Solicite su acceso a 'contacto@controlz.net.ar'.")
    st.stop() # Frena por completo el renderizado del dashboard si no pasas el login



# =====================================================================
# FUNCIONES AUXILIARES DE LÓGICA Y PARSEO
# =====================================================================
def obtener_datos_desplegables():
    try:
        _eid = st.session_state.get("empresa_id", 0)
        with _pg_conn() as _conn_desp:
            with _conn_desp.cursor() as _cur_desp:
                _cur_desp.execute(
                    "SELECT id, alias_propiedad, calle, numero, departamento, propietario, ciudad, provincia, tipo "
                    "FROM propiedades WHERE empresa_id = %s", (_eid,)
                )
                propiedades = pd.DataFrame([dict(r) for r in _cur_desp.fetchall()])
                _cur_desp.execute(
                    "SELECT id, apellidos, nombres FROM inquilinos WHERE empresa_id = %s", (_eid,)
                )
                inquilinos = pd.DataFrame([dict(r) for r in _cur_desp.fetchall()])
    except Exception as e:
        logging.error(f"Error al obtener datos desplegables: {e}")
        return {}, {}
    
    dict_propiedades = {}
    for _, row in propiedades.iterrows():
        dir_completa = f"{row['calle']} {row['numero']}"
        if isinstance(row['departamento'], str) and row['departamento'].strip():
            dir_completa += f", Depto: {row['departamento']}"
        dict_propiedades[f"{row['alias_propiedad']} ({dir_completa})"] = row['id']
        
    dict_inquilinos = {f"{row['apellidos']}, {row['nombres']}": row['id'] for _, row in inquilinos.iterrows()}
    return dict_propiedades, dict_inquilinos

# =====================================================================
# FUNCIONES DE CÁLCULO AUTOMÁTICO DE ÍNDICES (ICL e IPC)
# =====================================================================

@st.cache_data(ttl=3600)
def _obtener_icl_bcra_xls(año: int) -> dict:
    """
    Descarga el XLS del ICL publicado por el BCRA para el año dado.
    Columna 7 = fecha (formato 20260101), columna 8 = valor ICL.
    Los datos reales arrancan en la fila 26 (las anteriores son encabezados).
    Retorna dict {"YYYY-MM-DD": valor_float}.
    Cache de 1 hora.
    """
    url = f"https://www.bcra.gob.ar/pdfs/PublicacionesEstadisticas/icl{año}.xls"
    try:
        resp = requests.get(url, timeout=15, verify=False)
        resp.raise_for_status()
        df_raw = pd.read_excel(BytesIO(resp.content), header=None)
        resultado = {}
        for _, row in df_raw.iterrows():
            try:
                fecha_raw = str(row.iloc[7]).strip()
                valor_raw = row.iloc[8]
                # La celda de fecha tiene formato YYYYMMDD (ej: 20260101)
                if len(fecha_raw) != 8 or not fecha_raw.isdigit():
                    continue
                fecha = pd.to_datetime(fecha_raw, format="%Y%m%d")
                valor = float(valor_raw)
                resultado[fecha.strftime("%Y-%m-%d")] = valor
            except Exception:
                continue
        if resultado:
            logging.info(f"[ICL] BCRA: {len(resultado)} registros obtenidos para {año}.")
            return resultado
        raise ValueError("El XLS del BCRA no contenía datos válidos.")
    except Exception as e:
        logging.warning(f"[ICL] Fuente primaria BCRA falló para {año}: {e}")

    # ── Fallback: API pública de IndecData / datos.gob.ar para ICL ──
    try:
        url_fb = (
            "https://apis.datos.gob.ar/series/api/series/"
            "?ids=174.1_ICL_0_0_32"
            "&limit=5000&format=json"
        )
        resp_fb = requests.get(url_fb, timeout=15)
        resp_fb.raise_for_status()
        data_fb = resp_fb.json()
        puntos_fb = [(p[0], p[1]) for p in data_fb.get("data", []) if p[1] is not None]
        if puntos_fb:
            resultado_fb = {f: float(v) for f, v in puntos_fb}
            logging.info(f"[ICL] Fallback datos.gob.ar: {len(resultado_fb)} registros.")
            return resultado_fb
    except Exception as e2:
        logging.warning(f"[ICL] Fallback datos.gob.ar también falló: {e2}")

    return {}


@st.cache_data(ttl=3600)
def _obtener_ipc_indec() -> dict:
    """
    Descarga el IPC Nivel General mensual desde la API pública de datos.gob.ar (INDEC).
    La serie 145.3_INGNACUAL_DICI_M_38 devuelve variaciones mensuales (ej: 0.0158 = 1.58%).
    Las acumulamos en un índice base=1 desde el primer dato disponible.
    Retorna dict {"YYYY-MM-DD": indice_acumulado_float}.
    """
    url = (
        "https://apis.datos.gob.ar/series/api/series/"
        "?ids=145.3_INGNACUAL_DICI_M_38"
        "&limit=1000&format=json"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        puntos = [(p[0], p[1]) for p in data.get("data", []) if p[1] is not None]
        if not puntos:
            raise ValueError("La API del INDEC no devolvió datos.")
        # Acumular: indice[0] = 1, indice[n] = indice[n-1] * (1 + variacion[n])
        resultado = {}
        indice_acum = 1.0
        for fecha_str, variacion in puntos:
            indice_acum *= (1.0 + float(variacion))
            resultado[fecha_str] = indice_acum
        logging.info(f"[IPC] INDEC: {len(resultado)} períodos obtenidos.")
        return resultado
    except Exception as e:
        logging.warning(f"[IPC] Fuente primaria datos.gob.ar falló: {e}")

    # ── Fallback: serie alternativa de IPC en datos.gob.ar ──
    try:
        url_fb2 = (
            "https://apis.datos.gob.ar/series/api/series/"
            "?ids=145.3_INGNACUAL_DICI_M_38,103.1_I2N_2016_M_19"
            "&limit=1000&format=json"
        )
        resp_fb2 = requests.get(url_fb2, timeout=15)
        resp_fb2.raise_for_status()
        data_fb2 = resp_fb2.json()
        puntos_fb2 = [(p[0], p[1]) for p in data_fb2.get("data", []) if p[1] is not None]
        if puntos_fb2:
            resultado_fb2 = {}
            indice_acum2 = 1.0
            for fecha_str, variacion in puntos_fb2:
                indice_acum2 *= (1.0 + float(variacion))
                resultado_fb2[fecha_str] = indice_acum2
            logging.info(f"[IPC] Fallback serie alternativa: {len(resultado_fb2)} períodos.")
            return resultado_fb2
    except Exception as e2:
        logging.warning(f"[IPC] Fallback alternativo también falló: {e2}")

    return {}


def _buscar_valor_mas_cercano(fecha_target: datetime, data: dict, dias_max: int = 45) -> float | None:
    """
    Busca en `data` (dict YYYY-MM-DD → float) el valor más cercano a `fecha_target`,
    retrocediendo hasta `dias_max` días. Útil para ICL (diario) e IPC (mensual).
    """
    for delta in range(0, dias_max + 1):
        clave = (fecha_target - dateutil.relativedelta.relativedelta(days=delta)).strftime("%Y-%m-%d")
        if clave in data:
            return data[clave]
    return None


def calcular_valor_actualizado_icl(
    monto_inicial: float,
    fecha_inicio: datetime,
    meses_intervalo: int
) -> float | None:
    """
    Calcula el nuevo valor de alquiler con ICL del BCRA.
    Fórmula: valor_nuevo = monto_inicial × (ICL_fecha_actualiz / ICL_fecha_inicio)
    """
    try:
        fecha_actualizacion = fecha_inicio + dateutil.relativedelta.relativedelta(months=meses_intervalo)
        años = {fecha_inicio.year, fecha_actualizacion.year}
        icl_data: dict = {}
        for año in años:
            icl_data.update(_obtener_icl_bcra_xls(año))

        if not icl_data:
            return None

        icl_inicio  = _buscar_valor_mas_cercano(fecha_inicio, icl_data, dias_max=10)
        icl_actual  = _buscar_valor_mas_cercano(fecha_actualizacion, icl_data, dias_max=10)

        if icl_inicio and icl_actual and icl_inicio > 0:
            return float(round(monto_inicial * (icl_actual / icl_inicio)))
        return None
    except Exception as e:
        logging.warning(f"[ICL] Error calculando: {e}")
        return None


def calcular_valor_actualizado_ipc(
    monto_inicial: float,
    fecha_inicio: datetime,
    meses_intervalo: int
) -> float | None:
    """
    Calcula el nuevo valor de alquiler con IPC del INDEC (datos.gob.ar).
    El IPC es mensual: usa el índice del mes de inicio y del mes de actualización.
    Fórmula: valor_nuevo = monto_inicial × (IPC_mes_actualiz / IPC_mes_inicio)
    """
    try:
        fecha_actualizacion = fecha_inicio + dateutil.relativedelta.relativedelta(months=meses_intervalo)
        ipc_data = _obtener_ipc_indec()

        if not ipc_data:
            return None

        # El IPC en la API viene con fecha al primer día del mes ("YYYY-MM-01")
        ipc_inicio  = _buscar_valor_mas_cercano(fecha_inicio, ipc_data, dias_max=45)
        ipc_actual  = _buscar_valor_mas_cercano(fecha_actualizacion, ipc_data, dias_max=45)

        if ipc_inicio and ipc_actual and ipc_inicio > 0:
            return float(round(monto_inicial * (ipc_actual / ipc_inicio)))
        return None
    except Exception as e:
        logging.warning(f"[IPC] Error calculando: {e}")
        return None


def limpiar_string_a_float(texto_num):
    if not texto_num:
        return 0.0
    s = str(texto_num).replace("$", "").strip()
    if not s:
        return 0.0
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s and "," not in s:
        partes = s.split(".")
        if len(partes[-1]) == 3:
            s = s.replace(".", "")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def verificar_contrato_existente(propiedad_id):
    """Verifica si ya existe un contrato activo para una propiedad dada.
    Retorna (codigo, estado) del contrato más reciente, o None si no existe."""
    try:
        with conectar_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT codigo, estado FROM contratos WHERE alias_propiedad = (SELECT alias_propiedad FROM propiedades WHERE id = %s AND empresa_id = %s) AND empresa_id = %s ORDER BY codigo DESC LIMIT 1",
                (propiedad_id, st.session_state.get("empresa_id", 0), st.session_state.get("empresa_id", 0))
            )
            return cursor.fetchone()
    except Exception as e:
        logging.warning(f"Error al verificar contrato existente para propiedad {propiedad_id}: {e}")
        return None




# ── Test de conexión temprano ──────────────────────────────────────────────
try:
    _tc = conectar_db()
    _tc.close()
except RuntimeError as _ce:
    st.error(f"❌ No se pudo conectar a PostgreSQL:\n\n`{_ce}`")
    st.info(
        "Verificá en **Streamlit Cloud → Settings → Secrets**:\n\n"
        "```toml\n[database]\nsupabase_url = \"postgresql://postgres.PROJECT:PASS"
        "@aws-1-sa-east-1.pooler.supabase.com:6543/postgres\"\n```"
    )
    st.stop()

# Barra superior con información del operador, Empresa activa automática y botón de Salida
top_col1, top_col2 = st.columns([7, 3])
with top_col1:
    st.title("🏢 Gestión de Propiedades")
with top_col2:
    st.markdown(
        f"<p style='text-align: right; margin-bottom: 5px;'>"
        f"🏢 Empresa: <b>{st.session_state.empresa_actual_nombre.upper()}</b><br>"
        f"👤 Operador: <b>{st.session_state.usuario_actual.upper()}</b>"
        f"</p>", 
        unsafe_allow_html=True
    )
    if st.button("🔒 Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.usuario_actual = ""
        st.session_state.empresa_actual_nombre = ""
        st.session_state.empresa_db = None
        st.rerun()


# =====================================================================
# CONFIGURACIÓN DINÁMICA DE PESTAÑAS SEGÚN PERMISOS Y ROL
# =====================================================================

# 1. Definición del rol actual
rol_actual = st.session_state.get("usuario_rol", "user")

# 2. Definición maestra de pestañas
pestanas_maestras = {
    "📈 Tablero de Control": "dashboard",
    "📊 Planilla de Contratos": "planilla", 
    "💰 Registrar / Emitir Recibo": "pagos",
    "🗄️ Historial de Caja": "historial_pagos",
    "📝 Carga de Contratos": "carga", 
    "⚙️ Cargar Inquilinos / Propiedades": "auxiliares",
    "🔧 Gastos de Propiedades": "gastos"
}

# --- AQUÍ VA EL BLOQUE QUE ME PREGUNTAS ---
# Es el encargado de filtrar qué elementos de 'pestanas_maestras' 
# son visibles para el usuario según su rol o permisos guardados en sesión.
if rol_actual == "superadmin":
    # Superadmin: acceso total a todas las pestañas sin restricción
    pestanas_visibles_nombres = list(pestanas_maestras.keys()) + ["⚙️ Panel de Gestión"]
    pestanas_visibles_claves = list(pestanas_maestras.values()) + ["panel_gestion"]
elif rol_actual == "admin":
    # Admin: recarga permisos desde BD en cada render (evita que queden desactualizados en sesión)
    _username_admin = st.session_state.get("username", "")
    _db_admin = st.session_state.get("empresa_db", "")
    if _username_admin and _db_admin:
        permisos_usuario = obtener_permisos_desde_db(_username_admin, _db_admin)
        st.session_state.permisos_usuario = permisos_usuario
    else:
        permisos_usuario = st.session_state.get("permisos_usuario", [])
    pestanas_visibles_nombres = []
    pestanas_visibles_claves = []
    for nombre, clave in pestanas_maestras.items():
        if clave in permisos_usuario:
            pestanas_visibles_nombres.append(nombre)
            pestanas_visibles_claves.append(clave)
    # Panel de Gestión siempre visible para admin
    pestanas_visibles_nombres.append("⚙️ Panel de Gestión")
    pestanas_visibles_claves.append("panel_gestion")
elif rol_actual == "propietario":
    # Propietario: acceso de solo lectura a Dashboard, Planilla e Historial de Caja
    _pestanas_propietario = ["dashboard", "planilla", "historial_pagos", "gastos"]
    pestanas_visibles_nombres = [n for n, c in pestanas_maestras.items() if c in _pestanas_propietario]
    pestanas_visibles_claves = [c for c in pestanas_maestras.values() if c in _pestanas_propietario]
else:
    # Lee de la sesión (donde los guardamos en el login)
    permisos_usuario = st.session_state.get("permisos_usuario", [])
    
    # Inicializamos las listas de visualización
    pestanas_visibles_nombres = []
    pestanas_visibles_claves = []
    
    for nombre, clave in pestanas_maestras.items():
        if clave in permisos_usuario:
            pestanas_visibles_nombres.append(nombre)
            pestanas_visibles_claves.append(clave)


# =====================================================================
# RENDERIZADO EFECTIVO DE LAS PESTAÑAS EN STREAMLIT (CORREGIDO)
# =====================================================================

# Dibujamos en la interfaz las pestañas calculadas UNA SOLA VEZ
tabs_creados = st.tabs(pestanas_visibles_nombres)

# Inicializamos de forma segura todas las variables de control en None
tab_dashboard = None
tab_planilla = None
tab_pagos = None
tab_historial_pagos = None
tab_carga = None
tab_auxiliares = None
tab_gastos = None
tab_superadmin = None

# Asignación limpia y controlada basada en las claves activas
if "dashboard" in pestanas_visibles_claves:
    tab_dashboard = tabs_creados[pestanas_visibles_claves.index("dashboard")]

if "planilla" in pestanas_visibles_claves:
    tab_planilla = tabs_creados[pestanas_visibles_claves.index("planilla")]

if "pagos" in pestanas_visibles_claves:
    tab_pagos = tabs_creados[pestanas_visibles_claves.index("pagos")]

if "historial_pagos" in pestanas_visibles_claves:
    tab_historial_pagos = tabs_creados[pestanas_visibles_claves.index("historial_pagos")]

if "carga" in pestanas_visibles_claves:
    tab_carga = tabs_creados[pestanas_visibles_claves.index("carga")]

if "auxiliares" in pestanas_visibles_claves:
    tab_auxiliares = tabs_creados[pestanas_visibles_claves.index("auxiliares")]

if "gastos" in pestanas_visibles_claves:
    tab_gastos = tabs_creados[pestanas_visibles_claves.index("gastos")]

# AQUÍ: tab_superadmin se activa perfectamente tanto para 'superadmin' como para 'admin'
if "panel_gestion" in pestanas_visibles_claves:
    tab_superadmin = tabs_creados[pestanas_visibles_claves.index("panel_gestion")]

# =====================================================================
# MEJORA 2: TABLERO DE CONTROL (DASHBOARD INTERACTIVO Y ALERTAS)
# =====================================================================
if tab_dashboard:
    with tab_dashboard:
        st.subheader("⚡ Alertas Estratégicas y Métricas Generales")
        _pf = st.session_state.get("propietario_filtro", "")
        _pf_activo = rol_actual == "propietario" and bool(_pf)
        _eid_dash = st.session_state.get("empresa_id", 0)
        _where_pf = "AND p.propietario = %s" if _pf_activo else ""
        _params_pf = (_eid_dash, _pf) if _pf_activo else (_eid_dash,)

        query_dash = f'''
            SELECT c.codigo, p.alias_propiedad, (i.apellidos || ', ' || i.nombres) as inquilino,
                c.estado, c.fin_contrato, c.prox_actualizacion, c.alquiler, c.mes_contrato, c.act_contrato
            FROM contratos c
            JOIN propiedades p ON c.alias_propiedad = p.alias_propiedad
            JOIN inquilinos i ON c.dni_inquilino = i.dni
            WHERE c.empresa_id = %s AND c.estado = 'Activo' {_where_pf}
        '''

        conn = conectar_db()
        with _pg_conn() as _conn_d:
            with _conn_d.cursor() as _cur_d:
                _cur_d.execute(query_dash, _params_pf)
                _rows_d = _cur_d.fetchall()
                _cols_d = [x.name for x in _cur_d.description]
        df_dash = pd.DataFrame([dict(r) for r in _rows_d], columns=_cols_d) if _rows_d else pd.DataFrame(columns=_cols_d)
        # Suma de cobros: usar monto_abonado (nombre real en schema migrado)
        _pagos_q = f"SELECT COALESCE(ph.monto_abonado, 0) AS monto_total FROM pagos_historial ph WHERE ph.empresa_id = %s {'AND ph.propiedad IN (SELECT alias_propiedad FROM propiedades WHERE propietario = %s AND empresa_id = %s)' if _pf_activo else ''}"
        _params_pagos = (_eid_dash, _pf, _eid_dash) if _pf_activo else (_eid_dash,)
        try:
            with _pg_conn() as _conn_pq:
                with _conn_pq.cursor() as _cur_pq:
                    _cur_pq.execute(_pagos_q, _params_pagos)
                    _rows_pq = _cur_pq.fetchall()
                    _cols_pq = [x.name for x in _cur_pq.description]
            df_pagos_totales = pd.DataFrame([dict(r) for r in _rows_pq], columns=_cols_pq) if _rows_pq else pd.DataFrame(columns=_cols_pq)
        except Exception as _qe2:
            st.error(f"❌ Error en _pagos_q: `{_qe2}`")
            st.code(_pagos_q)
            try:
                with _pg_conn() as _conn2:
                    with _conn2.cursor() as _cur2:
                        _cur2.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'pagos_historial' ORDER BY ordinal_position")
                        _cols_ph = [r["column_name"] for r in _cur2.fetchall()]
                st.write("Columnas reales de pagos_historial:", _cols_ph)
            except Exception as _ce:
                st.write(f"No se pudo leer schema: {_ce}")
            conn.close()
            st.stop()
        conn.close()
        
        total_activos = len(df_dash)
        caja_historica = df_pagos_totales['monto_total'].sum() if not df_pagos_totales.empty else 0.0
        
        vencen_pronto = 0
        actualizan_este_mes = 0
        lista_alertas_vencimiento = []
        lista_alertas_actualizacion = []
        
        fecha_hoy = datetime.now().date()
        
        for _, row in df_dash.iterrows():
            try:
                try:
                    fin_dt = datetime.strptime(row['fin_contrato'], "%Y-%m-%d").date()
                except ValueError:
                    fin_dt = datetime.strptime(row['fin_contrato'], "%d/%m/%Y").date()
                dias_para_vencer = (fin_dt - fecha_hoy).days
                if 0 <= dias_para_vencer <= 60:
                    vencen_pronto += 1
                    lista_alertas_vencimiento.append(f"⚠️ El contrato de **{row['inquilino']}** ({row['alias_propiedad']}) vence en **{dias_para_vencer} días** ({row['fin_contrato']}).")
            except:
                pass
                
            opciones_meses = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24}
            frecuencia = opciones_meses.get(row['act_contrato'], 6)
            mes_vivo = row['mes_contrato'] or 1
            if ((mes_vivo - 1) % frecuencia) == 0:
                actualizan_este_mes += 1
                lista_alertas_actualizacion.append(f"📈 Corresponde ajustar alquiler a **{row['inquilino']}** ({row['alias_propiedad']}). Período: {row['act_contrato']}.")

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Contratos Activos", total_activos)
        kpi2.metric("Ajustes este Mes", actualizan_este_mes, delta=f"{actualizan_este_mes} requeridos", delta_color="inverse" if actualizan_este_mes > 0 else "normal")
        kpi3.metric("Próximos Vencimientos (60d)", vencen_pronto, delta=f"{vencen_pronto} alertas", delta_color="off")
        kpi4.metric("Recaudación Total de Caja", f"$ {caja_historica:,.2f}")
        
        st.markdown("---")
        col_al1, col_al2 = st.columns(2)
        
        with col_al1:
            st.markdown("##### 📅 Alertas de Vencimiento de Plazos")
            if lista_alertas_vencimiento:
                for alerta in lista_alertas_vencimiento:
                    st.warning(alerta)
            else:
                st.success("✅ No hay contratos por vencer en los próximos 60 días.")
                
        with col_al2:
            st.markdown("##### 📈 Alertas de Actualización de Valores (Índices)")
            if lista_alertas_actualizacion:
                for alerta in lista_alertas_actualizacion:
                    st.info(alerta)
            else:
                st.success("✅ Todos los contratos se encuentran en períodos normales de facturación.")



# =====================================================================
# PESTAÑA 2: VISUALIZACIÓN DE PLANILLA (RESULTADOS CON JOIN)
# =====================================================================
if tab_planilla:
    with tab_planilla:
        st.subheader("Historial y Estado de Contratos")

        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            busqueda = st.text_input("🔍 Buscar por Inquilino, Calle o Alias:", placeholder="Ej: Pérez o Mitre", key="buscar_planilla")
        with col_f2:
            filtro_estado = st.multiselect("Filtrar por Estado:", ["Activo", "Finalizado", "Cancelado", "Vencido"], default=["Activo"], key="filtro_estado_planilla")
        
        _pf_plan = st.session_state.get("propietario_filtro", "")
        _pf_plan_activo = rol_actual == "propietario" and bool(_pf_plan)
        _eid_plan = st.session_state.get("empresa_id", 0)
        _where_plan = "AND p.propietario = %s" if _pf_plan_activo else ""
        _params_plan = (_eid_plan, _pf_plan) if _pf_plan_activo else (_eid_plan,)

        conn = conectar_db()
        try:
            query = f'''
                SELECT 
                    c.codigo AS "CÓDIGO",
                    p.alias_propiedad AS "ALIAS PROPIEDAD",
                    (i.apellidos || ', ' || i.nombres) AS "INQUILINO",
                    (p.calle || ' ' || p.numero || CASE WHEN p.departamento <> '' AND p.departamento IS NOT NULL THEN ', Dto: ' || p.departamento ELSE '' END) AS "PROPIEDAD",
                    c.estado AS "ESTADO",
                    c.inicio_contrato AS "INICIO_CONTRATO",
                    c.fin_contrato AS "FIN_CONTRATO",
                    c.calc_duracion AS "CALC_DURACION",
                    c.monto_inicial AS "MONTO INICIAL",
                    c.alquiler AS "ALQUILER",
                    c.servicios_total AS "SERVICIOS_TOTAL",
                    c.total_pagado AS "TOTAL_ESTIMADO"
                FROM contratos c
                JOIN propiedades p ON c.alias_propiedad = p.alias_propiedad
                JOIN inquilinos i ON c.dni_inquilino = i.dni
                WHERE c.empresa_id = %s AND 1=1 {_where_plan}
                ORDER BY c.codigo DESC
            '''
            with _pg_conn() as _conn_pl:
                with _conn_pl.cursor() as _cur_pl:
                    _cur_pl.execute(query, _params_plan)
                    _rows_pl = _cur_pl.fetchall()
                    _cols_pl = [x.name for x in _cur_pl.description]
            df = pd.DataFrame([dict(r) for r in _rows_pl], columns=_cols_pl) if _rows_pl else pd.DataFrame(columns=_cols_pl)

            # 2. AGREGA ESTAS LÍNEAS PARA VOLVER A PONER LAS BARRAS:
            if not df.empty:
                # Pasamos las fechas a texto y cambiamos guiones por las barras de tu CSV
                df['INICIO_CONTRATO'] = df['INICIO_CONTRATO'].astype(str).str.replace('-', '/')
                df['FIN_CONTRATO'] = df['FIN_CONTRATO'].astype(str).str.replace('-', '/')
                if 'PROX_ACTUALIZACION' in df.columns:
                    df['PROX_ACTUALIZACION'] = df['PROX_ACTUALIZACION'].astype(str).str.replace('-', '/')

            # 3. Se muestra la tabla en la app ya corregida
            st.dataframe(df, use_container_width=True, hide_index=True)

            if not df.empty:
                if busqueda:
                    df = df[
                        df['INQUILINO'].str.contains(busqueda, case=False, na=False) | 
                        df['PROPIEDAD'].str.contains(busqueda, case=False, na=False) |
                        df['ALIAS PROPIEDAD'].str.contains(busqueda, case=False, na=False)
                    ]
                if filtro_estado:
                    df = df[df['ESTADO'].isin(filtro_estado)]
                
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No se registran contratos en la base de datos bajo los criterios de búsqueda.")
        except Exception as e:
            st.error(f"Error de lectura en la planilla general: {e}")
        finally:
            conn.close()


    # =====================================================================
    # PESTAÑA 3: CONTROL DE COBRANZAS, HISTORIAL DE CAJA Y RECIBO PDF/WHATSAPP
    # =====================================================================
    
if tab_pagos:
    if "pago_impactado" not in st.session_state:
        st.session_state.pago_impactado = False
    if "contrato_impactado_id" not in st.session_state:
        st.session_state.contrato_impactado_id = None
    with tab_pagos:
        st.subheader("💰 Registrar Cobro Mensual y Emitir Comprobantes")

        # ── Cotización USD del momento del cobro ──────────────────────
        _usd_pago_col, _ = st.columns([2, 3])
        _cotizacion_usd_pago = _usd_pago_col.number_input(
            "💵 Cotización USD al momento del cobro ($ ARS por 1 USD):",
            min_value=1.0,
            value=float(st.session_state.get("cotizacion_usd_hist", 1300.0)),
            step=10.0,
            key="cotizacion_usd_pago_input",
            help="Este valor se guardará junto al pago y no cambiará aunque la cotización cambie después"
        )
        st.session_state["cotizacion_usd_hist"] = _cotizacion_usd_pago
    
        conn = conectar_db()
    # CORRECCIÓN: Agregamos c.monto_inicial a la consulta SQL
        query_activos = '''
            SELECT 
                c.codigo, p.alias_propiedad, 
                (p.calle || ' ' || p.numero || CASE WHEN p.departamento <> '' AND p.departamento IS NOT NULL THEN ', Dto: ' || p.departamento ELSE '' END) AS propiedad_dir,
                i.apellidos, i.nombres, i.telefono, i.email,
                c.prox_actualizacion, c.alquiler, c.indice, c.act_contrato, c.calc_duracion,
                c.fin_contrato,
                c.mes_contrato, c.monto_honorarios, c.honorarios_pagados,
                c.cuota_honorarios, c.cuotas_honorarios_pagadas,
                c.monto_garantia, c.garantia, c.cuotas_deposito, c.cuotas_deposito_pagadas,
                c.imp_inmobiliario, c.expensas, c.edesal, c.gas, c.municipalidad, c.ooss, c.cochera, c.servicios_total,
                c.servicios, c.inicio_contrato, c.monto_inicial
            FROM contratos c
            JOIN propiedades p ON c.alias_propiedad = p.alias_propiedad
            JOIN inquilinos i ON c.dni_inquilino = i.dni
            WHERE c.empresa_id = %s AND c.estado = 'Activo'
            ORDER BY c.codigo DESC
        '''
        
        with _pg_conn() as _conn_act:
            with _conn_act.cursor() as _cur_act:
                _cur_act.execute(query_activos, (st.session_state.get("empresa_id", 0),))
                _rows_act = _cur_act.fetchall()
                _cols_act = [d.name for d in _cur_act.description]
        df_activos = pd.DataFrame([dict(r) for r in _rows_act], columns=_cols_act) if _rows_act else pd.DataFrame(columns=_cols_act)
        
        # --- PROCESAMIENTO DINÁMICO DEL ALQUILER ACTUALIZADO ---
        dict_activos = {}
        for _, r in df_activos.iterrows():
            datos_dict = r.to_dict()
            
            texto_servicios = str(r['servicios'])
            match_alquiler = re.search(r'\[Alq\.Actualizado:\s*\$?([\d\.,]+)', texto_servicios)
            
            if match_alquiler:
                valor_actualizado_parseado = limpiar_string_a_float(match_alquiler.group(1))
                if valor_actualizado_parseado > 0:
                    datos_dict['alquiler'] = valor_actualizado_parseado
                    
            key_desplegable = f"Cod: {r['codigo']} | {r['alias_propiedad']} - Inquilino: {str(r['apellidos']).upper()}, {str(r['nombres']).title()}"
            dict_activos[key_desplegable] = datos_dict
        
        if not dict_activos:
            st.info("No se registran contratos en estado 'Activo' para liquidar pagos.")
        else:
            contrato_seleccionado = st.selectbox("Seleccione el Contrato Activo a liquidar:", options=list(dict_activos.keys()), key="sb_pago_activo")
            c_datos = dict_activos[contrato_seleccionado]

            st.markdown("### 📝 Datos de la Liquidación Actual")
            
            # --- REPLICACIÓN DE ALERTAS DE ACTUALIZACIÓN ---
            try:
                try:
                    inicio_contrato_dt = datetime.strptime(c_datos['inicio_contrato'], "%Y-%m-%d").date()
                except ValueError:
                    inicio_contrato_dt = datetime.strptime(c_datos['inicio_contrato'], "%d/%m/%Y").date()
                try:
                    fin_contrato_dt = datetime.strptime(c_datos['fin_contrato'], "%Y-%m-%d").date()
                except ValueError:
                    fin_contrato_dt = datetime.strptime(c_datos['fin_contrato'], "%d/%m/%Y").date()
                
                opciones_actualizacion = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24}
                meses_a_texto = {str(v): k for k, v in opciones_actualizacion.items()}
                act_contrato_sel_raw = str(c_datos['act_contrato'] or "").strip()
                # Soporta tanto "Cuatrimestral" como "4" guardado en la BD
                if act_contrato_sel_raw in opciones_actualizacion:
                    act_contrato_sel = act_contrato_sel_raw
                elif act_contrato_sel_raw in meses_a_texto:
                    act_contrato_sel = meses_a_texto[act_contrato_sel_raw]
                else:
                    act_contrato_sel = act_contrato_sel_raw
                meses_a_sumar = opciones_actualizacion.get(act_contrato_sel, 6)
                
                fecha_hoy = datetime.now().date()
                prox_actualizacion_calculada = inicio_contrato_dt + dateutil.relativedelta.relativedelta(months=meses_a_sumar)
                
                while prox_actualizacion_calculada < fecha_hoy and prox_actualizacion_calculada <= fin_contrato_dt:
                    prox_actualizacion_calculada += dateutil.relativedelta.relativedelta(months=meses_a_sumar)
                    
                necesita_renovacion = prox_actualizacion_calculada > fin_contrato_dt
                
                diferencia_hoy = dateutil.relativedelta.relativedelta(fecha_hoy, inicio_contrato_dt)
                total_meses_transcurridos = (diferencia_hoy.years * 12) + diferencia_hoy.months
                if total_meses_transcurridos < 0: total_meses_transcurridos = 0
                mes_actual_contrato_vivo = total_meses_transcurridos + 1
                
                es_mes_de_actualizacion = ((mes_actual_contrato_vivo - 1) % meses_a_sumar) == 0
                
                if necesita_renovacion:
                    st.error("🚨 Estado del Período: **RENOVAR** (La fecha de próxima actualización excede el fin del contrato)")
                elif es_mes_de_actualizacion:
                    st.warning(f"⚠️ **AVISO:** El inquilino está en el mes {mes_actual_contrato_vivo} de contrato. Según la frecuencia '{act_contrato_sel}', **corresponde aplicar una actualización del monto** en este periodo.")
                else:
                    st.info(f"Estado: Período normal (Mes {mes_actual_contrato_vivo}). No corresponde actualizar el alquiler este mes.")
                    
            except Exception as e:
                st.error(f"No se pudieron calcular las alertas de período para este contrato: {e}")

            # 2. SECCIÓN DE COLUMNAS E INPUTS NUMÉRICOS (EDICIÓN DE MONTOS)
            st.markdown("#### 🔧 Ajustar montos para el período actual")
            ed_col1, ed_col2, ed_col3, ed_col4, ed_col5 = st.columns(5)
            
            val_base_expensas = _safe_float(c_datos.get('expensas'))
            val_base_edesal = _safe_float(c_datos.get('edesal'))
            val_base_gas = _safe_float(c_datos.get('gas'))
            val_base_municipalidad = _safe_float(c_datos.get('municipalidad'))
            val_base_cochera = _safe_float(c_datos.get('cochera'))
            
            monto_expensas = ed_col1.number_input("🏢 Expensas Consorcio ($):", min_value=0.0, value=val_base_expensas, step=500.0)
            monto_edesal = ed_col2.number_input("⚡ Luz (EDESAL) ($):", min_value=0.0, value=val_base_edesal, step=500.0)
            monto_gas = ed_col3.number_input("🔥 Gas Natural ($):", min_value=0.0, value=val_base_gas, step=500.0)
            monto_municipalidad = ed_col4.number_input("🏛️ Tasas Municipales ($):", min_value=0.0, value=val_base_municipalidad, step=200.0)
            monto_cochera = ed_col5.number_input("🚗 Alquiler Cochera ($):", min_value=0.0, value=val_base_cochera, step=1000.0)

            # --- CONCEPTOS ESPECIALES DE CONTRATO UNIFICADOS Y COMPORTAMIENTO IDÉNTICO ---
            st.markdown("#### 📑 Conceptos Especiales de Contrato")
            ed_col_esp1, ed_col_esp2 = st.columns(2)

            # ── HONORARIOS (a cargo del inquilino) ──────────────────────────
            _monto_inicial = _safe_float(c_datos.get('monto_inicial'))
            _raw_hon = c_datos.get('monto_honorarios')
            total_honorarios_inquilino  = _safe_float(_raw_hon) if _raw_hon is not None else _monto_inicial
            if total_honorarios_inquilino == 0.0:
                total_honorarios_inquilino = _monto_inicial
            cuotas_hon_pactadas         = _safe_int(c_datos.get('cuota_honorarios'), 1)
            pagado_honorarios_inquilino = _safe_float(c_datos.get('honorarios_pagados'))
            saldo_honorarios_inquilino  = max(0.0, total_honorarios_inquilino - pagado_honorarios_inquilino)
            cuotas_hon_pagadas          = _safe_int(c_datos.get('cuotas_honorarios_pagadas'), 0)
            cuotas_hon_pendientes       = max(0, cuotas_hon_pactadas - cuotas_hon_pagadas)

            # Valor de la cuota: total dividido en las cuotas pactadas
            valor_cuota_hon = round(total_honorarios_inquilino / cuotas_hon_pactadas, 2) if cuotas_hon_pactadas > 0 else 0.0
            # Default del mes: cuota normal, o el saldo si es la última y hay diferencia de redondeo
            default_hon = min(valor_cuota_hon, saldo_honorarios_inquilino) if cuotas_hon_pendientes > 0 else 0.0

            with ed_col_esp1:
                if cuotas_hon_pendientes > 0:
                    st.info(
                        f"💼 Honorarios: cuota {cuotas_hon_pagadas + 1} de {cuotas_hon_pactadas} — "
                        f"valor cuota: **$ {valor_cuota_hon:,.2f}** — saldo total: $ {saldo_honorarios_inquilino:,.2f}"
                    )
                else:
                    st.success("💼 Honorarios: ✅ Completamente abonados.")
            monto_honorarios_pago = ed_col_esp1.number_input(
                "💼 Honorarios Inmobiliaria (Comisión Contrato) ($):",
                min_value=0.0,
                value=default_hon,
                step=1000.0,
                help=(
                    f"Total pactado: ${total_honorarios_inquilino:,.2f} en {cuotas_hon_pactadas} cuota(s). "
                    f"Pagado: ${pagado_honorarios_inquilino:,.2f} ({cuotas_hon_pagadas} cuota(s)). "
                    f"Pendientes: {cuotas_hon_pendientes} cuota(s) — Saldo: ${saldo_honorarios_inquilino:,.2f}"
                )
            )

            # ── DEPÓSITO DE GARANTÍA (a cargo del inquilino) ────────────────
            _raw_garantia = c_datos.get('monto_garantia')
            val_teorico_garantia = _safe_float(_raw_garantia) if _raw_garantia is not None else _monto_inicial
            if val_teorico_garantia == 0.0:
                val_teorico_garantia = _monto_inicial
            cuotas_dep_pactadas     = _safe_int(c_datos.get('cuotas_deposito'), 1)
            try:
                pagado_garantia_inquilino = _safe_float(c_datos.get('garantia'))
            except (ValueError, TypeError):
                pagado_garantia_inquilino = 0.0
            saldo_garantia_inquilino = max(0.0, val_teorico_garantia - pagado_garantia_inquilino)
            cuotas_dep_pagadas       = _safe_int(c_datos.get('cuotas_deposito_pagadas'), 0)
            cuotas_dep_pendientes    = max(0, cuotas_dep_pactadas - cuotas_dep_pagadas)

            valor_cuota_dep = round(val_teorico_garantia / cuotas_dep_pactadas, 2) if cuotas_dep_pactadas > 0 else 0.0
            default_dep = min(valor_cuota_dep, saldo_garantia_inquilino) if cuotas_dep_pendientes > 0 else 0.0

            with ed_col_esp2:
                if cuotas_dep_pendientes > 0:
                    st.info(
                        f"🛡️ Depósito: cuota {cuotas_dep_pagadas + 1} de {cuotas_dep_pactadas} — "
                        f"valor cuota: **$ {valor_cuota_dep:,.2f}** — saldo total: $ {saldo_garantia_inquilino:,.2f}"
                    )
                else:
                    st.success("🛡️ Depósito de Garantía: ✅ Completamente abonado.")
            monto_garantia_pago = ed_col_esp2.number_input(
                "🛡️ Respaldo con Monto Depositado (Garantía) ($):",
                min_value=0.0,
                value=default_dep,
                step=1000.0,
                help=(
                    f"Total pactado: ${val_teorico_garantia:,.2f} en {cuotas_dep_pactadas} cuota(s). "
                    f"Depositado: ${pagado_garantia_inquilino:,.2f} ({cuotas_dep_pagadas} cuota(s)). "
                    f"Pendientes: {cuotas_dep_pendientes} cuota(s) — Saldo: ${saldo_garantia_inquilino:,.2f}"
                )
            )

            # Re-calculamos dinámicamente la lista de servicios basada en los nuevos inputs de pantalla
            detalles_recibo_servicios = []
            desglose_pantalla_pdf = []
            
            if c_datos['imp_inmobiliario'] and c_datos['imp_inmobiliario'] > 0 and "[Imp.Inmob: Inquilino]" in str(c_datos['servicios']):
                detalles_recibo_servicios.append(f" - Imp. Inmobiliario: $ {c_datos['imp_inmobiliario']:,.2f}")
                desglose_pantalla_pdf.append({"Concepto": "📌 Impuesto Inmobiliario Provincial", "Monto": c_datos['imp_inmobiliario']})
                
            if monto_expensas > 0:
                detalles_recibo_servicios.append(f" - Expensas Consorcio: $ {monto_expensas:,.2f}")
                desglose_pantalla_pdf.append({"Concepto": "🏢 Expensas Consorcio", "Monto": monto_expensas})
                
            if monto_edesal > 0:
                detalles_recibo_servicios.append(f" - Luz (EDESAL): $ {monto_edesal:,.2f}")
                desglose_pantalla_pdf.append({"Concepto": "⚡ Energía Eléctrica (EDESAL)", "Monto": monto_edesal})
                
            if monto_gas > 0:
                detalles_recibo_servicios.append(f" - Gas Natural: $ {monto_gas:,.2f}")
                desglose_pantalla_pdf.append({"Concepto": "🔥 Gas Natural", "Monto": monto_gas})
                
            if monto_municipalidad > 0:
                detalles_recibo_servicios.append(f" - Tasas Municipales: $ {monto_municipalidad:,.2f}")
                desglose_pantalla_pdf.append({"Concepto": "🏛️ Tasas Municipales", "Monto": monto_municipalidad})
                
            if c_datos['ooss'] and c_datos['ooss'] > 0:
                detalles_recibo_servicios.append(f" - Obras Sanitarias (OO.SS): $ {c_datos['ooss']:,.2f}")
                desglose_pantalla_pdf.append({"Concepto": "💧 Obras Sanitarias (OO.SS)", "Monto": c_datos['ooss']})
                
            if monto_cochera > 0:
                detalles_recibo_servicios.append(f" - Alquiler Cochera: $ {monto_cochera:,.2f}")
                desglose_pantalla_pdf.append({"Concepto": "🚗 Alquiler Cochera Complementaria", "Monto": monto_cochera})

            if monto_honorarios_pago > 0:
                detalles_recibo_servicios.append(f" - Honorarios Inmobiliaria: $ {monto_honorarios_pago:,.2f}")
                desglose_pantalla_pdf.append({"Concepto": "💼 Honorarios Inmobiliaria (Comisión de Contrato)", "Monto": monto_honorarios_pago})
                
            if monto_garantia_pago > 0:
                detalles_recibo_servicios.append(f" - Respaldo Monto Depositado: $ {monto_garantia_pago:,.2f}")
                desglose_pantalla_pdf.append({"Concepto": "🛡️ Respaldo con Monto Depositado (Depósito en Garantía)", "Monto": monto_garantia_pago})

            # monto_serv_pago se calculará después del expander, desde _desglose_editado
            # Aquí solo definimos los auxiliares que se necesitan antes
            val_imp_inmob = _safe_float(c_datos.get('imp_inmobiliario')) if "[Imp.Inmob: Inquilino]" in str(c_datos['servicios']) else 0.0
            val_ooss = _safe_float(c_datos.get('ooss'))
            # Subtotal provisorio para el campo "Adicionales" (se reemplaza tras el expander)
            monto_serv_pago = val_imp_inmob + monto_expensas + monto_edesal + monto_gas + monto_municipalidad + val_ooss + monto_cochera + monto_honorarios_pago + monto_garantia_pago

            # ── MONTO NETO ALQUILER con cálculo automático de índice ─────────
            val_monto_ini_recibo = _safe_float(c_datos.get('monto_inicial'))
            val_alq_ultimo_recibo = _safe_float(c_datos.get('alquiler'))
            indice_recibo = str(c_datos.get('indice') or 'ICL').upper()

            # Convertir date a datetime igual que en la pestaña de carga
            inicio_contrato_recibo = datetime.combine(inicio_contrato_dt, datetime.min.time())

            st.markdown("#### 💰 Monto Neto de Alquiler")
            r_col1, r_col2, r_col3 = st.columns([2, 2, 2])
            r_col1.markdown(f"🔗 [Verificar en arquiler.com](https://arquiler.com/pwa?amount={int(val_monto_ini_recibo)}&date={inicio_contrato_dt.strftime('%Y-%m-%d')}&months={meses_a_sumar}&rate={indice_recibo.lower()})")

            # Calcular la última fecha de actualización ya aplicada.
            # Ejemplo: inicio 1-ene-25, trimestral, hoy 10-jun-26 → prox = 1-jul-26 → última = 1-abr-26
            try:
                _ultima_act_dt = prox_actualizacion_calculada - dateutil.relativedelta.relativedelta(months=int(meses_a_sumar))
                _delta_ultima = dateutil.relativedelta.relativedelta(_ultima_act_dt, inicio_contrato_dt)
                _meses_hasta_ultima_act = (_delta_ultima.years * 12) + _delta_ultima.months
                if _meses_hasta_ultima_act <= 0:
                    _meses_hasta_ultima_act = int(meses_a_sumar)
            except Exception:
                _meses_hasta_ultima_act = int(meses_a_sumar)

            # Calcula: monto_inicial × (ICL_ultima_actualizacion / ICL_inicio_contrato)
            valor_auto_recibo = None
            if indice_recibo in ("ICL", "IPC"):
                with st.spinner(f"⏳ Consultando {indice_recibo}..."):
                    if indice_recibo == "ICL":
                        valor_auto_recibo = calcular_valor_actualizado_icl(
                            val_monto_ini_recibo, inicio_contrato_recibo, _meses_hasta_ultima_act
                        )
                    elif indice_recibo == "IPC":
                        valor_auto_recibo = calcular_valor_actualizado_ipc(
                            val_monto_ini_recibo, inicio_contrato_recibo, _meses_hasta_ultima_act
                        )

            if valor_auto_recibo is not None:
                valor_auto_recibo_fmt = f"$ {int(valor_auto_recibo):,}".replace(",", ".")
                _fecha_desde_fmt = inicio_contrato_dt.strftime("%d/%m/%Y")
                _fecha_hasta_fmt = _ultima_act_dt.strftime("%d/%m/%Y")
                r_col2.metric(
                    label=f"📡 Auto {indice_recibo} (oficial)",
                    value=valor_auto_recibo_fmt,
                    help=(
                        f"Calculado con datos oficiales del {'BCRA' if indice_recibo == 'ICL' else 'INDEC'}. "
                        f"Período: {_fecha_desde_fmt} → {_fecha_hasta_fmt} "
                        f"({_meses_hasta_ultima_act} meses acumulados desde el inicio del contrato)."
                    )
                )
                val_base_alq = valor_auto_recibo
            else:
                if indice_recibo in ("ICL", "IPC"):
                    fuente_r = "BCRA" if indice_recibo == "ICL" else "INDEC"
                    r_col2.warning(
                        f"⚠️ No se pudo obtener el índice desde {fuente_r}. "
                        "Ingresá el valor manualmente o verificá en arquiler.com (↖).",
                    )
                    if r_col2.button("🔄 Reintentar", key=f"retry_indice_recibo_{c_datos['codigo']}"):
                        _obtener_icl_bcra_xls.clear()
                        _obtener_ipc_indec.clear()
                        st.rerun()
                val_base_alq = val_alq_ultimo_recibo if val_alq_ultimo_recibo > 0 else val_monto_ini_recibo

            # Resetear el campo si el valor calculado cambió (evita cacheo de session_state)
            _key_alq_pago = f"monto_alq_pago_{c_datos['codigo']}"
            _key_alq_ref  = f"_ref_alq_pago_{c_datos['codigo']}"
            if st.session_state.get(_key_alq_ref) != val_base_alq:
                st.session_state[_key_alq_pago] = val_base_alq
                st.session_state[_key_alq_ref]  = val_base_alq

            cp_col1, cp_col2, cp_col3, cp_col4 = st.columns(4)
            monto_alq_pago = cp_col1.number_input("Monto Neto Alquiler ($):", min_value=0.0, value=val_base_alq, step=5000.0, key=_key_alq_pago)
            # cp_col2 y cp_col3 se llenan después del expander con el total real
            _ph_servicios = cp_col2.empty()
            _ph_total     = cp_col3.empty()
            metodo_pago = cp_col4.selectbox("Método de Pago:", ["Transferencia Bancaria", "Efectivo", "Depósito", "Cheque"])

            
            # 3. CONSTRUCCIÓN DE LA TABLA EDITABLE DE CONCEPTOS
            with st.expander("🔍 Ver y editar conceptos del comprobante", expanded=True):
                st.markdown("Podés ajustar la descripción y el monto de cada concepto antes de generar el comprobante. Los cambios sólo afectan al PDF.")

                # ── Fila del alquiler base (siempre presente, editable) ──
                _ecol_h1, _ecol_h2 = st.columns([3, 1])
                _ecol_h1.markdown("**Descripción**")
                _ecol_h2.markdown("**Monto ($)**")

                _alq_desc_edit = st.text_input(
                    "Descripción alquiler",
                    value="Valor Locativo Neto (Alquiler Base)",
                    label_visibility="collapsed",
                    key=f"desc_alq_{c_datos['codigo']}"
                )
                # monto_alq_pago ya viene del number_input de arriba; lo mostramos como referencia
                _ecol_h2.markdown(f"$ {monto_alq_pago:,.2f}")

                # ── Filas editables para cada concepto de servicio ──
                _desglose_editado = []   # lista de {"Concepto": str, "Monto": float}
                for _idx_item, _item in enumerate(desglose_pantalla_pdf):
                    _ic1, _ic2 = st.columns([3, 1])
                    _desc_e = _ic1.text_input(
                        f"desc_{_idx_item}",
                        value=_item["Concepto"],
                        label_visibility="collapsed",
                        key=f"desc_{c_datos['codigo']}_{_idx_item}"
                    )
                    _monto_e = _ic2.number_input(
                        f"monto_{_idx_item}",
                        value=float(_item["Monto"]),
                        min_value=0.0,
                        step=100.0,
                        label_visibility="collapsed",
                        key=f"monto_{c_datos['codigo']}_{_idx_item}"
                    )
                    _desglose_editado.append({"Concepto": _desc_e, "Monto": _monto_e})

                # ── Línea extra libre ──
                st.markdown("---")
                st.caption("➕ Concepto adicional libre (opcional)")
                _extra_c1, _extra_c2 = st.columns([3, 1])
                _extra_desc = _extra_c1.text_input(
                    "Descripción extra",
                    value="",
                    placeholder="Ej: Sellado de contrato, Multa por mora...",
                    label_visibility="collapsed",
                    key=f"extra_desc_{c_datos['codigo']}"
                )
                _extra_monto = _extra_c2.number_input(
                    "Monto extra",
                    value=0.0,
                    min_value=0.0,
                    step=100.0,
                    label_visibility="collapsed",
                    key=f"extra_monto_{c_datos['codigo']}"
                )
                if _extra_desc.strip() and _extra_monto > 0:
                    _desglose_editado.append({"Concepto": _extra_desc.strip(), "Monto": _extra_monto})

                # ── Recalcular total con montos editados ──
                _total_servicios_editado = sum(d["Monto"] for d in _desglose_editado)
                _total_comprobante_editado = monto_alq_pago + _total_servicios_editado
                st.markdown(f"**Total comprobante: $ {_total_comprobante_editado:,.2f}**")

            # Recalcular monto_serv_pago y total_pago_real desde el desglose editado
            # Esto sincroniza el expander con el campo "Monto Abonado"
            monto_serv_pago = _total_servicios_editado
            total_pago_real = monto_alq_pago + monto_serv_pago
            # Llenar los placeholders con los totales reales
            _ph_servicios.number_input("Monto Adicionales / Servicios ($):", min_value=0.0, value=float(monto_serv_pago), disabled=True, key=f"ph_serv_{c_datos['codigo']}")
            _ph_total.number_input("TOTAL A RECAUDAR ($):", min_value=0.0, value=float(total_pago_real), disabled=True, key=f"ph_total_{c_datos['codigo']}")

            # --- NUEVA LÓGICA: Período calculado dinámicamente desde fechas ---
            try:
                _inicio_dt = datetime.strptime(str(c_datos['inicio_contrato']), "%Y-%m-%d").date()
            except ValueError:
                _inicio_dt = datetime.strptime(str(c_datos['inicio_contrato']), "%d/%m/%Y").date()
            try:
                _fin_dt = datetime.strptime(str(c_datos['fin_contrato']), "%Y-%m-%d").date()
            except ValueError:
                _fin_dt = datetime.strptime(str(c_datos['fin_contrato']), "%d/%m/%Y").date()

            # Mes actual del contrato: meses transcurridos desde el inicio + 1
            _diff_actual = dateutil.relativedelta.relativedelta(datetime.now().date(), _inicio_dt)
            _meses_transcurridos = (_diff_actual.years * 12) + _diff_actual.months
            if _meses_transcurridos < 0:
                _meses_transcurridos = 0
            mes_actual_num = _meses_transcurridos + 1

            # Duración total en meses entre inicio y fin del contrato (ambos extremos inclusivos)
            _delta = dateutil.relativedelta.relativedelta(_fin_dt, _inicio_dt)
            meses_totales_contrato = (_delta.years * 12) + _delta.months
            if _delta.days > 0 and _fin_dt.day != _inicio_dt.day:
                meses_totales_contrato += 1
            if meses_totales_contrato <= 0:
                meses_totales_contrato = _safe_int(c_datos.get('calc_duracion'), 0)

            # Generar lista de todos los meses del contrato
            opciones_periodo = [f"Mes {m} de {meses_totales_contrato}" for m in range(1, meses_totales_contrato + 1)]
            indice_default = max(0, min(mes_actual_num - 1, len(opciones_periodo) - 1))

            mes_periodo_texto = st.selectbox(
                "📅 Período a liquidar:",
                options=opciones_periodo,
                index=indice_default,
                key=f"sel_periodo_{c_datos['codigo']}"
            )

            # --- VERIFICAR SI YA EXISTE UN PAGO PARA ESTE PERÍODO ---
            with _pg_conn() as _conn_chk:
                with _conn_chk.cursor() as _cur_chk:
                    _cur_chk.execute(
                        "SELECT monto_abonado AS monto_total, comentario AS comentarios FROM pagos_historial WHERE codigo_contrato = %s AND periodo = %s ORDER BY id DESC",
                        (c_datos['codigo'], mes_periodo_texto)
                    )
                    _rows_existentes = _cur_chk.fetchall()
                    _cur_chk.execute(
                        "SELECT periodo, monto_abonado AS monto_total, comentario AS comentarios FROM pagos_historial WHERE codigo_contrato = %s AND periodo != %s ORDER BY id ASC",
                        (c_datos['codigo'], mes_periodo_texto)
                    )
                    _todos_los_pagos = _cur_chk.fetchall()

            _row_existente = _rows_existentes[0] if _rows_existentes else None

            # Calcular saldos pendientes de períodos anteriores
            # Leemos directamente la columna saldo_pendiente (suma por período, el último registro es el vigente)
            _saldos_anteriores_detalle = {}
            for _row_ph in _todos_los_pagos:
                _p = _row_ph["periodo"]; _monto = _row_ph["monto_total"]; _coment = _row_ph["comentarios"]
                _abonado = float(_monto or 0)
                # Extraer saldo de comentarios (compatibilidad con registros viejos)
                import re as _re
                _match_tot = _re.search(r'Saldo: \$ ([\d\.,]+)', _coment or "")
                if _match_tot:
                    _saldo_ese = float(_match_tot.group(1).replace('.','').replace(',','.'))
                    _saldos_anteriores_detalle[_p] = _saldo_ese

            # Complementar con la columna saldo_pendiente de registros nuevos
            with _pg_conn() as _conn_sp:
                with _conn_sp.cursor() as _cur_sp:
                    _cur_sp.execute(
                        """SELECT periodo, saldo_pendiente FROM pagos_historial
                           WHERE codigo_contrato = %s AND periodo != %s
                           AND saldo_pendiente > 0
                           ORDER BY id DESC""",
                        (c_datos['codigo'], mes_periodo_texto)
                    )
                    _sp_rows = _cur_sp.fetchall()
            # La columna saldo_pendiente tiene prioridad sobre el texto del comentario
            for _sp_row in _sp_rows:
                _p_sp = _sp_row["periodo"]; _s_sp = _sp_row["saldo_pendiente"]
                _saldos_anteriores_detalle[_p_sp] = float(_s_sp or 0)

            # Filtrar solo los que efectivamente tienen saldo > 0
            _saldos_anteriores_detalle = {p: s for p, s in _saldos_anteriores_detalle.items() if s > 0}
            _total_saldos_anteriores = sum(_saldos_anteriores_detalle.values())

            # Calcular saldo acumulado real del período seleccionado
            saldo_periodo_anterior = 0.0
            _total_abonado_periodo = 0.0
            if _row_existente:
                _total_abonado_periodo = sum(float(r["monto_total"] or 0) for r in _rows_existentes)
                saldo_periodo_anterior = max(0.0, total_pago_real - _total_abonado_periodo)
                if saldo_periodo_anterior > 0:
                    st.warning(
                        f"⚠️ **Período {mes_periodo_texto} con pago parcial registrado.** "
                        f"Total abonado hasta ahora: **$ {_total_abonado_periodo:,.2f}** — "
                        f"Saldo pendiente: **$ {saldo_periodo_anterior:,.2f}**"
                    )
                else:
                    st.error(f"🔒 **{mes_periodo_texto} ya fue liquidado en su totalidad** (Total abonado: $ {_total_abonado_periodo:,.2f}). No se puede volver a impactar.")
            else:
                # Período nuevo: mostrar y sumar saldos anteriores si existen
                if _total_saldos_anteriores > 0:
                    _detalle_saldos = " | ".join([f"{p}: $ {s:,.2f}" for p, s in _saldos_anteriores_detalle.items() if s > 0])
                    st.warning(f"📋 Saldos pendientes de períodos anteriores: $ {_total_saldos_anteriores:,.2f} ({_detalle_saldos})")

            # Total a cubrir en este recibo:
            # - Período con saldo parcial → cubrir ese saldo
            # - Período nuevo → total del mes + saldos de períodos anteriores
            if saldo_periodo_anterior > 0:
                _total_a_cubrir = saldo_periodo_anterior
            elif not _row_existente:
                _total_a_cubrir = total_pago_real + _total_saldos_anteriores
                if _total_saldos_anteriores > 0:
                    cp_col3.empty()  # reemplazar el widget anterior
                    st.info(f"💰 **TOTAL A RECAUDAR (con saldos anteriores): $ {_total_a_cubrir:,.2f}**  "
                            f"*(Mes actual: $ {total_pago_real:,.2f} + Saldos anteriores: $ {_total_saldos_anteriores:,.2f})*")
            else:
                _total_a_cubrir = total_pago_real

            # --- MONTO ABONADO Y SALDO PENDIENTE ---
            _valor_default_abonado = float(_total_a_cubrir)
            _key_abonado = f"monto_abonado_{c_datos['codigo']}_{mes_periodo_texto}"

            # Si el total a cubrir cambió respecto al valor guardado en session_state, resetear
            _key_ref = f"_ref_total_{c_datos['codigo']}_{mes_periodo_texto}"
            if st.session_state.get(_key_ref) != _valor_default_abonado:
                st.session_state[_key_abonado] = _valor_default_abonado
                st.session_state[_key_ref] = _valor_default_abonado

            saldo_col1, saldo_col2 = st.columns(2)
            monto_abonado = saldo_col1.number_input(
                "💵 Monto Abonado por el Inquilino ($):",
                min_value=0.0,
                value=float(_valor_default_abonado),
                step=1000.0,
                key=_key_abonado
            )
            saldo_pendiente = _total_a_cubrir - monto_abonado
            if saldo_pendiente > 0:
                saldo_col2.metric("⚠️ Saldo Pendiente ($):", f"$ {saldo_pendiente:,.2f}", delta=f"-{saldo_pendiente:,.2f}", delta_color="inverse")
            elif saldo_pendiente < 0:
                saldo_col2.metric("✅ A Favor del Inquilino ($):", f"$ {abs(saldo_pendiente):,.2f}", delta=f"+{abs(saldo_pendiente):,.2f}", delta_color="normal")
            else:
                saldo_col2.metric("✅ Saldo Pendiente ($):", "$ 0,00 — Cancelado", delta="Pago completo", delta_color="off")

            comentarios_pago = st.text_input("Notas / Comentarios Internos de Caja:", placeholder="Ej: Abonó del 1 al 5 en término")
            
            # --- BOTÓN IMPACTAR COBRO EN CAJA HISTORICA ---
            # Resetear flag si el usuario cambió de contrato
            if st.session_state.contrato_impactado_id != c_datos['codigo']:
                st.session_state.pago_impactado = False
                st.session_state.contrato_impactado_id = None

            if st.button("📥 Impactar Cobro en Caja Histórica", type="primary",
                           disabled=bool(_row_existente and saldo_periodo_anterior == 0)):
                conn = conectar_db()
                cursor = conn.cursor()
                try:
                    # 1. Guarda el registro en el historial de cobros con los montos recalculados
                    # Saldo real = lo que faltó cubrir de este recibo
                    _saldo_a_guardar = max(0.0, _total_a_cubrir - monto_abonado)
                    _comentario_completo = comentarios_pago or ""
                    if _saldo_a_guardar > 0:
                        _comentario_completo += f" | Abonado: $ {monto_abonado:,.2f} | Saldo: $ {_saldo_a_guardar:,.2f}"
                    _val_ooss_insert = _safe_float(c_datos.get('ooss'))
                    _val_imp_insert = _safe_float(c_datos.get('imp_inmobiliario')) if "[Imp.Inmob: Inquilino]" in str(c_datos.get('servicios','')) else 0.0
                    # Calcular valores USD al tipo de cambio del momento
                    _tc_insert = st.session_state.get("cotizacion_usd_hist", 0.0)
                    _tc_insert = float(_tc_insert) if float(_tc_insert) > 0 else 0.0
                    _alq_usd    = round(monto_alq_pago / _tc_insert, 2)    if _tc_insert > 0 else 0.0
                    _coch_usd   = round(monto_cochera / _tc_insert, 2)     if _tc_insert > 0 else 0.0
                    _imp_usd    = round(_val_imp_insert / _tc_insert, 2)   if _tc_insert > 0 else 0.0
                    _ret_agencia = round(monto_abonado * _safe_float(c_datos.get('honorarios')) / 100.0, 2)
                    _ret_usd    = round(_ret_agencia / _tc_insert, 2)      if _tc_insert > 0 else 0.0
                    cursor.execute('''
                        INSERT INTO pagos_historial (
                            empresa_id, codigo_contrato, propiedad, inquilino,
                            periodo, monto_alquiler,
                            fecha, metodo_pago, comentario,
                            monto_expensas, monto_edesal, monto_gas, monto_municipalidad,
                            monto_cochera, monto_ooss, monto_imp_inmobiliario,
                            monto_honorarios, monto_garantia,
                            monto_abonado, saldo_pendiente, saldos_anteriores
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        st.session_state.get("empresa_id", 0),
                        c_datos['codigo'], c_datos.get('propiedad_dir', ''), c_datos.get('inquilino_nombre', ''),
                        mes_periodo_texto, monto_alq_pago,
                        datetime.now().strftime("%d/%m/%Y %H:%M"), metodo_pago, _comentario_completo,
                        monto_expensas, monto_edesal, monto_gas, monto_municipalidad,
                        monto_cochera, _val_ooss_insert, _val_imp_insert,
                        monto_honorarios_pago, monto_garantia_pago,
                        monto_abonado, _saldo_a_guardar, _total_saldos_anteriores
                    ))

                    # 2. Avanzar automáticamente el contador del mes vivo del contrato
                    nuevo_mes_vivo = (c_datos['mes_contrato'] or 1) + 1
                    cursor.execute("UPDATE contratos SET mes_contrato = %s WHERE codigo = %s", (nuevo_mes_vivo, c_datos['codigo']))

                    # 3. Pisar el valor del alquiler base con el monto recién cobrado
                    cursor.execute("UPDATE contratos SET alquiler = %s WHERE codigo = %s", (monto_alq_pago, c_datos['codigo']))

                    # 4. Acumula el cobro de honorarios directamente sobre lo que ya pagó el Inquilino
                    nuevos_honorarios_acumulados = pagado_honorarios_inquilino + monto_honorarios_pago
                    # Incrementar cuotas_honorarios_pagadas solo si se cobró algo en este concepto
                    nuevas_cuotas_hon_pagadas = cuotas_hon_pagadas + (1 if monto_honorarios_pago > 0 and cuotas_hon_pendientes > 0 else 0)

                    # 4b. Acumula el cobro de garantía directamente sobre el Monto Depositado a la Fecha
                    nueva_garantia_acumulada = pagado_garantia_inquilino + monto_garantia_pago
                    # Incrementar cuotas_deposito_pagadas solo si se cobró algo en este concepto
                    nuevas_cuotas_dep_pagadas = cuotas_dep_pagadas + (1 if monto_garantia_pago > 0 and cuotas_dep_pendientes > 0 else 0)

                    # 5. Guardar los valores actualizados de manera persistente en la base de datos
                    cursor.execute('''
                        UPDATE contratos
                        SET expensas = %s, edesal = %s, gas = %s, municipalidad = %s, cochera = %s,
                            honorarios_pagados = %s, cuotas_honorarios_pagadas = %s,
                            garantia = %s, cuotas_deposito_pagadas = %s,
                            servicios_total = %s
                        WHERE codigo = %s
                    ''', (monto_expensas, monto_edesal, monto_gas, monto_municipalidad, monto_cochera,
                          nuevos_honorarios_acumulados, nuevas_cuotas_hon_pagadas,
                          str(nueva_garantia_acumulada), nuevas_cuotas_dep_pagadas,
                          monto_serv_pago, c_datos['codigo']))

                    conn.commit()
                    st.success(f"✔️ Cobro de {mes_periodo_texto} guardado. Abonado: $ {monto_abonado:,.2f} de $ {_total_a_cubrir:,.2f}. ¡Contrato avanzado al Mes {nuevo_mes_vivo}!")
                    if saldo_pendiente > 0:
                        st.warning(f"⚠️ Saldo pendiente del inquilino: $ {saldo_pendiente:,.2f}")
                    elif saldo_pendiente < 0:
                        st.info(f"✅ El inquilino pagó $ {abs(saldo_pendiente):,.2f} de más (a su favor).")
                    if monto_honorarios_pago > 0:
                        st.info(f"🔄 Honorarios: cuota {nuevas_cuotas_hon_pagadas} de {cuotas_hon_pactadas} cobrada. Acumulado: $ {nuevos_honorarios_acumulados:,.2f}")
                    if monto_garantia_pago > 0:
                        st.info(f"🛡️ Depósito Garantía: cuota {nuevas_cuotas_dep_pagadas} de {cuotas_dep_pactadas} cobrada. Acumulado: $ {nueva_garantia_acumulada:,.2f}")

                    # Activar flag para mostrar el PDF sin recargar la página
                    st.session_state.pago_impactado = True
                    st.session_state.contrato_impactado_id = c_datos['codigo']

                except Exception as e:
                    st.error(f"Error al procesar el impacto en caja: {e}")
                finally:
                    conn.close()

            if st.session_state.pago_impactado and st.session_state.contrato_impactado_id == c_datos['codigo']:
                st.markdown("---")
                st.markdown("### 🚀 Generador Inteligente de Comprobantes (WhatsApp & PDF Profesional)")
            
                txt_alquiler_fmt = f"$ {monto_alq_pago:,.2f}"
                txt_servicios_fmt = f"$ {monto_serv_pago:,.2f}"
                txt_total_fmt = f"$ {total_pago_real:,.2f}"
                servicios_str_whatsapp = "\n".join(detalles_recibo_servicios) if detalles_recibo_servicios else " - No se registran conceptos adicionales."
                
                mes_actual_num = c_datos['mes_contrato'] or 1
                try:
                    _fin_pdf = datetime.strptime(str(c_datos['fin_contrato']), "%Y-%m-%d").date()
                except ValueError:
                    _fin_pdf = datetime.strptime(str(c_datos['fin_contrato']), "%d/%m/%Y").date()
                try:
                    _ini_pdf = datetime.strptime(str(c_datos['inicio_contrato']), "%Y-%m-%d").date()
                except ValueError:
                    _ini_pdf = datetime.strptime(str(c_datos['inicio_contrato']), "%d/%m/%Y").date()
                _d_pdf = dateutil.relativedelta.relativedelta(_fin_pdf, _ini_pdf)
                _meses_pdf = (_d_pdf.years * 12) + _d_pdf.months
                if _d_pdf.days > 0 and _fin_pdf.day != _ini_pdf.day:
                    _meses_pdf += 1
                meses_totales_contrato = _meses_pdf or int(c_datos['calc_duracion'] or 0)
                periodo_numerico_pdf = f"Mes {mes_actual_num} de {meses_totales_contrato}"

                plantilla_texto = (
                    f"¡Hola {c_datos['nombres']}! 👋 Te acercamos el detalle de liquidación correspondiente al período *{mes_periodo_texto}* para la propiedad ubicada en *{c_datos['propiedad_dir']}*.\n\n"
                    f"🔹 *Concepto Alquiler:* {txt_alquiler_fmt}\n"
                    f"🔹 *Conceptos Adicionales / Servicios / Especiales:* {txt_servicios_fmt}\n"
                    f"{servicios_str_whatsapp}\n\n"
                    f"💰 *TOTAL ABONADO:* *{txt_total_fmt}* ({metodo_pago})\n\n"
                    f"📌 El presente sirve como comprobante de pago definitivo para los conceptos descritos. ¡Muchas gracias por tu responsabilidad!"
                )
                
                texto_final_recibo = st.text_area(
                    "Cuerpo de la Notificación comercial:", 
                    value=plantilla_texto.replace("\\n", "\n"), 
                    height=200
                )
                
                # Obtener teléfono del usuario que emite el recibo (desde usuarios_central)
                _tel_emisor = ""
                try:
                    with _pg_conn() as _conn_em:
                        with _conn_em.cursor() as _cur_em:
                            _cur_em.execute(
                                "SELECT telefono FROM usuarios_central WHERE username = %s",
                                (st.session_state.get("username", ""),)
                            )
                            _row_em = _cur_em.fetchone()
                        if _row_em and _row_em.get("telefono"):
                            _tel_emisor = str(_row_em["telefono"]).strip()
                except Exception:
                    pass

                def _normalizar_tel(tel):
                    """Devuelve número limpio para wa.me (solo dígitos, con prefijo 54 si es ARG)"""
                    t = tel.replace("+", "").replace(" ", "").replace("-", "")
                    if len(t) == 10 and not t.startswith("54"):
                        t = "54" + t
                    return t

                texto_url = urllib.parse.quote(texto_final_recibo)

                btn_c1, btn_c2, btn_c3 = st.columns(3)

                with btn_c1:
                    tel_inquilino = str(c_datos['telefono'] or "").strip()
                    if tel_inquilino:
                        tel_wa_inq = _normalizar_tel(tel_inquilino)
                        st.markdown(f'<a href="https://wa.me/{tel_wa_inq}?text={texto_url}" target="_blank"><button style="width:100%; padding:12px; background-color:#25D366; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">📲 Enviar al Inquilino</button></a>', unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ Inquilino sin celular.")

                with btn_c2:
                    if _tel_emisor:
                        tel_wa_emisor = _normalizar_tel(_tel_emisor)
                        st.markdown(f'<a href="https://wa.me/{tel_wa_emisor}?text={texto_url}" target="_blank"><button style="width:100%; padding:12px; background-color:#128C7E; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">📋 Enviarme a mí ({_tel_emisor})</button></a>', unsafe_allow_html=True)
                    else:
                        st.info("📵 Sin teléfono configurado en tu perfil.")

                with btn_c3:
                    _total_pdf_editado = monto_alq_pago + sum(d['Monto'] for d in _desglose_editado)

                    _pdf_bytes = generar_pdf_recibo(
                        comprobante_nro=f"RC-00{c_datos['codigo']}",
                        fecha_emision=datetime.now().strftime('%d/%m/%Y'),
                        periodo=mes_periodo_texto,
                        locatario=f"{c_datos['apellidos']}, {c_datos['nombres']}",
                        propiedad=c_datos['propiedad_dir'],
                        alquiler_desc=_alq_desc_edit,
                        alquiler_monto=monto_alq_pago,
                        filas_servicios=_desglose_editado,
                        total=_total_pdf_editado,
                        metodo_pago=metodo_pago,
                        nombre_empresa=st.session_state.get('nombre_empresa', 'Mi Empresa'),
                    )
                    st.download_button(
                        label="📄 Descargar Comprobante PDF",
                        data=_pdf_bytes,
                        file_name=f"{c_datos['apellidos']}_{c_datos['codigo']}_{mes_periodo_texto.lower().replace(' ','_')}.pdf",
                        mime="application/pdf",
                        help="Descarga el comprobante como PDF listo para archivar o enviar.",
                    )


# =====================================================================
# PESTAÑA 4: MÓDULO DE HISTORIAL DE PAGOS COMPLETO (MEJORA 1 VISUALIZACIÓN)
# =====================================================================
if tab_historial_pagos:
    with tab_historial_pagos:
        st.subheader("🗄️ Registro Completo de Caja y Balance Mensual")

        _pf_hist = st.session_state.get("propietario_filtro", "")
        _pf_hist_activo = rol_actual == "propietario" and bool(_pf_hist)
        _eid_hist = st.session_state.get("empresa_id", 0)
        _where_hist = "AND ph.propiedad IN (SELECT alias_propiedad FROM propiedades WHERE propietario = %s AND empresa_id = %s)" if _pf_hist_activo else ""
        _params_hist = (_eid_hist, _pf_hist, _eid_hist) if _pf_hist_activo else (_eid_hist,)

        conn = conectar_db()
        # Query ampliada: trae todos los montos detallados para poder reimprimir el recibo
        query_historial = f"""
            SELECT
                ph.id                                       AS "ID PAGO",
                ph.codigo_contrato                          AS "COD CONTRATO",
                ph.propiedad                                AS "PROPIEDAD",
                ph.propiedad                                AS "DIR PROPIEDAD",
                ph.inquilino                                AS "INQUILINO",
                ph.inquilino                                AS "_apellidos",
                ''                                          AS "_nombres",
                ''                                          AS "_telefono",
                ph.periodo                                  AS "PERIODO",
                COALESCE(ph.monto_alquiler,0)               AS "ALQUILER ($)",
                0                                           AS "SERVICIOS ($)",
                COALESCE(ph.monto_abonado,0)               AS "TOTAL ($)",
                ph.fecha                                    AS "FECHA IMPACTO",
                COALESCE(ph.metodo_pago,'')                 AS "METODO",
                COALESCE(ph.monto_expensas,0)               AS "_expensas",
                COALESCE(ph.monto_edesal,0)                 AS "_edesal",
                COALESCE(ph.monto_gas,0)                    AS "_gas",
                COALESCE(ph.monto_municipalidad,0)          AS "_municipalidad",
                COALESCE(ph.monto_cochera,0)                AS "_cochera",
                COALESCE(ph.monto_ooss,0)                   AS "_ooss",
                COALESCE(ph.monto_imp_inmobiliario,0)       AS "_imp_inmobiliario",
                COALESCE(ph.monto_honorarios,0)             AS "_honorarios",
                COALESCE(ph.monto_garantia,0)               AS "_garantia",
                COALESCE(ph.monto_abonado,0)                AS "_abonado",
                COALESCE(ph.saldo_pendiente,0)              AS "_saldo_pendiente",
                COALESCE(ph.comentario,'')                 AS "_comentarios",
                NULL                                        AS "_inicio_contrato",
                0                                           AS "_pct_admin",
                0                                           AS "COTIZACIÓN USD",
                0                                           AS "ALQUILER (USD)",
                0                                           AS "COCHERA (USD)",
                0                                           AS "IMP. INMOBILIARIO (USD)",
                0                                           AS "RETENCIÓN AGENCIA (USD)"
            FROM pagos_historial ph
            WHERE ph.empresa_id = %s {_where_hist}
            ORDER BY ph.id DESC
        """
        with _pg_conn() as _conn_h:
            with _conn_h.cursor() as _cur_h:
                _cur_h.execute(query_historial, _params_hist)
                _rows_h = _cur_h.fetchall()
                _cols_h = [x.name for x in _cur_h.description]
        df_historial = pd.DataFrame([dict(r) for r in _rows_h], columns=_cols_h) if _rows_h else pd.DataFrame(columns=_cols_h)
        conn.close()

        if df_historial.empty:
            st.info("Aún no se registran cobros mensuales asentados de manera definitiva en el libro de caja.")
        else:
            st.caption("💡 Los valores en USD se calculan con la cotización registrada al momento de cada cobro.")

            # ── Filtros ──────────────────────────────────────────────────
            f_periodo = st.text_input(
                "Filtrar historial por palabra clave (Ej: Mayo o Efectivo):",
                placeholder="Escriba para filtrar..."
            )
            if f_periodo:
                df_historial = df_historial[
                    df_historial['PERIODO'].str.contains(f_periodo, case=False, na=False) |
                    df_historial['INQUILINO'].str.contains(f_periodo, case=False, na=False) |
                    df_historial['METODO'].str.contains(f_periodo, case=False, na=False)
                ]

            # ── Calcular columna MES/AÑO a partir del periodo y fecha de inicio ──
            _meses_es = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
                5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
                9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
            }

            def _calcular_mes_anio(row):
                try:
                    # Extraer número de mes del periodo (Ej: "Mes 3 de 24" → 3)
                    _match = re.match(r'Mes\s+(\d+)\s+de\s+\d+', str(row['PERIODO']))
                    if not _match:
                        return ""
                    _num_mes_contrato = int(_match.group(1))
                    # Parsear fecha de inicio
                    _inicio_str = str(row['_inicio_contrato'])
                    try:
                        _inicio_dt = datetime.strptime(_inicio_str, "%Y-%m-%d").date()
                    except ValueError:
                        _inicio_dt = datetime.strptime(_inicio_str, "%d/%m/%Y").date()
                    # Sumar (num_mes - 1) meses al inicio para obtener el mes calendario
                    _fecha_mes = _inicio_dt + dateutil.relativedelta.relativedelta(months=_num_mes_contrato - 1)
                    return f"{_meses_es[_fecha_mes.month]} {_fecha_mes.year}"
                except Exception:
                    return ""

            df_historial["MES/AÑO"] = df_historial.apply(_calcular_mes_anio, axis=1)

            # ── Retención agencia en pesos (calculada; la versión USD viene de la BD) ──
            df_historial["RETENCIÓN AGENCIA ($)"] = (
                df_historial["_abonado"] / 100.0 * df_historial["_pct_admin"]
            ).round(2)

            # Renombrar columnas internas al nombre de visualización
            df_historial = df_historial.rename(columns={
                "_imp_inmobiliario": "IMP. INMOBILIARIO ($)",
                "_expensas":         "EXPENSAS ($)",
                "_edesal":           "LUZ EDESAL ($)",
                "_gas":              "GAS ($)",
                "_municipalidad":    "MUNICIPALIDAD ($)",
                "_ooss":             "OO.SS ($)",
                "_cochera":          "COCHERA ($)",
                "_honorarios":       "HONORARIOS ($)",
                "_garantia":         "GARANTÍA ($)",
                "_abonado":          "ABONADO ($)",
                "_saldo_pendiente":  "SALDO PEND. ($)",
            })

            # ── Columnas visibles en la tabla ────────────────────────────
            _cols_vista = [
                "ID PAGO", "COD CONTRATO", "PROPIEDAD", "INQUILINO",
                "PERIODO", "MES/AÑO",
                "ALQUILER ($)", "ALQUILER (USD)",
                "IMP. INMOBILIARIO ($)", "IMP. INMOBILIARIO (USD)", "EXPENSAS ($)", "LUZ EDESAL ($)",
                "GAS ($)", "MUNICIPALIDAD ($)", "OO.SS ($)",
                "COCHERA ($)", "COCHERA (USD)", "HONORARIOS ($)", "GARANTÍA ($)",
                "SERVICIOS ($)", "TOTAL ($)",
                "ABONADO ($)", "RETENCIÓN AGENCIA ($)", "RETENCIÓN AGENCIA (USD)",
                "SALDO PEND. ($)",
                "COTIZACIÓN USD", "FECHA IMPACTO", "METODO"
            ]

            st.dataframe(df_historial[_cols_vista], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("##### 📊 Resumen Estadístico de Caja Registrada")
            c_r1, c_r2, c_r3, c_r4, c_r5 = st.columns(5)
            c_r1.metric("Total Cobrado",     f"$ {df_historial['TOTAL ($)'].sum():,.2f}")
            c_r2.metric("Alquiler",          f"$ {df_historial['ALQUILER ($)'].sum():,.2f}")
            c_r3.metric("Cochera",           f"$ {df_historial['COCHERA ($)'].sum():,.2f}")
            c_r4.metric("Servicios",         f"$ {df_historial['SERVICIOS ($)'].sum():,.2f}")
            c_r5.metric("Saldo Pendiente",   f"$ {df_historial['SALDO PEND. ($)'].sum():,.2f}")

            # ── Sección de Reimpresión ────────────────────────────────────
            st.markdown("---")
            st.markdown("##### 🖨️ Reimprimir Comprobante")
            st.caption("Seleccioná un registro para regenerar y descargar el comprobante PDF original.")

            # Construir etiquetas legibles para el selector
            _opciones_reimp = {
                f"RC-00{row['COD CONTRATO']}-{row['PERIODO'].replace(' ','')}  |  {row['INQUILINO']}  |  {row['PROPIEDAD']}  |  $ {row['TOTAL ($)']:,.2f}": idx
                for idx, row in df_historial.iterrows()
            }

            _sel_label = st.selectbox(
                "Seleccionar pago a reimprimir:",
                ["— Seleccione un registro —"] + list(_opciones_reimp.keys()),
                key="reimp_sel"
            )

            if _sel_label != "— Seleccione un registro —":
                _idx = _opciones_reimp[_sel_label]
                _r = df_historial.loc[_idx]

                # Previsualización compacta del registro seleccionado
                with st.expander("🔍 Ver datos del comprobante seleccionado", expanded=True):
                    _pc1, _pc2, _pc3, _pc4 = st.columns(4)
                    _pc1.markdown(f"**Inquilino:** {_r['INQUILINO']}")
                    _pc2.markdown(f"**Propiedad:** {_r['PROPIEDAD']}")
                    _pc3.markdown(f"**Período:** {_r['PERIODO']}")
                    _pc4.markdown(f"**Total:** $ {_r['TOTAL ($)']:,.2f}")

                    _pd1, _pd2, _pd3, _pd4 = st.columns(4)
                    _pd1.markdown(f"**Alquiler:** $ {_r['ALQUILER ($)']:,.2f}")
                    _pd2.markdown(f"**Método pago:** {_r['METODO']}")
                    _pd3.markdown(f"**Fecha impacto:** {_r['FECHA IMPACTO']}")
                    _pd4.markdown(f"**ID Pago:** {_r['ID PAGO']}")

                # ── Reconstruir el HTML del recibo desde los datos guardados ──
                def _fmt(val):
                    return f"$ {float(val):,.2f}" if val else "$ 0,00"

                _filas_servicios_html = ""
                if float(_r['IMP. INMOBILIARIO ($)'] or 0) > 0:
                    _filas_servicios_html += f"<tr><td>📌 Impuesto Inmobiliario Provincial</td><td style='text-align:right;'>{_fmt(_r['IMP. INMOBILIARIO ($)'])}</td></tr>"
                if float(_r['EXPENSAS ($)'] or 0) > 0:
                    _filas_servicios_html += f"<tr><td>🏢 Expensas Consorcio</td><td style='text-align:right;'>{_fmt(_r['EXPENSAS ($)'])}</td></tr>"
                if float(_r['LUZ EDESAL ($)'] or 0) > 0:
                    _filas_servicios_html += f"<tr><td>⚡ Energía Eléctrica (EDESAL)</td><td style='text-align:right;'>{_fmt(_r['LUZ EDESAL ($)'])}</td></tr>"
                if float(_r['GAS ($)'] or 0) > 0:
                    _filas_servicios_html += f"<tr><td>🔥 Gas Natural</td><td style='text-align:right;'>{_fmt(_r['GAS ($)'])}</td></tr>"
                if float(_r['MUNICIPALIDAD ($)'] or 0) > 0:
                    _filas_servicios_html += f"<tr><td>🏛️ Tasas Municipales</td><td style='text-align:right;'>{_fmt(_r['MUNICIPALIDAD ($)'])}</td></tr>"
                if float(_r['OO.SS ($)'] or 0) > 0:
                    _filas_servicios_html += f"<tr><td>💧 Obras Sanitarias (OO.SS)</td><td style='text-align:right;'>{_fmt(_r['OO.SS ($)'])}</td></tr>"
                if float(_r['COCHERA ($)'] or 0) > 0:
                    _filas_servicios_html += f"<tr><td>🚗 Alquiler Cochera Complementaria</td><td style='text-align:right;'>{_fmt(_r['COCHERA ($)'])}</td></tr>"
                if float(_r['HONORARIOS ($)'] or 0) > 0:
                    _filas_servicios_html += f"<tr><td>💼 Honorarios Inmobiliaria (Comisión de Contrato)</td><td style='text-align:right;'>{_fmt(_r['HONORARIOS ($)'])}</td></tr>"
                if float(_r['GARANTÍA ($)'] or 0) > 0:
                    _filas_servicios_html += f"<tr><td>🛡️ Respaldo con Monto Depositado (Depósito en Garantía)</td><td style='text-align:right;'>{_fmt(_r['GARANTÍA ($)'])}</td></tr>"

                _comentario_html = ""
                if _r['_comentarios'] and str(_r['_comentarios']).strip():
                    _comentario_html = f"""
                    <table class="info-grid" style="margin-top:12px;">
                        <tr><td><strong>Observaciones:</strong> {_r['_comentarios']}</td></tr>
                    </table>"""

                _html_reimp = f"""
                <html>
                <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; padding: 30px; color: #333; background-color: #fafafa; }}
                    .invoice-card {{ background: #fff; padding: 40px; max-width: 750px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
                    .header-table {{ width: 100%; border-bottom: 3px solid #1a365d; padding-bottom: 15px; margin-bottom: 25px; }}
                    .title-main {{ color: #1a365d; font-size: 24px; font-weight: bold; margin: 0; }}
                    .meta-text {{ font-size: 13px; color: #555; text-align: right; }}
                    .section-title {{ background: #f0f4f8; padding: 8px 12px; font-weight: bold; color: #2c5282; margin-top: 20px; border-radius: 4px; }}
                    .info-grid {{ width: 100%; margin: 15px 0; font-size: 14px; line-height: 1.6; }}
                    .items-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }}
                    .items-table th {{ background: #2c5282; color: white; padding: 10px; text-align: left; }}
                    .items-table td {{ padding: 12px 10px; border-bottom: 1px solid #e2e8f0; }}
                    .total-row {{ font-size: 16px; font-weight: bold; color: #1a365d; background: #edf2f7; }}
                    .footer-stamp {{ margin-top: 60px; text-align: center; font-size: 12px; color: #718096; border-top: 1px solid #e2e8f0; padding-top: 15px; }}
                    .signature-line {{ border-top: 1px solid #4a5568; width: 200px; margin: 40px auto 10px auto; }}
                    .reprint-badge {{ background: #fff3cd; border: 1px solid #ffc107; color: #856404; padding: 4px 10px; border-radius: 4px; font-size: 11px; display: inline-block; margin-bottom: 10px; }}
                </style>
                </head>
                <body>
                    <div class="invoice-card">
                        <div class="reprint-badge">🖨️ REIMPRESIÓN — Documento original registrado el {_r['FECHA IMPACTO']}</div>
                        <table class="header-table">
                            <tr>
                                <td><h1 class="title-main">RECIBO DE ALQUILER</h1></td>
                                <td class="meta-text">
                                    <strong>Comprobante N°:</strong> RC-00{_r['COD CONTRATO']}-{str(_r['PERIODO']).replace(' ','')}<br>
                                    <strong>Fecha Emisión Original:</strong> {_r['FECHA IMPACTO']}<br>
                                    <strong>Período:</strong> {_r['PERIODO']}<br>
                                    <strong>ID Registro:</strong> #{_r['ID PAGO']}
                                </td>
                            </tr>
                        </table>

                        <div class="section-title">Datos Comerciales del Contrato</div>
                        <table class="info-grid">
                            <tr>
                                <td width="15%"><strong>Locatario:</strong></td><td>{_r['INQUILINO']}</td>
                                <td width="15%"><strong>Propiedad:</strong></td><td>{_r['DIR PROPIEDAD']}</td>
                            </tr>
                        </table>

                        <div class="section-title">Desglose de Conceptos Liquidados</div>
                        <table class="items-table">
                            <thead>
                                <tr>
                                    <th>Descripción del Concepto Asociado</th>
                                    <th style="text-align: right;">Subtotal</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>Valor Locativo Neto (Alquiler Base)</td>
                                    <td style="text-align: right;">{_fmt(_r['ALQUILER ($)'])}</td>
                                </tr>
                                {_filas_servicios_html}
                                <tr class="total-row">
                                    <td>TOTAL CONSOLIDADO PERCIBIDO</td>
                                    <td style="text-align: right;">{_fmt(_r['TOTAL ($)'])}</td>
                                </tr>
                            </tbody>
                        </table>

                        <table class="info-grid" style="margin-top:20px;">
                            <tr><td><strong>Forma de Cancelación:</strong> {_r['METODO']}</td></tr>
                        </table>
                        {_comentario_html}

                        <div style="text-align: right; margin-top: 40px;">
                            <div class="signature-line"></div>
                            <span style="font-size:13px; font-weight:bold; color:#4a5568;">{st.session_state.get('nombre_empresa', 'Mi Empresa')}</span>
                        </div>

                        <div class="footer-stamp">
                            Comprobante emitido de manera electrónica. Reimpresión autorizada — Datos extraídos del registro original N° {_r['ID PAGO']}.
                        </div>
                    </div>
                    <script>window.print();</script>
                </body>
                </html>
                """

                _nombre_archivo_reimp = f"reimpresion_RC-00{_r['COD CONTRATO']}_{str(_r['PERIODO']).replace(' ','_').lower()}.html"
                st.download_button(
                    label="🖨️ Descargar Comprobante para Reimprimir (PDF)",
                    data=_html_reimp,
                    file_name=_nombre_archivo_reimp,
                    mime="text/html",
                    type="primary",
                    help="Descarga el comprobante reconstruido. Al abrirlo en el navegador se activará la ventana de impresión/PDF."
                )
    
    
    
# =====================================================================
# PESTAÑA 5: FORMULARIO REACTIVO DE CARGA DE CONTRATOS (CORREGIDA)
# =====================================================================
    
if tab_carga:
    with tab_carga:
        st.subheader("Formulario de Registro Técnico del Contrato")
    
        dict_propiedades, dict_inquilinos = obtener_datos_desplegables()
            
        if not dict_propiedades or not dict_inquilinos:
            st.warning("⚠️ Módulo de carga bloqueado: Debe registrar al menos una Propiedad y un Inquilino en la pestaña '⚙️ Cargar Inquilinos / Propiedades' para poder generar un contrato.")
        else:
            permitir_edicion = st.toggle("🔒 Habilitar Formulario de Carga", value=False)
                
            if not permitir_edicion:
                st.info("Formulario protegido contra escrituras accidentales. Active el interruptor de arriba para editar.")
    
            # --- 1. SELECCIÓN DE ENTIDADES Y DATOS MAESTROS (PROCESO REACTIVO) ---
            st.markdown("### 1. Selección de Entidades y Datos Maestros")
            c1, c2, c3 = st.columns([2, 2, 1])
                
            lista_propiedades = list(dict_propiedades.keys())
            lista_inquilinos = list(dict_inquilinos.keys())
            estados_disponibles = ["Activo", "Finalizado", "Cancelado", "Revalorizado", "Vencido", "Inhabitado"]
    
            # 🔧 PASO 1: SELECCIONAR PROPIEDAD
            # IMPORTANTE: el selectbox de propiedad NUNCA se deshabilita,
            # para que Streamlit siempre detecte cambios y recargue los datos de la BD.
            propiedad_seleccionada = c1.selectbox(
                "Seleccione la Propiedad (Alias / Ubicación):", 
                lista_propiedades, 
                key="prop_sel_main"
            )
    
            # ✅ AHORA SÍ PODEMOS USAR propiedad_id
            propiedad_id = dict_propiedades[propiedad_seleccionada]
    
            # Inicializar estado de sesión de forma segura
            if "propiedad_activa" not in st.session_state:
                st.session_state.propiedad_activa = None
            if "datos_contrato" not in st.session_state:
                st.session_state.datos_contrato = None
    
            # Detectar cambio de propiedad para forzar recarga de datos desde la BD
            if st.session_state.propiedad_activa != propiedad_id:
                st.session_state.propiedad_activa = propiedad_id
                u = cargar_datos_iniciales_contrato(propiedad_id)
                st.session_state.datos_contrato = u
    
                # ══════════════════════════════════════════════════════════════
                # CRÍTICO: escribir los valores de la BD en el session_state de
                # cada widget. Streamlit ignora value= en rerenders si la key
                # ya existe — hay que sobrescribirla directamente.
                # ══════════════════════════════════════════════════════════════
                opciones_actualizacion_tmp = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24}
                indices_disponibles_tmp = ["ICL", "IPC", "UVA", "Otro"]
    
                if u:
                    # Inquilino y estado
                    if u.get("inquilino_id"):
                        inq_nombre = next((n for n, i in dict_inquilinos.items() if i == u["inquilino_id"]), None)
                        if inq_nombre:
                            st.session_state["inq_sel_main"] = inq_nombre
                    if u.get("estado") in estados_disponibles:
                        st.session_state["estado_sel_main"] = u["estado"]
                    # Sección 2 — Fechas
                    try:
                        from datetime import date as date_type
                        def parse_fecha(val):
                            """Intenta parsear una fecha; retorna None si el valor es inválido."""
                            if not val:
                                return None
                            try:
                                return date_type.fromisoformat(str(val))
                            except Exception:
                                return None
                        hoy = datetime.now().replace(day=1).date()
                        st.session_state["inicio_contrato_main"] = parse_fecha(u.get("inicio_contrato")) or hoy
                        st.session_state["fin_contrato_main"]    = parse_fecha(u.get("fin_contrato"))    or (hoy + dateutil.relativedelta.relativedelta(years=2))
                    except Exception:
                        pass
                    act_val_raw = str(u.get("act_contrato", "")).strip()
                    # La BD puede tener el número de meses ("4") o el texto ("Cuatrimestral")
                    # Construimos ambos mapeos para cubrir los dos casos
                    meses_a_texto = {str(v): k for k, v in opciones_actualizacion_tmp.items()}
                    if act_val_raw in opciones_actualizacion_tmp:
                        act_val = act_val_raw          # ya es texto: "Cuatrimestral"
                    elif act_val_raw in meses_a_texto:
                        act_val = meses_a_texto[act_val_raw]  # número → texto: "4" → "Cuatrimestral"
                    else:
                        act_val = "Semestral"
                    st.session_state["act_contrato_main"] = act_val
    
                    # Sección 3 — Valores económicos
                    st.session_state["monto_inicial_main"]       = float(u["monto_inicial"])   if u.get("monto_inicial")   is not None else 80000.0
                    st.session_state["alquiler_ultimo_main"]     = float(u["alquiler"])         if u.get("alquiler")         is not None else 80000.0
                    ind_val = u.get("indice", "ICL")
                    st.session_state["indice_sel_main"]          = ind_val if ind_val in indices_disponibles_tmp else "ICL"
                    mes_act = opciones_actualizacion_tmp.get(act_val, 6)
                    st.session_state["meses_atras_main"]         = int(u["mes_actualizacion_contrato"]) if u.get("mes_actualizacion_contrato") is not None else mes_act
                    alq_fmt = f"{float(u['alquiler']):,.2f}".replace(",", "v").replace(".", ",").replace("v", ".") if u.get("alquiler") is not None else "0,00"
                    st.session_state["alquiler_actualizado_main"] = alq_fmt
    
                    # Sección 4 — Honorarios
                    st.session_state["honorarios_pct_live"]      = float(u["honorarios"])        if u.get("honorarios")        is not None else 5.0
                    st.session_state["hon_inq_total_live"]       = float(u["monto_honorarios"]) if u.get("monto_honorarios") not in (None, 0, 0.0) else float(u.get("monto_inicial") or 80000.0)
                    st.session_state["cuota_hon_live"]           = max(1, int(u["cuota_honorarios"])) if u.get("cuota_honorarios") is not None else 1
                    st.session_state["hon_pagados_live"]         = float(u["honorarios_pagados"]) if u.get("honorarios_pagados") is not None else 0.0
    
                    # Sección 5 — Garantías
                    st.session_state["deposito_total_live_sec5"] = float(u["monto_garantia"]) if u.get("monto_garantia") not in (None, 0, 0.0) else float(u.get("monto_inicial") or 80000.0)
                    st.session_state["dep_pagados_live_sec5"]    = float(u["garantia_pagada"])   if u.get("garantia_pagada")   is not None else 0.0
                    tipos_garantia_tmp = ["Sin Garantía", "Propietario", "Recibo de Sueldo", "Bien Inmueble", "Aval Bancario", "Otro"]
                    val_tipo_tmp = u.get("tipo_de_garantie", "Sin Garantía")
                    st.session_state["tipo_garantia_live_sec5"]  = val_tipo_tmp if val_tipo_tmp in tipos_garantia_tmp else "Sin Garantía"
    
                    # Sección 6 — Servicios
                    st.session_state["edesal_live"]              = float(u["edesal"])            if u.get("edesal")            is not None else 0.0
                    st.session_state["gas_live"]                 = float(u["gas"])               if u.get("gas")               is not None else 0.0
                    st.session_state["municipalidad_live"]       = float(u["municipalidad"])     if u.get("municipalidad")     is not None else 0.0
                    st.session_state["ooss_live"]                = float(u["ooss"])              if u.get("ooss")              is not None else 0.0
                    st.session_state["expensas_live"]            = float(u["expensas"])          if u.get("expensas")          is not None else 0.0
                    st.session_state["cochera_live"]             = float(u["cochera"])           if u.get("cochera")           is not None else 0.0
                    st.session_state["imp_inmob_live"]           = float(u["imp_inmobiliario"])  if u.get("imp_inmobiliario")  is not None else 0.0
                else:
                    # Sin contrato previo: resetear todo a defaults
                    st.session_state["estado_sel_main"]           = "Activo"
                    hoy = datetime.now().replace(day=1).date()
                    st.session_state["inicio_contrato_main"]      = hoy
                    st.session_state["fin_contrato_main"]         = hoy + dateutil.relativedelta.relativedelta(years=2)
                    st.session_state["act_contrato_main"]         = "Semestral"
                    st.session_state["monto_inicial_main"]        = 80000.0
                    st.session_state["alquiler_ultimo_main"]      = 80000.0
                    st.session_state["indice_sel_main"]           = "ICL"
                    st.session_state["meses_atras_main"]          = 6
                    st.session_state["alquiler_actualizado_main"] = "80.000,00"
                    st.session_state["honorarios_pct_live"]       = 5.0
                    st.session_state["hon_inq_total_live"]        = 0.0
                    st.session_state["cuota_hon_live"]            = 1
                    st.session_state["hon_pagados_live"]          = 0.0
                    st.session_state["deposito_total_live_sec5"]  = 0.0
                    st.session_state["dep_pagados_live_sec5"]     = 0.0
                    st.session_state["edesal_live"]               = 0.0
                    st.session_state["gas_live"]                  = 0.0
                    st.session_state["municipalidad_live"]        = 0.0
                    st.session_state["ooss_live"]                 = 0.0
                    st.session_state["expensas_live"]             = 0.0
                    st.session_state["cochera_live"]              = 0.0
                    st.session_state["imp_inmob_live"]            = 0.0
    
                # Forzar rerender para que los widgets lean el session_state actualizado
                st.rerun()
    
            # Usamos 'u' como la fuente de datos cargada en el estado
            u = st.session_state.datos_contrato
    
    
            # 🔧 PASO 2: DETERMINAR ÍNDICE DEL INQUILINO PARA PRESELECCIONAR
            if u and 'dni_inquilino' in u:
                idx_inq = buscar_inquilino_por_id(u['dni_inquilino'], lista_inquilinos, dict_inquilinos)
            else:
                idx_inq = 0
    
            # 🔧 PASO 3: ÚNICO SELECTBOX DE INQUILINO (SIN DUPLICADOS)
            inquilino_seleccionada = c2.selectbox(
                "Seleccione el Inquilino (Apellido, Nombre):", 
                lista_inquilinos, 
                disabled=not permitir_edicion,
                key="inq_sel_main"
            )
    
            # Obtener ID del inquilino seleccionado
            inquilino_id = dict_inquilinos[inquilino_seleccionada]
    
            state_contrato = c3.selectbox(
                "Estado del Contrato:", 
                estados_disponibles,
                disabled=not permitir_edicion,
                key="estado_sel_main"
            )
    
            # Verificar si existe un contrato previo para esta propiedad
            contrato_previo = verificar_contrato_existente(propiedad_id)
            modo_guardado = "Crear Nuevo"
            id_contrato_a_modificar = None
    
            if contrato_previo:
                id_contrato_a_modificar = contrato_previo["codigo"]
                st.info(f"ℹ️ **Aviso:** Esta propiedad ya posee un contrato registrado (Código Interno: {id_contrato_a_modificar} - Estado: {contrato_previo['estado']}).")
                modo_guardado = st.radio(
                    "¿Qué acción desea realizar al guardar?",
                    ["Actualizar (Modificar el contrato existente)", "Crear uno nuevo (Nuevo Registro Histórico)"],
                    index=0,
                    disabled=not permitir_edicion
                )
                
            # --- 2. FECHAS, PLAZOS Y DURACIÓN ---
            fecha_primer_dia_actual = datetime.now().replace(day=1).date()
            fecha_primer_dia_vencimiento = fecha_primer_dia_actual + dateutil.relativedelta.relativedelta(years=2)
    
            st.markdown("### 2. Fechas, Plazos y Duración (Cálculos Dinámicos)")
            cf1, cf2 = st.columns(2)
            inicio_contrato = cf1.date_input(
                "Inicio del Contrato:", 
                value=fecha_primer_dia_actual, 
                format="DD/MM/YYYY", 
                disabled=not permitir_edicion,
                key="inicio_contrato_main"
            )
            fin_contrato = cf2.date_input(
                "Fin del Contrato:", 
                value=fecha_primer_dia_vencimiento, 
                format="DD/MM/YYYY", 
                disabled=not permitir_edicion,
                key="fin_contrato_main"
            )
    
            cf3, cf4, cf5 = st.columns([2, 1, 1])
            opciones_actualizacion = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24}
                
            act_contrato_seleccionado = cf3.selectbox(
                "Actualización Contrato (Frecuencia):", 
                list(opciones_actualizacion.keys()), 
                disabled=not permitir_edicion,
                key="act_contrato_main"
            )
            meses_a_sumar = opciones_actualizacion[act_contrato_seleccionado]
    
            fecha_hoy = datetime.now().date()
            prox_actualizacion_calculada = inicio_contrato + dateutil.relativedelta.relativedelta(months=meses_a_sumar)
    
            while prox_actualizacion_calculada < fecha_hoy and prox_actualizacion_calculada <= fin_contrato:
                prox_actualizacion_calculada += dateutil.relativedelta.relativedelta(months=meses_a_sumar)
    
            necesita_renovacion = prox_actualizacion_calculada > fin_contrato
    
            diferencia_hoy = dateutil.relativedelta.relativedelta(fecha_hoy, inicio_contrato)
            total_meses_transcurridos = (diferencia_hoy.years * 12) + diferencia_hoy.months
            if total_meses_transcurridos < 0: 
                total_meses_transcurridos = 0
            mes_actual_contrato_vivo = total_meses_transcurridos + 1
    
            es_mes_de_actualizacion = ((mes_actual_contrato_vivo - 1) % meses_a_sumar) == 0
    
            # Mostrar alertas de período
            if necesita_renovacion:
                st.error("🚨 Estado del Período: **RENOVAR** (La fecha de próxima actualización excede el fin del contrato)")
            elif es_mes_de_actualizacion:
                st.warning(f"⚠️ **AVISO:** Estás en el mes {mes_actual_contrato_vivo} de contrato. Según la frecuencia '{act_contrato_seleccionado}', **corresponde aplicar una actualización del monto** en este periodo.")
            else:
                st.info(f"Estado: Período normal (Mes {mes_actual_contrato_vivo}). No corresponde actualizar el alquiler este mes.")
    
            with cf4:
                if not necesita_renovacion:
                    st.date_input(
                        "Próxima Actualización:", 
                        value=prox_actualizacion_calculada, 
                        format="DD/MM/YYYY", 
                        disabled=True,
                    )
    
            diff_contrato = dateutil.relativedelta.relativedelta(fin_contrato, inicio_contrato)
            duracion_meses_calculada = (diff_contrato.years * 12) + diff_contrato.months
            if diff_contrato.days > 0 and fin_contrato.day != inicio_contrato.day:
                duracion_meses_calculada += 1
            cf5.text_input(
                "Duración del Contrato:", 
                value=f"{duracion_meses_calculada} meses", 
                disabled=True,
            )
    
            # --- 3. VALORES ECONÓMICOS E ÍNDICES ---
            st.markdown("### 3. Valores Económicos e Índices")
            cv1, cv2 = st.columns(2)
                
            # Valores con fallback seguro
            val_monto_ini = float(u['monto_inicial']) if u and u.get('monto_inicial') is not None else 80000.0
            val_alq_ult = float(u['alquiler']) if u and u.get('alquiler') not in (None, 0, 0.0) else val_monto_ini
                
            monto_inicial = cv1.number_input(
                "Monto Inicial ($):", 
                min_value=0.0, 
                step=5000.0, 
                value=val_monto_ini, 
                disabled=not permitir_edicion, 
                key="monto_inicial_main"
            )
            alquiler = cv2.number_input(
                "Último Valor Cobrado ($):", 
                min_value=0.0, 
                step=5000.0, 
                value=val_alq_ult, 
                disabled=not permitir_edicion, 
                key="alquiler_ultimo_main"
            )
                
            cv_ind, cv_meses = st.columns(2)
            indices_disponibles = ["ICL", "IPC", "UVA", "Otro"]
                
            indice_seleccionado = cv_ind.selectbox(
                "Índice Aplicado:", 
                indices_disponibles, 
                disabled=not permitir_edicion,
                key="indice_sel_main"
            )
            meses_atras = cv_meses.number_input(
                "Intervalo de Meses para Ajustar:", 
                min_value=1, 
                max_value=24, 
                value=int(meses_a_sumar), 
                disabled=not permitir_edicion,
                key="meses_atras_main"
            )
                
            indice_final = st.text_input(
                "Especifique el Índice personalizado:", 
                value=u['indice'] if u and indice_seleccionado == "Otro" else "", 
                placeholder="Ej: Ajuste Fijo", 
                disabled=not permitir_edicion if indice_seleccionado == "Otro" else True,
                key="indice_custom_main"
            ) if indice_seleccionado == "Otro" else indice_seleccionado
    
            codigo_rate = indice_final.lower()
            fecha_param_str = inicio_contrato.strftime("%Y-%m-%d")
            url_calculo_dinamica = f"https://arquiler.com/pwa?amount={int(monto_inicial)}&date={fecha_param_str}&months={meses_atras}&rate={codigo_rate}"
                
            c_web1, c_web2, c_web3 = st.columns([2, 2, 2])
            c_web1.markdown(f"🔗 [Abrir panel en arquiler.com]({url_calculo_dinamica})")
    
            # ── AUTO-CÁLCULO ICL / IPC ────────────────────────────────────────────
            valor_auto = None
            indice_upper = indice_final.upper()
    
            if permitir_edicion and indice_upper in ("ICL", "IPC"):
                with st.spinner(f"⏳ Consultando {indice_upper}..."):
                    if indice_upper == "ICL":
                        valor_auto = calcular_valor_actualizado_icl(
                            monto_inicial, inicio_contrato, int(meses_atras)
                        )
                    elif indice_upper == "IPC":
                        valor_auto = calcular_valor_actualizado_ipc(
                            monto_inicial, inicio_contrato, int(meses_atras)
                        )
    
            if valor_auto is not None:
                valor_auto_fmt = f"$ {valor_auto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                c_web2.metric(
                    label=f"📡 Auto {indice_upper} (oficial)",
                    value=valor_auto_fmt,
                    help=f"Calculado automáticamente usando datos oficiales del {'BCRA' if indice_upper == 'ICL' else 'INDEC'}."
                )
                valor_por_defecto_fmt = f"{valor_auto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                if permitir_edicion and indice_upper in ("ICL", "IPC"):
                    fuente_c = "BCRA" if indice_upper == "ICL" else "INDEC"
                    c_web2.warning(
                        f"⚠️ No se pudo obtener el índice desde {fuente_c}. "
                        "Ingresá el valor manualmente o verificá en arquiler.com (↖)."
                    )
                    if c_web2.button("🔄 Reintentar", key="retry_indice_carga"):
                        _obtener_icl_bcra_xls.clear()
                        _obtener_ipc_indec.clear()
                        st.rerun()
                valor_por_defecto_fmt = f"{alquiler:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
            alquiler_actualizado_texto = c_web3.text_input(
                "Valor Actualizado ($):",
                value=valor_por_defecto_fmt,
                key="alquiler_actualizado_main",
                disabled=not permitir_edicion,
                help="Auto-completado con el índice oficial. Podés ajustarlo manualmente."
            )
    
            alquiler_actualizado = limpiar_string_a_float(alquiler_actualizado_texto)
                
            valor_vacio = (alquiler_actualizado is None or alquiler_actualizado <= 0.0)
            alquiler_sin_cambios = (alquiler_actualizado == alquiler)
                
            bloqueo_por_actualizacion = False
            if needs_renov_status := (necesita_renovacion or valor_vacio):
                bloqueo_por_actualizacion = True
            elif es_mes_de_actualizacion and alquiler_sin_cambios:
                bloqueo_por_actualizacion = True
    
            if necesita_renovacion:
                st.error("🚨 Estado del Período: **RENOVAR** (La fecha de próxima actualización excede el fin del contrato)")
            elif valor_vacio:
                st.error("❌ **Error:** El 'Valor Actualizado obtenido' debe ser un número positivo mayor a 0.")
            elif es_mes_de_actualizacion and alquiler_sin_cambios:
                st.warning(f"⚡ **MES DE ACTUALIZACIÓN (Mes {mes_actual_contrato_vivo})**: Debe ingresar un valor distinto al anterior ($ {alquiler:,.2f}) para poder guardar.")
            elif es_mes_de_actualizacion and not alquiler_sin_cambios:
                st.success(f"✅ **Mes de actualización:** Nuevo valor confirmado ($ {alquiler_actualizado:,.2f}).")
            else:
                st.info(f"Estado: Período normal (Mes {mes_actual_contrato_vivo}).")
    
     
            # --- 4. LIQUIDACIÓN DE IMPORTES DE AGENCIA ---
            st.markdown("### 4. Liquidación de Importes de Agencia")
            with st.container(border=True):
                st.markdown("##### **A) COMISION INMOBILIARIA (A cargo del Propietario - Retención Mensual)**")
                ch_prop1, ch_prop2 = st.columns(2)
                val_hon_pct = float(u['honorarios']) if u and u.get('honorarios') is not None else 5.0
                honorarios_pct = ch_prop1.number_input("Porcentaje de Administración (%):", min_value=0.0, value=val_hon_pct, step=0.5, disabled=not permitir_edicion, key="honorarios_pct_live")
                    
                retencion_mensual_estimated = alquiler_actualizado * (honorarios_pct / 100.0) if not valor_vacio else 0.0
                ret_mensual_fmt = f"$ {retencion_mensual_estimated:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                ch_prop2.text_input("Retención mensual calculada ($):", value=ret_mensual_fmt, disabled=True, key="retencion_mensual_live")
                
            with st.container(border=True):
                st.markdown("##### **B) HONORARIOS INMOBILIARIA (A cargo del Inquilino - Comisión de Contrato)**")
                ch_inq1, ch_inq2, ch_inq3 = st.columns(3)
                    
                # Default: si no hay valor guardado, usar monto_inicial como base
                val_hon_total = float(u['monto_honorarios']) if u and u.get('monto_honorarios') not in (None, 0, 0.0) else float(monto_inicial)
                honorarios_inquilino_total = ch_inq1.number_input(
                    "Monto Total de Comisión ($):", 
                    min_value=0.0, 
                    value=val_hon_total, 
                    step=5000.0, 
                    disabled=not permitir_edicion, 
                    key="hon_inq_total_live"
                )
                    
                val_cuotas_hon = int(u['cuota_honorarios']) if u and u.get('cuota_honorarios') is not None else 1
                cuota_honorarios = ch_inq2.number_input(
                    "Cuotas pactadas para el pago:", 
                    min_value=1, 
                    value=max(1, val_cuotas_hon),
                    step=1, 
                    disabled=not permitir_edicion, 
                    key="cuota_hon_live"
                )
    
                # Valor calculado por cuota
                valor_por_cuota = honorarios_inquilino_total / cuota_honorarios if cuota_honorarios > 0 else 0.0
                valor_por_cuota_fmt = f"$ {valor_por_cuota:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                ch_inq3.number_input(
                    "Valor por cuota ($):", 
                    value=valor_por_cuota, 
                    disabled=True, 
                    key="valor_cuota_hon_live"
                )
    
                val_hon_pagados = float(u['honorarios_pagados']) if u and u.get('honorarios_pagados') is not None else 0.0
                honorarios_pagados = st.number_input(
                    "Monto pagado a la fecha ($):", 
                    min_value=0.0, 
                    value=val_hon_pagados, 
                    step=5000.0, 
                    disabled=not permitir_edicion, 
                    key="hon_pagados_live"
                )
    
                val_cuotas_hon_pagas = int(u['cuotas_honorarios_pagadas']) if u and u.get('cuotas_honorarios_pagadas') is not None else 0
                cuotas_honorarios_pagadas = st.number_input(
                    "Cuotas de honorarios pagadas:",
                    min_value=0,
                    max_value=int(cuota_honorarios),
                    value=min(val_cuotas_hon_pagas, int(cuota_honorarios)),
                    step=1,
                    disabled=not permitir_edicion,
                    key="cuotas_hon_pagas_live"
                )
                    
                saldo_inquilino_hon = honorarios_inquilino_total - honorarios_pagados
                if saldo_inquilino_hon > 0:
                    cuotas_pendientes = saldo_inquilino_hon / valor_por_cuota if valor_por_cuota > 0 else 0
                    saldo_hon_fmt = f"$ {saldo_inquilino_hon:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                    st.warning(f"💵 Saldo pendiente: **{saldo_hon_fmt}** — {cuotas_pendientes:.1f} cuota(s) de {valor_por_cuota_fmt} c/u.")
    
            # --- 5. RESPALDO Y GARANTÍAS DEL CONTRATO ---
            st.markdown("### 5. Respaldo y Garantías del Contrato")
            st.markdown("##### **A) Respaldo con Documento Pagaré**")
            cg_pag1, cg_pag2 = st.columns(2)
                
            # Verificación en el diccionario
            tiene_pag_idx = 1 if u and "Sí" in str(u.get('garantia', '')) else 0
            tiene_pagare = cg_pag1.selectbox("¿Aplica Pagaré firmado?:", ["No", "Sí"], index=tiene_pag_idx, disabled=not permitir_edicion, key="tiene_pagare_live_sec5")
            monto_pagare = cg_pag2.number_input("Monto acordado del Pagaré ($):", min_value=0.0, value=0.0, step=10000.0, disabled=not permitir_edicion if tiene_pagare == "Sí" else True, key="monto_pagare_live_sec5")
    
            # Tipo de garantía
            tipos_garantia = ["Sin Garantía", "Propietario", "Recibo de Sueldo", "Bien Inmueble", "Aval Bancario", "Otro"]
            val_tipo_garantia = u.get("tipo_de_garantie", "Sin Garantía") if u else "Sin Garantía"
            idx_tipo_gar = tipos_garantia.index(val_tipo_garantia) if val_tipo_garantia in tipos_garantia else 0
            tipo_de_garantie = st.selectbox("Tipo de Garantía:", tipos_garantia, index=idx_tipo_gar, disabled=not permitir_edicion, key="tipo_garantia_live_sec5")
    
            with st.container(border=True):
                st.markdown("##### **C) DEPÓSITO DE RESPALDO / GARANTÍA (A cargo del Inquilino)**")
                ch_dep1, ch_dep2, ch_dep3 = st.columns(3)
                    
                # Default: si no hay valor guardado, usar monto_inicial como base
                val_deposito_total = float(u['monto_garantia']) if u and u.get('monto_garantia') not in (None, 0, 0.0) else float(monto_inicial)
                monto_deposito_total = ch_dep1.number_input(
                    "Monto Total de Depósito Pactado ($):", 
                    min_value=0.0, 
                    value=val_deposito_total, 
                    step=5000.0, 
                    disabled=not permitir_edicion, 
                    key="deposito_total_live_sec5"
                )
    
                val_cuotas_dep = int(u.get('cuotas_deposito', 1)) if u and u.get('cuotas_deposito') not in (None, 0) else 1
                cuotas_deposito = ch_dep2.number_input(
                    "Cuotas pactadas para el pago:", 
                    min_value=1, 
                    value=max(1, val_cuotas_dep), 
                    step=1, 
                    disabled=not permitir_edicion, 
                    key="cuotas_dep_live_sec5"
                )
    
                # Valor calculado por cuota
                valor_por_cuota_dep = monto_deposito_total / cuotas_deposito if cuotas_deposito > 0 else 0.0
                valor_por_cuota_dep_fmt = f"$ {valor_por_cuota_dep:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                ch_dep3.number_input(
                    "Valor por cuota ($):", 
                    value=valor_por_cuota_dep, 
                    disabled=True, 
                    key="valor_cuota_dep_live"
                )
    
                val_deposito_pagado = float(u['garantia_pagada']) if u and u.get('garantia_pagada') is not None else 0.0
                deposito_pagados = st.number_input(
                    "Monto de Depósito Reintegrado / Pagado a la fecha ($):", 
                    min_value=0.0, 
                    value=val_deposito_pagado, 
                    step=5000.0, 
                    disabled=not permitir_edicion, 
                    key="dep_pagados_live_sec5"
                )
    
                val_cuotas_dep_pagas = int(u['cuotas_deposito_pagadas']) if u and u.get('cuotas_deposito_pagadas') is not None else 0
                cuotas_deposito_pagadas = st.number_input(
                    "Cuotas de depósito pagadas:",
                    min_value=0,
                    max_value=int(cuotas_deposito),
                    value=min(val_cuotas_dep_pagas, int(cuotas_deposito)),
                    step=1,
                    disabled=not permitir_edicion,
                    key="cuotas_dep_pagas_live"
                )
                    
                saldo_inquilino_dep = max(0.0, monto_deposito_total - deposito_pagados)
                    
                if saldo_inquilino_dep <= 0 and monto_deposito_total > 0:
                    estado_garantia_calculado = "Depositada Completa"
                    st.success("✅ Depósito de respaldo: **abonado en su totalidad.**")
                elif monto_deposito_total == 0:
                    estado_garantia_calculado = "Sin Depósito"
                else:
                    saldo_dep_fmt = f"$ {saldo_inquilino_dep:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                    cuotas_pendientes_dep = saldo_inquilino_dep / valor_por_cuota_dep if valor_por_cuota_dep > 0 else 0
                    estado_garantia_calculado = f"Financiando (Saldo: {saldo_dep_fmt})"
                    st.warning(f"💵 Saldo pendiente: **{saldo_dep_fmt}** — {cuotas_pendientes_dep:.1f} cuota(s) de {valor_por_cuota_dep_fmt} c/u.")
    
            # --- 6. DESGLOSE DE SERVICIOS MENSUALES ($) ---
            st.markdown("### 6. Desglose de Servicios Mensuales ($)")
                
            with st.container(border=True):
                st.markdown("##### **⚡ / 🔥 / 💧 / 🏛️ Servicios Públicos y Municipales**")
                g1_col1, g1_col2 = st.columns(2)
                    
                with g1_col1:
                    with st.container():
                        s_col5, s_col6 = st.columns([3, 2])
                        val_ede = float(u['edesal']) if u and u.get('edesal') is not None else 0.0
                        edesal = s_col5.number_input("Monto Electricidad ($):", min_value=0.0, value=val_ede, step=500.0, disabled=not permitir_edicion, key="edesal_live")
                        cargo_electricidad = s_col6.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_elec", disabled=not permitir_edicion)
                        num_nis = st.number_input("NIS Nro:", min_value=0, value=0, step=1, key="id_nis", disabled=not permitir_edicion)
                        
                    st.markdown("---")
                    with st.container():
                        s_col7, s_col8 = st.columns([3, 2])
                        val_gas = float(u['gas']) if u and u.get('gas') is not None else 0.0
                        gas = s_col7.number_input("Monto Gas ($):", min_value=0.0, value=val_gas, step=500.0, disabled=not permitir_edicion, key="gas_live")
                        cargo_gas = s_col8.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_gas", disabled=not permitir_edicion)
                        cuenta_gas = st.text_input("Nro de Cuenta (Gas):", key="id_cta_gas", disabled=not permitir_edicion)
                            
                with g1_col2:
                    with st.container():
                        s_col9, s_col10 = st.columns([3, 2])
                        val_mun = float(u['municipalidad']) if u and u.get('municipalidad') is not None else 0.0
                        municipalidad = s_col9.number_input("Monto Municipalidad ($):", min_value=0.0, value=val_mun, step=500.0, disabled=not permitir_edicion, key="municipalidad_live")
                        cargo_municipalidad = s_col10.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_mun", disabled=not permitir_edicion)
                        finca_mun = st.text_input("Finca Nro:", key="id_finca_mun", disabled=not permitir_edicion)
                        
                    st.markdown("---")
                    with st.container():
                        s_col11, s_col12 = st.columns([3, 2])
                        val_oos = float(u['ooss']) if u and u.get('ooss') is not None else 0.0
                        ooss = s_col11.number_input("Monto OO.SS. ($):", min_value=0.0, value=val_oos, step=500.0, disabled=not permitir_edicion, key="ooss_live")
                        cargo_ooss = s_col12.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_oos", disabled=not permitir_edicion)
                        cuenta_oos = st.text_input("Nro de Cuenta (OO.SS.):", key="id_cta_oos", disabled=not permitir_edicion)
    
            with st.container(border=True):
                st.markdown("##### **🏢 Complementos de Propiedad y Consorcio**")
                g2_col1, g2_col2 = st.columns(2)
                    
                with g2_col1:
                    s_col3, s_col4 = st.columns([3, 2])
                    val_exp = float(u['expensas']) if u and u.get('expensas') is not None else 0.0
                    expensas = s_col3.number_input("Monto Expensas ($):", min_value=0.0, value=val_exp, step=500.0, disabled=not permitir_edicion, key="expensas_live")
                    cargo_expensas = s_col4.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_exp", disabled=not permitir_edicion)
                        
                with g2_col2:
                    s_col13, s_col14 = st.columns([3, 2])
                    val_coch = float(u['cochera']) if u and u.get('cochera') is not None else 0.0
                    cochera = s_col13.number_input("Monto Cochera ($):", min_value=0.0, value=val_coch, step=1000.0, disabled=not permitir_edicion, key="cochera_live")
                    cargo_cochera = s_col14.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_coch", disabled=not permitir_edicion)
    
            with st.container(border=True):
                st.markdown("##### **📌 Impuesto Provincial Individual**")
                s_col1, s_col2 = st.columns([3, 2])
                val_imp_inmob = float(u['imp_inmobiliario']) if u and u.get('imp_inmobiliario') is not None else 0.0
                imp_inmobiliario = s_col1.number_input("Imp. Inmobiliario ($):", min_value=0.0, value=val_imp_inmob, step=500.0, disabled=not permitir_edicion, key="imp_inmob_live")
                cargo_inmobiliario = s_col2.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=1, key="cargo_inmob", disabled=not permitir_edicion)
    
            notas_adicionales_input = st.text_input("Notas Adicionales de Servicios:", disabled=not permitir_edicion, key="notas_servicios_live")
                
            str_identificadores = f"[NIS: {num_nis}] [Cta Gas: {cuenta_gas}] [Finca: {finca_mun}] [Cta OO.SS.: {cuenta_oos}]"
            detalles_pagos_str = f"| Elec: {cargo_electricidad} | Gas: {cargo_gas} | Mun: {cargo_municipalidad} | OOSS: {cargo_ooss} | Exp: {cargo_expensas} | Inmob: {cargo_inmobiliario}"
                
            if notas_adicionales_input.strip():
                servicios_detalle = f"{str_identificadores} {detalles_pagos_str} | Notas: {notas_adicionales_input}"
            else:
                servicios_detalle = f"{str_identificadores} {detalles_pagos_str}"
    
            m_inmob_liq = imp_inmobiliario if cargo_inmobiliario == "Inquilino" else 0.0
            m_exp_liq = expensas if cargo_expensas == "Inquilino" else 0.0
            m_elec_liq = edesal if cargo_electricidad == "Inquilino" else 0.0
            m_gas_liq = gas if cargo_gas == "Inquilino" else 0.0
            m_mun_liq = municipalidad if cargo_municipalidad == "Inquilino" else 0.0
            m_oos_liq = ooss if cargo_ooss == "Inquilino" else 0.0
            m_coch_liq = cochera if cargo_cochera == "Inquilino" else 0.0
                
            servicios_total_calculado = (m_inmob_liq + m_exp_liq + m_elec_liq + m_gas_liq + m_mun_liq + m_oos_liq + m_coch_liq)
    
            # --- 7. CONSOLIDACIÓN DEL PAGO DE ALQUILER INICIAL (CÁLCULO DINÁMICO) ---
            st.markdown("### 7. Consolidación del Pago de Alquiler Inicial")
            cp_1, cp_2, cp_3 = st.columns(3)
                
            base_calculo_cobro = float(alquiler_actualizado) if not valor_vacio else 0.0
                
            alquiler_cobrado = cp_1.number_input(
                "Monto Neto de Alquiler Cobrado ($):", 
                min_value=0.0, 
                value=base_calculo_cobro, 
                step=5000.0, 
                disabled=True,
                key="alquiler_cobrado_live"
            )
                
            total_pagado_calculado = alquiler_cobrado + servicios_total_calculado
                
            cp_2.number_input("Total de Servicios Adicionados ($):", value=float(servicios_total_calculado), disabled=True, key="box_total_servicios_live")
            cp_3.number_input("TOTAL CONSOLIDADO COBRADO (Caja) ($):", value=float(total_pagado_calculado), disabled=True, key="box_total_caja_live")
    
                
            # --- BOTÓN GUARDAR FINAL ---
            st.markdown("---")
                
            boton_deshabilitado = (not permitir_edicion) or bloqueo_por_actualizacion or necesita_renovacion
            texto_boton = "💾 Actualizar Contrato Existente" if (contrato_previo and "Actualizar" in modo_guardado) else "💾 Guardar y Registrar Contrato Completo"
                
            btn_guardar_final = st.button(texto_boton, disabled=boton_deshabilitado, type="primary", key="btn_guardar_contrato_final_main")
                
    
                    
                
            if btn_guardar_final:
                alq_act_fmt = f"${alquiler_actualizado:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                m_pag_fmt = f"${monto_pagare:,.0f}".replace(",", "v").replace(".", ",").replace("v", ".")
                    
                detalle_garantia_unificado = f"Pagaré: {tiene_pagare} ({m_pag_fmt}) | Depósito: {estado_garantia_calculado}"
                registro_distribucion = f"[Alq.Actualizado: {alq_act_fmt} | Imp.Inmob: {cargo_inmobiliario}] {servicios_detalle}".strip()
                    
                inicio_str = inicio_contrato.strftime('%d/%m/%Y')
                fin_str = fin_contrato.strftime('%d/%m/%Y')
                prox_act_str = prox_actualizacion_calculada.strftime('%d/%m/%Y')
                meses_atras_calculado = meses_atras
                    
                conn = conectar_db()
                cursor = conn.cursor()
                try:
                    _eid_c = st.session_state.get("empresa_id", 0)
                    # Resolver alias y dni desde los IDs del selector
                    cursor.execute("SELECT alias_propiedad FROM propiedades WHERE id = %s AND empresa_id = %s", (propiedad_id, _eid_c))
                    _pr = cursor.fetchone()
                    _alias_prop = _pr["alias_propiedad"] if _pr else ""
                    cursor.execute("SELECT dni FROM inquilinos WHERE id = %s AND empresa_id = %s", (inquilino_id, _eid_c))
                    _ir = cursor.fetchone()
                    _dni_inq = _ir["dni"] if _ir else ""

                    if contrato_previo and "Actualizar" in modo_guardado:
                        cursor.execute('''
                            UPDATE contratos 
                            SET alias_propiedad=%s, dni_inquilino=%s,
                                estado=%s, inicio_contrato=%s, fin_contrato=%s,
                                calc_duracion=%s, act_contrato=%s, indice=%s, monto_inicial=%s, alquiler=%s, prox_actualizacion=%s,
                                mes_contrato=%s, mes_actualizacion_contrato=%s, servicios=%s, honorarios=%s, monto_honorarios=%s,
                                cuota_honorarios=%s, honorarios_pagados=%s, cuotas_honorarios_pagadas=%s,
                                tipo_de_garantie=%s, monto_garantia=%s, garantia=%s, garantia_pagada=%s,
                                cuotas_deposito=%s, cuotas_deposito_pagadas=%s,
                                imp_inmobiliario=%s, expensas=%s, edesal=%s, gas=%s, municipalidad=%s, ooss=%s, servicios_total=%s,
                                cochera=%s, alquiler_cobrado=%s, total_pagado=%s
                            WHERE codigo = %s AND empresa_id = %s
                        ''', (
                            _alias_prop, _dni_inq, state_contrato, inicio_str, fin_str,
                            duracion_meses_calculada, act_contrato_seleccionado, indice_final, monto_inicial, alquiler, prox_act_str,
                            mes_actual_contrato_vivo, meses_atras_calculado, registro_distribucion, honorarios_pct, retencion_mensual_estimated,
                            cuota_honorarios, honorarios_pagados, cuotas_honorarios_pagadas,
                            tipo_de_garantie, monto_deposito_total, detalle_garantia_unificado, deposito_pagados,
                            cuotas_deposito, cuotas_deposito_pagadas,
                            imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, servicios_total_calculado,
                            cochera, alquiler_cobrado, total_pagado_calculado,
                            id_contrato_a_modificar, _eid_c
                        ))
                        st.success(f"✔️ ¡Contrato N° {id_contrato_a_modificar} actualizado correctamente!")
    
                    else:
                        if state_contrato == "Activo":
                            cursor.execute('''
                                UPDATE contratos 
                                SET estado = 'Finalizado' 
                                WHERE alias_propiedad = %s AND empresa_id = %s AND estado = 'Activo'
                            ''', (_alias_prop, _eid_c))
                            
                        cursor.execute('''
                            INSERT INTO contratos (
                                empresa_id, alias_propiedad, dni_inquilino, estado, inicio_contrato, fin_contrato,
                                calc_duracion, act_contrato, indice, monto_inicial, alquiler, prox_actualizacion,
                                mes_contrato, mes_actualizacion_contrato, servicios, honorarios, monto_honorarios,
                                cuota_honorarios, honorarios_pagados, cuotas_honorarios_pagadas,
                                tipo_de_garantie, monto_garantia, garantia, garantia_pagada,
                                cuotas_deposito, cuotas_deposito_pagadas,
                                imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, servicios_total,
                                cochera, alquiler_cobrado, total_pagado
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            _eid_c, _alias_prop, _dni_inq, state_contrato, inicio_str, fin_str,
                            duracion_meses_calculada, act_contrato_seleccionado, indice_final, monto_inicial, alquiler, prox_act_str,
                            mes_actual_contrato_vivo, meses_atras_calculado, registro_distribucion, honorarios_pct, retencion_mensual_estimated,
                            cuota_honorarios, honorarios_pagados, cuotas_honorarios_pagadas,
                            tipo_de_garantie, monto_deposito_total, detalle_garantia_unificado, deposito_pagados,
                            cuotas_deposito, cuotas_deposito_pagadas,
                            imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, servicios_total_calculado,
                            cochera, alquiler_cobrado, total_pagado_calculado
                        ))
                        st.success("✔️ ¡Nuevo contrato creado e insertado con éxito!")
    
                    conn.commit()
                    # Actualización del session_state post-guardado para mantener consistencia general
                    st.session_state.ultimo_contrato = obtener_ultimo_contrato()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error de base de datos al impactar los cambios: {e}")
                finally:
                    conn.close()
    
# =====================================================================
# PESTAÑA 6: CARGA DE AUXILIARES (INQUILINOS / PROPIEDADES)
# =====================================================================
if tab_auxiliares:
        with tab_auxiliares:
            st.subheader("⚙️ Panel de Configuración de Entidades")
                
            sub_tab1, sub_tab2 = st.tabs(["👤 Nuevo Inquilino", "🏠 Nueva Propiedad"])
                
            with sub_tab1:
                st.markdown("#### Registrar Nuevo Inquilino")
                with st.form("form_inquilino", clear_on_submit=True):
                    apellidos = st.text_input("Apellidos:")
                    nombres = st.text_input("Nombres:")
                    dni = st.text_input("DNI (Sin puntos):")
                    email = st.text_input("Email:")
                    tel = st.text_input("Teléfono:")
                        
                    btn_inq = st.form_submit_button("Guardar Inquilino")
                        
                    if btn_inq:
                        if not apellidos or not nombres:
                            st.error("Apellidos y Nombres son obligatorios.")
                        else:
                            conn = conectar_db()
                            try:
                                cursor = conn.cursor()
                                cursor.execute('''
                                    INSERT INTO inquilinos (empresa_id, apellidos, nombres, dni, telefono, email)
                                    VALUES (%s, %s, %s, %s, %s)
                                ''', (apellidos.strip(), nombres.strip(), dni.strip() or None, tel.strip() or None, email.strip() or None))
                                conn.commit()
                                st.success(f"✅ Inquilino '{apellidos}, {nombres}' guardado correctamente.")
                            except psycopg2.errors.UniqueViolation:
                                st.error("⚠️ Ya existe un inquilino con ese DNI o con el mismo apellido y nombre.")
                            except Exception as e:
                                st.error(f"Error al guardar el inquilino: {e}")
                            finally:
                                conn.close()
    
            with sub_tab2:
                st.markdown("📝 Registrar Nueva Propiedad")
                with st.form("form_propiedad", clear_on_submit=True):
                    alias = st.text_input("Alias de la Propiedad:")
                    calle = st.text_input("Calle / Av:")
                    numero = st.text_input("Número:")
                    depto = st.text_input("Departamento:")
                    propietario = st.text_input("Nombre del Propietario:")
                    ciudad = st.text_input("Ciudad:")
                    provincia = st.text_input("Provincia:")
                    tipo = st.text_input("Características:")
                        
                    col1, col2 = st.columns(2)
                    nis = col1.text_input("NIS Nro:")
                    cuenta_gas = col2.text_input("Cuenta Nro (GAS):")
                        
                    col3, col4 = st.columns(2)
                    finca = col3.text_input("Finca Nro:")
                    cuenta_ooss = col4.text_input("Cuenta Nro (OO.SS):")
                        
                    nro_padron = st.text_input("Nro Padrón:")
                        
                    btn_prop = st.form_submit_button("Guardar Propiedad")
                        
                    if btn_prop:
                        if not alias or not calle or not numero:
                            st.warning("Completa los campos obligatorios.")
                        else:
                            conn = conectar_db()
                            try:
                                cursor = conn.cursor()
                                cursor.execute('''
                                    INSERT INTO propiedades (empresa_id, alias_propiedad, calle, numero, departamento, propietario, 
                                                            ciudad, provincia, tipo, nis, cuenta_gas, finca, cuenta_ooss, nro_padron) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ''', (alias, calle, numero, depto, propietario, ciudad, provincia, tipo, 
                                      nis, cuenta_gas, finca, cuenta_ooss, nro_padron))
                                conn.commit()
                                st.success("Propiedad guardada.")
                            except Exception as e:
                                st.error(f"Error: {e}")
                            finally:
                                conn.close()
    
    
    
            # =====================================================================
            # MÓDULO DE EDICIÓN / MODIFICACIÓN DE DATOS EXISTENTES
            # =====================================================================
            st.markdown("---")
            st.markdown("### 🔄 Modificar Datos de Inquilinos o Propiedades Existentes")
    
            # Consultamos los desplegables actualizados del sistema
            dict_propiedades_edit, dict_inquilinos_edit = obtener_datos_desplegables()
    
            # AQUÍ HACEMOS LA SEPARACIÓN EN PESTAÑAS
            tab_edit_inq, tab_edit_prop = st.tabs(["👤 Editar Inquilino", "🏠 Editar Propiedad"])
    
            # --- PESTAÑA DE INQUILINOS ---
            with tab_edit_inq:
                if not dict_inquilinos_edit:
                    st.info("No hay inquilinos registrados para editar.")
                else:
                    inquilino_a_editar = st.selectbox("Seleccione el Inquilino a modificar:", list(dict_inquilinos_edit.keys()), key="select_inq_edit_tab")
                    id_inq_edit = dict_inquilinos_edit[inquilino_a_editar]
                        
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute("SELECT apellidos, nombres, dni, telefono, email FROM inquilinos WHERE id = %s", (id_inq_edit,))
                    datos_inq = cursor.fetchone()
                    conn.close()
                        
                    if datos_inq:
                        crear_formulario_editar_inquilino(id_inq_edit, datos_inq)
    
            # --- PESTAÑA DE PROPIEDADES ---
            with tab_edit_prop:
                if not dict_propiedades_edit:
                    st.info("No hay propiedades registradas para editar.")
                else:
                    propiedad_a_editar = st.selectbox("Seleccione la Propiedad a modificar:", list(dict_propiedades_edit.keys()), key="select_prop_edit_tab")
                    id_prop_edit = dict_propiedades_edit[propiedad_a_editar]
                        
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute("SELECT alias_propiedad, calle, numero, departamento FROM propiedades WHERE id = %s", (id_prop_edit,))
                    datos_prop = cursor.fetchone()
                    conn.close()
                        
                    if datos_prop:
                        crear_formulario_editar_propiedad(id_prop_edit, datos_prop)
    
# =====================================================================
# PESTAÑA 7: PANEL DE GESTIÓN (DINÁMICO PARA SUPERADMIN Y ADMIN DE EMPRESA)
# =====================================================================
if tab_superadmin:
    with tab_superadmin:
        rol_sesion = st.session_state.get("rol")
            
        if rol_sesion == "superadmin":
            st.subheader("👑 Panel de Control Global (SuperAdmin)")
        else:
            st.subheader(f"🏢 Panel de Administración — {st.session_state.get('nombre_empresa', 'Mi Empresa')}")
            
        # 1. Definición de subpestañas dinámicas según el rol de la sesión
        lista_subtabs = ["👤 Crear Usuarios", "🔐 Editar Permisos"]
        if rol_sesion == "superadmin":
            lista_subtabs.append("🚀 Importar / Exportar Datos (CSV)")
                
        subtabs_objetos = st.tabs(lista_subtabs)
        subtab_usuarios = subtabs_objetos[0]
        subtab_permisos = subtabs_objetos[1]
        if rol_sesion == "superadmin":
            subtab_csv = subtabs_objetos[2]
                
        # =====================================================================
        # SUBPESTAÑA 1: CREACIÓN DE USUARIOS (Adaptada dinámicamente)
        # =====================================================================
        with subtab_usuarios:
            st.markdown("#### Registrar nuevo usuario en el sistema")
                
            with st.form("form_crear_usuario", clear_on_submit=True):
                st.markdown("#### ➕ Formulario de Alta de Operadores")
                    
                new_username = st.text_input("Nombre de Usuario (Login):").strip()
                new_password = st.text_input("Contraseña:", type="password")
                    
                col_name1, col_name2 = st.columns(2)
                new_apellidos = col_name1.text_input("Apellidos:")
                new_nombres = col_name2.text_input("Nombres:")
                    
                # Control visual y restricción de datos según el rol
                if rol_sesion == "admin":
                    new_empresa = st.text_input("Nombre de la Empresa:", value=st.session_state.get("nombre_empresa"), disabled=True)
                    new_rol = st.selectbox("Rol del Usuario:", ["user", "propietario"])
                else:
                    new_empresa = st.text_input("Nombre de la Empresa / Inmobiliaria:").strip()
                    new_rol = st.selectbox("Rol del Usuario:", ["user", "propietario", "admin", "superadmin"])
                    
                btn_crear_user = st.form_submit_button("➕ Crear Usuario", type="primary")
                    
                if btn_crear_user:
                    if new_username and new_password and new_empresa and new_apellidos and new_nombres:
                            
                        try:
                            conn = conectar_db_central()
                            cursor = conn.cursor()
                                
                            # Determinar el directorio y el archivo de base de datos de destino
                            if rol_sesion == "admin":
                                # Si es un admin de empresa, heredamos de forma estricta su base de datos actual
                                ruta_db_completa = st.session_state.get("empresa_db")
                                nombre_directorio = os.path.dirname(ruta_db_completa)
                            else:
                                # Si es superadmin y crea una empresa nueva:
                                token_carpeta = secrets.token_hex(8)
                                nombre_directorio = token_carpeta  
                                nombre_archivo_final = "data.db"
                                ruta_db_completa = os.path.join(nombre_directorio, nombre_archivo_final)
    
                            # Asegurar la existencia física del directorio
                            if nombre_directorio and not os.path.exists(nombre_directorio):
                                os.makedirs(nombre_directorio, exist_ok=True)
                                st.info(f"📁 Directorio seguro creado de forma física en el servidor.")
                                
                            # Cifrado seguro utilizando Bcrypt
                            rondas_seguridad = st.secrets["seguridad"]["bcrypt_rounds"]
                            salt = bcrypt.gensalt(rounds=rondas_seguridad)
                            hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')
                                
                            # Insertar el registro en la base centralizada de enrutamiento
                            cursor.execute('''
                                INSERT INTO usuarios_central (username, password_hash, nombre_empresa, archivo_db, rol, apellidos, nombres)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (username) DO NOTHING
                            ''', (
                                new_username, 
                                hashed_pw, 
                                new_empresa, 
                                ruta_db_completa, 
                                new_rol, 
                                new_apellidos.strip().upper(), 
                                new_nombres.strip().title()
                            ))
                            conn.commit()
                                
                            # Inicializar el archivo físico SQLite si no existía
                            if not os.path.exists(ruta_db_completa):
                                conn_nueva_empresa = conectar_db()
                                crear_tablas_empresa(conn_nueva_empresa)
                                conn_nueva_empresa.close()
                                st.info(f"📁 Base de datos inicializada con tablas para: {new_empresa}")
    
                            st.success(f"¡Usuario '{new_username}' registrado con éxito!")
                            st.balloons()                            
                                
                        except psycopg2.errors.UniqueViolation:
                            st.error("Error: El nombre de usuario ya se encuentra registrado.")
                        except Exception as e:
                            st.error(f"Error al organizar el entorno de base de datos: {e}")
                        finally:
                            if 'conn' in locals():
                                conn.close()
                    else:
                        st.error("Por favor completa todos los campos del formulario.")
    
        # =====================================================================
        # SUBPESTAÑA 2: ASIGNACIÓN DE PERMISOS (Multi-Tenant Seguro)
        # =====================================================================
        with subtab_permisos:
            st.markdown("### 👤 Editar Usuarios y Permisos de Pestañas")
    
            conn_central = conectar_db_central()
            cursor_central = conn_central.cursor()
    
            if rol_sesion == "superadmin":
                cursor_central.execute("SELECT username, nombre_empresa, rol, archivo_db FROM usuarios_central")
            elif rol_sesion == "admin":
                cursor_central.execute('''
                    SELECT username, nombre_empresa, rol, archivo_db 
                    FROM usuarios_central 
                    WHERE archivo_db = %s
                    AND rol IN ('user', 'propietario')
                ''', (st.session_state.get("empresa_db"),))
            else:
                st.error("🚫 No tienes permisos suficientes para gestionar usuarios.")
                conn_central.close()
                st.stop()
    
            usuarios_lista = cursor_central.fetchall()
            conn_central.close()
    
            dict_usuarios = {f"{u['username']} ({u['nombre_empresa']} - Rol: {u['rol']})": (u['username'], u['archivo_db']) for u in usuarios_lista}
    
            if dict_usuarios:
                usuario_form_label = st.selectbox("Seleccione el usuario que desea editar:", list(dict_usuarios.keys()))
                user_seleccionado, ruta_db_user = dict_usuarios[usuario_form_label]
    
                conn_central = conectar_db_central()
                cursor_central = conn_central.cursor()
                cursor_central.execute("SELECT rol, nombre_empresa, apellidos, nombres, telefono, propietario_filtro FROM usuarios_central WHERE username = %s", (user_seleccionado,))
                datos_user_actual = cursor_central.fetchone()
                conn_central.close()
    
                rol_actual_user        = datos_user_actual["rol"]               if datos_user_actual else "user"
                empresa_user           = datos_user_actual["nombre_empresa"]     if datos_user_actual else ""
                apellidos_actual       = datos_user_actual["apellidos"]  or ""   if datos_user_actual else ""
                nombres_actual         = datos_user_actual["nombres"]    or ""   if datos_user_actual else ""
                telefono_actual        = datos_user_actual["telefono"]   or ""   if datos_user_actual else ""
                prop_filtro_actual     = datos_user_actual["propietario_filtro"] or "" if datos_user_actual else ""
    
                with st.form(f"form_editar_{user_seleccionado}"):
                    st.markdown(f"🔹 **Modificando a:** `{user_seleccionado}` — Empresa: *{empresa_user}*")

                    st.markdown("#### 🔐 Acceso")
                    nueva_pass = st.text_input("🔑 Cambiar Contraseña (Dejar vacío para mantener la actual):", type="password")

                    opciones_roles = ["user", "propietario"] if rol_sesion == "admin" else ["user", "propietario", "admin"]
                    if rol_sesion == "superadmin":
                        opciones_roles.append("superadmin")

                    nuevo_rol = st.selectbox("🎖️ Rol en el Sistema:", opciones_roles, index=opciones_roles.index(rol_actual_user) if rol_actual_user in opciones_roles else 0)

                    st.markdown("#### 👤 Datos Personales")
                    _dcol1, _dcol2, _dcol3 = st.columns(3)
                    nuevo_apellido  = _dcol1.text_input("Apellido/s:", value=apellidos_actual)
                    nuevo_nombre    = _dcol2.text_input("Nombre/s:", value=nombres_actual)
                    nuevo_telefono  = _dcol3.text_input("📱 Teléfono:", value=telefono_actual, placeholder="Ej: +54 266 4123456")

                    if nuevo_rol == "propietario":
                        st.markdown("#### 🏠 Vinculación con Propiedades")
                        # Cargar propietarios únicos desde la BD de la empresa del usuario
                        _prop_opciones = []
                        try:
                            try:
                                _eid_prop = _get_empresa_id(ruta_db_user)
                                if _eid_prop:
                                    with _pg_conn() as _conn_props:
                                        with _conn_props.cursor() as _cur_props:
                                            _cur_props.execute(
                                                "SELECT DISTINCT propietario FROM propiedades WHERE propietario IS NOT NULL AND propietario != '' AND empresa_id = %s ORDER BY propietario",
                                                (_eid_prop,)
                                            )
                                            _prop_opciones = [r["propietario"] for r in _cur_props.fetchall()]
                            except Exception:
                                pass
                        except Exception:
                            pass

                        if _prop_opciones:
                            _idx_prop = _prop_opciones.index(prop_filtro_actual) if prop_filtro_actual in _prop_opciones else 0
                            nuevo_prop_filtro = st.selectbox(
                                "🏠 Propietario vinculado:",
                                options=_prop_opciones,
                                index=_idx_prop,
                                help="El usuario solo verá contratos e historial de las propiedades de este propietario."
                            )
                        else:
                            st.warning("⚠️ No se encontraron propietarios cargados en la base de datos de esta empresa.")
                            nuevo_prop_filtro = st.text_input(
                                "Nombre del Propietario (manual):",
                                value=prop_filtro_actual,
                                placeholder="Ej: García, Juan Carlos"
                            )
                    else:
                        nuevo_prop_filtro = prop_filtro_actual
    
                    st.markdown("---")
                    if nuevo_rol == "propietario":
                        st.info("🏠 El rol **Propietario** tiene acceso fijo de solo lectura a: Dashboard, Planilla de Contratos e Historial de Caja. No requiere configuración de permisos.")
                        p_dash = p_plan = p_pagos = p_hist = p_carga = p_aux = p_gastos = False
                    else:
                        st.markdown("#### 📑 Asignación de Permisos de Pestañas (Para roles 'admin' y 'user')")

                        permisos_actuales = []
                        if ruta_db_user and os.path.exists(ruta_db_user):
                            try:
                                conn_emp = conectar_db()
                                cursor_emp = conn_emp.cursor()
                                if cursor_emp.fetchone():
                                    cursor_emp.execute("SELECT pestana FROM permisos_usuario WHERE username = %s", (user_seleccionado,))
                                    permisos_actuales = [row["pestana"] for row in cursor_emp.fetchall()]
                                conn_emp.close()
                            except Exception as e:
                                st.warning(f"Aviso al recuperar permisos existentes: {e}")

                        p_dash  = st.checkbox("📈 Tablero de Control",              value=("dashboard"       in permisos_actuales))
                        p_plan  = st.checkbox("📊 Planilla de Contratos",            value=("planilla"        in permisos_actuales))
                        p_pagos = st.checkbox("💰 Registrar / Emitir Recibo",        value=("pagos"           in permisos_actuales))
                        p_hist  = st.checkbox("🗄️ Historial de Caja",                value=("historial_pagos" in permisos_actuales))
                        p_carga = st.checkbox("📝 Carga de Contratos",               value=("carga"           in permisos_actuales))
                        p_aux   = st.checkbox("⚙️ Cargar Inquilinos / Propiedades",  value=("auxiliares"      in permisos_actuales))
                        p_gastos= st.checkbox("🔧 Gastos de Propiedades",            value=("gastos"          in permisos_actuales))
    
                    btn_guardar_cambios = st.form_submit_button("💾 Guardar Cambios", type="primary")
    
                    if btn_guardar_cambios:
                        conn_central = conectar_db_central()
                        cursor_central = conn_central.cursor()
                        try:
                            # 1. Actualizar datos en BD Central
                            if nueva_pass.strip():
                                rondas = st.secrets["seguridad"]["bcrypt_rounds"]
                                hashed = bcrypt.hashpw(nueva_pass.encode('utf-8'), bcrypt.gensalt(rounds=rondas)).decode('utf-8')
                                cursor_central.execute(
                                    "UPDATE usuarios_central SET password_hash = %s, rol = %s, apellidos = %s, nombres = %s, telefono = %s, propietario_filtro = %s WHERE username = %s",
                                    (hashed, nuevo_rol, nuevo_apellido.strip(), nuevo_nombre.strip(), nuevo_telefono.strip(), nuevo_prop_filtro.strip(), user_seleccionado)
                                )
                            else:
                                cursor_central.execute(
                                    "UPDATE usuarios_central SET rol = %s, apellidos = %s, nombres = %s, telefono = %s, propietario_filtro = %s WHERE username = %s",
                                    (nuevo_rol, nuevo_apellido.strip(), nuevo_nombre.strip(), nuevo_telefono.strip(), nuevo_prop_filtro.strip(), user_seleccionado)
                                )
                            conn_central.commit()
                                
                            # 2. Sincronización en BD Empresa
                            if ruta_db_user and ruta_db_user:
                                conn_emp = conectar_db()
                                cursor_emp = conn_emp.cursor()
                                    
                                # Asegurar existencia de la tabla
                                cursor_emp.execute('''CREATE TABLE IF NOT EXISTS permisos_usuario 
                                                    (username TEXT, pestana TEXT, PRIMARY KEY(username, pestana))''')
                                    
                                cursor_emp.execute("DELETE FROM permisos_usuario WHERE username = %s", (user_seleccionado,))
                                    
                                nuevas_pestanas = []
                                if p_dash: nuevas_pestanas.append("dashboard")
                                if p_plan: nuevas_pestanas.append("planilla")
                                if p_pagos: nuevas_pestanas.append("pagos")
                                if p_hist: nuevas_pestanas.append("historial_pagos")
                                if p_carga: nuevas_pestanas.append("carga")
                                if p_aux: nuevas_pestanas.append("auxiliares")
                                if p_gastos: nuevas_pestanas.append("gastos")
                                    
                                for p in nuevas_pestanas:
                                    cursor_emp.execute("INSERT INTO permisos_usuario (username, pestana) VALUES (%s, %s) ON CONFLICT (username, pestana) DO NOTHING", (user_seleccionado, p))
                                    
                                conn_emp.commit()
                                conn_emp.close()
                                st.success(f"Permisos de '{user_seleccionado}' actualizados. Se ha forzado la creación de la tabla de permisos.")
                                
                        except Exception as e:
                            st.error(f"Error al sincronizar: {e}")
                        finally:
                            conn_central.close()
                            st.rerun() # FORZAMOS EL REFRESH PARA VER LOS CAMBIOS
            else:
                st.info("No se encontraron usuarios activos en este entorno empresarial.")
    
        # =====================================================================
        # SUBPESTAÑA 3: EXCLUSIVA MÓDULO CSV (Solo visible para SuperAdmin)
        # =====================================================================
        if rol_sesion == "superadmin":
            with subtab_csv:
                st.markdown("### 📊 Operaciones Avanzadas de Migración (CSV)")
                st.info("Módulo global para inyección directa y respaldos analíticos de tablas SQLite.")
                    
                # MAPEO ACTUALIZADO: Sin 'SERVICIOS PACTADOS'
                MAPEO_CONTRATOS = {
                    "ALIAS PROPIEDAD": "alias_propiedad",
                    "DNI INQUILINO": "dni_inquilino",
                    "ESTADO": "estado",
                    "INICIO CONTRATO": "inicio_contrato",
                    "FIN CONTRATO": "fin_contrato",
                    "DURACIÓN (MESES)": "calc_duracion",
                    "ACTUALIZACIÓN": "act_contrato",
                    "ÍNDICE": "indice",
                    "MONTO INICIAL": "monto_inicial",
                    "ALQUILER BASE": "alquiler",
                    "PRÓX ACTUALIZACIÓN": "prox_actualizacion",
                    "MES CONTRATO": "mes_contrato",
                    "MES ACTUALIZACIÓN": "mes_actualizacion_contrato",
                    "HONORARIOS": "honorarios",
                    "MONTO HONORARIOS": "monto_honorarios",
                    "CUOTAS HONORARIOS": "cuota_honorarios",
                    "HONORARIOS PAGADOS": "honorarios_pagados",
                    "TIPO GARANTÍA": "tipo_de_garantie",
                    "VALOR GARANTÍA": "monto_garantia",
                    "GARANTÍA": "garantia",
                    "GARANTÍA PAGADA": "garantia_pagada",
                    "IMP INMO": "imp_inmobiliario",
                    "EXPENSAS BASE": "expensas",
                    "LUZ BASE": "edesal",
                    "GAS BASE": "gas",
                    "MUNI BASE": "municipalidad",
                    "AGUA BASE": "ooss",
                    "COCHERA BASE": "cochera"
                }
    
                with _pg_conn() as _conn_emp_list:
                    with _conn_emp_list.cursor() as _cur_emp_list:
                        _cur_emp_list.execute("SELECT DISTINCT nombre_empresa, archivo_db FROM usuarios_central")
                        _rows_emp = _cur_emp_list.fetchall()

                # En PostgreSQL no hay archivos físicos — solo empresas registradas
                dict_bases = {}
                for r in _rows_emp:
                    _nom = str(r["nombre_empresa"]).strip() if r["nombre_empresa"] else ""
                    _adb = str(r["archivo_db"]).strip() if r["archivo_db"] else ""
                    if _nom and _adb:
                        dict_bases[f"Empresa: {_nom}"] = _adb

                if not dict_bases:
                    st.info("No hay empresas registradas.")
                    st.stop()
                        
                base_seleccionada = st.selectbox("1️⃣ Seleccione la Empresa a operar:", options=list(dict_bases.keys()))
                db_file_target = dict_bases[base_seleccionada]
                _empresa_id_csv = _get_empresa_id(db_file_target)

                # Tablas disponibles en Postgres
                TABLAS_DISPONIBLES_PG = ["propiedades", "inquilinos", "contratos", "pagos_historial", "gastos_propiedades", "permisos_usuario"]
                tablas_disponibles = TABLAS_DISPONIBLES_PG
                        
                if tablas_disponibles:
                    tabla_seleccionada = st.selectbox("2️⃣ Seleccione la Tabla destino:", options=tablas_disponibles)
                        
                    col_exp, col_imp = st.columns(2)
                        
                    # --- OPERACIÓN A: EXPORTACIÓN (BAJAR CSV) ---
                    with col_exp:
                        st.markdown("#### 📥 Extraer Datos (Bajar CSV)")
                        try:
                            if tabla_seleccionada == "contratos":
                                query = '''
                                    SELECT 
                                        c.alias_propiedad AS "ALIAS PROPIEDAD",
                                        c.dni_inquilino AS "DNI INQUILINO",
                                        c.estado AS "ESTADO",
                                        c.inicio_contrato AS "INICIO CONTRATO",
                                        c.fin_contrato AS "FIN CONTRATO",
                                        c.calc_duracion AS "DURACIÓN (MESES)",
                                        c.act_contrato AS "ACTUALIZACIÓN",
                                        c.indice AS "ÍNDICE",
                                        c.monto_inicial AS "MONTO INICIAL",
                                        c.alquiler AS "ALQUILER BASE",
                                        c.prox_actualizacion AS "PRÓX ACTUALIZACIÓN",
                                        c.mes_contrato AS "MES CONTRATO",
                                        c.mes_actualizacion_contrato AS "MES ACTUALIZACIÓN",
                                        c.honorarios AS "HONORARIOS",
                                        c.monto_honorarios AS "MONTO HONORARIOS",
                                        c.cuota_honorarios AS "CUOTAS HONORARIOS",
                                        c.honorarios_pagados AS "HONORARIOS PAGADOS",
                                        c.tipo_de_garantie AS "TIPO GARANTÍA",
                                        c.monto_garantia AS "VALOR GARANTÍA",
                                        c.garantia AS "GARANTÍA",
                                        c.garantia_pagada AS "GARANTÍA PAGADA",
                                        c.imp_inmobiliario AS "IMP INMO",
                                        c.expensas AS "EXPENSAS BASE",
                                        c.edesal AS "LUZ BASE",
                                        c.gas AS "GAS BASE",
                                        c.municipalidad AS "MUNI BASE",
                                        c.ooss AS "AGUA BASE",
                                        c.cochera AS "COCHERA BASE"
                                    FROM contratos c
                                    WHERE c.empresa_id = %s
                                    ORDER BY c.codigo DESC
                                '''
                                _params_exp = (_empresa_id_csv,)
                            else:
                                # permisos_usuario no tiene empresa_id — filtrar solo por username
                                TABLAS_SIN_EMPRESA_ID = {"permisos_usuario", "empresas", "usuarios_central"}
                                if tabla_seleccionada in TABLAS_SIN_EMPRESA_ID:
                                    query = f"SELECT * FROM {tabla_seleccionada}"
                                    _params_exp = ()
                                else:
                                    query = f"SELECT * FROM {tabla_seleccionada} WHERE empresa_id = %s"
                                    _params_exp = (_empresa_id_csv,)

                            with _pg_conn() as _conn_exp:
                                with _conn_exp.cursor() as _cur_exp:
                                    _cur_exp.execute(query, _params_exp)
                                    _rows_exp = _cur_exp.fetchall()
                                    _cols_exp = [d.name for d in _cur_exp.description]

                            df_export = pd.DataFrame(_rows_exp, columns=_cols_exp) if _rows_exp else pd.DataFrame(columns=_cols_exp)

                            if tabla_seleccionada != "contratos":
                                if 'id' in df_export.columns:
                                    df_export = df_export.drop(columns=['id'])
                                if 'empresa_id' in df_export.columns:
                                    df_export = df_export.drop(columns=['empresa_id'])
                            else:
                                if "DNI INQUILINO" in df_export.columns:
                                    df_export["DNI INQUILINO"] = df_export["DNI INQUILINO"].astype(str).str.split('.').str[0]
                                if "ACTUALIZACIÓN" in df_export.columns:
                                    df_export["ACTUALIZACIÓN"] = pd.to_numeric(df_export["ACTUALIZACIÓN"], errors='coerce').fillna(0).astype(int)
                                if "MONTO HONORARIOS" in df_export.columns:
                                    df_export["MONTO HONORARIOS"] = pd.to_numeric(df_export["MONTO HONORARIOS"], errors='coerce').round(2)
                                
                            st.write(f"Vista previa de `{tabla_seleccionada}` ({len(df_export)} registros):")
                            st.dataframe(df_export.head(5), use_container_width=True, hide_index=True)
                                
                            csv_data = df_export.to_csv(index=False, sep=";", encoding="latin-1")
                                
                            st.download_button(
                                label=f"⬇️ Descargar tabla '{tabla_seleccionada}' como CSV",
                                data=csv_data,
                                file_name=f"backup_{tabla_seleccionada}_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error(f"Fallo al compilar exportación: {e}")
                                
    
                    # --- OPERACIÓN B: INYECCIÓN / PROCESO INVERSO (SUBIR CSV) ---
                    with col_imp:
                        st.markdown("#### 📤 Insertar / Sobrescribir Datos (Subir CSV)")
                            
                        archivo_subido = st.file_uploader(
                            f"Cargar archivo para inyectar en '{tabla_seleccionada}'", 
                            type=["csv"], 
                            key=f"uploader_{db_file_target}_{tabla_seleccionada}"
                        )
    
                        if archivo_subido is not None:
                            try:
                                # 1. Usamos 'utf-8-sig' para remover automáticamente el 'ï»¿' si Excel lo insertó
                                # Si arroja error por caracteres extraños, retrocede ordenadamente a 'latin-1'
                                try:
                                    df = pd.read_csv(archivo_subido, sep=';', encoding='utf-8-sig')
                                except UnicodeDecodeError:
                                    archivo_subido.seek(0) # Resetear puntero del archivo
                                    df = pd.read_csv(archivo_subido, sep=';', encoding='latin-1')
                                    
                                # 2. LIMPIEZA CLAVE: Remover espacios en blanco residuales de los nombres de columnas
                                df.columns = [c.strip() for c in df.columns]
                                    
                                if tabla_seleccionada != "contratos":
                                    if 'id' in df.columns:
                                        df = df.drop(columns=['id'])
                                            
                                import numpy as np
                                df = df.replace({pd.NA: None, np.nan: None})
                                    
                                columnas_csv = list(df.columns)
                                    
                                # --- PROCESADOR EXCLUSIVO PARA CONTRATOS ---
                                if tabla_seleccionada == "contratos":
                                    if "ALIAS PROPIEDAD" not in columnas_csv:
                                        st.error("❌ El CSV debe incluir la columna 'ALIAS PROPIEDAD'.")
                                        st.info(f"Columnas detectadas: {columnas_csv}")
                                    else:
                                        _eid_cont_imp = _empresa_id_csv or st.session_state.get("empresa_id", 0)
                                        contratos_listos_para_db = []
                                        errores_relacion = []

                                        with _pg_conn() as _conn_val:
                                            with _conn_val.cursor() as _cur_val:
                                                for index, fila in df.iterrows():
                                                    # ── Solo ALIAS PROPIEDAD es obligatorio ──
                                                    alias_prop_limpio = str(fila['ALIAS PROPIEDAD']).strip() if fila.get('ALIAS PROPIEDAD') is not None else ""
                                                    if not alias_prop_limpio or alias_prop_limpio.lower() == 'nan':
                                                        errores_relacion.append(f"Fila {index+2}: 'ALIAS PROPIEDAD' vacío — fila omitida.")
                                                        continue

                                                    # Verificar que la propiedad exista
                                                    _cur_val.execute(
                                                        "SELECT alias_propiedad FROM propiedades WHERE TRIM(alias_propiedad) = %s AND empresa_id = %s",
                                                        (alias_prop_limpio, _eid_cont_imp)
                                                    )
                                                    res_prop = _cur_val.fetchone()
                                                    if not res_prop:
                                                        errores_relacion.append(f"Fila {index+2}: Propiedad '{alias_prop_limpio}' no existe.")
                                                        continue

                                                    # DNI INQUILINO — opcional
                                                    dni_limpio = None
                                                    if 'DNI INQUILINO' in columnas_csv:
                                                        _dni_raw = fila.get('DNI INQUILINO')
                                                        if _dni_raw is not None and str(_dni_raw).strip() not in ('', 'nan'):
                                                            dni_limpio = str(_dni_raw).split('.')[0].strip()
                                                            _cur_val.execute(
                                                                "SELECT dni FROM inquilinos WHERE dni = %s AND empresa_id = %s",
                                                                (dni_limpio, _eid_cont_imp)
                                                            )
                                                            res_inq = _cur_val.fetchone()
                                                            if not res_inq:
                                                                errores_relacion.append(f"Fila {index+2}: Inquilino DNI '{dni_limpio}' no existe — se importará sin inquilino.")
                                                                dni_limpio = None

                                                    registro_fila = {
                                                        'alias_propiedad': res_prop['alias_propiedad'],
                                                        'dni_inquilino': dni_limpio,
                                                        '_fila_csv': index + 2
                                                    }

                                                    # Procesar el resto de columnas — todas opcionales
                                                    for alias_sql, col_db in MAPEO_CONTRATOS.items():
                                                        if col_db in ('alias_propiedad', 'dni_inquilino'):
                                                            continue
                                                        valor_celda = fila.get(alias_sql) if alias_sql in df.columns else None
                                                        if valor_celda is None or str(valor_celda).strip() in ('', 'nan', 'None'):
                                                            valor_celda = None
                                                        elif col_db in ['inicio_contrato', 'fin_contrato', 'prox_actualizacion']:
                                                            try: valor_celda = pd.to_datetime(str(valor_celda).strip(), dayfirst=True).strftime('%Y-%m-%d')
                                                            except: valor_celda = None
                                                        elif col_db in ['act_contrato', 'mes_contrato', 'mes_actualizacion_contrato', 'cuota_honorarios', 'honorarios_pagados', 'garantia_pagada']:
                                                            try: valor_celda = int(float(str(valor_celda).split('.')[0]))
                                                            except: valor_celda = None
                                                        elif col_db in ['monto_inicial', 'alquiler', 'monto_honorarios', 'monto_garantia', 'imp_inmobiliario', 'expensas', 'edesal', 'gas', 'municipalidad', 'ooss', 'cochera']:
                                                            try: valor_celda = round(float(str(valor_celda).replace(',', '.')), 2)
                                                            except: valor_celda = None
                                                        else:
                                                            valor_celda = str(valor_celda).strip()
                                                        registro_fila[col_db] = valor_celda

                                                    contratos_listos_para_db.append(registro_fila)

                                        if errores_relacion:
                                            st.warning(f"⚠️ Avisos ({len(errores_relacion)}):")
                                            for err in errores_relacion[:8]: st.caption(err)
                                            if len(errores_relacion) > 8: st.caption(f"...y otros {len(errores_relacion)-8} avisos.")

                                        if contratos_listos_para_db:
                                            df_preview = pd.DataFrame(contratos_listos_para_db)
                                            fila_nums = df_preview.pop('_fila_csv')
                                            df_preview.insert(0, 'Fila CSV', fila_nums)

                                            st.markdown(f"**{len(df_preview)} contrato(s) listos para importar**")
                                            st.caption("Seleccioná los que querés importar o usá el botón para importar todos.")

                                            sel_cont = st.dataframe(
                                                df_preview, use_container_width=True, hide_index=True,
                                                selection_mode="multi-row", on_select="rerun",
                                                key=f"sel_contratos_{archivo_subido.name}"
                                            )
                                            indices_cont = sel_cont.get("selection", {}).get("rows", [])

                                            col_cb1, col_cb2 = st.columns(2)
                                            _imp_todos = col_cb1.button("✅ Importar TODOS", type="primary", use_container_width=True, key="btn_cont_todos")
                                            _imp_sel   = col_cb2.button(f"⬆️ Importar seleccionados ({len(indices_cont)})", use_container_width=True, key="btn_cont_sel", disabled=not indices_cont)

                                            registros_a_importar = []
                                            if _imp_todos:
                                                registros_a_importar = contratos_listos_para_db
                                            elif _imp_sel and indices_cont:
                                                registros_a_importar = [contratos_listos_para_db[i] for i in indices_cont]

                                            if registros_a_importar:
                                                cols_cont = ["empresa_id", "alias_propiedad", "dni_inquilino"] + [v for v in MAPEO_CONTRATOS.values() if v not in ("alias_propiedad", "dni_inquilino")]
                                                placeholders_cont = ", ".join(["%s"] * len(cols_cont))
                                                query_cont = f"INSERT INTO contratos ({', '.join(cols_cont)}) VALUES ({placeholders_cont}) ON CONFLICT DO NOTHING"
                                                datos_cont = [tuple([_eid_cont_imp] + [r.get(c) for c in cols_cont[1:]]) for r in registros_a_importar]
                                                _cont_key = f"imported_contratos_{archivo_subido.name}_{len(datos_cont)}"
                                                if _cont_key not in st.session_state:
                                                    try:
                                                        with _pg_conn() as _conn_imp_c:
                                                            with _conn_imp_c.cursor() as _cur_imp_c:
                                                                _cur_imp_c.executemany(query_cont, datos_cont)
                                                        st.session_state[_cont_key] = True
                                                        st.success(f"✅ {len(datos_cont)} contrato(s) importado(s) correctamente.")
                                                        st.balloons()
                                                        st.rerun()
                                                    except psycopg2.Error as op_err:
                                                        st.error(f"❌ Error al importar: {op_err}")
                                                
                                # --- LÓGICA ESTÁNDAR PARA OTRAS TABLAS ---
                                else:
                                    esquema_esperado = ESQUEMAS_VALIDOS.get(tabla_seleccionada, [])
                                    if columnas_csv == esquema_esperado:
                                            
                                        if tabla_seleccionada == "propiedades" and "alias_propiedad" in df.columns:
                                            df["alias_propiedad"] = df["alias_propiedad"].astype(str).str.strip()
    
                                        if tabla_seleccionada == "inquilinos" and "telefono" in df.columns:
                                            df["telefono"] = df["telefono"].astype(str).str.split('.').str[0]
                                            df["telefono"] = df["telefono"].replace({"nan": None, "None": None, "": None})

                                        # ── Detectar duplicados vs existentes en Postgres ──
                                        _eid_imp = _empresa_id_csv or st.session_state.get("empresa_id", 0)
                                        with _pg_conn() as _conn_imp_chk:
                                            with _conn_imp_chk.cursor() as _cur_imp_chk:
                                                columna_clave = 'alias_propiedad' if tabla_seleccionada == 'propiedades' else 'dni'
                                                _cur_imp_chk.execute(
                                                    f"SELECT {columna_clave} FROM {tabla_seleccionada} WHERE empresa_id = %s",
                                                    (_eid_imp,)
                                                )
                                                existentes = {str(r[columna_clave]) for r in _cur_imp_chk.fetchall()}

                                        df["_existe"] = df[columna_clave].astype(str).isin(existentes)
                                        df_nuevos   = df[~df["_existe"]].drop(columns=["_existe"])
                                        df_dupes    = df[df["_existe"]].drop(columns=["_existe"])
                                        df_display  = df.drop(columns=["_existe"])

                                        st.markdown(f"**{len(df)} fila(s) leídas del CSV** — "
                                                    f"🟢 {len(df_nuevos)} nuevas · "
                                                    f"🔴 {len(df_dupes)} ya existen (se omitirán)")

                                        # ── Tabla interactiva con selección de filas ──
                                        st.caption("Seleccioná las filas que querés importar. Por defecto solo las nuevas están preseleccionadas.")

                                        sel_result = st.dataframe(
                                            df_display,
                                            use_container_width=True,
                                            hide_index=False,
                                            selection_mode="multi-row",
                                            on_select="rerun",
                                            key=f"sel_import_{tabla_seleccionada}_{archivo_subido.name}"
                                        )

                                        indices_sel = sel_result.get("selection", {}).get("rows", [])

                                        # Preseleccionar solo filas nuevas si el usuario no eligió nada
                                        if not indices_sel:
                                            indices_nuevos = [i for i, v in enumerate(~df["_existe"] if "_existe" in df.columns else [True]*len(df)) if v]
                                            st.info(f"💡 Hacé clic en las filas a importar, o usá los botones de abajo.")
                                            col_sel1, col_sel2 = st.columns(2)
                                            _sel_todas = col_sel1.button("✅ Importar TODAS las nuevas", key=f"btn_todas_{tabla_seleccionada}", use_container_width=True)
                                            _sel_ninguna = col_sel2.button("❌ Cancelar", key=f"btn_cancel_{tabla_seleccionada}", use_container_width=True)

                                            if _sel_todas:
                                                df_a_importar = df_nuevos
                                            elif _sel_ninguna:
                                                st.info("Importación cancelada.")
                                                df_a_importar = pd.DataFrame()
                                            else:
                                                df_a_importar = pd.DataFrame()  # esperar selección
                                        else:
                                            df_a_importar = df_display.iloc[indices_sel]
                                            # Filtrar los que ya existen de la selección manual
                                            df_a_importar = df_a_importar[~df_a_importar[columna_clave].astype(str).isin(existentes)]
                                            dupes_en_sel = len(df_display.iloc[indices_sel]) - len(df_a_importar)
                                            if dupes_en_sel > 0:
                                                st.warning(f"⚠️ {dupes_en_sel} fila(s) seleccionada(s) ya existen y serán omitidas.")

                                            st.markdown(f"**{len(df_a_importar)} fila(s) listas para importar**")
                                            _btn_confirmar = st.button(
                                                f"⬆️ Confirmar e importar {len(df_a_importar)} registro(s)",
                                                type="primary", use_container_width=True,
                                                key=f"btn_confirm_{tabla_seleccionada}"
                                            )
                                            if not _btn_confirmar:
                                                df_a_importar = pd.DataFrame()

                                        # ── Ejecutar importación — solo una vez con flag en session_state ──
                                        _import_key = f"imported_{tabla_seleccionada}_{archivo_subido.name}_{len(df_a_importar)}"
                                        if not df_a_importar.empty and _import_key not in st.session_state:
                                            cols_pg = ", ".join(["empresa_id"] + list(esquema_esperado))
                                            placeholders = ", ".join(["%s"] * (1 + len(esquema_esperado)))
                                            query_imp = f"INSERT INTO {tabla_seleccionada} ({cols_pg}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                                            datos = [
                                                tuple([_eid_imp] + [reg.get(c) for c in esquema_esperado])
                                                for reg in df_a_importar.to_dict(orient='records')
                                            ]
                                            with _pg_conn() as _conn_imp:
                                                with _conn_imp.cursor() as _cur_imp:
                                                    _cur_imp.executemany(query_imp, datos)
                                            st.session_state[_import_key] = True
                                            st.success(f"✅ ¡{len(datos)} registro(s) importados en '{tabla_seleccionada}'!")
                                            st.balloons()
                                            st.rerun()
                                    else:
                                        st.error("❌ El esquema de columnas del CSV no coincide con los campos requeridos.")
                                        st.info(f"Campos requeridos por el sistema:\n{esquema_esperado}")
                            except Exception as e:
                                st.error(f"Error al procesar el archivo CSV: {e}")
    
# =====================================================================
        # SECCIÓN EXCLUSIVA: ELIMINACIÓN DE EMPRESAS (Solo SuperAdmin)
        # =====================================================================
        if rol_sesion == "superadmin":
            st.markdown("---")
            st.markdown("### 🚨 Zona de Peligro: Eliminar Empresa y Entorno")
                
            with st.expander("❌ Hacer clic aquí para gestionar la eliminación de empresas", expanded=False):
                st.warning("⚠️ Esta acción es irreversible. Se borrarán permanentemente todos los registros de la empresa en Supabase.")
                    
                with _pg_conn() as _conn_emp_del:
                    with _conn_emp_del.cursor() as _cur_emp_del:
                        _cur_emp_del.execute("SELECT DISTINCT nombre_empresa, archivo_db FROM usuarios_central")
                        _rows_emp_del = _cur_emp_del.fetchall()

                if _rows_emp_del:
                    dict_empresas_del = {r["nombre_empresa"]: r["archivo_db"] for r in _rows_emp_del if r["nombre_empresa"]}
                        
                    empresa_a_eliminar = st.selectbox(
                        "Seleccione la empresa que desea eliminar por completo:",
                        options=list(dict_empresas_del.keys()),
                        key="sb_eliminar_empresa"
                    )
                        
                    confirmacion_texto = st.text_input(
                        f"Para confirmar, escriba exactamente el nombre de la empresa (**{empresa_a_eliminar}**):"
                    )
                        
                    btn_destruir_empresa = st.button("💥 ELIMINAR EMPRESA", type="primary", use_container_width=True)
                        
                    if btn_destruir_empresa:
                        if confirmacion_texto == empresa_a_eliminar:
                            ruta_db_a_borrar = dict_empresas_del[empresa_a_eliminar]
                            try:
                                _eid_a_borrar = _get_empresa_id(ruta_db_a_borrar)
                                with _pg_conn() as _conn_borrar:
                                    with _conn_borrar.cursor() as _cur_borrar:
                                        if _eid_a_borrar:
                                            # Borrar todos los datos de la empresa en orden (FK)
                                            for _tbl in ["pagos_historial", "gastos_propiedades",
                                                         "permisos_usuario", "contratos",
                                                         "inquilinos", "propiedades"]:
                                                try:
                                                    _cur_borrar.execute(f"DELETE FROM {_tbl} WHERE empresa_id = %s", (_eid_a_borrar,))
                                                except Exception:
                                                    pass
                                            _cur_borrar.execute("DELETE FROM empresas WHERE id = %s", (_eid_a_borrar,))
                                        _cur_borrar.execute("DELETE FROM usuarios_central WHERE nombre_empresa = %s", (empresa_a_eliminar,))

                                st.success(f"🔥 La empresa '{empresa_a_eliminar}' y todos sus datos han sido eliminados de Supabase.")
                                st.balloons()
                                st.rerun()
                                    
                            except Exception as e:
                                st.error(f"Error crítico durante el proceso de borrado: {e}")
                        else:
                            st.error("❌ El nombre ingresado no coincide. Operación cancelada.")
                else:
                    st.info("No hay empresas registradas disponibles para eliminar.")
    
        # =====================================================================
        # NUEVA SECCIÓN MODULAR: ELIMINACIÓN DE FILAS EN LAS TABLAS (SOLO SuperAdmin)
        # =====================================================================
        if rol_sesion == "superadmin":
            st.markdown("---")
            st.markdown("### 🗑️ Gestión de Datos Central: Eliminar Filas / Registros en Bloque")
                
            with st.expander("🛠️ [SuperAdmin] Panel de Eliminación Múltiple Forzada", expanded=False):
                st.warning("⚠️ **Zona Crítica:** Al borrar registros con este panel se forzará la eliminación en la base de datos operativa de la empresa seleccionada. Use con extrema precaución.")
                    
                # Selector de empresa — usar cursor directo (pd.read_sql_query falla con RealDictCursor)
                with _pg_conn() as _conn_del_list:
                    with _conn_del_list.cursor() as _cur_del_list:
                        _cur_del_list.execute("SELECT DISTINCT nombre_empresa, archivo_db FROM usuarios_central")
                        _rows_del = _cur_del_list.fetchall()

                if _rows_del:
                    dict_empresas_filas = {r["nombre_empresa"]: r["archivo_db"] for r in _rows_del if r["nombre_empresa"] and r["archivo_db"]}
                        
                    empresa_datos_seleccionada = st.selectbox(
                        "1. Seleccione la Empresa:",
                        options=list(dict_empresas_filas.keys()),
                        key="sb_empresa_datos_del_multi"
                    )
                        
                    ruta_db_objetivo = dict_empresas_filas[empresa_datos_seleccionada]
                    _eid_del = _get_empresa_id(ruta_db_objetivo)

                    tabla_seleccionada = st.selectbox(
                        "2. Seleccione la tabla:",
                        options=["contratos", "inquilinos", "propiedades", "pagos_historial"],
                        format_func=lambda x: x.upper(),
                        key="sb_tabla_operativa_del_multi"
                    )
                        
                    TABLAS_PERMITIDAS = {"contratos", "inquilinos", "propiedades", "pagos_historial"}
                    if tabla_seleccionada not in TABLAS_PERMITIDAS:
                        st.error(f"❌ Tabla '{tabla_seleccionada}' no permitida.")
                    else:
                        try:
                            _TABLAS_SIN_EID = {"permisos_usuario", "empresas", "usuarios_central"}
                            with _pg_conn() as _conn_lect:
                                with _conn_lect.cursor() as _cur_lect:
                                    if tabla_seleccionada in _TABLAS_SIN_EID:
                                        _cur_lect.execute(f"SELECT * FROM {tabla_seleccionada}")
                                    else:
                                        _cur_lect.execute(
                                            f"SELECT * FROM {tabla_seleccionada} WHERE empresa_id = %s",
                                            (_eid_del,)
                                        )
                                    _rows_lect = _cur_lect.fetchall()
                                    _cols_lect = [d.name for d in _cur_lect.description]
                            df_completo = pd.DataFrame(_rows_lect, columns=_cols_lect) if _rows_lect else pd.DataFrame(columns=_cols_lect)

                            if df_completo.empty:
                                st.info(f"La tabla '{tabla_seleccionada.upper()}' de '{empresa_datos_seleccionada}' está vacía.")
                            else:
                                id_col_name = "codigo" if "codigo" in df_completo.columns else "id" if "id" in df_completo.columns else None

                                if id_col_name:
                                    st.info("💡 **Tip:** Hacé clic en la casilla del encabezado para seleccionar todo.")

                                    tabla_interactiva = st.dataframe(
                                        df_completo,
                                        use_container_width=True,
                                        hide_index=True,
                                        selection_mode="multi-row",
                                        on_select="rerun",
                                        key=f"tabla_sel_{empresa_datos_seleccionada}_{tabla_seleccionada}"
                                    )

                                    indices_seleccionados = tabla_interactiva.get("selection", {}).get("rows", [])

                                    if indices_seleccionados:
                                        ids_a_borrar = df_completo.iloc[indices_seleccionados][id_col_name].tolist()
                                        cant_filas = len(ids_a_borrar)

                                        st.error(f"🔴 **{cant_filas}** registro(s) seleccionados de `{tabla_seleccionada.upper()}` — empresa: **{empresa_datos_seleccionada}**")
                                        st.caption(f"IDs marcados ({id_col_name.upper()}): {ids_a_borrar}")

                                        frase_esperada = f"FORZAR BORRADO {cant_filas} FILAS"
                                        confirmacion_palabra = st.text_input(
                                            f"Escriba exactamente: **{frase_esperada}**",
                                            key="txt_confirmacion_multi_del"
                                        )

                                        btn_eliminar_bloque = st.button(
                                            f"💥 FORZAR ELIMINACIÓN DE {cant_filas} REGISTROS",
                                            type="primary",
                                            use_container_width=True,
                                            key="btn_forzar_borrado"
                                        )

                                        if btn_eliminar_bloque:
                                            if confirmacion_palabra == frase_esperada:
                                                try:
                                                    placeholder = ",".join(["%s"] * cant_filas)
                                                    with _pg_conn() as conn_del:
                                                        with conn_del.cursor() as cursor_del:
                                                            if tabla_seleccionada in _TABLAS_SIN_EID:
                                                                cursor_del.execute(
                                                                    f"DELETE FROM {tabla_seleccionada} WHERE {id_col_name} IN ({placeholder})",
                                                                    tuple(ids_a_borrar)
                                                                )
                                                            else:
                                                                cursor_del.execute(
                                                                    f"DELETE FROM {tabla_seleccionada} WHERE {id_col_name} IN ({placeholder}) AND empresa_id = %s",
                                                                    tuple(ids_a_borrar) + (_eid_del,)
                                                                )
                                                    st.success(f"✅ {cant_filas} registros eliminados de '{tabla_seleccionada.upper()}' — '{empresa_datos_seleccionada}'.")
                                                    st.balloons()
                                                    st.rerun()
                                                except Exception as sql_e:
                                                    st.error(f"❌ Error al borrar: {sql_e}")
                                            else:
                                                st.error(f"❌ La frase no coincide. Escriba exactamente: **{frase_esperada}**")
                                    else:
                                        st.info("💡 Seleccioná una o más filas para habilitar el borrado.")

                        except Exception as e:
                            st.error(f"❌ Error al leer '{empresa_datos_seleccionada}': {e}")
                else:
                    st.info("No hay empresas registradas.")

# =====================================================================
# PESTAÑA: GASTOS DE PROPIEDADES
# =====================================================================
if tab_gastos:
    with tab_gastos:
        st.subheader("🔧 Registro de Gastos de Propiedades")

        conn = conectar_db()

        # --- Cargar propiedades disponibles (filtradas si es propietario) ---
        _pf_g = st.session_state.get("propietario_filtro", "")
        _pf_g_activo = rol_actual == "propietario" and bool(_pf_g)
        if _pf_g_activo:
            with _pg_conn() as _cpg1:
                with _cpg1.cursor() as _cupg1:
                    _cupg1.execute("SELECT id, alias_propiedad, propietario FROM propiedades WHERE empresa_id = %s AND propietario = %s ORDER BY alias_propiedad", (st.session_state.get("empresa_id", 0), _pf_g))
                    _props_gasto = pd.DataFrame([dict(r) for r in _cupg1.fetchall()])
        else:
            with _pg_conn() as _cpg2:
                with _cpg2.cursor() as _cupg2:
                    _cupg2.execute("SELECT id, alias_propiedad, propietario FROM propiedades WHERE empresa_id = %s ORDER BY alias_propiedad", (st.session_state.get("empresa_id", 0),))
                    _props_gasto = pd.DataFrame([dict(r) for r in _cupg2.fetchall()])
        conn.close()

        _categorias_gasto = [
            "🔨 Reparación / Arreglo",
            "💡 Servicios (Luz / Gas / Agua)",
            "🏛️ Impuestos y Tasas",
            "🛡️ Seguro de Propiedad",
            "🏗️ Obra / Mejora",
            "🧹 Mantenimiento / Limpieza",
            "📋 Honorarios Profesionales",
            "📦 Otros Pasivos",
        ]

        subtab_nuevo, subtab_historial, subtab_metricas = st.tabs(["➕ Registrar Gasto", "📋 Historial de Gastos", "📊 Métricas por Propiedad"])

        # ── SUBPESTAÑA 1: FORMULARIO DE CARGA ──────────────────────────
        with subtab_nuevo:
            if _props_gasto.empty:
                st.warning("No hay propiedades disponibles para registrar gastos.")
            else:
                _dict_props = {f"{r['alias_propiedad']} ({r['propietario'] or 'Sin propietario'})": r['id'] for _, r in _props_gasto.iterrows()}

                # Input de cotización fuera del form para que actualice session_state en tiempo real
                _usd_g_reg_col, _ = st.columns([2, 3])
                _cotizacion_usd_g_reg = _usd_g_reg_col.number_input(
                    "💵 Cotización USD al momento del gasto ($ ARS por 1 USD):",
                    min_value=1.0,
                    value=float(st.session_state.get("cotizacion_usd_hist", 1300.0)),
                    step=10.0,
                    key="cotizacion_usd_gasto_reg_input",
                    help="Este valor se guardará junto al gasto y no cambiará aunque la cotización cambie después"
                )
                st.session_state["cotizacion_usd_hist"] = _cotizacion_usd_g_reg

                with st.form("form_gasto_propiedad", clear_on_submit=True):
                    st.markdown("#### 📝 Datos del Gasto")

                    _gcol1, _gcol2 = st.columns(2)
                    _prop_label = _gcol1.selectbox("🏠 Propiedad:", list(_dict_props.keys()))
                    _prop_id_sel = _dict_props[_prop_label]
                    _fecha_gasto = _gcol2.date_input("📅 Fecha del Gasto:", value=datetime.now().date())

                    _gcol3, _gcol4 = st.columns(2)
                    _categoria = _gcol3.selectbox("📂 Categoría:", _categorias_gasto)
                    _monto = _gcol4.number_input("💲 Monto ($):", min_value=0.0, step=500.0)

                    _descripcion = st.text_input("📄 Descripción:", placeholder="Ej: Cambio de cañería cocina")

                    _gcol5, _gcol6 = st.columns(2)
                    _proveedor = _gcol5.text_input("🏢 Proveedor / Empresa:", placeholder="Ej: Plomería González")
                    _comprobante = _gcol6.text_input("🧾 N° Comprobante / Factura:", placeholder="Ej: FA-0001-00012345")

                    _gcol7, _gcol8 = st.columns(2)
                    _pagado_por = _gcol7.selectbox("💳 Pagado por:", ["Inmobiliaria", "Propietario", "Inquilino", "Otro"])
                    _observaciones = _gcol8.text_input("🗒️ Observaciones:", placeholder="Opcional")

                    _btn_gasto = st.form_submit_button("💾 Registrar Gasto", type="primary")

                    if _btn_gasto:
                        if _monto <= 0:
                            st.error("❌ El monto debe ser mayor a cero.")
                        elif not _descripcion.strip():
                            st.error("❌ La descripción es obligatoria.")
                        else:
                            try:
                                conn = conectar_db()
                                _tc_g = float(st.session_state.get("cotizacion_usd_hist", 0.0))
                                _monto_usd_g = round(_monto / _tc_g, 2) if _tc_g > 0 else 0.0
                                conn.execute(
                                    """INSERT INTO gastos_propiedades
                                       (empresa_id, propiedad_id, fecha, categoria, descripcion, monto, proveedor, comprobante, pagado_por, observaciones)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                    (st.session_state.get('empresa_id',0), _prop_id_sel, _fecha_gasto.strftime("%Y-%m-%d"), _categoria,
                                     _descripcion.strip(), _monto, _proveedor.strip(),
                                     _comprobante.strip(), _pagado_por, _observaciones.strip(),
)
                                )
                                conn.commit()
                                conn.close()
                                st.success(f"✅ Gasto de $ {_monto:,.2f} registrado correctamente en {_prop_label}.")
                                st.rerun()
                            except Exception as _e:
                                st.error(f"Error al guardar: {_e}")

        # ── SUBPESTAÑA 2: HISTORIAL ─────────────────────────────────────
        with subtab_historial:
            conn = conectar_db()
            _eid_g = st.session_state.get("empresa_id", 0)
            _where_g = "AND p.propietario = %s" if _pf_g_activo else ""
            _params_g = (_eid_g, _pf_g) if _pf_g_activo else (_eid_g,)
            with _pg_conn() as _cg, _cg.cursor() as _cug:
              _df_gastos = None
            with _pg_conn() as _conn_dg:
                with _conn_dg.cursor() as _cur_dg:
                    _cur_dg.execute(f"""
                SELECT gp.id AS "ID", p.alias_propiedad AS "PROPIEDAD", p.propietario AS "PROPIETARIO",
                       gp.fecha AS "FECHA", gp.categoria AS "CATEGORÍA", gp.descripcion AS "DESCRIPCIÓN",
                       gp.monto AS "MONTO ($)",
                       0 AS "COTIZACIÓN USD",
                       0 AS "MONTO (USD)",
                       gp.proveedor AS "PROVEEDOR",
                       gp.comprobante AS "COMPROBANTE", gp.pagado_por AS "PAGADO POR",
                       gp.observaciones AS "OBSERVACIONES"
                FROM gastos_propiedades gp
                JOIN propiedades p ON gp.propiedad_id = p.id AND p.empresa_id = gp.empresa_id
                WHERE gp.empresa_id = %s {_where_g}
                ORDER BY gp.fecha DESC, gp.id DESC
            """, _params_g)
                    _rows_dg = _cur_dg.fetchall()
                    _cols_dg = [x.name for x in _cur_dg.description]
            _df_gastos = pd.DataFrame([dict(r) for r in _rows_dg], columns=_cols_dg) if _rows_dg else pd.DataFrame(columns=_cols_dg)
            conn.close()

            if _df_gastos.empty:
                st.info("Aún no se registraron gastos.")
            else:
                st.caption("💡 Los valores en USD corresponden a la cotización del momento en que se registró cada gasto.")

                # Filtros
                _hcol1, _hcol2, _hcol3 = st.columns(3)
                _f_prop = _hcol1.selectbox("Filtrar por propiedad:", ["Todas"] + list(_df_gastos["PROPIEDAD"].unique()))
                _f_cat  = _hcol2.selectbox("Filtrar por categoría:", ["Todas"] + list(_df_gastos["CATEGORÍA"].unique()))
                _f_txt  = _hcol3.text_input("Buscar texto:", placeholder="Descripción, proveedor...")

                _df_f = _df_gastos.copy()
                if _f_prop != "Todas":
                    _df_f = _df_f[_df_f["PROPIEDAD"] == _f_prop]
                if _f_cat != "Todas":
                    _df_f = _df_f[_df_f["CATEGORÍA"] == _f_cat]
                if _f_txt:
                    _mask = (
                        _df_f["DESCRIPCIÓN"].str.contains(_f_txt, case=False, na=False) |
                        _df_f["PROVEEDOR"].str.contains(_f_txt, case=False, na=False) |
                        _df_f["OBSERVACIONES"].str.contains(_f_txt, case=False, na=False)
                    )
                    _df_f = _df_f[_mask]

                # Totales
                _total_gastos = _df_f["MONTO ($)"].sum()
                _total_gastos_usd = _df_f["MONTO (USD)"].sum()
                _mc1, _mc2, _mc3, _mc4 = st.columns(4)
                _mc1.metric("Total Gastos Filtrados", f"$ {_total_gastos:,.2f}")
                _mc2.metric("Total Gastos (USD)", f"U$S {_total_gastos_usd:,.2f}")
                _mc3.metric("Cantidad de Registros", len(_df_f))
                _mc4.metric("Promedio por Gasto", f"$ {(_total_gastos / len(_df_f)):,.2f}" if len(_df_f) > 0 else "$ 0,00")

                # Reordenar columnas para mostrar USD junto a pesos
                _cols_gastos_vista = [
                    "PROPIEDAD", "PROPIETARIO", "FECHA", "CATEGORÍA", "DESCRIPCIÓN",
                    "MONTO ($)", "COTIZACIÓN USD", "MONTO (USD)",
                    "PROVEEDOR", "COMPROBANTE", "PAGADO POR", "OBSERVACIONES"
                ]
                st.dataframe(_df_f[_cols_gastos_vista], use_container_width=True, hide_index=True)

                # Exportar
                _csv_gastos = _df_f[_cols_gastos_vista].to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Exportar a CSV", _csv_gastos, "gastos_propiedades.csv", "text/csv")

        # ── SUBPESTAÑA 3: MÉTRICAS POR PROPIEDAD ────────────────────────
        with subtab_metricas:
            st.markdown("#### 📊 Ingresos vs. Salidas por Propiedad")

            conn = conectar_db()

            # ── Cargar ingresos desde pagos_historial ──
            _eid_m = st.session_state.get("empresa_id", 0)
            _where_m = "AND p.propietario = %s" if _pf_g_activo else ""
            _params_m = (_eid_m, _pf_g) if _pf_g_activo else (_eid_m,)

            _df_ingresos_raw = None
            with _pg_conn() as _conn_ir:
                with _conn_ir.cursor() as _cur_ir:
                    _cur_ir.execute(f"""
                SELECT
                    ph.propiedad                                                        AS propiedad,
                    COALESCE(p.propietario, '')                                        AS propietario,
                    ph.periodo                                                          AS periodo,
                    NULL                                                                AS inicio_contrato,
                    0                                                                   AS calc_duracion,
                    COALESCE(ph.monto_alquiler, 0)                                    AS alquiler,
                    COALESCE(ph.monto_cochera, 0)                                     AS cochera,
                    COALESCE(ph.monto_alquiler, 0) + COALESCE(ph.monto_cochera, 0)   AS total_ingreso,
                    0                                                                   AS gasto_admin,
                    COALESCE(ph.monto_imp_inmobiliario, 0)                            AS imp_inmobiliario,
                    0                                                                   AS alquiler_usd,
                    0                                                                   AS cochera_usd,
                    0                                                                   AS total_ingreso_usd,
                    0                                                                   AS gasto_admin_usd,
                    0                                                                   AS imp_inmobiliario_usd
                FROM pagos_historial ph
                LEFT JOIN propiedades p ON ph.propiedad = p.alias_propiedad AND p.empresa_id = ph.empresa_id
                WHERE ph.empresa_id = %s {_where_m}
                ORDER BY ph.periodo
            """, _params_m)
                    _rows_ir = _cur_ir.fetchall()
                    _cols_ir = [x.name for x in _cur_ir.description]
            _df_ingresos_raw = pd.DataFrame([dict(r) for r in _rows_ir], columns=_cols_ir) if _rows_ir else pd.DataFrame(columns=_cols_ir)

            # ── Calcular mes calendario desde el período del contrato ──
            # periodo tiene formato "Mes N de M" (ej. "Mes 1 de 12")
            # mes_calendario = inicio_contrato + (N-1) meses → YYYY-MM
            if not _df_ingresos_raw.empty:
                import re as _re
                import dateutil.relativedelta

                def _extraer_nro_mes(p):
                    try:
                        m = _re.search(r'Mes\s+(\d+)', str(p))
                        return int(m.group(1)) if m else 0
                    except Exception:
                        return 0

                def _calc_mes_cal(row):
                    try:
                        nro = _extraer_nro_mes(row["periodo"])
                        if nro == 0:
                            return ""
                        inicio = pd.to_datetime(row["inicio_contrato"])
                        cal = inicio + dateutil.relativedelta.relativedelta(months=nro - 1)
                        return cal.strftime("%Y-%m")
                    except Exception:
                        return ""

                _df_ingresos_raw["nro_periodo"]    = _df_ingresos_raw["periodo"].apply(_extraer_nro_mes)
                _df_ingresos_raw["mes_calendario"] = _df_ingresos_raw.apply(_calc_mes_cal, axis=1)
            else:
                _df_ingresos_raw["nro_periodo"]    = pd.Series(dtype=int)
                _df_ingresos_raw["mes_calendario"] = pd.Series(dtype=str)

            # ── Cargar gastos desde gastos_propiedades ──
            _df_gastos_raw = None
            with _pg_conn() as _conn_gr:
                with _conn_gr.cursor() as _cur_gr:
                    _cur_gr.execute(f"""
                SELECT
                    p.alias_propiedad                              AS propiedad,
                    COALESCE(p.propietario, '')                   AS propietario,
                    TO_CHAR(gp.fecha::date, 'YYYY-MM')          AS periodo,
                    SUM(gp.monto)                                 AS total_gasto,
                    0                                             AS total_gasto_usd
                FROM gastos_propiedades gp
                JOIN propiedades p ON gp.propiedad_id = p.id AND p.empresa_id = gp.empresa_id
                WHERE gp.empresa_id = %s {"AND p.propietario = %s" if _pf_g_activo else ""}
                GROUP BY p.alias_propiedad, p.propietario, TO_CHAR(gp.fecha::date, 'YYYY-MM')
                ORDER BY periodo
            """, _params_m)
                    _rows_ir = _cur_ir.fetchall()
                    _cols_ir = [x.name for x in _cur_ir.description]
            _df_ingresos_raw = pd.DataFrame([dict(r) for r in _rows_ir], columns=_cols_ir) if _rows_ir else pd.DataFrame(columns=_cols_ir)

            conn.close()

            if _df_ingresos_raw.empty and _df_gastos_raw.empty:
                st.info("Aún no hay datos de ingresos ni gastos para mostrar métricas.")
            else:
                st.caption("💡 Los valores en USD corresponden a las cotizaciones registradas al momento de cada cobro/gasto.")

                # ── Extraer años disponibles desde mes_calendario (ingresos) y periodo (gastos) ──
                _cal_ing = (
                    _df_ingresos_raw["mes_calendario"].dropna()
                    if not _df_ingresos_raw.empty else pd.Series(dtype=str)
                )
                _cal_gas = (
                    _df_gastos_raw["periodo"].dropna().astype(str).str[:7]
                    if not _df_gastos_raw.empty else pd.Series(dtype=str)
                )
                _todos_cal = pd.concat([_cal_ing, _cal_gas])
                _todos_cal = _todos_cal[_todos_cal.str.match(r"^\d{4}-\d{2}$", na=False)]
                _anios_disp = sorted(_todos_cal.str[:4].unique(), reverse=True)
                _meses_nombres = {
                    "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
                    "05": "Mayo",  "06": "Junio",   "07": "Julio", "08": "Agosto",
                    "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
                }

                # ── Lista de propietarios disponibles ──
                _propietarios_disp = []
                if not _pf_g_activo:
                    _todos_props = pd.concat([
                        _df_ingresos_raw[["propietario"]] if not _df_ingresos_raw.empty else pd.DataFrame(columns=["propietario"]),
                        _df_gastos_raw[["propietario"]]   if not _df_gastos_raw.empty   else pd.DataFrame(columns=["propietario"])
                    ])
                    _propietarios_disp = sorted(_todos_props["propietario"].dropna().unique().tolist())
                    _propietarios_disp = [p for p in _propietarios_disp if p.strip()]

                # ── Opciones de período de contrato (ej. "Mes 1 de 12") ──
                _periodos_contrato_disp = []
                if not _df_ingresos_raw.empty:
                    _pc_vals = (
                        _df_ingresos_raw[["nro_periodo", "periodo"]]
                        .dropna()
                        .drop_duplicates()
                        .sort_values("nro_periodo")
                    )
                    _periodos_contrato_disp = _pc_vals["periodo"].tolist()

                # ── Filtros ──
                st.markdown("**🔎 Filtros**")

                # Fila 1: Propietario + Propiedad
                if not _pf_g_activo and _propietarios_disp:
                    _mcol0, _mcol1 = st.columns(2)
                    _f_propietario_m = _mcol0.selectbox("👤 Propietario:", ["Todos"] + _propietarios_disp, key="met_propietario")
                else:
                    _mcol1, = st.columns([1])
                    _f_propietario_m = _pf_g if _pf_g_activo else "Todos"

                _props_lista_m = ["Todas"] + sorted(_props_gasto["alias_propiedad"].tolist()) if not _props_gasto.empty else ["Todas"]
                _f_prop_m = _mcol1.selectbox("🏠 Propiedad:", _props_lista_m, key="met_prop")

                # Fila 2: Mes calendario (Año + Mes) + Período de contrato
                _fcol1, _fcol2, _fcol3 = st.columns(3)
                _anio_sel      = _fcol1.selectbox("📅 Año (calendario):", ["Todos"] + _anios_disp, key="met_anio")
                _meses_disp    = ["Todos"] + [f"{k} – {v}" for k, v in _meses_nombres.items()]
                _mes_sel_label = _fcol2.selectbox("📆 Mes calendario:", _meses_disp, key="met_mes",
                                                  help="Filtra por el mes real del calendario en que corresponde el cobro")
                _mes_sel       = _mes_sel_label[:2] if _mes_sel_label != "Todos" else "Todos"

                _f_periodo_contrato = _fcol3.selectbox(
                    "📋 Período del contrato:",
                    ["Todos"] + _periodos_contrato_disp,
                    key="met_periodo_contrato",
                    help="Filtra por el número de mes dentro del contrato (ej: Mes 1 de 12 = primer mes)"
                )

                # ── Selector de moneda ──
                _moneda_sel = st.radio(
                    "💱 Ver métricas en:",
                    ["$ Pesos", "U$S Dólares"],
                    horizontal=True,
                    key="met_moneda"
                )
                _ver_usd = (_moneda_sel == "U$S Dólares")

                # ── Aplicar filtros a ingresos ──
                _dfi = _df_ingresos_raw.copy()
                if not _dfi.empty:
                    if _f_propietario_m != "Todos":
                        _dfi = _dfi[_dfi["propietario"] == _f_propietario_m]
                    if _f_prop_m != "Todas":
                        _dfi = _dfi[_dfi["propiedad"] == _f_prop_m]
                    # Filtro por período del contrato ("Mes N de M")
                    if _f_periodo_contrato != "Todos":
                        _dfi = _dfi[_dfi["periodo"] == _f_periodo_contrato]
                    # Filtro por mes calendario (calculado desde inicio_contrato + nro_periodo)
                    if _anio_sel != "Todos":
                        _dfi = _dfi[_dfi["mes_calendario"].str[:4] == _anio_sel]
                    if _mes_sel != "Todos":
                        _dfi = _dfi[_dfi["mes_calendario"].str[5:7] == _mes_sel]

                # ── Aplicar filtros a gastos (su campo periodo ya es YYYY-MM) ──
                _dfg = _df_gastos_raw.copy()
                if not _dfg.empty:
                    _dfg["periodo"] = _dfg["periodo"].astype(str).str[:7]
                    if _f_propietario_m != "Todos":
                        _dfg = _dfg[_dfg["propietario"] == _f_propietario_m]
                    if _f_prop_m != "Todas":
                        _dfg = _dfg[_dfg["propiedad"] == _f_prop_m]
                    if _anio_sel != "Todos":
                        _dfg = _dfg[_dfg["periodo"].str[:4] == _anio_sel]
                    if _mes_sel != "Todos":
                        _dfg = _dfg[_dfg["periodo"].str[5:7] == _mes_sel]
                    # Si se filtra por período de contrato, alinear gastos al mismo mes calendario
                    if _f_periodo_contrato != "Todos" and not _dfi.empty:
                        _meses_cal_dfi = _dfi["mes_calendario"].dropna().unique()
                        _dfg = _dfg[_dfg["periodo"].isin(_meses_cal_dfi)]

                # ── Totales en PESOS ──
                _total_ing     = _dfi["total_ingreso"].sum()    if not _dfi.empty else 0.0
                _total_alq     = _dfi["alquiler"].sum()         if not _dfi.empty else 0.0
                _total_coch    = _dfi["cochera"].sum()          if not _dfi.empty else 0.0
                _total_gas     = _dfg["total_gasto"].sum()      if not _dfg.empty else 0.0
                _total_adm     = _dfi["gasto_admin"].sum()      if not _dfi.empty else 0.0
                _total_imp_inm = _dfi["imp_inmobiliario"].sum() if not _dfi.empty else 0.0
                _total_pasivos = _total_gas + _total_adm + _total_imp_inm
                _balance       = _total_ing - _total_pasivos

                # ── Totales en USD (desde BD) ──
                _total_ing_usd     = _dfi["total_ingreso_usd"].sum()    if not _dfi.empty else 0.0
                _total_alq_usd     = _dfi["alquiler_usd"].sum()         if not _dfi.empty else 0.0
                _total_coch_usd    = _dfi["cochera_usd"].sum()          if not _dfi.empty else 0.0
                _total_gas_usd     = _dfg["total_gasto_usd"].sum()      if not _dfg.empty else 0.0
                _total_adm_usd     = _dfi["gasto_admin_usd"].sum()      if not _dfi.empty else 0.0
                _total_imp_inm_usd = _dfi["imp_inmobiliario_usd"].sum() if not _dfi.empty else 0.0
                _total_pasivos_usd = _total_gas_usd + _total_adm_usd + _total_imp_inm_usd
                _balance_usd       = _total_ing_usd - _total_pasivos_usd

                # ── KPIs según moneda seleccionada ──
                if not _ver_usd:
                    # ── KPIs en PESOS ──
                    st.markdown("**📥 Ingresos — $**")
                    _km1, _km2, _km3 = st.columns(3)
                    _km1.metric("💰 Total Ingresos",  f"$ {_total_ing:,.2f}", help="Alquiler + Cochera del período filtrado")
                    _km2.metric("🏠 Alquiler",        f"$ {_total_alq:,.2f}")
                    _km3.metric("🚗 Cochera",         f"$ {_total_coch:,.2f}")

                    st.markdown("**📤 Pasivos — $**")
                    _kp1, _kp2, _kp3 = st.columns(3)
                    _kp1.metric("🔧 Gastos Propiedad",    f"$ {_total_gas:,.2f}")
                    _kp2.metric("🏢 Gasto Adm.",          f"$ {_total_adm:,.2f}")
                    _kp3.metric("🏛️ Imp. Inmobiliario",   f"$ {_total_imp_inm:,.2f}")

                    _bm1, _bm2 = st.columns([1, 3])
                    _color_balance = "normal" if _balance >= 0 else "inverse"
                    _bm1.metric("📈 Balance Neto ($)", f"$ {_balance:,.2f}", delta_color=_color_balance)
                else:
                    # ── KPIs en USD ──
                    st.markdown("**📥 Ingresos — U$S**")
                    _ku1, _ku2, _ku3 = st.columns(3)
                    _ku1.metric("💰 Total Ingresos",  f"U$S {_total_ing_usd:,.2f}", help="Alquiler + Cochera en USD al tipo de cambio de cada cobro")
                    _ku2.metric("🏠 Alquiler",        f"U$S {_total_alq_usd:,.2f}")
                    _ku3.metric("🚗 Cochera",         f"U$S {_total_coch_usd:,.2f}")

                    st.markdown("**📤 Pasivos — U$S**")
                    _kpu1, _kpu2, _kpu3 = st.columns(3)
                    _kpu1.metric("🔧 Gastos Propiedad",   f"U$S {_total_gas_usd:,.2f}")
                    _kpu2.metric("🏢 Gasto Adm.",         f"U$S {_total_adm_usd:,.2f}")
                    _kpu3.metric("🏛️ Imp. Inmobiliario",  f"U$S {_total_imp_inm_usd:,.2f}")

                    _bu1, _bu2 = st.columns([1, 3])
                    _color_balance_usd = "normal" if _balance_usd >= 0 else "inverse"
                    _bu1.metric("📈 Balance Neto (U$S)", f"U$S {_balance_usd:,.2f}", delta_color=_color_balance_usd)

                st.divider()

                # ── Tabla comparativa por período ──
                st.markdown("##### 📋 Detalle por Período")

                # Agrupar ingresos por propiedad + mes_calendario (clave para merge con gastos)
                # Conservar "periodo" (texto del contrato) como primer valor del grupo
                _dfi_grp = (
                    _dfi.groupby(["propiedad", "mes_calendario"], as_index=False)
                    .agg(
                        periodo_contrato=("periodo", "first"),
                        alquiler=("alquiler", "sum"),
                        cochera=("cochera", "sum"),
                        total_ingreso=("total_ingreso", "sum"),
                        gasto_admin=("gasto_admin", "sum"),
                        imp_inmobiliario=("imp_inmobiliario", "sum"),
                        alquiler_usd=("alquiler_usd", "sum"),
                        cochera_usd=("cochera_usd", "sum"),
                        total_ingreso_usd=("total_ingreso_usd", "sum"),
                        gasto_admin_usd=("gasto_admin_usd", "sum"),
                        imp_inmobiliario_usd=("imp_inmobiliario_usd", "sum"),
                    )
                    if not _dfi.empty
                    else pd.DataFrame(columns=["propiedad", "mes_calendario", "periodo_contrato",
                                               "alquiler", "cochera", "total_ingreso",
                                               "gasto_admin", "imp_inmobiliario", "alquiler_usd", "cochera_usd",
                                               "total_ingreso_usd", "gasto_admin_usd", "imp_inmobiliario_usd"])
                )
                # Renombrar mes_calendario → periodo para el merge con gastos (que usa YYYY-MM)
                _dfi_grp = _dfi_grp.rename(columns={"mes_calendario": "periodo"})

                _dfg_grp_cols = ["propiedad", "periodo", "total_gasto", "total_gasto_usd"]
                _df_merge = pd.merge(
                    _dfi_grp,
                    _dfg[_dfg_grp_cols] if not _dfg.empty else pd.DataFrame(columns=_dfg_grp_cols),
                    on=["propiedad", "periodo"],
                    how="outer"
                )
                # Rellenar numéricos con 0, pero preservar strings como periodo_contrato
                _numeric_cols_merge = [c for c in _df_merge.columns if c not in ("propiedad", "periodo", "periodo_contrato")]
                _df_merge[_numeric_cols_merge] = _df_merge[_numeric_cols_merge].fillna(0)
                if "periodo_contrato" in _df_merge.columns:
                    _df_merge["periodo_contrato"] = _df_merge["periodo_contrato"].fillna("")

                if not _df_merge.empty:
                    _df_merge["total_pasivos"]     = _df_merge["total_gasto"] + _df_merge["gasto_admin"] + _df_merge["imp_inmobiliario"]
                    _df_merge["total_pasivos_usd"] = _df_merge["total_gasto_usd"] + _df_merge["gasto_admin_usd"] + _df_merge["imp_inmobiliario_usd"]
                    _df_merge["balance"]           = _df_merge["total_ingreso"] - _df_merge["total_pasivos"]
                    _df_merge["balance_usd"]       = _df_merge["total_ingreso_usd"] - _df_merge["total_pasivos_usd"]
                    _df_merge = _df_merge.sort_values(["propiedad", "periodo"])

                    # Formatear periodo (YYYY-MM) a "Octubre 2024"
                    def _fmt_mes_anio(v):
                        try:
                            partes = str(v)[:7].split("-")
                            return f"{_meses_nombres.get(partes[1], partes[1])} {partes[0]}"
                        except Exception:
                            return str(v)

                    _df_display = _df_merge.copy()
                    _df_display["periodo"] = _df_display["periodo"].apply(_fmt_mes_anio)
                    _df_display = _df_display.rename(columns={
                        "propiedad":             "PROPIEDAD",
                        "periodo":               "MES / AÑO",
                        "periodo_contrato":      "PERÍODO CONTRATO",
                        "alquiler":              "ALQUILER ($)",
                        "cochera":               "COCHERA ($)",
                        "total_ingreso":         "TOTAL INGRESO ($)",
                        "alquiler_usd":          "ALQUILER (USD)",
                        "cochera_usd":           "COCHERA (USD)",
                        "total_ingreso_usd":     "TOTAL INGRESO (USD)",
                        "total_gasto":           "GASTOS PROP. ($)",
                        "total_gasto_usd":       "GASTOS PROP. (USD)",
                        "gasto_admin":           "GASTO ADM. ($)",
                        "gasto_admin_usd":       "GASTO ADM. (USD)",
                        "imp_inmobiliario":      "IMP. INMO. ($)",
                        "imp_inmobiliario_usd":  "IMP. INMO. (USD)",
                        "total_pasivos":         "TOTAL PASIVOS ($)",
                        "total_pasivos_usd":     "TOTAL PASIVOS (USD)",
                        "balance":               "BALANCE ($)",
                        "balance_usd":           "BALANCE (USD)",
                    })

                    def _color_balance_row(val):
                        color = "#d4edda" if val >= 0 else "#f8d7da"
                        return f"background-color: {color}"

                    _no_fmt = ("PROPIEDAD", "MES / AÑO", "PERÍODO CONTRATO")
                    if not _ver_usd:
                        _cols_display = [
                            "PROPIEDAD", "MES / AÑO", "PERÍODO CONTRATO",
                            "ALQUILER ($)", "COCHERA ($)", "TOTAL INGRESO ($)",
                            "GASTOS PROP. ($)", "GASTO ADM. ($)", "IMP. INMO. ($)",
                            "TOTAL PASIVOS ($)", "BALANCE ($)",
                        ]
                        _fmt_dict = {c: "$ {:,.2f}" for c in _cols_display if c not in _no_fmt}
                        _styled = _df_display[_cols_display].style.map(
                            _color_balance_row, subset=["BALANCE ($)"]
                        ).format(_fmt_dict)
                        _csv_nombre = "metricas_pesos.csv"
                    else:
                        _cols_display = [
                            "PROPIEDAD", "MES / AÑO", "PERÍODO CONTRATO",
                            "ALQUILER (USD)", "COCHERA (USD)", "TOTAL INGRESO (USD)",
                            "GASTOS PROP. (USD)", "GASTO ADM. (USD)", "IMP. INMO. (USD)",
                            "TOTAL PASIVOS (USD)", "BALANCE (USD)",
                        ]
                        _fmt_dict = {c: "U$S {:,.2f}" for c in _cols_display if c not in _no_fmt}
                        _styled = _df_display[_cols_display].style.map(
                            _color_balance_row, subset=["BALANCE (USD)"]
                        ).format(_fmt_dict)
                        _csv_nombre = "metricas_dolares.csv"

                    st.dataframe(_styled, use_container_width=True, hide_index=True)

                    # Exportar
                    _csv_m = _df_display[_cols_display].to_csv(index=False).encode("utf-8")
                    st.download_button("⬇️ Exportar métricas a CSV", _csv_m, _csv_nombre, "text/csv")

                    # ── Gráfico de barras agrupadas ──
                    st.markdown("##### 📊 Gráfico Ingresos vs. Gastos")
                    if not _ver_usd:
                        _df_chart = _df_merge.groupby("periodo", as_index=False).agg(
                            Ingresos=("total_ingreso", "sum"),
                            Gastos=("total_gasto", "sum")
                        ).sort_values("periodo")
                    else:
                        _df_chart = _df_merge.groupby("periodo", as_index=False).agg(
                            Ingresos=("total_ingreso_usd", "sum"),
                            Gastos=("total_gasto_usd", "sum")
                        ).sort_values("periodo")

                    if not _df_chart.empty:
                        import altair as alt
                        _df_long = _df_chart.melt(id_vars="periodo", var_name="Tipo", value_name="Monto")
                        _fmt_tooltip = "$,.2f" if not _ver_usd else ",.2f"
                        _y_title = "$ Monto" if not _ver_usd else "U$S Monto"
                        _chart = (
                            alt.Chart(_df_long)
                            .mark_bar()
                            .encode(
                                x=alt.X("periodo:N", title="Período", sort=None),
                                y=alt.Y("Monto:Q", title=_y_title),
                                color=alt.Color("Tipo:N", scale=alt.Scale(
                                    domain=["Ingresos", "Gastos"],
                                    range=["#28a745", "#dc3545"]
                                )),
                                xOffset="Tipo:N",
                                tooltip=["periodo", "Tipo", alt.Tooltip("Monto:Q", format=_fmt_tooltip)]
                            )
                            .properties(height=350)
                        )
                        st.altair_chart(_chart, use_container_width=True)
                else:
                    st.info("No hay datos combinados para mostrar con los filtros seleccionados.")
