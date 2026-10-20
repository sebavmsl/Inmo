-- =====================================================================
-- 0023_carga_contratos.sql  (Entrega 2 — V2.018)
--
-- Se corre A MANO en el SQL Editor de Supabase, completo, una sola vez.
-- Va todo dentro de una transacción: si algo falla, no queda nada a medias.
--
-- NO afecta a Python (Streamlit):
--   - Solo AGREGA columnas (con valor por defecto) y UNA función nueva.
--     Python lee contratos y pagos por nombre de columna, así que las
--     columnas nuevas le son invisibles.
--   - No modifica ninguna función, trigger ni política existente.
--
-- Contenido:
--   1. Columnas nuevas en contratos: dia_vencimiento, cochera_monto_inicial,
--      cochera_actualiza_con_indice, cargo_general_servicios, monto_pagare.
--   2. Columna nueva en pagos_historial: monto_cargo_general.
--   3. Permisos: editar las columnas nuevas y usar la secuencia del código
--      de contrato (el código lo asigna la base, igual que en Python).
--   4. crear_contrato_v2(): alta atómica — cierra el contrato activo
--      anterior de la propiedad, crea el nuevo y registra los meses ya
--      transcurridos, todo o nada.
-- =====================================================================

begin;

-- ─────────────────────────────────────────────────────────────────────
-- 1. Columnas nuevas en contratos
-- ─────────────────────────────────────────────────────────────────────
alter table public.contratos
  add column if not exists dia_vencimiento integer not null default 10,
  add column if not exists cochera_monto_inicial numeric,
  add column if not exists cochera_actualiza_con_indice boolean not null default false,
  add column if not exists cargo_general_servicios numeric not null default 0,
  add column if not exists monto_pagare numeric not null default 0;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'contratos_dia_vencimiento_check') then
    alter table public.contratos
      add constraint contratos_dia_vencimiento_check check (dia_vencimiento between 1 and 31);
  end if;
end $$;

-- En los contratos existentes, la cochera inicial arranca con el valor
-- actual (decisión de Carga: revisarla antes de activar el tilde).
update public.contratos set cochera_monto_inicial = coalesce(cochera, 0) where cochera_monto_inicial is null;

-- ─────────────────────────────────────────────────────────────────────
-- 2. Columna nueva en pagos_historial
-- ─────────────────────────────────────────────────────────────────────
alter table public.pagos_historial
  add column if not exists monto_cargo_general numeric not null default 0;

-- ─────────────────────────────────────────────────────────────────────
-- 3. Permisos
-- ─────────────────────────────────────────────────────────────────────
-- 0021 pasó el UPDATE de contratos a permiso por columna (sin saldo_actual):
-- las columnas nuevas hay que habilitarlas una por una.
grant update (dia_vencimiento, cochera_monto_inicial, cochera_actualiza_con_indice, cargo_general_servicios, monto_pagare)
  on public.contratos to authenticated;

-- El código del contrato lo da la secuencia (Python inserta sin código).
grant usage on sequence public.contratos_codigo_seq to authenticated;

-- ─────────────────────────────────────────────────────────────────────
-- 4. crear_contrato_v2
--
--   p_contrato: las columnas del contrato nuevo, con sus nombres reales
--               (empresa_id, alias_propiedad, dni_inquilino, ...). El
--               código NO se manda: lo asigna la secuencia.
--   p_meses:    lista de meses ya transcurridos a registrar, en orden:
--               [{ nro, periodo, fecha, alquiler, expensas, edesal, gas,
--                  municipalidad, cochera, ooss, imp_inmobiliario,
--                  honorarios, garantia, cargo_general, ajuste, abonado,
--                  comision, metodo_pago, comentario }]
--
--   SECURITY INVOKER: corre con los permisos y el RLS del usuario logueado.
--   Devuelve { ok, codigo, cerrados: [{codigo, estado}], error }.
-- ─────────────────────────────────────────────────────────────────────
create or replace function public.crear_contrato_v2(p_contrato jsonb, p_meses jsonb default '[]'::jsonb)
returns jsonb
language plpgsql
security invoker
as $function$
declare
  v_c public.contratos%rowtype;
  v_codigo integer;
  v_cerrados jsonb := '[]'::jsonb;
  v_viejo record;
  v_fin date;
  v_fin_mes date := (date_trunc('month', (now() at time zone 'America/Argentina/Buenos_Aires')) + interval '1 month - 1 day')::date;
  v_estado_viejo text;
  v_inquilino text;
  v_m jsonb;
  v_total numeric;
  v_abonado numeric;
  v_saldo numeric := 0;
  v_saldo_antes numeric;
  v_nro text;
  v_seq bigint;
  v_anio text := to_char(now() at time zone 'America/Argentina/Buenos_Aires', 'YYYY');
  v_usuario text;
