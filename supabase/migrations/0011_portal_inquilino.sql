-- =====================================================================
-- 0011_portal_inquilino.sql
--
-- Módulo 9 — Portal del Inquilino. Único módulo sin equivalente en v1
-- (diseño desde cero). Ver docs/DESIGN_LOG.md para el razonamiento
-- completo.
-- =====================================================================

-- ── 1. Autenticación — mismo mecanismo que usuarios_central ────────────
alter table inquilinos
  add column if not exists auth_user_id uuid references auth.users(id);

-- SIN índice único sobre auth_user_id a propósito: el mismo
-- auth_user_id puede repetirse en varias filas de `inquilinos` (una
-- persona real, inquilino de dos empresas distintas con el mismo
-- email/cuenta — ver corrección de multi-tenencia en DESIGN_LOG.md). La
-- prevención de "no crear una cuenta de Auth duplicada para el mismo
-- email" se hace en el Server Action (enviarLinkAcceso, Módulo 10),
-- reusando el auth_user_id existente en vez de crear uno nuevo.

-- ── 2. Aislamiento de datos — políticas ADICIONALES (se combinan con OR
--      sobre las políticas de staff de la migración 0001, no las
--      reemplazan) ─────────────────────────────────────────────────────
-- Corrección de multi-tenencia (ver DESIGN_LOG.md): comparación por
-- conjunto, no una función escalar — el mismo auth_user_id puede
-- corresponder a inquilinos de más de una empresa.
drop policy if exists "inquilino_lee_sus_contratos" on contratos;
create policy "inquilino_lee_sus_contratos" on contratos for select
  using (dni_inquilino in (select dni from inquilinos where auth_user_id = auth.uid()));

drop policy if exists "inquilino_lee_sus_pagos" on pagos_historial;
create policy "inquilino_lee_sus_pagos" on pagos_historial for select
  using (
    codigo_contrato in (
      select c.codigo from contratos c
      where c.dni_inquilino in (select dni from inquilinos where auth_user_id = auth.uid())
    )
  );

-- El inquilino puede ver su propia fila en `inquilinos` (para mostrar
-- sus propios datos en el Portal).
drop policy if exists "inquilino_lee_su_propia_fila" on inquilinos;
create policy "inquilino_lee_su_propia_fila" on inquilinos for select
  using (auth_user_id = auth.uid());

-- ── 3. Comprobantes subidos por el inquilino ────────────────────────────
create table if not exists comprobantes_inquilino (
  id bigserial primary key,
  empresa_id int not null,
  codigo_contrato text not null,
  storage_path text not null,
  monto_declarado numeric,
  fecha_subida timestamptz not null default now(),
  estado text not null default 'pendiente' check (estado in ('pendiente', 'aprobado', 'rechazado')),
  revisado_por text,
  fecha_revision timestamptz
);

alter table comprobantes_inquilino enable row level security;

drop policy if exists "staff_lee_comprobantes_inquilino" on comprobantes_inquilino;
create policy "staff_lee_comprobantes_inquilino" on comprobantes_inquilino for select
  using (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id());

drop policy if exists "staff_actualiza_comprobantes_inquilino" on comprobantes_inquilino;
create policy "staff_actualiza_comprobantes_inquilino" on comprobantes_inquilino for update
  using (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id())
  with check (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id());

drop policy if exists "inquilino_lee_sus_comprobantes_subidos" on comprobantes_inquilino;
create policy "inquilino_lee_sus_comprobantes_subidos" on comprobantes_inquilino for select
  using (codigo_contrato in (
    select c.codigo from contratos c
    where c.dni_inquilino in (select dni from inquilinos where auth_user_id = auth.uid())
  ));

drop policy if exists "inquilino_sube_comprobantes" on comprobantes_inquilino;
create policy "inquilino_sube_comprobantes" on comprobantes_inquilino for insert
  with check (codigo_contrato in (
    select c.codigo from contratos c
    where c.dni_inquilino in (select dni from inquilinos where auth_user_id = auth.uid())
  ));

-- ── 4. Reclamos del inquilino, con vínculo opcional a un gasto real ────
create table if not exists reclamos_inquilino (
  id bigserial primary key,
  empresa_id int not null,
  codigo_contrato text not null,
  descripcion text not null,
  estado text not null default 'abierto' check (estado in ('abierto', 'en_progreso', 'resuelto')),
  fecha timestamptz not null default now(),
  respuesta_staff text,
  gasto_id int references gastos_propiedades(id)
);

comment on column reclamos_inquilino.gasto_id is
  'Nullable — conecta el reclamo con el gasto real que generó al '
  'resolverlo (ej. una reparación). Trazabilidad en los dos sentidos. '
  'Ver docs/DESIGN_LOG.md, Módulo 9.';

alter table reclamos_inquilino enable row level security;

drop policy if exists "staff_lee_reclamos" on reclamos_inquilino;
create policy "staff_lee_reclamos" on reclamos_inquilino for select
  using (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id());

drop policy if exists "staff_actualiza_reclamos" on reclamos_inquilino;
create policy "staff_actualiza_reclamos" on reclamos_inquilino for update
  using (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id())
  with check (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id());

drop policy if exists "inquilino_lee_sus_reclamos" on reclamos_inquilino;
create policy "inquilino_lee_sus_reclamos" on reclamos_inquilino for select
  using (codigo_contrato in (
    select c.codigo from contratos c
    where c.dni_inquilino in (select dni from inquilinos where auth_user_id = auth.uid())
  ));

drop policy if exists "inquilino_crea_reclamos" on reclamos_inquilino;
create policy "inquilino_crea_reclamos" on reclamos_inquilino for insert
  with check (codigo_contrato in (
    select c.codigo from contratos c
    where c.dni_inquilino in (select dni from inquilinos where auth_user_id = auth.uid())
  ));

-- ── 5. Storage — aislamiento de archivos (ver DESIGN_LOG.md) ───────────
-- Convención de carpetas: {bucket}/{empresa_id}/{codigo_contrato}/archivo
-- Buckets a crear manualmente en el dashboard de Supabase Storage:
--   comprobantes-pago (privado), comprobantes-inquilino (privado)

drop policy if exists "staff_lee_comprobantes" on storage.objects;
create policy "staff_lee_comprobantes" on storage.objects for select
  using (
    bucket_id in ('comprobantes-pago', 'comprobantes-inquilino')
    and (auth_rol() = 'superadmin' or (storage.foldername(name))[1] = auth_empresa_id()::text)
  );

drop policy if exists "inquilino_lee_sus_comprobantes" on storage.objects;
create policy "inquilino_lee_sus_comprobantes" on storage.objects for select
  using (
    bucket_id in ('comprobantes-pago', 'comprobantes-inquilino')
    and (storage.foldername(name))[2] in (
      select codigo from contratos where dni_inquilino in (select dni from inquilinos where auth_user_id = auth.uid())
    )
  );

drop policy if exists "inquilino_sube_comprobantes_storage" on storage.objects;
create policy "inquilino_sube_comprobantes_storage" on storage.objects for insert
  with check (
    bucket_id = 'comprobantes-inquilino'
    and (storage.foldername(name))[2] in (
      select codigo from contratos where dni_inquilino in (select dni from inquilinos where auth_user_id = auth.uid())
    )
  );
