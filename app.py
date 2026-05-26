import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import dateutil.relativedelta
import re
import urllib.parse

# =====================================================================
# 1. BASE DE DATOS: CONFIGURACIÓN RELACIONAL E HISTORIAL DE PAGOS
# =====================================================================
def conectar_db():
    return sqlite3.connect('sistema_alquileres_v3.db')

def inicializar_tablas():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Tabla 1: Inquilinos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inquilinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apellidos TEXT NOT NULL,
            nombres TEXT NOT NULL,
            dni TEXT,             
            telefono TEXT,
            email TEXT,            
            UNIQUE(apellidos, nombres)
        )
    ''')
    
    # Tabla 2: Propiedades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS propiedades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias_propiedad TEXT NOT NULL UNIQUE,
            calle TEXT NOT NULL,
            numero TEXT NOT NULL,
            departamento TEXT 
        )
    ''')
    
    # Tabla 3: Contratos
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
            servicios TEXT,
            honorarios REAL,
            monto_honorarios REAL,
            cuota_honorarios INTEGER,
            honorarios_pagados REAL,
            tipo_de_garantie TEXT,
            monto_garantia REAL,
            garantia TEXT,
            garantia_pagada REAL,
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
    
    # Tabla 4 (MEJORA 1): Historial de Pagos Reales (Caja)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pagos_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contrato_id INTEGER NOT NULL,
            periodo TEXT NOT NULL,
            monto_alquiler REAL NOT NULL,
            monto_servicios REAL NOT NULL,
            monto_total REAL NOT NULL,
            fecha_pago TEXT NOT NULL,
            metodo_pago TEXT NOT NULL,
            comentarios TEXT,
            FOREIGN KEY (contrato_id) REFERENCES contratos(codigo)
        )
    ''')
    conn.commit()
    conn.close()

inicializar_tablas()

# =====================================================================
# FUNCIONES AUXILIARES DE LÓGICA Y PARSEO
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
# INTERFAZ DE USUARIO GENERAL (Streamlit)
# =====================================================================
st.set_page_config(page_title="Gestión de Alquileres Pro", layout="wide")
st.title("🏢 Sistema Avanzado de Gestión de Alquileres e Historial de Caja")

tab_dashboard, tab_planilla, tab_pagos, tab_historial_pagos, tab_carga, tab_auxiliares = st.tabs([
    "📈 Tablero de Control",
    "📊 Planilla de Contratos", 
    "💰 Registrar / Emitir Recibo",
    "🗄️ Historial de Caja",
    "📝 Carga de Contratos", 
    "⚙️ Cargar Inquilinos / Propiedades"
])

# =====================================================================
# MEJORA 2: TABLERO DE CONTROL (DASHBOARD INTERACTIVO Y ALERTAS)
# =====================================================================
with tab_dashboard:
    st.subheader("⚡ Alertas Estratégicas y Métricas Generales")
    
    conn = conectar_db()
    query_dash = '''
        SELECT c.codigo, p.alias_propiedad, (i.apellidos || ', ' || i.nombres) as inquilino,
               c.estado, c.fin_contrato, c.prox_actualizacion, c.alquiler, c.mes_contrato, c.act_contrato
        FROM contratos c
        JOIN propiedades p ON c.propiedad_id = p.id
        JOIN inquilinos i ON c.inquilino_id = i.id
        WHERE c.estado = 'Activo'
    '''
    df_dash = pd.read_sql_query(query_dash, conn)
    df_pagos_totales = pd.read_sql_query("SELECT monto_total FROM pagos_historial", conn)
    conn.close()
    
    # Cálculos para los KPIs
    total_activos = len(df_dash)
    caja_historica = df_pagos_totales['monto_total'].sum() if not df_pagos_totales.empty else 0.0
    
    vencen_pronto = 0
    actualizan_este_mes = 0
    lista_alertas_vencimiento = []
    lista_alertas_actualizacion = []
    
    fecha_hoy = datetime.now().date()
    
    for _, row in df_dash.iterrows():
        # Verificación de vencimiento de contrato (60 días)
        try:
            fin_dt = datetime.strptime(row['fin_contrato'], "%d/%m/%Y").date()
            dias_para_vencer = (fin_dt - fecha_hoy).days
            if 0 <= dias_para_vencer <= 60:
                vencen_pronto += 1
                lista_alertas_vencimiento.append(f"⚠️ El contrato de **{row['inquilino']}** ({row['alias_propiedad']}) vence en **{dias_para_vencer} días** ({row['fin_contrato']}).")
        except:
            pass
            
        # Verificación si es mes de actualización
        opciones_meses = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24}
        frecuencia = opciones_meses.get(row['act_contrato'], 6)
        mes_vivo = row['mes_contrato'] or 1
        if ((mes_vivo - 1) % frecuencia) == 0:
            actualizan_este_mes += 1
            lista_alertas_actualizacion.append(f"📈 Corresponde ajustar alquiler a **{row['inquilino']}** ({row['alias_propiedad']}). Período: {row['act_contrato']}.")

    # Mostrar métricas principales
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
with tab_planilla:
    st.subheader("Historial y Estado de Contratos")
    
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        busqueda = st.text_input("🔍 Buscar por Inquilino, Calle o Alias:", placeholder="Ej: Pérez o Mitre", key="buscar_planilla")
    with col_f2:
        filtro_estado = st.multiselect("Filtrar por Estado:", ["Activo", "Finalizado", "Cancelado", "Vencido"], default=["Activo"], key="filtro_estado_planilla")
    
    conn = conectar_db()
    try:
        # AGREGADO: c.monto_inicial AS [MONTO INICIAL] en el SELECT
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
                c.monto_inicial AS [MONTO INICIAL],
                c.alquiler AS [ALQUILER],
                c.servicios_total AS [SERVICIOS_TOTAL],
                c.total_pagado AS [TOTAL_ESTIMADO]
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
        else:
            st.info("No se registran contratos en la base de datos bajo los criterios de búsqueda.")
    except Exception as e:
        st.error(f"Error de lectura en la planilla general: {e}")
    finally:
        conn.close()


# =====================================================================
# PESTAÑA 3: CONTROL DE COBRANZAS, HISTORIAL DE CAJA Y RECIBO PDF/WHATSAPP
# =====================================================================
with tab_pagos:
    st.subheader("💰 Registrar Cobro Mensual y Emitir Comprobantes")
    
    conn = conectar_db()
    # CORRECCIÓN: Agregamos c.monto_inicial a la consulta SQL
    query_activos = '''
        SELECT 
            c.codigo, p.alias_propiedad, 
            (p.calle || ' ' || p.numero || CASE WHEN p.departamento <> '' AND p.departamento IS NOT NULL THEN ', Dto: ' || p.departamento ELSE '' END) AS propiedad_dir,
            i.apellidos, i.nombres, i.telefono, i.email,
            c.prox_actualizacion, c.alquiler, c.indice, c.act_contrato, c.calc_duracion,
            c.mes_contrato, c.monto_honorarios, c.honorarios_pagados, c.monto_garantia, c.garantia, c.imp_inmobiliario, c.expensas, c.edesal, c.gas, c.municipalidad, c.ooss, c.cochera, c.servicios_total,
            c.servicios, c.inicio_contrato, c.monto_inicial
        FROM contratos c
        JOIN propiedades p ON c.propiedad_id = p.id
        JOIN inquilinos i ON c.inquilino_id = i.id
        WHERE c.estado = 'Activo'
        ORDER BY c.codigo DESC
    '''
    
    df_activos = pd.read_sql_query(query_activos, conn)
    conn.close()
    
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
            inicio_contrato_dt = datetime.strptime(c_datos['inicio_contrato'], "%d/%m/%Y").date()
            duracion_meses = int(c_datos['calc_duracion'] or 0)
            fin_contrato_dt = inicio_contrato_dt + dateutil.relativedelta.relativedelta(months=duracion_meses)
            
            opciones_actualizacion = {"Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24}
            act_contrato_sel = c_datos['act_contrato']
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
        
        val_base_expensas = float(c_datos['expensas'] or 0.0)
        val_base_edesal = float(c_datos['edesal'] or 0.0)
        val_base_gas = float(c_datos['gas'] or 0.0)
        val_base_municipalidad = float(c_datos['municipalidad'] or 0.0)
        val_base_cochera = float(c_datos['cochera'] or 0.0)
        
        monto_expensas = ed_col1.number_input("🏢 Expensas Consorcio ($):", min_value=0.0, value=val_base_expensas, step=500.0)
        monto_edesal = ed_col2.number_input("⚡ Luz (EDESAL) ($):", min_value=0.0, value=val_base_edesal, step=500.0)
        monto_gas = ed_col3.number_input("🔥 Gas Natural ($):", min_value=0.0, value=val_base_gas, step=500.0)
        monto_municipalidad = ed_col4.number_input("🏛️ Tasas Municipales ($):", min_value=0.0, value=val_base_municipalidad, step=200.0)
        monto_cochera = ed_col5.number_input("🚗 Alquiler Cochera ($):", min_value=0.0, value=val_base_cochera, step=1000.0)

        # --- CONCEPTOS ESPECIALES DE CONTRATO UNIFICADOS Y COMPORTAMIENTO IDÉNTICO ---
        st.markdown("#### 📑 Conceptos Especiales de Contrato")
        ed_col_esp1, ed_col_esp2 = st.columns(2)
        
        # Lógica de Honorarios
        total_honorarios_inquilino = float(c_datos['monto_inicial'] or 0.0)
        pagado_honorarios_inquilino = float(c_datos['honorarios_pagados'] or 0.0)
        saldo_honorarios_inquilino = max(0.0, total_honorarios_inquilino - pagado_honorarios_inquilino)
        
        monto_honorarios_pago = ed_col_esp1.number_input(
            "💼 Honorarios Inmobiliaria (Comisión Contrato) ($):", 
            min_value=0.0, 
            value=saldo_honorarios_inquilino, 
            step=1000.0, 
            help=f"Comisión Pactada Inquilino: ${total_honorarios_inquilino:.2f}. Pagado a la fecha: ${pagado_honorarios_inquilino:.2f}. Saldo restante: ${saldo_honorarios_inquilino:.2f}"
        )
        
        # Lógica de Garantía REFORMADA (Sincronizada con el campo 'garantia' de la carga)
        val_teorico_garantia = float(c_datos['monto_garantia'] or 0.0)
        try:
            pagado_garantia_inquilino = float(c_datos['garantia'] or 0.0)
        except ValueError:
            pagado_garantia_inquilino = 0.0
            
        saldo_garantia_inquilino = max(0.0, val_teorico_garantia - pagado_garantia_inquilino)
        
        monto_garantia_pago = ed_col_esp2.number_input(
            "🛡️ Respaldo con Monto Depositado (Garantía) ($):", 
            min_value=0.0, 
            value=saldo_garantia_inquilino, 
            step=5000.0, 
            help=f"Monto de garantía estipulado: ${val_teorico_garantia:.2f}. Depositado a la fecha: ${pagado_garantia_inquilino:.2f}. Saldo faltante: ${saldo_garantia_inquilino:.2f}"
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

        # Sumatoria dinámica de la parte variable de servicios modificada en pantalla + los nuevos conceptos
        val_imp_inmob = float(c_datos['imp_inmobiliario'] or 0.0) if "[Imp.Inmob: Inquilino]" in str(c_datos['servicios']) else 0.0
        val_ooss = float(c_datos['ooss'] or 0.0)
        
        monto_serv_pago = val_imp_inmob + monto_expensas + monto_edesal + monto_gas + monto_municipalidad + val_ooss + monto_cochera + monto_honorarios_pago + monto_garantia_pago

        cp_col1, cp_col2, cp_col3, cp_col4 = st.columns(4)
        val_base_alq = float(c_datos['alquiler'] or 0.0)
        monto_alq_pago = cp_col1.number_input("Monto Neto Alquiler ($):", min_value=0.0, value=val_base_alq, step=5000.0)
        
        # Muestra el total consolidado de conceptos adicionales de forma informativa
        cp_col2.number_input("Monto Adicionales / Servicios ($):", min_value=0.0, value=monto_serv_pago, disabled=True)
        
        total_pago_real = monto_alq_pago + monto_serv_pago
        cp_col3.number_input("TOTAL A RECAUDAR ($):", value=total_pago_real, disabled=True)
        metodo_pago = cp_col4.selectbox("Método de Pago:", ["Transferencia Bancaria", "Efectivo", "Depósito", "Cheque"])
        
        # 3. CONSTRUCCIÓN DE LA TABLA REACTIVA
        with st.expander("🔍 Ver conceptos consolidados del PDF oficial", expanded=True):
            st.markdown("Los siguientes conceptos e importes son los que se computarán de forma exacta en el comprobante:")
            
            items_vista = [{"Concepto Asociado": "Valor Locativo Neto (Alquiler Base)", "Monto": f"$ {monto_alq_pago:,.2f}"}]
            for item in desglose_pantalla_pdf:
                items_vista.append({"Concepto Asociado": item["Concepto"], "Monto": f"$ {item['Monto']:,.2f}"})
                
            st.table(pd.DataFrame(items_vista))

        mes_periodo_texto = st.text_input("Especificar Período Liquidado (Mes / Año):", value=datetime.now().strftime("%B %Y").capitalize())
        comentarios_pago = st.text_input("Notas / Comentarios Internos de Caja:", placeholder="Ej: Abonó del 1 al 5 en término")
        
        # --- BOTÓN IMPACTAR COBRO EN CAJA HISTORICA ---
        if st.button("📥 Impactar Cobro en Caja Histórica", type="primary"):
            conn = conectar_db()
            cursor = conn.cursor()
            try:
                # 1. Guarda el registro en el historial de cobros con los montos recalculados
                cursor.execute('''
                    INSERT INTO pagos_historial (contrato_id, periodo, monto_alquiler, monto_servicios, monto_total, fecha_pago, metodo_pago, comentarios)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (c_datos['codigo'], mes_periodo_texto, monto_alq_pago, monto_serv_pago, total_pago_real, datetime.now().strftime("%d/%m/%Y %H:%M"), metodo_pago, comentarios_pago))
                
                # 2. Avanzar automáticamente el contador del mes vivo del contrato
                nuevo_mes_vivo = (c_datos['mes_contrato'] or 1) + 1
                cursor.execute("UPDATE contratos SET mes_contrato = ? WHERE codigo = ?", (nuevo_mes_vivo, c_datos['codigo']))
                
                # 3. Pisar el valor del alquiler base con el monto recién cobrado
                cursor.execute("UPDATE contratos SET alquiler = ? WHERE codigo = ?", (monto_alq_pago, c_datos['codigo']))
                
                # 4. MODIFICACIÓN EXPLICITA: Acumula el cobro de honorarios directamente sobre lo que ya pagó el Inquilino
                nuevos_honorarios_acumulados = pagado_honorarios_inquilino + monto_honorarios_pago
                
                # 4b. NUEVA MODIFICACIÓN SÉNCRO: Acumula el cobro de garantía directamente sobre el Monto Depositado a la Fecha ('garantia')
                nueva_garantia_acumulada = pagado_garantia_inquilino + monto_garantia_pago
                
                # 5. Guardar los valores actualizados de manera persistente en la base de datos
                cursor.execute('''
                    UPDATE contratos 
                    SET expensas = ?, edesal = ?, gas = ?, municipalidad = ?, cochera = ?, honorarios_pagados = ?, garantia = ?, servicios_total = ?
                    WHERE codigo = ?
                ''', (monto_expensas, monto_edesal, monto_gas, monto_municipalidad, monto_cochera, nuevos_honorarios_acumulados, str(nueva_garantia_acumulada), monto_serv_pago, c_datos['codigo']))
                
                conn.commit()
                st.success(f"✔️ Cobro de {mes_periodo_texto} guardado de manera permanente en el Historial de Caja. ¡Contrato avanzado al Mes {nuevo_mes_vivo}!")
                st.info(f"🔄 Los honorarios pagados acumulados del inquilino subieron a: $ {nuevos_honorarios_acumulados:,.2f}")
                st.info(f"🛡️ El monto de garantía depositado a la fecha subió a: $ {nueva_garantia_acumulada:,.2f}")

                st.rerun()
                
            except Exception as e:
                st.error(f"Error al procesar el impacto en caja: {e}")
            finally:
                conn.close()

        st.markdown("---")
        st.markdown("### 🚀 Generador Inteligente de Comprobantes (WhatsApp & PDF Profesional)")
        
        txt_alquiler_fmt = f"$ {monto_alq_pago:,.2f}"
        txt_servicios_fmt = f"$ {monto_serv_pago:,.2f}"
        txt_total_fmt = f"$ {total_pago_real:,.2f}"
        servicios_str_whatsapp = "\n".join(detalles_recibo_servicios) if detalles_recibo_servicios else " - No se registran conceptos adicionales."
        
        mes_actual_num = c_datos['mes_contrato'] or 1
        meses_totales_contrato = c_datos['calc_duracion'] or 0
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
        
        btn_c1, btn_c2 = st.columns(2)
        
        with btn_c1:
            tel_inquilino = str(c_datos['telefono'] or "").strip()
            if tel_inquilino:
                tel_whatsapp = "54" + tel_inquilino if len(tel_inquilino) == 10 and not tel_inquilino.startswith("54") else tel_inquilino
                texto_url = urllib.parse.quote(texto_final_recibo)
                st.markdown(f'<a href="https://wa.me/{tel_whatsapp}?text={texto_url}" target="_blank"><button style="width:100%; padding:12px; background-color:#25D366; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">📲 Despachar Recibo por WhatsApp</button></a>', unsafe_allow_html=True)
            else:
                st.warning("⚠️ Inquilino sin celular válido.")
                
        with btn_c2:
            # --- EXPORTACIÓN AUTOMATIZADA A PDF PROFESIONAL DE ALTA FIDELIDAD ---
            html_pdf_profesional = f"""
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
            </style>
            </head>
            <body>
                <div class="invoice-card">
                    <table class="header-table">
                        <tr>
                            <td><h1 class="title-main">RECIBO DE ALQUILER</h1></td>
                            <td class="meta-text">
                                <strong>Comprobante N°:</strong> RC-00{c_datos['codigo']}-{mes_periodo_texto.replace(' ','')}<br>
                                <strong>Fecha Emisión:</strong> {datetime.now().strftime('%d/%m/%Y')}<br>
                                <strong>Período:</strong> {periodo_numerico_pdf} <br> <small style="color: #718096;">({mes_periodo_texto})</small>
                            </td>
                        </tr>
                    </table>
                    
                    <div class="section-title">Datos Comerciales del Contrato</div>
                    <table class="info-grid">
                        <tr>
                            <td width="15%"><strong>Locatario:</strong></td><td>{c_datos['apellidos']}, {c_datos['nombres']}</td>
                            <td width="15%"><strong>Propiedad:</strong></td><td>{c_datos['propiedad_dir']} ({c_datos['alias_propiedad']})</td>
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
                                <td style="text-align: right;">{txt_alquiler_fmt}</td>
                            </tr>
                            
                            {f"<tr><td>📌 Impuesto Inmobiliario Provincial</td><td style='text-align: right;'>$ {c_datos['imp_inmobiliario']:,.2f}</td></tr>" if c_datos['imp_inmobiliario'] and c_datos['imp_inmobiliario'] > 0 and "[Imp.Inmob: Inquilino]" in str(c_datos['servicios']) else ""}
                            {f"<tr><td>🏢 Expensas Consorcio</td><td style='text-align: right;'>$ {monto_expensas:,.2f}</td></tr>" if monto_expensas > 0 else ""}
                            {f"<tr><td>⚡ Energía Eléctrica (EDESAL)</td><td style='text-align: right;'>$ {monto_edesal:,.2f}</td></tr>" if monto_edesal > 0 else ""}
                            {f"<tr><td>🔥 Gas Natural</td><td style='text-align: right;'>$ {monto_gas:,.2f}</td></tr>" if monto_gas > 0 else ""}
                            {f"<tr><td>🏛️ Tasas Municipales</td><td style='text-align: right;'>$ {monto_municipalidad:,.2f}</td></tr>" if monto_municipalidad > 0 else ""}
                            {f"<tr><td>💧 Obras Sanitarias (OO.SS)</td><td style='text-align: right;'>$ {c_datos['ooss']:,.2f}</td></tr>" if c_datos['ooss'] and c_datos['ooss'] > 0 else ""}
                            {f"<tr><td>🚗 Alquiler Cochera Complementaria</td><td style='text-align: right;'>$ {monto_cochera:,.2f}</td></tr>" if monto_cochera > 0 else ""}
                            {f"<tr><td>💼 Honorarios Inmobiliaria (Comisión de Contrato)</td><td style='text-align: right;'>$ {monto_honorarios_pago:,.2f}</td></tr>" if monto_honorarios_pago > 0 else ""}
                            {f"<tr><td>🛡️ Respaldo con Monto Depositado (Depósito en Garantía)</td><td style='text-align: right;'>$ {monto_garantia_pago:,.2f}</td></tr>" if monto_garantia_pago > 0 else ""}
                            
                            <tr class="total-row">
                                <td>TOTAL CONSOLIDADO PERCIBIDO</td>
                                <td style="text-align: right;">{txt_total_fmt}</td>
                            </tr>
                        </tbody>
                    </table>
                    
                    <table class="info-grid" style="margin-top:20px;">
                        <tr><td><strong>Forma de Cancelación:</strong> {metodo_pago}</td></tr>
                    </table>
                    
                    <div style="text-align: right; margin-top: 40px;">
                        <div class="signature-line"></div>
                        <span style="font-size:13px; font-weight:bold; color:#4a5568;">Administración de Propiedades</span>
                    </div>
                    
                    <div class="footer-stamp">
                        Comprobante emitido de manera electrónica. Documento de respaldo archivado de manera conforme.
                    </div>
                </div>
                <script>window.print();</script>
            </body>
            </html>
            """
            st.download_button(
                label="🖨️ Descargar Comprobante PDF Corporativo",
                data=html_pdf_profesional,
                file_name=f"comprobante_oficial_C_{c_datos['codigo']}_{mes_periodo_texto.lower().replace(' ','_')}.html",
                mime="text/html",
                help="Genera un archivo optimizado de alta fidelidad. Al abrirlo, el sistema abrirá nativamente la ventana para guardar como PDF comercial."
            )


