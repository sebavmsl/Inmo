-- =====================================================================
-- 0014_edicion_concurrente.sql
--
-- Módulo transversal "Ediciones simultáneas" (ver docs/DESIGN_LOG.md):
-- optimistic locking (bloquea el guardado si alguien más guardó primero,
-- por comparación de `updated_at`) + presencia en vivo (aviso de quién
-- más está con el formulario abierto, heartbeat cada 20s / vencimiento
-- a los 60s). NO es locking pesimista: nadie queda bloqueado para
-- EMPEZAR a editar, solo para GUARDAR sobre un valor desactualizado.
--
-- Reglas de negocio confirmadas por el usuario:
--   - El bloqueo de guardado por conflicto aplica IGUAL a todos los
--     roles, incluido superadmin.
--   - El aviso de "quién más está editando" NUNCA menciona a
--     superadmin, ni directa ni indirectamente: si el único otro editor
--     presente es superadmin, no se muestra ningún aviso (ver
--     lib/concurrencia/queries.ts, listarPresencia()).
-- =====================================================================

-- ── 1. Optimistic locking: updated_at + trigger que lo mantiene ──────
alter table contratos        add column if not exists updated_at timestamptz not null default now();
alter table propiedades      add column if not exists updated_at timestamptz not null default now();
alter table inquilinos       add column if not exists updated_at timestamptz not null default now();
alter table usuarios_central add column if not exists updated_at timestamptz not null default now();

create or replace function fn_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists trg_set_updated_at on contratos;
create trigger trg_set_updated_at before update on contratos
  for each row execute function fn_set_updated_at();

drop trigger if exists trg_set_updated_at on propiedades;
create trigger trg_set_updated_at before update on propiedades
  for each row execute function fn_set_updated_at();

drop trigger if exists trg_set_updated_at on inquilinos;
create trigger trg_set_updated_at before update on inquilinos
  for each row execute function fn_set_updated_at();

drop trigger if exists trg_set_updated_at on usuarios_central;
create trigger trg_set_updated_at before update on usuarios_central
  for each row execute function fn_set_updated_at();

-- ── 2. Presencia en vivo ──────────────────────────────────────────────
-- Una fila por (tabla, registro_id, username): se hace upsert cada 20s
-- mientras el formulario está abierto (heartbeat), y se borra al cerrar
-- el formulario. Una fila con actualizado_en de hace más de 60s se
-- considera vencida (el cliente cerró el navegador sin avisar) — el
-- filtro de vencimiento se aplica en la query, no acá, así no hace
-- falta un cron de limpieza para que la feature funcione.
create table if not exists ediciones_presencia (
  id bigserial primary key,
  empresa_id int not null references empresas(id),
  tabla text not null,
  registro_id text not null,
  username text not null,
  actualizado_en timestamptz not null default now(),
  unique (tabla, registro_id, username)
);

create index if not exists ediciones_presencia_lookup
  on ediciones_presencia (tabla, registro_id, actualizado_en);

alter table ediciones_presencia enable row level security;

drop policy if exists "empresa_isolation_select" on ediciones_presencia;
create policy "empresa_isolation_select" on ediciones_presencia for select
  using (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id());

-- Cada usuario administra únicamente SU PROPIA fila de presencia (el
-- heartbeat y el borrado al cerrar el formulario son siempre sobre uno
-- mismo, nunca sobre la fila de otro usuario).
drop policy if exists "propia_presencia" on ediciones_presencia;
create policy "propia_presencia" on ediciones_presencia for all
  using (
    username = (select username from usuarios_central where auth_user_id = auth.uid())
    and empresa_id = auth_empresa_id()
  )
  with check (
    username = (select username from usuarios_central where auth_user_id = auth.uid())
    and empresa_id = auth_empresa_id()
  );
