-- =====================================================================
-- 0008_servicios_estructurado.sql
--
-- Módulo 5 — reemplaza el patrón de texto libre + substring matching de
-- `contratos.servicios` por columnas estructuradas y tipadas. Ver
-- docs/DESIGN_LOG.md, sección "contratos.servicios — bug confirmado".
--
-- Motivo del bug que esto corrige: v1 codificaba "a cargo de" (Elec,
-- Gas, Mun, OOSS, Exp, Imp.Inmob) como texto dentro de `servicios`, y
-- Módulo 4 intentaba leerlo de vuelta con un substring que nunca podía
-- matchear el formato real guardado — el Impuesto Inmobiliario "a cargo
-- del inquilino" nunca se cobraba, aunque estuviera configurado así.
-- Confirmado sin impacto financiero en producción (0 filas con esa
-- config activa) — se corrige de raíz igual, no se parchea el regex.
--
-- 100% aditivo: `contratos.servicios` queda intacta, v1 la sigue usando
-- exactamente igual.
-- =====================================================================

alter table contratos
  add column if not exists cargo_electricidad text check (cargo_electricidad in ('Inquilino','Propietario')) default 'Inquilino',
  add column if not exists cargo_gas text check (cargo_gas in ('Inquilino','Propietario')) default 'Inquilino',
  add column if not exists cargo_municipalidad text check (cargo_municipalidad in ('Inquilino','Propietario')) default 'Inquilino',
  add column if not exists cargo_ooss text check (cargo_ooss in ('Inquilino','Propietario')) default 'Inquilino',
  add column if not exists cargo_expensas text check (cargo_expensas in ('Inquilino','Propietario')) default 'Inquilino',
  add column if not exists cargo_imp_inmobiliario text check (cargo_imp_inmobiliario in ('Inquilino','Propietario')) default 'Propietario';
  -- 'Propietario' es el default real de v1 para Impuesto Inmobiliario
  -- (índice 1 del selectbox) — los demás arrancan en 'Inquilino'.

comment on column contratos.cargo_imp_inmobiliario is
  'Reemplaza el chequeo roto "[Imp.Inmob: Inquilino]" sobre contratos.servicios '
  '(ver DESIGN_LOG.md). Columna real, tipada, sin parseo de texto.';

-- ── Backfill: migrar la configuración ya cargada en v1 (texto libre) ──
-- Correr una sola vez, después de crear las columnas. Idempotente — se
-- puede re-correr sin riesgo. NO toca contratos.servicios.
update contratos
set
  cargo_electricidad    = coalesce((regexp_match(servicios, 'Elec: (\w+)'))[1], 'Inquilino'),
  cargo_gas              = coalesce((regexp_match(servicios, 'Gas: (\w+)'))[1], 'Inquilino'),
  cargo_municipalidad    = coalesce((regexp_match(servicios, 'Mun: (\w+)'))[1], 'Inquilino'),
  cargo_ooss             = coalesce((regexp_match(servicios, 'OOSS: (\w+)'))[1], 'Inquilino'),
  cargo_expensas         = coalesce((regexp_match(servicios, 'Exp: (\w+)'))[1], 'Inquilino'),
  -- OJO: '\| Inmob:' con la barra adelante — para NO matchear el
  -- prefijo roto "Imp.Inmob: X" (que también contiene "Inmob: X" adentro).
  cargo_imp_inmobiliario = coalesce((regexp_match(servicios, '\| Inmob: (\w+)'))[1], 'Propietario')
where servicios is not null;