# =====================================================================
# PESTAÑA 4: MÓDULO DE HISTORIAL DE PAGOS COMPLETO (MEJORA 1 VISUALIZACIÓN)
# =====================================================================
with tab_historial_pagos:
    st.subheader("🗄️ Registro Completo de Caja y Balance Mensual")
    
    conn = conectar_db()
    query_historial = '''
        SELECT ph.id as [ID PAGO], c.codigo as [COD CONTRATO], p.alias_propiedad as [PROPIEDAD],
               (i.apellidos || ', ' || i.nombres) as [INQUILINO], ph.periodo as [PERIODO],
               ph.monto_alquiler as [ALQUILER ($)], ph.monto_servicios as [SERVICIOS ($)],
               ph.monto_total as [TOTAL ($)], ph.fecha_pago as [FECHA IMPACTO], ph.metodo_pago as [METODO]
        FROM pagos_historial ph
        JOIN contratos c ON ph.contrato_id = c.codigo
        JOIN propiedades p ON c.propiedad_id = p.id
        JOIN inquilinos i ON c.inquilino_id = i.id
        ORDER BY ph.id DESC
    '''
    df_historial = pd.read_sql_query(query_historial, conn)
    conn.close()
    
    if df_historial.empty:
        st.info("Aún no se registran cobros mensuales asentados de manera definitiva en el libro de caja.")
    else:
        # Filtros del historial
        f_periodo = st.text_input("Filtrar historial por palabra clave (Ej: Mayo o Efectivo):", placeholder="Escriba para filtrar...")
        if f_periodo:
            df_historial = df_historial[
                df_historial['PERIODO'].str.contains(f_periodo, case=False, na=False) |
                df_historial['INQUILINO'].str.contains(f_periodo, case=False, na=False) |
                df_historial['METODO'].str.contains(f_periodo, case=False, na=False)
            ]
            
        st.dataframe(df_historial, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("##### 📊 Resumen Estadístico de Caja Registrada")
        c_r1, c_r2, c_r3 = st.columns(3)
        c_r1.metric("Volumen Total Cobrado", f"$ {df_historial['TOTAL ($)'].sum():,.2f}")
        c_r2.metric("Puras Cuotas de Alquiler", f"$ {df_historial['ALQUILER ($)'].sum():,.2f}")
        c_r3.metric("Fondo de Reintegro de Servicios", f"$ {df_historial['SERVICIOS ($)'].sum():,.2f}")

# =====================================================================
# PESTAÑA 5: FORMULARIO REACTIVO DE CARGA DE CONTRATOS (EDICIÓN EN VIVO)
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
        inquilino_seleccionada = c2.selectbox("Seleccione el Inquilino (Apellido, Nombre):", lista_inquilinos, index=idx_inq, disabled=not permitir_edicion)
        state_contrato = c3.selectbox("Estado del Contrato:", estados_disponibles, index=idx_estado, disabled=not permitir_edicion)
        
        propiedad_id = dict_propiedades[propiedad_seleccionada]
        inquilino_id = dict_inquilinos[inquilino_seleccionada]

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
        
        # --- 2. FECHAS, PLAZOS Y DURACIÓN ---
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

        fecha_hoy = datetime.now().date()
        prox_actualizacion_calculada = inicio_contrato + dateutil.relativedelta.relativedelta(months=meses_a_sumar)

        while prox_actualizacion_calculada < fecha_hoy and prox_actualizacion_calculada <= fin_contrato:
            prox_actualizacion_calculada += dateutil.relativedelta.relativedelta(months=meses_a_sumar)

        necesita_renovacion = prox_actualizacion_calculada > fin_contrato

        diferencia_hoy = dateutil.relativedelta.relativedelta(fecha_hoy, inicio_contrato)
        total_meses_transcurridos = (diferencia_hoy.years * 12) + diferencia_hoy.months
        if total_meses_transcurridos < 0: total_meses_transcurridos = 0
        mes_actual_contrato_vivo = total_meses_transcurridos + 1

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
        
        monto_inicial = cv1.number_input("Monto Inicial ($):", min_value=0.0, step=5000.0, value=val_monto_ini, disabled=not permitir_edicion, key="monto_inicial_live")
        alquiler = cv2.number_input("Último Valor Cobrado ($):", min_value=0.0, step=5000.0, value=val_alq_ult, disabled=not permitir_edicion, key="alquiler_ultimo_live")
        
        cv_ind, cv_meses = st.columns(2)
        indices_disponibles = ["ICL", "IPC", "UVA", "Otro"]
        idx_ind = indices_disponibles.index(u[6]) if u and u[6] in indices_disponibles else 0
        
        indice_seleccionado = cv_ind.selectbox("Índice Aplicado:", indices_disponibles, index=idx_ind, disabled=not permitir_edicion)
        meses_atras = cv_meses.number_input("Intervalo de Meses para Ajustar:", min_value=1, max_value=24, value=int(meses_a_sumar), disabled=not permitir_edicion)
        
        indice_final = st.text_input("Especifique el Índice personalizado:", value=u[6] if u and idx_ind == 3 else "", placeholder="Ej: Ajuste Fijo", disabled=not permitir_edicion) if indice_seleccionado == "Otro" else indice_seleccionado

        codigo_rate = indice_final.lower()
        fecha_param_str = inicio_contrato.strftime("%Y-%m-%d")
        url_calculo_dinamica = f"https://arquiler.com/pwa?amount={int(alquiler)}&date={fecha_param_str}&months={meses_atras}&rate={codigo_rate}"
        

        #  CÓDIGO CORREGIDO:
        c_web1, c_web2 = st.columns([2, 3])
        c_web1.markdown(f"🔗 [Abrir panel en arquiler.com]({url_calculo_dinamica})")

        # Formateamos dinámicamente usando el valor actual de la variable 'alquiler'
        valor_por_defecto_fmt = f"{alquiler:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

        alquiler_actualizado_texto = c_web2.text_input(
        "Valor Actualizado obtenido ($):", 
        value=valor_por_defecto_fmt, # <--- Forzamos a que tome siempre el valor reflejado en 'Último Valor Cobrado'
        key="campo_alquiler_actualizado_text", 
        disabled=not permitir_edicion
        )


        alquiler_actualizado = limpiar_string_a_float(alquiler_actualizado_texto)
        
        valor_invalido_o_vacio = (alquiler_actualizado is None or alquiler_actualizado <= 0.0)
        alquiler_sin_cambios = (alquiler_actualizado == alquiler)
        
        bloqueo_por_actualizacion = False
        if necesita_renovacion or valor_invalido_o_vacio:
            bloqueo_por_actualizacion = True
        elif es_mes_de_actualizacion and alquiler_sin_cambios:
            bloqueo_por_actualizacion = True

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

        # --- 4. LIQUIDACIÓN DE IMPORTES DE AGENCIA ---
        st.markdown("### 4. Liquidación de Importes de Agencia")
        with st.container(border=True):
            st.markdown("##### **A) COMISION INMOBILIARIA (A cargo del Propietario - Retención Mensual)**")
            ch_prop1, ch_prop2 = st.columns(2)
            val_hon_pct = float(u[7]) if u and u[7] is not None else 5.0
            honorarios_pct = ch_prop1.number_input("Porcentaje de Administración (%):", min_value=0.0, value=val_hon_pct, step=0.5, disabled=not permitir_edicion, key="honorarios_pct_live")
            
            # --- REACTIVIDAD: Se calcula directamente con el valor de la caja 'alquiler_actualizado'
            retencion_mensual_estimated = alquiler_actualizado * (honorarios_pct / 100.0) if not valor_invalido_o_vacio else 0.0
            ret_mensual_fmt = f"$ {retencion_mensual_estimated:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            ch_prop2.text_input("Retención mensual calculada ($):", value=ret_mensual_fmt, disabled=True, key="retencion_mensual_live")
        
        with st.container(border=True):
            st.markdown("##### **B) HONORARIOS INMOBILIARIA (A cargo del Inquilino - Comisión de Contrato)**")
            ch_inq1, ch_inq2, ch_inq3 = st.columns(3)
            
            # 🟢 CORRECCIÓN: Leemos el índice 16 de la tupla u (monto_honorarios) en lugar del valor del alquiler (monto_inicial)
            val_hon_total = float(u[16]) if u and len(u) > 16 and u[16] is not None else 0.0
            honorarios_inquilino_total = ch_inq1.number_input("Monto Total de Comisión ($):", min_value=0.0, value=val_hon_total, step=5000.0, disabled=not permitir_edicion, key="hon_inq_total_live")
            
            val_cuotas_hon = int(u[17]) if u and len(u) > 17 and u[17] is not None else 1
            cuota_honorarios = ch_inq2.number_input("Cuotas pactadas para el pago:", min_value=1, value=val_cuotas_hon, step=1, disabled=not permitir_edicion, key="cuota_hon_live")
            
            val_hon_pagados = float(u[18]) if u and len(u) > 18 and u[18] is not None else 0.0
            honorarios_pagados = ch_inq3.number_input("Monto pagado a la fecha ($):", min_value=0.0, value=val_hon_pagados, step=5000.0, disabled=not permitir_edicion, key="hon_pagados_live")
            
            saldo_inquilino_hon = honorarios_inquilino_total - honorarios_pagados
            if saldo_inquilino_hon > 0: 
                saldo_hon_fmt = f"$ {saldo_inquilino_hon:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                st.warning(f"💵 Honorarios Inquilino: Queda un saldo de **{saldo_hon_fmt}** a financiar.")


        # --- 5. RESPALDO Y GARANTÍAS DEL CONTRATO ---
        st.markdown("### 5. Respaldo y Garantías del Contrato")
        st.markdown("##### **A) Respaldo con Documento Pagaré**")
        cg_pag1, cg_pag2 = st.columns(2)
        tiene_pag_idx = 1 if u and "Sí" in str(u[9]) else 0
        
        # 🟢 CORRECCIÓN DE KEY: cambiado a "tiene_pagare_live_sec5"
        tiene_pagare = cg_pag1.selectbox("¿Aplica Pagaré firmado?:", ["No", "Sí"], index=tiene_pag_idx, disabled=not permitir_edicion, key="tiene_pagare_live_sec5")
        
        # 🟢 CORRECCIÓN DE KEY: cambiado a "monto_pagare_live_sec5"
        monto_pagare = cg_pag2.number_input("Monto acordado del Pagaré ($):", min_value=0.0, value=0.0, step=10000.0, disabled=not permitir_edicion if tiene_pagare == "Sí" else True, key="monto_pagare_live_sec5")

        with st.container(border=True):
            st.markdown("##### **C) DEPÓSITO DE RESPALDO / GARANTÍA (A cargo del Inquilino)**")
            ch_dep1, ch_dep2 = st.columns(2)
            
            val_deposito_total = float(u[19]) if u and len(u) > 19 and u[19] is not None else 0.0
            
            # 🟢 CORRECCIÓN DE KEY: cambiado a "deposito_total_live_sec5"
            monto_deposito_total = ch_dep1.number_input("Monto Total de Depósito Pactado ($):", min_value=0.0, value=val_deposito_total, step=5000.0, disabled=not permitir_edicion, key="deposito_total_live_sec5")
            
            val_deposito_pagado = float(u[20]) if u and len(u) > 20 and u[20] is not None else 0.0
            deposito_pagados = ch_dep2.number_input("Monto de Depósito Reintegrado / Pagado a la fecha ($):", min_value=0.0, value=val_deposito_pagado, step=5000.0, disabled=not permitir_edicion, key="dep_pagados_live_sec5")
            
            saldo_inquilino_dep = max(0.0, monto_deposito_total - deposito_pagados)
            
            if saldo_inquilino_dep <= 0 and monto_deposito_total > 0:
                estado_garantia_calculado = "Depositada Completa"
            elif monto_deposito_total == 0:
                estado_garantia_calculado = "Sin Depósito"
            else:
                saldo_dep_fmt = f"$ {saldo_inquilino_dep:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                estado_garantia_calculado = f"Financiando (Saldo: {saldo_dep_fmt})"
                
                st.warning(f"💵 Depósito de Respaldo: Queda un saldo de **{saldo_dep_fmt}** a financiar.")

        # --- 6. DESGLOSE DE SERVICIOS MENSUALES ($) ---
        st.markdown("### 6. Desglose de Servicios Mensuales ($)")
        
        with st.container(border=True):
            st.markdown("##### **⚡ / 🔥 / 💧 / 🏛️ Servicios Públicos y Municipales**")
            g1_col1, g1_col2 = st.columns(2)
            
            with g1_col1:
                with st.container():
                    s_col5, s_col6 = st.columns([3, 2])
                    val_ede = float(u[12]) if u and u[12] is not None else 0.0
                    edesal = s_col5.number_input("Monto Electricidad ($):", min_value=0.0, value=val_ede, step=500.0, disabled=not permitir_edicion, key="edesal_live")
                    cargo_electricidad = s_col6.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_elec", disabled=not permitir_edicion)
                    num_nis = st.number_input("NIS Nro:", min_value=0, value=0, step=1, key="id_nis", disabled=not permitir_edicion)
                
                st.markdown("---")
                with st.container():
                    s_col7, s_col8 = st.columns([3, 2])
                    val_gas = float(u[13]) if u and u[13] is not None else 0.0
                    gas = s_col7.number_input("Monto Gas ($):", min_value=0.0, value=val_gas, step=500.0, disabled=not permitir_edicion, key="gas_live")
                    cargo_gas = s_col8.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_gas", disabled=not permitir_edicion)
                    cuenta_gas = st.text_input("Nro de Cuenta (Gas):", key="id_cta_gas", disabled=not permitir_edicion)
                    
            with g1_col2:
                with st.container():
                    s_col9, s_col10 = st.columns([3, 2])
                    val_mun = float(u[14]) if u and u[14] is not None else 0.0
                    municipalidad = s_col9.number_input("Monto Municipalidad ($):", min_value=0.0, value=val_mun, step=500.0, disabled=not permitir_edicion, key="municipalidad_live")
                    cargo_municipalidad = s_col10.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_mun", disabled=not permitir_edicion)
                    finca_mun = st.text_input("Finca Nro:", key="id_finca_mun", disabled=not permitir_edicion)
                
                st.markdown("---")
                with st.container():
                    s_col11, s_col12 = st.columns([3, 2])
                    val_oos = float(u[15]) if u and u[15] is not None else 0.0
                    ooss = s_col11.number_input("Monto OO.SS. ($):", min_value=0.0, value=val_oos, step=500.0, disabled=not permitir_edicion, key="ooss_live")
                    cargo_ooss = s_col12.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_oos", disabled=not permitir_edicion)
                    cuenta_oos = st.text_input("Nro de Cuenta (OO.SS.):", key="id_cta_oos", disabled=not permitir_edicion)

        with st.container(border=True):
            st.markdown("##### **🏢 Complementos de Propiedad y Consorcio**")
            g2_col1, g2_col2 = st.columns(2)
            
            with g2_col1:
                s_col3, s_col4 = st.columns([3, 2])
                val_exp = float(u[10]) if u and u[10] is not None else 0.0
                expensas = s_col3.number_input("Monto Expensas ($):", min_value=0.0, value=val_exp, step=500.0, disabled=not permitir_edicion, key="expensas_live")
                cargo_expensas = s_col4.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_exp", disabled=not permitir_edicion)
                
            with g2_col2:
                s_col13, s_col14 = st.columns([3, 2])
                val_coch = float(u[16]) if u and len(u) > 16 and u[16] is not None else 0.0
                cochera = s_col13.number_input("Monto Cochera ($):", min_value=0.0, value=val_coch, step=1000.0, disabled=not permitir_edicion, key="cochera_live")
                cargo_cochera = s_col14.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_coch", disabled=not permitir_edicion)

        with st.container(border=True):
            st.markdown("##### **📌 Impuesto Provincial Individual**")
            s_col1, s_col2 = st.columns([3, 2])
            val_imp_inmob = float(u[9]) if u and u[9] is not None else 0.0
            imp_inmobiliario = s_col1.number_input("Imp. Inmobiliario ($):", min_value=0.0, value=val_imp_inmob, step=500.0, disabled=not permitir_edicion, key="imp_inmob_live")
            cargo_inmobiliario = s_col2.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=1, key="cargo_inmob", disabled=not permitir_edicion)

        notas_adicionales_input = st.text_input("Notas Adicionales de Servicios:", disabled=not permitir_edicion, key="notas_servicios_live")
        
        str_identificadores = f"[NIS: {num_nis}] [Cta Gas: {cuenta_gas}] [Finca: {finca_mun}] [Cta OO.SS.: {cuenta_oos}]"
        detalles_pagos_str = f"| Elec: {cargo_electricidad} | Gas: {cargo_gas} | Mun: {cargo_municipalidad} | OOSS: {cargo_ooss} | Exp: {cargo_expensas} | Inmob: {cargo_inmobiliario}"
        
        if notas_adicionales_input.strip():
            servicios_detalle = f"{str_identificadores} {detalles_pagos_str} | Notas: {notas_adicionales_input}"
        else:
            servicios_detalle = f"{str_identificadores} {detalles_pagos_str}"

        # --- REACTIVIDAD EXPLICITA: Suma los servicios que dicen "Inquilino" en vivo
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
        
        # El neto toma el valor convertido de lo que el usuario escribió arriba en "Valor Actualizado obtenido"
        base_calculo_cobro = float(alquiler_actualizado) if not valor_invalido_o_vacio else 0.0
        
        alquiler_cobrado = cp_1.number_input(
            "Monto Neto de Alquiler Cobrado ($):", 
            min_value=0.0, 
            value=base_calculo_cobro, 
            step=5000.0, 
            disabled=True,
            key="alquiler_cobrado_live"  # <--- Atrapa el cambio manual si se quiere alterar antes de guardar
        )
        
        # El total final responde directamente a la suma de lo que está tipiado en "Monto Neto Cobrado" + "Servicios"
        total_pagado_calculado = alquiler_cobrado + servicios_total_calculado
        
        cp_2.number_input("Total de Servicios Adicionados ($):", value=float(servicios_total_calculado), disabled=True, key="box_total_servicios_live")
        cp_3.number_input("TOTAL CONSOLIDADO COBRADO (Caja) ($):", value=float(total_pagado_calculado), disabled=True, key="box_total_caja_live")

        st.markdown("---")
        
        boton_deshabilitado = (not permitir_edicion) or bloqueo_por_actualizacion or necesita_renovacion
        texto_boton = "💾 Actualizar Contrato Existente" if (contrato_previo and "Actualizar" in modo_guardado) else "💾 Guardar y Registrar Contrato Completo"
        
        btn_guardar_final = st.button(texto_boton, disabled=boton_deshabilitado, type="primary", key="btn_guardar_contrato_final")
        
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
# PESTAÑA 6: CARGA DE AUXILIARES (INQUILINOS / PROPIEDADES)
# =====================================================================
with tab_auxiliares:
    st.subheader("⚙️ Panel de Configuración de Entidades")
    col_aux1, col_aux2 = st.columns(2)
    
    with col_aux1:
        st.markdown("#### Registrar Nuevo Inquilino")
        with st.form("form_inquilino", clear_on_submit=True):
            apellidos = st.text_input("Apellidos:", placeholder="Ej: Pérez Rossi")
            nombres = st.text_input("Nombres:", placeholder="Ej: Juan Carlos")
            dni = st.text_input("DNI (Sin puntos):", placeholder="Ej: 34567890")
            email = st.text_input("Email:", placeholder="Ej: juancarlos@gmail.com")
            tel = st.text_input("Teléfono Celular (10 dígitos):", placeholder="Ej: 2657123456")
            
            btn_inq = st.form_submit_button("Guardar Inquilino")
            if btn_inq and apellidos and nombres:
                tel_limpio = tel.strip().replace(" ", "").replace("-", "")
                email_limpio = email.strip().lower()
                dni_limpio = dni.strip().replace(".", "").replace(" ", "")
                                
                if dni_limpio and not dni_limpio.isdigit():
                    st.error("⚠️ El DNI debe contener únicamente números.")
                elif tel_limpio and not re.match(r"^[1-9]\d{9}$", tel_limpio):
                    st.error("⚠️ Teléfono inválido (Debe tener 10 dígitos sin 0 ni 15).")
                else:

                    apellidos_fmt = apellidos.strip().upper()  # Todo MAYÚSCULAS
                    nombres_fmt = nombres.strip().title()      # Primera Letra Mayúscula

                    conn = conectar_db()
                    cursor = conn.cursor()
                    try:
                        cursor.execute("INSERT INTO inquilinos (apellidos, nombres, dni, telefono, email) VALUES (?, ?, ?, ?, ?)", 
                        (apellidos_fmt, nombres_fmt, dni_limpio, tel_limpio, email_limpio))
                        conn.commit()
                        st.success(f"✔️ Inquilino {apellidos}, {nombres} guardado.")
                    except sqlite3.IntegrityError:
                        st.error("Ya existe un inquilino registrado con este nombre.")
                    finally:
                        conn.close()
                    
    with col_aux2:
        st.markdown("#### Registrar Nueva Propiedad")
        with st.form("form_propiedad", clear_on_submit=True):
            alias = st.text_input("Alias de la Propiedad:", placeholder="Ej: Dpto 3B - Torre Mitre")
            calle = st.text_input("Calle / Av:", placeholder="Ej: Av. Mitre")
            numero = st.text_input("Número:", placeholder="Ej: 1450")
            depto = st.text_input("Departamento (Opcional):", placeholder="Ej: Piso 3 - Dpto B")
            
            btn_prop = st.form_submit_button("Guardar Propiedad")
            if btn_prop and alias and calle and numero:
                conn = conectar_db()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO propiedades (alias_propiedad, calle, numero, departamento) VALUES (?, ?, ?, ?)", 
                                   (alias.strip(), calle.strip(), numero.strip(), depto.strip()))
                    conn.commit()
                    st.success(f"Propiedad '{alias}' registrada.")
                except sqlite3.IntegrityError:
                    st.error("El Alias de la propiedad ya se encuentra registrado.")
                finally:
                    conn.close()


