-- =====================================================================
-- 0017_auxiliares_completo.sql
--
-- Módulo 3 — Auxiliares completo (ver docs/DESIGN_LOG.md). Dos cosas:
--
-- 1. Columnas de `propiedades` que el alta de v1 sí tenía pero nunca se
--    portaron a v2 (ciudad, provincia, tipo, nis, cuenta_gas, finca,
--    cuenta_ooss, nro_padron) — necesarias para el alta/edición completos.
--
-- 2. Confirma el bug real encontrado en v1 (no es una regresión de v2):
--    su "Editar Propiedad" solo permitía tocar alias/calle/número/depto/
--    grupo — ni propietario ni estas 8 columnas eran editables después
--    del alta, a diferencia del formulario de alta que sí las pedía
--    todas. v2 corrige esto: la edición cubre TODOS los campos.
-- =====================================================================

alter table propiedades
  add column if not exists ciudad text,
  add column if not exists provincia text,
  add column if not exists tipo text,
  add column if not exists nis text,
  add column if not exists cuenta_gas text,
  add column if not exists finca text,
  add column if not exists cuenta_ooss text,
  add column if not exists nro_padron text;
