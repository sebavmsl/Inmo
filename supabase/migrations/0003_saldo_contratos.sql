-- =====================================================================
-- 0003_saldo_contratos.sql
--
-- Saldo corriente por contrato, cacheado y mantenido por un TRIGGER de
-- Postgres — no por código de aplicación. Esto es intencional: mientras
-- v1 y v2 convivan cobrando pagos en paralelo, ninguna de las dos apps
-- necesita saber que esta columna existe. El trigger reacciona a
-- cualquier INSERT/UPDATE en `pagos_historial`, venga de psycopg2 (v1)
-- o de Supabase (v2), sin acoplar una versión con la otra.
--
-- No modifica ni resta ninguna columna existente — es 100% aditivo.
-- =====================================================================

-- ── 1. Columna nueva en contratos ─────────────────────────────────────
alter table contratos
  add column if not exists saldo_actual numeric not null default 0;
-- Positivo = el inquilino debe. Negativo = saldo a favor del inquilino.

comment on column contratos.saldo_actual is
  'Saldo corriente (cuenta corriente), mantenido automáticamente por '
  'trg_recalcular_saldo. No editar a mano salvo corrección puntual '
  '(y en ese caso, mejor cargar una fila de pagos_historial tipo '
  'Corrección para que quede el rastro contable).';

-- Ningún usuario (ni siquiera admin/superadmin desde el cliente) puede
-- escribir esta columna directamente — solo el trigger, que corre como
-- SECURITY DEFINER. Sin esto, cualquier UPDATE normal a `contratos`
-- (permitido por las políticas RLS de la migración 0001, que cubren la
-- fila entera) podría pisar el saldo real sin dejar rastro en
-- pagos_historial. Esto es a nivel de columna, no de fila — el resto de
-- columnas de `contratos` siguen editables como siempre.
revoke update (saldo_actual) on contratos from authenticated;

-- `pagos_historial` es un libro contable — solo se agregan filas nuevas,
-- nunca se edita ni se borra una ya guardada (confirmado revisando
-- app.py: el único UPDATE que v1 le hace a esta tabla es el paso de
-- "saldar períodos anteriores", que el modelo de cuenta corriente ya
-- reemplaza por completo). Cualquier corrección se hace agregando una
-- fila tipo Corrección — nunca editando el pasado. Esto también protege
-- saldo_actual de forma indirecta: si alguien pudiera editar el
-- saldo_pendiente de la última fila de un contrato, el trigger lo
-- tomaría como válido igual.
revoke update, delete on pagos_historial from authenticated;

-- ── 2. Función que recalcula el saldo de UN contrato ──────────────────
-- MODELO: cuenta corriente. Cada fila de pagos_historial ya guarda el
-- ACUMULADO total hasta ese momento (no un saldo aislado de su propio
-- período) — ver docs/DESIGN_LOG.md, sección "Saldo de contratos".
-- Por eso el trigger NO suma por período (sumar duplicaría deuda ya
-- arrastrada de un mes a otro): solo copia el saldo_pendiente de la
-- ÚLTIMA fila insertada para ese contrato.
create or replace function recalcular_saldo_actual()
returns trigger
language plpgsql
security definer
as $$
declare
  v_codigo text;
  v_saldo numeric;
begin
  v_codigo := coalesce(new.codigo_contrato, old.codigo_contrato);

  select saldo_pendiente
  into v_saldo
  from pagos_historial
  where codigo_contrato = v_codigo
  order by id desc
  limit 1;

  update contratos
  set saldo_actual = coalesce(v_saldo, 0)
  where codigo = v_codigo;

  return null; -- trigger AFTER: el valor de retorno se ignora
exception when others then
  -- Blindaje: un fallo acá (por ejemplo, un caso de borde de datos que no
  -- contemplamos) NUNCA debe poder bloquear la escritura real de un pago
  -- en pagos_historial — ni la de v1 ni la de v2. En el peor caso, se
  -- pierde este recálculo puntual de saldo_actual (se corrige solo en el
  -- próximo pago de ese contrato), pero el INSERT/UPDATE original que
  -- disparó el trigger siempre se completa.
  return null;
end;
$$;

-- ── 3. Trigger: se dispara solo, para cualquier INSERT/UPDATE ─────────
-- (DELETE incluido por si algún día se borra una fila mal cargada,
-- como el caso de prueba que ya limpiamos a mano en esta conversación)
drop trigger if exists trg_recalcular_saldo on pagos_historial;
create trigger trg_recalcular_saldo
  after insert or update or delete on pagos_historial
  for each row
  execute function recalcular_saldo_actual();

-- ── 4. Backfill: calcular saldo_actual para los contratos existentes ──
-- Corre una sola vez, con los datos que ya están cargados hoy.
-- MISMO criterio que el trigger (ver función arriba): la ÚLTIMA fila del
-- contrato (por id, sin agrupar por período) ya refleja el total real
-- acumulado, incluso para datos históricos de v1 — la fórmula de v1
-- (total_a_cubrir = cargos del período + deuda vieja arrastrada) hornea
-- la deuda acumulada dentro de cada fila nueva, así que no hace falta
-- sumar entre períodos para el arranque tampoco.
update contratos c
set saldo_actual = coalesce((
  select ph.saldo_pendiente
  from pagos_historial ph
  where ph.codigo_contrato = c.codigo
  order by ph.id desc
  limit 1
), 0);

-- =====================================================================
-- Uso futuro (Dashboard, panel de deudas, Portal del Inquilino):
--   SELECT codigo, saldo_actual FROM contratos WHERE saldo_actual > 0
--     ORDER BY saldo_actual DESC;
-- Instantáneo — no recorre pagos_historial en el momento de la consulta.
-- =====================================================================
