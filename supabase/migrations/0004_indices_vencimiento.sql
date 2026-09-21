-- =====================================================================
-- 0004_indices_vencimiento.sql
--
-- Módulo 3 — motor de índices ICL/IPC/UVA + vencimiento automático de
-- contratos + archivado. Ver docs/DESIGN_LOG.md para el diseño completo
-- y el razonamiento detrás de cada decisión (candados, SECURITY DEFINER
-- en vez de service_role, etc.)
--
-- 100% aditivo — no toca ninguna columna ni tabla que use v1.
-- =====================================================================

-- ── 1. Tabla de índices, pública (sin empresa_id) ──────────────────────
create table if not exists indices_historicos (
  tipo text not null check (tipo in ('ICL', 'IPC', 'UVA')),
  fecha date not null,
  valor numeric not null,
  primary key (tipo, fecha)
);

alter table indices_historicos enable row level security;

drop policy if exists "lectura_publica" on indices_historicos;
create policy "lectura_publica" on indices_historicos for select
  using (true); -- cualquier usuario autenticado puede leer, son datos públicos del BCRA/INDEC

-- Sin política de escritura para "authenticated": la única forma de
-- escribir es a través de upsert_indice() (SECURITY DEFINER, abajo).

-- ── 2. Columnas nuevas ───────────────────────────────────────────────
alter table configuraciones_empresa
  add column if not exists cron_indices_habilitado boolean not null default false;

alter table contratos
  add column if not exists fecha_finalizacion date,
  add column if not exists finalizado_por text check (finalizado_por in ('auto_vencimiento', 'renovacion')),
  add column if not exists archivado boolean not null default false;

comment on column contratos.finalizado_por is
  'NULL para finalizaciones manuales de v1 (renovación existente, líneas '
  '6023-6028 de app.py, que no llena esta columna) o contratos ya '
  'finalizados antes de esta migración. auto_vencimiento = lo marcó '
  'vencer_contratos_automaticamente(). renovacion = se cargó un contrato '
  'nuevo para la misma propiedad.';

-- ── 3. upsert_indice — guarda un punto de la serie (cron diario) ──────
create or replace function upsert_indice(p_tipo text, p_fecha date, p_valor numeric)
returns void
language plpgsql
security definer
as $$
begin
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
$$;

-- ── 4. vencer_contratos_automaticamente — SIN período de gracia ───────
-- Corre SIEMPRE para todas las empresas (sin toggle — decisión del
-- usuario, ver DESIGN_LOG.md). "Hoy" se calcula en huso horario
-- Argentina, no en UTC (evita que un contrato venza un día antes/después
-- por la diferencia horaria del servidor del cron).
create or replace function vencer_contratos_automaticamente(p_secret_cron text)
returns int
language plpgsql
security definer
as $$
declare
  v_secret_real text;
  v_hoy_ar date;
  v_afectados int;
begin
  select decrypted_secret into v_secret_real
  from vault.decrypted_secrets where name = 'cron_secret';

  if p_secret_cron is null or p_secret_cron != v_secret_real then
    raise exception 'Secreto de cron inválido';
  end if;

  v_hoy_ar := (now() at time zone 'America/Argentina/Buenos_Aires')::date;

  update contratos
  set estado = 'Finalizado',
      fecha_finalizacion = v_hoy_ar,
      finalizado_por = 'auto_vencimiento'
  where estado = 'Activo'
    and fin_contrato is not null
    and fin_contrato::date <= v_hoy_ar; -- fin_contrato es text en la base real

  get diagnostics v_afectados = row_count;
  return v_afectados;
end;
$$;

-- ── 5. aplicar_actualizaciones_indices — botón manual o cron ──────────
-- p_empresa_id NULL = modo global (cron, TODAS las empresas con
-- cron_indices_habilitado = true). p_empresa_id con valor = modo
-- botón manual, valida que sea la propia empresa del usuario.
-- p_solo_pendientes: true = saltea contratos ya calculados este mes
-- (candado del cron, SIEMPRE true en modo cron). El botón manual lo
-- expone como checkbox, destildado por defecto (igual que v1).
--
-- IMPORTANTE: esta función NO calcula el valor en sí (eso requiere
-- pegarle a APIs externas — BCRA/datos.gob.ar — algo que Postgres no
-- puede hacer sin una extensión de red). Server Action / Route Handler
-- (TypeScript) hacen el cálculo con lib/indices/calculo.ts y llaman a
-- esta función solo para el paso final: escribir el resultado, con la
-- misma validación de elegibilidad centralizada acá para que el botón
-- manual y el cron nunca diverjan en el criterio.
create or replace function aplicar_actualizacion_individual(
  p_codigo_contrato int,
  p_valor_calculado numeric,
  p_empresa_id int,
  p_secret_cron text default null
)
returns boolean
language plpgsql
security definer
as $$
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
  elsif p_empresa_id != auth_empresa_id() and auth_rol() != 'superadmin' then
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
$$;

-- ── 6. Elegibilidad para el motor bulk (Planilla / cron) ───────────────
-- Devuelve los contratos candidatos a recalcular índice este mes, con
-- el mismo criterio que ya usaba v1 (prox_actualizacion este mes, índice
-- ICL/IPC/UVA, activo) + el candado "solo pendientes" cuando corresponde.
create or replace function contratos_elegibles_actualizacion(
  p_empresa_id int, -- NULL = todas las empresas (modo cron global)
  p_solo_pendientes boolean default false
)
returns table (
  codigo int, empresa_id int, alias_propiedad text, monto_inicial numeric,
  fecha_inicio text, indice text, frecuencia_meses int
)
language sql
security definer
stable
as $$
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
    and (p_empresa_id is not null or ce.cron_indices_habilitado = true) -- modo cron: solo empresas opt-in
    and (
      not p_solo_pendientes
      or c.alquiler_calculado_fecha is null
      or date_trunc('month', c.alquiler_calculado_fecha::date) != date_trunc('month', current_date)
    );
$$;
