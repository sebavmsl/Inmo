-- =====================================================================
-- 0010_whatsapp_recordatorios.sql
--
-- Módulo 8 — Recordatorios automáticos por WhatsApp.
--
-- IMPORTANTE: `whatsapp_recordatorios` y `whatsapp_recordatorios_log` ya
-- existen en producción (las creó v1, aunque el motor automático de v1
-- tiene el bug documentado en docs/DESIGN_LOG.md — nunca compara contra
-- la fecha real de cada contrato). NO se recrean ni se renombra ninguna
-- columna existente — v1 sigue leyendo/escribiendo `dia_del_mes` exactamente
-- igual que siempre, aunque esa función suya no funcione bien.
-- =====================================================================

-- ── 1. Columna nueva, al lado de la vieja (nunca se toca dia_del_mes) ──
alter table whatsapp_recordatorios
  add column if not exists dias_antes int;

comment on column whatsapp_recordatorios.dias_antes is
  'Offset real en días antes del evento (vencimiento/actualización). '
  'Columna de v2 — NO confundir con dia_del_mes, que es la columna '
  'original de v1 (mal usada como día calendario, ver DESIGN_LOG.md). '
  'v2 lee/escribe dias_antes; v1 sigue usando dia_del_mes sin cambios.';

-- ── 2. Deduplicación: asegurar que exista un UNIQUE en el log ──────────
-- Por si v1 la creó sin esta constraint — es la red de seguridad real
-- contra reenvíos duplicados el mismo día (ver DESIGN_LOG.md, sección
-- "Deduplicación"). Aditivo: si ya existiera, este bloque no hace nada.
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'whatsapp_recordatorios_log_dedup_key'
  ) then
    alter table whatsapp_recordatorios_log
      add constraint whatsapp_recordatorios_log_dedup_key
      unique (codigo_contrato, tipo, fecha_envio);
  end if;
end $$;

-- ── 3. RLS de las tablas (por si no estaba habilitado) ─────────────────
-- Mismo criterio que el resto de tablas de negocio: aislamiento por
-- empresa vía auth_empresa_id() (definida en 0001_v2_auth_setup.sql).
alter table whatsapp_recordatorios enable row level security;
alter table whatsapp_recordatorios_log enable row level security;

drop policy if exists "empresa_isolation_select" on whatsapp_recordatorios;
create policy "empresa_isolation_select" on whatsapp_recordatorios for select
  using (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id());

drop policy if exists "empresa_isolation_write" on whatsapp_recordatorios;
create policy "empresa_isolation_write" on whatsapp_recordatorios for all
  using (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id())
  with check (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id());

drop policy if exists "empresa_isolation_select" on whatsapp_recordatorios_log;
create policy "empresa_isolation_select" on whatsapp_recordatorios_log for select
  using (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id());
-- Sin política de INSERT para "authenticated": el cron no tiene sesión de
-- usuario (auth.uid() es null), así que ninguna política RLS común le
-- serviría. Escribe exclusivamente a través de la función de abajo.

-- ── 4. Reserva atómica de envío (dedup real, sin condición de carrera) ──
-- El cron llama esto ANTES de mandar el WhatsApp, no después: si devuelve
-- TRUE, "reservó" el envío (nadie más puede reservarlo también, gracias al
-- UNIQUE del paso 2) y recién ahí procede a mandar el mensaje. Si devuelve
-- FALSE, ya se había enviado (o reservado) hoy para ese contrato+tipo —
-- no manda nada. Evita el mismo problema de "leer antes de escribir sin
-- candado" que ya resolvimos para el saldo de contratos, aplicado acá al
-- envío de mensajes.
create or replace function intentar_reservar_recordatorio(
  p_empresa_id int,
  p_codigo_contrato int, -- whatsapp_recordatorios_log.codigo_contrato es integer (confirmado)
  p_tipo text,
  p_secret_cron text
)
returns boolean
language plpgsql
security definer
as $$
declare
  v_secret_real text;
  v_reservado boolean;
begin
  select decrypted_secret into v_secret_real
  from vault.decrypted_secrets where name = 'cron_secret';

  if p_secret_cron is null or p_secret_cron != v_secret_real then
    raise exception 'Secreto de cron inválido';
  end if;

  -- fecha_envio es TEXT en la base real (no date) — cast explícito.
  insert into whatsapp_recordatorios_log (empresa_id, codigo_contrato, tipo, fecha_envio, enviado)
  values (p_empresa_id, p_codigo_contrato, p_tipo, current_date::text, true)
  on conflict (codigo_contrato, tipo, fecha_envio) do nothing;

  get diagnostics v_reservado = row_count;
  return v_reservado > 0;
exception when others then
  -- Blindaje: si algo falla acá (mismo criterio que los triggers de saldo/
  -- auditoría), nunca debe tirar abajo el resto del proceso del cron —
  -- simplemente no se manda ese recordatorio puntual, se reintenta mañana.
  return false;
end;
$$;

