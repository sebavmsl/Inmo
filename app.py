import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import dateutil.relativedelta
import re

# =====================================================================
# 1. BASE DE DATOS: CONFIGURACIÓN RELACIONAL (CAMPOS SEPARADOS)
# =====================================================================
def conectar_db():
    return sqlite3.connect('sistema_alquileres_v3.db')

def inicializar_tablas():
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Activar el soporte para Claves Foráneas de forma explícita en SQLite
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Tabla 1: INQUILINOS (Apellidos y Nombres separados)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inquilinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        apellidos TEXT NOT NULL,
        nombres TEXT NOT NULL,
        dni TEXT,             -- Cambiado de dni_cuit a dni
        telefono TEXT,
        email TEXT,            -- <--- NUEVA COLUMNA AGREGADA
        UNIQUE(apellidos, nombres)
    )
''')
    
    # Tabla 2: PROPIEDADES (Dirección detallada y separada)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS propiedades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias_propiedad TEXT NOT NULL UNIQUE,
            calle TEXT NOT NULL,
            numero TEXT NOT NULL,
            departamento TEXT -- Puede quedar vacío si es una casa
        )
    ''')
    
    # Tabla 3: CONTRATOS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contratos (
            codigo INTEGER PRIMARY KEY AUTOINCREMENT,
            propiedad_id INTEGER NOT NULL,
            inquilino_id INTEGER NOT NULL,
            estado TEXT NOT NULL,
            inicio_contrato DATE NOT NULL,
            fin_contrato DATE NOT NULL,
            calc_duracion INTEGER,
            act_contrato TEXT,
            indice TEXT,
            monto_inicial REAL,
            alquiler REAL,
            prox_actualizacion DATE,
            mes_contrato INTEGER,
            mes_actualizacion_contrato INTEGER,
            services TEXT,
            honorarios REAL,
            monto_honorarios REAL,
            cuota_honorarios INTEGER,
            honorarios_pagados REAL,
            tipo_de_garantie TEXT,
            monto_garantia REAL,
            garantia TEXT,
            imp_inmobiliario REAL,
            expensas REAL,
            edesal REAL,
            gas REAL,
            municipalidad REAL,
            ooss REAL,
            servicios_total REAL,
            cochera REAL,
            alquiler_cobrado REAL,
            total_pagado REAL,
            FOREIGN KEY (propiedad_id) REFERENCES propiedades(id),
            FOREIGN KEY (inquilino_id) REFERENCES inquilinos(id)
        )
    ''')
    conn.commit()
    conn.close()

# Ejecutamos la inicialización al arrancar la app
inicializar_tablas()

# =====================================================================
# FUNCIONES AUXILIARES DE LÓGICA
# =====================================================================
def obtener_datos_desplegables():
    conn = conectar_db()
    
    propiedades = pd.read_sql_query('''
        SELECT id, alias_propiedad, calle, numero, departamento 
        FROM propiedades
    ''', conn)
    
    inquilinos = pd.read_sql_query("SELECT id, apellidos, nombres FROM inquilinos", conn)
    conn.close()
    
    dict_propiedades = {}
    for _, row in propiedades.iterrows():
        dir_completa = f"{row['calle']} {row['numero']}"
        if row['departamento'] and row['departamento'].strip():
            dir_completa += f", Depto: {row['departamento']}"
        dict_propiedades[f"{row['alias_propiedad']} ({dir_completa})"] = row['id']
        
    dict_inquilinos = {f"{row['apellidos']}, {row['nombres']}": row['id'] for _, row in inquilinos.iterrows()}
    
    return dict_propiedades, dict_inquilinos


def obtener_contratos_activos_completos():
    """Consulta y retorna un diccionario con los datos específicos de contratos activos."""
    conn = conectar_db()
    query = '''
        SELECT 
            c.codigo, 
            p.alias_propiedad, 
            (p.calle || ' ' || p.numero || CASE WHEN p.departamento <> '' AND p.departamento IS NOT NULL THEN ', Dto: ' || p.departamento ELSE '' END) AS propiedad_dir,
            i.apellidos, 
            i.nombres, 
            c.prox_actualizacion, 
            c.alquiler, 
            c.indice,
            c.act_contrato,
            c.calc_duracion,
            c.mes_contrato,
            c.mes_actualizacion_contrato,
            c.monto_honorarios, 
            c.honorarios_pagados,
            c.monto_garantia, 
            c.garantia,
            c.imp_inmobiliario, 
            c.expensas, 
            c.edesal, 
            c.gas, 
            c.municipalidad, 
            c.ooss, 
            c.cochera,
            c.servicios_total,
            c.inicio_contrato
        FROM contratos c
        JOIN propiedades p ON c.propiedad_id = p.id
        JOIN inquilinos i ON c.inquilino_id = i.id
        WHERE c.estado = 'Activo'
        ORDER BY c.codigo DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    dict_contratos = {}
    for _, row in df.iterrows():
        label = f"Cod: {row['codigo']} | {row['alias_propiedad']} - Inquilino: {row['apellidos']}, {row['nombres']}"
        dict_contratos[label] = row.to_dict()
    return dict_contratos


# =====================================================================
# 2. INTERFAZ DE USUARIO CONFIGURACIÓN GENERAL (Streamlit)
# =====================================================================
st.set_page_config(page_title="Gestión de Alquileres Relacional", layout="wide")
st.title("🏢 Sistema Integral de Gestión de Alquileres")
st.caption("Entorno web avanzado con base de datos SQLite relacional y campos de dirección atomizados.")

# Definición de pestañas de navegación
tab_planilla, tab_pagos, tab_carga, tab_auxiliares = st.tabs([
    "📊 Planilla General", 
    "💰 Registrar / Ver Pagos",
    "📝 Carga de Contratos", 
    "⚙️ Cargar Inquilinos / Propiedades"
])

