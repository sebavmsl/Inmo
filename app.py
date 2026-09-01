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

import math
import psycopg2
import psycopg2.extras
import requests
import decimal
from io import BytesIO
from contextlib import contextmanager

# =====================================================================
# VERSIÓN DEL ARCHIVO — mantener el "v1" fijo y subir de a uno los
# últimos 3 dígitos en cada nueva versión generada (v1.001 → v1.002 →
# v1.003 ...). Se muestra como sello fijo en la esquina inferior derecha.
# =====================================================================
APP_VERSION = "v1.174"

TERMINOS_TEXTO = """
## Términos y Condiciones de Uso
### Sistema de Gestión Inmobiliaria — Versión 1.0

---

**1. Aceptación de los Términos**

Al acceder y utilizar el Sistema de Gestión Inmobiliaria (en adelante, "el Sistema"), el usuario declara haber leído, comprendido y aceptado en su totalidad los presentes Términos y Condiciones. Si no está de acuerdo con alguno de estos términos, deberá abstenerse de utilizar el Sistema.

---

**2. Descripción del Servicio**

El Sistema es una plataforma de software como servicio (SaaS) diseñada para la gestión de contratos de locación, registro de cobros, emisión de comprobantes y administración de propiedades e inquilinos. El acceso al Sistema se otorga mediante credenciales personales e intransferibles.

---

**3. Protección de Datos Personales**

El Sistema almacena y procesa datos personales de terceros (inquilinos, propietarios y otros) en cumplimiento de la **Ley 25.326 de Protección de Datos Personales de la República Argentina** y su normativa complementaria.

- **Responsable del tratamiento de datos:** La empresa u organización que contrata el uso del Sistema (en adelante, "el Operador") es responsable del tratamiento de los datos personales ingresados.
- **El Desarrollador** actúa como encargado del tratamiento en su carácter de proveedor tecnológico, y no accede, comercializa ni cede los datos a terceros salvo requerimiento legal.
- El Operador es responsable de obtener los consentimientos necesarios de los titulares de los datos personales conforme a la normativa vigente.
- Los datos se almacenan en infraestructura cloud de terceros bajo estándares de seguridad internacionales, con cifrado en tránsito y en reposo, acceso restringido y políticas de respaldo periódico, conforme a las mejores prácticas de la industria tecnológica.
- El Operador tiene derecho a solicitar la eliminación de sus datos mediante comunicación formal al Desarrollador. Esta solicitud podrá realizarse una vez por año calendario, pudiendo estar sujeta a limitaciones técnicas en su ejecución.

---

**4. Responsabilidad por Cálculos e Índices**

El Sistema realiza cálculos automáticos basados en índices oficiales publicados por el BCRA (ICL) y el INDEC (IPC), obtenidos de fuentes públicas.

- El Desarrollador **no garantiza** la exactitud, disponibilidad o actualización en tiempo real de dichos índices.
- Los valores calculados son **orientativos** y no reemplazan la verificación con las fuentes oficiales.
- El Operador es responsable de verificar los montos antes de emitir comprobantes o impactar cobros.
- El Desarrollador no será responsable por pérdidas económicas derivadas de errores en los cálculos automáticos.

---

**5. Condiciones del Servicio SaaS**

- El acceso al Sistema está sujeto al pago de la tarifa acordada entre el Operador y el Desarrollador.
- El Desarrollador se reserva el derecho de suspender el acceso ante falta de pago o uso indebido del Sistema.
- El Desarrollador podrá actualizar, modificar o interrumpir el Sistema con previo aviso de 15 días corridos.
- El Desarrollador realiza todos los esfuerzos técnicos razonables para garantizar la máxima disponibilidad del Sistema, implementando medidas de monitoreo, redundancia y mantenimiento preventivo. No obstante, la disponibilidad puede verse afectada por factores ajenos al control del Desarrollador, tales como fallas en servicios de infraestructura de terceros, conectividad de red o causas de fuerza mayor.

---

**6. Uso Aceptable**

El Operador y sus usuarios se comprometen a:

- Utilizar el Sistema exclusivamente para los fines de gestión inmobiliaria para los que fue diseñado.
- No intentar acceder a datos de otras organizaciones ni vulnerar la seguridad del Sistema.
- No compartir credenciales de acceso con personas no autorizadas.
- No utilizar el Sistema para actividades ilegales o contrarias a la normativa vigente.

---

**7. Confidencialidad**

El Desarrollador se compromete a mantener la confidencialidad de toda la información del Operador y no divulgarla a terceros, salvo requerimiento judicial o legal expreso.

---

**8. Propiedad Intelectual**

El Sistema, su código fuente, diseño y funcionalidades son propiedad exclusiva del Desarrollador. El contrato de SaaS otorga una licencia de uso no exclusiva e intransferible, sin que ello implique cesión de derechos sobre el software.

---

**9. Modificaciones a los Términos**

El Desarrollador podrá modificar los presentes Términos con un preaviso de 15 días mediante notificación dentro del Sistema. El uso continuado del Sistema tras dicho período implica la aceptación de los nuevos términos.

---

**10. Jurisdicción**

Para cualquier controversia derivada del uso del Sistema, las partes se someten a la jurisdicción de los Tribunales Ordinarios de la ciudad de Villa Mercedes, provincia de San Luis, República Argentina, renunciando a cualquier otro fuero que pudiera corresponder.
"""

# Configuración de logging — debe ir antes de cualquier código que loggee
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── Compatibilidad Streamlit Cloud / Render ──────────────────────────────────
# En Render no hay secrets.toml — se usan variables de entorno
def _get_secret(section, key, env_var=None):
    """Lee de st.secrets (Streamlit Cloud) o variables de entorno (Render)."""
    # 1. Intentar st.secrets
    try:
        val = st.secrets[section][key]
        if val is not None:
            return str(val)
    except Exception:
        pass

    # 2. Variables de entorno — probar todos los formatos posibles
    _candidates = [
        f"{section}__{key}",           # superadmin__username
        f"{section.upper()}__{key.upper()}",  # SUPERADMIN__USERNAME
        f"{section}_{key}",            # superadmin_username
        f"{section.upper()}_{key.upper()}",   # SUPERADMIN_USERNAME
    ]
    if env_var:
        _candidates.insert(0, env_var)
        _candidates.insert(1, env_var.lower())

    for _c in _candidates:
        v = os.environ.get(_c)
        if v:
            return v

    # 3. Buscar ignorando mayúsculas
    _env_lower = {k.lower(): v for k, v in os.environ.items()}
    for _c in _candidates:
        v = _env_lower.get(_c.lower())
        if v:
            return v

    return None

# ── PostgreSQL / Supabase ────────────────────────────────────────────────────
@st.cache_resource
def _get_pg_dsn():
    dsn = (
        _get_secret("database", "supabase_url", "SUPABASE_URL") or
        _get_secret("database", "url", "DATABASE_URL") or
        _get_secret("database", "connection_string") or
        os.environ.get("supabase_url") or
        os.environ.get("DATABASE_URL") or
        os.environ.get("database_url")
    )
    if not dsn:
        raise RuntimeError("Falta conexión a BD. Configurá supabase_url en variables de entorno o secrets.toml")
    m = re.match(r'postgresql://([^:]+):([^@]+)@db\.([a-z0-9]+)\.supabase\.co(?::\d+)?/(\S+)', dsn)
    if m:
        user, password, ref, db_ = m.groups()
        if '.' not in user:
            user = f'postgres.{ref}'
        dsn = f'postgresql://{user}:{password}@aws-1-sa-east-1.pooler.supabase.com:6543/{db_}'
    elif ':5432/' in dsn:
        dsn = dsn.replace(':5432/', ':6543/')
    return dsn

@st.cache_resource
def _get_pool():
    """Pool de conexiones persistente — se crea una sola vez por instancia."""
    from psycopg2 import pool as pg_pool
    return pg_pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=20,
        dsn=_get_pg_dsn(),
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )

@contextmanager
def _pg_conn():
    """Obtiene una conexión del pool, hace commit/rollback y la devuelve."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)

class _PooledConnection:
    """
    Wrapper sobre una conexión psycopg2 obtenida del pool.
    Delega todos los atributos a la conexión real, pero sobreescribe
    close() para devolver la conexión al pool en vez de cerrarla.
    Necesario porque psycopg2 (extensión C) no permite monkey-patch
    de atributos nativos como conn.close directamente.
    """
    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn

    def close(self):
        try:
            self._pool.putconn(self._conn)
        except Exception:
            self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            try:
                self._conn.rollback()
            except Exception:
                pass
        else:
            try:
                self._conn.commit()
            except Exception:
                pass
        self.close()
        return False


def conectar_db():
    """Obtiene conexión del pool envuelta en _PooledConnection.
    Llamar conn.close() la devuelve al pool en vez de cerrarla."""
    pool = _get_pool()
    conn = pool.getconn()
    conn.autocommit = False
    return _PooledConnection(pool, conn)

def conectar_db_central():
    """Igual que conectar_db — en Postgres es la misma BD."""
    return conectar_db()

@st.cache_data(ttl=300)
def _get_empresa_id_cached(archivo_db: str):
    """Cache de empresa_id por 5 min — evita query repetida en cada rerun."""
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

def _get_empresa_id(archivo_db: str):
    return _get_empresa_id_cached(archivo_db)


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
    filas_servicios,
    total, metodo_pago, nombre_empresa,
    monto_abonado=None, saldo_pendiente=0.0,
    mes_anio="",
    observaciones="",
    es_reimpresion=False, fecha_original="", id_registro="",
    prox_actualizacion="",
    aviso_actualizacion_proximo=False,
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
        f"<b>Período:</b> {periodo}" + (f" — {mes_anio}" if mes_anio else ""),
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
    story += [dt, Spacer(1, 6)]
    if prox_actualizacion:
        prox_tbl = Table([[
            _p("<b>Próxima Actualización:</b>"),
            _p(prox_actualizacion, color=colors.HexColor("#c05621"), bold=True),
        ]], colWidths=[doc.width*0.25, doc.width*0.75])
        prox_tbl.setStyle(TableStyle([
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
            ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#fffaf0")),
            ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#fbd38d")),
            ("LEFTPADDING",(0,0),(-1,-1),8),
        ]))
        story += [prox_tbl, Spacer(1, 10)]
    else:
        story.append(Spacer(1, 10))

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
    story += [it, Spacer(1, 10)]

    # Monto abonado y saldo pendiente
    if monto_abonado is not None:
        _monto_ab = float(monto_abonado)
        _saldo_pd = float(saldo_pendiente) if saldo_pendiente else 0.0
        VERDE    = colors.HexColor("#276749")
        VERDE_BG = colors.HexColor("#f0fff4")
        ROJO_BG  = colors.HexColor("#fff5f5")
        ROJO     = colors.HexColor("#c53030")

        pago_rows = [[
            _p("MONTO ABONADO POR EL INQUILINO", bold=True, color=VERDE),
            _p(f"$ {_monto_ab:,.2f}", bold=True, color=VERDE, align=TA_RIGHT),
        ]]
        pago_tbl = Table(pago_rows, colWidths=[doc.width*0.72, doc.width*0.28])
        pago_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), VERDE_BG),
            ("TOPPADDING",    (0,0),(-1,-1), 8),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ]))
        story.append(pago_tbl)

        if _saldo_pd > 0:
            saldo_rows = [[
                _p("SALDO PENDIENTE", bold=True, color=ROJO),
                _p(f"$ {_saldo_pd:,.2f}", bold=True, color=ROJO, align=TA_RIGHT),
            ]]
            saldo_tbl = Table(saldo_rows, colWidths=[doc.width*0.72, doc.width*0.28])
            saldo_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), ROJO_BG),
                ("TOPPADDING",    (0,0),(-1,-1), 8),
                ("BOTTOMPADDING", (0,0),(-1,-1), 8),
                ("LEFTPADDING",   (0,0),(-1,-1), 8),
                ("RIGHTPADDING",  (0,0),(-1,-1), 8),
            ]))
            story.append(saldo_tbl)

    story.append(Spacer(1, 14))

    # Método de pago
    story.append(_p(f"<b>Forma de Cancelación:</b> {metodo_pago}"))
    if observaciones and str(observaciones).strip():
        story += [Spacer(1,4), _p(f"<b>Observaciones:</b> {observaciones}")]

    # Aviso de próxima actualización si corresponde en el período siguiente
    if aviso_actualizacion_proximo and prox_actualizacion:
        story.append(Spacer(1, 10))
        aviso_rows = [[_p(
            f"⚠️  AVISO: El próximo período corresponde aplicar una <b>ACTUALIZACIÓN DE ALQUILER</b> "
            f"según el índice pactado en el contrato. Fecha de actualización: <b>{prox_actualizacion}</b>.",
            size=9.5, color=colors.HexColor("#7b341e"),
        )]]
        aviso_tbl = Table(aviso_rows, colWidths=[doc.width])
        aviso_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#fff3cd")),
            ("BOX",           (0,0),(-1,-1), 1, colors.HexColor("#f6ad55")),
            ("TOPPADDING",    (0,0),(-1,-1), 8),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
            ("LEFTPADDING",   (0,0),(-1,-1), 10),
            ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ]))
        story.append(aviso_tbl)

    # Firma
    story.append(Spacer(1, 30))
    ft = Table([["", _p("_________________________",
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


def generar_pdf_rendicion(
    propietario, periodo, fecha_emision, nombre_empresa,
    filas_propiedades,
    total_alquiler, total_cochera, total_expensas, total_cobrado, total_comision, total_neto,
    saldo_anterior, monto_a_liquidar, monto_liquidado, saldo_pendiente,
    filas_detalle_recibos=None, total_servicios=0.0, total_otros=0.0,
    filas_retencion_gastos=None, total_retencion_gastos=0.0,
):
    """Genera el PDF de rendición de cuentas a un propietario. Devuelve bytes."""
    filas_detalle_recibos = filas_detalle_recibos or []
    filas_retencion_gastos = filas_retencion_gastos or []
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
    VERDE     = colors.HexColor("#276749")
    VERDE_BG  = colors.HexColor("#f0fff4")
    ROJO      = colors.HexColor("#c53030")
    ROJO_BG   = colors.HexColor("#fff5f5")
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

    # Encabezado
    hd = [[
        _p("RENDICIÓN A PROPIETARIO", size=20, bold=True, color=AZUL_OSC),
        _p(f"<b>Período:</b> {periodo}<br/><b>Fecha Emisión:</b> {fecha_emision}",
           size=9.5, color=colors.HexColor("#555555"), align=TA_RIGHT),
    ]]
    ht = Table(hd, colWidths=[doc.width*0.5, doc.width*0.5])
    ht.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1),"BOTTOM"),
        ("LINEBELOW",     (0,0),(-1,-1), 2, AZUL_OSC),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
    ]))
    story += [ht, Spacer(1, 14)]

    # Datos
    dt = Table([[
        _p("<b>Propietario:</b>"), _p(propietario),
        _p("<b>Inmobiliaria:</b>"), _p(nombre_empresa),
    ]], colWidths=[doc.width*0.18, doc.width*0.32, doc.width*0.18, doc.width*0.32])
    dt.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))
    story += [dt, Spacer(1, 14)]

    # Detalle por propiedad
    story.append(_rl_seccion_titulo("Detalle por Propiedad", AZUL_MED, GRIS_BG, doc.width))
    story.append(Spacer(1, 6))
    rows = [[
        _p("Propiedad", bold=True, color=BLANCO),
        _p("Alquiler", bold=True, color=BLANCO, align=TA_RIGHT),
        _p("Cochera", bold=True, color=BLANCO, align=TA_RIGHT),
        _p("Expensas", bold=True, color=BLANCO, align=TA_RIGHT),
        _p("Comisión", bold=True, color=BLANCO, align=TA_RIGHT),
        _p("Neto", bold=True, color=BLANCO, align=TA_RIGHT),
    ]]
    for f in filas_propiedades:
        rows.append([
            _p(str(f["propiedad"]), size=9),
            _p(f"$ {f['alquiler']:,.2f}", size=9, align=TA_RIGHT),
            _p(f"$ {f['cochera']:,.2f}", size=9, align=TA_RIGHT),
            _p(f"$ {f['expensas']:,.2f}", size=9, align=TA_RIGHT),
            _p(f"$ {f['comision']:,.2f}", size=9, align=TA_RIGHT),
            _p(f"$ {f['neto']:,.2f}", size=9, bold=True, align=TA_RIGHT),
        ])
    n = len(rows)
    it = Table(rows, colWidths=[doc.width*0.30, doc.width*0.17, doc.width*0.15, doc.width*0.15, doc.width*0.14, doc.width*0.17])
    it.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), AZUL_MED),
        ("LINEBELOW",     (0,1),(-1,n-1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",    (0,0),(-1,-1), 6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",   (0,0),(-1,-1), 6), ("RIGHTPADDING", (0,0),(-1,-1),6),
        ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
    ]))
    story += [it, Spacer(1, 14)]

    # Detalle de recibos incluidos
    if filas_detalle_recibos:
        story.append(_rl_seccion_titulo("Detalle de Recibos Incluidos", AZUL_MED, GRIS_BG, doc.width))
        story.append(Spacer(1, 6))
        rows_d = [[
            _p("Fecha", bold=True, color=BLANCO, size=8),
            _p("Propiedad", bold=True, color=BLANCO, size=8),
            _p("Período", bold=True, color=BLANCO, size=8),
            _p("Alquiler", bold=True, color=BLANCO, size=8, align=TA_RIGHT),
            _p("Cochera", bold=True, color=BLANCO, size=8, align=TA_RIGHT),
            _p("Expensas", bold=True, color=BLANCO, size=8, align=TA_RIGHT),
            _p("Comisión", bold=True, color=BLANCO, size=8, align=TA_RIGHT),
            _p("Neto", bold=True, color=BLANCO, size=8, align=TA_RIGHT),
        ]]
        for f in filas_detalle_recibos:
            rows_d.append([
                _p(str(f.get("fecha", "")), size=7.5),
                _p(str(f.get("propiedad", "")), size=7.5),
                _p(str(f.get("periodo", "")), size=7.5),
                _p(f"$ {float(f.get('alquiler', 0)):,.2f}", size=7.5, align=TA_RIGHT),
                _p(f"$ {float(f.get('cochera', 0)):,.2f}", size=7.5, align=TA_RIGHT),
                _p(f"$ {float(f.get('expensas', 0)):,.2f}", size=7.5, align=TA_RIGHT),
                _p(f"$ {float(f.get('comision', 0)):,.2f}", size=7.5, align=TA_RIGHT),
                _p(f"$ {float(f.get('neto', 0)):,.2f}", size=7.5, bold=True, align=TA_RIGHT),
            ])
        nd = len(rows_d)
        dt2 = Table(rows_d, colWidths=[doc.width*0.13, doc.width*0.24, doc.width*0.14, doc.width*0.13,
                                        doc.width*0.12, doc.width*0.12, doc.width*0.12, doc.width*0.13])
        dt2.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0), AZUL_MED),
            ("LINEBELOW",     (0,1),(-1,nd-1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING",    (0,0),(-1,-1), 5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("LEFTPADDING",   (0,0),(-1,-1), 5), ("RIGHTPADDING", (0,0),(-1,-1),5),
            ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
        ]))
        story += [dt2, Spacer(1, 14)]

    # Totales del período
    story.append(_rl_seccion_titulo("Totales del Período", AZUL_MED, GRIS_BG, doc.width))
    story.append(Spacer(1, 6))
    tot_rows = [
        [_p("Total Cobrado (Alquiler + Cochera + Expensas)"), _p(f"$ {total_cobrado:,.2f}", align=TA_RIGHT)],
        [_p("Comisión Administrativa (–)"), _p(f"$ {total_comision:,.2f}", align=TA_RIGHT)],
        [_p("NETO A RENDIR — ESTE PERÍODO", bold=True, color=AZUL_OSC),
         _p(f"$ {total_neto:,.2f}", bold=True, color=AZUL_OSC, align=TA_RIGHT)],
    ]
    nt = len(tot_rows)
    tt = Table(tot_rows, colWidths=[doc.width*0.72, doc.width*0.28])
    tt.setStyle(TableStyle([
        ("BACKGROUND",    (0,nt-1),(-1,nt-1), AZUL_CLAR),
        ("LINEBELOW",     (0,0),(-1,nt-2), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",    (0,0),(-1,-1), 7), ("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("LEFTPADDING",   (0,0),(-1,-1), 8), ("RIGHTPADDING", (0,0),(-1,-1),8),
    ]))
    story += [tt, Spacer(1, 14)]

    # Informativo: Servicios y Otros (no se descuentan del Neto a Rendir)
    if total_servicios > 0.01 or total_otros > 0.01:
        GRIS_INFO = colors.HexColor("#718096")
        info_rows = [[
            _p("Conceptos informativos (no afectan el Neto a Rendir)", size=9, color=GRIS_INFO),
            _p("", size=9),
        ]]
        if total_servicios > 0.01:
            info_rows.append([
                _p("Servicios (Imp. Inmob. + EDESAL + Gas + Municip. + OO.SS.)", size=9, color=GRIS_INFO),
                _p(f"$ {total_servicios:,.2f}", size=9, color=GRIS_INFO, align=TA_RIGHT),
            ])
        if total_otros > 0.01:
            info_rows.append([
                _p("Otros (Honorarios + Garantía)", size=9, color=GRIS_INFO),
                _p(f"$ {total_otros:,.2f}", size=9, color=GRIS_INFO, align=TA_RIGHT),
            ])
        it2 = Table(info_rows, colWidths=[doc.width*0.72, doc.width*0.28])
        it2.setStyle(TableStyle([
            ("LINEBELOW",     (0,0),(-1,-2), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING",    (0,0),(-1,-1), 5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("LEFTPADDING",   (0,0),(-1,-1), 8), ("RIGHTPADDING", (0,0),(-1,-1),8),
        ]))
        story += [it2, Spacer(1, 14)]

    # Liquidación (saldo anterior + monto liquidado + nuevo saldo)
    story.append(_rl_seccion_titulo("Liquidación", AZUL_MED, GRIS_BG, doc.width))
    story.append(Spacer(1, 6))

    if filas_retencion_gastos:
        story.append(_p(
            "Gastos Extraordinarios pagados por la Inmobiliaria/Inquilino/Otro, retenidos de esta liquidación:",
            size=8.5, color=GRIS_TEXT
        ))
        story.append(Spacer(1, 4))
        rows_ret = [[
            _p("Fecha", bold=True, color=BLANCO, size=8),
            _p("Propiedad", bold=True, color=BLANCO, size=8),
            _p("Categoría", bold=True, color=BLANCO, size=8),
            _p("Descripción", bold=True, color=BLANCO, size=8),
            _p("Pagado por", bold=True, color=BLANCO, size=8),
            _p("Monto", bold=True, color=BLANCO, size=8, align=TA_RIGHT),
        ]]
        for g in filas_retencion_gastos:
            rows_ret.append([
                _p(str(g.get("fecha", "")), size=7.5),
                _p(str(g.get("propiedad", "")), size=7.5),
                _p(str(g.get("categoria", "")), size=7.5),
                _p(str(g.get("descripcion", "")), size=7.5),
                _p(str(g.get("pagado_por", "")), size=7.5),
                _p(f"$ {float(g.get('monto', 0)):,.2f}", size=7.5, align=TA_RIGHT),
            ])
        nr = len(rows_ret)
        rt = Table(rows_ret, colWidths=[doc.width*0.12, doc.width*0.20, doc.width*0.16,
                                         doc.width*0.24, doc.width*0.14, doc.width*0.14])
        rt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0), AZUL_MED),
            ("LINEBELOW",     (0,1),(-1,nr-1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING",    (0,0),(-1,-1), 5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("LEFTPADDING",   (0,0),(-1,-1), 4), ("RIGHTPADDING", (0,0),(-1,-1),4),
            ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
        ]))
        story += [rt, Spacer(1, 10)]

    liq_rows = [
        [_p("Saldo Pendiente de Período(s) Anterior(es)"), _p(f"$ {saldo_anterior:,.2f}", align=TA_RIGHT)],
        [_p("Retención por Gastos (–)"), _p(f"$ {total_retencion_gastos:,.2f}", align=TA_RIGHT)],
        [_p("Monto Total a Liquidar", bold=True), _p(f"$ {monto_a_liquidar:,.2f}", bold=True, align=TA_RIGHT)],
    ]
    lt = Table(liq_rows, colWidths=[doc.width*0.72, doc.width*0.28])
    lt.setStyle(TableStyle([
        ("LINEBELOW",     (0,0),(-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",    (0,0),(-1,-1), 7), ("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("LEFTPADDING",   (0,0),(-1,-1), 8), ("RIGHTPADDING", (0,0),(-1,-1),8),
    ]))
    story += [lt, Spacer(1, 8)]

    pago_rows = [[
        _p("MONTO LIQUIDADO AL PROPIETARIO", bold=True, color=VERDE),
        _p(f"$ {monto_liquidado:,.2f}", bold=True, color=VERDE, align=TA_RIGHT),
    ]]
    pago_tbl = Table(pago_rows, colWidths=[doc.width*0.72, doc.width*0.28])
    pago_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), VERDE_BG),
        ("TOPPADDING",    (0,0),(-1,-1), 8), ("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("LEFTPADDING",   (0,0),(-1,-1), 8), ("RIGHTPADDING", (0,0),(-1,-1),8),
    ]))
    story.append(pago_tbl)

    if abs(saldo_pendiente) > 0.01:
        _label_saldo = "SALDO PENDIENTE A FAVOR DEL PROPIETARIO" if saldo_pendiente > 0 else "SALDO A FAVOR DE LA INMOBILIARIA"
        saldo_rows = [[
            _p(_label_saldo, bold=True, color=ROJO),
            _p(f"$ {abs(saldo_pendiente):,.2f}", bold=True, color=ROJO, align=TA_RIGHT),
        ]]
        saldo_tbl = Table(saldo_rows, colWidths=[doc.width*0.72, doc.width*0.28])
        saldo_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), ROJO_BG),
            ("TOPPADDING",    (0,0),(-1,-1), 8), ("BOTTOMPADDING",(0,0),(-1,-1),8),
            ("LEFTPADDING",   (0,0),(-1,-1), 8), ("RIGHTPADDING", (0,0),(-1,-1),8),
        ]))
        story += [Spacer(1, 4), saldo_tbl]

    # Aviso de próxima actualización si corresponde en el período siguiente
    if aviso_actualizacion_proximo and prox_actualizacion:
        story.append(Spacer(1, 10))
        aviso_rows = [[_p(
            f"⚠️  AVISO: El próximo período corresponde aplicar una <b>ACTUALIZACIÓN DE ALQUILER</b> "
            f"según el índice pactado en el contrato. Fecha de actualización: <b>{prox_actualizacion}</b>.",
            size=9.5, color=colors.HexColor("#7b341e"),
        )]]
        aviso_tbl = Table(aviso_rows, colWidths=[doc.width])
        aviso_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#fff3cd")),
            ("BOX",           (0,0),(-1,-1), 1, colors.HexColor("#f6ad55")),
            ("TOPPADDING",    (0,0),(-1,-1), 8),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
            ("LEFTPADDING",   (0,0),(-1,-1), 10),
            ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ]))
        story.append(aviso_tbl)

    # Firma
    story.append(Spacer(1, 30))
    ft = Table([["", _p("_________________________",
                         size=11, color=GRIS_TEXT, align=TA_CENTER)]],
               colWidths=[doc.width*0.55, doc.width*0.45])
    story.append(ft)

    # Pie
    story += [Spacer(1,20),
              HRFlowable(width=doc.width, thickness=0.5, color=colors.HexColor("#e2e8f0")),
              Spacer(1,6),
              _p("Documento de rendición de cuentas emitido de manera electrónica.",
                 size=9, color=colors.HexColor("#718096"), align=TA_CENTER)]

    doc.build(story)
    return buffer.getvalue()




def _safe_float(val, default=0.0):
    """Convierte a float de forma segura — maneja None, NaN, strings vacíos."""
    if val is None:
        return default
    try:
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

# 🚀 AGREGAR AQUÍ (Única llamada en todo el script)
st.set_page_config(page_title="Gestión de Alquileres Pro", layout="wide", initial_sidebar_state="expanded")

# 2. Inyección de CSS para ocultar elementos
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# 2.b Sello de versión — esquina inferior derecha, visible en toda la app
# (incluida la pantalla de login). Permite confirmar a simple vista qué
# build del archivo está corriendo.
st.markdown(
    f"""
    <div style="
        position: fixed;
        bottom: 8px;
        right: 14px;
        z-index: 9999;
        background-color: rgba(0,0,0,0.55);
        color: #ffffff;
        padding: 2px 10px;
        border-radius: 8px;
        font-size: 11px;
        font-family: monospace;
        letter-spacing: 0.5px;
        pointer-events: none;
    ">
        {APP_VERSION}
    </div>
    """,
    unsafe_allow_html=True
)


# 1. Definimos qué columnas esperamos para cada tabla (puedes ampliarlo)
ESQUEMAS_VALIDOS = {
    "propiedades": ['alias_propiedad', 'calle', 'numero', 'departamento', 'propietario', 'ciudad', 'provincia', 'tipo', 'nis', 'cuenta_gas', 'finca', 'cuenta_ooss', 'nro_padron'],
    "inquilinos": ['apellidos', 'nombres', 'dni', 'telefono', 'email'],
    "gastos_propiedades": ['propiedad_id', 'fecha', 'categoria', 'descripcion', 'monto', 'proveedor', 'comprobante', 'pagado_por', 'observaciones', 'tipo_gasto', 'cobrado', 'periodo_cobrado'],
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
# NOTA: conectar_db() y conectar_db_central() están definidas arriba
# usando el pool de conexiones (_get_pool). No redefinir acá.

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
                    st.cache_data.clear()
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
        # Cargar grupos existentes para el selectbox
        _eid_edit_grp = st.session_state.get("empresa_id", 0)
        try:
            with _pg_conn() as _conn_eg:
                with _conn_eg.cursor() as _cur_eg:
                    _cur_eg.execute(
                        "SELECT DISTINCT grupo FROM propiedades WHERE empresa_id = %s AND grupo IS NOT NULL AND grupo != \'\' ORDER BY grupo",
                        (_eid_edit_grp,)
                    )
                    _grupos_edit = [r["grupo"] for r in _cur_eg.fetchall()]
        except Exception:
            _grupos_edit = []
        
        _grupo_actual = datos_prop.get("grupo", "") or ""
        _opciones_grupo = ["— Sin grupo —"] + _grupos_edit
        _idx_grupo = _opciones_grupo.index(_grupo_actual) if _grupo_actual in _opciones_grupo else 0
        edit_grupo_sel = st.selectbox("🏢 Grupo / Edificio:", options=_opciones_grupo, index=_idx_grupo)
        edit_grupo = "" if edit_grupo_sel == "— Sin grupo —" else edit_grupo_sel
        
        if st.form_submit_button("💾 Guardar Cambios Propiedad", type="primary"):
            if not edit_alias or not edit_calle or not edit_numero:
                st.error("Alias, Calle y Número son obligatorios.")
            else:
                conn = conectar_db()
                cursor = conn.cursor()
                try:
                    cursor.execute('''
                        UPDATE propiedades 
                        SET alias_propiedad = %s, calle = %s, numero = %s, departamento = %s, grupo = %s
                        WHERE id = %s
                    ''', (edit_alias, edit_calle, edit_numero, edit_depto, edit_grupo.strip() or None, id_prop_edit))
                    
                    conn.commit()
                    st.cache_data.clear()
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
        if username_clean == _get_secret("superadmin", "username", "SUPERADMIN_USERNAME"):
            stored_hash = (_get_secret("superadmin", "password_hash", "SUPERADMIN_PASSWORD_HASH") or "").encode("utf-8")
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
                    st.session_state.pestana_activa = "dashboard"
                    st.session_state.terminos_aceptados = None  # forzar reverificación desde BD

                    # Obtener empresa_id desde PostgreSQL
                    try:
                        if datos_sesion["rol"] == "superadmin":
                            st.session_state.empresa_id = 2  # Empresa SuperAdmin en Supabase
                        else:
                            _eid = _get_empresa_id(datos_sesion["archivo_db"])
                            if not _eid:
                                with _pg_conn() as _fc:
                                    with _fc.cursor() as _cur:
                                        _cur.execute(
                                            "SELECT id FROM empresas WHERE nombre_comercial = %s",
                                            (datos_sesion["nombre_empresa"],)
                                        )
                                        _row = _cur.fetchone()
                                        _eid = _row["id"] if _row else None
                            st.session_state.empresa_id = _eid if _eid else 0
                            if st.session_state.empresa_id == 0:
                                st.warning(f"⚠️ No se encontró empresa_id para '{datos_sesion['nombre_empresa']}'.")
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
        st.caption(f"Versión {APP_VERSION}")
    st.stop() # Frena el renderizado si no está autenticado

# ── Verificar aceptación de términos (fuera del bloque de login) ──
if st.session_state.autenticado and st.session_state.get('usuario_rol') != 'superadmin':
    _username_tc = st.session_state.get('usuario_actual', '')
    _terminos_ok = st.session_state.get('terminos_aceptados', None)
    logging.info(f"[TyC] autenticado={st.session_state.autenticado}, rol={st.session_state.get('usuario_rol')}, username={_username_tc}, terminos_ok={_terminos_ok}")

    if _terminos_ok is None:
        try:
            with _pg_conn() as _conn_tc:
                with _conn_tc.cursor() as _cur_tc:
                    _cur_tc.execute(
                        'SELECT terminos_aceptados FROM usuarios_central WHERE username = %s',
                        (_username_tc,)
                    )
                    _row_tc = _cur_tc.fetchone()
                    _terminos_ok = bool(_row_tc['terminos_aceptados']) if _row_tc else False
                    st.session_state['terminos_aceptados'] = _terminos_ok
        except Exception:
            _terminos_ok = False
            st.session_state['terminos_aceptados'] = False

    if not _terminos_ok:
        st.markdown('## 📋 Términos y Condiciones de Uso')
        st.markdown('Antes de continuar, por favor leé y aceptá los Términos y Condiciones del Sistema.')
        with st.container(height=400):
            st.markdown('\n## Términos y Condiciones de Uso\n### Sistema de Gestión Inmobiliaria — Versión 1.0\n\n---\n\n**1. Aceptación de los Términos**\n\nAl acceder y utilizar el Sistema de Gestión Inmobiliaria (en adelante, "el Sistema"), el usuario declara haber leído, comprendido y aceptado en su totalidad los presentes Términos y Condiciones. Si no está de acuerdo con alguno de estos términos, deberá abstenerse de utilizar el Sistema.\n\n---\n\n**2. Descripción del Servicio**\n\nEl Sistema es una plataforma de software como servicio (SaaS) diseñada para la gestión de contratos de locación, registro de cobros, emisión de comprobantes y administración de propiedades e inquilinos. El acceso al Sistema se otorga mediante credenciales personales e intransferibles.\n\n---\n\n**3. Protección de Datos Personales**\n\nEl Sistema almacena y procesa datos personales de terceros (inquilinos, propietarios y otros) en cumplimiento de la **Ley 25.326 de Protección de Datos Personales de la República Argentina** y su normativa complementaria.\n\n- **Responsable del tratamiento de datos:** La empresa u organización que contrata el uso del Sistema (en adelante, "el Operador") es responsable del tratamiento de los datos personales ingresados.\n- **El Desarrollador** actúa como encargado del tratamiento en su carácter de proveedor tecnológico, y no accede, comercializa ni cede los datos a terceros salvo requerimiento legal.\n- El Operador es responsable de obtener los consentimientos necesarios de los titulares de los datos personales conforme a la normativa vigente.\n- Los datos se almacenan en infraestructura cloud de terceros bajo estándares de seguridad internacionales, con cifrado en tránsito y en reposo, acceso restringido y políticas de respaldo periódico, conforme a las mejores prácticas de la industria tecnológica.\n- El Operador tiene derecho a solicitar la eliminación de sus datos mediante comunicación formal al Desarrollador. Esta solicitud podrá realizarse una vez por año calendario, pudiendo estar sujeta a limitaciones técnicas en su ejecución.\n\n---\n\n**4. Responsabilidad por Cálculos e Índices**\n\nEl Sistema realiza cálculos automáticos basados en índices oficiales publicados por el BCRA (ICL) y el INDEC (IPC), obtenidos de fuentes públicas.\n\n- El Desarrollador **no garantiza** la exactitud, disponibilidad o actualización en tiempo real de dichos índices.\n- Los valores calculados son **orientativos** y no reemplazan la verificación con las fuentes oficiales.\n- El Operador es responsable de verificar los montos antes de emitir comprobantes o impactar cobros.\n- El Desarrollador no será responsable por pérdidas económicas derivadas de errores en los cálculos automáticos.\n\n---\n\n**5. Condiciones del Servicio SaaS**\n\n- El acceso al Sistema está sujeto al pago de la tarifa acordada entre el Operador y el Desarrollador.\n- El Desarrollador se reserva el derecho de suspender el acceso ante falta de pago o uso indebido del Sistema.\n- El Desarrollador podrá actualizar, modificar o interrumpir el Sistema con previo aviso de 15 días corridos.\n- El Desarrollador realiza todos los esfuerzos técnicos razonables para garantizar la máxima disponibilidad del Sistema, implementando medidas de monitoreo, redundancia y mantenimiento preventivo. No obstante, la disponibilidad puede verse afectada por factores ajenos al control del Desarrollador, tales como fallas en servicios de infraestructura de terceros, conectividad de red o causas de fuerza mayor.\n\n---\n\n**6. Uso Aceptable**\n\nEl Operador y sus usuarios se comprometen a:\n\n- Utilizar el Sistema exclusivamente para los fines de gestión inmobiliaria para los que fue diseñado.\n- No intentar acceder a datos de otras organizaciones ni vulnerar la seguridad del Sistema.\n- No compartir credenciales de acceso con personas no autorizadas.\n- No utilizar el Sistema para actividades ilegales o contrarias a la normativa vigente.\n\n---\n\n**7. Confidencialidad**\n\nEl Desarrollador se compromete a mantener la confidencialidad de toda la información del Operador y no divulgarla a terceros, salvo requerimiento judicial o legal expreso.\n\n---\n\n**8. Propiedad Intelectual**\n\nEl Sistema, su código fuente, diseño y funcionalidades son propiedad exclusiva del Desarrollador. El contrato de SaaS otorga una licencia de uso no exclusiva e intransferible, sin que ello implique cesión de derechos sobre el software.\n\n---\n\n**9. Modificaciones a los Términos**\n\nEl Desarrollador podrá modificar los presentes Términos con un preaviso de 15 días mediante notificación dentro del Sistema. El uso continuado del Sistema tras dicho período implica la aceptación de los nuevos términos.\n\n---\n\n**10. Jurisdicción**\n\nPara cualquier controversia derivada del uso del Sistema, las partes se someten a la jurisdicción de los Tribunales Ordinarios de la ciudad de Villa Mercedes, provincia de San Luis, República Argentina, renunciando a cualquier otro fuero que pudiera corresponder.\n')
        st.markdown('---')
        _acepto = st.checkbox('✅ He leído y acepto los Términos y Condiciones de Uso')
        if st.button('Continuar →', type='primary', disabled=not _acepto):
            try:
                with _pg_conn() as _conn_tc2:
                    with _conn_tc2.cursor() as _cur_tc2:
                        _cur_tc2.execute(
                            'UPDATE usuarios_central SET terminos_aceptados = TRUE, terminos_fecha = %s WHERE username = %s',
                            (datetime.now().strftime('%d/%m/%Y %H:%M'), _username_tc)
                        )
                    _conn_tc2.commit()
                st.session_state['terminos_aceptados'] = True
                st.session_state.pestana_activa = "dashboard"
                st.rerun()
            except Exception as _e_tc:
                st.error(f'Error al guardar la aceptación: {_e_tc}')
        st.stop()

# =====================================================================
# FUNCIONES AUXILIARES DE LÓGICA Y PARSEO
# =====================================================================
@st.cache_data(ttl=600)
def obtener_datos_desplegables(empresa_id: int):
    """Cache correcto por empresa_id — evita que distintas empresas compartan el mismo cache."""
    try:
        with _pg_conn() as _conn_desp:
            with _conn_desp.cursor() as _cur_desp:
                _cur_desp.execute(
                    "SELECT id, alias_propiedad, calle, numero, departamento, propietario, ciudad, provincia, tipo "
                    "FROM propiedades WHERE empresa_id = %s ORDER BY id ASC", (empresa_id,)
                )
                propiedades = pd.DataFrame([dict(r) for r in _cur_desp.fetchall()])
                _cur_desp.execute(
                    "SELECT id, apellidos, nombres FROM inquilinos WHERE empresa_id = %s ORDER BY id ASC", (empresa_id,)
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
        dict_propiedades[f"ID: {row['id']} | {row['alias_propiedad']} ({dir_completa})"] = row['id']
        
    dict_inquilinos = {f"Cod: {row['id']} | {row['apellidos']}, {row['nombres']}": row['id'] for _, row in inquilinos.iterrows()}
    return dict_propiedades, dict_inquilinos

# =====================================================================
# FUNCIONES DE LECTURA CACHEADAS (PERFORMANCE)
# ---------------------------------------------------------------------
# Streamlit re-ejecuta el cuerpo de TODAS las pestañas en cada rerun
# (no solo la que se está viendo). Sin cache, eso significa repetir
# estas consultas pesadas en cada clic, multiplicado por la cantidad
# de usuarios conectados. TTL corto (30s) + limpieza explícita
# (st.cache_data.clear()) justo después de cada guardado exitoso, para
# que el propio usuario vea sus cambios al instante.
# =====================================================================

def _query_df(query: str, params: tuple):
    """Ejecuta una query y devuelve un DataFrame. Helper interno para las funciones cacheadas."""
    with _pg_conn() as _conn:
        with _conn.cursor() as _cur:
            _cur.execute(query, params)
            _rows = _cur.fetchall()
            _cols = [c.name for c in _cur.description]
    if not _rows:
        return pd.DataFrame(columns=_cols)
    _df = pd.DataFrame([dict(r) for r in _rows], columns=_cols)
    # psycopg2 devuelve las columnas NUMERIC de Postgres como decimal.Decimal, no float.
    # Si no se convierten acá, cualquier cálculo posterior que las mezcle con un float
    # normal (ej. suma de totales) revienta con TypeError. Se convierte una sola vez,
    # en la raíz, para que todas las funciones cacheadas queden a salvo de este problema.
    for _col in _df.columns:
        if _df[_col].apply(lambda v: isinstance(v, decimal.Decimal)).any():
            _df[_col] = _df[_col].apply(lambda v: float(v) if isinstance(v, decimal.Decimal) else v)
    return _df


def _agregar_mes_calendario(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega 'nro_periodo' y 'mes_calendario' (YYYY-MM) a un DataFrame que tenga
    las columnas 'periodo' (formato "Mes N de M") e 'inicio_contrato'.
    Se usa tanto en Métricas como en Rendición a Propietarios."""
    if df.empty:
        df["nro_periodo"]    = pd.Series(dtype=int)
        df["mes_calendario"] = pd.Series(dtype=str)
        return df

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
            _ini = str(row.get("inicio_contrato", "") or "").strip()
            if not _ini or _ini == "None":
                return ""
            try:
                inicio = pd.to_datetime(_ini, format="%Y-%m-%d")
            except Exception:
                try:
                    inicio = pd.to_datetime(_ini, format="%d/%m/%Y")
                except Exception:
                    inicio = pd.to_datetime(_ini, dayfirst=True)
            cal = inicio + dateutil.relativedelta.relativedelta(months=nro - 1)
            return cal.strftime("%Y-%m")
        except Exception:
            return ""

    df = df.copy()
    df["nro_periodo"]    = df["periodo"].apply(_extraer_nro_mes)
    df["mes_calendario"] = df.apply(_calc_mes_cal, axis=1)
    return df