begin
  v_c := jsonb_populate_record(null::public.contratos, p_contrato);

  -- Empresa: un usuario normal solo puede crear en la suya.
  if v_c.empresa_id is null then
    return jsonb_build_object('ok', false, 'error', 'Falta la empresa.');
  end if;
  if coalesce(auth_rol(), '') <> 'superadmin' and v_c.empresa_id is distinct from auth_empresa_id() then
    return jsonb_build_object('ok', false, 'error', 'No podés crear contratos en otra empresa.');
  end if;

  if coalesce(v_c.estado, '') not in ('Activo', 'Finalizado', 'Cancelado') then
    return jsonb_build_object('ok', false, 'error', 'Estado inválido.');
  end if;

  -- Un alta a la vez por propiedad (evita dos contratos activos si se
  -- aprieta guardar dos veces).
  perform pg_advisory_xact_lock(hashtext('alta_contrato:' || v_c.empresa_id || ':' || coalesce(v_c.alias_propiedad, '')));

  if not exists (select 1 from public.propiedades p
                 where p.empresa_id = v_c.empresa_id and p.alias_propiedad = v_c.alias_propiedad) then
    return jsonb_build_object('ok', false, 'error', 'La propiedad no existe en esta empresa.');
  end if;

  select i.apellidos || ', ' || i.nombres into v_inquilino
  from public.inquilinos i
  where i.empresa_id = v_c.empresa_id and i.dni = v_c.dni_inquilino
  limit 1;
  if v_inquilino is null then
    return jsonb_build_object('ok', false, 'error', 'El inquilino no existe en esta empresa.');
  end if;

  -- 1. Cerrar el contrato activo anterior de la propiedad (solo si el
  --    nuevo es Activo). Finalizado si ya terminó o termina este mes, o si
  --    ya no le quedan meses; si no, Cancelado (se cortó antes de tiempo).
  if v_c.estado = 'Activo' then
    for v_viejo in
      select codigo, fin_contrato, mes_contrato, calc_duracion
      from public.contratos
      where empresa_id = v_c.empresa_id and alias_propiedad = v_c.alias_propiedad and estado = 'Activo'
      for update
    loop
      v_fin := case
        when v_viejo.fin_contrato ~ '^\d{4}-\d{2}-\d{2}' then to_date(left(v_viejo.fin_contrato, 10), 'YYYY-MM-DD')
        when v_viejo.fin_contrato ~ '^\d{1,2}/\d{1,2}/\d{4}' then to_date(v_viejo.fin_contrato, 'DD/MM/YYYY')
        else null end;
      v_estado_viejo := case
        when (v_fin is not null and v_fin <= v_fin_mes)
          or (v_viejo.mes_contrato is not null and v_viejo.calc_duracion is not null and v_viejo.mes_contrato >= v_viejo.calc_duracion)
        then 'Finalizado' else 'Cancelado' end;

      update public.contratos
      set estado = v_estado_viejo, finalizado_por = 'renovacion'
      where codigo = v_viejo.codigo;

      v_cerrados := v_cerrados || jsonb_build_object('codigo', v_viejo.codigo, 'estado', v_estado_viejo);
    end loop;
  end if;

  -- 2. Crear el contrato (el código lo da la secuencia).
  insert into public.contratos (
    empresa_id, alias_propiedad, dni_inquilino, estado, inicio_contrato, fin_contrato,
    calc_duracion, act_contrato, indice, monto_inicial, alquiler, prox_actualizacion,
    mes_contrato, mes_actualizacion_contrato, servicios, honorarios, monto_honorarios,
    cuota_honorarios, honorarios_pagados, cuotas_honorarios_pagadas,
    tipo_de_garantie, monto_garantia, garantia, garantia_pagada,
    cuotas_deposito, cuotas_deposito_pagadas,
    imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, servicios_total,
    cochera, alquiler_cobrado, total_pagado,
    honorarios_pagados_base, cuotas_honorarios_pagadas_base, garantia_pagada_base, cuotas_deposito_pagadas_base,
    cargo_electricidad, cargo_gas, cargo_municipalidad, cargo_ooss, cargo_expensas, cargo_imp_inmobiliario,
    dia_vencimiento, cochera_monto_inicial, cochera_actualiza_con_indice, cargo_general_servicios, monto_pagare
  ) values (
    v_c.empresa_id, v_c.alias_propiedad, v_c.dni_inquilino, v_c.estado, v_c.inicio_contrato, v_c.fin_contrato,
    v_c.calc_duracion, v_c.act_contrato, v_c.indice, v_c.monto_inicial, v_c.alquiler, v_c.prox_actualizacion,
    v_c.mes_contrato, v_c.mes_actualizacion_contrato, v_c.servicios, v_c.honorarios, v_c.monto_honorarios,
    v_c.cuota_honorarios, coalesce(v_c.honorarios_pagados, 0), coalesce(v_c.cuotas_honorarios_pagadas, 0),
    v_c.tipo_de_garantie, v_c.monto_garantia, v_c.garantia, coalesce(v_c.garantia_pagada, 0),
    coalesce(v_c.cuotas_deposito, 1), coalesce(v_c.cuotas_deposito_pagadas, 0),
    coalesce(v_c.imp_inmobiliario, 0), coalesce(v_c.expensas, 0), coalesce(v_c.edesal, 0), coalesce(v_c.gas, 0),
    coalesce(v_c.municipalidad, 0), coalesce(v_c.ooss, 0), coalesce(v_c.servicios_total, 0),
    coalesce(v_c.cochera, 0), coalesce(v_c.alquiler_cobrado, 0), coalesce(v_c.total_pagado, 0),
    0, 0, 0, 0,
    coalesce(v_c.cargo_electricidad, 'Inquilino'), coalesce(v_c.cargo_gas, 'Inquilino'),
    coalesce(v_c.cargo_municipalidad, 'Inquilino'), coalesce(v_c.cargo_ooss, 'Inquilino'),
    coalesce(v_c.cargo_expensas, 'Inquilino'), coalesce(v_c.cargo_imp_inmobiliario, 'Propietario'),
    coalesce(v_c.dia_vencimiento, 10), coalesce(v_c.cochera_monto_inicial, v_c.cochera, 0),
    coalesce(v_c.cochera_actualiza_con_indice, false), coalesce(v_c.cargo_general_servicios, 0),
    coalesce(v_c.monto_pagare, 0)
  )
  returning codigo into v_codigo;

  -- 3. Meses ya transcurridos: un registro por mes, en orden. El saldo es
  --    cuenta corriente: arranca en 0 y acumula (total del mes − abonado).
  --    trg_recalcular_saldo deja en el contrato el saldo del último.
  v_usuario := coalesce(p_contrato->>'registrado_por', '');

  for v_m in select value from jsonb_array_elements(coalesce(p_meses, '[]'::jsonb)) order by (value->>'nro')::int
  loop
    if coalesce(v_m->>'fecha', '') !~ '^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$' then
      raise exception 'Fecha inválida en el mes %: %', v_m->>'nro', v_m->>'fecha';
    end if;

    v_abonado := coalesce((v_m->>'abonado')::numeric, 0);
    if v_abonado < 0 then
      raise exception 'El monto abonado del mes % no puede ser negativo', v_m->>'nro';
    end if;

    v_total := coalesce((v_m->>'alquiler')::numeric, 0) + coalesce((v_m->>'expensas')::numeric, 0)
             + coalesce((v_m->>'edesal')::numeric, 0) + coalesce((v_m->>'gas')::numeric, 0)
             + coalesce((v_m->>'municipalidad')::numeric, 0) + coalesce((v_m->>'cochera')::numeric, 0)
             + coalesce((v_m->>'ooss')::numeric, 0) + coalesce((v_m->>'imp_inmobiliario')::numeric, 0)
             + coalesce((v_m->>'honorarios')::numeric, 0) + coalesce((v_m->>'garantia')::numeric, 0)
             + coalesce((v_m->>'cargo_general')::numeric, 0) + coalesce((v_m->>'ajuste')::numeric, 0);

    v_saldo_antes := v_saldo;
    v_saldo := v_saldo + v_total - v_abonado;

    -- Número de comprobante con la misma secuencia que Python, solo si
    -- entró plata (un mes adeudado sin pago no tiene recibo).
    v_nro := '';
    if v_abonado > 0 then
      v_seq := nextval('public.seq_nro_recibo');
      v_nro := 'RC-' || v_anio || '-' || lpad(v_seq::text, greatest(5, length(v_seq::text)), '0');
    end if;

    insert into public.pagos_historial (
      empresa_id, codigo_contrato, username, pestana, fecha, periodo, inquilino, propiedad,
      monto_alquiler, monto_expensas, monto_edesal, monto_gas, monto_municipalidad, monto_cochera,
      monto_ooss, monto_imp_inmobiliario, monto_honorarios, monto_garantia, monto_cargo_general,
      concepto_extra_desc, monto_concepto_extra,
      monto_abonado, saldo_pendiente, saldos_anteriores, metodo_pago, comentario,
      cotizacion_usd, registrado_por, nro_comprobante, monto_gasto_admin, tipo_pago
    ) values (
      v_c.empresa_id, v_codigo, v_usuario, 'carga', v_m->>'fecha', v_m->>'periodo', v_inquilino, v_c.alias_propiedad,
      coalesce((v_m->>'alquiler')::numeric, 0), coalesce((v_m->>'expensas')::numeric, 0),
      coalesce((v_m->>'edesal')::numeric, 0), coalesce((v_m->>'gas')::numeric, 0),
      coalesce((v_m->>'municipalidad')::numeric, 0), coalesce((v_m->>'cochera')::numeric, 0),
      coalesce((v_m->>'ooss')::numeric, 0), coalesce((v_m->>'imp_inmobiliario')::numeric, 0),
      coalesce((v_m->>'honorarios')::numeric, 0), coalesce((v_m->>'garantia')::numeric, 0),
      coalesce((v_m->>'cargo_general')::numeric, 0),
      case when coalesce((v_m->>'ajuste')::numeric, 0) <> 0 then 'Ajuste carga inicial' else '' end,
      coalesce((v_m->>'ajuste')::numeric, 0),
      v_abonado, v_saldo, v_saldo_antes, v_m->>'metodo_pago', coalesce(v_m->>'comentario', ''),
      0, v_usuario, v_nro,
      case when coalesce((v_m->>'comision')::boolean, false)
           then round(v_abonado * coalesce(v_c.honorarios, 0) / 100.0, 2) else 0 end,
      'Normal'
    );
  end loop;

  return jsonb_build_object('ok', true, 'codigo', v_codigo, 'cerrados', v_cerrados);
end;
$function$;

revoke execute on function public.crear_contrato_v2(jsonb, jsonb) from public, anon;
grant execute on function public.crear_contrato_v2(jsonb, jsonb) to authenticated;

commit;