# =====================================================================
# PESTAÑA 1: VISUALIZACIÓN DE PLANILLA (RESULTADOS CON JOIN)
# =====================================================================
with tab_planilla:
    st.subheader("Historial y Estado de Contratos")
    
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        busqueda = st.text_input("🔍 Buscar por Inquilino, Calle, Alias, etc:", placeholder="Ej: Pérez, Mitre o Depto 3A")
    with col_f2:
        filtro_estado = st.multiselect("Filtrar por Estado:", ["Activo", "Vencido", "Inhabitado"], default=["Activo"])
    
    conn = conectar_db()
    try:
        query = '''
            SELECT 
                c.codigo AS [CÓDIGO],
                p.alias_propiedad AS [ALIAS PROPIEDAD],
                (i.apellidos || ', ' || i.nombres) AS [INQUILINO],
                (p.calle || ' ' || p.numero || CASE WHEN p.departamento <> '' AND p.departamento IS NOT NULL THEN ', Dto: ' || p.departamento ELSE '' END) AS [PROPIEDAD],
                c.estado AS [ESTADO],
                c.inicio_contrato AS [INICIO_CONTRATO],
                c.fin_contrato AS [FIN_CONTRATO],
                c.calc_duracion AS [CALC_DURACION],
                c.alquiler AS [ALQUILER],
                c.servicios_total AS [SERVICIOS_TOTAL],
                c.alquiler_cobrado AS [ALQUILER_COBRADO],
                c.total_pagado AS [TOTAL_PAGADO],
                c.monto_honorarios AS [MONTO_HONORARIOS],
                c.honorarios_pagados AS [HONORARIOS_PAGADOS]
            FROM contratos c
            JOIN propiedades p ON c.propiedad_id = p.id
            JOIN inquilinos i ON c.inquilino_id = i.id
            ORDER BY c.codigo DESC
        '''
        df = pd.read_sql_query(query, conn)
        
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
            
            st.markdown("---")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Contratos Listados", len(df))
            m2.metric("Total Cobrado Alquileres", f"$ {df['ALQUILER_COBRADO'].sum():,.2f}")
            m3.metric("Honorarios Restantes por Cobrar", f"$ {(df['MONTO_HONORARIOS'].sum() - df['HONORARIOS_PAGADOS'].sum()):,.2f}")
            m4.metric("Total Gastos Servicios", f"$ {df['SERVICIOS_TOTAL'].sum():,.2f}")
        else:
            st.info("No se registran contratos en la base de datos bajo los criterios de búsqueda.")
    except Exception as e:
        st.error(f"Error de lectura en la planilla general: {e}")
    finally:
        conn.close()


# =====================================================================
# FUNCIÓN AUXILIAR: TRADUCTOR DE TEXTO A NÚMERO (SOPORTA PUNTOS EN MILES)
# =====================================================================
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


# =====================================================================
# PESTAÑA 2: CONTROL Y VERIFICACIÓN DE DATOS DE PAGO
# =====================================================================
with tab_pagos:
    st.subheader("💰 Panel de Control de Cobranzas e Información de Contrato")
    
    dict_activos = obtener_contratos_activos_completos()
    
    if not dict_activos:
        st.info("No se registran contratos en estado 'Activo' en este momento.")
    else:
        contrato_seleccionado = st.selectbox(
            "Seleccione el Contrato Activo a consultar:", 
            options=list(dict_activos.keys())
        )
        
        c_datos = dict_activos[contrato_seleccionado]
        
        # Extracción y parsing de valores
        alquiler_base = float(c_datos['alquiler']) if c_datos['alquiler'] is not None else 0.0
        indice_f = str(c_datos['indice']).lower()
        
        opciones_meses = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24}
        frecuencia_txt = c_datos['act_contrato'] if c_datos['act_contrato'] in opciones_meses else "Semestral"
        meses_intervalo = opciones_meses[frecuencia_txt]
        
        # El valor actualizado toma por defecto el último valor cobrado
        valor_actualizado_fmt = f"{round(alquiler_base, 2):,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
        
        # Generación de la URL para arquiler.com
        try:
            inicio_dt = datetime.strptime(c_datos['inicio_contrato'], "%d/%m/%Y")
            fecha_param = inicio_dt.strftime("%Y-%m-%d")
        except:
            fecha_param = datetime.now().strftime("%Y-%m-%d")
            
        url_arquiler = f"https://arquiler.com/pwa?amount={int(alquiler_base)}&date={fecha_param}&months={meses_intervalo}&rate={indice_f}"
        
        # Filtrado estricto en vivo de los servicios que se guardaron a cargo del Inquilino
        servicios_inquilino_list = []
        if c_datos['imp_inmobiliario'] and "[Imp.Inmob: Inquilino]" in str(c_datos['servicios']):
            servicios_inquilino_list.append(f"Impuesto Inmobiliario: $ {c_datos['imp_inmobiliario']:,.2f}")
        if c_datos['expensas'] and c_datos['expensas'] > 0:
            servicios_inquilino_list.append(f"Expensas: $ {c_datos['expensas']:,.2f}")
        if c_datos['edesal'] and c_datos['edesal'] > 0:
            servicios_inquilino_list.append(f"EDESAL (Luz): $ {c_datos['edesal']:,.2f}")
        if c_datos['gas'] and c_datos['gas'] > 0:
            servicios_inquilino_list.append(f"Gas: $ {c_datos['gas']:,.2f}")
        if c_datos['municipalidad'] and c_datos['municipalidad'] > 0:
            servicios_inquilino_list.append(f"Tasas Municipales: $ {c_datos['municipalidad']:,.2f}")
        if c_datos['ooss'] and c_datos['ooss'] > 0:
            servicios_inquilino_list.append(f"Obras Sanitarias: $ {c_datos['ooss']:,.2f}")
        if c_datos['cochera'] and c_datos['cochera'] > 0:
            servicios_inquilino_list.append(f"Cochera: $ {c_datos['cochera']:,.2f}")

        # Renderizado estructural del panel de visualización
        st.markdown("### 📋 Ficha Técnica del Contrato")
        
        inf_c1, inf_c2, inf_c3 = st.columns(3)
        with inf_c1:
            st.text_input("🏠 Propiedad:", value=c_datos['propiedad_dir'], disabled=True)
            st.text_input("📅 Próxima actualización:", value=c_datos['prox_actualizacion'], disabled=True)
            st.text_input("💵 Último valor cobrado:", value=f"$ {alquiler_base:,.2f}", disabled=True)
            
        with inf_c2:
            st.text_input("📈 Valor actualizado obtenido:", value=f"$ {valor_actualizado_fmt}", disabled=True)
            
            mes_actual_pago = c_datos['mes_contrato'] if c_datos['mes_contrato'] is not None else 1
            duracion_total_pago = c_datos['calc_duracion'] if c_datos['calc_duracion'] is not None else 24
            st.text_input("📊 Estado del período:", value=f"Mes {mes_actual_pago} de {duracion_total_pago}", disabled=True, help="Mes actual de contrato sobre la duración total.")
            
            st.markdown(f"🔗 **Enlace Externo:** [Abrir panel en arquiler.com]({url_arquiler})")
            
        with inf_c3:
            st.text_input("💼 Honorarios inmobiliaria (Saldo pendiente):", value=f"$ {(float(c_datos['monto_honorarios'] or 0.0) - float(c_datos['honorarios_pagados'] or 0.0)):,.2f} (Total: $ {c_datos['monto_honorarios'] or 0.0:,.2f})", disabled=True)
            st.text_input("🛡️ Monto de depósito de garantía a pagar:", value=f"$ {c_datos['monto_garantia'] or 0.0:,.2f} — Estado: {c_datos['garantia']}", disabled=True)

        st.markdown("##### 🛠️ Servicios a cargo del inquilino:")
        if servicios_inquilino_list:
            for s_item in servicios_inquilino_list:
                st.markdown(f" * {s_item}")
            st.caption(f"**Total consolidado de servicios liquidables:** $ {c_datos['servicios_total'] or 0.0:,.2f}")
        else:
            st.caption("No se registran servicios adicionales configurados a cargo del inquilino.")


