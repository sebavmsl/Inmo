-- =====================================================================
-- 0006_pagos_extras.sql
--
-- Módulo 4 — columnas adicionales para Pagos. Ver docs/DESIGN_LOG.md
-- para el diseño completo (modelo de cuenta corriente ya resuelto en
-- 0003_saldo_contratos.sql — esta migración cubre lo que faltaba:
-- referencia de Complemento y el patrón "base + ledger" de
-- honorarios/garantía).
--
-- 100% aditivo — no renombra ni toca ninguna columna que use v1.
-- =====================================================================

-- ── 1. Contexto del Complemento en el comprobante ──────────────────────
alter table pagos_historial
  add column if not exists comprobante_referencia text;

comment on column pagos_historial.comprobante_referencia is
  'Solo se completa en pagos tipo Complemento: nro_comprobante de la fila '
  'Normal que dejó el saldo pendiente de ese mismo período. Permite '
  'mostrar contexto real en el PDF ("este pago cubre el saldo del '
  'Comprobante RC-...") en vez del "$0,00" desconectado que muestra v1.';

-- ── 2. Honorarios y garantía — patrón "base + ledger" ──────────────────
-- Columnas NUEVAS al lado de las originales (honorarios_pagados,
-- cuotas_honorarios_pagadas, garantia, cuotas_deposito_pagadas) — NO se
-- renombran, v1 las sigue usando exactamente igual. El total real en v2
-- es siempre: base + SUM(pagos_historial.monto_honorarios / monto_garantia
-- para ese contrato). Ver DESIGN_LOG.md, sección "Honorarios y garantía".
alter table contratos
  add column if not exists honorarios_pagados_base numeric not null default 0,
  add column if not exists cuotas_honorarios_pagadas_base int not null default 0,
  add column if not exists garantia_pagada_base numeric not null default 0,
  add column if not exists cuotas_deposito_pagadas_base int not null default 0;

comment on column contratos.honorarios_pagados_base is
  'Punto de partida editable SOLO en Carga de Contratos (Módulo 5) — para '
  'contratos migrados o con historia previa a v2. El total mostrado en '
  'cualquier pantalla de v2 es SIEMPRE base + SUM(pagos_historial.monto_honorarios). '
  'Nunca representa "el total actual" por sí sola.';

-- Copia el valor ya cargado en v1 como punto de partida — así los
-- contratos existentes no arrancan en $0 en v2.
-- OJO: `garantia` (texto) es un estado/etiqueta (ej. el resultado de
-- estado_garantia_calculado en v1, no un monto) — el monto realmente
-- pagado de depósito está en `garantia_pagada` (numeric). Confirmado
-- contra app.py (líneas 6015/6047: "deposito_pagados" se guarda ahí).
update contratos set
  honorarios_pagados_base = coalesce(honorarios_pagados, 0),
  cuotas_honorarios_pagadas_base = coalesce(cuotas_honorarios_pagadas, 0),
  garantia_pagada_base = coalesce(garantia_pagada, 0),
  cuotas_deposito_pagadas_base = coalesce(cuotas_deposito_pagadas, 0)
where honorarios_pagados_base = 0 and cuotas_honorarios_pagadas_base = 0
  and garantia_pagada_base = 0 and cuotas_deposito_pagadas_base = 0;
-- (el WHERE evita pisar valores si esta migración se corre más de una
-- vez después de que alguien ya haya usado las columnas _base en v2)

-- ── 3. impactar_cobro — TODO el flujo en una sola transacción ──────────
-- Puerto de app.py líneas 4200-4457, con el modelo de cuenta corriente.
--
-- IMPORTANTE (hallazgo de esta sesión, al escribir el Server Action):
-- pg_advisory_xact_lock solo dura lo que dura UNA transacción. Cada
-- llamada de Supabase-js (.rpc()/.select()/.insert()) es su propia
-- transacción — si el candado se toma en una llamada aparte de la
-- lectura+escritura, se libera antes de que sirva de algo. Por eso
-- TODA la secuencia (candado → leer saldo → calcular → insertar →
-- efectos secundarios) vive en una sola función, para que el candado
-- realmente proteja la transacción completa.
--
-- No necesita SECURITY DEFINER: corre con el usuario logueado, sobre un
-- contrato de su propia empresa — RLS normal alcanza (a diferencia de
-- las funciones del cron, que no tienen sesión de usuario).
create or replace function impactar_cobro(
  p_codigo_contrato int,
  p_empresa_id int,
  p_tipo_pago text,
  p_periodo text,
  p_monto_alquiler numeric, p_monto_expensas numeric, p_monto_edesal numeric,
  p_monto_gas numeric, p_monto_municipalidad numeric, p_monto_cochera numeric,
  p_monto_ooss numeric, p_monto_imp_inmobiliario numeric, p_monto_honorarios numeric,
  p_monto_garantia numeric, p_monto_concepto_extra numeric,
  p_diferencia_correccion numeric, -- solo para tipo_pago = 'Corrección'
  p_monto_abonado numeric,
  p_metodo_pago text, p_comentario text, p_cotizacion_usd numeric,
  p_registrado_por text
)
returns table (ok boolean, nro_comprobante text, saldo_nuevo numeric, mensaje_error text)
language plpgsql
security invoker -- explícito: corre con los permisos del usuario que llama, no del dueño
as $$
declare
  v_contrato record;
  v_cargos numeric;
  v_pagado numeric;
  v_monto_para_comision numeric;
  v_saldo_nuevo numeric;
  v_gasto_admin numeric;
  v_nro_comprobante text;
  v_comprobante_referencia text;