-- ── 5. Lectura de recordatorios pendientes, cruzando todas las empresas ─
-- El cron no tiene sesión de usuario (auth.uid() es null) — el cliente
-- normal con RLS no podría leer contratos de más de una empresa. Esta
-- función SECURITY DEFINER hace la comparación real por contrato
-- (fecha_evento − hoy = dias_antes configurado), corrigiendo el bug de
-- v1 documentado en DESIGN_LOG.md (que comparaba contra el día del mes,
-- no contra la fecha real de cada contrato).
create or replace function obtener_recordatorios_pendientes(p_secret_cron text)
returns table (
  empresa_id int,
  codigo_contrato text,
  tipo text,
  telefono text,
  nombre text,
  direccion text,
  fecha_evento text, -- fin_contrato / prox_actualizacion son TEXT en la base real, no date
  indice text
)
language plpgsql
security definer
as $$
declare
  v_secret_real text;
begin
  select decrypted_secret into v_secret_real
  from vault.decrypted_secrets where name = 'cron_secret';

  if p_secret_cron is null or p_secret_cron != v_secret_real then
    raise exception 'Secreto de cron inválido';
  end if;

  return query
  select
    c.empresa_id,
    c.codigo::text as codigo_contrato,
    r.tipo,
    regexp_replace(coalesce(i.telefono, ''), '[\s-]', '', 'g') as telefono,
    trim(coalesce(i.nombres, '') || ' ' || coalesce(i.apellidos, '')) as nombre,
    trim(
      coalesce(p.calle, '') || ' ' || coalesce(p.numero, '') ||
      case when p.piso is not null and p.piso != '' then ' Piso ' || p.piso else '' end ||
      case when p.departamento is not null and p.departamento != '' then ' Depto ' || p.departamento else '' end
    ) as direccion,
    case when r.tipo = 'vencimiento' then c.fin_contrato else c.prox_actualizacion end as fecha_evento,
    c.indice
  from contratos c
  join whatsapp_recordatorios r on r.empresa_id = c.empresa_id and r.activo = true and r.dias_antes is not null
  join configuraciones_empresa ce on ce.empresa_id = c.empresa_id and ce.whatsapp_habilitado = true
  join inquilinos i on i.dni = c.dni_inquilino and i.empresa_id = c.empresa_id
  join propiedades p on p.alias_propiedad = c.alias_propiedad and p.empresa_id = c.empresa_id
  where c.estado = 'Activo'
    and coalesce(i.telefono, '') != ''
    and (
      (r.tipo = 'vencimiento' and c.fin_contrato is not null
        and (c.fin_contrato::date - current_date) = r.dias_antes)
      or
      (r.tipo = 'actualizacion' and c.prox_actualizacion is not null
        and (c.prox_actualizacion::date - current_date) = r.dias_antes)
    )
    -- No repetir si ya se reservó/envió hoy para este contrato+tipo.
    -- Cast a ::text de ambos lados porque no tenemos confirmado si
    -- whatsapp_recordatorios_log.codigo_contrato (tabla pre-existente de
    -- v1) es text o integer — así funciona sin importar cuál sea.
    and not exists (
      select 1 from whatsapp_recordatorios_log l
      where l.codigo_contrato::text = c.codigo::text and l.tipo = r.tipo and l.fecha_envio = current_date::text
    );
end;
$$;

-- ── 6. Credenciales de WhatsApp para el cron (mismo criterio que en la app) ─
-- Espejo de lib/whatsapp/enviar.ts::getCredencialesWhatsapp(), pero
-- callable sin sesión de usuario — validado por el mismo secreto de cron.
create or replace function obtener_credenciales_whatsapp_cron(p_empresa_id int, p_secret_cron text)
returns table (phone_id text, token text)
language plpgsql
security definer
as $$
declare
  v_secret_real text;
  v_row record;
  v_secret_id text;
  v_phone_id text;
begin
  select decrypted_secret into v_secret_real
  from vault.decrypted_secrets where name = 'cron_secret';

  if p_secret_cron is null or p_secret_cron != v_secret_real then
    raise exception 'Secreto de cron inválido';
  end if;

  select ce.whatsapp_credenciales_propias, ce.whatsapp_phone_id, ce.whatsapp_token_secret_id,
         wn.phone_id as pool_phone_id, wn.token_secret_id as pool_secret_id
  into v_row
  from configuraciones_empresa ce
  left join whatsapp_numeros wn on wn.id = ce.whatsapp_numero_id
  where ce.empresa_id = p_empresa_id;

  if v_row is null then
    return;
  end if;

  if v_row.whatsapp_credenciales_propias then
    v_secret_id := v_row.whatsapp_token_secret_id;
    v_phone_id := v_row.whatsapp_phone_id;
  else
    v_secret_id := v_row.pool_secret_id;
    v_phone_id := v_row.pool_phone_id;
  end if;

  if v_secret_id is null or v_phone_id is null then
    return;
  end if;

  return query
  select v_phone_id, leer_token_whatsapp(v_secret_id);
end;
$$;