# =====================================================================
# PESTAÑA 3: FORMULARIO REACTIVO DE CARGA DE CONTRATOS
# =====================================================================
with tab_carga:
    st.subheader("Formulario de Registro Técnico del Contrato")
    
    dict_propiedades, dict_inquilinos = obtener_datos_desplegables()
    
    if not dict_propiedades or not dict_inquilinos:
        st.warning("⚠️ Módulo de carga bloqueado: Debe registrar al menos una Propiedad y un Inquilino en la pestaña '⚙️ Cargar Inquilinos / Propiedades' para poder generar un contrato.")
    else:
        permitir_edicion = st.toggle("🔒 Habilitar Formulario de Carga", value=False)
        
        if not permitir_edicion:
            st.info("Formulario protegido contra escrituras accidentales. Active el interruptor de arriba para editar.")

        def obtener_ultimo_contrato():
            conn = conectar_db()
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    SELECT propiedad_id, inquilino_id, estado, monto_inicial, alquiler, 
                           act_contrato, indice, honorarios, monto_garantia,
                           imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, cochera
                    FROM contratos 
                    ORDER BY codigo DESC LIMIT 1
                ''')
                return cursor.fetchone()
            except Exception:
                return None
            finally:
                conn.close()

        # Función auxiliar para comprobar si la propiedad ya cuenta con algún contrato anterior
        def verificar_contrato_existente(p_id):
            conn = conectar_db()
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT codigo, estado FROM contratos WHERE propiedad_id = ? ORDER BY codigo DESC LIMIT 1', (p_id,))
                return cursor.fetchone()
            except Exception:
                return None
            finally:
                conn.close()

        if "ultimo_contrato" not in st.session_state:
            st.session_state.ultimo_contrato = obtener_ultimo_contrato()

        u = st.session_state.ultimo_contrato
            
        # --- 1. SELECCIÓN DE ENTIDADES Y DATOS MAESTROS ---
        st.markdown("### 1. Selección de Entidades y Datos Maestros")
        c1, c2, c3 = st.columns([2, 2, 1])
        
        lista_propiedades = list(dict_propiedades.keys())
        idx_prop = 0
        if u and u[0] in dict_propiedades.values():
            idx_prop = lista_propiedades.index(next(k for k, v in dict_propiedades.items() if v == u[0]))

        lista_inquilinos = list(dict_inquilinos.keys())
        idx_inq = 0
        if u and u[1] in dict_inquilinos.values():
            idx_inq = lista_inquilinos.index(next(k for k, v in dict_inquilinos.items() if v == u[1]))

        estados_disponibles = ["Activo", "Finalizado", "Cancelado", "Revalorizado", "Vencido", "Inhabitado"]
        idx_estado = estados_disponibles.index(u[2]) if u and u[2] in estados_disponibles else 0

        propiedad_seleccionada = c1.selectbox("Seleccione la Propiedad (Alias / Ubicación):", lista_propiedades, index=idx_prop, disabled=not permitir_edicion)
        inquilino_seleccionado = c2.selectbox("Seleccione el Inquilino (Apellido, Nombre):", lista_inquilinos, index=idx_inq, disabled=not permitir_edicion)
        state_contrato = c3.selectbox("Estado del Contrato:", estados_disponibles, index=idx_estado, disabled=not permitir_edicion)
        
        propiedad_id = dict_propiedades[propiedad_seleccionada]
        inquilino_id = dict_inquilinos[inquilino_seleccionado]

        # --- DETECCIÓN DE CONTRATO EXISTENTE PARA LA PROPIEDAD ---
        contrato_previo = verificar_contrato_existente(propiedad_id)
        modo_guardado = "Crear Nuevo"
        id_contrato_a_modificar = None

        if contrato_previo:
            id_contrato_a_modificar = contrato_previo[0]
            st.info(f"ℹ️ **Aviso:** Esta propiedad ya posee un contrato registrado (Código Interno: {id_contrato_a_modificar} - Estado: {contrato_previo[1]}).")
            modo_guardado = st.radio(
                "¿Qué acción desea realizar al guardar?",
                ["Actualizar (Modificar el contrato existente)", "Crear uno nuevo (Nuevo Registro Histórico)"],
                index=0,
                disabled=not permitir_edicion
            )
        

# =====================================================================
# 2. FECHAS, PLAZOS Y DURACIÓN (CÁLCULOS DINÁMICOS)
# =====================================================================
        # --- Asegurar que las fechas existan antes de la Sección 2 ---
        fecha_primer_dia_actual = datetime.now().replace(day=1).date()
        fecha_primer_dia_vencimiento = fecha_primer_dia_actual + dateutil.relativedelta.relativedelta(years=2)

        st.markdown("### 2. Fechas, Plazos y Duración (Cálculos Dinámicos)")
        cf1, cf2 = st.columns(2)
        inicio_contrato = cf1.date_input("Inicio del Contrato:", value=fecha_primer_dia_actual, format="DD/MM/YYYY", disabled=not permitir_edicion)
        fin_contrato = cf2.date_input("Fin del Contrato:", value=fecha_primer_dia_vencimiento, format="DD/MM/YYYY", disabled=not permitir_edicion)

        cf3, cf4, cf5 = st.columns([2, 1, 1])
        opciones_actualizacion = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24}
        idx_act = list(opciones_actualizacion.keys()).index(u[5]) if u and u[5] in opciones_actualizacion else 4

        act_contrato_seleccionado = cf3.selectbox("Actualización Contrato (Frecuencia):", list(opciones_actualizacion.keys()), index=idx_act, disabled=not permitir_edicion)
        meses_a_sumar = opciones_actualizacion[act_contrato_seleccionado]

        # Cálculos de tiempo para la advertencia
        fecha_hoy = datetime.now().date()
        prox_actualizacion_calculada = inicio_contrato + dateutil.relativedelta.relativedelta(months=meses_a_sumar)

        # Bucle para encontrar la próxima fecha válida de actualización
        while prox_actualizacion_calculada < fecha_hoy and prox_actualizacion_calculada <= fin_contrato:
            prox_actualizacion_calculada += dateutil.relativedelta.relativedelta(months=meses_a_sumar)

        necesita_renovacion = prox_actualizacion_calculada > fin_contrato

        # Cálculo del mes actual de contrato
        diferencia_hoy = dateutil.relativedelta.relativedelta(fecha_hoy, inicio_contrato)
        total_meses_transcurridos = (diferencia_hoy.years * 12) + diferencia_hoy.months
        if total_meses_transcurridos < 0: total_meses_transcurridos = 0
        mes_actual_contrato_vivo = total_meses_transcurridos + 1

        # Lógica de advertencia visual (NUEVO)
        es_mes_de_actualizacion = ((mes_actual_contrato_vivo - 1) % meses_a_sumar) == 0

        if necesita_renovacion:
            st.error("🚨 Estado del Período: **RENOVAR** (La fecha de próxima actualización excede el fin del contrato)")
        elif es_mes_de_actualizacion:
                st.warning(f"⚠️ **AVISO:** Estás en el mes {mes_actual_contrato_vivo} de contrato. Según la frecuencia '{act_contrato_seleccionado}', **corresponde aplicar una actualización del monto** en este periodo.")
        else:
            st.info(f"Estado: Período normal (Mes {mes_actual_contrato_vivo}). No corresponde actualizar el alquiler este mes.")

        with cf4:
            if not necesita_renovacion:
                st.date_input("Próxima Actualización:", value=prox_actualizacion_calculada, format="DD/MM/YYYY", disabled=True)

        fin_con_un_dia_mas = fin_contrato + dateutil.relativedelta.relativedelta(days=1)
        diff_contrato = dateutil.relativedelta.relativedelta(fin_con_un_dia_mas, inicio_contrato)
        duracion_meses_calculada = (diff_contrato.years * 12) + diff_contrato.months
        cf5.text_input("Duración del Contrato:", value=f"{duracion_meses_calculada} meses", disabled=True)


        # --- 3. VALORES ECONÓMICOS E ÍNDICES ---
        st.markdown("### 3. Valores Económicos e Índices")
        cv1, cv2 = st.columns(2)
        
        val_monto_ini = float(u[3]) if u and u[3] is not None else 80000.0
        val_alq_ult = float(u[4]) if u and u[4] is not None else 80000.0
        
        monto_inicial = cv1.number_input("Monto Inicial ($):", min_value=0.0, step=5000.0, value=val_monto_ini, disabled=not permitir_edicion)
        alquiler = cv2.number_input("Último Valor Cobrado ($):", min_value=0.0, step=5000.0, value=val_alq_ult, disabled=not permitir_edicion)
        
        cv_ind, cv_meses = st.columns(2)
        indices_disponibles = ["ICL", "IPC", "UVA", "Otro"]
        idx_ind = indices_disponibles.index(u[6]) if u and u[6] in indices_disponibles else 0
        
        indice_seleccionado = cv_ind.selectbox("Índice Aplicado:", indices_disponibles, index=idx_ind, disabled=not permitir_edicion)
        meses_atras = cv_meses.number_input("Intervalo de Meses para Ajustar:", min_value=1, max_value=24, value=int(meses_a_sumar), disabled=not permitir_edicion)
        
        indice_final = st.text_input("Especifique el Índice personalizado:", value=u[6] if u and idx_ind == 3 else "", placeholder="Ej: Ajuste Fijo", disabled=not permitir_edicion) if indice_seleccionado == "Otro" else indice_seleccionado

        codigo_rate = indice_final.lower()
        fecha_param_str = inicio_contrato.strftime("%Y-%m-%d")
        url_calculo_dinamica = f"https://arquiler.com/pwa?amount={int(alquiler)}&date={fecha_param_str}&months={meses_atras}&rate={codigo_rate}"
        
        c_web1, c_web2 = st.columns([2, 3])
        c_web1.markdown(f"🔗 [Abrir panel en arquiler.com]({url_calculo_dinamica})")

        valor_por_defecto_fmt = f"{round(alquiler, 2):,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
        
        alquiler_actualizado_texto = c_web2.text_input(
            "Valor Actualizado obtenido ($):", 
            value=valor_por_defecto_fmt, 
            key="campo_alquiler_actualizado_text", 
            disabled=not permitir_edicion
        )
        alquiler_actualizado = limpiar_string_a_float(alquiler_actualizado_texto)
        
# --- FILTROS DE SEGURIDAD Y LOGICA DE AUMENTO ---
        if 'id_contrato_a_editar' in st.session_state and st.session_state['id_contrato_a_editar']:
            texto_boton = "Actualizar Monto de Contrato"
        else:
            texto_boton = "Actualizar Contrato Existente"
        
        
        valor_invalido_o_vacio = (alquiler_actualizado is None or alquiler_actualizado <= 0.0)
        es_mes_de_actualizacion = ((mes_actual_contrato_vivo - 1) % meses_a_sumar) == 0
        alquiler_sin_cambios = (alquiler_actualizado == alquiler)
        
        # 1. Determinamos si se debe bloquear
        bloqueo_por_actualizacion = False
        if necesita_renovacion:
            bloqueo_por_actualizacion = True
        elif valor_invalido_o_vacio:
            bloqueo_por_actualizacion = True
        elif es_mes_de_actualizacion and alquiler_sin_cambios:
            bloqueo_por_actualizacion = True

        # 2. Mostramos los mensajes y el botón (Lógica visual sobre el botón)
        if necesita_renovacion:
            st.error("🚨 Estado del Período: **RENOVAR** (La fecha de próxima actualización excede el fin del contrato)")
        elif valor_invalido_o_vacio:
            st.error("❌ **Error:** El 'Valor Actualizado obtenido' debe ser un número positivo mayor a 0.")
        elif es_mes_de_actualizacion and alquiler_sin_cambios:
            st.warning(f"⚡ **MES DE ACTUALIZACIÓN (Mes {mes_actual_contrato_vivo})**: Debe ingresar un valor distinto al anterior ($ {alquiler:,.2f}) para poder guardar.")
        elif es_mes_de_actualizacion and not alquiler_sin_cambios:
            st.success(f"✅ **Mes de actualización:** Nuevo valor confirmado ($ {alquiler_actualizado:,.2f}).")
        else:
            st.info(f"Estado: Período normal (Mes {mes_actual_contrato_vivo}).")

        # 3. Definimos y mostramos el botón
        boton_deshabilitado = (not permitir_edicion) or bloqueo_por_actualizacion or necesita_renovacion
        btn_guardar_final = st.button(texto_boton, disabled=boton_deshabilitado, type="primary")



        # --- 4. LIQUIDACIÓN DE IMPORTES DE AGENCIA ---
        st.markdown("### 4. Liquidación de Importes de Agencia")
        with st.container(border=True):
            st.markdown("##### **A) COMISION INMOBILIARIA (A cargo del Propietario - Retención Mensual)**")
            ch_prop1, ch_prop2 = st.columns(2)
            val_hon_pct = float(u[7]) if u and u[7] is not None else 5.0
            honorarios_pct = ch_prop1.number_input("Porcentaje de Administración (%):", min_value=0.0, value=val_hon_pct, step=0.5, disabled=not permitir_edicion)
            
            retencion_mensual_estimated = alquiler_actualizado * (honorarios_pct / 100.0) if not valor_invalido_o_vacio else 0.0
            ret_mensual_fmt = f"$ {retencion_mensual_estimated:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            ch_prop2.text_input("Retención mensual calculada ($):", value=ret_mensual_fmt, disabled=True)
        
        with st.container(border=True):
            st.markdown("##### **B) HONORARIOS INMOBILIARIA (A cargo del Inquilino - Comisión de Contrato)**")
            ch_inq1, ch_inq2, ch_inq3 = st.columns(3)
            honorarios_inquilino_total = ch_inq1.number_input("Monto Total de Comisión ($):", min_value=0.0, value=float(monto_inicial), step=5000.0, disabled=not permitir_edicion)
            cuota_honorarios = ch_inq2.number_input("Cuotas pactadas para el pago:", min_value=1, value=1, step=1, disabled=not permitir_edicion)
            honorarios_pagados = ch_inq3.number_input("Monto pagado a la fecha ($):", min_value=0.0, step=5000.0, disabled=not permitir_edicion)
            
            saldo_inquilino_hon = honorarios_inquilino_total - honorarios_pagados
            if saldo_inquilino_hon > 0: 
                saldo_hon_fmt = f"$ {saldo_inquilino_hon:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                st.warning(f"💵 Honorarios Inquilino: Queda un saldo de **{saldo_hon_fmt}** a financiar.")

        # --- 5. RESPALDO Y GARANTÍAS DEL CONTRATO ---
        st.markdown("### 5. Respaldo y Garantías del Contrato")
        st.markdown("##### **A) Respaldo con Documento Pagaré**")
        cg_pag1, cg_pag2 = st.columns(2)
        tiene_pag_idx = 1 if u and "Sí" in str(u[9]) else 0
        tiene_pagare = cg_pag1.selectbox("¿Aplica Pagaré firmado?:", ["No", "Sí"], index=tiene_pag_idx, disabled=not permitir_edicion)
        monto_pagare = cg_pag2.number_input("Monto acordado del Pagaré ($):", min_value=0.0, value=0.0, step=10000.0, disabled=not permitir_edicion if tiene_pagare == "Sí" else True)

        st.markdown("##### **B) Respaldo con Monto Depositado**")
        cg_dep1, cg_dep2, cg_dep3, cg_dep4 = st.columns(4)
        val_dep_tot = float(u[8]) if u and u[8] is not None else float(monto_inicial)
        monto_deposito_total = cg_dep1.number_input("Monto Total Depósito ($):", min_value=0.0, value=val_dep_tot, step=5000.0, disabled=not permitir_edicion)
        cuotas_deposito = cg_dep2.number_input("Cuotas pactadas depósito:", min_value=1, value=1, step=1, disabled=not permitir_edicion)
        deposito_pagado = cg_dep3.number_input("Monto depositado a la fecha ($):", min_value=0.0, step=5000.0, disabled=not permitir_edicion)
        
        saldo_deposito = monto_deposito_total - deposito_pagado
        estado_garantia_calculado = "Depositada" if saldo_deposito <= 0 else f"Financiando (Saldo: $ {saldo_deposito:,.2f})"
        cg_dep4.text_input("Estado del Depósito:", value=estado_garantia_calculado, disabled=True)



# =====================================================================
        # SECCIÓN 6: DESGLOSE DE SERVICIOS MENSUALES ($)
        # =====================================================================
        st.markdown("### 6. Desglose de Servicios Mensuales ($)")
        
        # --- GRUPO A: SERVICIOS PÚBLICOS E IMPUESTOS MUNICIPALES ---
        with st.container(border=True):
            st.markdown("##### **⚡ / 🔥 / 💧 / 🏛️ Servicios Públicos y Municipales**")
            g1_col1, g1_col2 = st.columns(2)
            
            with g1_col1:
                # Electricidad
                with st.container():
                    s_col5, s_col6 = st.columns([3, 2])
                    val_ede = float(u[12]) if u and u[12] is not None else 0.0
                    edesal = s_col5.number_input("Monto Electricidad ($):", min_value=0.0, value=val_ede, step=500.0, disabled=not permitir_edicion)
                    cargo_electricidad = s_col6.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_elec", disabled=not permitir_edicion)
                    num_nis = st.number_input("NIS Nro:", min_value=0, value=0, step=1, key="id_nis", disabled=not permitir_edicion)
                
                # Gas
                st.markdown("---")
                with st.container():
                    s_col7, s_col8 = st.columns([3, 2])
                    val_gas = float(u[13]) if u and u[13] is not None else 0.0
                    gas = s_col7.number_input("Monto Gas ($):", min_value=0.0, value=val_gas, step=500.0, disabled=not permitir_edicion)
                    cargo_gas = s_col8.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_gas", disabled=not permitir_edicion)
                    cuenta_gas = st.text_input("Nro de Cuenta (Gas):", key="id_cta_gas", disabled=not permitir_edicion)
                    
            with g1_col2:
                # Municipalidad
                with st.container():
                    s_col9, s_col10 = st.columns([3, 2])
                    val_mun = float(u[14]) if u and u[14] is not None else 0.0
                    municipalidad = s_col9.number_input("Monto Municipalidad ($):", min_value=0.0, value=val_mun, step=500.0, disabled=not permitir_edicion)
                    cargo_municipalidad = s_col10.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_mun", disabled=not permitir_edicion)
                    finca_mun = st.text_input("Finca Nro:", key="id_finca_mun", disabled=not permitir_edicion)
                
                # Obras Sanitarias (OO.SS)
                st.markdown("---")
                with st.container():
                    s_col11, s_col12 = st.columns([3, 2])
                    val_oos = float(u[15]) if u and u[15] is not None else 0.0
                    ooss = s_col11.number_input("Monto OO.SS. ($):", min_value=0.0, value=val_oos, step=500.0, disabled=not permitir_edicion)
                    cargo_ooss = s_col12.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_oos", disabled=not permitir_edicion)
                    cuenta_oos = st.text_input("Nro de Cuenta (OO.SS.):", key="id_cta_oos", disabled=not permitir_edicion)

        # --- GRUPO B: COMPLEMENTOS DE LA PROPIEDAD ---
        with st.container(border=True):
            st.markdown("##### **🏢 Complementos de Propiedad y Consorcio**")
            g2_col1, g2_col2 = st.columns(2)
            
            with g2_col1:
                s_col3, s_col4 = st.columns([3, 2])
                val_exp = float(u[10]) if u and u[10] is not None else 0.0
                expensas = s_col3.number_input("Monto Expensas ($):", min_value=0.0, value=val_exp, step=500.0, disabled=not permitir_edicion)
                cargo_expensas = s_col4.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_exp", disabled=not permitir_edicion)
                
            with g2_col2:
                s_col13, s_col14 = st.columns([3, 2])
                val_coch = float(u[15]) if u and len(u) > 16 and u[16] is not None else 0.0
                cochera = s_col13.number_input("Monto Cochera ($):", min_value=0.0, value=val_coch, step=1000.0, disabled=not permitir_edicion)
                cargo_cochera = s_col14.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_coch", disabled=not permitir_edicion)

        # --- GRUPO C: IMPUESTO PROVINCIAL ESTRUCTURAL ---
        with st.container(border=True):
            st.markdown("##### **📌 Impuesto Provincial Individual**")
            s_col1, s_col2 = st.columns([3, 2])
            val_imp_inmob = float(u[9]) if u and u[9] is not None else 0.0
            imp_inmobiliario = s_col1.number_input("Imp. Inmobiliario ($):", min_value=0.0, value=val_imp_inmob, step=500.0, disabled=not permitir_edicion)
            cargo_inmobiliario = s_col2.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=1, key="cargo_inmob", disabled=not permitir_edicion)

        # NOTAS GENERALES Y DETALLES STRING
        st.text(" ") 
        notas_adicionales_input = st.text_input("Notas Adicionales de Servicios:", disabled=not permitir_edicion)
        
        str_identificadores = f"[NIS: {num_nis}] [Cta Gas: {cuenta_gas}] [Finca: {finca_mun}] [Cta OO.SS.: {cuenta_oos}]"
        detalles_pagos_str = f"| Elec: {cargo_electricidad} | Gas: {cargo_gas} | Mun: {cargo_municipalidad} | OOSS: {cargo_ooss} | Exp: {cargo_expensas} | Inmob: {cargo_inmobiliario}"
        
        if notas_adicionales_input.strip():
            servicios_detalle = f"{str_identificadores} {detalles_pagos_str} | Notas: {notas_adicionales_input}"
        else:
            servicios_detalle = f"{str_identificadores} {detalles_pagos_str}"

        # --- CALCULO TOTAL DE LIQUIDACIÓN DINÁMICA ---
        m_inmob_liq = imp_inmobiliario if cargo_inmobiliario == "Inquilino" else 0.0
        m_exp_liq = expensas if cargo_expensas == "Inquilino" else 0.0
        m_elec_liq = edesal if cargo_electricidad == "Inquilino" else 0.0
        m_gas_liq = gas if cargo_gas == "Inquilino" else 0.0
        m_mun_liq = municipalidad if cargo_municipalidad == "Inquilino" else 0.0
        m_oos_liq = ooss if cargo_ooss == "Inquilino" else 0.0
        m_coch_liq = cochera if cargo_cochera == "Inquilino" else 0.0
        
        servicios_total_calculado = (m_inmob_liq + m_exp_liq + m_elec_liq + m_gas_liq + m_mun_liq + m_oos_liq + m_coch_liq)


        

        # --- 7. CONSOLIDACIÓN DEL PAGO DE ALQUILER INICIAL ---
        st.markdown("### 7. Consolidación del Pago de Alquiler Inicial")
        cp_1, cp_2, cp_3 = st.columns(3)
        
        base_calculo_cobro = float(alquiler_actualizado) if not valor_invalido_o_vacio else 0.0
        alquiler_cobrado = cp_1.number_input("Monto Neto de Alquiler Cobrado ($):", min_value=0.0, value=base_calculo_cobro, step=5000.0, disabled=not permitir_edicion)
        total_pagado_calculado = alquiler_cobrado + servicios_total_calculado
        
        cp_2.number_input("Total de Servicios Adicionados ($):", value=float(servicios_total_calculado), disabled=True)
        cp_3.number_input("TOTAL CONSOLIDADO COBRADO (Caja) ($):", value=float(total_pagado_calculado), disabled=True)

        st.markdown("---")
        
        # --- CONTROL DE BLOQUEO GLOBAL DEL BOTÓN ---
        boton_deshabilitado = (not permitir_edicion) or bloqueo_por_actualizacion or necesita_renovacion
        
        # Ajustamos dinámicamente la etiqueta de texto del botón principal
        texto_boton = "💾 Actualizar Contrato Existente" if (contrato_previo and "Actualizar" in modo_guardado) else "💾 Guardar y Registrar Contrato Completo"
        
        btn_guardar_final = st.button(texto_boton, disabled=boton_deshabilitado, type="primary")
        
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
                # ESTRATEGIA A: ACTUALIZAR REGISTRO EXISTENTE
                if contrato_previo and "Actualizar" in modo_guardado:
                    cursor.execute('''
                        UPDATE contratos 
                        SET propiedad_id=?, inquilino_id=?, estado=?, inicio_contrato=?, fin_contrato=?,
                            calc_duracion=?, act_contrato=?, indice=?, monto_inicial=?, alquiler=?, prox_actualizacion=?,
                            mes_contrato=?, mes_actualizacion_contrato=?, servicios=?, honorarios=?, monto_honorarios=?,
                            cuota_honorarios=?, honorarios_pagados=?, monto_garantia=?, garantia=?,
                            imp_inmobiliario=?, expensas=?, edesal=?, gas=?, municipalidad=?, ooss=?, servicios_total=?,
                            cochera=?, alquiler_cobrado=?, total_pagado=?
                        WHERE codigo = ?
                    ''', (
                        propiedad_id, inquilino_id, state_contrato, inicio_str, fin_str,
                        duracion_meses_calculada, act_contrato_seleccionado, indice_final, monto_inicial, alquiler, prox_act_str,
                        mes_actual_contrato_vivo, meses_atras_calculado, registro_distribucion, honorarios_pct, retencion_mensual_estimated,
                        cuota_honorarios, honorarios_pagados, monto_deposito_total, detalle_garantia_unificado,
                        imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, servicios_total_calculado,
                        cochera, alquiler_cobrado, total_pagado_calculado, id_contrato_a_modificar
                    ))
                    st.success(f"✔️ ¡Contrato N° {id_contrato_a_modificar} actualizado correctamente!")

                # ESTRATEGIA B: CREAR UN NUEVO CONTRATO HISTÓRICO
                else:
                    if state_contrato == "Activo":
                        cursor.execute('''
                            UPDATE contratos 
                            SET estado = 'Finalizado' 
                            WHERE propiedad_id = ? AND estado = 'Activo'
                        ''', (propiedad_id,))
                    
                    cursor.execute('''
                        INSERT INTO contratos (
                            propiedad_id, inquilino_id, estado, inicio_contrato, fin_contrato,
                            calc_duracion, act_contrato, indice, monto_inicial, alquiler, prox_actualizacion,
                            mes_contrato, mes_actualizacion_contrato, servicios, honorarios, monto_honorarios,
                            cuota_honorarios, honorarios_pagados, monto_garantia, garantia,
                            imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, servicios_total,
                            cochera, alquiler_cobrado, total_pagado
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        propiedad_id, inquilino_id, state_contrato, inicio_str, fin_str,
                        duracion_meses_calculada, act_contrato_seleccionado, indice_final, monto_inicial, alquiler, prox_act_str,
                        mes_actual_contrato_vivo, meses_atras_calculado, registro_distribucion, honorarios_pct, retencion_mensual_estimated,
                        cuota_honorarios, honorarios_pagados, monto_deposito_total, detalle_garantia_unificado,
                        imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, servicios_total_calculado,
                        cochera, alquiler_cobrado, total_pagado_calculado
                    ))
                    st.success("✔️ ¡Nuevo contrato creado e insertado con éxito!")

                conn.commit()
                st.session_state.ultimo_contrato = obtener_ultimo_contrato()
                st.rerun()
            except Exception as e:
                st.error(f"Error de base de datos al impactar los cambios: {e}")
            finally:
                conn.close()

