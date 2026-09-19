-- =====================================================================
-- 0012_panel_gestion.sql
--
-- Módulo 10 — Panel de Gestión. Ver docs/DESIGN_LOG.md para el diseño
-- completo (alta de empresa con service_role, eliminar empresa,
-- borrado en bloque).
-- =====================================================================

-- ── 1. Relajar NOT NULL para usuarios creados 100% en v2 ───────────────
-- v1 sigue completando estas columnas con datos reales para los
-- usuarios que él mismo crea, como siempre — esto solo habilita que un
-- usuario nuevo de v2 (que nunca va a loguearse en v1) pueda dejarlas
-- NULL en vez de un placeholder falso.
alter table usuarios_central alter column archivo_db drop not null;
alter table usuarios_central alter column password_hash drop not null;

-- ── 2. eliminar_empresa_completa — arregla 2 bugs confirmados en v1 ────
-- Bug 1: v1 intenta "DELETE FROM permisos_usuario WHERE empresa_id = %s"
--   pero esa tabla no tiene esa columna (falla silenciada por
--   try/except) — nunca se borra. Acá se filtra por username.
-- Bug 2: liquidaciones_propietarios y configuraciones_empresa no estaban
--   en la lista de tablas a borrar de v1 — quedaban huérfanas.
create or replace function eliminar_empresa_completa(p_empresa_id int, p_confirmacion_nombre text)
returns void
language plpgsql
security definer
as $$
declare
  v_nombre_real text;
  v_usernames text[];
begin
  if auth_rol() != 'superadmin' then
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
$$;

-- ── 3. eliminar_registros_bloque — reemplaza el panel de borrado de v1 ─
-- Único punto que puede cruzar el REVOKE de pagos_historial (ver
-- 0003_saldo_contratos.sql) — angosto, auditado, restringido a superadmin.
create or replace function eliminar_registros_bloque(
  p_tabla text,
  p_ids int[],
  p_empresa_id int,
  p_confirmacion text
)
returns int
language plpgsql
security definer
as $$
declare
  v_deleted int;
  v_username text;
begin
  if auth_rol() != 'superadmin' then
    raise exception 'Solo superadmin puede usar esta función';
  end if;
  if p_tabla not in ('contratos', 'inquilinos', 'propiedades', 'pagos_historial') then
    raise exception 'Tabla no permitida: %', p_tabla;
  end if;
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
     select %L, %L, id::text, ''borrado_masivo'', to_jsonb(t), %L
     from %I t where empresa_id = %L and id = any(%L::int[])',
    p_empresa_id, p_tabla, coalesce(v_username, 'sistema'), p_tabla, p_empresa_id, p_ids
  );

  execute format('delete from %I where empresa_id = $1 and id = any($2)', p_tabla)
    using p_empresa_id, p_ids;
  get diagnostics v_deleted = row_count;
  return v_deleted;
end;
$$;
