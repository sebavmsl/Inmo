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
                val_exp = float(u[10]) if u and u[10] is not None else 0.0  # Mapeado a expensas en base a tu consulta SQL original
                expensas = s_col3.number_input("Monto Expensas ($):", min_value=0.0, value=val_exp, step=500.0, disabled=not permitir_edicion)
                cargo_expensas = s_col4.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_exp", disabled=not permitir_edicion)
                
            with g2_col2:
                s_col13, s_col14 = st.columns([3, 2])
                val_coch = float(u[15]) if u and len(u) > 16 and u[16] is not None else 0.0  # Control de desborde de tupla
                cochera = s_col13.number_input("Monto Cochera ($):", min_value=0.0, value=val_coch, step=1000.0, disabled=not permitir_edicion)
                cargo_cochera = s_col14.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=0, key="cargo_coch", disabled=not permitir_edicion)

        # --- GRUPO C: IMPUESTO PROVINCIAL ESTRUCTURAL ---
        with st.container(border=True):
            st.markdown("##### **📌 Impuesto Provincial Individual**")
            s_col1, s_col2 = st.columns([3, 2])
            val_imp_inmob = float(u[9]) if u and u[9] is not None else 0.0  # Mapeado a imp_inmobiliario
            imp_inmobiliario = s_col1.number_input("Imp. Inmobiliario ($):", min_value=0.0, value=val_imp_inmob, step=500.0, disabled=not permitir_edicion)
            cargo_inmobiliario = s_col2.selectbox("A cargo de:", ["Inquilino", "Propietario"], index=1, key="cargo_inmob", disabled=not permitir_edicion)

        # NOTAS GENERALES Y DETALLES STRING
        st.text(" ") 
        notas_adicionales_input = st.text_input("Notas Adicionales de Servicios:", disabled=not permitir_edicion)
        
        # Consolidación estructurada para el registro de texto 'servicios'
        str_identificadores = f"[NIS: {num_nis}] [Cta Gas: {cuenta_gas}] [Finca: {finca_mun}] [Cta OO.SS.: {cuenta_oos}]"
        
        # Agregar detalles legibles para saber quién paga qué en la base de datos
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

        # Botón secundario opcional adaptado (Sin st.form_submit_button para no romper la reactividad)
        btn_sec6 = st.button("💾 Guardar Contrato Completo (Acceso Rápido)", key="btn_guardar_seccion_6", disabled=boton_deshabilitado, type="secondary")