# =====================================================================
# PESTAÑA 4: CARGA DE AUXILIARES (INQUILINOS / PROPIEDADES)
# =====================================================================
with tab_auxiliares:
    st.subheader("⚙️ Panel de Configuración de Entidades")
    
    col_aux1, col_aux2 = st.columns(2)
    
    with col_aux1:
        st.markdown("#### Registrar Nuevo Inquilino")
        with st.form("form_inquilino", clear_on_submit=True):
            apellidos = st.text_input("Apellidos:", placeholder="Ej: Pérez Rossi")
            nombres = st.text_input("Nombres:", placeholder="Ej: Juan Carlos")
            
            # Campo exclusivo para DNI
            dni = st.text_input("DNI (Documento Nacional de Identidad):", placeholder="Ej: 34567890", help="Ingrese el número de documento corrido, sin puntos ni espacios.")
            
            # Nuevo campo de Dirección Electrónica
            email = st.text_input("Dirección Electrónica (Email):", placeholder="Ej: juancarlos@gmail.com", help="Correo electrónico de contacto para notificaciones.")
            
            # Campo de teléfono con ejemplos de 10 dígitos
            tel = st.text_input(
                "Teléfono de Contacto (Celular):", 
                placeholder="Ej: 2657123456", 
                help="Formato obligatorio: 10 dígitos. Incluye característica SIN el 0, y número SIN el 15. Ejemplo: 2657 + 123456"
            )
            
            btn_inq = st.form_submit_button("Guardar Inquilino")
            
            if btn_inq and apellidos and nombres:
                tel_limpio = tel.strip().replace(" ", "").replace("-", "")
                email_limpio = email.strip().lower()
                dni_limpio = dni.strip().replace(".", "").replace(" ", "")
                
                # Expresión regular básica para validar correos electrónicos estándar
                regex_email = r"^[\w\.-]+@[\w\.-]+\.\w+$"
                
                # Validaciones previas al guardado
                if dni_limpio and not dni_limpio.isdigit():
                    st.error("⚠️ El DNI debe contener únicamente números (sin puntos).")
                elif not re.match(r"^[1-9]\d{9}$", tel_limpio):
                    st.error("⚠️ El número de teléfono es inválido. Debe tener exactamente 10 dígitos y no puede empezar con 0. Recuerda quitar el 0 y el 15.")
                elif email_limpio and not re.match(regex_email, email_limpio):
                    st.error("⚠️ La dirección electrónica (Email) no tiene un formato válido. Debe incluir un '@' y un dominio (Ej: .com).")
                else:
                    conn = conectar_db()
                    cursor = conn.cursor()
                    try:
                        # Guardamos incluyendo la nueva columna email
                        cursor.execute("INSERT INTO inquilinos (apellidos, nombres, dni, telefono, email) VALUES (?, ?, ?, ?, ?)", 
                                       (apellidos.strip(), nombres.strip(), dni_limpio, tel_limpio, email_limpio))
                        conn.commit()
                        st.success(f"✔️ Inquilino {apellidos}, {nombres} guardado con éxito.")
                    except sqlite3.IntegrityError:
                        st.error("Ya existe un inquilino con ese Apellido y Nombre.")
                    except sqlite3.OperationalError as e:
                        st.error(f"⚠️ Error operativo: Si agregaste el campo email recién ahora, necesitas borrar el archivo 'sistema_alquileres_v3.db' o agregar la columna manualmente en SQLite. Detalle: {e}")
                    finally:
                        conn.close()
                    
    with col_aux2:
        st.markdown("#### Registrar Nueva Propiedad")
        with st.form("form_propiedad", clear_on_submit=True):
            alias = st.text_input("Alias de la Propiedad:", placeholder="Ej: Dpto 3B - Torre Mitre o Casa Quinta")
            calle = st.text_input("Calle / Av:", placeholder="Ej: Av. Mitre")
            numero = st.text_input("Número:", placeholder="Ej: 1450")
            depto = st.text_input("Departamento / Piso / Bloque (Opcional):", placeholder="Ej: Piso 3 - Dpto B (Dejar vacío si es casa)")
            
            btn_prop = st.form_submit_button("Guardar Propiedad")
            
            if btn_prop and alias and calle and numero:
                conn = conectar_db()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO propiedades (alias_propiedad, calle, numero, departamento) VALUES (?, ?, ?, ?)", 
                                   (alias.strip(), calle.strip(), numero.strip(), depto.strip()))
                    conn.commit()
                    st.success(f"Propiedad '{alias}' registrada correctamente.")
                except sqlite3.IntegrityError:
                    st.error("El Alias de la propiedad ya se encuentra registrado.")
                finally:
                    conn.close()
