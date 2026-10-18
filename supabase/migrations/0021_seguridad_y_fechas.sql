-- =====================================================================
-- 0021_seguridad_y_fechas.sql  (Entrega 1 — V2.015)
--
-- Se corre A MANO en el SQL Editor de Supabase, completo, una sola vez.
-- Va todo dentro de una transacción: si algo falla, no queda nada a medias.
--
-- NO afecta a Python (Streamlit): Python se conecta como `postgres`, que es
-- dueño de todas las funciones y tablas. Todo lo de acá cambia permisos de
-- `anon` / `authenticated` (los roles de la API que usa la v2) o funciones
-- de trigger que ya están blindadas para no bloquear escrituras.
--
-- Contenido:
--   1. Chequeo de rol seguro ante NULL en las funciones que se cerraron
--      el 29/09, y se vuelven a habilitar solo para quien corresponde.
--   2. upsert_indice exige el secreto del cron.
--   3. Tokens de WhatsApp: solo el servidor (service_role).
--   4. saldo_actual: no editable desde la API (permiso por columna).
--   5. Auditoría: contratos usa `codigo`; se ignoran saldo_actual y updated_at.
--   6. updated_at no cambia cuando solo cambió el saldo.
--   7. impactar_cobro escribe la fecha en formato Python, hora Argentina.
--   8. registrar_liquidacion_propietario, ídem para fecha_liquidacion.
-- =====================================================================

begin;