begin
  -- 1. Candado — por CONTRATO completo (no por contrato+período como
  --    v1), porque con cuenta corriente todos los períodos comparten el
  --    mismo saldo. Dura toda esta transacción/función.
  perform pg_advisory_xact_lock(p_codigo_contrato::bigint);

  -- 2. Leer el contrato FRESCO, ya adentro del candado.
  -- La columna real de % de comisión es `honorarios`, no `honorarios_pct`
  -- (confirmado contra app.py — ver database.types.ts para el detalle).
  select codigo, alias_propiedad, saldo_actual, honorarios, mes_contrato
  into v_contrato
  from contratos
  where codigo = p_codigo_contrato and empresa_id = p_empresa_id;

  if v_contrato is null then
    return query select false, null::text, null::numeric, 'Contrato no encontrado'::text;
    return;
  end if;

  -- 3. Fórmula única de cuenta corriente (ver DESIGN_LOG.md)
  if p_tipo_pago = 'Normal' then
    v_cargos := coalesce(p_monto_alquiler,0) + coalesce(p_monto_expensas,0) + coalesce(p_monto_edesal,0)
              + coalesce(p_monto_gas,0) + coalesce(p_monto_municipalidad,0) + coalesce(p_monto_cochera,0)
              + coalesce(p_monto_ooss,0) + coalesce(p_monto_imp_inmobiliario,0) + coalesce(p_monto_honorarios,0)
              + coalesce(p_monto_garantia,0) + coalesce(p_monto_concepto_extra,0);
    v_pagado := p_monto_abonado;
    v_monto_para_comision := p_monto_abonado;
  elsif p_tipo_pago = 'Complemento' then
    v_cargos := 0;
    v_pagado := p_monto_abonado;
    v_monto_para_comision := p_monto_abonado;
  elsif p_tipo_pago = 'Corrección' then
    v_cargos := coalesce(p_diferencia_correccion, 0);
    v_pagado := 0;
    v_monto_para_comision := coalesce(p_diferencia_correccion, 0);
  else
    return query select false, null::text, null::numeric, format('Tipo de pago inválido: %s', p_tipo_pago)::text;
    return;
  end if;

  v_saldo_nuevo := coalesce(v_contrato.saldo_actual, 0) + v_cargos - v_pagado;
  v_gasto_admin := round(v_monto_para_comision * coalesce(v_contrato.honorarios, 0) / 100.0, 2);
  v_nro_comprobante := 'RC-' || p_codigo_contrato || '-' || to_char(now(), 'YYMMDDHH24MISS');

  -- 4. Complemento: contexto del comprobante Normal de este período
  if p_tipo_pago = 'Complemento' then
    select nro_comprobante into v_comprobante_referencia
    from pagos_historial
    where codigo_contrato = p_codigo_contrato and periodo = p_periodo and tipo_pago = 'Normal'
    order by id desc limit 1;
  end if;

  -- 5. Insertar — pagos_historial es de solo inserción (ver DESIGN_LOG.md)
  insert into pagos_historial (
    empresa_id, codigo_contrato, propiedad, tipo_pago, periodo, fecha, username,
    monto_alquiler, monto_expensas, monto_edesal, monto_gas, monto_municipalidad,
    monto_cochera, monto_ooss, monto_imp_inmobiliario, monto_honorarios, monto_garantia,
    monto_gasto_admin, monto_concepto_extra, monto_abonado, saldo_pendiente,
    metodo_pago, cotizacion_usd, registrado_por, nro_comprobante, comentario,
    comprobante_referencia
  ) values (
    p_empresa_id, p_codigo_contrato, v_contrato.alias_propiedad, p_tipo_pago, p_periodo, now(), p_registrado_por,
    coalesce(p_monto_alquiler,0), coalesce(p_monto_expensas,0), coalesce(p_monto_edesal,0),
    coalesce(p_monto_gas,0), coalesce(p_monto_municipalidad,0), coalesce(p_monto_cochera,0),
    coalesce(p_monto_ooss,0), coalesce(p_monto_imp_inmobiliario,0), coalesce(p_monto_honorarios,0),
    coalesce(p_monto_garantia,0), v_gasto_admin, coalesce(p_monto_concepto_extra,0),
    case when p_tipo_pago = 'Corrección' then coalesce(p_diferencia_correccion,0) else p_monto_abonado end,
    v_saldo_nuevo, p_metodo_pago, p_cotizacion_usd, p_registrado_por, v_nro_comprobante, p_comentario,
    v_comprobante_referencia
  );
  -- trg_recalcular_saldo (0003) actualiza contratos.saldo_actual solo
  -- al confirmarse este INSERT — sigue siendo la única puerta de escritura.

  -- 6. Efectos secundarios — SOLO en pago Normal (ver DESIGN_LOG.md)
  if p_tipo_pago = 'Normal' then
    update contratos
    set mes_contrato = coalesce(v_contrato.mes_contrato, 0) + 1,
        alquiler = case when p_monto_alquiler > 0 then p_monto_alquiler else alquiler end
    where codigo = p_codigo_contrato and empresa_id = p_empresa_id;
  end if;

  return query select true, v_nro_comprobante, v_saldo_nuevo, null::text;
end;
$$;