# =====================================================================
    # MÓDULO DE EDICIÓN / MODIFICACIÓN DE DATOS EXISTENTES
    # =====================================================================
    st.markdown("---")
    st.markdown("### 🔄 Modificar Datos de Inquilinos o Propiedades Existentes")
    
    # Consultamos los desplegables actualizados del sistema
    dict_propiedades_edit, dict_inquilinos_edit = obtener_datos_desplegables()
    
    tipo_edicion = st.radio("Seleccione qué desea editar:", ["Inquilino", "Propiedad"], horizontal=True, key="radio_tipo_edicion")
    
    if tipo_edicion == "Inquilino":
        if not dict_inquilinos_edit:
            st.info("No hay inquilinos registrados para editar.")
        else:
            inquilino_a_editar = st.selectbox("Seleccione el Inquilino a modificar:", list(dict_inquilinos_edit.keys()), key="select_inq_edit")
            id_inq_edit = dict_inquilinos_edit[inquilino_a_editar]
            
            # Buscamos los datos actuales en la base de datos
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("SELECT apellidos, nombres, dni, telefono, email FROM inquilinos WHERE id = ?", (id_inq_edit,))
            datos_inq = cursor.fetchone()
            conn.close()
            
            if datos_inq:
                with st.form("form_editar_inquilino"):
                    st.markdown(f"**Editando ID Interno: {id_inq_edit}**")
                    edit_apellido = st.text_input("Apellidos:", value=datos_inq[0])
                    edit_nombre = st.text_input("Nombres:", value=datos_inq[1])
                    edit_dni = st.text_input("DNI / CUIT:", value=datos_inq[2] if datos_inq[2] else "")
                    edit_tel = st.text_input("Teléfono:", value=datos_inq[3] if datos_inq[3] else "")
                    edit_email = st.text_input("Email:", value=datos_inq[4] if datos_inq[4] else "")
                    
                    btn_modificar_inq = st.form_submit_button("💾 Guardar Cambios Inquilino", type="primary")
                    
                    if btn_modificar_inq:
                        if edit_apellido.strip() and edit_nombre.strip():
                            edit_apellido_fmt = edit_apellido.strip().upper()  # Todo MAYÚSCULAS
                            edit_nombre_fmt = edit_nombre.strip().title()      # Primera Letra Mayúscula
                            conn = conectar_db()
                            cursor = conn.cursor()
                            try:

                                

                                cursor.execute('''
                                    UPDATE inquilinos 
                                    SET apellidos = ?, nombres = ?, dni = ?, telefono = ?, email = ? 
                                    WHERE id = ?
                                ''', (edit_apellido_fmt, edit_nombre_fmt, edit_dni.strip(), edit_tel.strip(), edit_email.strip(), id_inq_edit))
                                conn.commit()
                                st.success(f"¡Datos de {edit_apellido}, {edit_nombre} actualizados con éxito!")
                                st.rerun()
                            except sqlite3.IntegrityError:
                                st.error("Ya existe otro inquilino registrado con ese mismo Nombre y Apellido.")
                            finally:
                                conn.close()
                        else:
                            st.error("Los campos Nombre y Apellido son obligatorios.")

    elif tipo_edicion == "Propiedad":
        if not dict_propiedades_edit:
            st.info("No hay propiedades registradas para editar.")
        else:
            propiedad_a_editar = st.selectbox("Seleccione la Propiedad a modificar:", list(dict_propiedades_edit.keys()), key="select_prop_edit")
            id_prop_edit = dict_propiedades_edit[propiedad_a_editar]
            
            # Buscamos los datos actuales de la propiedad
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("SELECT alias_propiedad, calle, numero, departamento FROM propiedades WHERE id = ?", (id_prop_edit,))
            datos_prop = cursor.fetchone()
            conn.close()
            
            if datos_prop:
                with st.form("form_editar_propiedad"):
                    st.markdown(f"**Editando ID Interno: {id_prop_edit}**")
                    edit_alias = st.text_input("Alias de la Propiedad:", value=datos_prop[0])
                    edit_calle = st.text_input("Calle / Av:", value=datos_prop[1])
                    edit_numero = st.text_input("Número:", value=datos_prop[2])
                    edit_depto = st.text_input("Departamento / Piso / Bloque (Opcional):", value=datos_prop[3] if datos_prop[3] else "")
                    
                    btn_modificar_prop = st.form_submit_button("💾 Guardar Cambios Propiedad", type="primary")
                    
                    if btn_modificar_prop:
                        if edit_alias.strip() and edit_calle.strip() and edit_numero.strip():
                            conn = conectar_db()
                            cursor = conn.cursor()
                            try:
                                cursor.execute('''
                                    UPDATE propiedades 
                                    SET alias_propiedad = ?, calle = ?, numero = ?, departamento = ? 
                                    WHERE id = ?
                                ''', (edit_alias.strip(), edit_calle.strip(), edit_numero.strip(), edit_depto.strip(), id_prop_edit))
                                conn.commit()
                                st.success(f"¡Propiedad '{edit_alias}' modificada con éxito!")
                                st.rerun()
                            except sqlite3.IntegrityError:
                                st.error("El Alias ingresado ya pertenece a otra propiedad.")
                            finally:
                                conn.close()
                        else:
                            st.error("El Alias, Calle y Número son campos obligatorios.")