-- ─────────────────────────────────────────────────────────────────────
-- 1. Chequeo de rol seguro ante NULL
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.eliminar_empresa_completa(p_empresa_id integer, p_confirmacion_nombre text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_nombre_real text;
  v_usernames text[];
begin
  if coalesce(auth_rol(), '') <> 'superadmin' then
    raise exception 'Solo superadmin puede eliminar una empresa';
  end if;

  select nombre_comercial into v_nombre_real from empresas where id = p_empresa_id;
  if v_nombre_real is null then
    raise exception 'Empresa no encontrada';
  end if;
  if p_confirmacion_nombre != v_nombre_real then
    raise exception 'El nombre de confirmación no coincide';
  end if;

  -- usernames del staff de esta empresa, para el borrado de permisos_usuario
  -- (que no tiene empresa_id — se filtra por username, arreglando el bug #1)
  select array_agg(username) into v_usernames from usuarios_central where empresa_id = p_empresa_id;

  delete from pagos_historial where empresa_id = p_empresa_id;
  delete from gastos_propiedades where empresa_id = p_empresa_id;
  delete from contratos where empresa_id = p_empresa_id;
  delete from inquilinos where empresa_id = p_empresa_id;
  delete from propiedades where empresa_id = p_empresa_id;
  delete from liquidaciones_propietarios where empresa_id = p_empresa_id;
  delete from configuraciones_empresa where empresa_id = p_empresa_id;
  delete from planilla_verificaciones where empresa_id = p_empresa_id;
  delete from whatsapp_recordatorios where empresa_id = p_empresa_id;
  delete from whatsapp_recordatorios_log where empresa_id = p_empresa_id;
  delete from comprobantes_inquilino where empresa_id = p_empresa_id;
  delete from reclamos_inquilino where empresa_id = p_empresa_id;
  if v_usernames is not null then
    delete from permisos_usuario where username = any(v_usernames);
  end if;
  -- usuarios_central y auditoria_cambios NO se borran — decisión
  -- explícita del usuario (ver DESIGN_LOG.md).
  delete from empresas where id = p_empresa_id;
end;
$function$;
CREATE OR REPLACE FUNCTION public.eliminar_registros_bloque(p_tabla text, p_ids integer[], p_empresa_id integer, p_confirmacion text)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_deleted int;
  v_username text;
  v_col_id text;
begin
  if coalesce(auth_rol(), '') <> 'superadmin' then
    raise exception 'Solo superadmin puede usar esta función';
  end if;
  if p_tabla not in ('contratos', 'inquilinos', 'propiedades', 'pagos_historial') then
    raise exception 'Tabla no permitida: %', p_tabla;
  end if;

  -- `contratos` no tiene columna `id` en la base real — su identificador
  -- es `codigo` (integer). Las otras 3 tablas sí usan `id`. p_ids sigue
  -- siendo un array de enteros en los dos casos (para contratos, son
  -- códigos de contrato, no ids).
  v_col_id := case when p_tabla = 'contratos' then 'codigo' else 'id' end;
  if p_confirmacion != format('FORZAR BORRADO %s FILAS', array_length(p_ids, 1)) then
    raise exception 'Confirmación incorrecta';
  end if;

  -- Validación de integridad referencial (ver DESIGN_LOG.md): sin FK real
  -- entre contratos y propiedades/inquilinos, hay que chequear a mano
  -- que no queden contratos con referencias rotas.
  if p_tabla = 'propiedades' then
    if exists (
      select 1 from contratos
      where empresa_id = p_empresa_id
        and alias_propiedad in (select alias_propiedad from propiedades where id = any(p_ids))
    ) then
      raise exception 'No se puede borrar: hay contratos que referencian estas propiedades';
    end if;
  elsif p_tabla = 'inquilinos' then
    if exists (
      select 1 from contratos
      where empresa_id = p_empresa_id
        and dni_inquilino in (select dni from inquilinos where id = any(p_ids))
    ) then
      raise exception 'No se puede borrar: hay contratos que referencian estos inquilinos';
    end if;
  end if;

  select username into v_username from usuarios_central where auth_user_id = auth.uid();

  -- Auditoría ANTES de borrar (tipo_evento = 'borrado_masivo'), con el
  -- contenido completo de cada fila antes de perderla. Se arma con SQL
  -- dinámico porque la estructura de columnas difiere entre tablas.
  execute format(
    'insert into auditoria_cambios (empresa_id, tabla, registro_id, tipo_evento, cambios, realizado_por)
     select %L, %L, %I::text, ''borrado_masivo'', to_jsonb(t), %L
     from %I t where empresa_id = %L and %I = any(%L::int[])',
    p_empresa_id, p_tabla, v_col_id, coalesce(v_username, 'sistema'), p_tabla, p_empresa_id, v_col_id, p_ids
  );

  execute format('delete from %I where empresa_id = $1 and %I = any($2)', p_tabla, v_col_id)
    using p_empresa_id, p_ids;
  get diagnostics v_deleted = row_count;
  return v_deleted;
end;
$function$;
CREATE OR REPLACE FUNCTION public.aplicar_actualizacion_individual(p_codigo_contrato integer, p_valor_calculado numeric, p_empresa_id integer, p_secret_cron text DEFAULT NULL::text)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_secret_real text;
  v_contrato record;
  v_hoy date := current_date;
begin
  -- Autorización: o bien el secreto de cron es correcto (modo global),
  -- o el empresa_id coincide con el de quien llama (modo manual).
  if p_secret_cron is not null then
    select decrypted_secret into v_secret_real
    from vault.decrypted_secrets where name = 'cron_secret';
    if p_secret_cron != v_secret_real then
      raise exception 'Secreto de cron inválido';
    end if;
  elsif coalesce(auth_rol(), '') <> 'superadmin' and p_empresa_id is distinct from auth_empresa_id() then
    raise exception 'No autorizado para operar sobre esta empresa';
  end if;

  select * into v_contrato from contratos
  where codigo = p_codigo_contrato and empresa_id = p_empresa_id and estado = 'Activo';

  if v_contrato is null then
    return false;
  end if;

  update contratos
  set alquiler_calculado = p_valor_calculado,
      alquiler_calculado_fecha = v_hoy
  where codigo = p_codigo_contrato and empresa_id = p_empresa_id;

  return true;
exception when others then
  -- Blindaje: nunca debe bloquear otras actualizaciones del mismo lote.
  return false;
end;
$function$;
CREATE OR REPLACE FUNCTION public.contratos_elegibles_actualizacion(p_empresa_id integer, p_solo_pendientes boolean DEFAULT false)
 RETURNS TABLE(codigo integer, empresa_id integer, alias_propiedad text, monto_inicial numeric, fecha_inicio text, indice text, frecuencia_meses integer)
 LANGUAGE sql
 STABLE SECURITY DEFINER
AS $function$
  -- Notas de esquema real (auditado contra volcado de producción + app.py):
  --   • `contratos` no tiene columna `fecha_inicio` — es `inicio_contrato`.
  --     Se alias-ea acá para no tocar el código TypeScript que ya consume
  --     el resultado de esta función como `fecha_inicio`.
  --   • `inicio_contrato`, `prox_actualizacion` y `alquiler_calculado_fecha`
  --     son TEXT en la base real (no `date`) — de ahí el ::date explícito
  --     abajo. Se devuelve `fecha_inicio` como texto tal cual (sin castear)
  --     para no romper si algún registro viejo no está en formato ISO.
  --   • No existe `frecuencia_actualizacion` (enum de texto asumido) — la
  --     frecuencia real ya está en `act_contrato`, un integer con la
  --     cantidad de meses directamente (1, 2, 3, 4, 6, 12, 24 — confirmado
  --     contra app.py, "opciones_meses").
  select
    c.codigo, c.empresa_id, c.alias_propiedad, c.monto_inicial,
    c.inicio_contrato as fecha_inicio,
    c.indice,
    coalesce(c.act_contrato, 6) as frecuencia_meses
  from contratos c
  join configuraciones_empresa ce on ce.empresa_id = c.empresa_id
  where c.estado = 'Activo'
    and c.indice in ('ICL', 'IPC', 'UVA')
    and c.prox_actualizacion is not null
    and date_trunc('month', c.prox_actualizacion::date) = date_trunc('month', current_date)
    and (p_empresa_id is null or c.empresa_id = p_empresa_id)
    -- 0021: solo superadmin o la propia empresa (antes cualquiera veía todo)
    and (coalesce(auth_rol(), '') = 'superadmin' or c.empresa_id = auth_empresa_id())
    and (p_empresa_id is not null or ce.cron_indices_habilitado = true) -- modo cron: solo empresas opt-in
    and (
      not p_solo_pendientes
      or c.alquiler_calculado_fecha is null
      or date_trunc('month', c.alquiler_calculado_fecha::date) != date_trunc('month', current_date)
    );
$function$;

revoke execute on function public.eliminar_empresa_completa(integer, text) from public, anon;
revoke execute on function public.eliminar_registros_bloque(text, integer[], integer, text) from public, anon;
revoke execute on function public.aplicar_actualizacion_individual(integer, numeric, integer, text) from public, anon;
revoke execute on function public.contratos_elegibles_actualizacion(integer, boolean) from public, anon;
grant execute on function public.eliminar_empresa_completa(integer, text) to authenticated;
grant execute on function public.eliminar_registros_bloque(text, integer[], integer, text) to authenticated;
grant execute on function public.aplicar_actualizacion_individual(integer, numeric, integer, text) to authenticated;
grant execute on function public.contratos_elegibles_actualizacion(integer, boolean) to authenticated;

-- ─────────────────────────────────────────────────────────────────────
-- 2. upsert_indice exige el secreto del cron
-- ─────────────────────────────────────────────────────────────────────
drop function public.upsert_indice(text, date, numeric);
CREATE OR REPLACE FUNCTION public.upsert_indice(p_tipo text, p_fecha date, p_valor numeric, p_secret_cron text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_secret_real text;
begin
  select decrypted_secret into v_secret_real
  from vault.decrypted_secrets where name = 'cron_secret';
  if p_secret_cron is null or p_secret_cron is distinct from v_secret_real then
    raise exception 'Secreto de cron inválido';
  end if;

  if p_tipo not in ('ICL', 'IPC', 'UVA') then
    raise exception 'Tipo de índice no válido: %', p_tipo;
  end if;
  if p_valor is null or p_valor <= 0 then
    raise exception 'Valor de índice inválido: %', p_valor;
  end if;

  insert into indices_historicos (tipo, fecha, valor)
  values (p_tipo, p_fecha, p_valor)
  on conflict (tipo, fecha) do update set valor = excluded.valor;
end;
$function$;
revoke execute on function public.upsert_indice(text, date, numeric, text) from public, authenticated;
grant execute on function public.upsert_indice(text, date, numeric, text) to anon;

-- ─────────────────────────────────────────────────────────────────────
-- 3. Tokens de WhatsApp: solo el servidor (service_role)
-- ─────────────────────────────────────────────────────────────────────
-- Siguen cerradas para anon/authenticated (cerradas el 29/09). Python las
-- usa como postgres y no se ve afectado.
grant execute on function public.leer_token_whatsapp(uuid) to service_role;
grant execute on function public.guardar_token_whatsapp(text, text) to service_role;
grant execute on function public.actualizar_token_whatsapp(uuid, text) to service_role;

-- ─────────────────────────────────────────────────────────────────────
-- 4. saldo_actual no editable desde la API
-- ─────────────────────────────────────────────────────────────────────
-- Quitar UPDATE de una columna no alcanza mientras exista UPDATE sobre la
-- tabla entera: se quita el de tabla y se da por columna, todas menos
-- saldo_actual (la mantiene solo el trigger trg_recalcular_saldo).
revoke update on public.contratos from anon, authenticated;
grant update (codigo, empresa_id, alias_propiedad, dni_inquilino, estado, inicio_contrato, fin_contrato, calc_duracion, act_contrato, indice, monto_inicial, alquiler, prox_actualizacion, mes_contrato, mes_actualizacion_contrato, servicios, honorarios, monto_honorarios, cuota_honorarios, honorarios_pagados, cuotas_honorarios_pagadas, tipo_de_garantie, monto_garantia, garantia, garantia_pagada, cuotas_deposito, cuotas_deposito_pagadas, imp_inmobiliario, expensas, edesal, gas, municipalidad, ooss, servicios_total, cochera, alquiler_cobrado, total_pagado, alquiler_calculado, alquiler_calculado_fecha, fecha_finalizacion, finalizado_por, archivado, honorarios_pagados_base, cuotas_honorarios_pagadas_base, garantia_pagada_base, cuotas_deposito_pagadas_base, cargo_electricidad, cargo_gas, cargo_municipalidad, cargo_ooss, cargo_expensas, cargo_imp_inmobiliario, updated_at)
  on public.contratos to authenticated;

-- ─────────────────────────────────────────────────────────────────────
-- 5. Auditoría: contratos usa codigo; ignora saldo_actual y updated_at
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.fn_auditar_cambios()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_cambios jsonb := '{}'::jsonb;
  v_key text;
  v_username text;
begin
  select username into v_username from usuarios_central where auth_user_id = auth.uid();
  v_username := coalesce(v_username, 'sistema');

  if TG_OP = 'INSERT' then
    insert into auditoria_cambios (empresa_id, tabla, registro_id, tipo_evento, cambios, realizado_por)
    values (NEW.empresa_id, TG_TABLE_NAME, coalesce(to_jsonb(NEW)->>'id', to_jsonb(NEW)->>'codigo'), 'creacion', to_jsonb(NEW), v_username);
    return NEW;

  elsif TG_OP = 'UPDATE' then
    for v_key in select jsonb_object_keys(to_jsonb(NEW)) loop
      -- saldo_actual se excluye a propósito (ver DESIGN_LOG.md,
      -- "Interacción entre triggers — ruido en auditoria_cambios"):
      -- cambia en CADA pago vía trg_recalcular_saldo, y loggearlo acá
      -- inundaría la auditoría con una entrada por cada cobro en vez de
      -- reservarla para ediciones humanas intencionales.
      if v_key in ('saldo_actual', 'updated_at') then
        continue;
      end if;
      if to_jsonb(OLD)->v_key is distinct from to_jsonb(NEW)->v_key then
        v_cambios := v_cambios || jsonb_build_object(v_key,
          jsonb_build_object('antes', to_jsonb(OLD)->v_key, 'despues', to_jsonb(NEW)->v_key));
      end if;
    end loop;

    if v_cambios != '{}'::jsonb then
      insert into auditoria_cambios (empresa_id, tabla, registro_id, tipo_evento, cambios, realizado_por)
      values (NEW.empresa_id, TG_TABLE_NAME, coalesce(to_jsonb(NEW)->>'id', to_jsonb(NEW)->>'codigo'), 'edicion', v_cambios, v_username);
    end if;
    return NEW;
  end if;

  return null;
exception when others then
  -- Blindaje (ver DESIGN_LOG.md, auditoría "¿el SQL altera el
  -- funcionamiento de v1?"): un fallo acá nunca debe bloquear la
  -- escritura real del contrato/propiedad/inquilino.
  return coalesce(NEW, OLD);
end;
$function$;

-- ─────────────────────────────────────────────────────────────────────
-- 6. updated_at no cambia cuando solo cambió el saldo
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.fn_set_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
begin
  -- 0021: si lo único que cambió es saldo_actual (cada cobro lo recalcula),
  -- no se toca updated_at, para no generar falsos conflictos de edición.
  if (to_jsonb(new) - 'saldo_actual' - 'updated_at') = (to_jsonb(old) - 'saldo_actual' - 'updated_at') then
    new.updated_at := old.updated_at;
  else
    new.updated_at := now();
  end if;
  return new;
end;
$function$;

-- ─────────────────────────────────────────────────────────────────────
-- 7. impactar_cobro: fecha en formato Python (DD/MM/YYYY HH:MM, hora Argentina)
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.impactar_cobro(p_codigo_contrato integer, p_empresa_id integer, p_tipo_pago text, p_periodo text, p_monto_alquiler numeric, p_monto_expensas numeric, p_monto_edesal numeric, p_monto_gas numeric, p_monto_municipalidad numeric, p_monto_cochera numeric, p_monto_ooss numeric, p_monto_imp_inmobiliario numeric, p_monto_honorarios numeric, p_monto_garantia numeric, p_monto_concepto_extra numeric, p_diferencia_correccion numeric, p_monto_abonado numeric, p_metodo_pago text, p_comentario text, p_cotizacion_usd numeric, p_registrado_por text)
 RETURNS TABLE(ok boolean, nro_comprobante text, saldo_nuevo numeric, mensaje_error text)
 LANGUAGE plpgsql
AS $function$
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
    p_empresa_id, p_codigo_contrato, v_contrato.alias_propiedad, p_tipo_pago, p_periodo,
    to_char(now() at time zone 'America/Argentina/Buenos_Aires', 'DD/MM/YYYY HH24:MI'), p_registrado_por,
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
$function$;

-- ─────────────────────────────────────────────────────────────────────
-- 8. registrar_liquidacion_propietario: fecha en formato Python
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.registrar_liquidacion_propietario(p_empresa_id integer, p_propietario text, p_periodo text, p_monto_calculado numeric, p_saldo_anterior numeric, p_monto_retencion_gastos numeric, p_monto_a_liquidar numeric, p_monto_liquidado numeric, p_saldo_pendiente numeric, p_ids_gastos integer[], p_registrado_por text)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
begin
  insert into liquidaciones_propietarios (
    empresa_id, propietario, periodo, monto_calculado, saldo_anterior,
    monto_retencion_gastos, monto_a_liquidar, monto_liquidado,
    saldo_pendiente, fecha_liquidacion, registrado_por
  ) values (
    p_empresa_id, p_propietario, p_periodo, p_monto_calculado, p_saldo_anterior,
    p_monto_retencion_gastos, p_monto_a_liquidar, p_monto_liquidado,
    p_saldo_pendiente, to_char(now() at time zone 'America/Argentina/Buenos_Aires', 'DD/MM/YYYY HH24:MI'), p_registrado_por
  )
  on conflict (empresa_id, propietario, periodo) do update set
    monto_calculado = excluded.monto_calculado,
    saldo_anterior = excluded.saldo_anterior,
    monto_retencion_gastos = excluded.monto_retencion_gastos,
    monto_a_liquidar = excluded.monto_a_liquidar,
    monto_liquidado = excluded.monto_liquidado,
    saldo_pendiente = excluded.saldo_pendiente,
    fecha_liquidacion = excluded.fecha_liquidacion,
    registrado_por = excluded.registrado_por;

  if p_ids_gastos is not null and array_length(p_ids_gastos, 1) > 0 then
    update gastos_propiedades
    set cobrado = true, periodo_cobrado = p_periodo
    where empresa_id = p_empresa_id and id = any(p_ids_gastos);
  end if;
  -- Si el UPDATE de arriba fallara por algún motivo, todo lo anterior
  -- (el INSERT de la liquidación) se revierte también — misma función,
  -- misma transacción. Ya no puede quedar un estado a medias.
end;
$function$;

commit;
