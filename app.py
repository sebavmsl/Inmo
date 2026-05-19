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
    
    # Tabla 1: INQUILINOS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inquilinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apellidos TEXT NOT NULL,
            nombres TEXT NOT NULL,
            dni_cuit TEXT,
            telefono TEXT,
            UNIQUE(apellidos, nombres)
        )
    ''')
    
    # Tabla 2: PROPIEDADES
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS propiedades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias_propiedad TEXT NOT NULL UNIQUE,
            calle TEXT NOT NULL,
            numero TEXT NOT NULL,
            departamento TEXT
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
            servicios TEXT,
            honorarios REAL,
            monto_honorarios REAL,
            cuota_honorarios INTEGER,
            honorarios_pagados REAL,
            tipo_garantias TEXT,
            monto_garantia REAL,
            garantia TEXT,
            imp_inmobiliario REAL,
            expensas REAL,
            edesal REAL, -- Mantenido estructuralmente en BD para consistencia (Electricidad)
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


# =====================================================================
# 2. INTERFAZ DE USUARIO CONFIGURACIÓN GENERAL (Streamlit)
# =====================================================================
st.set_page_config(page_title="Gestión de Alquileres Relacional", layout="wide")
st.title("🏢 Sistema Integral de Gestión de Alquileres")
st.caption("Entorno web avanzado con base de datos SQLite relacional y campos de dirección atomizados.")

tab_planilla, tab_carga, tab_auxiliares = st.tabs([
    "📊 Planilla General", 
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
        filtro_estado = st.multiselect("Filtrar por Estado:", ["Activo", "Vencido", "Inhabitado", "Finalizado", "Cancelado"], default=["Activo"])
    
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
# FUNCIÓN AUXILIAR: TRADUCTOR DE TEXTO A NÚMERO
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
# PESTAÑA 2: FORMULARIO DE CARGA DE CONTRATOS
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
                           act_contrato, indice, honorarios, monto_garantia, tipo_garantias,
                           imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, cochera
                    FROM contratos 
                    ORDER BY codigo DESC LIMIT 1
                ''')
                return cursor.fetchone()
            except Exception:
                return None
            finally:
                conn.close()

        if "ultimo_contrato" not in st.session_state:
            st.session_state.ultimo_contrato = obtener_ultimo_contrato()

        u = st.session_state.ultimo_contrato
            
        with st.form("formulario_contratos_relacional", clear_on_submit=False):
            
            # --- GUARDADO E IMPACTO EN BD ---
            def procesar_guardado_contrato(
                propiedad_id, inquilino_id, state_contrato, inicio_contrato, fin_contrato,
                duracion_meses_calculada, act_contrato_seleccionado, indice_final, monto_inicial, alquiler,
                prox_actualizacion_calculada, total_meses_transcurridos, mes_actualizacion_calculado,
                alquiler_actualizado, honorarios_pct, retencion_mensual_estimated, cuota_honorarios, honorarios_pagados,
                tiene_pagare, monto_pagare, monto_deposito_total, estado_garantia_calculado, imp_inmobiliario,
                expensas, electricidad, gas, municipalidad, ooss, servicios_total_calculado,
                m_coch_liq, alquiler_cobrado, total_pagado_calculado, servicios_detalle
            ):
                alq_act_fmt = f"${alquiler_actualizado:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                m_pag_fmt = f"${monto_pagare:,.0f}".replace(",", "v").replace(".", ",").replace("v", ".")
                
                detalle_garantia_unificado = f"Pagaré: {tiene_pagare} ({m_pag_fmt}) | Depósito financiado"
                registro_distribucion = f"[Alq.Actualizado: {alq_act_fmt}] {servicios_detalle}".strip()
                
                inicio_str = inicio_contrato.strftime('%Y-%m-%d')
                fin_str = fin_contrato.strftime('%Y-%m-%d')
                prox_act_str = prox_actualizacion_calculada.strftime('%Y-%m-%d')
                
                conn = conectar_db()
                cursor = conn.cursor()
                try:
                    if state_contrato == "Activo":
                        cursor.execute('''
                            UPDATE contratos 
                            SET estado = 'Finalizado' 
                            WHERE propiedad_id = ? AND estado = 'Activo'
                        ''', (propiedad_id,))
                        conn.commit()
                    
                    cursor.execute('''
                        INSERT INTO contratos (
                            propiedad_id, inquilino_id, estado, inicio_contrato, fin_contrato,
                            calc_duracion, act_contrato, indice, monto_inicial, alquiler, prox_actualizacion,
                            mes_contrato, mes_actualizacion_contrato, servicios, honorarios, monto_honorarios,
                            cuota_honorarios, honorarios_pagados, tipo_garantias, monto_garantia, garantia,
                            imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, servicios_total,
                            cochera, alquiler_cobrado, total_pagado
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        propiedad_id, inquilino_id, state_contrato, inicio_str, fin_str,
                        duracion_meses_calculada, act_contrato_seleccionado, indice_final, monto_inicial, alquiler, prox_act_str,
                        total_meses_transcurridos, mes_actualizacion_calculado, registro_distribucion, honorarios_pct, retencion_mensual_estimated,
                        cuota_honorarios, honorarios_pagados, detalle_garantia_unificado, monto_deposito_total, estado_garantia_calculado,
                        imp_inmobiliario, expensas, electricidad, gas, municipalidad, ooss, servicios_total_calculado,
                        m_coch_liq, alquiler_cobrado, total_pagado_calculado
                    ))
                    conn.commit()
                    
                    st.session_state.ultimo_contrato = obtener_ultimo_contrato()
                    st.success("✔️ Contrato completo guardado con éxito en la base de datos.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error de base de datos al impactar el contrato: {e}")
                finally:
                    conn.close()

            # SECCIÓN 1: DATOS MAESTROS ENTIDADES
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
            
            fecha_primer_dia_actual = datetime.now().replace(day=1).date()
            fecha_primer_dia_vencimiento = fecha_primer_dia_actual + dateutil.relativedelta.relativedelta(years=2)

            # SECCIÓN 2: FECHAS Y PLAZOS
            st.markdown("### 2. Fechas, Plazos y Duración (Automatizados)")
            cf1, cf2 = st.columns(2)
            inicio_contrato = cf1.date_input("Inicio del Contrato:", value=fecha_primer_dia_actual, format="DD/MM/YYYY", disabled=not permitir_edicion)
            fin_contrato = cf2.date_input("Fin del Contrato:", value=fecha_primer_dia_vencimiento, format="DD/MM/YYYY", disabled=not permitir_edicion)
            
            cf3, cf4, cf5 = st.columns([2, 1, 1])
            opciones_actualizacion = {
                "Mensual": 1, "Bimensual": 2, "Trimestral": 3, "Cuatrimestral": 4, "Semestral": 6, "Anual": 12, "Bianual": 24
            }
            idx_act = list(opciones_actualizacion.keys()).index(u[5]) if u and u[5] in opciones_actualizacion else 4
            
            act_contrato_seleccionado = cf3.selectbox("Actualización Contrato (Frecuencia):", list(opciones_actualizacion.keys()), index=idx_act, disabled=not permitir_edicion)
            meses_a_sumar = opciones_actualizacion[act_contrato_seleccionado]
            
            fecha_hoy = datetime.now().date()
            prox_actualizacion_calculada = inicio_contrato + dateutil.relativedelta.relativedelta(months=meses_a_sumar)
            
            if meses_a_sumar > 0:
                while prox_actualizacion_calculada < fecha_hoy and prox_actualizacion_calculada <= fin_contrato:
                    prox_actualizacion_calculada += dateutil.relativedelta.relativedelta(months=meses_a_sumar)
            
            necesita_renovacion = prox_actualizacion_calculada > fin_contrato

            with cf4:
                if necesita_renovacion:
                    st.markdown(
                        """
                        <label style="font-size: 14px; color: rgb(49, 51, 63); font-weight: 400; display: block; margin-bottom: 4px;">Próxima Actualización:</label>
                        <div style="
                            background-color: #ffe6e6; color: #cc0000; border: 1px solid #ff9999; 
                            padding: 6px 12px; border-radius: 8px; font-weight: bold; text-align: center;
                            font-size: 14px; line-height: 1.6; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                        ">
                            🔄 RENOVAR
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                else:
                    st.date_input("Próxima Actualización:", value=prox_actualizacion_calculada, format="DD/MM/YYYY", disabled=True)
            
            fin_con_un_dia_mas = fin_contrato + dateutil.relativedelta.relativedelta(days=1)
            diff_contrato = dateutil.relativedelta.relativedelta(fin_con_un_dia_mas, inicio_contrato)
            duracion_meses_calculada = (diff_contrato.years * 12) + diff_contrato.months
            cf5.text_input("Duración del Contrato:", value=f"{duracion_meses_calculada} meses", disabled=True)
            
            diferencia_hoy = dateutil.relativedelta.relativedelta(fecha_hoy, inicio_contrato)
            total_meses_transcurridos = (diferencia_hoy.years * 12) + diferencia_hoy.months
            if total_meses_transcurridos < 0: total_meses_transcurridos = 0
            mes_actualizacion_calculado = (total_meses_transcurridos % meses_a_sumar) + 1

            btn_sec1_2 = st.form_submit_button("💾 Guardar Contrato Completo", key="btn_guardar_seccion_1_2", disabled=not permitir_edicion)

            # SECCIÓN 3: VALORES ECONÓMICOS E ÍNDICES
            st.markdown("### 3. Valores Económicos e Índices")
            cv1, cv2, cv3 = st.columns(3)
            
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

            valor_predeterminado_fmt = f"{alquiler:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            
            alquiler_actualizado_texto = c_web2.text_input(
                "Valor Actualizado obtenido ($):", 
                value=valor_predeterminado_fmt, 
                key="campo_alquiler_actualizado_text", 
                disabled=not permitir_edicion,
                help="Por defecto igual al último valor cobrado. Podés editarlo separando miles con puntos (Ej: 427.473)"
            )
            alquiler_actualizado = limpiar_string_a_float(alquiler_actualizado_texto)
            
            if necesita_renovacion:
                st.error("🚨 Estado del Período: **RENOVAR** (La fecha de próxima actualización excede el fin del contrato)")
            else:
                st.text_input("Estado del Período:", value=f"Mes {mes_actualizacion_calculado} de {act_contrato_seleccionado}", disabled=True)

            btn_sec3 = st.form_submit_button("💾 Guardar Contrato Completo", key="btn_guardar_seccion_3", disabled=not permitir_edicion)

            # SECCIÓN 4: LIQUIDACIONES E IMPORTES DE AGENCIA
            st.markdown("### 4. Liquidación de Importes de Agencia")
            
            with st.container(border=True):
                st.markdown("##### **A) COMISION INMOBILIARIA (A cargo del Propietario - Retención Mensual)**")
                ch_prop1, ch_prop2 = st.columns(2)
                
                val_hon_pct = float(u[7]) if u and u[7] is not None else 5.0
                honorarios_pct = ch_prop1.number_input("Porcentaje de Administración (%):", min_value=0.0, value=val_hon_pct, step=0.5, disabled=not permitir_edicion)
                retencion_mensual_estimated = alquiler_actualizado * (honorarios_pct / 100.0)
                
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

            btn_sec4 = st.form_submit_button("💾 Guardar Contrato Completo", key="btn_guardar_seccion_4", disabled=not permitir_edicion)

            # SECCIÓN 5: RESPALDO Y GARANTÍAS
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
            estado_garantia_calculado = "Depositada" if saldo_deposito == 0 and monto_deposito_total > 0 else (f"Parcial ({cuotas_deposito} ctis)" if saldo_deposito > 0 and deposito_pagado > 0 else "Pendiente")
            cg_dep4.text_input("Estado del Depósito:", value=estado_garantia_calculado, disabled=True)

            btn_sec5 = st.form_submit_button("💾 Guardar Contrato Completo", key="btn_guardar_seccion_5", disabled=not permitir_edicion)

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
                        electricidad = s_col5.number_input("Monto Electricidad ($):", min_value=0.0, value=val_ede, step=500.0, disabled=not permitir_edicion)
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
                    val_exp = float(u[11]) if u and u[11] is not None else 0.0
                    expensas = s_col3.number_input("Monto Expensas ($):", min_value=0.0, value=val_exp, step=500.0, disabled=not permitir_edicion)
                    cargo_expensas = s_col4.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_exp", disabled=not permitir_edicion)
                    
                with g2_col2:
                    s_col13, s_col14 = st.columns([3, 2])
                    val_coch = float(u[16]) if u and u[16] is not None else 0.0
                    cochera = s_col13.number_input("Monto Cochera ($):", min_value=0.0, value=val_coch, step=1000.0, disabled=not permitir_edicion)
                    cargo_cochera = s_col14.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_coch", disabled=not permitir_edicion)

            # --- GRUPO C: IMPUESTO PROVINCIAL ESTRUCTURAL ---
            with st.container(border=True):
                st.markdown("##### **📌 Impuesto Provincial Individual**")
                s_col1, s_col2 = st.columns([3, 2])
                val_imp_inmob = float(u[10]) if u and u[10] is not None else 0.0
                imp_inmobiliario = s_col1.number_input("Imp. Inmobiliario ($):", min_value=0.0, value=val_imp_inmob, step=500.0, disabled=not permitir_edicion)
                cargo_inmobiliario = s_col2.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=1, key="cargo_inmob", disabled=not permitir_edicion)

            # NOTAS GENERALES
            st.text(" ") 
            notas_adicionales_input = st.text_input("Notas Adicionales de Servicios:", disabled=not permitir_edicion)
            
            # Consolidación estructurada para el registro 'servicios'
            str_identificadores = f"[NIS: {num_nis}] [Cta Gas: {cuenta_gas}] [Finca: {finca_mun}] [Cta OO.SS.: {cuenta_oos}]"
            servicios_detalle = f"{str_identificadores} | {notas_adicionales_input}" if notas_adicionales_input.strip() else str_identificadores

            # NUEVO: Botón de guardado repetido para la sección 6
            btn_sec6 = st.form_submit_button("💾 Guardar Contrato Completo", key="btn_guardar_seccion_6", disabled=not permitir_edicion)

            # --- CALCULO TOTAL DE LIQUIDACIÓN ---
            m_inmob_liq = imp_inmobiliario if cargo_inmobiliario == "Inquilino" else 0.0
            m_exp_liq = expensas if cargo_expensas == "Inquilino" else 0.0
            m_elec_liq = electricidad if cargo_electricidad == "Inquilino" else 0.0
            m_gas_liq = gas if cargo_gas == "Inquilino" else 0.0
            m_mun_liq = municipalidad if cargo_municipalidad == "Inquilino" else 0.0
            m_oos_liq = ooss if cargo_ooss == "Inquilino" else 0.0
            m_coch_liq = cochera if cargo_cochera == "Inquilino" else 0.0
            servicios_total_calculado = (m_inmob_liq + m_exp_liq + m_elec_liq + m_gas_liq + m_mun_liq + m_oos_liq)
            
            # SECCIÓN 7: CAJA Y LIQUIDACIÓN DINÁMICA
            st.markdown("### 7. Caja y Liquidación Dinámica")
            col_liq1, col_liq2 = st.columns(2)
            with col_liq1:
                alquiler_cobrado = st.number_input("Alquiler Cobrado ($):", min_value=0.0, step=5000.0, value=float(alquiler_actualizado), disabled=not permitir_edicion)
            with col_liq2:
                total_pagado_calculado = alquiler_cobrado + m_coch_liq + servicios_total_calculado
                st.text("") 
                total_caja_fmt = f"$ {total_pagado_calculado:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                st.metric(label="Consolidado Total de Caja (A ingresar)", value=total_caja_fmt)

            btn_final = st.form_submit_button("💾 Guardar Contrato Completo", key="btn_guardar_seccion_final", disabled=not permitir_edicion)

            # Actualización del disparador lógico para incluir btn_sec6
            if btn_sec1_2 or btn_sec3 or btn_sec4 or btn_sec5 or btn_sec6 or btn_final:
                procesar_guardado_contrato(
                    propiedad_id=propiedad_id, inquilino_id=inquilino_id, state_contrato=state_contrato,
                    inicio_contrato=inicio_contrato, fin_contrato=fin_contrato, duracion_meses_calculada=duracion_meses_calculada,
                    act_contrato_seleccionado=act_contrato_seleccionado, indice_final=indice_final, monto_inicial=monto_inicial,
                    alquiler=alquiler, prox_actualizacion_calculada=prox_actualizacion_calculada, total_meses_transcurridos=total_meses_transcurridos,
                    mes_actualizacion_calculado=mes_actualizacion_calculado, alquiler_actualizado=alquiler_actualizado, honorarios_pct=honorarios_pct,
                    retencion_mensual_estimated=retencion_mensual_estimated, cuota_honorarios=cuota_honorarios, honorarios_pagados=honorarios_pagados,
                    tiene_pagare=tiene_pagare, monto_pagare=monto_pagare, monto_deposito_total=monto_deposito_total, estado_garantia_calculado=estado_garantia_calculado,
                    imp_inmobiliario=imp_inmobiliario, expensas=expensas, electricidad=electricidad, gas=gas,
                    municipalidad=municipalidad, ooss=ooss, servicios_total_calculado=servicios_total_calculado, m_coch_liq=m_coch_liq,
                    alquiler_cobrado=alquiler_cobrado, total_pagado_calculado=total_pagado_calculado, servicios_detalle=servicios_detalle
                )


# =====================================================================
# PESTAÑA 3: BASES AUXILIARES (CON CAMPOS SEPARADOS)
# =====================================================================
with tab_auxiliares:
    st.subheader("⚙️ Gestión de Tablas Maestras Auxiliares")
    col_a, col_b = st.columns(2)
    
    # SUB-FORMULARIO: INQUILINOS
    with col_a:
        st.markdown("#### 👤 Registrar Nuevo Inquilino")
        with st.form("form_inquilino", clear_on_submit=True):
            apellidos = st.text_input("Apellidos (ej: Pérez / Gómez Pasquale):")
            nombres = st.text_input("Nombres (ej: Juan Carlos):")
            dni = st.text_input("DNI:")
            tel = st.text_input(
                "Teléfono de Contacto (10 dígitos exactos, sin 0 inicial):", 
                max_chars=10, 
                placeholder="Ej: 2657123456"
            )
            
            btn_i = st.form_submit_button("Guardar Inquilino")
            
            if btn_i and apellidos and nombres:
                patron_telefono = r"^[1-9][0-9]{9}$"
                
                if not re.match(patron_telefono, tel):
                    st.error("❌ Error de validación: El teléfono debe componerse de exactamente 10 dígitos numéricos y NO puede iniciar con 0.")
                else:
                    apellidos_clean = apellidos.strip().title()
                    nombres_clean = nombres.strip().title()
                    
                    conn = conectar_db()
                    try:
                        conn.execute("INSERT INTO inquilinos (apellidos, nombres, dni_cuit, telefono) VALUES (?, ?, ?, ?)", 
                                     (apellidos_clean, nombres_clean, dni, tel))
                        conn.commit()
                        st.success(f"✔️ Inquilino '{apellidos_clean}, {nombres_clean}' incorporado correctamente.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("❌ Error: Ya existe una persona registrada con ese mismo Apellido y Nombre.")
                    finally:
                        conn.close()
            elif btn_i:
                st.error("❌ Los campos 'Apellidos' y 'Nombres' son obligatorios.")
                        
    # SUB-FORMULARIO: PROPIEDADES
    with col_b:
        st.markdown("#### 🏢 Registrar Nueva Propiedad")
        with st.form("form_propiedad", clear_on_submit=True):
            alias_p = st.text_input("Alias identificatorio (Ej: Depto 4B / Casa Alta):")
            st.markdown("**Componentes de la Dirección Física:**")
            calle_p = st.text_input("Calle / Avenida:")
            
            c_num, c_depto = st.columns([2, 1])
            num_p = c_num.text_input("Número / Altura:")
            depto_p = c_depto.text_input("Piso / Depto (Opcional):", placeholder="Ej: 4° B")
            
            btn_p = st.form_submit_button("Guardar Propiedad")
            
            if btn_p and alias_p and calle_p and num_p:
                conn = conectar_db()
                try:
                    conn.execute('''
                        INSERT INTO propiedades (alias_propiedad, calle, numero, departamento) 
                        VALUES (?, ?, ?, ?)
                    ''', (alias_p.strip(), calle_p.strip().title(), num_p.strip(), depto_p.strip().upper()))
                    conn.commit()
                    st.success(f"✔️ Propiedad '{alias_p.strip()}' incorporada correctamente.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("❌ Error: Ya existe una propiedad registrada utilizando ese mismo Alias.")
                finally:
                    conn.close()
            elif btn_p:
                st.error("❌ Los campos 'Alias', 'Calle' y 'Número' son de llenado obligatorio.")