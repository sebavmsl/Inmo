-- =====================================================================
-- 0007_auditoria_cambios.sql
--
-- Módulo 5 — auditoría genérica de contratos/propiedades/inquilinos.
-- Ver docs/DESIGN_LOG.md, sección "Tabla nueva auditoria_cambios".
--
-- 100% aditivo. No afecta a v1: el trigger se dispara sin importar qué
-- rol hace el INSERT/UPDATE (v1 usa psycopg2 con el rol postgres.<ref>,
-- que no está exento de triggers — a diferencia de RLS, los triggers sí
-- aplican a cualquier rol). Está deliberadamente blindado con
-- EXCEPTION WHEN OTHERS para que, aunque algo salga mal acá, nunca
-- bloquee la escritura real de un contrato/propiedad/inquilino (mismo
-- criterio que recalcular_saldo_actual(), ver 0003_saldo_contratos.sql).
-- =====================================================================

create table if not exists auditoria_cambios (
  id bigserial primary key,
  empresa_id int not null,
  tabla text not null,          -- 'contratos' | 'propiedades' | 'inquilinos'
  registro_id text not null,    -- el id de la fila afectada
  tipo_evento text not null,    -- 'creacion' | 'edicion' | 'borrado_masivo'
  cambios jsonb,                -- solo los campos que cambiaron: {"alquiler": {"antes": X, "despues": Y}, ...}
  realizado_por text,           -- username, o 'sistema' para eventos automáticos (cron)
  fecha timestamptz not null default now()
);

alter table auditoria_cambios enable row level security;

drop policy if exists "empresa_isolation_select" on auditoria_cambios;
create policy "empresa_isolation_select" on auditoria_cambios for select
  using (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id());
-- Sin política de escritura para "authenticated": solo se llena vía el
-- trigger (SECURITY DEFINER) o eliminar_registros_bloque() — nunca
-- directo desde la UI.

create or replace function fn_auditar_cambios()
returns trigger
language plpgsql
security definer
as $$
declare
  v_cambios jsonb := '{}'::jsonb;
  v_key text;
  v_username text;
begin
  select username into v_username from usuarios_central where auth_user_id = auth.uid();
  v_username := coalesce(v_username, 'sistema');

  if TG_OP = 'INSERT' then
    insert into auditoria_cambios (empresa_id, tabla, registro_id, tipo_evento, cambios, realizado_por)
    values (NEW.empresa_id, TG_TABLE_NAME, NEW.id::text, 'creacion', to_jsonb(NEW), v_username);
    return NEW;

  elsif TG_OP = 'UPDATE' then
    for v_key in select jsonb_object_keys(to_jsonb(NEW)) loop
      -- saldo_actual se excluye a propósito (ver DESIGN_LOG.md,
      -- "Interacción entre triggers — ruido en auditoria_cambios"):
      -- cambia en CADA pago vía trg_recalcular_saldo, y loggearlo acá
      -- inundaría la auditoría con una entrada por cada cobro en vez de
      -- reservarla para ediciones humanas intencionales.
      if v_key = 'saldo_actual' then
        continue;
      end if;
      if to_jsonb(OLD)->v_key is distinct from to_jsonb(NEW)->v_key then
        v_cambios := v_cambios || jsonb_build_object(v_key,
          jsonb_build_object('antes', to_jsonb(OLD)->v_key, 'despues', to_jsonb(NEW)->v_key));
      end if;
    end loop;

    if v_cambios != '{}'::jsonb then
      insert into auditoria_cambios (empresa_id, tabla, registro_id, tipo_evento, cambios, realizado_por)
      values (NEW.empresa_id, TG_TABLE_NAME, NEW.id::text, 'edicion', v_cambios, v_username);
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
$$;

drop trigger if exists trg_auditar on contratos;
create trigger trg_auditar after insert or update on contratos
  for each row execute function fn_auditar_cambios();

drop trigger if exists trg_auditar on propiedades;
create trigger trg_auditar after insert or update on propiedades
  for each row execute function fn_auditar_cambios();

drop trigger if exists trg_auditar on inquilinos;
create trigger trg_auditar after insert or update on inquilinos
  for each row execute function fn_auditar_cambios();
