-- =====================================================================
-- 0016_cotizacion_usd.sql
--
-- Módulo 4 — Cotización USD en Pagos/Gastos (ver docs/DESIGN_LOG.md).
-- Guarda el último valor de cotización REALMENTE USADO en un pago o
-- gasto de la empresa (venga de BNA o cargado a mano) — es el fallback
-- para cuando BNA no responde, así el formulario nunca precarga 0
-- salvo que la empresa no tenga ni un solo pago/gasto en USD todavía.
-- Ver lib/cotizacion/queries.ts.
-- =====================================================================

alter table configuraciones_empresa
  add column if not exists ultima_cotizacion_usd numeric,
  add column if not exists ultima_cotizacion_fecha timestamptz;