def _generar_nro_comprobante(empresa_id: int) -> str:
    """Genera un número de comprobante secuencial único global (todas las empresas comparten
    la misma secuencia). Usa nextval() de PostgreSQL, que es atómico por definición.
    Formato: RC-YYYY-NNNNN (ej: RC-2026-00042).
    """
    from datetime import datetime as _dt
    _anio = _dt.now().year
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT nextval('seq_nro_recibo')")
                row = cur.fetchone()
                nro = list(row.values())[0] if row else 1
            conn.commit()
        return f"RC-{_anio}-{nro:05d}"
    except Exception:
        import time as _t
        return f"RC-{_anio}-{int(_t.time()) % 100000}"


def _obtener_liquidacion_existente(empresa_id: int, propietario: str, periodo: str):
    """Devuelve la liquidación ya registrada para este propietario+período, si existe."""
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM liquidaciones_propietarios WHERE empresa_id = %s AND propietario = %s AND periodo = %s",
                    (empresa_id, propietario, periodo)
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception:
        return None


def _obtener_saldo_anterior_propietario(empresa_id: int, propietario: str, periodo_actual: str) -> float:
    """Devuelve el saldo_pendiente de la última liquidación previa a este período (arrastre)."""
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT saldo_pendiente FROM liquidaciones_propietarios
                       WHERE empresa_id = %s AND propietario = %s AND periodo < %s
                       ORDER BY periodo DESC LIMIT 1""",
                    (empresa_id, propietario, periodo_actual)
                )
                row = cur.fetchone()
                return float(row["saldo_pendiente"]) if row else 0.0
    except Exception:
        return 0.0


def _obtener_gastos_retencion_pendientes(empresa_id: int, propietario: str):
    """Gastos Extraordinarios pagados por alguien que no sea el Propietario (Inmobiliaria,
    Inquilino u Otro), todavía no descontados ('cobrado' = FALSE) — se retienen de la
    próxima liquidación a ese propietario."""
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT gp.id, p.alias_propiedad AS propiedad, gp.fecha, gp.categoria,
                           gp.descripcion, gp.monto, gp.pagado_por
                    FROM gastos_propiedades gp
                    JOIN propiedades p ON gp.propiedad_id = p.id AND p.empresa_id = gp.empresa_id
                    WHERE gp.empresa_id = %s AND p.propietario = %s
                      AND COALESCE(gp.tipo_gasto, 'Extraordinario') = 'Extraordinario'
                      AND COALESCE(gp.pagado_por, '') != 'Propietario'
                      AND COALESCE(gp.cobrado, FALSE) = FALSE
                    ORDER BY gp.fecha
                """, (empresa_id, propietario))
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    except Exception:
        return []


def _marcar_gastos_como_cobrados(empresa_id: int, ids_gastos: list, periodo: str):
    """Marca los gastos retenidos como 'cobrado' al registrar la liquidación,
    para que no se vuelvan a descontar en un período futuro."""
    if not ids_gastos:
        return
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE gastos_propiedades SET cobrado = TRUE, periodo_cobrado = %s "
                    "WHERE empresa_id = %s AND id = ANY(%s)",
                    (periodo, empresa_id, ids_gastos)
                )
    except Exception:
        pass


@st.cache_data(ttl=300, show_spinner=False)
def _cached_contratos_activos(empresa_id: int, propietario_filtro: str = ""):
    """Dashboard: contratos activos (para alertas de vencimiento/actualización)."""
    _where = "AND p.propietario = %s" if propietario_filtro else ""
    _params = (empresa_id, propietario_filtro) if propietario_filtro else (empresa_id,)
    query = f'''
        SELECT c.codigo, p.alias_propiedad, (i.apellidos || ', ' || i.nombres) as inquilino,
            c.estado, c.fin_contrato, c.prox_actualizacion, c.alquiler, c.mes_contrato, c.act_contrato
        FROM contratos c
        JOIN propiedades p ON c.alias_propiedad = p.alias_propiedad
        JOIN inquilinos i ON c.dni_inquilino = i.dni
        WHERE c.empresa_id = %s AND c.estado = 'Activo' {_where}
    '''
    return _query_df(query, _params)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_pagos_totales(empresa_id: int, propietario_filtro: str = ""):
    """Dashboard: suma de cobros históricos."""
    _where = "AND ph.propiedad IN (SELECT alias_propiedad FROM propiedades WHERE propietario = %s AND empresa_id = %s)" if propietario_filtro else ""
    _params = (empresa_id, propietario_filtro, empresa_id) if propietario_filtro else (empresa_id,)
    query = f"SELECT COALESCE(ph.monto_abonado, 0) AS monto_total FROM pagos_historial ph WHERE ph.empresa_id = %s {_where}"
    return _query_df(query, _params)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_planilla_cobranzas_mes(empresa_id: int, mes: int, anio: int, propietario_filtro: str = ""):
    """Planilla de cobranzas del mes: estado de pago de cada contrato activo."""
    _where = "AND p.propietario = %s" if propietario_filtro else ""
    _params = (empresa_id,) + ((propietario_filtro,) if propietario_filtro else ())
    query = f"""
        SELECT
            p.id                                        AS propiedad_id,
            p.alias_propiedad                           AS alias_propiedad,
            (i.apellidos || ', ' || i.nombres)          AS inquilino,
            c.codigo                                    AS codigo_contrato,
            i.id                                        AS inquilino_id,
            i.apellidos                                 AS apellidos,
            i.nombres                                   AS nombres,
            c.prox_actualizacion                        AS prox_actualizacion,
            c.fin_contrato                              AS fin_contrato,
            c.alquiler                                  AS ultimo_alquiler,
            c.monto_inicial                             AS monto_inicial,
            c.alquiler_calculado                        AS alquiler_calculado,
            c.alquiler_calculado_fecha                  AS alquiler_calculado_fecha,
            c.expensas                                  AS expensas,
            c.cochera                                   AS cochera,
            i.telefono                                  AS telefono,
            p.calle                                     AS calle,
            p.numero                                    AS numero
        FROM contratos c
        JOIN propiedades p ON c.alias_propiedad = p.alias_propiedad
        JOIN inquilinos i ON c.dni_inquilino = i.dni
        WHERE c.empresa_id = %s AND c.estado = 'Activo' {_where}
        ORDER BY p.id ASC
    """
    df_contratos = _query_df(query, _params)
    if df_contratos.empty:
        return df_contratos

    # Buscar el último pago del mes actual por contrato
    with _pg_conn() as _conn_pm:
        with _conn_pm.cursor() as _cur_pm:
            _cur_pm.execute(
                """SELECT DISTINCT ON (codigo_contrato)
                       codigo_contrato, monto_abonado, saldo_pendiente, fecha
                   FROM pagos_historial
                   WHERE empresa_id = %s
                     AND EXTRACT(MONTH FROM TO_DATE(SPLIT_PART(fecha, ' ', 1), 'DD/MM/YYYY')) = %s
                     AND EXTRACT(YEAR  FROM TO_DATE(SPLIT_PART(fecha, ' ', 1), 'DD/MM/YYYY')) = %s
                   ORDER BY codigo_contrato, id DESC""",
                (empresa_id, mes, anio)
            )
            _pagos = {r["codigo_contrato"]: r for r in _cur_pm.fetchall()}

    df_contratos["pagado_mes"] = df_contratos["codigo_contrato"].apply(
        lambda cod: float(_pagos.get(cod, {}).get("saldo_pendiente") or 0) == 0.0 if cod in _pagos else False
    )
    df_contratos["_pago_fecha"] = df_contratos["codigo_contrato"].apply(
        lambda cod: _pagos.get(cod, {}).get("fecha", "") if cod in _pagos else ""
    )
    return df_contratos


