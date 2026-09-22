-- =====================================================================
-- 0018_rendicion_expensas_flag.sql
--
-- Módulo 7 — Rendición a Propietarios (continuación).
--
-- Feature nueva de v2, sin equivalente en v1: algunas propiedades tienen
-- su consorcio/administración de expensas manejado directamente por el
-- propietario — la inmobiliaria solo hace de "caño" (cobra la expensa
-- del inquilino y la reenvía tal cual al consorcio), no es plata que
-- realmente le corresponda retener y rendir al propietario como parte
-- de lo cobrado. Para esos casos, la expensa NO debe sumar al "Total
-- Cobrado" / "Neto a Rendir" del propietario — pasa a ser informativa,
-- mismo tratamiento que ya tienen "Servicios" y "Otros".
--
-- Default FALSE: comportamiento actual sin cambios para todo el mundo
-- (expensas incluidas en el neto a rendir, igual que v1) hasta que se
-- tilde el flag caso por caso desde Auxiliares.
-- =====================================================================

alter table propiedades
  add column if not exists expensas_administrada_por_propietario boolean not null default false;

comment on column propiedades.expensas_administrada_por_propietario is
  'Si es TRUE, las expensas cobradas de esta propiedad NO se suman al Neto a Rendir del propietario (se muestran solo como informativo) — la inmobiliaria las cobra y reenvía al consorcio, no le corresponden al propietario.';
