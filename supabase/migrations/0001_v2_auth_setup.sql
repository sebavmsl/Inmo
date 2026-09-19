-- =====================================================================
-- 0001_v2_auth_setup.sql
--
-- Prepara la BD existente (compartida con v1) para Supabase Auth + RLS.
-- NO modifica ni borra nada que use app.py — solo agrega columnas nuevas
-- (nullable) y políticas. v1 sigue funcionando exactamente igual mientras
-- convive con v2.
--
-- Correr con el SQL Editor de Supabase o `supabase db push`.
-- =====================================================================

-- ── 1. Vincular usuarios_central con auth.users ──────────────────────
alter table usuarios_central
  add column if not exists auth_user_id uuid references auth.users(id),
  add column if not exists email text;

create unique index if not exists usuarios_central_auth_user_id_key
  on usuarios_central (auth_user_id);

create unique index if not exists usuarios_central_email_key
  on usuarios_central (email);

-- ── 2. Helper: empresa_id y rol del usuario autenticado actual ───────
-- security definer para poder leer usuarios_central desde una política
-- RLS sin caer en recursión infinita sobre la misma tabla.
create or replace function auth_empresa_id()
returns int
language sql
security definer
stable
as $$
  select empresa_id from usuarios_central where auth_user_id = auth.uid();
$$;

create or replace function auth_rol()
returns text
language sql
security definer
stable
as $$
  select rol from usuarios_central where auth_user_id = auth.uid();
$$;

-- ── 3. RLS: aislamiento multi-empresa ─────────────────────────────────
-- Mismo criterio que el filtro manual por `empresa_id` que hacía cada
-- query de app.py, pero garantizado por Postgres. superadmin ve todo.

alter table propiedades            enable row level security;
alter table inquilinos             enable row level security;
alter table contratos              enable row level security;
alter table pagos_historial        enable row level security;
alter table gastos_propiedades     enable row level security;
alter table liquidaciones_propietarios enable row level security;
alter table configuraciones_empresa    enable row level security;

do $$
declare
  tabla text;
begin
  foreach tabla in array array[
    'propiedades', 'inquilinos', 'contratos', 'pagos_historial',
    'gastos_propiedades', 'liquidaciones_propietarios', 'configuraciones_empresa'
  ]
  loop
    execute format(
      'drop policy if exists "empresa_isolation_select" on %I; '
      'create policy "empresa_isolation_select" on %I for select '
      '  using (auth_rol() = ''superadmin'' or empresa_id = auth_empresa_id());',
      tabla, tabla
    );
    execute format(
      'drop policy if exists "empresa_isolation_write" on %I; '
      'create policy "empresa_isolation_write" on %I for all '
      '  using (auth_rol() = ''superadmin'' or empresa_id = auth_empresa_id()) '
      '  with check (auth_rol() = ''superadmin'' or empresa_id = auth_empresa_id());',
      tabla, tabla
    );
  end loop;
end $$;

-- El rol "propietario" es de solo lectura en la app (ver
-- lib/auth/permissions.ts → esSoloLectura). Se deja documentado acá para
-- cuando se agreguen policies más finas por rol; hoy el control de
-- "solo lectura" vive en la UI (Server Actions no se exponen en esas
-- pantallas para ese rol). Si se quiere blindar también a nivel de BD,
-- agregar una policy adicional que excluya `auth_rol() = 'propietario'`
-- de los `insert/update/delete`.

-- ── 4. usuarios_central y permisos_usuario: cada usuario ve su propia fila ──
alter table usuarios_central  enable row level security;
alter table permisos_usuario  enable row level security;

drop policy if exists "propio_perfil" on usuarios_central;
create policy "propio_perfil" on usuarios_central for select
  using (auth_rol() = 'superadmin' or auth_user_id = auth.uid());

drop policy if exists "propio_perfil_update" on usuarios_central;
create policy "propio_perfil_update" on usuarios_central for update
  using (auth_user_id = auth.uid())
  with check (auth_user_id = auth.uid());

drop policy if exists "propios_permisos" on permisos_usuario;
create policy "propios_permisos" on permisos_usuario for select
  using (
    auth_rol() = 'superadmin'
    or username = (select username from usuarios_central where auth_user_id = auth.uid())
  );

-- =====================================================================
-- Pendiente (Módulo 10 — Panel de Gestión):
--   Script/flujo para crear un auth.users por cada fila existente de
--   usuarios_central (requiere `email` cargado) usando
--   supabase.auth.admin.createUser() con la service_role key, y luego
--   completar `auth_user_id`. Se arma junto con el Panel de Gestión para
--   poder hacerlo usuario por usuario desde la UI en vez de un script
--   de una sola corrida.
-- =====================================================================