@st.cache_data(ttl=300, show_spinner=False)
def _cached_planilla_contratos(empresa_id: int, propietario_filtro: str = ""):
    """Planilla: listado general de contratos."""
    _where = "AND p.propietario = %s" if propietario_filtro else ""
    _params = (empresa_id, propietario_filtro) if propietario_filtro else (empresa_id,)
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
        WHERE c.empresa_id = %s AND 1=1 {_where}
        ORDER BY c.codigo DESC
    '''
    return _query_df(query, _params)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_historial_pagos(empresa_id: int, propietario_filtro: str = ""):
    """Historial de Caja: listado completo de cobros registrados."""
    _where = "AND ph.propiedad IN (SELECT alias_propiedad FROM propiedades WHERE propietario = %s AND empresa_id = %s)" if propietario_filtro else ""
    _params = (empresa_id, propietario_filtro, empresa_id) if propietario_filtro else (empresa_id,)
    query = f"""
        SELECT
            ph.id                                       AS "ID PAGO",
            ph.codigo_contrato                          AS "COD CONTRATO",
            ph.propiedad                                AS "PROPIEDAD",
            ph.propiedad                                AS "DIR PROPIEDAD",
            COALESCE(p2.calle || ' ' || p2.numero || CASE WHEN p2.departamento <> '' AND p2.departamento IS NOT NULL THEN ', Dto: ' || p2.departamento ELSE '' END, ph.propiedad) AS "DOMICILIO",
            COALESCE(ph.propiedad || ' (' || p2.calle || ' ' || p2.numero || CASE WHEN p2.departamento <> '' AND p2.departamento IS NOT NULL THEN ', Dto: ' || p2.departamento ELSE '' END || ')', ph.propiedad) AS "ALIAS / UBICACIÓN",
            ph.inquilino                                AS "INQUILINO",
            ph.inquilino                                AS "_apellidos",
            ''                                          AS "_nombres",
            ''                                          AS "_telefono",
            ph.periodo                                  AS "PERIODO",
            COALESCE(ph.monto_alquiler,0)               AS "ALQUILER ($)",
            COALESCE(ph.monto_imp_inmobiliario,0) + COALESCE(ph.monto_edesal,0)
                + COALESCE(ph.monto_gas,0) + COALESCE(ph.monto_municipalidad,0)
                + COALESCE(ph.monto_ooss,0)                AS "SERVICIOS ($)",
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
            COALESCE(ph.monto_concepto_extra,0)         AS "_concepto_extra",
            COALESCE(ph.concepto_extra_desc,'')         AS "_concepto_extra_desc",
            COALESCE(ph.monto_abonado,0)                AS "_abonado",
            COALESCE(ph.saldo_pendiente,0)              AS "_saldo_pendiente",
            COALESCE(ph.comentario,'')                 AS "_comentarios",
            COALESCE(c.inicio_contrato, '')            AS "_inicio_contrato",
            0                                           AS "_pct_admin",
            COALESCE(ph.nro_comprobante, '')           AS "NRO COMPROBANTE",
            COALESCE(ph.cotizacion_usd,0)              AS "COTIZACIÓN USD",
            CASE WHEN COALESCE(ph.cotizacion_usd,0) > 0
                 THEN ROUND((COALESCE(ph.monto_alquiler,0) / ph.cotizacion_usd)::NUMERIC, 2)
                 ELSE 0 END                             AS "ALQUILER (USD)",
            CASE WHEN COALESCE(ph.cotizacion_usd,0) > 0
                 THEN ROUND((COALESCE(ph.monto_cochera,0) / ph.cotizacion_usd)::NUMERIC, 2)
                 ELSE 0 END                             AS "COCHERA (USD)",
            CASE WHEN COALESCE(ph.cotizacion_usd,0) > 0
                 THEN ROUND((COALESCE(ph.monto_imp_inmobiliario,0) / ph.cotizacion_usd)::NUMERIC, 2)
                 ELSE 0 END                             AS "IMP. INMOBILIARIO (USD)",
            0                                           AS "RETENCIÓN AGENCIA (USD)"
        FROM pagos_historial ph
        LEFT JOIN contratos c ON ph.codigo_contrato = c.codigo AND c.empresa_id = ph.empresa_id
        LEFT JOIN propiedades p2 ON (ph.propiedad = p2.alias_propiedad OR ph.propiedad = (p2.calle || ' ' || p2.numero)) AND p2.empresa_id = ph.empresa_id
        WHERE ph.empresa_id = %s {_where}
        ORDER BY ph.id DESC
    """
    return _query_df(query, _params)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_gastos_historial(empresa_id: int, propietario_filtro: str = ""):
    """Gastos: historial completo de gastos de propiedades."""
    _where = "AND p.propietario = %s" if propietario_filtro else ""
    _params = (empresa_id, propietario_filtro) if propietario_filtro else (empresa_id,)
    query = f"""
        SELECT gp.id AS "ID", p.id AS "COD_PROPIEDAD", p.alias_propiedad AS "PROPIEDAD", p.propietario AS "PROPIETARIO",
               gp.fecha AS "FECHA", gp.categoria AS "CATEGORÍA", gp.descripcion AS "DESCRIPCIÓN",
               gp.monto AS "MONTO ($)",
               COALESCE(gp.cotizacion_usd, 0) AS "COTIZACIÓN USD",
               CASE WHEN COALESCE(gp.cotizacion_usd, 0) > 0
                    THEN ROUND((gp.monto / gp.cotizacion_usd)::NUMERIC, 2)
                    ELSE 0 END AS "MONTO (USD)",
               COALESCE(gp.tipo_gasto, 'Ordinario') AS "TIPO",
               gp.proveedor AS "PROVEEDOR",
               gp.comprobante AS "COMPROBANTE", gp.pagado_por AS "PAGADO POR",
               gp.observaciones AS "OBSERVACIONES"
        FROM gastos_propiedades gp
        JOIN propiedades p ON gp.propiedad_id = p.id AND p.empresa_id = gp.empresa_id
        WHERE gp.empresa_id = %s {_where}
        ORDER BY gp.fecha DESC, gp.id DESC
    """
    return _query_df(query, _params)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_metricas_ingresos(empresa_id: int, propietario_filtro: str = ""):
    """Métricas / Rendición: ingresos crudos desde pagos_historial (sin procesar mes_calendario)."""
    _where = "AND p.propietario = %s" if propietario_filtro else ""
    _params = (empresa_id, propietario_filtro) if propietario_filtro else (empresa_id,)
    query = f"""
        SELECT
            ph.id                                                               AS id_pago,
            ph.fecha                                                            AS fecha,
            COALESCE(ph.nro_comprobante, '')                                   AS nro_comprobante,
            COALESCE(ph.inquilino, '')                                         AS inquilino,
            ph.propiedad                                                        AS propiedad,
            COALESCE(p.propietario, '')                                        AS propietario,
            COALESCE(p.grupo, '')                                              AS grupo,
            ph.periodo                                                          AS periodo,
            COALESCE(c.inicio_contrato, '')                                   AS inicio_contrato,
            0                                                                   AS calc_duracion,
            COALESCE(ph.monto_alquiler, 0)                                    AS alquiler,
            COALESCE(ph.monto_cochera, 0)                                     AS cochera,
            COALESCE(ph.monto_expensas, 0)                                    AS expensas,
            COALESCE(ph.monto_imp_inmobiliario, 0)                            AS imp_inmobiliario,
            COALESCE(ph.monto_edesal, 0)                                      AS edesal,
            COALESCE(ph.monto_gas, 0)                                         AS gas,
            COALESCE(ph.monto_municipalidad, 0)                               AS municipalidad,
            COALESCE(ph.monto_ooss, 0)                                        AS ooss,
            COALESCE(ph.monto_honorarios, 0)                                  AS honorarios,
            COALESCE(ph.monto_garantia, 0)                                    AS garantia,
            COALESCE(ph.monto_concepto_extra, 0)                              AS concepto_extra,
            COALESCE(ph.concepto_extra_desc, '')                              AS concepto_extra_desc,
            COALESCE(ph.monto_abonado, 0)                                     AS abonado,
            COALESCE(ph.monto_alquiler, 0) + COALESCE(ph.monto_cochera, 0)
                + COALESCE(ph.monto_expensas, 0)                              AS total_ingreso,
            COALESCE(ph.monto_gasto_admin, 0)                                 AS gasto_admin,
            CASE WHEN COALESCE(ph.cotizacion_usd, 0) > 0
                 THEN ROUND((COALESCE(ph.monto_alquiler, 0) / ph.cotizacion_usd)::NUMERIC, 2)
                 ELSE 0 END                                                    AS alquiler_usd,
            CASE WHEN COALESCE(ph.cotizacion_usd, 0) > 0
                 THEN ROUND((COALESCE(ph.monto_cochera, 0) / ph.cotizacion_usd)::NUMERIC, 2)
                 ELSE 0 END                                                    AS cochera_usd,
            CASE WHEN COALESCE(ph.cotizacion_usd, 0) > 0
                 THEN ROUND(((COALESCE(ph.monto_alquiler, 0) + COALESCE(ph.monto_cochera, 0)
                      + COALESCE(ph.monto_expensas, 0)) / ph.cotizacion_usd)::NUMERIC, 2)
                 ELSE 0 END                                                    AS total_ingreso_usd,
            CASE WHEN COALESCE(ph.cotizacion_usd, 0) > 0
                 THEN ROUND((COALESCE(ph.monto_expensas, 0) / ph.cotizacion_usd)::NUMERIC, 2)
                 ELSE 0 END                                                    AS expensas_usd,
            CASE WHEN COALESCE(ph.cotizacion_usd, 0) > 0
                 THEN ROUND((COALESCE(ph.monto_gasto_admin, 0) / ph.cotizacion_usd)::NUMERIC, 2)
                 ELSE 0 END                                                    AS gasto_admin_usd,
            CASE WHEN COALESCE(ph.cotizacion_usd, 0) > 0
                 THEN ROUND((COALESCE(ph.monto_imp_inmobiliario, 0) / ph.cotizacion_usd)::NUMERIC, 2)
                 ELSE 0 END                                                    AS imp_inmobiliario_usd
        FROM pagos_historial ph
        LEFT JOIN propiedades p ON ph.propiedad = p.alias_propiedad AND p.empresa_id = ph.empresa_id
        LEFT JOIN contratos c ON ph.codigo_contrato = c.codigo AND c.empresa_id = ph.empresa_id
        WHERE ph.empresa_id = %s {_where}
        ORDER BY ph.periodo
    """
    return _query_df(query, _params)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_metricas_gastos(empresa_id: int, propietario_filtro: str = ""):
    """Métricas: gastos crudos agrupados por propiedad/período."""
    _where = "AND p.propietario = %s" if propietario_filtro else ""
    _params = (empresa_id, propietario_filtro) if propietario_filtro else (empresa_id,)
    query = f"""
        SELECT
            p.alias_propiedad                              AS propiedad,
            COALESCE(p.propietario, '')                   AS propietario,
            COALESCE(p.grupo, '')                          AS grupo,
            TO_CHAR(gp.fecha::date, 'YYYY-MM')           AS periodo,
            SUM(gp.monto)                                 AS total_gasto,
            SUM(CASE WHEN COALESCE(gp.cotizacion_usd, 0) > 0
                     THEN ROUND((gp.monto / gp.cotizacion_usd)::NUMERIC, 2)
                     ELSE 0 END)                           AS total_gasto_usd
        FROM gastos_propiedades gp
        JOIN propiedades p ON gp.propiedad_id = p.id AND p.empresa_id = gp.empresa_id
        WHERE gp.empresa_id = %s {_where}
        GROUP BY p.alias_propiedad, p.propietario, p.grupo, TO_CHAR(gp.fecha::date, 'YYYY-MM')
        ORDER BY periodo
    """
    return _query_df(query, _params)



@st.cache_data(ttl=3600)
def _obtener_icl_bcra_xls(año: int) -> dict:
    """
    Descarga el XLS del ICL publicado por el BCRA para el año dado.
    Detecta automáticamente las columnas de fecha y valor.
    Retorna dict {"YYYY-MM-DD": valor_float}.
    Cache de 1 hora.
    """
    url = f"https://www.bcra.gob.ar/pdfs/PublicacionesEstadisticas/icl{año}.xls"
    try:
        resp = requests.get(url, timeout=15, verify=False)
        resp.raise_for_status()
        try:
            df_raw = pd.read_excel(BytesIO(resp.content), header=None, engine="xlrd")
        except Exception as e_xls:
            logging.warning(f"[ICL] Error al leer XLS con xlrd: {e_xls}. Intentando con openpyxl...")
            try:
                df_raw = pd.read_excel(BytesIO(resp.content), header=None, engine="openpyxl")
            except Exception as e_xls2:
                logging.warning(f"[ICL] Error con openpyxl también: {e_xls2}")
                raise e_xls2
        logging.info(f"[ICL] XLS shape: {df_raw.shape}, columnas: {list(df_raw.columns)}")

        resultado = {}
        # Buscar columnas de fecha (formato YYYYMMDD de 8 dígitos) y valor numérico
        col_fecha = None
        col_valor = None
        for col_idx in range(min(15, len(df_raw.columns))):
            col_data = df_raw.iloc[:, col_idx].astype(str)
            fechas_validas = col_data.str.match(r'^\d{8}$').sum()
            if fechas_validas > 5:
                col_fecha = col_idx
                # El valor suele estar en la columna siguiente
                col_valor = col_idx + 1
                logging.info(f"[ICL] Columna fecha detectada: {col_fecha}, valor: {col_valor}")
                break

        if col_fecha is None:
            # Fallback: usar columnas 7 y 8 como antes
            col_fecha, col_valor = 7, 8
            logging.warning(f"[ICL] No se detectó columna fecha, usando col 7 y 8 por defecto")

        for _, row in df_raw.iterrows():
            try:
                fecha_raw = str(row.iloc[col_fecha]).strip()
                valor_raw = row.iloc[col_valor]
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
        logging.warning(f"[ICL] XLS descargado pero sin datos válidos. Primeras filas: {df_raw.head(30).to_string()}")
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
        f"👤 Operador: <b>{st.session_state.usuario_actual.upper()}</b><br>"
        f"<span style='font-size: 0.75em; color: gray;'>Versión {APP_VERSION}</span>"
        f"</p>", 
        unsafe_allow_html=True
    )

    # ── Selector de empresa para superadmin ──────────────────────────
    if st.session_state.get("rol") == "superadmin":
        try:
            with _pg_conn() as _conn_top:
                with _conn_top.cursor() as _cur_top:
                    _cur_top.execute("SELECT id, nombre_comercial FROM empresas ORDER BY id")
                    _empresas_top = _cur_top.fetchall()
            _dict_top = {r["nombre_comercial"]: r["id"] for r in _empresas_top}
            _nombres_top = list(_dict_top.keys())
            _empresa_actual_nombre = next(
                (n for n, i in _dict_top.items() if i == st.session_state.get("empresa_id", 2)),
                _nombres_top[0] if _nombres_top else "SuperAdmin"
            )
            _idx_default = _nombres_top.index(_empresa_actual_nombre) if _empresa_actual_nombre in _nombres_top else 0
            _emp_sel_top = st.selectbox(
                "🏢 Trabajando en:",
                options=_nombres_top,
                index=_idx_default,
                key="sb_superadmin_empresa_top",
                label_visibility="collapsed"
            )
            # Actualizar empresa_id si cambió — sin rerun, se aplica en el próximo ciclo
            _nuevo_eid = _dict_top[_emp_sel_top]
            if _nuevo_eid != st.session_state.get("empresa_id"):
                st.session_state.empresa_id = _nuevo_eid
                st.session_state.empresa_actual_nombre = _emp_sel_top
                st.cache_data.clear()
                st.rerun()
        except Exception:
            pass
    # ─────────────────────────────────────────────────────────────────

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

# Cargar configuración de empresa — siempre desde BD
try:
    with _pg_conn() as _conn_cfg0:
        with _conn_cfg0.cursor() as _cur_cfg0:
            _cur_cfg0.execute(
                """SELECT ce.actualizar_alquiler_auto, ce.whatsapp_habilitado,
                          ce.whatsapp_credenciales_propias,
                          ce.whatsapp_token, ce.whatsapp_phone_id,
                          wn.phone_id AS pool_phone_id
                   FROM configuraciones_empresa ce
                   LEFT JOIN whatsapp_numeros wn ON ce.whatsapp_numero_id = wn.id
                   WHERE ce.empresa_id = %s""",
                (st.session_state.get("empresa_id", 0),)
            )
            _row_cfg0 = _cur_cfg0.fetchone()
            st.session_state["cfg_actualizar_alquiler_auto"] = bool(_row_cfg0["actualizar_alquiler_auto"]) if _row_cfg0 else True
            st.session_state["cfg_whatsapp_habilitado"]      = bool(_row_cfg0["whatsapp_habilitado"])      if _row_cfg0 else False
            if _row_cfg0:
                if _row_cfg0["whatsapp_credenciales_propias"]:
                    st.session_state["cfg_whatsapp_token"]    = _row_cfg0["whatsapp_token"]    or ""
                    st.session_state["cfg_whatsapp_phone_id"] = _row_cfg0["whatsapp_phone_id"] or ""
                else:
                    st.session_state["cfg_whatsapp_phone_id"] = _row_cfg0["pool_phone_id"] or ""
                    st.session_state["cfg_whatsapp_token"]    = ""  # se lee desde Vault al enviar
            else:
                st.session_state["cfg_whatsapp_token"]    = ""
                st.session_state["cfg_whatsapp_phone_id"] = ""
except Exception:
    st.session_state["cfg_actualizar_alquiler_auto"] = True
    st.session_state["cfg_whatsapp_habilitado"]      = False
    st.session_state["cfg_whatsapp_token"]           = ""
    st.session_state["cfg_whatsapp_phone_id"]        = ""

# Cargar permiso de WhatsApp del usuario actual — siempre desde BD
# Superadmin siempre tiene WhatsApp habilitado
if st.session_state.get("usuario_rol") == "superadmin":
    st.session_state["usr_whatsapp_habilitado"] = True
else:
    try:
        with _pg_conn() as _conn_wa_s:
            with _conn_wa_s.cursor() as _cur_wa_s:
                _cur_wa_s.execute(
                    "SELECT whatsapp_habilitado FROM permisos_usuario WHERE username = %s LIMIT 1",
                    (st.session_state.get("usuario_actual", ""),)
                )
                _row_wa_s = _cur_wa_s.fetchone()
                st.session_state["usr_whatsapp_habilitado"] = bool(_row_wa_s["whatsapp_habilitado"]) if _row_wa_s else False
    except Exception:
        st.session_state["usr_whatsapp_habilitado"] = False

# ── Envío automático de recordatorios WhatsApp ──────────────────────────
_hoy_rec = datetime.now().date()
_flag_rec = f"recordatorios_enviados_{_hoy_rec.strftime('%Y-%m-%d')}"

if (
    st.session_state.get("cfg_whatsapp_habilitado", False) and
    not st.session_state.get(_flag_rec, False)
):
    try:
        _eid_rec = st.session_state.get("empresa_id", 0)
        _hoy_dia = _hoy_rec.day

        # Verificar si hoy es un día de recordatorio configurado
        with _pg_conn() as _conn_rec_auto:
            with _conn_rec_auto.cursor() as _cur_rec_auto:
                _cur_rec_auto.execute(
                    "SELECT tipo, dia_del_mes FROM whatsapp_recordatorios WHERE empresa_id = %s AND activo = TRUE AND dia_del_mes = %s",
                    (_eid_rec, _hoy_dia)
                )
                _recs_hoy = _cur_rec_auto.fetchall()

        if _recs_hoy:
            _wa_creds_rec = _get_wa_credenciales(_eid_rec)

            if _wa_creds_rec:
                # Obtener contratos activos con datos necesarios
                with _pg_conn() as _conn_c_rec:
                    with _conn_c_rec.cursor() as _cur_c_rec:
                        _cur_c_rec.execute("""
                            SELECT c.codigo, c.fin_contrato, c.prox_actualizacion,
                                   c.indice, p.calle, p.numero, p.piso, p.departamento,
                                   i.nombres, i.apellidos, i.telefono
                            FROM contratos c
                            JOIN propiedades p ON c.propiedad_id = p.id
                            JOIN inquilinos i ON c.dni_inquilino = i.dni
                            WHERE c.empresa_id = %s AND c.estado = 'Activo'
                            AND i.telefono IS NOT NULL AND i.telefono != ''
                        """, (_eid_rec,))
                        _contratos_rec = _cur_c_rec.fetchall()

                _fecha_hoy_str = _hoy_rec.strftime("%Y-%m-%d")
                _enviados = 0

                for _tipo_rec in _recs_hoy:
                    _tipo = _tipo_rec["tipo"]

                    for _c_rec in _contratos_rec:
                        # Verificar si ya se envió hoy para este contrato y tipo
                        with _pg_conn() as _conn_log:
                            with _conn_log.cursor() as _cur_log:
                                _cur_log.execute(
                                    "SELECT id FROM whatsapp_recordatorios_log WHERE empresa_id = %s AND tipo = %s AND codigo_contrato = %s AND fecha_envio = %s",
                                    (_eid_rec, _tipo, _c_rec["codigo"], _fecha_hoy_str)
                                )
                                if _cur_log.fetchone():
                                    continue  # Ya enviado hoy

                        # Armar dirección
                        _dir_rec = f"{_c_rec.get('calle','')} {_c_rec.get('numero','')}".strip()
                        if _c_rec.get("piso"):
                            _dir_rec += f" Piso {_c_rec['piso']}"
                        if _c_rec.get("departamento"):
                            _dir_rec += f" Depto {_c_rec['departamento']}"
                        _nombre_rec = f"{_c_rec.get('nombres','')} {_c_rec.get('apellidos','')}".strip()
                        _tel_rec = str(_c_rec.get("telefono","") or "").strip().replace(" ","").replace("-","")

                        _enviado_ok = False

                        if _tipo == "vencimiento" and _c_rec.get("fin_contrato"):
                            try:
                                _fin_rec = datetime.strptime(str(_c_rec["fin_contrato"])[:10], "%Y-%m-%d").date()
                                _enviado_ok = _enviar_mensaje_whatsapp(
                                    phone_id=_wa_creds_rec["phone_id"],
                                    token=_wa_creds_rec["token"],
                                    numero_destino=_tel_rec,
                                    template_name="recordatorio_vencimiento_contrato",
                                    variables=[
                                        _nombre_rec,
                                        _dir_rec,
                                        _fin_rec.strftime("%d/%m/%Y"),
                                    ]
                                )
                            except Exception as _e_rv:
                                logging.warning(f"[Recordatorio] Error vencimiento contrato {_c_rec['codigo']}: {_e_rv}")

                        elif _tipo == "actualizacion" and _c_rec.get("prox_actualizacion"):
                            try:
                                _prox_rec = datetime.strptime(str(_c_rec["prox_actualizacion"])[:10], "%Y-%m-%d").date()
                                _enviado_ok = _enviar_mensaje_whatsapp(
                                    phone_id=_wa_creds_rec["phone_id"],
                                    token=_wa_creds_rec["token"],
                                    numero_destino=_tel_rec,
                                    template_name="recordatorio_actualizacion_alquiler",
                                    variables=[
                                        _nombre_rec,
                                        _prox_rec.strftime("%d/%m/%Y"),
                                        _dir_rec,
                                        _c_rec.get("indice", "ICL"),
                                    ]
                                )
                            except Exception as _e_ra:
                                logging.warning(f"[Recordatorio] Error actualización contrato {_c_rec['codigo']}: {_e_ra}")

                        # Registrar en log
                        if _enviado_ok:
                            try:
                                with _pg_conn() as _conn_log2:
                                    with _conn_log2.cursor() as _cur_log2:
                                        _cur_log2.execute(
                                            "INSERT INTO whatsapp_recordatorios_log (empresa_id, tipo, codigo_contrato, fecha_envio, enviado) VALUES (%s, %s, %s, %s, TRUE)",
                                            (_eid_rec, _tipo, _c_rec["codigo"], _fecha_hoy_str)
                                        )
                                    _conn_log2.commit()
                                _enviados += 1
                            except Exception as _e_log:
                                logging.warning(f"[Recordatorio] Error guardando log: {_e_log}")

                logging.info(f"[Recordatorio] {_enviados} mensajes enviados para el día {_hoy_dia}.")

        # Marcar como procesado para hoy
        st.session_state[_flag_rec] = True

    except Exception as _e_rec_auto:
        logging.warning(f"[Recordatorio] Error en proceso automático: {_e_rec_auto}")
    except Exception:
        st.session_state["usr_whatsapp_habilitado"] = False

# ── Envío automático de recordatorios WhatsApp ─────────────────────────
# Se ejecuta una vez por día por sesión si WhatsApp está habilitado
_hoy_rec = datetime.now().date()
_key_rec_hoy = f"recordatorios_enviados_{_hoy_rec}"
if (
    st.session_state.get("cfg_whatsapp_habilitado", False) and
    not st.session_state.get(_key_rec_hoy, False)
):
    try:
        _eid_rec = st.session_state.get("empresa_id", 0)
        _dia_hoy = _hoy_rec.day

        # Verificar si hoy hay recordatorios activos configurados
        with _pg_conn() as _conn_rec_auto:
            with _conn_rec_auto.cursor() as _cur_rec_auto:
                _cur_rec_auto.execute(
                    "SELECT tipo FROM whatsapp_recordatorios WHERE empresa_id = %s AND dia_del_mes = %s AND activo = TRUE",
                    (_eid_rec, _dia_hoy)
                )
                _tipos_hoy = [r["tipo"] for r in _cur_rec_auto.fetchall()]

        if _tipos_hoy:
            _wa_creds_rec = _get_wa_credenciales(_eid_rec)

            if _wa_creds_rec:
                # Obtener contratos activos con datos necesarios
                with _pg_conn() as _conn_c_rec:
                    with _conn_c_rec.cursor() as _cur_c_rec:
                        _cur_c_rec.execute("""
                            SELECT c.codigo, c.fin_contrato, c.prox_actualizacion, c.indice,
                                   i.nombres, i.apellidos, i.telefono,
                                   p.calle, p.numero, p.departamento
                            FROM contratos c
                            JOIN propiedades p ON c.alias_propiedad = p.alias_propiedad
                            JOIN inquilinos i ON c.dni_inquilino = i.dni
                            WHERE c.empresa_id = %s AND c.estado = 'Activo'
                        """, (_eid_rec,))
                        _contratos_rec = _cur_c_rec.fetchall()

                _fecha_hoy_str = _hoy_rec.strftime("%d/%m/%Y")
                _enviados = 0

                for _cr in _contratos_rec:
                    _tel = str(_cr["telefono"] or "").strip().replace(" ","").replace("-","")
                    if not _tel:
                        continue

                    _nombre = f"{_cr['nombres']} {_cr['apellidos']}".strip()
                    _dir = f"{_cr['calle']} {_cr['numero']}"
                    if _cr.get("departamento"):
                        _dir += f" Dto. {_cr['departamento']}"

                    # Verificar si ya se envió hoy este recordatorio
                    with _pg_conn() as _conn_log:
                        with _conn_log.cursor() as _cur_log:
                            _cur_log.execute(
                                "SELECT id FROM whatsapp_recordatorios_log WHERE empresa_id = %s AND codigo_contrato = %s AND fecha_envio = %s",
                                (_eid_rec, _cr["codigo"], _fecha_hoy_str)
                            )
                            _ya_enviado = _cur_log.fetchone()

                    if _ya_enviado:
                        continue

                    _enviado_algo = False

                    # Recordatorio vencimiento
                    if "vencimiento" in _tipos_hoy and _cr["fin_contrato"]:
                        try:
                            _fin_d = datetime.strptime(str(_cr["fin_contrato"])[:10], "%Y-%m-%d").date()
                            _fin_fmt = _fin_d.strftime("%d/%m/%Y")
                            _ok = _enviar_mensaje_whatsapp(
                                phone_id=_wa_creds_rec["phone_id"],
                                token=_wa_creds_rec["token"],
                                numero_destino=_tel,
                                template_name="recordatorio_vencimiento_contrato",
                                variables=[_nombre, _dir, _fin_fmt]
                            )
                            if _ok:
                                _enviado_algo = True
                                _enviados += 1
                        except Exception as _e_rv:
                            logging.warning(f"[WA Recordatorio vencimiento] contrato {_cr['codigo']}: {_e_rv}")

                    # Recordatorio actualización
                    if "actualizacion" in _tipos_hoy and _cr["prox_actualizacion"]:
                        try:
                            _prox_d = datetime.strptime(str(_cr["prox_actualizacion"])[:10], "%Y-%m-%d").date()
                            _prox_fmt = _prox_d.strftime("%d/%m/%Y")
                            _indice = str(_cr["indice"] or "ICL")
                            _ok = _enviar_mensaje_whatsapp(
                                phone_id=_wa_creds_rec["phone_id"],
                                token=_wa_creds_rec["token"],
                                numero_destino=_tel,
                                template_name="recordatorio_actualizacion_alquiler",
                                variables=[_nombre, _prox_fmt, _dir, _indice]
                            )
                            if _ok:
                                _enviado_algo = True
                                _enviados += 1
                        except Exception as _e_ra:
                            logging.warning(f"[WA Recordatorio actualizacion] contrato {_cr['codigo']}: {_e_ra}")

                    # Registrar en el log si se envió algo
                    if _enviado_algo:
                        try:
                            with _pg_conn() as _conn_log2:
                                with _conn_log2.cursor() as _cur_log2:
                                    _cur_log2.execute(
                                        "INSERT INTO whatsapp_recordatorios_log (empresa_id, tipo, codigo_contrato, fecha_envio) VALUES (%s, %s, %s, %s)",
                                        (_eid_rec, ",".join(_tipos_hoy), _cr["codigo"], _fecha_hoy_str)
                                    )
                                _conn_log2.commit()
                        except Exception as _e_log:
                            logging.warning(f"[WA Log] Error guardando log: {_e_log}")

                if _enviados > 0:
                    logging.info(f"[WA Recordatorios] {_enviados} mensajes enviados el {_fecha_hoy_str}")

        st.session_state[_key_rec_hoy] = True

    except Exception as _e_rec_auto:
        logging.warning(f"[WA Recordatorios] Error general: {_e_rec_auto}")

# 2. Definición maestra de pestañas
pestanas_maestras = {
    "📈 Tablero de Control": "dashboard",
    "📊 Planilla de Contratos": "planilla", 
    "💰 Registrar / Emitir Recibo": "pagos",
    "🗄️ Historial de Caja": "historial_pagos",
    "📝 Carga de Contratos": "carga", 
    "⚙️ Cargar Inquilinos / Propiedades": "auxiliares",
    "🔧 Gastos de Propiedades": "gastos",
    "📑 Rendición a Propietarios": "rendicion"
}

# --- AQUÍ VA EL BLOQUE QUE ME PREGUNTAS ---
# Es el encargado de filtrar qué elementos de 'pestanas_maestras' 
# son visibles para el usuario según su rol o permisos guardados en sesión.
if rol_actual == "superadmin":
    # Superadmin: acceso total a todas las pestañas sin restricción
    pestanas_visibles_nombres = list(pestanas_maestras.keys()) + ["⚙️ Panel de Gestión", "📄 Términos y Condiciones"]
    pestanas_visibles_claves = list(pestanas_maestras.values()) + ["panel_gestion", "terminos"]
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
    pestanas_visibles_nombres.append("📄 Términos y Condiciones")
    pestanas_visibles_claves.append("terminos")
elif rol_actual == "propietario":
    # Propietario: acceso de solo lectura a Dashboard, Planilla e Historial de Caja
    _pestanas_propietario = ["dashboard", "planilla", "historial_pagos", "gastos", "rendicion"]
    pestanas_visibles_nombres = [n for n, c in pestanas_maestras.items() if c in _pestanas_propietario]
    pestanas_visibles_claves = [c for c in pestanas_maestras.values() if c in _pestanas_propietario]
    pestanas_visibles_nombres.append("📄 Términos y Condiciones")
    pestanas_visibles_claves.append("terminos")
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
    pestanas_visibles_nombres.append("📄 Términos y Condiciones")
    pestanas_visibles_claves.append("terminos")


# =====================================================================
# RENDERIZADO EFECTIVO: MENÚ LATERAL (ÍCONO + NOMBRE)
# =====================================================================
# El expandir/colapsar el sidebar completo lo maneja el control nativo de
# Streamlit (la flecha «» arriba a la izquierda) — no hay forma de engancharle
# código propio desde Python, así que el menú siempre se muestra con
# ícono + nombre, sin un modo "solo ícono" aparte.

def _separar_icono(nombre_completo):
    """Separa '📈 Tablero de Control' en ('📈', 'Tablero de Control')."""
    partes = nombre_completo.split(" ", 1)
    return (partes[0], partes[1]) if len(partes) == 2 else (nombre_completo, "")

# Pestaña activa. Si la guardada ya no es válida para este usuario
# (cambiaron permisos, cambió de rol, etc.) se cae a la primera disponible.
if (
    "pestana_activa" not in st.session_state
    or st.session_state.pestana_activa not in pestanas_visibles_claves
):
    st.session_state.pestana_activa = pestanas_visibles_claves[0] if pestanas_visibles_claves else None

with st.sidebar:
    for _nombre_pest, _clave_pest in zip(pestanas_visibles_nombres, pestanas_visibles_claves):
        _icono_pest, _label_pest = _separar_icono(_nombre_pest)
        _es_activa = (st.session_state.pestana_activa == _clave_pest)
        if st.button(
            f"{_icono_pest}  {_label_pest}",
            key=f"nav_{_clave_pest}",
            use_container_width=True,
            type="primary" if _es_activa else "secondary",
        ):
            st.session_state.pestana_activa = _clave_pest
            st.rerun()

_pestana_activa = st.session_state.pestana_activa

# Inicializamos de forma segura todas las variables de control en None
tab_dashboard = None
tab_planilla = None
tab_pagos = None
tab_historial_pagos = None
tab_carga = None
tab_auxiliares = None
tab_gastos = None
tab_rendicion = None
tab_superadmin = None

# Cada variable es un contenedor real SOLO si es la sección activa — el resto del
# archivo sigue usando "with tab_x:" sin cambios, y de paso esto evita que se
# ejecute el código de las otras 8 secciones en cada rerun (antes corrían todas).
if _pestana_activa == "dashboard":
    tab_dashboard = st.container()
if _pestana_activa == "planilla":
    tab_planilla = st.container()
def _get_wa_credenciales(empresa_id: int) -> dict:
    """
    Obtiene el token y phone_id de WhatsApp para una empresa.
    Resuelve el token desde Supabase Vault si corresponde.
    Retorna {"token": str, "phone_id": str} o None si no está configurado.
    """
    try:
        with _pg_conn() as _conn_wac:
            with _conn_wac.cursor() as _cur_wac:
                _cur_wac.execute("""
                    SELECT ce.whatsapp_habilitado, ce.whatsapp_credenciales_propias,
                           ce.whatsapp_phone_id, ce.whatsapp_token_secret_id,
                           ce.whatsapp_numero_id,
                           wn.phone_id AS pool_phone_id, wn.token_secret_id AS pool_secret_id
                    FROM configuraciones_empresa ce
                    LEFT JOIN whatsapp_numeros wn ON wn.id = ce.whatsapp_numero_id
                    WHERE ce.empresa_id = %s
                """, (empresa_id,))
                _row = _cur_wac.fetchone()
                if not _row or not _row["whatsapp_habilitado"]:
                    return None

                if _row["whatsapp_credenciales_propias"]:
                    # Token propio de la empresa — leer desde Vault
                    _secret_id = _row["whatsapp_token_secret_id"]
                    _phone_id  = _row["whatsapp_phone_id"]
                else:
                    # Token del pool del superadmin
                    _secret_id = _row["pool_secret_id"]
                    _phone_id  = _row["pool_phone_id"]

                if not _secret_id or not _phone_id:
                    return None

                # Leer token desde Vault
                _cur_wac.execute("SELECT leer_token_whatsapp(%s) AS token", (_secret_id,))
                _token_row = _cur_wac.fetchone()
                _token = _token_row["token"] if _token_row else None

                if not _token:
                    return None

                return {"token": _token, "phone_id": _phone_id}
    except Exception as _e_wac:
        logging.warning(f"[WhatsApp] Error obteniendo credenciales: {_e_wac}")
        return None


def _enviar_mensaje_whatsapp(phone_id: str, token: str, numero_destino: str,
                              template_name: str, variables: list, documento_bytes: bytes = None,
                              documento_nombre: str = "documento.pdf") -> bool:
    """
    Envía un mensaje de WhatsApp usando la API de Meta.
    Soporta plantillas con variables y documentos adjuntos.
    """
    import requests as _req
    _headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    _url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"

    # Si hay documento, subirlo primero
    _media_id = None
    if documento_bytes:
        try:
            _upload_url = f"https://graph.facebook.com/v19.0/{phone_id}/media"
            _upload_resp = _req.post(
                _upload_url,
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (documento_nombre, documento_bytes, "application/pdf")},
                data={"messaging_product": "whatsapp"}
            )
            _media_id = _upload_resp.json().get("id")
        except Exception as _e_upload:
            logging.warning(f"[WhatsApp] Error subiendo documento: {_e_upload}")

    # Armar componentes del template
    _components = []
    if _media_id:
        _components.append({
            "type": "header",
            "parameters": [{"type": "document", "document": {"id": _media_id, "filename": documento_nombre}}]
        })
    if variables:
        _components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(v)} for v in variables]
        })

    _payload = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "es_AR"},
            "components": _components
        }
    }

    try:
        _resp = _req.post(_url, headers=_headers, json=_payload, timeout=15)
        _data = _resp.json()
        if _resp.status_code == 200 and "messages" in _data:
            logging.info(f"[WhatsApp] Mensaje enviado a {numero_destino} — template: {template_name}")
            return True
        else:
            logging.warning(f"[WhatsApp] Error enviando a {numero_destino}: {_data}")
            return False
    except Exception as _e_send:
        logging.warning(f"[WhatsApp] Excepción enviando: {_e_send}")
        return False


def _obtener_cotizacion_bna():
    try:
        import urllib.request, json
        url = "https://api.bluelytics.com.ar/v2/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        oficial_venta = data.get("oficial", {}).get("value_sell")
        if oficial_venta:
            return float(oficial_venta)
    except Exception:
        pass
    return None


if _pestana_activa == "pagos":
    tab_pagos = st.container()
if _pestana_activa == "historial_pagos":
    tab_historial_pagos = st.container()
if _pestana_activa == "carga":
    tab_carga = st.container()
if _pestana_activa == "auxiliares":
    tab_auxiliares = st.container()
if _pestana_activa == "gastos":
    tab_gastos = st.container()
if _pestana_activa == "rendicion":
    tab_rendicion = st.container()
if _pestana_activa == "panel_gestion":
    tab_superadmin = st.container()

# =====================================================================
# MEJORA 2: TABLERO DE CONTROL (DASHBOARD INTERACTIVO Y ALERTAS)
# =====================================================================
if tab_dashboard:
    with tab_dashboard:
        st.subheader("⚡ Alertas Estratégicas y Métricas Generales")
        _pf = st.session_state.get("propietario_filtro", "")
        _pf_activo = rol_actual == "propietario" and bool(_pf)
        _eid_dash = st.session_state.get("empresa_id", 0)

        df_dash = _cached_contratos_activos(_eid_dash, _pf if _pf_activo else "")
        # Suma de cobros: usar monto_abonado (nombre real en schema migrado)
        try:
            df_pagos_totales = _cached_pagos_totales(_eid_dash, _pf if _pf_activo else "")
        except Exception as _qe2:
            logging.error(f"[Dashboard] Error en query pagos: {_qe2}")
            st.error("❌ Error al cargar la recaudación. Revisá los logs del servidor.")
            st.stop()
        
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
            except Exception as _e_venc:
                logging.warning(f"[Dashboard] Error procesando vencimiento para fila: {_e_venc}")
                
            opciones_meses = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24}
            _act_raw = row['act_contrato']
            frecuencia = _act_raw if isinstance(_act_raw, int) else opciones_meses.get(str(_act_raw), 6)
            _meses_a_txt = {1:'Mensual',2:'Bimensual',3:'Trimestral',4:'Cuatrimestral',6:'Semestral',12:'Anual',24:'Bianual'}
            _act_lbl = _meses_a_txt.get(frecuencia, str(frecuencia))

            # Usar prox_actualizacion para determinar si corresponde este mes o el próximo
            try:
                _prox_str = str(row.get('prox_actualizacion', '') or '').strip()
                if _prox_str:
                    try: _prox_dt = datetime.strptime(_prox_str, "%Y-%m-%d").date()
                    except Exception: _prox_dt = datetime.strptime(_prox_str, "%d/%m/%Y").date()
                    
                    _mes_actual = fecha_hoy.replace(day=1)
                    _mes_proximo = (_mes_actual + dateutil.relativedelta.relativedelta(months=1))
                    _prox_mes = _prox_dt.replace(day=1)
                    
                    if _prox_mes == _mes_actual:
                        actualizan_este_mes += 1
                        lista_alertas_actualizacion.append(
                            f"📈 **ESTE MES** — Ajustar alquiler de **{row['inquilino']}** ({row['alias_propiedad']}). Frecuencia: {_act_lbl}. Próx. actualización: {_prox_str}."
                        )
                    elif _prox_mes == _mes_proximo:
                        lista_alertas_actualizacion.append(
                            f"📅 **MES PRÓXIMO** — Ajustar alquiler de **{row['inquilino']}** ({row['alias_propiedad']}). Frecuencia: {_act_lbl}. Próx. actualización: {_prox_str}."
                        )
                else:
                    # Fallback: usar mes_vivo % frecuencia
                    mes_vivo = row['mes_contrato'] or 1
                    if ((mes_vivo - 1) % frecuencia) == 0 and mes_vivo > 1:
                        actualizan_este_mes += 1
                        lista_alertas_actualizacion.append(
                            f"📈 Corresponde ajustar alquiler a **{row['inquilino']}** ({row['alias_propiedad']}). Período: {_act_lbl}."
                        )
            except Exception:
                pass

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
                    if "ESTE MES" in alerta:
                        st.warning(alerta)
                    else:
                        st.info(alerta)
            else:
                st.success("✅ No hay actualizaciones de alquiler este mes ni el próximo.")



# =====================================================================
# PESTAÑA 2: VISUALIZACIÓN DE PLANILLA (RESULTADOS CON JOIN)
# =====================================================================
if tab_planilla:
    with tab_planilla:
        st.subheader("📋 Planilla de Cobranzas del Mes")
        # Limpiar caché si se acaba de impactar un cobro
        if st.session_state.get("_limpiar_planilla_cache", False):
            _cached_planilla_cobranzas_mes.clear()
            st.session_state["_limpiar_planilla_cache"] = False

        _pf_plan = st.session_state.get("propietario_filtro", "")
        _pf_plan_activo = rol_actual == "propietario" and bool(_pf_plan)
        _eid_plan = st.session_state.get("empresa_id", 0)
        _hoy_plan = datetime.now()
        _mes_plan = _hoy_plan.month
        _anio_plan = _hoy_plan.year
        _meses_es = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        _nombre_mes = f"{_meses_es[_hoy_plan.month - 1]} {_hoy_plan.year}"

        st.caption(f"Período: **{_nombre_mes}** — contratos activos con estado de pago del mes.")

        try:
            df_cob = _cached_planilla_cobranzas_mes(
                _eid_plan, _mes_plan, _anio_plan,
                _pf_plan if _pf_plan_activo else ""
            )

            if df_cob.empty:
                st.info("No hay contratos activos registrados.")
            else:
                _pagaron = df_cob[df_cob["pagado_mes"] == True]
                _faltan  = df_cob[df_cob["pagado_mes"] == False]
                _res_col1, _res_col2, _res_col3, _res_col4 = st.columns([4, 1, 1, 1])
                _res_col1.markdown(f"✅ **Pagaron:** {len(_pagaron)}  &nbsp;&nbsp;  ⏳ **Faltan pagar:** {len(_faltan)}  &nbsp;&nbsp;  **Total:** {len(df_cob)}")

                # Botón envío masivo de recibos preliminares
                _wa_masivo_ok = (
                    st.session_state.get("cfg_whatsapp_habilitado", False) and
                    st.session_state.get("usr_whatsapp_habilitado", False)
                )
                if _wa_masivo_ok:
                    if _res_col4.button("📲 Enviar preliminares", key="btn_prelim_masivo", use_container_width=True, help="Enviar recibo preliminar a todos los contratos con ✓ marcado"):
                        _wa_creds_masivo = _get_wa_credenciales(_eid_plan)
                        if _wa_creds_masivo:
                            _enviados_masivo = 0
                            _errores_masivo = 0
                            for _, _rm in df_pendientes.iterrows():
                                _key_ver_m = f"datos_verificados_{_rm['codigo_contrato']}"
                                if not st.session_state.get(_key_ver_m, False):
                                    continue
                                _tel_m = str(_rm.get("telefono","") or "").strip().replace(" ","").replace("-","")
                                if not _tel_m:
                                    continue
                                try:
                                    _alq_m = float(str(_alquiler_display(_rm)).replace("$ ","").replace(",","")) if _alquiler_display(_rm) != "—" else 0.0
                                except: _alq_m = 0.0
                                _coch_m = float(_rm["cochera"]) if _rm["cochera"] and str(_rm["cochera"]) not in ("","None","nan") else 0.0
                                _exp_m  = st.session_state.get(f"plan_exp_{_rm['codigo_contrato']}", 0.0)
                                _adic_m = _coch_m + _exp_m
                                _total_m = _alq_m + _adic_m
                                _dir_m = f"{_rm.get('calle','')} {_rm.get('numero','')}".strip()
                                _ok_m = _enviar_mensaje_whatsapp(
                                    phone_id=_wa_creds_masivo["phone_id"],
                                    token=_wa_creds_masivo["token"],
                                    numero_destino=_tel_m,
                                    template_name="recibo_preliminar_alquiler",
                                    variables=[
                                        _rm["inquilino"], _nombre_mes, _dir_m,
                                        f"{_alq_m:,.0f}", f"{_adic_m:,.0f}", f"{_total_m:,.0f}",
                                        datetime.now().date().replace(day=10).strftime("%d/%m/%Y"),
                                    ]
                                )
                                if _ok_m:
                                    _enviados_masivo += 1
                                    st.session_state[f"_reset_ver_{_rm['codigo_contrato']}"] = True
                                else:
                                    _errores_masivo += 1
                            if _enviados_masivo > 0:
                                st.toast(f"✅ {_enviados_masivo} recibo(s) preliminar(es) enviado(s).", icon="✅")
                            if _errores_masivo > 0:
                                st.toast(f"⚠️ {_errores_masivo} envío(s) fallaron.", icon="⚠️")
                            if _enviados_masivo == 0 and _errores_masivo == 0:
                                st.toast("ℹ️ No hay contratos con ✓ marcado para enviar.", icon="ℹ️")
                        else:
                            st.error("❌ Sin credenciales de WhatsApp configuradas.")

                # Botón actualizar valores ICL/IPC del mes
                if _res_col3.button("🔄 Actualizar índices", key="btn_actualizar_indices", use_container_width=True, help="Calcula y guarda alquiler_calculado para todos los contratos ICL/IPC con actualización en el mes actual"):
                    _hoy_act = datetime.now().date()
                    _mes_act = _hoy_act.replace(day=1)
                    _ok_count = 0
                    _err_count = 0
                    with st.spinner("⏳ Calculando índices para contratos del mes..."):
                        # Obtener contratos ICL/IPC con prox_actualizacion en el mes actual ya vencida
                        try:
                            with _pg_conn() as _conn_act:
                                with _conn_act.cursor() as _cur_act:
                                    _cur_act.execute("""
                                        SELECT codigo, indice, inicio_contrato, monto_inicial,
                                               prox_actualizacion, act_contrato
                                        FROM contratos
                                        WHERE empresa_id = %s AND estado = 'Activo'
                                        AND indice IN ('ICL', 'IPC')
                                        AND prox_actualizacion IS NOT NULL
                                    """, (_eid_plan,))
                                    _contratos_act = _cur_act.fetchall()

                            _fecha_calc = datetime.now().strftime("%Y-%m-%d")
                            logging.info(f"[actualizar_indices] hoy={_hoy_act}, mes_act={_mes_act}, contratos encontrados={len(_contratos_act)}")

                            # Obtener contratos ya pagados en el mes actual
                            with _pg_conn() as _conn_pag:
                                with _conn_pag.cursor() as _cur_pag:
                                    _cur_pag.execute("""
                                        SELECT DISTINCT ON (codigo_contrato) codigo_contrato
                                        FROM pagos_historial
                                        WHERE empresa_id = %s
                                        AND EXTRACT(MONTH FROM TO_DATE(SPLIT_PART(fecha, ' ', 1), 'DD/MM/YYYY')) = %s
                                        AND EXTRACT(YEAR  FROM TO_DATE(SPLIT_PART(fecha, ' ', 1), 'DD/MM/YYYY')) = %s
                                        AND saldo_pendiente = 0
                                        ORDER BY codigo_contrato, id DESC
                                    """, (_eid_plan, _hoy_act.month, _hoy_act.year))
                                    _ya_pagados = {r["codigo_contrato"] for r in _cur_pag.fetchall()}
                            logging.info(f"[actualizar_indices] ya pagados este mes: {_ya_pagados}")
                            for _c in _contratos_act:
                                try:
                                    _prox_d = datetime.strptime(str(_c["prox_actualizacion"])[:10], "%Y-%m-%d").date()
                                    _prox_mes = _prox_d.replace(day=1)
                                    logging.info(f"[actualizar_indices] contrato={_c['codigo']} prox={_prox_d} prox_mes={_prox_mes} mes_act={_mes_act} skip={_prox_mes != _mes_act or _prox_d > _hoy_act}")
                                    if _prox_mes != _mes_act or _prox_d > _hoy_act:
                                        continue
                                    # Saltar si ya está pagado este mes
                                    if _c["codigo"] in _ya_pagados:
                                        logging.info(f"[actualizar_indices] contrato={_c['codigo']} ya pagado — omitido")
                                        continue
                                    # Calcular meses desde inicio
                                    _ini_str = str(_c["inicio_contrato"])[:10]
                                    try: _ini_d = datetime.strptime(_ini_str, "%Y-%m-%d").date()
                                    except: _ini_d = datetime.strptime(_ini_str, "%d/%m/%Y").date()
                                    _meses_act = int(_c["act_contrato"] or 4)
                                    _ultima_act = _prox_d - dateutil.relativedelta.relativedelta(months=_meses_act)
                                    _delta = dateutil.relativedelta.relativedelta(_ultima_act, _ini_d)
                                    _meses_calc = (_delta.years * 12) + _delta.months
                                    if _meses_calc <= 0: _meses_calc = _meses_act
                                    _ini_str_fmt = _ini_d  # pasar objeto date, no string
                                    _monto_ini = float(_c["monto_inicial"] or 0)
                                    if _monto_ini <= 0: continue
                                    if _c["indice"] == "ICL":
                                        _val_calc = calcular_valor_actualizado_icl(_monto_ini, _ini_str_fmt, _meses_calc)
                                    else:
                                        _val_calc = calcular_valor_actualizado_ipc(_monto_ini, _ini_str_fmt, _meses_calc)
                                    if _val_calc:
                                        with _pg_conn() as _conn_upd:
                                            with _conn_upd.cursor() as _cur_upd:
                                                _cur_upd.execute(
                                                    "UPDATE contratos SET alquiler_calculado = %s, alquiler_calculado_fecha = %s WHERE codigo = %s",
                                                    (_val_calc, _fecha_calc, _c["codigo"])
                                                )
                                            _conn_upd.commit()
                                        _ok_count += 1
                                except Exception as _e_ci:
                                    logging.warning(f"[actualizar_indices] Error en contrato {_c['codigo']}: {_e_ci}")
                                    _err_count += 1
                        except Exception as _e_act:
                            st.error(f"Error al actualizar índices: {_e_act}")

                    _cached_planilla_cobranzas_mes.clear()
                    if _ok_count > 0:
                        st.success(f"✅ {_ok_count} contrato(s) actualizados correctamente.")
                    if _err_count > 0:
                        st.warning(f"⚠️ {_err_count} contrato(s) no pudieron calcularse.")
                    if _ok_count == 0 and _err_count == 0:
                        st.info("ℹ️ No hay contratos ICL/IPC con actualización pendiente en el mes actual.")

                # ── Botón imprimir: construye y muestra HTML solo al hacer clic ──
                # ── Generar PDF de planilla para descargar ──
                def _generar_pdf_planilla():
                    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                    from reportlab.lib.pagesizes import A4, landscape
                    from reportlab.lib import colors
                    from reportlab.lib.units import mm
                    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                    from io import BytesIO

                    buf = BytesIO()
                    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                                            leftMargin=15*mm, rightMargin=15*mm,
                                            topMargin=15*mm, bottomMargin=15*mm)
                    styles = getSampleStyleSheet()
                    _st_titulo = ParagraphStyle("titulo", parent=styles["Heading2"], fontSize=11, spaceAfter=2)
                    _st_sub    = ParagraphStyle("sub",    parent=styles["Normal"],   fontSize=7.5,  textColor=colors.grey)
                    _st_cell   = ParagraphStyle("cell",   parent=styles["Normal"],   fontSize=7.5)
                    _st_bold   = ParagraphStyle("bold",   parent=styles["Normal"],   fontSize=7.5,  fontName="Helvetica-Bold")

                    story = []
                    story.append(Paragraph(f"Planilla de Cobranzas — {_nombre_mes}", _st_titulo))
                    story.append(Paragraph(
                        f"✅ Pagaron: {len(_pagaron)}   ⏳ Faltan pagar: {len(_faltan)}   Total: {len(df_cob)}",
                        _st_sub))
                    story.append(Spacer(1, 3*mm))

                    # Leyenda de colores
                    from reportlab.platypus import Table as _Table, TableStyle as _TableStyle
                    _ley_data = [[
                        Paragraph("<b>Referencias:</b>", _st_cell),
                        Paragraph("  ", _st_cell),
                        Paragraph("📈 Actualizar este mes", _st_cell),
                        Paragraph("  ", _st_cell),
                        Paragraph("📅 Actualizar mes próximo", _st_cell),
                        Paragraph("  ", _st_cell),
                        Paragraph("🔄 Renovar contrato", _st_cell),
                    ]]
                    _ley_tbl = _Table(_ley_data, colWidths=[30*mm, 4*mm, 55*mm, 4*mm, 58*mm, 4*mm, 45*mm])
                    _ley_tbl.setStyle(_TableStyle([
                        ("BACKGROUND", (2,0), (2,0), colors.HexColor("#fff3cd")),
                        ("BACKGROUND", (4,0), (4,0), colors.HexColor("#d0e8f7")),
                        ("BACKGROUND", (6,0), (6,0), colors.HexColor("#fde8e8")),
                        ("FONTSIZE",   (0,0), (-1,-1), 7),
                        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
                        ("TOPPADDING", (0,0), (-1,-1), 2),
                        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
                        ("LEFTPADDING",   (0,0), (-1,-1), 4),
                        ("GRID", (2,0), (2,0), 0.3, colors.HexColor("#f9a825")),
                        ("GRID", (4,0), (4,0), 0.3, colors.HexColor("#1565c0")),
                        ("GRID", (6,0), (6,0), 0.3, colors.HexColor("#e53935")),
                    ]))
                    story.append(_ley_tbl)
                    story.append(Spacer(1, 3*mm))

                    def _fn(val):
                        try:
                            return f"$ {float(val):,.0f}" if val is not None and str(val) not in ("","None","nan") else "—"
                        except: return "—"

                    def _fn_alq(rp):
                        _hoy = datetime.now().date()
                        _mes_actual = _hoy.replace(day=1)
                        # 1. alquiler_calculado del mes actual
                        try:
                            _calc = float(rp["alquiler_calculado"]) if rp["alquiler_calculado"] is not None and str(rp["alquiler_calculado"]) not in ("","None","nan") else 0.0
                            _cf = str(rp.get("alquiler_calculado_fecha") or "").strip()
                            if _calc > 0 and _cf and _cf not in ("","None","nan"):
                                if datetime.strptime(_cf[:10], "%Y-%m-%d").date().replace(day=1) == _mes_actual:
                                    return _fn(_calc)
                        except: pass
                        # 2. alquiler vigente
                        try:
                            _alq = float(rp["ultimo_alquiler"]) if rp["ultimo_alquiler"] is not None and str(rp["ultimo_alquiler"]) not in ("","None","nan") else 0.0
                            if _alq > 0: return _fn(_alq)
                        except: pass
                        # 3. monto_inicial
                        try:
                            _ini = float(rp["monto_inicial"]) if rp["monto_inicial"] is not None and str(rp["monto_inicial"]) not in ("","None","nan") else 0.0
                            if _ini > 0: return _fn(_ini)
                        except: pass
                        return "—"

                    _fh = datetime.now().date()

                    # Encabezado
                    _data = [["", "Propiedad", "Inquilino", "Próx.Act.", "Alquiler", "Cochera", "F.Pago", "Expensas"]]

                    for _, _rp in df_cob.iterrows():
                        _pr = _rp["prox_actualizacion"]
                        _fi = _rp["fin_contrato"]
                        _ps = "—"
                        _row_color = None
                        try:
                            def _td(v):
                                if v is None: return None
                                import pandas as pd
                                if pd.isna(v) if hasattr(pd,'isna') else False: return None
                                s = str(v)[:10].strip()
                                if s in ("","None","nan","NaT"): return None
                                try: return datetime.strptime(s,"%Y-%m-%d").date()
                                except:
                                    try: return datetime.strptime(s,"%d/%m/%Y").date()
                                    except: return None
                            _fi_d = _td(_fi); _pr_d = _td(_pr)
                            if _pr_d:
                                _ma = _fh.replace(day=1)
                                _mp = _ma + dateutil.relativedelta.relativedelta(months=1)
                                if _fi_d and _pr_d > _fi_d:
                                    _ps = "RENOVAR"
                                    if (_fi_d - _fh).days <= 60: _row_color = colors.HexColor("#fde8e8")
                                elif _pr_d.replace(day=1) == _ma:
                                    _ps = _pr_d.strftime("%Y/%m"); _row_color = colors.HexColor("#fff3cd")
                                elif _pr_d.replace(day=1) == _mp:
                                    _ps = _pr_d.strftime("%Y/%m"); _row_color = colors.HexColor("#d0e8f7")
                                else:
                                    _ps = _pr_d.strftime("%Y/%m")
                        except: pass

                        _icono_color = colors.HexColor("#155724") if _rp["pagado_mes"] else colors.HexColor("#721c24")
                        _icono = Paragraph(
                            f"<font color='{'#155724' if _rp['pagado_mes'] else '#721c24'}'>"
                            f"{'PAGADO' if _rp['pagado_mes'] else 'PEND.'}</font>",
                            _st_cell
                        )
                        _fp = _rp["_pago_fecha"][:10] if _rp["_pago_fecha"] else "—"
                        _data.append([
                            _icono,
                            Paragraph(f"<b>{_rp['alias_propiedad']}</b>", _st_bold),
                            Paragraph(_rp["inquilino"], _st_cell),
                            _ps,
                            _fn_alq(_rp),
                            _fn(_rp["cochera"]),
                            _fp,
                            _fn(_rp["expensas"]),
                        ])

                    # Columnas distribuidas en los 267mm disponibles en landscape A4
                    _col_widths = [18*mm, 33*mm, 70*mm, 22*mm, 32*mm, 28*mm, 22*mm, 32*mm]
                    t = Table(_data, colWidths=_col_widths, repeatRows=1)
                    _ts = [
                        ("BACKGROUND",  (0,0), (-1,0),  colors.HexColor("#2c3e50")),
                        ("TEXTCOLOR",   (0,0), (-1,0),  colors.white),
                        ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
                        ("FONTSIZE",    (0,0), (-1,-1), 7.5),
                        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f9fa")]),
                        ("GRID",        (0,0), (-1,-1), 0.3, colors.HexColor("#dee2e6")),
                        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
                        ("ALIGN",       (3,0), (3,-1),  "CENTER"),
                        ("ALIGN",       (4,0), (7,-1),  "RIGHT"),
                        ("TOPPADDING",  (0,0), (-1,-1), 2),
                        ("BOTTOMPADDING",(0,0),(-1,-1), 2),
                    ]
                    # Colores por fila según actualización
                    for _ri, _rp in enumerate(df_cob.itertuples(), start=1):
                        _pr = getattr(_rp, "prox_actualizacion", None)
                        _fi = getattr(_rp, "fin_contrato", None)
                        try:
                            def _td2(v):
                                if v is None: return None
                                import pandas as pd
                                if pd.isna(v) if hasattr(pd,'isna') else False: return None
                                s = str(v)[:10].strip()
                                if s in ("","None","nan","NaT"): return None
                                try: return datetime.strptime(s,"%Y-%m-%d").date()
                                except:
                                    try: return datetime.strptime(s,"%d/%m/%Y").date()
                                    except: return None
                            _fi_d2 = _td2(_fi); _pr_d2 = _td2(_pr)
                            if _pr_d2:
                                _ma2 = _fh.replace(day=1)
                                _mp2 = _ma2 + dateutil.relativedelta.relativedelta(months=1)
                                if _fi_d2 and _pr_d2 > _fi_d2 and (_fi_d2 - _fh).days <= 60:
                                    _ts.append(("BACKGROUND", (0,_ri), (-1,_ri), colors.HexColor("#fde8e8")))
                                elif _pr_d2.replace(day=1) == _ma2:
                                    _ts.append(("BACKGROUND", (0,_ri), (-1,_ri), colors.HexColor("#fff3cd")))
                                elif _pr_d2.replace(day=1) == _mp2:
                                    _ts.append(("BACKGROUND", (0,_ri), (-1,_ri), colors.HexColor("#d0e8f7")))
                        except: pass

                    t.setStyle(TableStyle(_ts))
                    story.append(t)
                    doc.build(story)
                    return buf.getvalue()

                _pdf_bytes = _generar_pdf_planilla()
                _res_col2.download_button(
                    label="🖨️ Descargar PDF",
                    data=_pdf_bytes,
                    file_name=f"planilla_cobranzas_{_nombre_mes.replace(' ','_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="btn_pdf_planilla"
                )
                st.markdown("---")

                # ── Función de navegación a Registrar/Emitir Recibo ──
                def _ir_a_recibo(row):
                    _key = f"ID: {row['propiedad_id']} | {row['alias_propiedad']} - Inquilino: Cod: {row['inquilino_id']} | {str(row['apellidos']).upper()}, {str(row['nombres']).title()} | Contr: {row['codigo_contrato']}"
                    st.session_state["sb_pago_activo"] = _key
                    st.session_state.pestana_activa = "pagos"
                    st.rerun()

                _mes_actual_dt  = datetime(_anio_plan, _mes_plan, 1)
                _mes_proximo_dt = _mes_actual_dt + dateutil.relativedelta.relativedelta(months=1)

                def _fmt_num(val):
                    try:
                        return f"$ {float(val):,.0f}" if val is not None and str(val) not in ("", "None", "nan") else "—"
                    except (ValueError, TypeError):
                        return "—"

                def _alquiler_display(row):
                    """
                    Prioridad:
                    1. alquiler_calculado si fue calculado este mes
                    2. alquiler (último cobrado)
                    3. monto_inicial
                    4. Alerta si prox_actualizacion ya pasó en este mes pero no hay valor calculado
                    5. —
                    """
                    _hoy = datetime.now().date()
                    _mes_actual = _hoy.replace(day=1)

                    # 1. alquiler_calculado del mes actual
                    try:
                        _calc = float(row["alquiler_calculado"]) if row["alquiler_calculado"] is not None and str(row["alquiler_calculado"]) not in ("","None","nan") else 0.0
                        _calc_fecha_str = str(row["alquiler_calculado_fecha"] or "").strip()
                        if _calc > 0 and _calc_fecha_str and _calc_fecha_str not in ("","None","nan"):
                            _calc_fecha = datetime.strptime(_calc_fecha_str[:10], "%Y-%m-%d").date()
                            if _calc_fecha.replace(day=1) == _mes_actual:
                                return _fmt_num(_calc)
                    except: pass

                    # 2. alquiler vigente (último cobrado)
                    try:
                        _alq = float(row["ultimo_alquiler"]) if row["ultimo_alquiler"] is not None and str(row["ultimo_alquiler"]) not in ("","None","nan") else 0.0
                        if _alq > 0:
                            return _fmt_num(_alq)
                    except: pass

                    # 3. monto_inicial
                    try:
                        _ini = float(row["monto_inicial"]) if row["monto_inicial"] is not None and str(row["monto_inicial"]) not in ("","None","nan") else 0.0
                        if _ini > 0:
                            return _fmt_num(_ini)
                    except: pass

                    return "—"

                def _alquiler_alerta(row):
                    """Devuelve alerta si prox_actualizacion ya pasó en este mes pero no hay valor calculado del mes."""
                    _hoy = datetime.now().date()
                    _mes_actual = _hoy.replace(day=1)
                    try:
                        _prox = row["prox_actualizacion"]
                        if _prox and str(_prox) not in ("","None","nan"):
                            _prox_d = datetime.strptime(str(_prox)[:10], "%Y-%m-%d").date()
                            # La actualización corresponde a este mes y ya pasó
                            if _prox_d.replace(day=1) == _mes_actual and _prox_d <= _hoy:
                                # Verificar si tiene valor calculado del mes
                                _calc_fecha_str = str(row.get("alquiler_calculado_fecha") or "").strip()
                                if not _calc_fecha_str or _calc_fecha_str in ("","None","nan"):
                                    return True
                                _calc_fecha = datetime.strptime(_calc_fecha_str[:10], "%Y-%m-%d").date()
                                if _calc_fecha.replace(day=1) != _mes_actual:
                                    return True
                    except: pass
                    return False

                # ── Renderizado con st.columns (todo en la misma línea) ──
                _COLS = [0.4, 0.3, 0.4, 1.2, 2, 0.7, 1, 0.8, 0.9, 1]
                _HEADERS = ["💰", "", "✓", "Propiedad", "Inquilino", "Próx.Act.", "Alquiler", "Cochera", "F.Pago", "Expensas"]

                def _render_filas(df_iter, grupo_label=None):
                    if grupo_label:
                        st.markdown(f"<div style='background:#495057;color:white;padding:5px 10px;font-size:0.83em;font-weight:600;margin-top:8px;border-radius:4px;'>{grupo_label}</div>", unsafe_allow_html=True)

                    # Encabezado
                    _hcols = st.columns(_COLS)
                    for _hc, _ht in zip(_hcols, _HEADERS):
                        _hc.markdown(f"<div style='font-weight:700;font-size:0.8em;color:#495057;padding:2px 0;border-bottom:2px solid #2c3e50;'>{_ht}</div>", unsafe_allow_html=True)

                    for _, _row in df_iter.iterrows():
                        # Color de fila
                        _prox_raw = _row["prox_actualizacion"]
                        _fin_raw  = _row["fin_contrato"]
                        _bg = ""
                        _prox_str = "—"
                        _leyenda = ""
                        _ley_color = ""
                        _ley_text_color = ""
                        _ley_border = ""
                        try:
                            # Misma lógica que el tablero de control
                            _fecha_hoy_plan = datetime.now().date()

                            # Fin de contrato
                            _fin_dt = None
                            if _fin_raw and str(_fin_raw) not in ("", "None", "nan"):
                                try: _fin_dt = datetime.strptime(str(_fin_raw)[:10], "%Y-%m-%d").date()
                                except ValueError: _fin_dt = datetime.strptime(str(_fin_raw)[:10], "%d/%m/%Y").date()

                            # Próxima actualización
                            _prox_raw_str = str(_prox_raw or "").strip()
                            if _prox_raw_str and _prox_raw_str not in ("None", "nan"):
                                try: _prox_dt = datetime.strptime(_prox_raw_str[:10], "%Y-%m-%d").date()
                                except ValueError: _prox_dt = datetime.strptime(_prox_raw_str[:10], "%d/%m/%Y").date()

                                _mes_actual_p  = _fecha_hoy_plan.replace(day=1)
                                _mes_proximo_p = _mes_actual_p + dateutil.relativedelta.relativedelta(months=1)
                                _prox_mes_p    = _prox_dt.replace(day=1)

                                # Formatear fecha siempre desde el objeto parseado
                                _prox_fmt = _prox_dt.strftime("%Y/%m")

                                # RENOVAR — igual que tablero
                                if _fin_dt and _prox_dt > _fin_dt:
                                    _dias_para_vencer = (_fin_dt - _fecha_hoy_plan).days
                                    _prox_str = "🔄 RENOVAR"
                                    if _dias_para_vencer <= 60:
                                        _bg = "background:#fde8e8"
                                        _leyenda = f"🚨 RENOVAR — El contrato vence en {_dias_para_vencer} día(s)"
                                        _ley_color, _ley_text_color, _ley_border = "#ffb3b3", "#7b0000", "#e53935"

                                # ESTE MES — igual que tablero
                                elif _prox_mes_p == _mes_actual_p:
                                    _prox_str = _prox_fmt
                                    _bg = "background:#fff3cd"
                                    _leyenda = "📈 ESTE MES — Corresponde actualizar el alquiler"
                                    _ley_color, _ley_text_color, _ley_border = "#ffe082", "#7b4f00", "#f9a825"

                                # MES PRÓXIMO — igual que tablero
                                elif _prox_mes_p == _mes_proximo_p:
                                    _prox_str = _prox_fmt
                                    _bg = "background:#d0e8f7"
                                    _leyenda = "📅 MES PRÓXIMO — Actualización inminente"
                                    _ley_color, _ley_text_color, _ley_border = "#90caf9", "#0d47a1", "#1565c0"

                                else:
                                    _prox_str = _prox_fmt

                        except Exception:
                            _prox_str = "—"

                        if _leyenda:
                            st.markdown(f"<div style='background:{_ley_color};padding:2px 10px;font-size:0.76em;font-weight:600;color:{_ley_text_color};border-left:4px solid {_ley_border};border-radius:3px;margin-top:4px;'>{_leyenda}</div>", unsafe_allow_html=True)

                        _estado = "✅ Pagado" if _row["pagado_mes"] else "⏳ Pendiente"
                        _estado_color = "#155724" if _row["pagado_mes"] else "#721c24"
                        _estado_bg    = "#d4edda" if _row["pagado_mes"] else "#f8d7da"
                        _fecha_pago   = _row["_pago_fecha"][:10] if _row["_pago_fecha"] else "—"

                        def _cel(txt, align="left", bold=False):
                            _w = "font-weight:600;" if bold else ""
                            return f"<div style='{_bg};{_w}font-size:0.83em;padding:5px 4px;border-bottom:1px solid #dee2e6;text-align:{align};'>{txt}</div>"

                        _rc = st.columns(_COLS)

                        # 💰 botón — ir a Registrar/Emitir Recibo
                        with _rc[0]:
                            st.markdown(f"<div style='{_bg};padding:3px 0;border-bottom:1px solid #dee2e6;'></div>", unsafe_allow_html=True)
                            if st.button("💰", key=f"btn_recibo_{_row['codigo_contrato']}", help="Ir a Registrar / Emitir Recibo", use_container_width=True):
                                _ir_a_recibo(_row)
                            # Botón confirmar pago — solo para pendientes
                            if not _row["pagado_mes"]:
                                _key_cobro = f"cobro_open_{_row['codigo_contrato']}"
                                if _key_cobro not in st.session_state:
                                    st.session_state[_key_cobro] = False
                                if st.button("✅", key=f"btn_cobro_{_row['codigo_contrato']}", help="Confirmar pago y enviar comprobante", use_container_width=True):
                                    st.session_state[_key_cobro] = not st.session_state[_key_cobro]
                                    st.rerun()

                        # Estado — ícono
                        _icono_estado = "✅" if _row["pagado_mes"] else "⏳"
                        _rc[1].markdown(_cel(_icono_estado, align="center"), unsafe_allow_html=True)

                        # Checkbox "Datos verificados" — solo para pendientes con WhatsApp habilitado
                        _wa_plan_ok = (
                            not _row["pagado_mes"] and
                            st.session_state.get("cfg_whatsapp_habilitado", False) and
                            st.session_state.get("usr_whatsapp_habilitado", False)
                        )
                        _key_verificado = f"datos_verificados_{_row['codigo_contrato']}"
                        if _wa_plan_ok:
                            _rc[2].checkbox("", key=_key_verificado, label_visibility="collapsed",
                                          help="Datos verificados — incluir en envío masivo de recibo preliminar")
                        else:
                            _rc[2].markdown(_cel("", align="center"), unsafe_allow_html=True)

                        # Propiedad
                        _rc[3].markdown(_cel(f"<strong>{_row['alias_propiedad']}</strong>"), unsafe_allow_html=True)

                        # Inquilino
                        _rc[4].markdown(_cel(_row["inquilino"]), unsafe_allow_html=True)

                        # Próx. actualización
                        _rc[5].markdown(_cel(_prox_str, align="center"), unsafe_allow_html=True)

                        # Alquiler — con alerta si corresponde
                        _alq_display = _alquiler_display(_row)
                        _alq_alerta  = _alquiler_alerta(_row)
                        if _alq_alerta:
                            _rc[6].markdown(
                                f"<div style='{_bg};font-size:0.75em;padding:5px 4px;border-bottom:1px solid #dee2e6;"
                                f"color:#856404;background:#fff3cd;border-radius:3px;' title='Los valores no han sido cargados para generar un nuevo cálculo'>"
                                f"⚠️ Sin calcular</div>",
                                unsafe_allow_html=True
                            )
                        else:
                            _rc[6].markdown(_cel(_alq_display, align="right"), unsafe_allow_html=True)

                        # Cochera
                        _rc[7].markdown(_cel(_fmt_num(_row["cochera"]), align="right"), unsafe_allow_html=True)

                        # Fecha pago
                        _rc[8].markdown(_cel(_fecha_pago, align="center"), unsafe_allow_html=True)

                        # Expensas — number_input editable
                        try:
                            _exp_val = float(_row["expensas"]) if _row["expensas"] is not None and str(_row["expensas"]) not in ("", "None", "nan") else 0.0
                        except (ValueError, TypeError):
                            _exp_val = 0.0
                        _key_exp_plan = f"plan_exp_{_row['codigo_contrato']}"
                        if _key_exp_plan not in st.session_state:
                            st.session_state[_key_exp_plan] = _exp_val
                        _exp_nuevo = _rc[9].number_input("Expensas", min_value=0.0, step=500.0, key=_key_exp_plan, label_visibility="collapsed")
                        if _exp_nuevo != _exp_val:
                            try:
                                with _pg_conn() as _conn_exp:
                                    with _conn_exp.cursor() as _cur_exp:
                                        _cur_exp.execute("UPDATE contratos SET expensas = %s WHERE codigo = %s AND empresa_id = %s", (_exp_nuevo, int(_row["codigo_contrato"]), _eid_plan))
                                    _conn_exp.commit()
                                _cached_planilla_cobranzas_mes.clear()
                            except Exception as _e_exp:
                                _rc[9].error(f"Error: {_e_exp}")

                        # ── Envío directo de recibo preliminar ──
                        if _wa_plan_ok:
                            _tel_pre = str(_row.get("telefono", "") or "").strip().replace(" ","").replace("-","")
                            _key_prelim_open = f"prelim_open_{_row['codigo_contrato']}"
                            if _key_prelim_open not in st.session_state:
                                st.session_state[_key_prelim_open] = False

                            if st.button("📋", key=f"btn_prelim_{_row['codigo_contrato']}", help="Ver y enviar recibo preliminar por WhatsApp", use_container_width=False):
                                st.session_state[_key_prelim_open] = not st.session_state[_key_prelim_open]
                                st.rerun()

                            # Preview del mensaje
                            if st.session_state.get(_key_prelim_open, False):
                                try:
                                    _alq_pre = float(str(_alq_display).replace("$ ","").replace(",","")) if _alq_display != "—" else 0.0
                                except: _alq_pre = 0.0
                                _coch_pre = float(_row["cochera"]) if _row["cochera"] and str(_row["cochera"]) not in ("","None","nan") else 0.0
                                _exp_pre  = st.session_state.get(_key_exp_plan, 0.0)
                                _adic_pre = _coch_pre + _exp_pre
                                _total_pre = _alq_pre + _adic_pre
                                _dir_pre = f"{_row.get('calle','')} {_row.get('numero','')}".strip()
                                _nombre_pre = _row["inquilino"]
                                _fecha_lim_pre = datetime.now().date().replace(day=10).strftime("%d/%m/%Y")

                                _texto_preview = (
                                    f"Hola *{_nombre_pre}*, le acercamos el detalle del recibo preliminar "
                                    f"correspondiente al período *{_nombre_mes}* de la propiedad ubicada en *{_dir_pre}*.\n\n"
                                    f"📋 Detalle:\n"
                                    f"• Alquiler: ${_alq_pre:,.0f}\n"
                                    f"• Conceptos adicionales: ${_adic_pre:,.0f}\n"
                                    f"• *Total a abonar: ${_total_pre:,.0f}*\n\n"
                                    f"Por favor verificá los datos y abonalo antes del {_fecha_lim_pre}. "
                                    f"Ante cualquier consulta comunicate con nosotros. Muchas gracias."
                                )

                                with st.expander(f"📋 Vista previa — {_row['alias_propiedad']}", expanded=True):
                                    st.info(_texto_preview)
                                    if not _tel_pre:
                                        st.warning("⚠️ El inquilino no tiene teléfono registrado.")
                                    else:
                                        st.caption(f"📱 Se enviará al: +{_tel_pre}")
                                        _c1, _c2 = st.columns(2)
                                        if _c1.button("📲 Confirmar envío", key=f"btn_confirmar_prelim_{_row['codigo_contrato']}", type="primary"):
                                            _wa_creds_pre = _get_wa_credenciales(st.session_state.get("empresa_id", 0))
                                            if _wa_creds_pre:
                                                _ok_pre = _enviar_mensaje_whatsapp(
                                                    phone_id=_wa_creds_pre["phone_id"],
                                                    token=_wa_creds_pre["token"],
                                                    numero_destino=_tel_pre,
                                                    template_name="recibo_preliminar_alquiler",
                                                    variables=[
                                                        _nombre_pre, _nombre_mes, _dir_pre,
                                                        f"{_alq_pre:,.0f}", f"{_adic_pre:,.0f}",
                                                        f"{_total_pre:,.0f}", _fecha_lim_pre,
                                                    ]
                                                )
                                                if _ok_pre:
                                                    st.session_state[_key_prelim_open] = False
                                                    st.session_state[f"_reset_ver_{_row['codigo_contrato']}"] = True
                                                    st.session_state[f"_msg_prelim_{_row['codigo_contrato']}"] = f"✅ Preliminar enviado a {_nombre_pre}."
                                                    st.rerun()
                                                else:
                                                    st.error("❌ No se pudo enviar.")
                                            else:
                                                st.error("❌ Sin credenciales de WhatsApp.")
                                        if _c2.button("✖️ Cancelar", key=f"btn_cancelar_prelim_{_row['codigo_contrato']}"):
                                            st.session_state[_key_prelim_open] = False
                                            st.rerun()

                            # Toast si se envió en el rerun anterior
                            if st.session_state.pop(f"_reset_ver_{_row['codigo_contrato']}", False):
                                if _key_verificado in st.session_state:
                                    del st.session_state[_key_verificado]
                            _msg_prelim = st.session_state.pop(f"_msg_prelim_{_row['codigo_contrato']}", None)
                            if _msg_prelim:
                                st.toast(_msg_prelim, icon="✅")

                        if not _row["pagado_mes"] and st.session_state.get(f"cobro_open_{_row['codigo_contrato']}", False):
                            with st.expander(f"✅ Confirmar pago — {_row['alias_propiedad']}", expanded=True):
                                _c_col1, _c_col2 = st.columns(2)

                                # Alquiler
                                _alq_cobro_val = float(str(_alq_display).replace("$ ","").replace(",","")) if _alq_display != "—" else 0.0
                                _alq_cobro = _c_col1.number_input("Alquiler ($):", value=_alq_cobro_val, min_value=0.0, step=1000.0, key=f"cobro_alq_{_row['codigo_contrato']}")

                                # Expensas
                                _exp_cobro = _c_col1.number_input("Expensas ($):", value=st.session_state.get(_key_exp_plan, 0.0), min_value=0.0, step=500.0, key=f"cobro_exp_{_row['codigo_contrato']}")

                                # Cochera
                                _coch_cobro_val = float(_row["cochera"]) if _row["cochera"] and str(_row["cochera"]) not in ("","None","nan") else 0.0
                                _coch_cobro = _c_col2.number_input("Cochera ($):", value=_coch_cobro_val, min_value=0.0, step=500.0, key=f"cobro_coch_{_row['codigo_contrato']}")

                                # Método de pago
                                _metodo_cobro = _c_col2.selectbox("Método de pago:", ["Transferencia Bancaria", "Efectivo", "Cheque", "Otro"], key=f"cobro_metodo_{_row['codigo_contrato']}")

                                # Total y monto abonado
                                _total_cobro = _alq_cobro + _exp_cobro + _coch_cobro
                                st.markdown(f"**Total: $ {_total_cobro:,.0f}**")
                                _abonado_cobro = st.number_input("Monto abonado ($):", value=_total_cobro, min_value=0.0, step=1000.0, key=f"cobro_abonado_{_row['codigo_contrato']}")
                                _comentario_cobro = st.text_input("Comentarios (opcional):", key=f"cobro_comentario_{_row['codigo_contrato']}")

                                # WhatsApp opcional
                                _wa_cobro_ok = st.session_state.get("cfg_whatsapp_habilitado", False) and st.session_state.get("usr_whatsapp_habilitado", False)
                                _enviar_wa_cobro = False
                                if _wa_cobro_ok:
                                    _enviar_wa_cobro = st.checkbox("📲 Enviar comprobante por WhatsApp al confirmar", value=True, key=f"cobro_wa_{_row['codigo_contrato']}")

                                _cc1, _cc2 = st.columns(2)
                                if _cc1.button("✅ Confirmar e impactar", key=f"btn_confirmar_cobro_{_row['codigo_contrato']}", type="primary"):
                                    try:
                                        _eid_cobro = st.session_state.get("empresa_id", 0)
                                        _saldo_cobro = max(0.0, _total_cobro - _abonado_cobro)
                                        _periodo_cobro = _nombre_mes

                                        # Buscar datos del contrato para el INSERT
                                        with _pg_conn() as _conn_cobro:
                                            with _conn_cobro.cursor() as _cur_cobro:
                                                # Obtener nro comprobante
                                                _cur_cobro.execute("SELECT COALESCE(MAX(CAST(nro_comprobante AS INTEGER)), 0) + 1 AS nro FROM pagos_historial WHERE empresa_id = %s", (_eid_cobro,))
                                                _nro_cobro = str(_cur_cobro.fetchone()["nro"]).zfill(6)

                                                # INSERT en pagos_historial
                                                _cur_cobro.execute("""
                                                    INSERT INTO pagos_historial (
                                                        empresa_id, codigo_contrato, propiedad, inquilino,
                                                        periodo, monto_alquiler, fecha, metodo_pago, comentario,
                                                        monto_expensas, monto_cochera,
                                                        monto_abonado, saldo_pendiente, saldos_anteriores,
                                                        registrado_por, nro_comprobante, tipo_pago
                                                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                                """, (
                                                    _eid_cobro, _row["codigo_contrato"],
                                                    _row["alias_propiedad"], _row["inquilino"],
                                                    _periodo_cobro, _alq_cobro,
                                                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                                                    _metodo_cobro, _comentario_cobro or "",
                                                    _exp_cobro, _coch_cobro,
                                                    _abonado_cobro, _saldo_cobro, 0.0,
                                                    st.session_state.get("usuario_actual", ""),
                                                    _nro_cobro, "Normal"
                                                ))

                                                # Avanzar mes del contrato
                                                _cur_cobro.execute("SELECT mes_contrato FROM contratos WHERE codigo = %s", (_row["codigo_contrato"],))
                                                _mes_act_cobro = (_cur_cobro.fetchone()["mes_contrato"] or 0) + 1
                                                _cur_cobro.execute("UPDATE contratos SET mes_contrato = %s, alquiler = %s WHERE codigo = %s", (_mes_act_cobro, _alq_cobro, _row["codigo_contrato"]))

                                            _conn_cobro.commit()

                                        st.cache_data.clear()
                                        _cached_planilla_cobranzas_mes.clear()
                                        st.session_state[f"cobro_open_{_row['codigo_contrato']}"] = False
                                        st.session_state["_limpiar_planilla_cache"] = True

                                        # Enviar WhatsApp si corresponde
                                        if _enviar_wa_cobro and _wa_cobro_ok:
                                            _wa_creds_cobro = _get_wa_credenciales(_eid_cobro)
                                            _tel_cobro = str(_row.get("telefono","") or "").strip().replace(" ","").replace("-","")
                                            if _wa_creds_cobro and _tel_cobro:
                                                _dir_cobro = f"{_row.get('calle','')} {_row.get('numero','')}".strip()
                                                _enviar_mensaje_whatsapp(
                                                    phone_id=_wa_creds_cobro["phone_id"],
                                                    token=_wa_creds_cobro["token"],
                                                    numero_destino=_tel_cobro,
                                                    template_name="comprobante_pago_alquiler",
                                                    variables=[
                                                        _row["inquilino"], _periodo_cobro, _dir_cobro,
                                                        f"{_abonado_cobro:,.0f}",
                                                        datetime.now().strftime("%d/%m/%Y"),
                                                        _metodo_cobro,
                                                    ]
                                                )

                                        st.success(f"✅ Cobro de {_row['alias_propiedad']} impactado correctamente.")
                                        st.rerun()

                                    except Exception as _e_cobro:
                                        st.error(f"❌ Error al impactar: {_e_cobro}")

                                if _cc2.button("✖️ Cancelar", key=f"btn_cancelar_cobro_{_row['codigo_contrato']}"):
                                    st.session_state[f"cobro_open_{_row['codigo_contrato']}"] = False
                                    st.rerun()


                df_pendientes = df_cob[df_cob["pagado_mes"] == False]
                df_pagados    = df_cob[df_cob["pagado_mes"] == True]

                if not df_pendientes.empty:
                    _render_filas(df_pendientes, f"⏳ Pendientes de pago — {len(df_pendientes)} contrato(s)")
                if not df_pagados.empty:
                    _render_filas(df_pagados, f"✅ Pagados en {_nombre_mes} — {len(df_pagados)} contrato(s)")


        except Exception as e:
            st.error(f"Error al cargar la planilla de cobranzas: {e}")


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

        # Mostrar mensajes del último impacto si los hay
        if "_msgs_impacto" in st.session_state:
            for _tipo_msg, _txt_msg in st.session_state.pop("_msgs_impacto"):
                getattr(st, _tipo_msg)(_txt_msg)

        # ── Cotización USD — autocargar BNA al abrir la pestaña ───────
        # Auto-cargar cotización BNA si no hay una guardada
        if not st.session_state.get("cotizacion_usd_hist") or st.session_state.get("cotizacion_usd_hist", 0) <= 1:
            _tc_auto = _obtener_cotizacion_bna()
            if _tc_auto:
                st.session_state["cotizacion_usd_hist"] = _tc_auto
                st.session_state["cotizacion_usd_pago_input"] = _tc_auto

        _usd_pago_col, _usd_btn_col, _ = st.columns([2, 1, 2])
        if _usd_btn_col.button("🔄 BNA", help="Obtener cotización oficial BNA", use_container_width=True):
            _tc_bna = _obtener_cotizacion_bna()
            if _tc_bna:
                st.session_state["cotizacion_usd_hist"] = _tc_bna
                st.session_state["cotizacion_usd_pago_input"] = _tc_bna
                st.success(f"Cotización BNA: $ {_tc_bna:,.2f}")
            else:
                st.warning("No se pudo obtener la cotización BNA. Ingresala manualmente.")

        if "cotizacion_usd_pago_input" not in st.session_state:
            st.session_state["cotizacion_usd_pago_input"] = float(st.session_state.get("cotizacion_usd_hist", 1300.0))

        _cotizacion_usd_pago = _usd_pago_col.number_input(
            "💵 Cotización USD al momento del cobro ($ ARS por 1 USD):",
            min_value=1.0,
            step=10.0,
            key="cotizacion_usd_pago_input",
            help="Presioná 🔄 BNA para autocompletar con la cotización oficial del día"
        )
        st.session_state["cotizacion_usd_hist"] = _cotizacion_usd_pago
    
    # CORRECCIÓN: Agregamos c.monto_inicial a la consulta SQL
        query_activos = '''
            SELECT 
                c.codigo, p.id AS propiedad_codigo, p.alias_propiedad, 
                (p.calle || ' ' || p.numero || CASE WHEN p.departamento <> '' AND p.departamento IS NOT NULL THEN ', Dto: ' || p.departamento ELSE '' END) AS propiedad_dir,
                i.id AS inquilino_id, i.apellidos, i.nombres, i.telefono, i.email,
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
            ORDER BY p.id ASC
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
                    
            key_desplegable = f"ID: {r['propiedad_codigo']} | {r['alias_propiedad']} - Inquilino: Cod: {r['inquilino_id']} | {str(r['apellidos']).upper()}, {str(r['nombres']).title()} | Contr: {r['codigo']}"
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
                if meses_a_sumar == 0:
                    prox_actualizacion_calculada = fin_contrato_dt + dateutil.relativedelta.relativedelta(days=1)
                else:
                    prox_actualizacion_calculada = inicio_contrato_dt + dateutil.relativedelta.relativedelta(months=meses_a_sumar)
                    while prox_actualizacion_calculada < fecha_hoy:
                        prox_actualizacion_calculada += dateutil.relativedelta.relativedelta(months=meses_a_sumar)
                    
                necesita_renovacion = False if meses_a_sumar == 0 else prox_actualizacion_calculada > fin_contrato_dt
                
                diferencia_hoy = dateutil.relativedelta.relativedelta(fecha_hoy, inicio_contrato_dt)
                total_meses_transcurridos = (diferencia_hoy.years * 12) + diferencia_hoy.months
                if total_meses_transcurridos < 0: total_meses_transcurridos = 0
                mes_actual_contrato_vivo = total_meses_transcurridos + 1
                
                es_mes_de_actualizacion = False if meses_a_sumar == 0 else ((mes_actual_contrato_vivo - 1) % meses_a_sumar) == 0
                
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

            val_base_expensas      = _safe_float(c_datos.get('expensas'))
            val_base_edesal        = _safe_float(c_datos.get('edesal'))
            val_base_gas           = _safe_float(c_datos.get('gas'))
            val_base_municipalidad = _safe_float(c_datos.get('municipalidad'))
            val_base_cochera       = _safe_float(c_datos.get('cochera'))
            val_base_ooss          = _safe_float(c_datos.get('ooss'))

            _cod = c_datos['codigo']
            _key_expensas       = f"monto_expensas_{_cod}"
            _key_edesal         = f"monto_edesal_{_cod}"
            _key_gas            = f"monto_gas_{_cod}"
            _key_municipalidad  = f"monto_municipalidad_{_cod}"
            _key_cochera        = f"monto_cochera_{_cod}"
            _key_ooss           = f"monto_ooss_{_cod}"

            if _key_expensas      not in st.session_state: st.session_state[_key_expensas]      = val_base_expensas
            if _key_edesal        not in st.session_state: st.session_state[_key_edesal]        = val_base_edesal
            if _key_gas           not in st.session_state: st.session_state[_key_gas]           = val_base_gas
            if _key_municipalidad not in st.session_state: st.session_state[_key_municipalidad] = val_base_municipalidad
            if _key_cochera       not in st.session_state: st.session_state[_key_cochera]       = val_base_cochera
            if _key_ooss          not in st.session_state: st.session_state[_key_ooss]          = val_base_ooss

            ed_col1, ed_col2, ed_col3, ed_col4, ed_col5, ed_col6 = st.columns(6)
            monto_expensas      = ed_col1.number_input("🏢 Expensas Consorcio ($):", min_value=0.0, step=500.0,  key=_key_expensas)
            monto_edesal        = ed_col2.number_input("⚡ Luz (EDESAL) ($):",       min_value=0.0, step=500.0,  key=_key_edesal)
            monto_gas           = ed_col3.number_input("🔥 Gas Natural ($):",        min_value=0.0, step=500.0,  key=_key_gas)
            monto_municipalidad = ed_col4.number_input("🏛️ Tasas Municipales ($):",  min_value=0.0, step=200.0,  key=_key_municipalidad)
            monto_cochera       = ed_col5.number_input("🚗 Alquiler Cochera ($):",   min_value=0.0, step=1000.0, key=_key_cochera)
            monto_ooss          = ed_col6.number_input("💧 Monto OO.SS. ($):",       min_value=0.0, step=200.0,  key=_key_ooss)

            # --- CONCEPTOS ESPECIALES DE CONTRATO UNIFICADOS Y COMPORTAMIENTO IDÉNTICO ---
            st.markdown("#### 📑 Conceptos Especiales de Contrato")
            ed_col_esp1, ed_col_esp2 = st.columns(2)

            # ── HONORARIOS (a cargo del inquilino) ──────────────────────────
            _monto_inicial = _safe_float(c_datos.get('monto_inicial'))
            _raw_hon = c_datos.get('monto_honorarios')
            _cuotas_hon_cfg = _safe_int(c_datos.get('cuota_honorarios'), 0)
            if _raw_hon is None:
                # NULL en BD y hay cuotas pactadas → usar monto_inicial como base
                total_honorarios_inquilino = _monto_inicial if _cuotas_hon_cfg > 0 else 0.0
            else:
                # Valor explícito (incluyendo 0) → respetar siempre
                total_honorarios_inquilino = _safe_float(_raw_hon)
            cuotas_hon_pactadas         = max(1, _cuotas_hon_cfg) if _cuotas_hon_cfg > 0 else 1
            pagado_honorarios_inquilino = _safe_float(c_datos.get('honorarios_pagados'))
            saldo_honorarios_inquilino  = max(0.0, total_honorarios_inquilino - pagado_honorarios_inquilino)
            cuotas_hon_pagadas          = _safe_int(c_datos.get('cuotas_honorarios_pagadas'), 0)
            cuotas_hon_pendientes       = max(0, cuotas_hon_pactadas - cuotas_hon_pagadas)
            valor_cuota_hon = round(total_honorarios_inquilino / cuotas_hon_pactadas, 2) if cuotas_hon_pactadas > 0 and total_honorarios_inquilino > 0 else 0.0
            default_hon = min(valor_cuota_hon, saldo_honorarios_inquilino) if cuotas_hon_pendientes > 0 and total_honorarios_inquilino > 0 else 0.0
            cuotas_hon_pactadas         = max(1, _cuotas_hon_cfg) if _cuotas_hon_cfg > 0 else 1
            pagado_honorarios_inquilino = _safe_float(c_datos.get('honorarios_pagados'))
            saldo_honorarios_inquilino  = max(0.0, total_honorarios_inquilino - pagado_honorarios_inquilino)
            cuotas_hon_pagadas          = _safe_int(c_datos.get('cuotas_honorarios_pagadas'), 0)
            cuotas_hon_pendientes       = max(0, cuotas_hon_pactadas - cuotas_hon_pagadas)

            # Valor de la cuota
            valor_cuota_hon = round(total_honorarios_inquilino / cuotas_hon_pactadas, 2) if cuotas_hon_pactadas > 0 and total_honorarios_inquilino > 0 else 0.0
            # Default: cuota del mes, o 0 si no aplican honorarios
            default_hon = min(valor_cuota_hon, saldo_honorarios_inquilino) if cuotas_hon_pendientes > 0 and total_honorarios_inquilino > 0 else 0.0

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
            # Valores por defecto para garantía — se sobreescriben en el bloque else si hay garantía pactada
            pagado_garantia_inquilino = 0.0
            cuotas_dep_pagadas        = 0
            cuotas_dep_pactadas       = 1
            cuotas_dep_pendientes     = 0
            saldo_garantia_inquilino  = 0.0
            valor_cuota_dep           = 0.0

            if val_teorico_garantia == 0.0:
                # Sin garantía pactada — no usar monto_inicial como fallback
                with ed_col_esp2:
                    st.info("🛡️ Sin garantía pactada.")
                monto_garantia_pago = ed_col_esp2.number_input(
                    "🛡️ Respaldo con Monto Depositado (Garantía) ($):",
                    min_value=0.0, value=0.0, step=1000.0,
                    disabled=True
                )
            else:
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
                _cuota_actual_gar = cuotas_dep_pagadas + 1
                detalles_recibo_servicios.append(f" - Respaldo Monto Depositado (Cuota {_cuota_actual_gar}/{cuotas_dep_pactadas}): $ {monto_garantia_pago:,.2f}")
                desglose_pantalla_pdf.append({"Concepto": f"🛡️ Respaldo con Monto Depositado (Depósito en Garantía) — Cuota {_cuota_actual_gar}/{cuotas_dep_pactadas}", "Monto": monto_garantia_pago})

            # monto_serv_pago se calculará después del expander, desde _desglose_editado
            # Aquí solo definimos los auxiliares que se necesitan antes
            val_imp_inmob = _safe_float(c_datos.get('imp_inmobiliario')) if "[Imp.Inmob: Inquilino]" in str(c_datos['servicios']) else 0.0
            val_ooss = monto_ooss
            # Subtotal provisorio para el campo "Adicionales" (se reemplaza tras el expander)
            monto_serv_pago = val_imp_inmob + monto_expensas + monto_edesal + monto_gas + monto_municipalidad + val_ooss + monto_cochera + monto_honorarios_pago + monto_garantia_pago

            # ── MONTO NETO ALQUILER con cálculo automático de índice ─────────
            val_monto_ini_recibo = _safe_float(c_datos.get('monto_inicial'))
            val_alq_ultimo_recibo = _safe_float(c_datos.get('alquiler'))
            indice_recibo = str(c_datos.get('indice') or 'ICL').upper()

            # Convertir date a datetime igual que en la pestaña de carga
            inicio_contrato_recibo = datetime.combine(inicio_contrato_dt, datetime.min.time())

            # Valor base fallback: alquiler vigente del contrato, o monto inicial si no hay.
            val_base_alq = val_alq_ultimo_recibo if val_alq_ultimo_recibo > 0 else val_monto_ini_recibo
            _key_alq_pago = f"monto_alq_pago_{c_datos['codigo']}"

            st.markdown("#### 💰 Monto Neto de Alquiler")
            _auto_alq_activado = st.session_state.get("cfg_actualizar_alquiler_auto", True)
            if _auto_alq_activado:
                r_col1, r_col2 = st.columns([2, 2])
            else:
                r_col1, r_col2, r_col3 = st.columns([2, 2, 1])
            r_col1.markdown(f"🔗 [Verificar en arquiler.com](https://arquiler.com/pwa?amount={int(val_monto_ini_recibo)}&date={inicio_contrato_dt.strftime('%Y-%m-%d')}&months={meses_a_sumar}&rate={indice_recibo.lower()})")

            # Calcular la última fecha de actualización ya aplicada.
            # Ejemplo: inicio 1-ene-25, trimestral, hoy 10-jun-26 → prox = 1-jul-26 → última = 1-abr-26
            try:
                if meses_a_sumar == 0:
                    _ultima_act_dt = inicio_contrato_dt
                    _meses_hasta_ultima_act = 0
                else:
                    _ultima_act_dt = prox_actualizacion_calculada - dateutil.relativedelta.relativedelta(months=int(meses_a_sumar))
                    _delta_ultima = dateutil.relativedelta.relativedelta(_ultima_act_dt, inicio_contrato_dt)
                    _meses_hasta_ultima_act = (_delta_ultima.years * 12) + _delta_ultima.months
                    # No forzar a meses_a_sumar si es 0 — significa que aún no hubo actualización
            except Exception:
                _meses_hasta_ultima_act = int(meses_a_sumar)

            # Calcula: monto_inicial × (ICL_ultima_actualizacion / ICL_inicio_contrato)
            valor_auto_recibo = None
            _fallo_consulta_indice = False
            _sin_calculo_disponible = False

            # Si el mes de inicio del contrato es el mes actual, no hay período de actualización todavía
            _mismo_mes_inicio_recibo = (
                inicio_contrato_dt.year == datetime.now().year and
                inicio_contrato_dt.month == datetime.now().month
            )

            if indice_recibo in ("ICL", "IPC") and not _mismo_mes_inicio_recibo and _meses_hasta_ultima_act > 0:
                with st.spinner(f"⏳ Consultando {indice_recibo}..."):
                    if indice_recibo == "ICL":
                        valor_auto_recibo = calcular_valor_actualizado_icl(
                            val_monto_ini_recibo, inicio_contrato_recibo, _meses_hasta_ultima_act
                        )
                    elif indice_recibo == "IPC":
                        valor_auto_recibo = calcular_valor_actualizado_ipc(
                            val_monto_ini_recibo, inicio_contrato_recibo, _meses_hasta_ultima_act
                        )
            elif _mismo_mes_inicio_recibo or _meses_hasta_ultima_act <= 0:
                _sin_calculo_disponible = True

            # Guardar alquiler_calculado en la BD si se obtuvo un valor válido
            if valor_auto_recibo is not None:
                try:
                    _fecha_calc_hoy = datetime.now().strftime("%Y-%m-%d")
                    with _pg_conn() as _conn_calc:
                        with _conn_calc.cursor() as _cur_calc:
                            _cur_calc.execute(
                                "UPDATE contratos SET alquiler_calculado = %s, alquiler_calculado_fecha = %s WHERE codigo = %s",
                                (valor_auto_recibo, _fecha_calc_hoy, c_datos['codigo'])
                            )
                        _conn_calc.commit()
                except Exception as _e_calc:
                    logging.warning(f"[alquiler_calculado] No se pudo guardar: {_e_calc}")

            # Valor por defecto del campo editable:
            # - Activado: ICL/IPC calculado → alquiler vigente → monto inicial (se autocompleta)
            # - Desactivado: SIEMPRE el alquiler vigente del contrato (el usuario usa "Aplicar" si quiere el actualizado)
            if _auto_alq_activado:
                _val_default_alq = (valor_auto_recibo if valor_auto_recibo else None) or val_base_alq
            else:
                _val_default_alq = val_base_alq
            if _key_alq_pago not in st.session_state:
                st.session_state[_key_alq_pago] = _val_default_alq

            if valor_auto_recibo is not None:
                valor_auto_recibo_fmt = f"$ {int(valor_auto_recibo):,}".replace(",", ".")
                _fecha_desde_fmt = inicio_contrato_dt.strftime("%d/%m/%Y")
                _fecha_hasta_fmt = _ultima_act_dt.strftime("%d/%m/%Y")
                _help_monto_act = (
                    f"Calculado con datos oficiales del {'BCRA' if indice_recibo == 'ICL' else 'INDEC'} ({indice_recibo}). "
                    f"Período: {_fecha_desde_fmt} → {_fecha_hasta_fmt} "
                    f"({_meses_hasta_ultima_act} meses acumulados desde el inicio del contrato). "
                )
                _help_monto_act += (
                    "Este valor se carga automáticamente en el campo 'Monto Neto Alquiler'."
                    if _auto_alq_activado else
                    "Es solo una sugerencia — no se aplica sola, usá el botón si querés cargarla."
                )
                r_col2.metric(
                    label="📊 Monto Actualizado",
                    value=valor_auto_recibo_fmt,
                    help=_help_monto_act
                )
                if not _auto_alq_activado:
                    r_col3.markdown("<div style='height: 1.9em'></div>", unsafe_allow_html=True)
                    if r_col3.button(
                        "⬅️ Aplicar",
                        key=f"aplicar_monto_act_{c_datos['codigo']}",
                        help="Carga este monto en 'Monto Neto Alquiler' de abajo. No guarda nada en la base de datos todavía — eso recién pasa al impactar el cobro.",
                        use_container_width=True,
                    ):
                        st.session_state[_key_alq_pago] = valor_auto_recibo
                        st.rerun()
            else:
                if meses_a_sumar == 0:
                    _sin_calculo_disponible = True
                elif _mismo_mes_inicio_recibo or _meses_hasta_ultima_act <= 0:
                    r_col2.info(
                        f"ℹ️ Aún no corresponde aplicar actualización por {indice_recibo}. "
                        f"El primer ajuste corresponderá en {prox_actualizacion_calculada.strftime('%m/%Y')}. "
                        "Ingresá el monto manualmente."
                    )
                elif indice_recibo in ("ICL", "IPC"):
                    fuente_r = "BCRA" if indice_recibo == "ICL" else "INDEC"
                    _fallo_consulta_indice = True
                    r_col2.warning(
                        f"⚠️ No se pudo obtener el índice desde {fuente_r}. "
                        "Ingresá el valor manualmente o verificá en arquiler.com (↖).",
                    )
                    # Mostrar detalle del error en un expander para diagnóstico
                    with r_col2.expander("🔍 Ver detalle del error"):
                        try:
                            _url_test = f"https://www.bcra.gob.ar/pdfs/PublicacionesEstadisticas/icl{datetime.now().year}.xls"
                            _r_test = requests.get(_url_test, timeout=8, verify=False)
                            st.caption(f"URL: `{_url_test}`")
                            st.caption(f"HTTP status: `{_r_test.status_code}`")
                            st.caption(f"Content-Type: `{_r_test.headers.get('Content-Type', 'N/A')}`")
                            st.caption(f"Tamaño respuesta: `{len(_r_test.content)} bytes`")
                        except Exception as _e_test:
                            st.caption(f"Error de conexión: `{_e_test}`")
                    if r_col2.button("🔄 Reintentar", key=f"retry_indice_recibo_{c_datos['codigo']}"):
                        _obtener_icl_bcra_xls.clear()
                        _obtener_ipc_indec.clear()
                        st.rerun()
                else:
                    _sin_calculo_disponible = True
                    r_col2.info(
                        f"ℹ️ El índice de este contrato ({indice_recibo}) no tiene cálculo automático. "
                        "Verificá el monto manualmente antes de impactar el cobro.",
                    )


            cp_col1, cp_col2, cp_col3, cp_col4 = st.columns(4)
            monto_alq_pago = cp_col1.number_input("Monto Neto Alquiler ($):", min_value=0.0, step=5000.0, key=_key_alq_pago)
            # cp_col2 y cp_col3 se llenan después del expander con el total real
            _ph_servicios = cp_col2.empty()
            _ph_total     = cp_col3.empty()
            metodo_pago = cp_col4.selectbox("Método de Pago:", ["Transferencia Bancaria", "Efectivo", "Depósito", "Cheque"])

            
            # 3. VISTA PREVIA DEL COMPROBANTE
            with st.expander("🧾 Vista previa del comprobante", expanded=True):
                st.markdown("Revisá los conceptos del comprobante. Solo podés agregar un concepto adicional libre.")

                # ── Encabezado ──
                _ecol_h1, _ecol_h2 = st.columns([3, 1])
                _ecol_h1.markdown("**Descripción**")
                _ecol_h2.markdown("**Monto ($)**")

                # ── Alquiler base — solo lectura ──
                _alq_desc_edit = "Valor Locativo Neto (Alquiler Base)"
                _fila_alq1, _fila_alq2 = st.columns([3, 1])
                _fila_alq1.markdown(_alq_desc_edit)
                _fila_alq2.markdown(f"$ {monto_alq_pago:,.2f}")

                # ── Conceptos de servicio — solo lectura ──
                _desglose_editado = []
                for _item in desglose_pantalla_pdf:
                    _fila1, _fila2 = st.columns([3, 1])
                    _fila1.markdown(_item["Concepto"])
                    _fila2.markdown(f"$ {float(_item['Monto']):,.2f}")
                    _desglose_editado.append({"Concepto": _item["Concepto"], "Monto": float(_item["Monto"])})

                # ── Concepto adicional libre (único editable) ──
                st.markdown("---")
                st.caption("➕ Concepto adicional libre (opcional)")
                _extra_c1, _extra_c2 = st.columns([3, 1])
                _key_extra_desc  = f"extra_desc_{c_datos['codigo']}"
                _key_extra_monto = f"extra_monto_{c_datos['codigo']}"
                if _key_extra_desc  not in st.session_state: st.session_state[_key_extra_desc]  = ""
                if _key_extra_monto not in st.session_state: st.session_state[_key_extra_monto] = 0.0
                _extra_desc = _extra_c1.text_input(
                    "Descripción extra",
                    placeholder="Ej: Sellado de contrato, Multa por mora...",
                    label_visibility="collapsed",
                    key=_key_extra_desc
                )
                _extra_monto = _extra_c2.number_input(
                    "Monto extra",
                    min_value=0.0,
                    step=100.0,
                    label_visibility="collapsed",
                    key=_key_extra_monto
                )
                if _extra_monto > 0:
                    _concepto_extra = _extra_desc.strip() if _extra_desc.strip() else "Concepto adicional"
                    _desglose_editado.append({"Concepto": _concepto_extra, "Monto": _extra_monto})

                # ── Total — se calcula DESPUÉS de incluir el concepto extra ──
                _total_servicios_editado = sum(d["Monto"] for d in _desglose_editado)
                _total_comprobante_editado = monto_alq_pago + _total_servicios_editado
                st.markdown("---")
                st.markdown(f"**Total comprobante: $ {_total_comprobante_editado:,.2f}**")

            # Recalcular monto_serv_pago y total_pago_real desde el desglose editado
            # Esto sincroniza el expander con el campo "Monto Abonado"
            monto_serv_pago = _total_servicios_editado
            total_pago_real = monto_alq_pago + monto_serv_pago
            # Llenar los placeholders con los totales reales
            _ph_servicios.metric("Monto Adicionales / Servicios ($):", value=f"$ {monto_serv_pago:,.2f}".replace(",","v").replace(".",",").replace("v","."))
            _ph_total.metric("TOTAL A RECAUDAR ($):", value=f"$ {total_pago_real:,.2f}".replace(",","v").replace(".",",").replace("v","."))

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

            # Resetear pago_impactado si el período cambia
            _periodo_key = f"_ultimo_periodo_{c_datos['codigo']}"
            if st.session_state.get(_periodo_key) != mes_periodo_texto:
                st.session_state[_periodo_key] = mes_periodo_texto
                st.session_state.pago_impactado = False
                st.session_state.contrato_impactado_id = None

            # --- VALIDACIÓN DE ADELANTO ---
            # Detectar si el período elegido saltea meses sin pagar.
            # indice_default = próximo mes a cobrar (base 0).
            # Si el período elegido está más de un paso adelante → bloquear.
            _idx_elegido = opciones_periodo.index(mes_periodo_texto) if mes_periodo_texto in opciones_periodo else 0
            _hay_salto_adelanto = _idx_elegido > indice_default
            if _hay_salto_adelanto:
                _meses_faltantes = [opciones_periodo[i] for i in range(indice_default, _idx_elegido)]
                st.error(
                    f"🚫 **No se puede registrar el pago del {mes_periodo_texto}** porque hay "
                    f"{len(_meses_faltantes)} mes(es) sin pagar: "
                    f"{', '.join(_meses_faltantes)}. "
                    "Registrá primero los períodos anteriores en orden."
                )

            # --- GASTOS ORDINARIOS PENDIENTES DE COBRO ---
            try:
                with _pg_conn() as _conn_gord:
                    with _conn_gord.cursor() as _cur_gord:
                        _cur_gord.execute("""
                            SELECT SUM(gp.monto) AS total_pendiente, COUNT(*) AS cantidad
                            FROM gastos_propiedades gp
                            JOIN propiedades p ON gp.propiedad_id = p.id
                            WHERE p.alias_propiedad = %s AND gp.empresa_id = %s
                            AND COALESCE(gp.tipo_gasto, 'Extraordinario') = 'Ordinario'
                            AND COALESCE(gp.cobrado, FALSE) = FALSE
                        """, (c_datos.get('propiedad_dir', ''), st.session_state.get('empresa_id', 0)))
                        _gord_row = _cur_gord.fetchone()
                if _gord_row and _gord_row['total_pendiente'] and float(_gord_row['total_pendiente']) > 0:
                    _total_gord = float(_gord_row['total_pendiente'])
                    _cant_gord = int(_gord_row['cantidad'])
                    st.warning(f"🏘️ **Gastos ordinarios pendientes:** {_cant_gord} gasto(s) por **$ {_total_gord:,.2f}** sin cobrar a este inquilino.")
            except Exception:
                pass

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

            # Complementar con la columna saldo_pendiente de registros nuevos.
            # DISTINCT ON (periodo) trae el último registro por período (id DESC),
            # evitando el doble conteo cuando un período fue absorbido por un cobro posterior.
            with _pg_conn() as _conn_sp:
                with _conn_sp.cursor() as _cur_sp:
                    _cur_sp.execute(
                        """SELECT DISTINCT ON (periodo) periodo, saldo_pendiente
                           FROM pagos_historial
                           WHERE codigo_contrato = %s AND periodo != %s
                           ORDER BY periodo, id DESC""",
                        (c_datos['codigo'], mes_periodo_texto)
                    )
                    _sp_rows = _cur_sp.fetchall()
            # La columna saldo_pendiente tiene prioridad sobre el texto del comentario.
            # Si el último registro del período tiene saldo 0, ese período está saldado.
            for _sp_row in _sp_rows:
                _p_sp = _sp_row["periodo"]
                _s_sp = float(_sp_row["saldo_pendiente"] or 0)
                if _s_sp > 0:
                    _saldos_anteriores_detalle[_p_sp] = _s_sp
                else:
                    _saldos_anteriores_detalle.pop(_p_sp, None)

            # Separar saldos positivos (deuda) de negativos (a favor del inquilino)
            _saldos_anteriores_detalle = {p: s for p, s in _saldos_anteriores_detalle.items() if s != 0}
            _saldos_a_favor_detalle    = {p: s for p, s in _saldos_anteriores_detalle.items() if s < 0}
            _saldos_anteriores_detalle = {p: s for p, s in _saldos_anteriores_detalle.items() if s > 0}
            _total_saldos_anteriores   = sum(_saldos_anteriores_detalle.values())
            _total_saldos_a_favor      = sum(_saldos_a_favor_detalle.values())  # negativo

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
                    st.info(f"✅ **{mes_periodo_texto} ya fue liquidado** (Total abonado: $ {_total_abonado_periodo:,.2f}). Podés registrar una corrección si hubo un error en algún concepto.")
                    _key_modo_correccion = f"modo_correccion_{c_datos['codigo']}_{mes_periodo_texto}"
                    if _key_modo_correccion not in st.session_state:
                        st.session_state[_key_modo_correccion] = False
                    if not st.session_state[_key_modo_correccion]:
                        if st.button("✏️ Registrar Corrección", key=f"btn_correccion_{c_datos['codigo']}_{mes_periodo_texto}"):
                            st.session_state[_key_modo_correccion] = True
                            st.rerun()
                    _es_modo_correccion = st.session_state.get(_key_modo_correccion, False)
            else:
                # Período nuevo: mostrar y sumar saldos anteriores si existen
                if _total_saldos_anteriores > 0:
                    _detalle_saldos = " | ".join([f"{p}: $ {s:,.2f}" for p, s in _saldos_anteriores_detalle.items() if s > 0])
                    st.warning(f"📋 Saldos pendientes de períodos anteriores: $ {_total_saldos_anteriores:,.2f} ({_detalle_saldos})")

            # Total a cubrir en este recibo:
            # - Período con saldo parcial → cubrir ese saldo
            # - Período nuevo → total del mes + saldos de períodos anteriores - saldos a favor
            # - Modo corrección → el usuario ingresa la diferencia (puede ser negativa)
            _es_modo_correccion = st.session_state.get(f"modo_correccion_{c_datos['codigo']}_{mes_periodo_texto}", False)
            if saldo_periodo_anterior > 0:
                _total_a_cubrir = saldo_periodo_anterior
            elif _es_modo_correccion:
                _total_a_cubrir = 0.0  # el usuario ingresa la diferencia libremente
            elif not _row_existente:
                _total_a_cubrir = total_pago_real + _total_saldos_anteriores + _total_saldos_a_favor
                if _total_saldos_anteriores > 0 or _total_saldos_a_favor < 0:
                    cp_col3.empty()
                    _msg_total = f"💰 **TOTAL A RECAUDAR: $ {_total_a_cubrir:,.2f}**  *(Mes actual: $ {total_pago_real:,.2f}"
                    if _total_saldos_anteriores > 0:
                        _msg_total += f" + Saldos anteriores: $ {_total_saldos_anteriores:,.2f}"
                    if _total_saldos_a_favor < 0:
                        _msg_total += f" − Saldo a favor: $ {abs(_total_saldos_a_favor):,.2f}"
                    _msg_total += ")*"
                    st.info(_msg_total)
                if _total_saldos_a_favor < 0:
                    _detalle_favor = " | ".join([f"{p}: $ {abs(s):,.2f}" for p, s in _saldos_a_favor_detalle.items()])
                    st.success(f"🟢 Saldo a favor del inquilino: $ {abs(_total_saldos_a_favor):,.2f} ({_detalle_favor}) — descontado del total.")
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
            if _es_modo_correccion:
                st.warning("✏️ **Modo corrección activo** — Ingresá la diferencia a registrar. Usá un monto **negativo** si hay que devolver dinero al inquilino.")
                _key_corr_monto = f"corr_monto_{c_datos['codigo']}_{mes_periodo_texto}"
                if _key_corr_monto not in st.session_state:
                    st.session_state[_key_corr_monto] = 0.0
                monto_abonado = saldo_col1.number_input(
                    "✏️ Diferencia a registrar ($):",
                    value=st.session_state[_key_corr_monto],
                    step=1000.0,
                    key=_key_corr_monto,
                    help="Positivo: el inquilino paga más. Negativo: se le devuelve dinero."
                )
                saldo_pendiente = monto_abonado  # en corrección el saldo = la diferencia (puede ser negativa)
            else:
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

            # ── Confirmación si el Monto Neto Alquiler difiere del Monto Actualizado, o si no se pudo verificar ──
            _difiere_monto_alq = (
                valor_auto_recibo is not None
                and abs(float(valor_auto_recibo) - float(monto_alq_pago)) > 0.01
            )
            _requiere_confirmacion = _difiere_monto_alq or _fallo_consulta_indice or _sin_calculo_disponible
            _key_conf_dif = f"confirmar_dif_monto_{c_datos['codigo']}_{mes_periodo_texto}"

            _clic_impactar = st.button(
                "📥 Impactar Cobro en Caja Histórica" if not _es_modo_correccion else "✏️ Confirmar Corrección",
                type="primary",
                disabled=bool(
                    _hay_salto_adelanto or
                    (_row_existente and saldo_periodo_anterior == 0 and not _es_modo_correccion)
                )
            )

            _debe_guardar_cobro = False
            if _clic_impactar:
                if _requiere_confirmacion:
                    st.session_state[_key_conf_dif] = "pedir"
                else:
                    _debe_guardar_cobro = True

            if st.session_state.get(_key_conf_dif) == "pedir":
                if _difiere_monto_alq:
                    st.warning(
                        f"⚠️ El **Monto Neto Alquiler** cargado (\\$ {monto_alq_pago:,.2f}) es distinto al "
                        f"**Monto Actualizado** calculado por {indice_recibo} (\\$ {valor_auto_recibo:,.2f}). "
                        "¿Confirmás que querés impactar el cobro con el monto que está cargado?"
                    )
                elif _fallo_consulta_indice:
                    st.warning(
                        f"⚠️ No se pudo consultar el índice **{indice_recibo}** para verificar si el "
                        f"**Monto Neto Alquiler** (\\$ {monto_alq_pago:,.2f}) está actualizado. "
                        "¿Confirmás que querés impactar el cobro igual, sin esa verificación?"
                    )
                else:
                    st.warning(
                        f"⚠️ Este contrato usa índice **{indice_recibo}**, que no tiene cálculo automático. "
                        f"No hay forma de verificar si el **Monto Neto Alquiler** (\\$ {monto_alq_pago:,.2f}) está actualizado. "
                        "¿Confirmás que el monto es correcto e impactás el cobro?"
                    )
                _wc1, _wc2 = st.columns(2)
                if _wc1.button("✅ Sí, confirmar e impactar igual", type="primary", key=f"conf_dif_si_{c_datos['codigo']}"):
                    st.session_state[_key_conf_dif] = None
                    _debe_guardar_cobro = True
                if _wc2.button("❌ Cancelar y revisar el monto", key=f"conf_dif_no_{c_datos['codigo']}"):
                    st.session_state[_key_conf_dif] = None
                    st.info("Cobro no impactado. Ajustá el monto si hace falta y volvé a intentar.")
                    st.rerun()

            if _debe_guardar_cobro:
                conn = conectar_db()
                cursor = conn.cursor()
                try:
                    # --- PROTECCIÓN CONTRA DOBLE COBRO SIMULTÁNEO ---
                    # Adquirir advisory lock sobre contrato+período ANTES de cualquier lectura o escritura.
                    # Si dos usuarios presionan "Impactar" al mismo tiempo para el mismo contrato/período,
                    # PostgreSQL serializa las dos transacciones: la segunda espera a que la primera termine.
                    # El lock se libera automáticamente al hacer commit o rollback.
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))",
                        (f"{c_datos['codigo']}|{mes_periodo_texto}",)
                    )
                    # Re-verificar dentro del lock: el estado puede haber cambiado
                    # desde que se cargó la pantalla hasta que el usuario presionó "Impactar"
                    cursor.execute(
                        "SELECT monto_abonado AS monto_total FROM pagos_historial "
                        "WHERE codigo_contrato = %s AND periodo = %s ORDER BY id DESC",
                        (c_datos['codigo'], mes_periodo_texto)
                    )
                    _rows_existentes = cursor.fetchall()
                    # --- FIN PROTECCIÓN ---

                    # 1. Guarda el registro en el historial de cobros con los montos recalculados
                    # Saldo real = lo que faltó cubrir de este recibo
                    _es_correccion_insert = st.session_state.get(f"modo_correccion_{c_datos['codigo']}_{mes_periodo_texto}", False)
                    if _es_correccion_insert:
                        # En corrección el saldo puede ser negativo (a favor del inquilino)
                        _saldo_a_guardar = monto_abonado  # positivo: debe más; negativo: a favor
                        _comentario_completo = f"[CORRECCIÓN] {comentarios_pago or ''} | Diferencia: $ {monto_abonado:,.2f}".strip()
                        # Limpiar modo corrección después de impactar
                        st.session_state[f"modo_correccion_{c_datos['codigo']}_{mes_periodo_texto}"] = False
                    else:
                        _saldo_a_guardar = max(0.0, _total_a_cubrir - monto_abonado)
                        _comentario_completo = comentarios_pago or ""
                        if _saldo_a_guardar > 0:
                            _comentario_completo += f" | Abonado: $ {monto_abonado:,.2f} | Saldo: $ {_saldo_a_guardar:,.2f}"
                    # Generar número de comprobante secuencial único (atómico, seguro ante concurrencia)
                    _nro_comprobante_insert = _generar_nro_comprobante(
                        st.session_state.get("empresa_id", 0)
                    )
                    st.session_state["ultimo_nro_comprobante"] = _nro_comprobante_insert
                    _val_ooss_insert = _safe_float(c_datos.get('ooss'))
                    _val_imp_insert = _safe_float(c_datos.get('imp_inmobiliario')) if "[Imp.Inmob: Inquilino]" in str(c_datos.get('servicios','')) else 0.0
                    # Calcular valores USD al tipo de cambio del momento
                    _tc_insert = st.session_state.get("cotizacion_usd_hist", 0.0)
                    _tc_insert = float(_tc_insert) if float(_tc_insert) > 0 else 0.0
                    _alq_usd    = round(monto_alq_pago / _tc_insert, 2)    if _tc_insert > 0 else 0.0
                    _coch_usd   = round(monto_cochera / _tc_insert, 2)     if _tc_insert > 0 else 0.0
                    _imp_usd    = round(_val_imp_insert / _tc_insert, 2)   if _tc_insert > 0 else 0.0
                    _ret_agencia = round(monto_abonado * _safe_float(c_datos.get('honorarios')) / 100.0, 2)
                    # Si ya existe un pago para este período, el alquiler ya fue registrado
                    # El segundo pago solo registra el complemento (monto_abonado), no duplica el alquiler
                    _monto_alq_insert = monto_alq_pago if not _rows_existentes else 0.0
                    _monto_serv_insert = monto_serv_pago if not _rows_existentes else 0.0
                    _monto_exp_insert  = monto_expensas if not _rows_existentes else 0.0
                    _monto_ede_insert  = monto_edesal if not _rows_existentes else 0.0
                    _monto_gas_insert  = monto_gas if not _rows_existentes else 0.0
                    _monto_mun_insert  = monto_municipalidad if not _rows_existentes else 0.0
                    _monto_coch_insert = monto_cochera if not _rows_existentes else 0.0
                    _monto_ooss_insert = _val_ooss_insert if not _rows_existentes else 0.0
                    _monto_imp_insert2 = _val_imp_insert if not _rows_existentes else 0.0
                    # Concepto adicional libre: solo se guarda si se completaron los dos campos
                    _extra_incluido = bool(_extra_desc.strip() and _extra_monto > 0)
                    _concepto_extra_desc_insert  = _extra_desc.strip() if (_extra_incluido and not _rows_existentes) else ""
                    _monto_concepto_extra_insert = _extra_monto if (_extra_incluido and not _rows_existentes) else 0.0

                    # Determinar tipo de pago
                    if _es_correccion_insert:
                        _tipo_pago_insert = "Corrección"
                    elif not _rows_existentes:
                        _tipo_pago_insert = "Normal"
                    else:
                        _tipo_pago_insert = "Complemento"

                    cursor.execute('''
                        INSERT INTO pagos_historial (
                            empresa_id, codigo_contrato, propiedad, inquilino,
                            periodo, monto_alquiler,
                            fecha, metodo_pago, comentario,
                            monto_expensas, monto_edesal, monto_gas, monto_municipalidad,
                            monto_cochera, monto_ooss, monto_imp_inmobiliario,
                            monto_honorarios, monto_garantia, monto_gasto_admin,
                            concepto_extra_desc, monto_concepto_extra,
                            monto_abonado, saldo_pendiente, saldos_anteriores,
                            cotizacion_usd, registrado_por, nro_comprobante, tipo_pago
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        st.session_state.get("empresa_id", 0),
                        c_datos['codigo'], c_datos.get('alias_propiedad', ''), f"{c_datos.get('apellidos','')}, {c_datos.get('nombres','')}".strip(", "),
                        mes_periodo_texto, _monto_alq_insert,
                        datetime.now().strftime("%d/%m/%Y %H:%M"), metodo_pago, _comentario_completo,
                        _monto_exp_insert, _monto_ede_insert, _monto_gas_insert, _monto_mun_insert,
                        _monto_coch_insert, _monto_ooss_insert, _monto_imp_insert2,
                        monto_honorarios_pago, monto_garantia_pago, _ret_agencia,
                        _concepto_extra_desc_insert, _monto_concepto_extra_insert,
                        monto_abonado, _saldo_a_guardar, _total_saldos_anteriores,
                        _tc_insert, st.session_state.get("username", ""), _nro_comprobante_insert, _tipo_pago_insert
                    ))

                    # 2a. Saldar períodos anteriores absorbidos por este pago
                    # Si este cobro incluye saldos de períodos previos (_total_saldos_anteriores > 0),
                    # ponemos saldo_pendiente = 0 en el último registro de cada uno de esos períodos.
                    # Así evitamos que se cuenten dos veces en cobros futuros.
                    if _total_saldos_anteriores > 0 and monto_abonado >= _total_saldos_anteriores:
                        for _per_saldar, _monto_saldar in _saldos_anteriores_detalle.items():
                            cursor.execute(
                                """UPDATE pagos_historial
                                   SET saldo_pendiente = 0
                                   WHERE id = (
                                       SELECT id FROM pagos_historial
                                       WHERE codigo_contrato = %s AND periodo = %s
                                       ORDER BY id DESC LIMIT 1
                                   )""",
                                (c_datos['codigo'], _per_saldar)
                            )

                    # 2b. Avanzar el mes vivo SOLO si es el período actual Y es el primer pago
                    cursor.execute("SELECT mes_contrato FROM contratos WHERE codigo = %s", (c_datos['codigo'],))
                    _row_mes = cursor.fetchone()
                    _mes_actual_vivo = int(_row_mes['mes_contrato'] or 1) if _row_mes else 1
                    _periodo_actual_idx = opciones_periodo.index(mes_periodo_texto) if mes_periodo_texto in opciones_periodo else 0
                    _es_periodo_actual = (_periodo_actual_idx >= indice_default - 1)
                    _es_primer_pago = not bool(_rows_existentes)  # no avanzar si es complemento
                    if _es_periodo_actual and _es_primer_pago:
                        nuevo_mes_vivo = _mes_actual_vivo + 1
                        cursor.execute("UPDATE contratos SET mes_contrato = %s WHERE codigo = %s", (nuevo_mes_vivo, c_datos['codigo']))
                        cursor.execute("UPDATE contratos SET alquiler = %s WHERE codigo = %s", (monto_alq_pago, c_datos['codigo']))
                        # Actualizar prox_actualizacion en la BD con el valor calculado
                        if not necesita_renovacion:
                            cursor.execute(
                                "UPDATE contratos SET prox_actualizacion = %s WHERE codigo = %s",
                                (prox_actualizacion_calculada.strftime('%Y-%m-%d'), c_datos['codigo'])
                            )
                    else:
                        nuevo_mes_vivo = _mes_actual_vivo
                        if not _es_periodo_actual:
                            st.info("ℹ️ Cobro de período anterior — contador no modificado.")
                        elif not _es_primer_pago:
                            st.info("ℹ️ Complemento de pago — contador no modificado.")

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
                    st.cache_data.clear()
                    _cached_planilla_cobranzas_mes.clear()
                    st.session_state["_limpiar_planilla_cache"] = True

                    # Guardar mensajes en session_state para mostrarlos después del rerun
                    _msgs_impacto = [("success", f"✔️ Cobro de {mes_periodo_texto} guardado. Abonado: $ {monto_abonado:,.2f} de $ {_total_a_cubrir:,.2f}. ¡Contrato avanzado al Mes {nuevo_mes_vivo}!")]
                    if saldo_pendiente > 0:
                        _msgs_impacto.append(("warning", f"⚠️ Saldo pendiente del inquilino: $ {saldo_pendiente:,.2f}"))
                    elif saldo_pendiente < 0:
                        _msgs_impacto.append(("info", f"✅ El inquilino pagó $ {abs(saldo_pendiente):,.2f} de más (a su favor)."))
                    if monto_honorarios_pago > 0:
                        _msgs_impacto.append(("info", f"🔄 Honorarios: cuota {nuevas_cuotas_hon_pagadas} de {cuotas_hon_pactadas} cobrada. Acumulado: $ {nuevos_honorarios_acumulados:,.2f}"))
                    if monto_garantia_pago > 0:
                        _msgs_impacto.append(("info", f"🛡️ Depósito Garantía: cuota {nuevas_cuotas_dep_pagadas} de {cuotas_dep_pactadas} cobrada. Acumulado: $ {nueva_garantia_acumulada:,.2f}"))
                    st.session_state["_msgs_impacto"] = _msgs_impacto

                    # Activar flag para mostrar el PDF sin recargar la página
                    st.session_state.pago_impactado = True
                    st.session_state.contrato_impactado_id = c_datos['codigo']
                    # Guardar firma del estado al momento de impactar
                    st.session_state.impacto_firma = (
                        mes_periodo_texto,
                        round(monto_alq_pago, 2),
                        round(monto_serv_pago, 2),
                        round(total_pago_real, 2),
                        round(monto_ooss, 2),
                        round(st.session_state.get(f"extra_monto_{c_datos['codigo']}", 0.0), 2),
                        st.session_state.get(f"extra_desc_{c_datos['codigo']}", "").strip(),
                    )
                    st.rerun()

                except Exception as e:
                    st.error(f"Error al procesar el impacto en caja: {e}")
                finally:
                    conn.close()

            # Calcular firma actual para detectar cambios post-impacto
            _firma_actual = (
                mes_periodo_texto,
                round(monto_alq_pago, 2),
                round(monto_serv_pago, 2),
                round(total_pago_real, 2),
                round(monto_ooss, 2),
                round(st.session_state.get(f"extra_monto_{c_datos['codigo']}", 0.0), 2),
                st.session_state.get(f"extra_desc_{c_datos['codigo']}", "").strip(),
            )
            _firma_guardada = st.session_state.get("impacto_firma")
            _estado_modificado = (
                st.session_state.pago_impactado
                and st.session_state.contrato_impactado_id == c_datos['codigo']
                and _firma_guardada is not None
                and _firma_actual != _firma_guardada
            )
            if _estado_modificado:
                st.session_state.pago_impactado = False
                st.session_state.contrato_impactado_id = None

            if st.session_state.pago_impactado and st.session_state.contrato_impactado_id == c_datos['codigo']:
                st.markdown("---")
                st.markdown("### 🚀 Generador Inteligente de Comprobantes (WhatsApp & PDF Profesional)")
            
                txt_alquiler_fmt = f"$ {monto_alq_pago:,.2f}"
                txt_servicios_fmt = f"$ {monto_serv_pago:,.2f}"
                txt_total_fmt = f"$ {total_pago_real:,.2f}"
                # Incluir el concepto extra libre en el detalle de WhatsApp si fue cargado
                _extra_desc_wa  = st.session_state.get(f"extra_desc_{c_datos['codigo']}", "").strip()
                _extra_monto_wa = st.session_state.get(f"extra_monto_{c_datos['codigo']}", 0.0)
                _detalles_wa = list(detalles_recibo_servicios)
                if _extra_monto_wa > 0:
                    _concepto_wa = _extra_desc_wa if _extra_desc_wa else "Concepto adicional"
                    _detalles_wa.append(f" - {_concepto_wa}: $ {_extra_monto_wa:,.2f}")
                servicios_str_whatsapp = "\n".join(_detalles_wa) if _detalles_wa else " - No se registran conceptos adicionales."

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
                    _es_complemento = bool(_rows_existentes)
                    _alq_monto_pdf = monto_alq_pago if not _es_complemento else 0.0
                    _alq_desc_pdf  = _alq_desc_edit if not _es_complemento else "Complemento de pago — Alquiler ya registrado"
                    _total_pdf_editado = _alq_monto_pdf + sum(d['Monto'] for d in _desglose_editado)
                    import time as _time
                    _nro_recibo = st.session_state.get("ultimo_nro_comprobante", f"RC-{c_datos['codigo']:04d}-{int(_time.time()) % 100000}")

                    # Calcular MES/AÑO para el PDF
                    _mes_anio_pdf = ""
                    try:
                        _match_p = re.match(r'Mes\s+(\d+)\s+de\s+\d+', str(mes_periodo_texto))
                        if _match_p and c_datos.get('inicio_contrato'):
                            _n = int(_match_p.group(1))
                            _ini_str = str(c_datos['inicio_contrato']).strip()
                            try: _ini_dt = datetime.strptime(_ini_str, "%Y-%m-%d").date()
                            except Exception: _ini_dt = datetime.strptime(_ini_str, "%d/%m/%Y").date()
                            _fm = _ini_dt + dateutil.relativedelta.relativedelta(months=_n - 1)
                            _meses_pdf = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                                         7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
                            _mes_anio_pdf = f"{_meses_pdf[_fm.month]} {_fm.year}"
                    except Exception:
                        pass

                    _prox_act_pdf = ""
                    _aviso_prox_act = False
                    try:
                        if not necesita_renovacion:
                            _prox_act_pdf = prox_actualizacion_calculada.strftime("%d/%m/%Y")
                            # Determinar la fecha del próximo período del recibo
                            _match_per = re.match(r'Mes\s+(\d+)\s+de\s+\d+', str(mes_periodo_texto))
                            if _match_per and c_datos.get('inicio_contrato'):
                                _n_per = int(_match_per.group(1))
                                _ini_str2 = str(c_datos['inicio_contrato']).strip()
                                try: _ini_dt2 = datetime.strptime(_ini_str2, "%Y-%m-%d").date()
                                except Exception: _ini_dt2 = datetime.strptime(_ini_str2, "%d/%m/%Y").date()
                                # Fecha del próximo período (mes N+1 del contrato)
                                _fecha_prox_periodo = _ini_dt2 + dateutil.relativedelta.relativedelta(months=_n_per)
                                # La actualización cae en el próximo período si es el mismo mes/año
                                _aviso_prox_act = (
                                    prox_actualizacion_calculada.year  == _fecha_prox_periodo.year and
                                    prox_actualizacion_calculada.month == _fecha_prox_periodo.month
                                )
                    except Exception:
                        pass
                    _pdf_bytes = generar_pdf_recibo(
                        comprobante_nro=_nro_recibo,
                        fecha_emision=datetime.now().strftime('%d/%m/%Y'),
                        periodo=mes_periodo_texto,
                        locatario=f"{c_datos['apellidos']}, {c_datos['nombres']}",
                        propiedad=c_datos['propiedad_dir'],
                        alquiler_desc=_alq_desc_pdf,
                        alquiler_monto=_alq_monto_pdf,
                        filas_servicios=_desglose_editado,
                        total=_total_pdf_editado,
                        metodo_pago=metodo_pago,
                        nombre_empresa=st.session_state.get('nombre_empresa', 'Mi Empresa'),
                        monto_abonado=monto_abonado,
                        saldo_pendiente=saldo_pendiente,
                        mes_anio=_mes_anio_pdf,
                        prox_actualizacion=_prox_act_pdf,
                        aviso_actualizacion_proximo=_aviso_prox_act,
                    )
                    _btn_col1, _btn_col2 = st.columns([1, 1])
                    _btn_col1.download_button(
                        label="📄 Descargar Comprobante PDF",
                        data=_pdf_bytes,
                        file_name=f"{c_datos['apellidos']}_{c_datos['codigo']}_{mes_periodo_texto.lower().replace(' ','_')}.pdf",
                        mime="application/pdf",
                        help="Descarga el comprobante como PDF listo para archivar o enviar.",
                        use_container_width=True,
                    )

                    # Botón WhatsApp — solo si está habilitado para empresa y usuario
                    _wa_ok = (
                        st.session_state.get("cfg_whatsapp_habilitado", False) and
                        st.session_state.get("usr_whatsapp_habilitado", False)
                    )
                    if _wa_ok:
                        _tel_inq = str(c_datos.get("telefono", "") or "").strip().replace(" ", "").replace("-", "")
                        if _tel_inq:
                            if _btn_col2.button("📲 Enviar por WhatsApp", key=f"btn_wa_recibo_{c_datos['codigo']}", use_container_width=True):
                                _wa_creds = _get_wa_credenciales(st.session_state.get("empresa_id", 0))
                                if _wa_creds:
                                    _dir_prop = c_datos.get("propiedad_dir", "")
                                    _nombre_inq = f"{c_datos.get('nombres', '')} {c_datos.get('apellidos', '')}".strip()
                                    _ok_wa = _enviar_mensaje_whatsapp(
                                        phone_id=_wa_creds["phone_id"],
                                        token=_wa_creds["token"],
                                        numero_destino=_tel_inq,
                                        template_name="comprobante_pago_alquiler",
                                        variables=[
                                            _nombre_inq,
                                            mes_periodo_texto,
                                            _dir_prop,
                                            f"{monto_abonado:,.0f}",
                                            datetime.now().strftime("%d/%m/%Y"),
                                            metodo_pago,
                                        ]
                                        # documento_bytes=_pdf_bytes — habilitar cuando comprobante_pago_con_pdf esté aprobada
                                    )
                                    if _ok_wa:
                                        st.success("✅ Comprobante enviado por WhatsApp.")
                                    else:
                                        st.error("❌ No se pudo enviar el comprobante. Verificá los logs.")
                                else:
                                    st.error("❌ No se encontraron credenciales de WhatsApp configuradas.")
                        else:
                            _btn_col2.warning("⚠️ El inquilino no tiene teléfono registrado.")


# =====================================================================
# PESTAÑA 4: MÓDULO DE HISTORIAL DE PAGOS COMPLETO (MEJORA 1 VISUALIZACIÓN)
# =====================================================================
if tab_historial_pagos:
    with tab_historial_pagos:

        _pf_hist = st.session_state.get("propietario_filtro", "")
        _pf_hist_activo = rol_actual == "propietario" and bool(_pf_hist)
        _eid_hist = st.session_state.get("empresa_id", 0)

        df_historial = _cached_historial_pagos(_eid_hist, _pf_hist if _pf_hist_activo else "")

        # Convertir columnas NUMERIC (Decimal) a float
        if not df_historial.empty:
            for _col in df_historial.columns:
                if _col not in ['ID PAGO', 'COD CONTRATO', 'PROPIEDAD', 'DIR PROPIEDAD', 'DOMICILIO', 'ALIAS / UBICACIÓN',
                                 'INQUILINO', '_apellidos', '_nombres', '_telefono', 'NRO COMPROBANTE',
                                 'PERIODO', 'FECHA IMPACTO', 'METODO', '_comentarios',
                                 '_inicio_contrato']:
                    try:
                        df_historial[_col] = pd.to_numeric(df_historial[_col], errors='coerce').fillna(0.0)
                    except Exception:
                        pass

        if df_historial.empty:
            st.info("Aún no se registran cobros mensuales asentados de manera definitiva en el libro de caja.")
        else:
            st.caption("💡 Los valores en USD se calculan con la cotización registrada al momento de cada cobro.")

            # ── Calcular columna MES/AÑO a partir del periodo y fecha de inicio ──
            _meses_es = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
                5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
                9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
            }

            def _calcular_mes_anio(row):
                try:
                    _match = re.match(r'Mes\s+(\d+)\s+de\s+\d+', str(row['PERIODO']))
                    if not _match:
                        return ""
                    _num_mes_contrato = int(_match.group(1))
                    _inicio_str = str(row['_inicio_contrato'] or "").strip()
                    if not _inicio_str or _inicio_str == "None":
                        return ""
                    try:
                        _inicio_dt = datetime.strptime(_inicio_str, "%Y-%m-%d").date()
                    except ValueError:
                        try:
                            _inicio_dt = datetime.strptime(_inicio_str, "%d/%m/%Y").date()
                        except ValueError:
                            return ""
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
                "_concepto_extra":      "CONCEPTO EXTRA ($)",
                "_concepto_extra_desc": "DESCRIPCIÓN EXTRA",
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
                "CONCEPTO EXTRA ($)", "DESCRIPCIÓN EXTRA",
                "SERVICIOS ($)", "TOTAL ($)",
                "ABONADO ($)", "RETENCIÓN AGENCIA ($)", "RETENCIÓN AGENCIA (USD)",
                "SALDO PEND. ($)",
                "COTIZACIÓN USD", "FECHA IMPACTO", "METODO"
            ]

            # ── Sección de Reportes ───────────────────────────────────────
            st.markdown("---")
            st.markdown("##### 📋 Generar Reporte de Cobros")

            with st.expander("⚙️ Configurar y descargar reporte", expanded=False):
                _rc1, _rc2, _rc3 = st.columns(3)

                # Filtro por fechas
                _fecha_min = datetime.strptime("01/01/2020", "%d/%m/%Y").date()
                _fecha_max = datetime.now().date()
                _rep_desde = _rc1.date_input("Desde:", value=_fecha_min, key="rep_fecha_desde")
                _rep_hasta = _rc2.date_input("Hasta:", value=_fecha_max, key="rep_fecha_hasta")

                # Filtro por usuario (registrado_por)
                _usuarios_rep = ["Toda la empresa"]
                try:
                    with _pg_conn() as _conn_ru:
                        with _conn_ru.cursor() as _cur_ru:
                            _cur_ru.execute(
                                "SELECT DISTINCT registrado_por FROM pagos_historial WHERE empresa_id = %s AND registrado_por IS NOT NULL AND registrado_por <> '' ORDER BY registrado_por",
                                (_eid_hist,)
                            )
                            _usuarios_rep += [r["registrado_por"] for r in _cur_ru.fetchall()]
                except Exception:
                    pass  # columna aún no creada — solo se mostrará "Toda la empresa"

                _rep_usuario = _rc3.selectbox("Filtrar por usuario:", _usuarios_rep, key="rep_usuario_sel")

                # Aplicar filtros sobre df_historial ya cargado
                df_rep = df_historial.copy()

                # Filtro fecha — parsear FECHA IMPACTO (formato dd/mm/yyyy HH:MM o similar)
                def _parse_fecha_rep(s):
                    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                        try:
                            return datetime.strptime(str(s).strip()[:19], fmt).date()
                        except ValueError:
                            continue
                    return None

                df_rep["_fecha_dt"] = df_rep["FECHA IMPACTO"].apply(_parse_fecha_rep)
                df_rep = df_rep[
                    df_rep["_fecha_dt"].apply(lambda d: d is not None and _rep_desde <= d <= _rep_hasta)
                ]

                # Filtro usuario
                if _rep_usuario != "Toda la empresa" and "registrado_por" in df_rep.columns:
                    df_rep = df_rep[df_rep["registrado_por"] == _rep_usuario]

                # Columnas del reporte según spec
                _cols_reporte = [
                    "FECHA IMPACTO", "PERIODO", "MES/AÑO", "ALIAS / UBICACIÓN", "INQUILINO",
                    "ALQUILER ($)", "EXPENSAS ($)", "COCHERA ($)",
                ]
                # Suma de servicios — mismo criterio que en Rendición a Propietarios:
                # Imp. Inmobiliario + EDESAL + Gas + Municipalidad + OO.SS.
                # (Honorarios y Garantía quedan fuera; no son "servicios" de la propiedad)
                _servicios_cols = ["IMP. INMOBILIARIO ($)", "LUZ EDESAL ($)", "GAS ($)", "MUNICIPALIDAD ($)", "OO.SS ($)"]
                _cols_existentes_serv = [c for c in _servicios_cols if c in df_rep.columns]
                df_rep["SERVICIOS ($)"] = df_rep[_cols_existentes_serv].sum(axis=1).round(2)
                _cols_reporte += ["SERVICIOS ($)", "TOTAL ($)", "ABONADO ($)"]
                _cols_reporte = [c for c in _cols_reporte if c in df_rep.columns]

                df_rep_vista = df_rep[_cols_reporte].copy()

                st.caption(f"**{len(df_rep_vista)} registros** en el período seleccionado.")

                # Totales
                _tr1, _tr2, _tr3, _tr4 = st.columns(4)
                _tr1.metric("Total Alquiler", f"$ {df_rep_vista['ALQUILER ($)'].sum():,.2f}")
                _tr2.metric("Total Servicios", f"$ {df_rep_vista['SERVICIOS ($)'].sum():,.2f}")
                _tr3.metric("Total Cobrado", f"$ {df_rep_vista['TOTAL ($)'].sum():,.2f}")
                _tr4.metric("Total Abonado", f"$ {df_rep_vista['ABONADO ($)'].sum():,.2f}")

                st.dataframe(df_rep_vista, use_container_width=True, hide_index=True)

                # ── Descarga Excel (CSV compatible con Excel) ────────────
                import io as _io
                _buf_csv = _io.StringIO()
                df_rep_vista.to_csv(_buf_csv, index=False, sep=";", decimal=",")
                # Agregar hoja de totales al final
                _buf_csv.write("\n;TOTALES\n")
                for _concepto, _col in [
                    ("Total Alquiler",  "ALQUILER ($)"),
                    ("Total Expensas",  "EXPENSAS ($)"),
                    ("Total Cochera",   "COCHERA ($)"),
                    ("Total Servicios", "SERVICIOS ($)"),
                    ("Total Cobrado",   "TOTAL ($)"),
                    ("Total Abonado",   "ABONADO ($)"),
                ]:
                    _v = df_rep_vista[_col].sum() if _col in df_rep_vista.columns else 0
                    _buf_csv.write(f"{_concepto};{_v:,.2f}\n")
                st.download_button(
                    "⬇️ Descargar Excel (CSV)",
                    _buf_csv.getvalue().encode("utf-8-sig"),  # utf-8-sig para que Excel lo abra bien
                    file_name=f"reporte_cobros_{_rep_desde}_{_rep_hasta}.csv",
                    mime="text/csv",
                )

                # ── Descarga PDF real con ReportLab ─────────────────────
                try:
                    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                    from reportlab.lib.pagesizes import A4, landscape
                    from reportlab.lib import colors
                    from reportlab.lib.units import mm
                    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
                    import io as _io_pdf

                    _buf_pdf = _io_pdf.BytesIO()
                    _doc_rep = SimpleDocTemplate(
                        _buf_pdf,
                        pagesize=landscape(A4),
                        leftMargin=15*mm, rightMargin=15*mm,
                        topMargin=15*mm, bottomMargin=15*mm,
                        title=f"Reporte de Cobros {_rep_desde} - {_rep_hasta}"
                    )
                    _styles = getSampleStyleSheet()
                    _story = []

                    # Título
                    _st_titulo = ParagraphStyle("titulo_rep", parent=_styles["Heading1"], fontSize=14, textColor=colors.HexColor("#1a365d"), spaceAfter=4)
                    _st_sub    = ParagraphStyle("sub_rep",    parent=_styles["Normal"],   fontSize=9,  textColor=colors.HexColor("#555555"), spaceAfter=10)
                    _story.append(Paragraph(f"Reporte de Cobros — {_rep_desde.strftime('%d/%m/%Y')} al {_rep_hasta.strftime('%d/%m/%Y')}", _st_titulo))
                    _story.append(Paragraph(f"Usuario: {_rep_usuario}  |  Empresa: {st.session_state.get('nombre_empresa', '')}  |  {len(df_rep_vista)} registros", _st_sub))
                    _story.append(Spacer(1, 4*mm))

                    # Tabla de datos
                    _headers_pdf = ["Fecha", "Período", "Mes/Año", "Alias / Ubicación", "Inquilino", "Alquiler", "Expensas", "Cochera", "Servicios", "Total ($)", "Abonado ($)"]
                    _col_keys    = ["FECHA IMPACTO", "PERIODO", "MES/AÑO", "ALIAS / UBICACIÓN", "INQUILINO", "ALQUILER ($)", "EXPENSAS ($)", "COCHERA ($)", "SERVICIOS ($)", "TOTAL ($)", "ABONADO ($)"]
                    _money_cols  = {"ALQUILER ($)", "EXPENSAS ($)", "COCHERA ($)", "SERVICIOS ($)", "TOTAL ($)", "ABONADO ($)"}

                    _col_widths = [22*mm, 26*mm, 20*mm, 50*mm, 38*mm, 20*mm, 18*mm, 18*mm, 18*mm, 20*mm, 20*mm]

                    _st_cell  = ParagraphStyle("cell",  parent=_styles["Normal"], fontSize=7, leading=9)
                    _st_money = ParagraphStyle("money", parent=_styles["Normal"], fontSize=7, leading=9, alignment=TA_RIGHT)
                    _st_hdr   = ParagraphStyle("hdr",   parent=_styles["Normal"], fontSize=7, leading=9, textColor=colors.white, alignment=TA_CENTER)

                    _data_pdf = [[Paragraph(h, _st_hdr) for h in _headers_pdf]]
                    for _, _rr in df_rep_vista.iterrows():
                        _fila = []
                        for _ck in _col_keys:
                            _val = _rr.get(_ck, "")
                            if _ck in _money_cols:
                                try: _txt = f"$ {float(_val):,.2f}"
                                except Exception: _txt = str(_val)
                                _fila.append(Paragraph(_txt, _st_money))
                            else:
                                _fila.append(Paragraph(str(_val or ""), _st_cell))
                        _data_pdf.append(_fila)

                    # Fila de totales
                    _tot_fila = [Paragraph("", _st_cell)] * 5
                    for _ck in ["ALQUILER ($)", "EXPENSAS ($)", "COCHERA ($)", "SERVICIOS ($)", "TOTAL ($)", "ABONADO ($)"]:
                        try: _tv = f"$ {df_rep_vista[_ck].sum():,.2f}"
                        except Exception: _tv = ""
                        _tot_fila.append(Paragraph(_tv, _st_money))
                    _data_pdf.append(_tot_fila)

                    _tbl_rep = Table(_data_pdf, colWidths=_col_widths, repeatRows=1)
                    _tbl_rep.setStyle(TableStyle([
                        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#1a365d")),
                        ("ROWBACKGROUNDS",(0, 1), (-1, -2), [colors.white, colors.HexColor("#f0f4f8")]),
                        ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#dce6f4")),
                        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
                        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#c0c0c0")),
                        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING",    (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]))
                    _story.append(_tbl_rep)
                    _story.append(Spacer(1, 6*mm))

                    # Pie de página
                    _story.append(Paragraph(
                        f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} — {st.session_state.get('nombre_empresa', '')}",
                        ParagraphStyle("footer_rep", parent=_styles["Normal"], fontSize=7, textColor=colors.grey)
                    ))

                    _doc_rep.build(_story)
                    _buf_pdf.seek(0)
                    st.download_button(
                        "🖨️ Descargar PDF",
                        _buf_pdf,
                        file_name=f"reporte_cobros_{_rep_desde}_{_rep_hasta}.pdf",
                        mime="application/pdf",
                    )
                except Exception as _e_pdf:
                    st.error(f"Error al generar PDF: {_e_pdf}")

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
                                    <strong>Comprobante N°:</strong> {_r.get('NRO COMPROBANTE') or f"RC-00{_r['COD CONTRATO']}-{str(_r['PERIODO']).replace(' ','')}"}<br>
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

            # ── Tabla completa y Resumen al final ────────────────────────
            st.markdown("---")
            st.subheader("🗄️ Registro Completo de Caja y Balance Mensual")
            st.dataframe(df_historial[_cols_vista], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("##### 📊 Resumen Estadístico de Caja Registrada")
            c_r1, c_r2, c_r3, c_r4, c_r5 = st.columns(5)
            c_r1.metric("Total Cobrado",     f"$ {df_historial['TOTAL ($)'].sum():,.2f}")
            c_r2.metric("Alquiler",          f"$ {df_historial['ALQUILER ($)'].sum():,.2f}")
            c_r3.metric("Cochera",           f"$ {df_historial['COCHERA ($)'].sum():,.2f}")
            c_r4.metric("Servicios",         f"$ {df_historial['SERVICIOS ($)'].sum():,.2f}")
            c_r5.metric("Saldo Pendiente",   f"$ {df_historial['SALDO PEND. ($)'].sum():,.2f}")
    
    
    
# =====================================================================
# PESTAÑA 5: FORMULARIO REACTIVO DE CARGA DE CONTRATOS (CORREGIDA)
# =====================================================================
    
if tab_carga:
    with tab_carga:
        st.subheader("Formulario de Registro Técnico del Contrato")
    
        dict_propiedades, dict_inquilinos = obtener_datos_desplegables(st.session_state.get("empresa_id", 0))
            
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
                st.session_state["_propiedad_cambio"] = True
                u = cargar_datos_iniciales_contrato(propiedad_id)
                st.session_state.datos_contrato = u
    
                # ══════════════════════════════════════════════════════════════
                # CRÍTICO: escribir los valores de la BD en el session_state de
                # cada widget. Streamlit ignora value= en rerenders si la key
                # ya existe — hay que sobrescribirla directamente.
                # ══════════════════════════════════════════════════════════════
                opciones_actualizacion_tmp = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24, "Sin actualización": 0}
                indices_disponibles_tmp = ["ICL", "IPC", "UVA", "Otro"]
    
                if u:
                    # Inquilino — buscar por dni_inquilino
                    # (se maneja en PASO 2 más abajo)

                    if u.get("estado") in estados_disponibles:
                        st.session_state["estado_sel_main"] = u["estado"]

                    # Sección 2 — Fechas
                    try:
                        from datetime import date as date_type
                        def parse_fecha(val):
                            if not val or str(val).strip() in ('', 'None', 'nan'): return None
                            s = str(val).strip()
                            # Formato ISO: YYYY-MM-DD
                            try: return date_type.fromisoformat(s)
                            except Exception: pass
                            # Formato argentino: DD/MM/YYYY
                            try:
                                from datetime import datetime as dt_
                                return dt_.strptime(s, "%d/%m/%Y").date()
                            except Exception: pass
                            return None
                        hoy = datetime.now().replace(day=1).date()
                        _fi = parse_fecha(u.get("inicio_contrato"))
                        _ff = parse_fecha(u.get("fin_contrato"))
                        st.session_state["inicio_contrato_main"] = _fi if _fi else hoy
                        st.session_state["fin_contrato_main"]    = _ff if _ff else (hoy + dateutil.relativedelta.relativedelta(years=2))
                    except Exception as _fe:
                        logging.error(f"parse_fecha error: {_fe}")

                    act_val_raw = str(u.get("act_contrato", "")).strip()
                    meses_a_texto = {str(v): k for k, v in opciones_actualizacion_tmp.items()}
                    if act_val_raw in opciones_actualizacion_tmp:
                        act_val = act_val_raw
                    elif act_val_raw in meses_a_texto:
                        act_val = meses_a_texto[act_val_raw]
                    else:
                        act_val = "Semestral"
                    st.session_state["act_contrato_main"] = act_val

                    # Sección 3 — Valores económicos
                    _alq = float(u["alquiler"]) if u.get("alquiler") is not None else 80000.0
                    st.session_state["monto_inicial_main"]        = float(u["monto_inicial"]) if u.get("monto_inicial") is not None else 80000.0
                    st.session_state["alquiler_ultimo_main"]      = _alq
                    ind_val = u.get("indice", "ICL")
                    st.session_state["indice_sel_main"]           = ind_val if ind_val in indices_disponibles_tmp else "ICL"
                    mes_act = opciones_actualizacion_tmp.get(act_val, 6)
                    st.session_state["meses_atras_main"]          = int(u["mes_actualizacion_contrato"]) if u.get("mes_actualizacion_contrato") is not None else mes_act
                    st.session_state["alquiler_actualizado_main"] = f"{_alq:,.2f}".replace(",","v").replace(".",",").replace("v",".")

                    # Sección 4 — Honorarios
                    _hon_pct = float(u["honorarios"]) if u.get("honorarios") is not None else 5.0
                    _hon_total = float(u["monto_honorarios"]) if u.get("monto_honorarios") not in (None, 0, 0.0) else 0.0
                    _cuota_hon = max(1, int(u["cuota_honorarios"])) if u.get("cuota_honorarios") not in (None, 0) else 1
                    st.session_state["honorarios_pct_live"]       = _hon_pct
                    st.session_state["hon_inq_total_live"]        = _hon_total
                    st.session_state["cuota_hon_live"]            = _cuota_hon
                    st.session_state["cuotas_hon_pagas_live"]     = _safe_int(u.get("cuotas_honorarios_pagadas"), 0)

                    # Sección 5 — Garantías
                    _tipos_garantia_nuevos = ["Sin Garantía", "Depósito", "Solo Pagaré", "Pagaré y Depósito", "Propietario", "Recibo de Sueldo", "Bien Inmueble", "Aval Bancario", "Otro"]
                    val_tipo_tmp = u.get("tipo_de_garantie", "Sin Garantía")
                    st.session_state["tipo_garantia_live_sec5"]   = val_tipo_tmp if val_tipo_tmp in _tipos_garantia_nuevos else "Sin Garantía"
                    _dep_total = float(u["monto_garantia"]) if u.get("monto_garantia") not in (None, 0, 0.0) else float(u.get("monto_inicial") or 80000.0)
                    st.session_state["deposito_total_live_sec5"]  = _dep_total
                    st.session_state["cuotas_dep_live_sec5"]      = max(1, _safe_int(u.get("cuotas_deposito"), 1))
                    st.session_state["cuotas_dep_pagas_live"]     = _safe_int(u.get("cuotas_deposito_pagadas"), 0)
                    # Pagaré — recuperar monto del campo garantia
                    _gar_raw_ss = str(u.get('garantia', ''))
                    try:
                        import re as _re2
                        _mp = _re2.search(r'PAG:Si:(\d+)', _gar_raw_ss)
                        st.session_state["monto_pagare_live_sec5"] = float(_mp.group(1)) if _mp else 0.0
                    except Exception:
                        st.session_state["monto_pagare_live_sec5"] = 0.0

                    # Sección 6 — Servicios
                    st.session_state["edesal_live"]               = _safe_float(u.get("edesal"))
                    st.session_state["gas_live"]                  = _safe_float(u.get("gas"))
                    st.session_state["municipalidad_live"]        = _safe_float(u.get("municipalidad"))
                    st.session_state["ooss_live"]                 = _safe_float(u.get("ooss"))
                    st.session_state["expensas_live"]             = _safe_float(u.get("expensas"))
                    st.session_state["cochera_live"]              = _safe_float(u.get("cochera"))
                    st.session_state["imp_inmob_live"]            = _safe_float(u.get("imp_inmobiliario"))
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
    
    
            # 🔧 PASO 2: PRESELECCIONAR INQUILINO SOLO AL CAMBIAR DE PROPIEDAD
            # _propiedad_cambio se setea True en el bloque de detección de cambio de propiedad
            _propiedad_cambio = st.session_state.get("_propiedad_cambio", False)
            if _propiedad_cambio:
                st.session_state["_propiedad_cambio"] = False
                if u and u.get('dni_inquilino'):
                    _dni_buscar = str(u['dni_inquilino']).strip()
                    _eid_busq = st.session_state.get("empresa_id", 0)
                    try:
                        with _pg_conn() as _conn_bi:
                            with _conn_bi.cursor() as _cur_bi:
                                _cur_bi.execute(
                                    "SELECT id, apellidos, nombres FROM inquilinos WHERE dni = %s AND empresa_id = %s",
                                    (_dni_buscar, _eid_busq)
                                )
                                _inq_row = _cur_bi.fetchone()
                        if _inq_row:
                            _inq_nombre_buscar = f"Cod: {_inq_row['id']} | {_inq_row['apellidos']}, {_inq_row['nombres']}"
                            st.session_state["inq_sel_main"] = _inq_nombre_buscar
                    except Exception:
                        pass
                elif u and u.get('inquilino_id'):
                    idx_inq = buscar_inquilino_por_id(u['inquilino_id'], lista_inquilinos, dict_inquilinos)
                    if idx_inq < len(lista_inquilinos):
                        st.session_state["inq_sel_main"] = lista_inquilinos[idx_inq]
    
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

            # Inicializar session_state con defaults si no existen aún
            if "inicio_contrato_main" not in st.session_state:
                st.session_state["inicio_contrato_main"] = fecha_primer_dia_actual
            if "fin_contrato_main" not in st.session_state:
                st.session_state["fin_contrato_main"] = fecha_primer_dia_vencimiento

            st.markdown("### 2. Fechas, Plazos y Duración (Cálculos Dinámicos)")
            cf1, cf2 = st.columns(2)
            inicio_contrato = cf1.date_input(
                "Inicio del Contrato:",
                format="DD/MM/YYYY",
                disabled=not permitir_edicion,
                key="inicio_contrato_main"
            )
            fin_contrato = cf2.date_input(
                "Fin del Contrato:",
                format="DD/MM/YYYY",
                disabled=not permitir_edicion,
                key="fin_contrato_main"
            )
    
            cf3, cf4, cf5 = st.columns([2, 1, 1])
            opciones_actualizacion = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24}
                
            _opciones_act_map = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24, "Sin actualización": 0}
            opciones_actualizacion["Sin actualización"] = 0
            act_contrato_seleccionado = cf3.selectbox(
                "Actualización Contrato (Frecuencia):", 
                list(opciones_actualizacion.keys()), 
                disabled=not permitir_edicion,
                key="act_contrato_main"
            )
            meses_a_sumar = opciones_actualizacion[act_contrato_seleccionado]
    
            fecha_hoy = datetime.now().date()
            if meses_a_sumar == 0:
                prox_actualizacion_calculada = fin_contrato + dateutil.relativedelta.relativedelta(days=1)
            else:
                prox_actualizacion_calculada = inicio_contrato + dateutil.relativedelta.relativedelta(months=meses_a_sumar)
                while prox_actualizacion_calculada < fecha_hoy:
                    prox_actualizacion_calculada += dateutil.relativedelta.relativedelta(months=meses_a_sumar)
    
            necesita_renovacion = False if meses_a_sumar == 0 else prox_actualizacion_calculada > fin_contrato
    
            diferencia_hoy = dateutil.relativedelta.relativedelta(fecha_hoy, inicio_contrato)
            total_meses_transcurridos = (diferencia_hoy.years * 12) + diferencia_hoy.months
            if total_meses_transcurridos < 0: 
                total_meses_transcurridos = 0
            mes_actual_contrato_vivo = total_meses_transcurridos + 1
    
            es_mes_de_actualizacion = False if meses_a_sumar == 0 else ((mes_actual_contrato_vivo - 1) % meses_a_sumar) == 0
    
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
            val_monto_ini = float(u['monto_inicial']) if u and u.get('monto_inicial') is not None else 0.0
            val_alq_ult = float(u['alquiler']) if u and u.get('alquiler') not in (None, 0, 0.0) else 0.0
                
            monto_inicial = cv1.number_input(
                "Monto Inicial ($):", 
                min_value=0.0, 
                step=5000.0, 
                value=st.session_state.get("monto_inicial_main", val_monto_ini), 
                disabled=not permitir_edicion, 
                key="monto_inicial_main"
            )
            alquiler = cv2.number_input(
                "Último Valor Cobrado ($):", 
                min_value=0.0, 
                step=5000.0, 
                value=st.session_state.get("alquiler_ultimo_main", val_alq_ult), 
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
            # Sincronizar automáticamente el intervalo con la frecuencia seleccionada
            if meses_a_sumar > 0:
                st.session_state["meses_atras_main"] = meses_a_sumar
            meses_atras = cv_meses.number_input(
                "Intervalo de Meses para Ajustar:", 
                min_value=1, 
                max_value=24, 
                value=meses_a_sumar if meses_a_sumar > 0 else 1,
                disabled=True,
                key="meses_atras_main",
                help="Se sincroniza automáticamente con la frecuencia seleccionada."
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
            _hoy_carga = datetime.now().date()
            _mismo_mes_inicio = (
                inicio_contrato.year == _hoy_carga.year and
                inicio_contrato.month == _hoy_carga.month
            )
            logging.info(f"[carga_contrato] inicio={inicio_contrato}, hoy={_hoy_carga}, mismo_mes={_mismo_mes_inicio}, monto_ini={monto_inicial}")

            if permitir_edicion and indice_upper in ("ICL", "IPC") and not _mismo_mes_inicio:
                with st.spinner(f"⏳ Consultando {indice_upper}..."):
                    if indice_upper == "ICL":
                        valor_auto = calcular_valor_actualizado_icl(
                            monto_inicial, inicio_contrato, int(meses_atras)
                        )
                    elif indice_upper == "IPC":
                        valor_auto = calcular_valor_actualizado_ipc(
                            monto_inicial, inicio_contrato, int(meses_atras)
                        )
    
            if valor_auto is not None and not _mismo_mes_inicio:
                valor_auto_fmt = f"$ {valor_auto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                c_web2.metric(
                    label=f"📡 Auto {indice_upper} (oficial)",
                    value=valor_auto_fmt,
                    help=f"Calculado automáticamente usando datos oficiales del {'BCRA' if indice_upper == 'ICL' else 'INDEC'}."
                )
                valor_por_defecto_fmt = f"{valor_auto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                # Si el mes de inicio es el mes actual, usar monto_inicial como default
                if _mismo_mes_inicio and monto_inicial > 0:
                    _def_base = monto_inicial
                    # Forzar session_state para pisar cualquier valor previo calculado
                    _fmt_ini = f"{monto_inicial:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    st.session_state["alquiler_actualizado_main"] = _fmt_ini
                    _def_base = monto_inicial
                elif alquiler and alquiler > 0:
                    _def_base = alquiler
                else:
                    _def_base = 0.0
                if permitir_edicion and indice_upper in ("ICL", "IPC") and not _mismo_mes_inicio:
                    fuente_c = "BCRA" if indice_upper == "ICL" else "INDEC"
                    c_web2.warning(
                        f"⚠️ No se pudo obtener el índice desde {fuente_c}. "
                        "Ingresá el valor manualmente o verificá en arquiler.com (↖)."
                    )
                    if c_web2.button("🔄 Reintentar", key="retry_indice_carga"):
                        _obtener_icl_bcra_xls.clear()
                        _obtener_ipc_indec.clear()
                        st.rerun()
                _def_val_act = _def_base
                valor_por_defecto_fmt = f"{_def_val_act:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
            alquiler_actualizado_texto = c_web3.text_input(
                "Valor Actualizado ($):",
                value=st.session_state.get("alquiler_actualizado_main", valor_por_defecto_fmt),
                key="alquiler_actualizado_main",
                disabled=not permitir_edicion,
                help="Auto-completado con el índice oficial. Podés ajustarlo manualmente."
            )
    
            alquiler_actualizado = limpiar_string_a_float(alquiler_actualizado_texto)
                
            valor_vacio = (alquiler_actualizado is None or alquiler_actualizado <= 0.0) and es_mes_de_actualizacion
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
                honorarios_pct = ch_prop1.number_input("Porcentaje de Administración (%):", min_value=0.0, value=st.session_state.get("honorarios_pct_live", val_hon_pct), step=0.5, disabled=not permitir_edicion, key="honorarios_pct_live")
                    
                retencion_mensual_estimated = alquiler_actualizado * (honorarios_pct / 100.0) if not valor_vacio else 0.0
                ret_mensual_fmt = f"$ {retencion_mensual_estimated:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                ch_prop2.metric("Retención mensual ($):", value=ret_mensual_fmt)
                
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
                    
                val_cuotas_hon = max(1, _safe_int(u.get('cuota_honorarios'), 1)) if u else 1
                cuota_honorarios = ch_inq2.number_input(
                    "Cuotas pactadas para el pago:", 
                    min_value=1, 
                    value=max(1, val_cuotas_hon),
                    step=1, 
                    disabled=not permitir_edicion, 
                    key="cuota_hon_live"
                )
    
                valor_por_cuota = honorarios_inquilino_total / cuota_honorarios if cuota_honorarios > 0 else 0.0
                valor_por_cuota_fmt = f"$ {valor_por_cuota:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                ch_inq3.metric("Valor por cuota ($):", value=valor_por_cuota_fmt)
    
                # Monto pagado calculado: cuotas_pagadas × valor_por_cuota
                # (se actualiza después de definir cuotas_honorarios_pagadas)
                honorarios_pagados = 0.0  # placeholder, se recalcula abajo
    
                val_cuotas_hon_pagas = _safe_int(u.get('cuotas_honorarios_pagadas'), 0) if u else 0
                cuotas_honorarios_pagadas = st.number_input(
                    "Cuotas de honorarios pagadas:",
                    min_value=0,
                    max_value=int(cuota_honorarios),
                    value=min(val_cuotas_hon_pagas, int(cuota_honorarios)),
                    step=1,
                    disabled=not permitir_edicion,
                    key="cuotas_hon_pagas_live"
                )

                # Monto pagado calculado
                monto_ya_pagado_hon = cuotas_honorarios_pagadas * valor_por_cuota
                honorarios_pagados = monto_ya_pagado_hon
                monto_pagado_hon_fmt = f"$ {monto_ya_pagado_hon:,.2f}".replace(",","v").replace(".",",").replace("v",".")
                st.metric("Monto abonado a la fecha ($):", value=monto_pagado_hon_fmt)
                saldo_inquilino_hon = max(0.0, honorarios_inquilino_total - monto_ya_pagado_hon)
                cuotas_pendientes_hon = max(0, int(cuota_honorarios) - cuotas_honorarios_pagadas)
                if saldo_inquilino_hon > 0:
                    saldo_hon_fmt = f"$ {saldo_inquilino_hon:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                    st.warning(f"💵 Saldo pendiente: **{saldo_hon_fmt}** — {cuotas_pendientes_hon} cuota(s) de {valor_por_cuota_fmt} c/u.")
                else:
                    st.success("✅ Honorarios completamente abonados.")
    
            # --- 5. RESPALDO Y GARANTÍAS DEL CONTRATO ---
            st.markdown("### 5. Respaldo y Garantías del Contrato")

            # Tipo de garantía — controla qué secciones se muestran
            tipos_garantia = [
                "Sin Garantía",
                "Depósito",
                "Solo Pagaré",
                "Pagaré y Depósito",
                "Propietario",
                "Recibo de Sueldo",
                "Bien Inmueble",
                "Aval Bancario",
                "Otro"
            ]
            val_tipo_garantia = u.get("tipo_de_garantie", "Sin Garantía") if u else "Sin Garantía"
            if val_tipo_garantia not in tipos_garantia:
                val_tipo_garantia = "Sin Garantía"
            idx_tipo_gar = tipos_garantia.index(val_tipo_garantia)
            tipo_de_garantie = st.selectbox(
                "Tipo de Garantía:", tipos_garantia,
                index=idx_tipo_gar, disabled=not permitir_edicion,
                key="tipo_garantia_live_sec5"
            )

            _gar_raw = str(u.get('garantia', '')) if u else ''
            _tiene_pagare_tipos = tipo_de_garantie in ("Solo Pagaré", "Pagaré y Depósito")
            _tiene_deposito_tipos = tipo_de_garantie in ("Depósito", "Pagaré y Depósito")

            # ── PAGARÉ ────────────────────────────────────────────────────────
            monto_pagare = 0.0
            tiene_pagare = "No"
            if _tiene_pagare_tipos:
                with st.container(border=True):
                    st.markdown("##### 📄 Pagaré *(solo informativo — no afecta cálculos)*")
                    # Recuperar monto del pagaré guardado
                    _val_monto_pag = 0.0
                    try:
                        _match_pag = re.search(r'PAG:Si:(\d+)', _gar_raw)
                        if _match_pag:
                            _val_monto_pag = float(_match_pag.group(1))
                        else:
                            _match_old = re.search(r'\$([0-9,.]+)', _gar_raw)
                            if _match_old:
                                _val_monto_pag = float(_match_old.group(1).replace('.','').replace(',','.'))
                    except Exception:
                        pass
                    monto_pagare = st.number_input(
                        "Monto del Pagaré ($):", min_value=0.0,
                        value=_val_monto_pag, step=10000.0,
                        disabled=not permitir_edicion,
                        key="monto_pagare_live_sec5"
                    )
                    tiene_pagare = "Sí"
                    if monto_pagare > 0:
                        m_pag_fmt = f"${monto_pagare:,.0f}".replace(",","v").replace(".",",").replace("v",".")
                        st.caption(f"📄 Pagaré registrado por {m_pag_fmt}")

            # ── DEPÓSITO DE GARANTÍA ───────────────────────────────────────────
            monto_deposito_total = 0.0
            cuotas_deposito = 1
            cuotas_deposito_pagadas = 0
            deposito_pagados = 0.0
            valor_por_cuota_dep = 0.0
            estado_garantia_calculado = "Sin Depósito"

            if _tiene_deposito_tipos:
                with st.container(border=True):
                    st.markdown("##### 🛡️ Depósito de Garantía *(a cargo del Inquilino)*")
                    ch_dep1, ch_dep2, ch_dep3 = st.columns(3)

                    _dep_default = (
                        _safe_float(u.get('monto_garantia')) if u and _safe_float(u.get('monto_garantia')) > 0
                        else _safe_float(monto_inicial) if _safe_float(monto_inicial) > 0
                        else _safe_float(alquiler_actualizado)
                    )
                    monto_deposito_total = ch_dep1.number_input(
                        "Monto Total Pactado ($):",
                        min_value=0.0, value=_dep_default, step=5000.0,
                        disabled=not permitir_edicion,
                        key="deposito_total_live_sec5"
                    )

                    val_cuotas_dep = max(1, _safe_int(u.get('cuotas_deposito'), 1)) if u else 1
                    cuotas_deposito = ch_dep2.number_input(
                        "Cuotas pactadas:",
                        min_value=1, value=max(1, val_cuotas_dep), step=1,
                        disabled=not permitir_edicion,
                        key="cuotas_dep_live_sec5"
                    )

                    valor_por_cuota_dep = monto_deposito_total / cuotas_deposito if cuotas_deposito > 0 else 0.0
                    valor_por_cuota_dep_fmt = f"$ {valor_por_cuota_dep:,.2f}".replace(",","v").replace(".",",").replace("v",".")
                    ch_dep3.metric("Valor por cuota ($):", value=valor_por_cuota_dep_fmt)

                    val_cuotas_dep_pagas = _safe_int(u.get('cuotas_deposito_pagadas'), 0) if u else 0
                    cuotas_deposito_pagadas = st.number_input(
                        "Cuotas pagadas:",
                        min_value=0, max_value=int(cuotas_deposito),
                        value=min(val_cuotas_dep_pagas, int(cuotas_deposito)),
                        step=1, disabled=not permitir_edicion,
                        key="cuotas_dep_pagas_live"
                    )

                    monto_ya_pagado_dep = cuotas_deposito_pagadas * valor_por_cuota_dep
                    deposito_pagados = monto_ya_pagado_dep
                    monto_pagado_dep_fmt = f"$ {monto_ya_pagado_dep:,.2f}".replace(",","v").replace(".",",").replace("v",".")
                    st.metric("Monto depositado a la fecha ($):", value=monto_pagado_dep_fmt)

                    saldo_inquilino_dep = max(0.0, monto_deposito_total - monto_ya_pagado_dep)
                    cuotas_pendientes_dep = max(0, int(cuotas_deposito) - cuotas_deposito_pagadas)

                    if monto_deposito_total == 0:
                        estado_garantia_calculado = "Sin Depósito"
                    elif saldo_inquilino_dep <= 0:
                        estado_garantia_calculado = "Depositada Completa"
                        st.success("✅ Depósito abonado en su totalidad.")
                    else:
                        saldo_dep_fmt = f"$ {saldo_inquilino_dep:,.2f}".replace(",","v").replace(".",",").replace("v",".")
                        estado_garantia_calculado = f"Financiando (Saldo: {saldo_dep_fmt})"
                        st.warning(f"💵 Saldo pendiente: **{saldo_dep_fmt}** — {cuotas_pendientes_dep} cuota(s) de {valor_por_cuota_dep_fmt} c/u.")

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

            # Recalcular desde el widget actual (no del session_state)
            _alq_txt_actual = st.session_state.get("alquiler_actualizado_main", "0")
            _alq_actual = limpiar_string_a_float(_alq_txt_actual)
            base_calculo_cobro = _alq_actual if _alq_actual > 0 else (float(alquiler_actualizado) if not valor_vacio else 0.0)
            alquiler_cobrado = base_calculo_cobro
            total_pagado_calculado = alquiler_cobrado + servicios_total_calculado

            def _fmt(v):
                return f"$ {v:,.2f}".replace(",","v").replace(".",",").replace("v",".")

            cp_1.metric("Monto Neto de Alquiler ($):", value=_fmt(alquiler_cobrado))
            cp_2.metric("Total Servicios ($):", value=_fmt(servicios_total_calculado))
            cp_3.metric("TOTAL CONSOLIDADO ($):", value=_fmt(total_pagado_calculado))
    
                
            # --- BOTÓN GUARDAR FINAL ---
            st.markdown("---")
                
            boton_deshabilitado = (not permitir_edicion) or bloqueo_por_actualizacion or necesita_renovacion
            texto_boton = "💾 Actualizar Contrato Existente" if (contrato_previo and "Actualizar" in modo_guardado) else "💾 Guardar y Registrar Contrato Completo"
                
            btn_guardar_final = st.button(texto_boton, disabled=boton_deshabilitado, type="primary", key="btn_guardar_contrato_final_main")
                
    
                    
                
            if btn_guardar_final:
                alq_act_fmt = f"${alquiler_actualizado:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                # Defaults seguros en caso de que las secciones no se hayan renderizado
                _estado_gar = locals().get('estado_garantia_calculado', 'Sin Depósito')
                _monto_pag  = locals().get('monto_pagare', 0.0)
                _tiene_pag  = locals().get('tiene_pagare', 'No')
                m_pag_fmt = f"${_monto_pag:,.0f}".replace(",", "v").replace(".", ",").replace("v", ".")
                _pag_str = f"PAG:{'Si' if _tiene_pag == 'Sí' else 'No'}:{int(_monto_pag)}"
                _dep_str = f"DEP:{_estado_gar.split('(')[0].strip()}"
                detalle_garantia_unificado = f"{_pag_str}|{_dep_str}"
                registro_distribucion = f"[Alq.Actualizado: {alq_act_fmt} | Imp.Inmob: {cargo_inmobiliario}] {servicios_detalle}".strip()
                    
                inicio_str = inicio_contrato.strftime('%Y-%m-%d')
                fin_str = fin_contrato.strftime('%Y-%m-%d')
                prox_act_str = prox_actualizacion_calculada.strftime('%Y-%m-%d')
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

                    # Validar que se haya seleccionado un inquilino válido
                    if not _dni_inq or not _alias_prop:
                        st.error("❌ Debés seleccionar una **Propiedad** y un **Inquilino** válidos antes de guardar el contrato.")
                        st.stop()

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
                            duracion_meses_calculada, _opciones_act_map.get(act_contrato_seleccionado, act_contrato_seleccionado), indice_final, monto_inicial, alquiler, prox_act_str,
                            mes_actual_contrato_vivo, meses_atras_calculado, registro_distribucion, honorarios_pct, retencion_mensual_estimated,
                            cuota_honorarios, honorarios_pagados, cuotas_honorarios_pagadas,
                            tipo_de_garantie, monto_deposito_total, estado_garantia_calculado.split("(")[0].strip(), float(deposito_pagados),
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
                            duracion_meses_calculada, _opciones_act_map.get(act_contrato_seleccionado, act_contrato_seleccionado), indice_final, monto_inicial, alquiler, prox_act_str,
                            mes_actual_contrato_vivo, meses_atras_calculado, registro_distribucion, honorarios_pct, retencion_mensual_estimated,
                            cuota_honorarios, honorarios_pagados, cuotas_honorarios_pagadas,
                            tipo_de_garantie, monto_deposito_total, estado_garantia_calculado.split("(")[0].strip(), float(deposito_pagados),
                            cuotas_deposito, cuotas_deposito_pagadas,
                            imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, servicios_total_calculado,
                            cochera, alquiler_cobrado, total_pagado_calculado
                        ))
                        st.success("✔️ ¡Nuevo contrato creado e insertado con éxito!")
    
                    conn.commit()
                    # Limpiar cache para que los nuevos datos aparezcan de inmediato
                    st.cache_data.clear()
                    st.session_state.datos_contrato = None
                    st.session_state.propiedad_activa = None
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

            # empresa_id ya viene del selector de la barra superior (superadmin)
            # o del login (usuarios normales) — no necesita selector adicional
            _eid_aux = st.session_state.get("empresa_id", 0)
            if st.session_state.get("rol") == "superadmin":
                st.caption(f"🏢 Trabajando en: **{st.session_state.get('empresa_actual_nombre', '')}**")
                
            sub_tab1, sub_tab2, sub_tab3 = st.tabs(["👤 Nuevo Inquilino", "🏠 Nueva Propiedad", "🏢 Nuevo Edificio/Grupo"])
                
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
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                    ON CONFLICT DO NOTHING
                                ''', (
                                    _eid_aux,
                                    apellidos.strip(), nombres.strip(), 
                                    dni.strip() or None, tel.strip() or None, email.strip() or None
                                ))
                                conn.commit()
                                st.success(f"✅ Inquilino '{apellidos}, {nombres}' guardado correctamente.")
                                st.cache_data.clear()
                                st.rerun()
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
                    # Grupos existentes para el selectbox
                    _eid_np = st.session_state.get("empresa_id", 0)
                    try:
                        with _pg_conn() as _conn_np_g:
                            with _conn_np_g.cursor() as _cur_np_g:
                                _cur_np_g.execute(
                                    "SELECT DISTINCT grupo FROM propiedades WHERE empresa_id = %s AND grupo IS NOT NULL AND grupo != '' ORDER BY grupo",
                                    (_eid_np,)
                                )
                                _grupos_np = [r["grupo"] for r in _cur_np_g.fetchall()]
                    except Exception:
                        _grupos_np = []
                    _grupo_np_sel = st.selectbox("🏢 Grupo / Edificio:", ["— Sin grupo —"] + _grupos_np)
                    grupo = "" if _grupo_np_sel == "— Sin grupo —" else _grupo_np_sel
                        
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
                                                            ciudad, provincia, tipo, nis, cuenta_gas, finca, cuenta_ooss, nro_padron, grupo) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT DO NOTHING
                                ''', (
                                    _eid_aux,
                                    alias, calle, numero, depto, propietario, ciudad, provincia, tipo,
                                    nis, cuenta_gas, finca, cuenta_ooss, nro_padron, grupo.strip() or None
                                ))
                                conn.commit()
                                st.success("Propiedad guardada.")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                            finally:
                                conn.close()

            with sub_tab3:
                st.markdown("📝 Crear / Actualizar Grupo de Propiedades")
                st.caption("Asignás un nombre de grupo a un conjunto de propiedades para usarlo en gastos compartidos.")

                # Cargar propiedades disponibles
                _eid_grp = st.session_state.get("empresa_id", 0)
                with _pg_conn() as _conn_grp:
                    with _conn_grp.cursor() as _cur_grp:
                        _cur_grp.execute(
                            "SELECT id, alias_propiedad, COALESCE(grupo, '') AS grupo FROM propiedades WHERE empresa_id = %s ORDER BY alias_propiedad",
                            (_eid_grp,)
                        )
                        _props_grp = _cur_grp.fetchall()

                if not _props_grp:
                    st.warning("No hay propiedades registradas.")
                else:
                    # Mostrar grupos existentes
                    _grupos_existentes = sorted(set(r["grupo"] for r in _props_grp if r["grupo"]))
                    if _grupos_existentes:
                        st.info(f"Grupos existentes: {', '.join(_grupos_existentes)}")

                    with st.form("form_grupo", clear_on_submit=False):
                        _nombre_grupo = st.text_input("🏢 Nombre del Grupo / Edificio:", placeholder="Ej: Tucumán 150")

                        _opciones_grp = {f"{r['alias_propiedad']} (grupo actual: {r['grupo'] or 'ninguno'})": r['id'] for r in _props_grp}
                        _props_sel_grp = st.multiselect(
                            "🏠 Propiedades que forman el grupo:",
                            options=list(_opciones_grp.keys()),
                            help="Seleccioná todas las unidades del edificio"
                        )

                        _btn_grupo = st.form_submit_button("💾 Guardar Grupo", type="primary")

                        if _btn_grupo:
                            if not _nombre_grupo.strip():
                                st.error("❌ Ingresá un nombre para el grupo.")
                            elif len(_props_sel_grp) < 2:
                                st.error("❌ Seleccioná al menos 2 propiedades.")
                            else:
                                _ids_grp = [_opciones_grp[l] for l in _props_sel_grp]
                                try:
                                    with _pg_conn() as _conn_grp_upd:
                                        with _conn_grp_upd.cursor() as _cur_grp_upd:
                                            for _pid in _ids_grp:
                                                _cur_grp_upd.execute(
                                                    "UPDATE propiedades SET grupo = %s WHERE id = %s AND empresa_id = %s",
                                                    (_nombre_grupo.strip(), _pid, _eid_grp)
                                                )
                                    st.cache_data.clear()
                                    st.success(f"✅ Grupo '{_nombre_grupo.strip()}' guardado con {len(_ids_grp)} propiedades.")
                                    st.rerun()
                                except Exception as _eg:
                                    st.error(f"Error: {_eg}")



            # =====================================================================
            # MÓDULO DE EDICIÓN / MODIFICACIÓN DE DATOS EXISTENTES
            # =====================================================================
            st.markdown("---")
            st.markdown("### 🔄 Modificar Datos de Inquilinos o Propiedades Existentes")
    
            # Consultamos los desplegables actualizados del sistema
            dict_propiedades_edit, dict_inquilinos_edit = obtener_datos_desplegables(st.session_state.get("empresa_id", 0))
    
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
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT apellidos, nombres, dni, telefono, email FROM inquilinos WHERE id = %s", (id_inq_edit,))
                        datos_inq = cursor.fetchone()
                    finally:
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
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT alias_propiedad, calle, numero, departamento, COALESCE(grupo, '') AS grupo FROM propiedades WHERE id = %s", (id_prop_edit,))
                        datos_prop = cursor.fetchone()
                    finally:
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
        lista_subtabs = ["👤 Crear Usuarios", "🔐 Editar Permisos", "⚙️ Configuraciones"]
        if rol_sesion == "superadmin":
            lista_subtabs.append("🚀 Importar / Exportar Datos (CSV)")
                
        subtabs_objetos = st.tabs(lista_subtabs)
        subtab_usuarios = subtabs_objetos[0]
        subtab_permisos = subtabs_objetos[1]
        subtab_config = subtabs_objetos[2]
        if rol_sesion == "superadmin":
            subtab_csv = subtabs_objetos[3]
                
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
                                
                            # Identificador lógico de la empresa (ya no es un archivo físico:
                            # todo vive en Postgres/Supabase. Se mantiene como string porque
                            # "archivo_db" se sigue usando como clave de enrutamiento en usuarios_central).
                            if rol_sesion == "admin":
                                # Si es un admin de empresa, heredamos de forma estricta su base de datos actual
                                ruta_db_completa = st.session_state.get("empresa_db")
                            else:
                                # Si es superadmin y crea una empresa nueva: identificador único
                                ruta_db_completa = f"{secrets.token_hex(8)}/data.db"

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
                        st.info("🏠 El rol **Propietario** tiene acceso fijo de solo lectura a: Dashboard, Planilla de Contratos, Historial de Caja, Gastos de Propiedades y Rendición a Propietarios. No requiere configuración de permisos.")
                        p_dash = p_plan = p_pagos = p_hist = p_carga = p_aux = p_gastos = p_rend = False
                    else:
                        st.markdown("#### 📑 Asignación de Permisos de Pestañas (Para roles 'admin' y 'user')")

                        permisos_actuales = []
                        try:
                            with _pg_conn() as _conn_perm:
                                with _conn_perm.cursor() as _cur_perm:
                                    _cur_perm.execute(
                                        "SELECT pestana FROM permisos_usuario WHERE username = %s",
                                        (user_seleccionado,)
                                    )
                                    permisos_actuales = [row["pestana"] for row in _cur_perm.fetchall()]
                        except Exception as e:
                            st.warning(f"Aviso al recuperar permisos existentes: {e}")

                        p_dash  = st.checkbox("📈 Tablero de Control",              value=("dashboard"       in permisos_actuales))
                        p_plan  = st.checkbox("📊 Planilla de Contratos",            value=("planilla"        in permisos_actuales))
                        p_pagos = st.checkbox("💰 Registrar / Emitir Recibo",        value=("pagos"           in permisos_actuales))
                        p_hist  = st.checkbox("🗄️ Historial de Caja",                value=("historial_pagos" in permisos_actuales))
                        p_carga = st.checkbox("📝 Carga de Contratos",               value=("carga"           in permisos_actuales))
                        p_aux   = st.checkbox("⚙️ Cargar Inquilinos / Propiedades",  value=("auxiliares"      in permisos_actuales))
                        p_gastos= st.checkbox("🔧 Gastos de Propiedades",            value=("gastos"          in permisos_actuales))
                        p_rend  = st.checkbox("📑 Rendición a Propietarios",         value=("rendicion"       in permisos_actuales))

                        # WhatsApp — solo habilitado si la empresa tiene WhatsApp activo
                        st.markdown("---")
                        st.markdown("#### 📲 WhatsApp Business")
                        _wa_empresa_ok = st.session_state.get("cfg_whatsapp_habilitado", False)
                        if not _wa_empresa_ok:
                            st.caption("Solicitá la funcionalidad de 📲 WhatsApp a tu administrador.")
                        try:
                            with _pg_conn() as _conn_wa_u:
                                with _conn_wa_u.cursor() as _cur_wa_u:
                                    _cur_wa_u.execute(
                                        "SELECT whatsapp_habilitado FROM permisos_usuario WHERE username = %s LIMIT 1",
                                        (user_seleccionado,)
                                    )
                                    _row_wa_u = _cur_wa_u.fetchone()
                                    _wa_user_actual = bool(_row_wa_u["whatsapp_habilitado"]) if _row_wa_u else False
                        except Exception:
                            _wa_user_actual = False
                        _wa_user_nuevo = st.toggle(
                            "Habilitar envío de mensajes por WhatsApp",
                            value=_wa_user_actual,
                            disabled=not _wa_empresa_ok,
                            key=f"wa_user_{user_seleccionado}",
                            help="Solo disponible si WhatsApp está habilitado para la empresa."
                        )
    
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
                            if ruta_db_user:
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
                                if p_rend: nuevas_pestanas.append("rendicion")
                                    
                                for p in nuevas_pestanas:
                                    cursor_emp.execute("INSERT INTO permisos_usuario (username, pestana) VALUES (%s, %s) ON CONFLICT (username, pestana) DO NOTHING", (user_seleccionado, p))

                                # Guardar permiso de WhatsApp por usuario
                                cursor_emp.execute(
                                    "UPDATE permisos_usuario SET whatsapp_habilitado = %s WHERE username = %s",
                                    (_wa_user_nuevo, user_seleccionado)
                                )
                                    
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
                    # VALOR GARANTÍA → monto_garantia (monto del pagaré si TIPO=PAGARE)
                    "VALOR GARANTÍA": "monto_garantia",
                    # GARANTÍA → monto depósito de garantía (se guarda en garantia_pagada como monto base)
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
                                                            except Exception: valor_celda = None
                                                        elif col_db in ['act_contrato', 'mes_contrato', 'mes_actualizacion_contrato', 'cuota_honorarios', 'honorarios_pagados', 'garantia_pagada']:
                                                            try: valor_celda = int(float(str(valor_celda).split('.')[0]))
                                                            except Exception: valor_celda = None
                                                        elif col_db in ['monto_inicial', 'alquiler', 'monto_honorarios', 'monto_garantia', 'imp_inmobiliario', 'expensas', 'edesal', 'gas', 'municipalidad', 'ooss', 'cochera']:
                                                            try: valor_celda = round(float(str(valor_celda).replace(',', '.')), 2)
                                                            except Exception: valor_celda = None
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
                                                        st.cache_data.clear()
                                                        st.success(f"✅ {len(datos_cont)} contrato(s) importado(s) correctamente.")
                                                        st.balloons()
                                                        st.rerun()
                                                    except psycopg2.Error as op_err:
                                                        st.error(f"❌ Error al importar: {op_err}")
                                                
                                # --- PROCESADOR PARA GASTOS_PROPIEDADES ---
                                if tabla_seleccionada == "gastos_propiedades":
                                    if "propiedad_id" not in columnas_csv:
                                        st.error("❌ El CSV debe tener la columna 'propiedad_id' con el alias de la propiedad.")
                                    else:
                                        _eid_gimp = _empresa_id_csv or st.session_state.get("empresa_id", 0)
                                        # Construir mapa alias → id
                                        with _pg_conn() as _conn_gmap:
                                            with _conn_gmap.cursor() as _cur_gmap:
                                                _cur_gmap.execute(
                                                    "SELECT id, alias_propiedad FROM propiedades WHERE empresa_id = %s",
                                                    (_eid_gimp,)
                                                )
                                                _prop_map = {r["alias_propiedad"]: r["id"] for r in _cur_gmap.fetchall()}

                                        # Procesar filas
                                        _gastos_ok = []
                                        _gastos_err = []
                                        for idx, fila in df.iterrows():
                                            _alias = str(fila.get("propiedad_id", "")).strip()
                                            if not _alias or _alias == "nan":
                                                _gastos_err.append(f"Fila {idx+2}: alias vacío")
                                                continue
                                            _pid = _prop_map.get(_alias)
                                            if not _pid:
                                                _gastos_err.append(f"Fila {idx+2}: '{_alias}' no encontrada")
                                                continue
                                            _fecha_g = None
                                            try:
                                                _fecha_g = pd.to_datetime(str(fila.get("fecha","")).strip(), dayfirst=True).strftime("%Y-%m-%d")
                                            except Exception:
                                                _gastos_err.append(f"Fila {idx+2}: fecha inválida")
                                                continue
                                            _gastos_ok.append({
                                                "propiedad_id": _pid,
                                                "fecha": _fecha_g,
                                                "categoria": str(fila.get("categoria","")).strip() or "📦 Otros Pasivos",
                                                "descripcion": str(fila.get("descripcion","")).strip(),
                                                "monto": float(str(fila.get("monto",0)).replace(",",".")),
                                                "proveedor": str(fila.get("proveedor","")).strip() or None,
                                                "comprobante": str(fila.get("comprobante","")).strip() or None,
                                                "pagado_por": str(fila.get("pagado_por","")).strip() or "Inmobiliaria",
                                                "observaciones": str(fila.get("observaciones","")).strip() or None,
                                                "tipo_gasto": str(fila.get("tipo_gasto","Extraordinario")).strip() or "Extraordinario",
                                                "cobrado": str(fila.get("cobrado","")).strip().lower() in ("true","1","si","sí"),
                                                "periodo_cobrado": str(fila.get("periodo_cobrado","")).strip() or None,
                                            })

                                        if _gastos_err:
                                            st.warning(f"⚠️ {len(_gastos_err)} fila(s) con errores:")
                                            for _e in _gastos_err[:5]: st.caption(_e)

                                        if _gastos_ok:
                                            df_prev_g = pd.DataFrame(_gastos_ok)
                                            st.markdown(f"**{len(_gastos_ok)} gasto(s) listos para importar**")
                                            st.dataframe(df_prev_g[["propiedad_id","fecha","categoria","descripcion","monto","tipo_gasto"]], use_container_width=True, hide_index=True)

                                            col_gb1, col_gb2 = st.columns(2)
                                            _imp_g_todos = col_gb1.button("✅ Importar TODOS", type="primary", use_container_width=True, key="btn_gimp_todos")
                                            _gimp_key = f"imported_gastos_{archivo_subido.name}_{len(_gastos_ok)}"

                                            if _imp_g_todos and _gimp_key not in st.session_state:
                                                with _pg_conn() as _conn_gi2:
                                                    with _conn_gi2.cursor() as _cur_gi2:
                                                        for _g in _gastos_ok:
                                                            _cur_gi2.execute("""
                                                                INSERT INTO gastos_propiedades
                                                                (empresa_id, propiedad_id, fecha, categoria, descripcion, monto,
                                                                 proveedor, comprobante, pagado_por, observaciones, tipo_gasto, cobrado, periodo_cobrado)
                                                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                                                ON CONFLICT DO NOTHING
                                                            """, (_eid_gimp, _g["propiedad_id"], _g["fecha"], _g["categoria"],
                                                                  _g["descripcion"], _g["monto"], _g["proveedor"], _g["comprobante"],
                                                                  _g["pagado_por"], _g["observaciones"], _g["tipo_gasto"],
                                                                  _g["cobrado"], _g["periodo_cobrado"]))
                                                st.session_state[_gimp_key] = True
                                                st.cache_data.clear()
                                                st.success(f"✅ {len(_gastos_ok)} gasto(s) importados.")
                                                st.balloons()
                                                st.rerun()

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
                                            st.cache_data.clear()
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

                                st.cache_data.clear()
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
                    
                # Selector de empresa — usar cursor directo
                with _pg_conn() as _conn_del_list:
                    with _conn_del_list.cursor() as _cur_del_list:
                        _cur_del_list.execute("SELECT DISTINCT nombre_empresa, archivo_db FROM usuarios_central")
                        _rows_del = _cur_del_list.fetchall()

                # Incluir empresa SuperAdmin (id=2, no tiene fila en usuarios_central)
                dict_empresas_filas = {r["nombre_empresa"]: r["archivo_db"] for r in _rows_del if r["nombre_empresa"] and r["archivo_db"]}
                dict_empresas_filas["SuperAdmin"] = "central.db"  # empresa del superadmin

                if dict_empresas_filas:
                    empresa_datos_seleccionada = st.selectbox(
                        "1. Seleccione la Empresa:",
                        options=list(dict_empresas_filas.keys()),
                        key="sb_empresa_datos_del_multi"
                    )
                        
                    ruta_db_objetivo = dict_empresas_filas[empresa_datos_seleccionada]
                    _eid_del = 2 if empresa_datos_seleccionada == "SuperAdmin" else _get_empresa_id(ruta_db_objetivo)

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
                                                    st.cache_data.clear()
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
        # SUBPESTAÑA: CONFIGURACIONES
        # =====================================================================
        with subtab_config:
            st.markdown("#### ⚙️ Configuraciones Generales")
            st.caption("Estas opciones afectan el comportamiento de la app para toda la empresa.")

            # Superadmin puede seleccionar cualquier empresa
            if rol_sesion == "superadmin":
                try:
                    with _pg_conn() as _conn_emps:
                        with _conn_emps.cursor() as _cur_emps:
                            _cur_emps.execute("SELECT id, nombre_empresa FROM empresas ORDER BY nombre_empresa")
                            _emps = _cur_emps.fetchall()
                    _dict_emps = {f"{e['nombre_empresa']} (ID: {e['id']})": e['id'] for e in _emps}
                    _emp_sel = st.selectbox("Seleccioná la empresa a configurar:", list(_dict_emps.keys()), key="cfg_empresa_sel")
                    _eid_cfg = _dict_emps[_emp_sel]
                except Exception:
                    _eid_cfg = st.session_state.get("empresa_id", 0)
            else:
                _eid_cfg = st.session_state.get("empresa_id", 0)

            # Cargar configuración actual desde la BD (o crear default si no existe)
            try:
                with _pg_conn() as _conn_cfg:
                    with _conn_cfg.cursor() as _cur_cfg:
                        _cur_cfg.execute(
                            "SELECT actualizar_alquiler_auto FROM configuraciones_empresa WHERE empresa_id = %s",
                            (_eid_cfg,)
                        )
                        _row_cfg = _cur_cfg.fetchone()
                        if _row_cfg is None:
                            _cur_cfg.execute(
                                "INSERT INTO configuraciones_empresa (empresa_id, actualizar_alquiler_auto) VALUES (%s, TRUE) "
                                "ON CONFLICT (empresa_id) DO NOTHING",
                                (_eid_cfg,)
                            )
                            _conn_cfg.commit()
                            _valor_actual_cfg = True
                        else:
                            _valor_actual_cfg = bool(_row_cfg["actualizar_alquiler_auto"])
            except Exception as _e_cfg:
                st.error(f"Error al cargar configuraciones: {_e_cfg}")
                _valor_actual_cfg = True

            st.markdown("---")
            st.markdown("##### 💰 Monto Neto Alquiler — Registrar / Emitir Recibo")
            _nuevo_valor_cfg = st.toggle(
                "Actualizar monto de alquiler automáticamente",
                value=_valor_actual_cfg,
                key="toggle_actualizar_alquiler_auto",
                help=(
                    "**Activado:** el campo 'Monto Neto Alquiler' se completa solo con el Monto Actualizado "
                    "calculado por ICL/IPC (sin botón Aplicar).\n\n"
                    "**Desactivado:** el campo usa el alquiler vigente del contrato por defecto, y aparece "
                    "el botón '⬅️ Aplicar' para cargar el Monto Actualizado manualmente (comportamiento v1.030)."
                )
            )

            if _nuevo_valor_cfg != _valor_actual_cfg:
                try:
                    with _pg_conn() as _conn_cfg2:
                        with _conn_cfg2.cursor() as _cur_cfg2:
                            _cur_cfg2.execute(
                                "UPDATE configuraciones_empresa SET actualizar_alquiler_auto = %s WHERE empresa_id = %s",
                                (_nuevo_valor_cfg, _eid_cfg)
                            )
                        _conn_cfg2.commit()
                    st.session_state["cfg_actualizar_alquiler_auto"] = _nuevo_valor_cfg
                    st.cache_data.clear()
                    st.success("✅ Configuración guardada.")
                    st.rerun()
                except Exception as _e_cfg2:
                    st.error(f"Error al guardar configuración: {_e_cfg2}")
            else:
                st.session_state["cfg_actualizar_alquiler_auto"] = _valor_actual_cfg

            st.markdown("---")
            st.markdown("##### 🔔 Recordatorios Automáticos por WhatsApp")

            _wa_activo_rec = st.session_state.get("cfg_whatsapp_habilitado", False)
            if not _wa_activo_rec:
                st.caption("⚠️ Habilitá WhatsApp para configurar recordatorios.")
            else:
                # Cargar recordatorios existentes
                try:
                    with _pg_conn() as _conn_rec:
                        with _conn_rec.cursor() as _cur_rec:
                            _cur_rec.execute(
                                "SELECT id, tipo, dia_del_mes, activo FROM whatsapp_recordatorios WHERE empresa_id = %s ORDER BY tipo, dia_del_mes",
                                (_eid_cfg,)
                            )
                            _recordatorios = _cur_rec.fetchall()
                except Exception as _e_rec:
                    st.error(f"Error cargando recordatorios: {_e_rec}")
                    _recordatorios = []

                # Separar por tipo
                _recs_venc = [r for r in _recordatorios if r["tipo"] == "vencimiento"]
                _recs_act  = [r for r in _recordatorios if r["tipo"] == "actualizacion"]

                # ── Vencimiento de contrato ──
                st.markdown("**📅 Vencimiento de contrato**")
                st.caption("Enviá recordatorios al inquilino cuando el contrato está por vencer.")

                for _r in _recs_venc:
                    _rv1, _rv2, _rv3 = st.columns([3, 1, 1])
                    _rv1.markdown(f"{'✅' if _r['activo'] else '❌'} **{_r['dia_del_mes']}** de cada mes")
                    if _rv2.button("🔄", key=f"toggle_rec_{_r['id']}", help="Activar/Desactivar"):
                        try:
                            with _pg_conn() as _conn_tr:
                                with _conn_tr.cursor() as _cur_tr:
                                    _cur_tr.execute("UPDATE whatsapp_recordatorios SET activo = NOT activo WHERE id = %s", (_r["id"],))
                                _conn_tr.commit()
                            st.rerun()
                        except Exception as _e_tr:
                            st.error(f"Error: {_e_tr}")
                    if _rv3.button("🗑️", key=f"del_rec_{_r['id']}", help="Eliminar"):
                        try:
                            with _pg_conn() as _conn_dr:
                                with _conn_dr.cursor() as _cur_dr:
                                    _cur_dr.execute("DELETE FROM whatsapp_recordatorios WHERE id = %s", (_r["id"],))
                                _conn_dr.commit()
                            st.rerun()
                        except Exception as _e_dr:
                            st.error(f"Error: {_e_dr}")

                with st.form("form_rec_venc"):
                    _rv_dias = st.number_input("Agregar recordatorio X días antes:", min_value=1, max_value=365, value=30, step=1, key="rv_dias_input")
                    if st.form_submit_button("➕ Agregar"):
                        try:
                            with _pg_conn() as _conn_arv:
                                with _conn_arv.cursor() as _cur_arv:
                                    _cur_arv.execute(
                                        "INSERT INTO whatsapp_recordatorios (empresa_id, tipo, dia_del_mes) VALUES (%s, 'vencimiento', %s)",
                                        (_eid_cfg, int(_rv_dias))
                                    )
                                _conn_arv.commit()
                            st.success(f"✅ Recordatorio de {int(_rv_dias)} días agregado.")
                            st.rerun()
                        except Exception as _e_arv:
                            st.error(f"Error: {_e_arv}")

                st.markdown("---")

                # ── Próxima actualización ──
                st.markdown("**📈 Próxima actualización de alquiler**")
                st.caption("Avisá al inquilino cuando se acerca la fecha de actualización del alquiler.")

                for _r in _recs_act:
                    _ra1, _ra2, _ra3 = st.columns([3, 1, 1])
                    _ra1.markdown(f"{'✅' if _r['activo'] else '❌'} **{_r['dia_del_mes']}** de cada mes")
                    if _ra2.button("🔄", key=f"toggle_rec_{_r['id']}", help="Activar/Desactivar"):
                        try:
                            with _pg_conn() as _conn_ta:
                                with _conn_ta.cursor() as _cur_ta:
                                    _cur_ta.execute("UPDATE whatsapp_recordatorios SET activo = NOT activo WHERE id = %s", (_r["id"],))
                                _conn_ta.commit()
                            st.rerun()
                        except Exception as _e_ta:
                            st.error(f"Error: {_e_ta}")
                    if _ra3.button("🗑️", key=f"del_rec_{_r['id']}", help="Eliminar"):
                        try:
                            with _pg_conn() as _conn_da:
                                with _conn_da.cursor() as _cur_da:
                                    _cur_da.execute("DELETE FROM whatsapp_recordatorios WHERE id = %s", (_r["id"],))
                                _conn_da.commit()
                            st.rerun()
                        except Exception as _e_da:
                            st.error(f"Error: {_e_da}")

                with st.form("form_rec_act"):
                    _ra_dias = st.number_input("Agregar recordatorio X días antes:", min_value=1, max_value=28, value=15, step=1, key="ra_dias_input")
                    if st.form_submit_button("➕ Agregar"):
                        try:
                            with _pg_conn() as _conn_ara:
                                with _conn_ara.cursor() as _cur_ara:
                                    _cur_ara.execute(
                                        "INSERT INTO whatsapp_recordatorios (empresa_id, tipo, dia_del_mes) VALUES (%s, 'actualizacion', %s)",
                                        (_eid_cfg, int(_ra_dias))
                                    )
                                _conn_ara.commit()
                            st.success(f"✅ Recordatorio de {int(_ra_dias)} días agregado.")
                            st.rerun()
                        except Exception as _e_ara:
                            st.error(f"Error: {_e_ara}")


            st.markdown("---")
            st.markdown("##### 📲 WhatsApp Business")

            _es_superadmin_cfg = (rol_sesion == "superadmin")

            try:
                with _pg_conn() as _conn_wa:
                    with _conn_wa.cursor() as _cur_wa:
                        _cur_wa.execute(
                            "SELECT whatsapp_habilitado, whatsapp_token, whatsapp_phone_id, whatsapp_credenciales_propias, whatsapp_numero_id FROM configuraciones_empresa WHERE empresa_id = %s",
                            (_eid_cfg,)
                        )
                        _row_wa = _cur_wa.fetchone()
                        _wa_habilitado      = bool(_row_wa["whatsapp_habilitado"])        if _row_wa else False
                        _wa_token           = _row_wa["whatsapp_token"]        or ""      if _row_wa else ""
                        _wa_phone_id        = _row_wa["whatsapp_phone_id"]     or ""      if _row_wa else ""
                        _wa_cred_propias    = bool(_row_wa["whatsapp_credenciales_propias"]) if _row_wa else False
                        _wa_numero_id       = _row_wa["whatsapp_numero_id"]               if _row_wa else None
            except Exception as _e_wa:
                st.error(f"Error al cargar configuración de WhatsApp: {_e_wa}")
                _wa_habilitado, _wa_token, _wa_phone_id, _wa_cred_propias, _wa_numero_id = False, "", "", False, None

            _wa_nuevo = st.toggle(
                "Habilitar WhatsApp Business para esta empresa",
                value=_wa_habilitado,
                key="toggle_whatsapp_habilitado",
                disabled=not _es_superadmin_cfg,
                help="Solo el superadmin puede habilitar/deshabilitar este módulo."
            )

            if _wa_nuevo:
                st.markdown("**¿Cómo se gestionan las credenciales?**")
                _cred_modo = st.radio(
                    "Modo de credenciales:",
                    ["Usar número del pool (administrado por superadmin)", "La empresa gestiona sus propias credenciales"],
                    index=1 if _wa_cred_propias else 0,
                    key="wa_cred_modo",
                    disabled=not _es_superadmin_cfg
                )
                _nueva_cred_propias = (_cred_modo == "La empresa gestiona sus propias credenciales")

                if not _nueva_cred_propias:
                    # ── Pool de números del superadmin ──
                    st.markdown("**Asignar número del pool:**")
                    if _es_superadmin_cfg:
                        # Gestión del pool
                        with st.expander("➕ Administrar pool de números"):
                            with st.form("form_nuevo_numero_wa"):
                                _nn_nombre   = st.text_input("Nombre/descripción del número:")
                                _nn_phone_id = st.text_input("Phone Number ID:")
                                _nn_token    = st.text_input("Token de acceso:", type="password")
                                if st.form_submit_button("Agregar número"):
                                    if _nn_nombre and _nn_phone_id and _nn_token:
                                        try:
                                            with _pg_conn() as _conn_nn:
                                                with _conn_nn.cursor() as _cur_nn:
                                                    # Guardar token en Vault y obtener secret_id
                                                    _cur_nn.execute(
                                                        "SELECT guardar_token_whatsapp(%s, %s) AS secret_id",
                                                        (f"wa_num_{_nn_nombre.strip()}", _nn_token.strip())
                                                    )
                                                    _secret_id = _cur_nn.fetchone()["secret_id"]
                                                    # Guardar número con secret_id (sin token en claro)
                                                    _cur_nn.execute(
                                                        "INSERT INTO whatsapp_numeros (nombre, phone_id, token_secret_id) VALUES (%s, %s, %s)",
                                                        (_nn_nombre.strip(), _nn_phone_id.strip(), _secret_id)
                                                    )
                                                _conn_nn.commit()
                                            st.success("✅ Número agregado con token encriptado en Vault.")
                                            st.rerun()
                                        except Exception as _e_nn:
                                            st.error(f"Error: {_e_nn}")
                                    else:
                                        st.warning("Completá todos los campos.")

                    # Selector de número del pool
                    try:
                        with _pg_conn() as _conn_pool:
                            with _conn_pool.cursor() as _cur_pool:
                                _cur_pool.execute("SELECT id, nombre, phone_id, activo FROM whatsapp_numeros ORDER BY id")
                                _numeros_pool = _cur_pool.fetchall()
                    except Exception:
                        _numeros_pool = []

                    if _numeros_pool:
                        _dict_numeros = {f"{r['nombre']} ({r['phone_id']}){'  ⛔' if not r['activo'] else ''}": r['id'] for r in _numeros_pool}
                        _num_actual_label = next((k for k, v in _dict_numeros.items() if v == _wa_numero_id), list(_dict_numeros.keys())[0])
                        _num_sel_label = st.selectbox("Número asignado:", list(_dict_numeros.keys()), index=list(_dict_numeros.keys()).index(_num_actual_label), disabled=not _es_superadmin_cfg)
                        _nuevo_numero_id = _dict_numeros[_num_sel_label]
                    else:
                        st.info("No hay números en el pool. Agregá uno con el botón de arriba.")
                        _nuevo_numero_id = None
                    _nuevo_token_empresa    = _wa_token
                    _nuevo_phone_id_empresa = _wa_phone_id

                else:
                    # ── Credenciales propias de la empresa ──
                    st.markdown("**Credenciales propias de la empresa:**")
                    _nuevo_token_empresa    = st.text_input("Token de acceso:", value=_wa_token, type="password", key="wa_token_empresa")
                    _nuevo_phone_id_empresa = st.text_input("Phone Number ID:", value=_wa_phone_id, key="wa_phone_id_empresa")
                    _nuevo_numero_id        = _wa_numero_id

                if _es_superadmin_cfg:
                    if st.button("💾 Guardar configuración de WhatsApp", key="btn_guardar_wa"):
                        try:
                            with _pg_conn() as _conn_wa2:
                                with _conn_wa2.cursor() as _cur_wa2:
                                    _token_secret_id_guardar = None
                                    if _nueva_cred_propias and _nuevo_token_empresa.strip():
                                        # Guardar token en Vault
                                        _cur_wa2.execute(
                                            "SELECT guardar_token_whatsapp(%s, %s) AS secret_id",
                                            (f"wa_empresa_{_eid_cfg}", _nuevo_token_empresa.strip())
                                        )
                                        _token_secret_id_guardar = _cur_wa2.fetchone()["secret_id"]
                                    _cur_wa2.execute(
                                        """UPDATE configuraciones_empresa SET
                                            whatsapp_habilitado = %s,
                                            whatsapp_credenciales_propias = %s,
                                            whatsapp_numero_id = %s,
                                            whatsapp_token = NULL,
                                            whatsapp_phone_id = %s,
                                            whatsapp_token_secret_id = %s
                                        WHERE empresa_id = %s""",
                                        (_wa_nuevo, _nueva_cred_propias, _nuevo_numero_id,
                                         _nuevo_phone_id_empresa, _token_secret_id_guardar, _eid_cfg)
                                    )
                                _conn_wa2.commit()
                            st.session_state["cfg_whatsapp_habilitado"]   = _wa_nuevo
                            st.session_state["cfg_whatsapp_phone_id"]     = _nuevo_phone_id_empresa
                            st.success("✅ Configuración de WhatsApp guardada con token encriptado en Vault.")
                            st.rerun()
                        except Exception as _e_wa2:
                            st.error(f"Error al guardar: {_e_wa2}")

            elif _wa_habilitado != _wa_nuevo and _es_superadmin_cfg:
                try:
                    with _pg_conn() as _conn_wa3:
                        with _conn_wa3.cursor() as _cur_wa3:
                            _cur_wa3.execute(
                                "UPDATE configuraciones_empresa SET whatsapp_habilitado = %s WHERE empresa_id = %s",
                                (_wa_nuevo, _eid_cfg)
                            )
                        _conn_wa3.commit()
                    st.session_state["cfg_whatsapp_habilitado"] = _wa_nuevo
                    st.success("✅ WhatsApp deshabilitado.")
                    st.rerun()
                except Exception as _e_wa3:
                    st.error(f"Error: {_e_wa3}")

            # ── Configuración de Recordatorios Automáticos ──────────────────
            if st.session_state.get("cfg_whatsapp_habilitado", False):
                st.markdown("---")
                st.markdown("##### ⏰ Recordatorios Automáticos")
                st.caption("Configurá cuántos días antes se envía cada tipo de recordatorio. Podés agregar múltiples.")

                # Cargar recordatorios existentes
                try:
                    with _pg_conn() as _conn_rec:
                        with _conn_rec.cursor() as _cur_rec:
                            _cur_rec.execute(
                                "SELECT id, tipo, dia_del_mes, activo FROM whatsapp_recordatorios WHERE empresa_id = %s ORDER BY tipo, dia_del_mes",
                                (_eid_cfg,)
                            )
                            _recordatorios = _cur_rec.fetchall()
                except Exception as _e_rec:
                    st.error(f"Error cargando recordatorios: {_e_rec}")
                    _recordatorios = []

                # Mostrar y gestionar recordatorios existentes
                for _tipo_lbl, _tipo_key in [("📅 Vencimiento de contrato", "vencimiento"), ("📈 Próxima actualización", "actualizacion")]:
                    st.markdown(f"**{_tipo_lbl}:**")
                    _recs_tipo = [r for r in _recordatorios if r["tipo"] == _tipo_key]

                    if _recs_tipo:
                        for _rec in _recs_tipo:
                            _r1, _r2, _r3 = st.columns([3, 1, 1])
                            _r1.markdown(f"{'✅' if _rec['activo'] else '❌'} {_rec['dia_del_mes']}** de cada mes")

                            if _r2.button("🔄", key=f"tog_rec_{_rec['id']}", help="Activar/Desactivar"):
                                try:
                                    with _pg_conn() as _conn_tr:
                                        with _conn_tr.cursor() as _cur_tr:
                                            _cur_tr.execute("UPDATE whatsapp_recordatorios SET activo = NOT activo WHERE id = %s", (_rec['id'],))
                                        _conn_tr.commit()
                                    st.rerun()
                                except Exception as _e_tr:
                                    st.error(f"Error: {_e_tr}")

                            if _r3.button("🗑️", key=f"del_rec_{_rec['id']}", help="Eliminar"):
                                try:
                                    with _pg_conn() as _conn_dr:
                                        with _conn_dr.cursor() as _cur_dr:
                                            _cur_dr.execute("DELETE FROM whatsapp_recordatorios WHERE id = %s", (_rec['id'],))
                                        _conn_dr.commit()
                                    st.rerun()
                                except Exception as _e_dr:
                                    st.error(f"Error: {_e_dr}")
                    else:
                        st.caption("No hay recordatorios configurados.")

                    # Agregar nuevo recordatorio para este tipo
                    _nc1, _nc2 = st.columns([2, 1])
                    _dia_nuevo = _nc1.number_input(
                        f"Agregar recordatorio ({_tipo_key}):",
                        min_value=1, max_value=28, value=15, step=1,
                        key=f"dias_nuevo_{_tipo_key}",
                        label_visibility="collapsed"
                    )
                    if _nc2.button(f"➕ Agregar", key=f"btn_add_rec_{_tipo_key}", use_container_width=True):
                        try:
                            with _pg_conn() as _conn_ar:
                                with _conn_ar.cursor() as _cur_ar:
                                    _cur_ar.execute(
                                        "INSERT INTO whatsapp_recordatorios (empresa_id, tipo, dia_del_mes) VALUES (%s, %s, %s)",
                                        (_eid_cfg, _tipo_key, int(_dia_nuevo))
                                    )
                                _conn_ar.commit()
                            st.success(f"✅ Recordatorio del día {_dia_nuevo} agregado.")
                            st.rerun()
                        except Exception as _e_ar:
                            st.error(f"Error: {_e_ar}")
                    st.markdown("")


# =====================================================================
if tab_gastos:
    with tab_gastos:
        st.subheader("🔧 Registro de Gastos de Propiedades")

        # --- Cargar propiedades disponibles (filtradas si es propietario) ---
        _pf_g = st.session_state.get("propietario_filtro", "")
        _pf_g_activo = rol_actual == "propietario" and bool(_pf_g)
        if _pf_g_activo:
            with _pg_conn() as _cpg1:
                with _cpg1.cursor() as _cupg1:
                    _cupg1.execute("SELECT id, alias_propiedad, propietario, calle, numero, grupo FROM propiedades WHERE empresa_id = %s AND propietario = %s ORDER BY alias_propiedad", (st.session_state.get("empresa_id", 0), _pf_g))
                    _props_gasto = pd.DataFrame([dict(r) for r in _cupg1.fetchall()])
        else:
            with _pg_conn() as _cpg2:
                with _cpg2.cursor() as _cupg2:
                    _cupg2.execute("SELECT id, alias_propiedad, propietario, calle, numero, grupo FROM propiedades WHERE empresa_id = %s ORDER BY alias_propiedad", (st.session_state.get("empresa_id", 0),))
                    _props_gasto = pd.DataFrame([dict(r) for r in _cupg2.fetchall()])

        _categorias_gasto = [
            "🔨 Reparación / Arreglo",
            "👷 Mano de obra",
            "🧱 Materiales",
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
                _dict_props = {f"Cod: {r['id']} | {r['alias_propiedad']} ({r['propietario'] or 'Sin propietario'})": r['id'] for _, r in _props_gasto.iterrows()}

                # Auto-cargar cotización BNA si no hay una guardada
                if not st.session_state.get("cotizacion_usd_hist") or st.session_state.get("cotizacion_usd_hist", 0) <= 1:
                    _tc_auto_g = _obtener_cotizacion_bna()
                    if _tc_auto_g:
                        st.session_state["cotizacion_usd_hist"] = _tc_auto_g

                _usd_g_reg_col, _usd_g_btn_col, _ = st.columns([2, 1, 2])
                if _usd_g_btn_col.button("🔄 BNA", help="Cotización oficial BNA", use_container_width=True, key="btn_bna_gastos"):
                    _tc_bna_g = _obtener_cotizacion_bna()
                    if _tc_bna_g:
                        st.session_state["cotizacion_usd_hist"] = _tc_bna_g
                        st.rerun()
                    else:
                        st.warning("No se pudo obtener la cotización BNA.")
                _cotizacion_usd_g_reg = _usd_g_reg_col.number_input(
                    "💵 Cotización USD al momento del gasto ($ ARS por 1 USD):",
                    min_value=1.0,
                    value=float(st.session_state.get("cotizacion_usd_hist", 1300.0)),
                    step=10.0,
                    key="cotizacion_usd_gasto_reg_input",
                    help="Este valor se guardará junto al gasto y no cambiará aunque la cotización cambie después"
                )
                st.session_state["cotizacion_usd_hist"] = _cotizacion_usd_g_reg

                # Radio button FUERA del form para que haga rerun al cambiar
                _tipo_gasto = st.radio(
                    "Tipo de gasto:",
                    ["🏠 Individual", "🏢 Compartido (Edificio)"],
                    horizontal=True,
                    key="tipo_gasto_radio_ext"
                )
                _es_compartido = "Compartido" in _tipo_gasto

                with st.form("form_gasto_propiedad", clear_on_submit=True):
                    st.markdown("#### 📝 Datos del Gasto")

                    # ── Tipo de gasto ──
                    if _es_compartido:
                        # Selector de grupo
                        _grupos_disp = []
                        if not _props_gasto.empty and "grupo" in _props_gasto.columns:
                            _grupos_disp = sorted(_props_gasto["grupo"].dropna().unique().tolist())

                        if _grupos_disp:
                            _grupo_sel = st.selectbox(
                                "🏢 Grupo / Edificio:",
                                ["— Seleccionar —"] + _grupos_disp,
                                key="grupo_gasto_sel"
                            )
                        else:
                            _grupo_sel = None
                            st.info("No hay grupos definidos. Asignale un grupo a las propiedades en Auxiliares.")

                        # Propiedades del grupo seleccionado
                        _ids_edif = []
                        if _grupo_sel and _grupo_sel != "— Seleccionar —" and not _props_gasto.empty and "grupo" in _props_gasto.columns:
                            _props_del_grupo = _props_gasto[_props_gasto["grupo"] == _grupo_sel]
                            _ids_edif = _props_del_grupo["id"].tolist()
                            _labels_grupo = _props_del_grupo["alias_propiedad"].tolist()
                            if _ids_edif:
                                st.caption(f"📋 Propiedades del grupo: {', '.join(_labels_grupo)}")

                        _prop_label = None
                        _prop_id_sel = None
                    else:
                        _gcol1, _gcol2 = st.columns(2)
                        _prop_label = _gcol1.selectbox("🏠 Propiedad:", list(_dict_props.keys()))
                        _prop_id_sel = _dict_props[_prop_label]
                        _fecha_gasto = _gcol2.date_input("📅 Fecha del Gasto:", value=datetime.now().date())

                    if _es_compartido:
                        _fecha_gasto = st.date_input("📅 Fecha del Gasto:", value=datetime.now().date())

                    _gcol3, _gcol4 = st.columns(2)
                    _categoria = _gcol3.selectbox("📂 Categoría:", _categorias_gasto)
                    _monto = _gcol4.number_input("💲 Monto Total ($):", min_value=0.0, step=500.0)

                    # Mostrar prorrateo en tiempo real
                    if _es_compartido and _ids_edif and _monto > 0:
                        _monto_por_unidad = _monto / len(_ids_edif)
                        st.info(f"📐 Se distribuirán **$ {_monto_por_unidad:,.2f}** a cada una de las **{len(_ids_edif)} unidades**")

                    _descripcion = st.text_input("📄 Descripción:", placeholder="Ej: Cambio de cañería cocina")

                    _gcol5, _gcol6 = st.columns(2)
                    _proveedor = _gcol5.text_input("🏢 Proveedor / Empresa:", placeholder="Ej: Plomería González")
                    _comprobante = _gcol6.text_input("🧾 N° Comprobante / Factura:", placeholder="Ej: FA-0001-00012345")

                    _gcol7, _gcol8, _gcol9 = st.columns(3)
                    _pagado_por = _gcol7.selectbox("💳 Pagado por:", ["Inmobiliaria", "Propietario", "Inquilino", "Otro"])
                    _tipo_gasto_ord = _gcol8.selectbox("📌 Tipo:", ["Extraordinario", "Ordinario"])
                    _observaciones = _gcol9.text_input("🗒️ Observaciones:", placeholder="Opcional")

                    _btn_gasto = st.form_submit_button("💾 Registrar Gasto", type="primary")

                    if _btn_gasto:
                        if _monto <= 0:
                            st.error("❌ El monto debe ser mayor a cero.")
                        elif not _descripcion.strip():
                            st.error("❌ La descripción es obligatoria.")
                        elif _es_compartido and len(_ids_edif) < 2:
                            st.error("❌ Seleccioná un grupo con al menos 2 propiedades.")
                        else:
                            try:
                                _eid_form = st.session_state.get('empresa_id', 0)
                                _sql_gasto = """INSERT INTO gastos_propiedades
                                    (empresa_id, propiedad_id, fecha, categoria, descripcion, monto,
                                     proveedor, comprobante, pagado_por, observaciones, tipo_gasto, cotizacion_usd)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

                                if _es_compartido:
                                    _monto_unit = round(_monto / len(_ids_edif), 2)
                                    _desc_compartida = f"{_descripcion.strip()} | EDIFICIO-PROPORCIONAL"
                                    with _pg_conn() as _conn_gi:
                                        with _conn_gi.cursor() as _cur_gi:
                                            _tc_gi = float(st.session_state.get("cotizacion_usd_hist", 0.0))
                                            for _pid in _ids_edif:
                                                _cur_gi.execute(_sql_gasto, (
                                                    _eid_form, _pid, _fecha_gasto.strftime("%Y-%m-%d"),
                                                    _categoria, _desc_compartida, _monto_unit,
                                                    _proveedor.strip(), _comprobante.strip(),
                                                    _pagado_por, _observaciones.strip(), _tipo_gasto_ord, _tc_gi
                                                ))
                                    st.success(f"✅ Gasto de $ {_monto:,.2f} distribuido en {len(_ids_edif)} unidades ($ {_monto_unit:,.2f} c/u).")
                                else:
                                    with _pg_conn() as _conn_gi:
                                        with _conn_gi.cursor() as _cur_gi:
                                            _tc_gi = float(st.session_state.get("cotizacion_usd_hist", 0.0))
                                            _cur_gi.execute(_sql_gasto, (
                                                _eid_form, _prop_id_sel, _fecha_gasto.strftime("%Y-%m-%d"),
                                                _categoria, _descripcion.strip(), _monto,
                                                _proveedor.strip(), _comprobante.strip(),
                                                _pagado_por, _observaciones.strip(), _tipo_gasto_ord, _tc_gi
                                            ))
                                    st.success(f"✅ Gasto de $ {_monto:,.2f} registrado en {_prop_label}.")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as _e:
                                st.error(f"Error al guardar: {_e}")

        # ── SUBPESTAÑA 2: HISTORIAL ─────────────────────────────────────
        with subtab_historial:
            _eid_g = st.session_state.get("empresa_id", 0)
            _df_gastos = _cached_gastos_historial(_eid_g, _pf_g if _pf_g_activo else "")

            if _df_gastos.empty:
                st.info("Aún no se registraron gastos.")
            else:
                st.caption("💡 Los valores en USD corresponden a la cotización del momento en que se registró cada gasto.")

                # Filtros
                _hcol1, _hcol2, _hcol3 = st.columns(3)
                _df_gastos["_PROP_LABEL"] = "Cod: " + _df_gastos["COD_PROPIEDAD"].astype(str) + " | " + _df_gastos["PROPIEDAD"]
                _mapa_prop_label = dict(zip(_df_gastos["_PROP_LABEL"], _df_gastos["PROPIEDAD"]))
                _f_prop_label = _hcol1.selectbox("Filtrar por propiedad:", ["Todas"] + sorted(_df_gastos["_PROP_LABEL"].unique()))
                _f_prop = _mapa_prop_label.get(_f_prop_label, "Todas") if _f_prop_label != "Todas" else "Todas"
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
                    "PROPIEDAD", "PROPIETARIO", "FECHA", "CATEGORÍA", "TIPO", "DESCRIPCIÓN",
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

            # ── Cargar ingresos desde pagos_historial (incluyendo expensas) ──
            _eid_m = st.session_state.get("empresa_id", 0)

            _df_ingresos_raw = _cached_metricas_ingresos(_eid_m, _pf_g if _pf_g_activo else "").copy()
            # Convertir columnas NUMERIC (Decimal) a float para evitar TypeError
            if not _df_ingresos_raw.empty:
                for _col in ['alquiler','cochera','expensas','total_ingreso','imp_inmobiliario','alquiler_usd','cochera_usd','total_ingreso_usd','gasto_admin_usd','imp_inmobiliario_usd']:
                    if _col in _df_ingresos_raw.columns:
                        _df_ingresos_raw[_col] = pd.to_numeric(_df_ingresos_raw[_col], errors='coerce').fillna(0.0)

            # ── Calcular mes calendario desde el período del contrato ──
            # periodo tiene formato "Mes N de M" (ej. "Mes 1 de 12")
            # mes_calendario = inicio_contrato + (N-1) meses → YYYY-MM
            _df_ingresos_raw = _agregar_mes_calendario(_df_ingresos_raw)

            # ── Cargar gastos desde gastos_propiedades ──
            _df_gastos_raw = _cached_metricas_gastos(_eid_m, _pf_g if _pf_g_activo else "")

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

                # Dropdown "Propiedad" — incluye también los grupos/edificios como opciones,
                # para no tener que cambiar de vista para filtrar por edificio.
                _opciones_prop_m = {"Todas": (None, None)}
                if not _props_gasto.empty and "grupo" in _props_gasto.columns:
                    _grupos_disp_m = sorted({
                        str(g).strip() for g in _props_gasto["grupo"].dropna().tolist() if str(g).strip()
                    })
                    for _g in _grupos_disp_m:
                        _opciones_prop_m[f"🏢 {_g} (grupo/edificio)"] = ("grupo", _g)
                if not _props_gasto.empty:
                    for _, _r_p in _props_gasto.sort_values("alias_propiedad").iterrows():
                        _opciones_prop_m[f"🏠 Cod: {_r_p['id']} | {_r_p['alias_propiedad']}"] = ("propiedad", _r_p['alias_propiedad'])

                _f_prop_m_label = _mcol1.selectbox("🏠 Propiedad:", list(_opciones_prop_m.keys()), key="met_prop")
                _f_prop_m_tipo, _f_prop_m_valor = _opciones_prop_m[_f_prop_m_label]

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
                    if _f_prop_m_tipo == "grupo":
                        _dfi = _dfi[_dfi["grupo"] == _f_prop_m_valor]
                        # Reemplazar propiedad por grupo para el agrupamiento de la tabla/gráfico
                        _dfi = _dfi.copy()
                        _dfi["propiedad"] = _dfi["grupo"].fillna("Sin grupo")
                    elif _f_prop_m_tipo == "propiedad":
                        _dfi = _dfi[_dfi["propiedad"] == _f_prop_m_valor]
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
                    if _f_prop_m_tipo == "grupo":
                        _dfg = _dfg[_dfg["grupo"] == _f_prop_m_valor]
                        _dfg = _dfg.copy()
                        _dfg["propiedad"] = _dfg["grupo"].fillna("Sin grupo")
                    elif _f_prop_m_tipo == "propiedad":
                        _dfg = _dfg[_dfg["propiedad"] == _f_prop_m_valor]
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
                _total_exp     = _dfi["expensas"].sum()         if not _dfi.empty else 0.0
                _total_gas     = _dfg["total_gasto"].sum()      if not _dfg.empty else 0.0
                _total_adm     = _dfi["gasto_admin"].sum()      if not _dfi.empty else 0.0
                _total_imp_inm = _dfi["imp_inmobiliario"].sum() if not _dfi.empty else 0.0
                _total_pasivos = _total_gas + _total_adm + _total_imp_inm
                _balance       = _total_ing - _total_pasivos

                # ── Totales en USD (desde BD) ──
                _total_ing_usd     = float(_dfi["total_ingreso_usd"].sum())    if not _dfi.empty else 0.0
                _total_alq_usd     = float(_dfi["alquiler_usd"].sum())         if not _dfi.empty else 0.0
                _total_coch_usd    = _dfi["cochera_usd"].sum()          if not _dfi.empty else 0.0
                _total_exp_usd     = float(_dfi["expensas_usd"].sum())         if not _dfi.empty else 0.0
                _total_gas_usd     = float(_dfg["total_gasto_usd"].sum())      if not _dfg.empty else 0.0
                _total_adm_usd     = float(_dfi["gasto_admin_usd"].sum())      if not _dfi.empty else 0.0
                _total_imp_inm_usd = float(_dfi["imp_inmobiliario_usd"].sum()) if not _dfi.empty else 0.0
                _total_pasivos_usd = _total_gas_usd + _total_adm_usd + _total_imp_inm_usd
                _balance_usd       = _total_ing_usd - _total_pasivos_usd

                # ── KPIs según moneda seleccionada ──
                if not _ver_usd:
                    # ── KPIs en PESOS ──
                    st.markdown("**📥 Ingresos — $**")
                    _km1, _km2, _km3 = st.columns(3)
                    _km1.metric("💰 Total Ingresos",  f"$ {_total_ing:,.2f}", help="Alquiler + Cochera + Expensas del período filtrado")
                    _km2.metric("🏠 Alquiler",        f"$ {_total_alq:,.2f}")
                    _km3.metric("🚗 Cochera",         f"$ {_total_coch:,.2f}")
                    _km4, _km5 = st.columns(2)
                    _km4.metric("🏘️ Expensas cobradas", f"$ {_total_exp:,.2f}")

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
                    _ku1.metric("💰 Total Ingresos",  f"U$S {_total_ing_usd:,.2f}", help="Alquiler + Cochera + Expensas en USD al tipo de cambio de cada cobro")
                    _ku2.metric("🏠 Alquiler",        f"U$S {_total_alq_usd:,.2f}")
                    _ku3.metric("🚗 Cochera",         f"U$S {_total_coch_usd:,.2f}")
                    _ku4, _ku5 = st.columns(2)
                    _ku4.metric("🏘️ Expensas cobradas", f"U$S {_total_exp_usd:,.2f}")

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
                        expensas=("expensas", "sum"),
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
                                               "alquiler", "cochera", "expensas", "total_ingreso",
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

# =====================================================================
# PESTAÑA: RENDICIÓN A PROPIETARIOS
# =====================================================================
if tab_rendicion:
    with tab_rendicion:
        st.markdown("#### 📑 Rendición a Propietarios")
        st.caption("Lo cobrado por propiedad, con la comisión administrativa ya descontada — listo para mostrarle al propietario.")

        _eid_rend = st.session_state.get("empresa_id", 0)
        _pf_rend = st.session_state.get("propietario_filtro", "")
        _pf_rend_activo = rol_actual == "propietario" and bool(_pf_rend)

        _df_rend_base = _cached_metricas_ingresos(_eid_rend, _pf_rend if _pf_rend_activo else "").copy()

        if _df_rend_base.empty:
            st.info("Todavía no hay cobros registrados para generar una rendición.")
        else:
            for _col_rend in ["alquiler", "cochera", "expensas", "gasto_admin",
                               "imp_inmobiliario", "edesal", "gas", "municipalidad",
                               "ooss", "honorarios", "garantia", "concepto_extra", "abonado"]:
                _df_rend_base[_col_rend] = pd.to_numeric(_df_rend_base[_col_rend], errors="coerce").fillna(0.0)

            _df_rend_base = _agregar_mes_calendario(_df_rend_base)

            _rc1, _rc2 = st.columns(2)
            if not _pf_rend_activo:
                _propietarios_rend = sorted({str(p).strip() for p in _df_rend_base["propietario"].dropna().tolist() if str(p).strip()})
                _propietario_sel_rend = _rc1.selectbox("👤 Propietario:", ["Todos"] + _propietarios_rend, key="rend_propietario")
            else:
                _propietario_sel_rend = _pf_rend
                _rc1.markdown(f"**👤 Propietario:**  \n{_pf_rend}")

            _periodos_rend = sorted({p for p in _df_rend_base["mes_calendario"].dropna().tolist() if str(p).strip()}, reverse=True)
            _idx_periodo_default = 1 if _periodos_rend else 0
            _periodo_sel_rend = _rc2.selectbox("📅 Período (mes calendario):", ["Todos"] + _periodos_rend, index=_idx_periodo_default, key="rend_periodo")

            # El PDF solo se habilita después de registrar la liquidación, y se vuelve
            # a deshabilitar si cambia el propietario o el período (mismo criterio que
            # en Emitir Recibo con "pago_impactado").
            if "liquidacion_registrada" not in st.session_state:
                st.session_state.liquidacion_registrada = False
            if "liquidacion_clave_registrada" not in st.session_state:
                st.session_state.liquidacion_clave_registrada = None

            _clave_filtro_rend = f"{_propietario_sel_rend}|{_periodo_sel_rend}"
            if st.session_state.get("_ultima_clave_filtro_rend") != _clave_filtro_rend:
                st.session_state["_ultima_clave_filtro_rend"] = _clave_filtro_rend
                st.session_state.liquidacion_registrada = False
                st.session_state.liquidacion_clave_registrada = None

            _df_rend = _df_rend_base.copy()
            if _propietario_sel_rend != "Todos":
                _df_rend = _df_rend[_df_rend["propietario"] == _propietario_sel_rend]
            if _periodo_sel_rend != "Todos":
                _df_rend = _df_rend[_df_rend["mes_calendario"] == _periodo_sel_rend]

            if _df_rend.empty:
                st.warning("No hay cobros para ese propietario/período.")
            else:
                _agrupado = _df_rend.groupby("propiedad", as_index=False).agg(
                    ALQUILER=("alquiler", "sum"),
                    COCHERA=("cochera", "sum"),
                    EXPENSAS=("expensas", "sum"),
                    COMISION=("gasto_admin", "sum"),
                ).sort_values("propiedad")
                _agrupado["TOTAL COBRADO"] = _agrupado["ALQUILER"] + _agrupado["COCHERA"] + _agrupado["EXPENSAS"]
                _agrupado["NETO A RENDIR"] = _agrupado["TOTAL COBRADO"] - _agrupado["COMISION"]

                _tot_alq      = float(_agrupado["ALQUILER"].sum())
                _tot_coch     = float(_agrupado["COCHERA"].sum())
                _tot_exp      = float(_agrupado["EXPENSAS"].sum())
                _tot_cobrado  = float(_agrupado["TOTAL COBRADO"].sum())
                _tot_comision = float(_agrupado["COMISION"].sum())
                _tot_neto     = float(_agrupado["NETO A RENDIR"].sum())

                # Informativos (NO se descuentan del Neto a Rendir):
                # "Servicios" = Imp. Inmobiliario + EDESAL + Gas + Municipalidad + OO.SS.
                # "Otros" = ítems restantes que entran en el cálculo de la comisión inmobiliaria
                #           (Honorarios + Garantía + Concepto adicional libre del recibo).
                _tot_servicios = float(
                    _df_rend["imp_inmobiliario"].sum() + _df_rend["edesal"].sum()
                    + _df_rend["gas"].sum() + _df_rend["municipalidad"].sum() + _df_rend["ooss"].sum()
                )
                _tot_otros = float(
                    _df_rend["honorarios"].sum() + _df_rend["garantia"].sum() + _df_rend["concepto_extra"].sum()
                )

                st.markdown(f"**{len(_agrupado)} propiedad(es)** — Propietario: **{_propietario_sel_rend}** — Período: **{_periodo_sel_rend}**")

                _km1, _km2, _km3, _km4 = st.columns(4)
                _km1.metric("💰 Total Cobrado",     f"$ {_tot_cobrado:,.2f}")
                _km2.metric("🏢 Comisión Adm. (–)", f"$ {_tot_comision:,.2f}")
                _km3.metric("📤 Neto a Rendir",     f"$ {_tot_neto:,.2f}")
                _km4.metric("🏠 Propiedades",       f"{len(_agrupado)}")

                st.caption("Informativo — no forman parte del Neto a Rendir del propietario:")
                _km5, _km6 = st.columns(2)
                _km5.metric("🔧 Servicios", f"$ {_tot_servicios:,.2f}",
                            help="Imp. Inmobiliario + EDESAL + Gas + Municipalidad + OO.SS.")
                _km6.metric("📦 Otros", f"$ {_tot_otros:,.2f}",
                            help="Honorarios + Garantía + Concepto adicional libre (ítems restantes del cálculo de la comisión inmobiliaria)")

                _disp = _agrupado.rename(columns={
                    "propiedad": "PROPIEDAD",
                    "COMISION": "COMISIÓN ADM. (–)",
                })[["PROPIEDAD", "ALQUILER", "COCHERA", "EXPENSAS", "TOTAL COBRADO", "COMISIÓN ADM. (–)", "NETO A RENDIR"]]

                _disp_fmt = _disp.copy()
                for _col_fmt in ["ALQUILER", "COCHERA", "EXPENSAS", "TOTAL COBRADO", "COMISIÓN ADM. (–)", "NETO A RENDIR"]:
                    _disp_fmt[_col_fmt] = _disp_fmt[_col_fmt].apply(lambda x: f"$ {x:,.2f}")

                st.dataframe(_disp_fmt, use_container_width=True, hide_index=True)

                st.markdown(
                    f"**TOTALES**  —  Alquiler: \\$ {_tot_alq:,.2f}  |  Cochera: \\$ {_tot_coch:,.2f}  |  "
                    f"Expensas: \\$ {_tot_exp:,.2f}  |  Total Cobrado: \\$ {_tot_cobrado:,.2f}  |  "
                    f"Comisión Adm.: \\$ {_tot_comision:,.2f}  |  **Neto a Rendir: \\$ {_tot_neto:,.2f}**"
                )

                # ── Detalle por recibo: incluye los demás ítems cobrados al inquilino ──
                # (Imp. Inmobiliario, EDESAL, Gas, Municipalidad, OO.SS., Honorarios, Garantía).
                # Son montos que pasan por el recibo pero NO se descuentan del "Neto a
                # Rendir" del propietario — se muestran solo a modo informativo/trazabilidad.
                st.markdown("---")
                st.markdown("#### 📋 Detalle de Recibos Incluidos")
                st.caption("Cada fila es un recibo emitido. Incluye, a modo informativo, los demás conceptos cobrados al inquilino que no forman parte del neto del propietario.")

                _detalle_rend = _df_rend.copy().sort_values(["propiedad", "periodo"])
                _detalle_rend["NETO"] = (
                    _detalle_rend["alquiler"] + _detalle_rend["cochera"] + _detalle_rend["expensas"]
                    - _detalle_rend["gasto_admin"]
                )
                _detalle_rend = _detalle_rend.rename(columns={
                    "fecha": "FECHA", "propiedad": "PROPIEDAD", "inquilino": "INQUILINO",
                    "periodo": "PERÍODO", "alquiler": "ALQUILER", "cochera": "COCHERA",
                    "expensas": "EXPENSAS", "gasto_admin": "COMISIÓN (–)",
                    "imp_inmobiliario": "IMP. INMOBILIARIO", "edesal": "LUZ (EDESAL)",
                    "gas": "GAS", "municipalidad": "MUNICIPALIDAD", "ooss": "OO.SS.",
                    "honorarios": "HONORARIOS", "garantia": "GARANTÍA",
                    "concepto_extra": "CONCEPTO EXTRA", "concepto_extra_desc": "DESCRIPCIÓN EXTRA",
                })
                _cols_detalle = ["FECHA", "PROPIEDAD", "INQUILINO", "PERÍODO",
                                  "ALQUILER", "COCHERA", "EXPENSAS", "COMISIÓN (–)", "NETO",
                                  "IMP. INMOBILIARIO", "LUZ (EDESAL)", "GAS", "MUNICIPALIDAD",
                                  "OO.SS.", "HONORARIOS", "GARANTÍA", "CONCEPTO EXTRA", "DESCRIPCIÓN EXTRA"]
                _detalle_rend = _detalle_rend[_cols_detalle]

                _detalle_fmt = _detalle_rend.copy()
                for _col_money in ["ALQUILER", "COCHERA", "EXPENSAS", "COMISIÓN (–)", "NETO",
                                    "IMP. INMOBILIARIO", "LUZ (EDESAL)", "GAS", "MUNICIPALIDAD",
                                    "OO.SS.", "HONORARIOS", "GARANTÍA", "CONCEPTO EXTRA"]:
                    _detalle_fmt[_col_money] = _detalle_fmt[_col_money].apply(lambda x: f"$ {x:,.2f}")

                st.dataframe(_detalle_fmt, use_container_width=True, hide_index=True)

                _csv_rend = _disp.to_csv(index=False).encode("utf-8-sig")
                _nombre_prop_csv = str(_propietario_sel_rend).replace(" ", "_").replace(",", "")
                _nombre_csv_rend = f"rendicion_{_nombre_prop_csv}_{_periodo_sel_rend}.csv"
                st.download_button(
                    "⬇️ Descargar CSV",
                    data=_csv_rend,
                    file_name=_nombre_csv_rend,
                    mime="text/csv",
                )

                # ── Liquidación: monto editable + saldo pendiente + PDF ──
                st.markdown("---")
                st.markdown("#### 💵 Liquidación")

                if _propietario_sel_rend == "Todos" or _periodo_sel_rend == "Todos":
                    st.info("Elegí un **propietario** y un **período** específicos (no \"Todos\") para registrar la liquidación y generar el PDF.")
                else:
                    _liq_existente = _obtener_liquidacion_existente(_eid_rend, _propietario_sel_rend, _periodo_sel_rend)
                    _saldo_anterior = _obtener_saldo_anterior_propietario(_eid_rend, _propietario_sel_rend, _periodo_sel_rend)

                    # ── Retención por gastos extraordinarios no pagados por el propietario ──
                    _gastos_retencion = _obtener_gastos_retencion_pendientes(_eid_rend, _propietario_sel_rend)
                    _tot_retencion_gastos = float(sum(float(g["monto"] or 0) for g in _gastos_retencion))

                    _monto_a_liquidar = _tot_neto + _saldo_anterior - _tot_retencion_gastos

                    if _liq_existente:
                        st.caption(f"ℹ️ Ya hay una liquidación registrada para este período (el {_liq_existente.get('fecha_liquidacion','')}) — podés corregirla y volver a guardar.")

                    if _gastos_retencion:
                        st.warning(f"🧾 **{len(_gastos_retencion)} gasto(s) extraordinario(s)** pagados por la inmobiliaria/inquilino/otro, pendientes de retener: **$ {_tot_retencion_gastos:,.2f}**")
                        _df_retencion = pd.DataFrame(_gastos_retencion).rename(columns={
                            "propiedad": "PROPIEDAD", "fecha": "FECHA", "categoria": "CATEGORÍA",
                            "descripcion": "DESCRIPCIÓN", "pagado_por": "PAGADO POR", "monto": "MONTO ($)",
                        })[["FECHA", "PROPIEDAD", "CATEGORÍA", "DESCRIPCIÓN", "PAGADO POR", "MONTO ($)"]]
                        _df_retencion["MONTO ($)"] = _df_retencion["MONTO ($)"].apply(lambda x: f"$ {float(x):,.2f}")
                        st.dataframe(_df_retencion, use_container_width=True, hide_index=True)

                    _lc1, _lc2, _lc3 = st.columns(3)
                    _lc1.metric("↩️ Saldo Pendiente Anterior", f"$ {_saldo_anterior:,.2f}")
                    _lc2.metric("🧾 Retención por Gastos (–)", f"$ {_tot_retencion_gastos:,.2f}",
                                help="Gastos Extraordinarios pagados por la Inmobiliaria/Inquilino/Otro, pendientes de descontar al propietario.")
                    _lc3.metric("💵 Monto Total a Liquidar", f"$ {_monto_a_liquidar:,.2f}",
                                help="Neto a Rendir + saldo pendiente de períodos anteriores − retención por gastos")

                    _key_monto_liq = f"monto_liquidado_{_eid_rend}_{_propietario_sel_rend}_{_periodo_sel_rend}"
                    if _key_monto_liq not in st.session_state:
                        st.session_state[_key_monto_liq] = float(_liq_existente["monto_liquidado"]) if _liq_existente else max(0.0, _monto_a_liquidar)

                    monto_liquidado_input = st.number_input(
                        "✏️ Monto Liquidado al Propietario ($):",
                        min_value=0.0, step=1000.0, key=_key_monto_liq,
                        help="Lo que efectivamente se le paga al propietario. Si es distinto al 'Monto Total a Liquidar', la diferencia queda como saldo pendiente para el próximo período."
                    )

                    _saldo_pendiente_nuevo = _monto_a_liquidar - monto_liquidado_input

                    if abs(_saldo_pendiente_nuevo) > 0.01:
                        if _saldo_pendiente_nuevo > 0:
                            st.warning(f"⚠️ Queda un **saldo pendiente a favor del propietario** de $ {_saldo_pendiente_nuevo:,.2f}, que se arrastra al próximo período.")
                        else:
                            st.warning(f"⚠️ Se liquidó **$ {abs(_saldo_pendiente_nuevo):,.2f} de más** — queda a favor de la inmobiliaria para el próximo período.")
                    else:
                        st.success("✅ El monto liquidado coincide con lo que corresponde. Sin saldo pendiente.")

                    _lb1, _lb2 = st.columns(2)
                    if _lb1.button("💾 Registrar Liquidación", type="primary", use_container_width=True, key="btn_guardar_liquidacion"):
                        try:
                            with _pg_conn() as _conn_liq:
                                with _conn_liq.cursor() as _cur_liq:
                                    _cur_liq.execute("""
                                        INSERT INTO liquidaciones_propietarios
                                            (empresa_id, propietario, periodo, monto_calculado, saldo_anterior,
                                             monto_retencion_gastos, monto_a_liquidar, monto_liquidado,
                                             saldo_pendiente, fecha_liquidacion, registrado_por)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (empresa_id, propietario, periodo) DO UPDATE SET
                                            monto_calculado        = EXCLUDED.monto_calculado,
                                            saldo_anterior          = EXCLUDED.saldo_anterior,
                                            monto_retencion_gastos  = EXCLUDED.monto_retencion_gastos,
                                            monto_a_liquidar        = EXCLUDED.monto_a_liquidar,
                                            monto_liquidado         = EXCLUDED.monto_liquidado,
                                            saldo_pendiente         = EXCLUDED.saldo_pendiente,
                                            fecha_liquidacion       = EXCLUDED.fecha_liquidacion,
                                            registrado_por          = EXCLUDED.registrado_por
                                    """, (
                                        _eid_rend, _propietario_sel_rend, _periodo_sel_rend, _tot_neto, _saldo_anterior,
                                        _tot_retencion_gastos, _monto_a_liquidar, monto_liquidado_input, _saldo_pendiente_nuevo,
                                        datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state.get("username", "")
                                    ))
                            _marcar_gastos_como_cobrados(_eid_rend, [g["id"] for g in _gastos_retencion], _periodo_sel_rend)
                            st.cache_data.clear()
                            st.session_state.liquidacion_registrada = True
                            st.session_state.liquidacion_clave_registrada = _clave_filtro_rend
                            st.success("✅ Liquidación registrada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al registrar la liquidación: {e}")

                    _pdf_habilitado = (
                        st.session_state.liquidacion_registrada
                        and st.session_state.liquidacion_clave_registrada == _clave_filtro_rend
                    )
                    if _pdf_habilitado:
                        _filas_pdf_rend = [{
                            "propiedad": _r["propiedad"],
                            "alquiler":  float(_r["ALQUILER"]),
                            "cochera":   float(_r["COCHERA"]),
                            "expensas":  float(_r["EXPENSAS"]),
                            "comision":  float(_r["COMISION"]),
                            "neto":      float(_r["NETO A RENDIR"]),
                        } for _, _r in _agrupado.iterrows()]

                        _filas_detalle_pdf = [{
                            "fecha":             _r["FECHA"],
                            "propiedad":         _r["PROPIEDAD"],
                            "periodo":           _r["PERÍODO"],
                            "alquiler":          float(_r["ALQUILER"]),
                            "cochera":           float(_r["COCHERA"]),
                            "expensas":          float(_r["EXPENSAS"]),
                            "comision":          float(_r["COMISIÓN (–)"]),
                            "neto":              float(_r["NETO"]),
                            "imp_inmobiliario":  float(_r["IMP. INMOBILIARIO"]),
                            "edesal":            float(_r["LUZ (EDESAL)"]),
                            "gas":               float(_r["GAS"]),
                            "municipalidad":     float(_r["MUNICIPALIDAD"]),
                            "ooss":              float(_r["OO.SS."]),
                            "honorarios":        float(_r["HONORARIOS"]),
                            "garantia":          float(_r["GARANTÍA"]),
                        } for _, _r in _detalle_rend.iterrows()]

                        _pdf_rend_bytes = generar_pdf_rendicion(
                            propietario=_propietario_sel_rend,
                            periodo=_periodo_sel_rend,
                            fecha_emision=datetime.now().strftime("%d/%m/%Y"),
                            nombre_empresa=st.session_state.get("nombre_empresa", "Mi Empresa"),
                            filas_propiedades=_filas_pdf_rend,
                            total_alquiler=_tot_alq, total_cochera=_tot_coch, total_expensas=_tot_exp,
                            total_cobrado=_tot_cobrado, total_comision=_tot_comision, total_neto=_tot_neto,
                            saldo_anterior=_saldo_anterior, monto_a_liquidar=_monto_a_liquidar,
                            monto_liquidado=monto_liquidado_input, saldo_pendiente=_saldo_pendiente_nuevo,
                            filas_detalle_recibos=_filas_detalle_pdf,
                            total_servicios=_tot_servicios, total_otros=_tot_otros,
                            filas_retencion_gastos=_gastos_retencion, total_retencion_gastos=_tot_retencion_gastos,
                        )
                        _lb2.download_button(
                            "📄 Descargar PDF de Rendición",
                            data=_pdf_rend_bytes,
                            file_name=f"rendicion_{_nombre_prop_csv}_{_periodo_sel_rend}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    else:
                        _lb2.button(
                            "📄 Descargar PDF de Rendición",
                            disabled=True,
                            use_container_width=True,
                            help="Primero registrá la liquidación con el botón de la izquierda.",
                        )

# =====================================================================
# PESTAÑA: TÉRMINOS Y CONDICIONES
# =====================================================================
if _pestana_activa == "terminos":
    st.subheader("📄 Términos y Condiciones de Uso")
    _username_tc_view = st.session_state.get("usuario_actual", "")
    try:
        with _pg_conn() as _conn_tcv:
            with _conn_tcv.cursor() as _cur_tcv:
                _cur_tcv.execute(
                    "SELECT terminos_aceptados, terminos_fecha FROM usuarios_central WHERE username = %s",
                    (_username_tc_view,)
                )
                _row_tcv = _cur_tcv.fetchone()
        if _row_tcv and _row_tcv["terminos_aceptados"]:
            st.success(f"✅ Términos aceptados el {_row_tcv['terminos_fecha']}")
        else:
            st.warning("⚠️ Términos pendientes de aceptación.")
    except Exception:
        pass

    st.markdown(globals().get("TERMINOS_TEXTO", "*(Texto de términos no disponible)*"))
