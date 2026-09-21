-- =====================================================================
-- 0009_registrar_liquidacion.sql
--
-- Módulo 7 — Rendición a Propietarios. Arregla el bug de atomicidad
-- confirmado en v1 (ver docs/DESIGN_LOG.md, "Retención de gastos en
-- Rendición"): v1 hace el INSERT de la liquidación y el UPDATE de
-- gastos_propiedades.cobrado en DOS transacciones separadas — si la
-- segunda falla después de que la primera ya se confirmó, los gastos
-- quedan sin marcar y se retienen DE NUEVO en la próxima liquidación,
-- duplicando el descuento al propietario.
--
-- Una sola función = una sola transacción = todo o nada.
-- No necesita SECURITY DEFINER: opera sobre datos de la propia empresa
-- del usuario logueado, RLS normal alcanza.
-- =====================================================================

create or replace function registrar_liquidacion_propietario(
  p_empresa_id int,
  p_propietario text,
  p_periodo text,
  p_monto_calculado numeric,
  p_saldo_anterior numeric,
  p_monto_retencion_gastos numeric,
  p_monto_a_liquidar numeric,
  p_monto_liquidado numeric,
  p_saldo_pendiente numeric,
  p_ids_gastos int[],
  p_registrado_por text
)
returns void
language plpgsql
as $$
begin
  insert into liquidaciones_propietarios (
    empresa_id, propietario, periodo, monto_calculado, saldo_anterior,
    monto_retencion_gastos, monto_a_liquidar, monto_liquidado,
    saldo_pendiente, fecha_liquidacion, registrado_por
  ) values (
    p_empresa_id, p_propietario, p_periodo, p_monto_calculado, p_saldo_anterior,
    p_monto_retencion_gastos, p_monto_a_liquidar, p_monto_liquidado,
    p_saldo_pendiente, now(), p_registrado_por
  )
  on conflict (empresa_id, propietario, periodo) do update set
    monto_calculado = excluded.monto_calculado,
    saldo_anterior = excluded.saldo_anterior,
    monto_retencion_gastos = excluded.monto_retencion_gastos,
    monto_a_liquidar = excluded.monto_a_liquidar,
    monto_liquidado = excluded.monto_liquidado,
    saldo_pendiente = excluded.saldo_pendiente,
    fecha_liquidacion = excluded.fecha_liquidacion,
    registrado_por = excluded.registrado_por;

  if p_ids_gastos is not null and array_length(p_ids_gastos, 1) > 0 then
    update gastos_propiedades
    set cobrado = true, periodo_cobrado = p_periodo
    where empresa_id = p_empresa_id and id = any(p_ids_gastos);
  end if;
  -- Si el UPDATE de arriba fallara por algún motivo, todo lo anterior
  -- (el INSERT de la liquidación) se revierte también — misma función,
  -- misma transacción. Ya no puede quedar un estado a medias.
end;
$$;
