-- =====================================================================
-- 0005_planilla_verificaciones.sql
--
-- Reemplaza el checkbox efímero de sesión de v1 (Streamlit) por un
-- estado persistente y compartido entre usuarios de la empresa — ver
-- docs/DESIGN_LOG.md, sección "Tabla nueva planilla_verificaciones".
-- =====================================================================

create table if not exists planilla_verificaciones (
  id bigserial primary key,
  empresa_id int not null,
  codigo_contrato int not null,
  periodo text not null, -- 'YYYY-MM', mes CALENDARIO — no confundir con
                          -- pagos_historial.periodo ("Mes N de M", relativo
                          -- al contrato). Ver DESIGN_LOG.md, "Hallazgo —
                          -- periodo NO es intercambiable entre tablas".
  verificado boolean not null default false,
  expensas_adhoc numeric, -- override puntual para el WhatsApp de este mes; NULL = usar el valor del contrato
  verificado_por text,
  verificado_fecha timestamptz,
  unique (codigo_contrato, periodo)
);

alter table planilla_verificaciones enable row level security;

drop policy if exists "empresa_isolation" on planilla_verificaciones;
create policy "empresa_isolation" on planilla_verificaciones for all
  using (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id())
  with check (auth_rol() = 'superadmin' or empresa_id = auth_empresa_id());
