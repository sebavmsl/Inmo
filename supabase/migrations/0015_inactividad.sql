-- =====================================================================
-- 0015_inactividad.sql
--
-- Cierre de sesión por inactividad (ver docs/DESIGN_LOG.md). Configurable
-- por empresa, con dos capas de aplicación (ver lib/supabase/middleware.ts
-- y components/InactivityGuard.tsx):
--   1. Cliente: avisa antes de cerrar y cierra sola con JS.
--   2. Servidor: si por lo que sea el JS no corrió (pestaña dormida,
--      navegador reabierto días después), el middleware igual corta la
--      sesión en el próximo request, comparando contra una cookie de
--      "última actividad" — no depende de esta columna en cada request
--      (ver por qué en middleware.ts), pero el valor sale de acá.
-- =====================================================================

alter table configuraciones_empresa
  add column if not exists timeout_inactividad_minutos int not null default 30;

alter table configuraciones_empresa
  drop constraint if exists timeout_inactividad_minutos_positivo;
alter table configuraciones_empresa
  add constraint timeout_inactividad_minutos_positivo check (timeout_inactividad_minutos > 0);
