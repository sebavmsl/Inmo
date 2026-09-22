import { createClient } from "@/lib/supabase/server";
import { sumarCategoria, montosDesdeFilaPago, type CategoriaConcepto } from "@/lib/conceptos/categorias";

/**
 * Categorías que se muestran como informativo en Rendición (no suman al
 * Neto a Rendir). Quedan afuera "ingreso-base" (ya es alquiler+cochera,
 * parte del Total Cobrado) y "expensas" (tiene su propia lógica de
 * dos estados según 0018_rendicion_expensas_flag.sql, más rica que un
 * simple total de categoría — ver totalExpensasInformativas).
 */
const CATEGORIAS_INFORMATIVAS: CategoriaConcepto[] = ["servicio", "tasa", "impuesto", "comisión", "depósito", "otro"];

export interface ResumenRendicion {
  propietario: string;
  periodoMes: string; // "YYYY-MM", calendario
  totalCobrado: number;
  comision: number;
  netoARendir: number;
  /**
   * Informativo, no se descuenta del Neto a Rendir — ver
   * lib/conceptos/categorias.ts (Categorización transversal de
   * conceptos, esta sesión). La categoría "comisión" acá es SOLO
   * honorarios de gestión (cuotas al inquilino): la comisión real de la
   * agencia (`gasto_admin`) ya está en `comision`/`netoARendir`, incluirla
   * de nuevo acá sería contarla dos veces.
   */
  informativoPorCategoria: Partial<Record<CategoriaConcepto, number>>;
  expensasInformativas: number; // informativo (ver 0018) — expensas de propiedades con administración propia
  saldoAnterior: number;
  gastosRetencion: { id: number; descripcion: string; monto: number }[];
  montoRetencionGastos: number;
  montoALiquidar: number;
  propiedades: number;
}

export interface FilaPropiedadRendicion {
  propiedad: string;
  propietario: string;
  alquiler: number;
  cochera: number;
  expensas: number; // solo la parte que SÍ suma al neto (propiedad sin flag, ver 0018)
  expensasInformativas: number; // propiedad con expensas_administrada_por_propietario = true
  comision: number;
  totalCobrado: number; // alquiler + cochera + expensas
  netoARendir: number; // totalCobrado − comisión
}

export interface FilaDetalleRendicion {
  fecha: string;
  propiedad: string;
  inquilino: string;
  periodo: string;
  alquiler: number;
  cochera: number;
  expensas: number;
  expensasInformativas: number;
  comision: number;
  neto: number;
  impInmobiliario: number;
  edesal: number;
  gas: number;
  municipalidad: number;
  ooss: number;
  honorarios: number;
  garantia: number;
  conceptoExtra: number;
  conceptoExtraDesc: string | null;
}

export interface TotalesRendicion {
  totalAlquiler: number;
  totalCochera: number;
  totalExpensas: number;
  totalExpensasInformativas: number;
  totalCobrado: number;
  totalComision: number;
  totalNeto: number;
  /** Ver ResumenRendicion.informativoPorCategoria — mismo criterio. */
  informativoPorCategoria: Partial<Record<CategoriaConcepto, number>>;
  propiedades: number;
}

interface PagoRendicionRaw {
  fecha: string;
  codigo_contrato: string;
  propiedad: string;
  inquilino: string;
  periodo: string;
  monto_alquiler: number;
  monto_cochera: number;
  monto_expensas: number;
  monto_gasto_admin: number;
  monto_imp_inmobiliario: number;
  monto_edesal: number;
  monto_gas: number;
  monto_municipalidad: number;
  monto_ooss: number;
  monto_honorarios: number;
  monto_garantia: number;
  monto_concepto_extra: number;
  concepto_extra_desc: string | null;
}

function rangoDelPeriodo(periodoMes: string): { desde: string; hasta: string } {
  const [anioStr, mesStr] = periodoMes.split("-");
  const anio = Number(anioStr ?? new Date().getFullYear());
  const mes = Number(mesStr ?? new Date().getMonth() + 1);
  return { desde: `${periodoMes}-01`, hasta: new Date(anio, mes, 0).toISOString().slice(0, 10) };
}

/**
 * Base compartida de Rendición: pagos + info de cada propiedad
 * (propietario, y si administra sus propias expensas — ver
 * 0018_rendicion_expensas_flag.sql). `propietarioFiltro`/`periodoMes`
 * en `null` = "Todos" (soporta la vista agregada, ver DESIGN_LOG.md /
 * pendiente "Todos los propietarios").
 */
async function obtenerPagosParaRendicion(
  empresaId: number,
  propietarioFiltro: string | null,
  periodoMes: string | null
): Promise<{
  pagos: PagoRendicionRaw[];
  propiedadInfo: Map<string, { propietario: string; expensasAdministrada: boolean }>;
}> {
  const supabase = await createClient();

  let propiedadesQuery = supabase
    .from("propiedades")
    .select("alias_propiedad, propietario, expensas_administrada_por_propietario")
    .eq("empresa_id", empresaId);
  if (propietarioFiltro) propiedadesQuery = propiedadesQuery.eq("propietario", propietarioFiltro);
  const { data: propiedades } = await propiedadesQuery;

  const propiedadInfo = new Map(
    (propiedades ?? []).map((p) => [
      p.alias_propiedad,
      { propietario: p.propietario, expensasAdministrada: p.expensas_administrada_por_propietario },
    ])
  );
  const aliasPropiedades = (propiedades ?? []).map((p) => p.alias_propiedad);
  if (aliasPropiedades.length === 0) return { pagos: [], propiedadInfo };

  let pagosQuery = supabase
    .from("pagos_historial")
    .select(
      `fecha, codigo_contrato, propiedad, inquilino, periodo,
       monto_alquiler, monto_cochera, monto_expensas, monto_gasto_admin,
       monto_imp_inmobiliario, monto_edesal, monto_gas, monto_municipalidad, monto_ooss,
       monto_honorarios, monto_garantia, monto_concepto_extra, concepto_extra_desc`
    )
    .eq("empresa_id", empresaId)
    .in("propiedad", aliasPropiedades);

  if (periodoMes) {
    const { desde, hasta } = rangoDelPeriodo(periodoMes);
    pagosQuery = pagosQuery.gte("fecha", desde).lte("fecha", hasta);
  }

  const { data: pagos, error } = await pagosQuery;
  if (error) throw new Error(`[Rendición] Error cargando pagos: ${error.message}`);

  return { pagos: pagos ?? [], propiedadInfo };
}

/**
 * Tabla agrupada por propiedad (puerto de `_agrupado`, app.py líneas
 * 8359-8366) + totales. Soporta propietario = null ("Todos") y
 * periodoMes = null ("Todos"), igual que el selector de v1.
 *
 * Las expensas de una propiedad con `expensas_administrada_por_propietario
 * = true` NO suman a `totalCobrado`/`netoARendir` — quedan en
 * `expensasInformativas` (feature nueva de v2, ver 0018).
 */
export async function getRendicionAgrupada(
  empresaId: number,
  propietarioFiltro: string | null,
  periodoMes: string | null
): Promise<{ filas: FilaPropiedadRendicion[]; totales: TotalesRendicion }> {
  const { pagos, propiedadInfo } = await obtenerPagosParaRendicion(empresaId, propietarioFiltro, periodoMes);

  const porPropiedad = new Map<string, FilaPropiedadRendicion>();
  const informativoPorCategoria: Partial<Record<CategoriaConcepto, number>> = {};

  for (const p of pagos) {
    const info = propiedadInfo.get(p.propiedad);
    const expensasVanAlNeto = !(info?.expensasAdministrada ?? false);

    const fila =
      porPropiedad.get(p.propiedad) ??
      ({
        propiedad: p.propiedad,
        propietario: info?.propietario ?? "—",
        alquiler: 0,
        cochera: 0,
        expensas: 0,
        expensasInformativas: 0,
        comision: 0,
        totalCobrado: 0,
        netoARendir: 0,
      } satisfies FilaPropiedadRendicion);

    fila.alquiler += p.monto_alquiler ?? 0;
    fila.cochera += p.monto_cochera ?? 0;
    if (expensasVanAlNeto) fila.expensas += p.monto_expensas ?? 0;
    else fila.expensasInformativas += p.monto_expensas ?? 0;
    fila.comision += p.monto_gasto_admin ?? 0;

    porPropiedad.set(p.propiedad, fila);

    // `gasto_admin` en 0 acá a propósito: ya es `comision`/`totalComision`
    // arriba, no es informativo — sumarlo de nuevo sería contarlo dos
    // veces (la categoría "comisión" también incluye honorarios, que sí
    // es puramente informativo).
    const montosInformativos = { ...montosDesdeFilaPago(p), gasto_admin: 0 };
    for (const categoria of CATEGORIAS_INFORMATIVAS) {
      informativoPorCategoria[categoria] = (informativoPorCategoria[categoria] ?? 0) + sumarCategoria(montosInformativos, categoria);
    }
  }

  const filas = Array.from(porPropiedad.values())
    .map((f) => ({
      ...f,
      totalCobrado: f.alquiler + f.cochera + f.expensas,
      netoARendir: f.alquiler + f.cochera + f.expensas - f.comision,
    }))
    .sort((a, b) => a.propiedad.localeCompare(b.propiedad));

  const totales: TotalesRendicion = {
    totalAlquiler: filas.reduce((a, f) => a + f.alquiler, 0),
    totalCochera: filas.reduce((a, f) => a + f.cochera, 0),
    totalExpensas: filas.reduce((a, f) => a + f.expensas, 0),
    totalExpensasInformativas: filas.reduce((a, f) => a + f.expensasInformativas, 0),
    totalCobrado: filas.reduce((a, f) => a + f.totalCobrado, 0),
    totalComision: filas.reduce((a, f) => a + f.comision, 0),
    totalNeto: filas.reduce((a, f) => a + f.netoARendir, 0),
    informativoPorCategoria,
    propiedades: filas.length,
  };

  return { filas, totales };
}

/**
 * Detalle recibo a recibo (puerto de `_detalle_rend`, app.py líneas
 * 8419-8445) — "Detalle de Recibos Incluidos", trazabilidad de todo lo
 * cobrado al inquilino aunque no forme parte del neto del propietario.
 */
export async function getDetalleRendicion(
  empresaId: number,
  propietarioFiltro: string | null,
  periodoMes: string | null
): Promise<FilaDetalleRendicion[]> {
  const { pagos, propiedadInfo } = await obtenerPagosParaRendicion(empresaId, propietarioFiltro, periodoMes);

  return pagos
    .map((p): FilaDetalleRendicion => {
      const info = propiedadInfo.get(p.propiedad);
      const expensasVanAlNeto = !(info?.expensasAdministrada ?? false);
      const expensasNeto = expensasVanAlNeto ? p.monto_expensas ?? 0 : 0;
      const expensasInformativas = expensasVanAlNeto ? 0 : p.monto_expensas ?? 0;

      return {
        fecha: p.fecha,
        propiedad: p.propiedad,
        inquilino: p.inquilino,
        periodo: p.periodo,
        alquiler: p.monto_alquiler ?? 0,
        cochera: p.monto_cochera ?? 0,
        expensas: expensasNeto,
        expensasInformativas,
        comision: p.monto_gasto_admin ?? 0,
        neto: (p.monto_alquiler ?? 0) + (p.monto_cochera ?? 0) + expensasNeto - (p.monto_gasto_admin ?? 0),
        impInmobiliario: p.monto_imp_inmobiliario ?? 0,
        edesal: p.monto_edesal ?? 0,
        gas: p.monto_gas ?? 0,
        municipalidad: p.monto_municipalidad ?? 0,
        ooss: p.monto_ooss ?? 0,
        honorarios: p.monto_honorarios ?? 0,
        garantia: p.monto_garantia ?? 0,
        conceptoExtra: p.monto_concepto_extra ?? 0,
        conceptoExtraDesc: p.concepto_extra_desc,
      };
    })
    .sort((a, b) => a.propiedad.localeCompare(b.propiedad) || a.periodo.localeCompare(b.periodo));
}

/**
 * Resumen para UN propietario + UN período específicos — la única
 * combinación en la que tiene sentido "Registrar Liquidación" y generar
 * el PDF (igual que v1: con "Todos" en cualquiera de los dos, ver
 * app.py línea 8469, ni siquiera se muestra la sección de Liquidación).
 *
 * Reusa getRendicionAgrupada() para los totales — antes este cálculo
 * estaba duplicado acá con su propia lógica (y no conocía el flag de
 * expensas de 0018); ahora hay una sola fuente de verdad.
 */
export async function calcularResumenRendicion(
  empresaId: number,
  propietario: string,
  periodoMes: string
): Promise<ResumenRendicion> {
  const supabase = await createClient();

  const { totales } = await getRendicionAgrupada(empresaId, propietario, periodoMes);

  // Saldo anterior — última liquidación previa de este propietario (ver
  // DESIGN_LOG.md: v1 ya hace esto bien, toma solo la última, sin sumar
  // todos los períodos — el mismo patrón correcto que adoptamos para
  // contratos.saldo_actual).
  const { data: liquidacionAnterior } = await supabase
    .from("liquidaciones_propietarios")
    .select("saldo_pendiente")
    .eq("empresa_id", empresaId)
    .eq("propietario", propietario)
    .lt("periodo", periodoMes)
    .order("periodo", { ascending: false })
    .limit(1)
    .maybeSingle();
  const saldoAnterior = liquidacionAnterior?.saldo_pendiente ?? 0;

  // Gastos "Extraordinarios" pagados por alguien que no sea el
  // propietario, pendientes de retener.
  const { data: propiedadesConId } = await supabase
    .from("propiedades")
    .select("id")
    .eq("empresa_id", empresaId)
    .eq("propietario", propietario);
  const idsPropiedades = (propiedadesConId ?? []).map((p) => p.id);

  const { data: gastos } = await supabase
    .from("gastos_propiedades")
    .select("id, descripcion, monto")
    .eq("empresa_id", empresaId)
    .in("propiedad_id", idsPropiedades)
    .eq("tipo_gasto", "Extraordinario")
    .neq("pagado_por", "Propietario")
    .eq("cobrado", false);

  const gastosRetencion = gastos ?? [];
  const montoRetencionGastos = gastosRetencion.reduce((a, g) => a + g.monto, 0);
  const montoALiquidar = totales.totalNeto + saldoAnterior - montoRetencionGastos;

  return {
    propietario,
    periodoMes,
    totalCobrado: totales.totalCobrado,
    comision: totales.totalComision,
    netoARendir: totales.totalNeto,
    informativoPorCategoria: totales.informativoPorCategoria,
    expensasInformativas: totales.totalExpensasInformativas,
    saldoAnterior,
    gastosRetencion,
    montoRetencionGastos,
    montoALiquidar,
    propiedades: totales.propiedades,
  };
}

export interface LiquidacionExistente {
  montoCalculado: number;
  saldoAnterior: number;
  montoRetencionGastos: number;
  montoALiquidar: number;
  montoLiquidado: number;
  saldoPendiente: number;
  fechaLiquidacion: string;
  registradoPor: string;
}

/**
 * Para el gate del botón "Descargar PDF de Rendición" — v1 lo habilita
 * solo tras registrar la liquidación EN ESA MISMA SESIÓN de navegador
 * (session_state), lo que se resetea si recargás la página. Acá se lee
 * directo de la base: el gate es "¿ya existe una liquidación guardada
 * para este propietario+período?", más robusto y sobrevive un refresh.
 */
export async function obtenerLiquidacionExistente(
  empresaId: number,
  propietario: string,
  periodoMes: string
): Promise<LiquidacionExistente | null> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("liquidaciones_propietarios")
    .select("monto_calculado, saldo_anterior, monto_retencion_gastos, monto_a_liquidar, monto_liquidado, saldo_pendiente, fecha_liquidacion, registrado_por")
    .eq("empresa_id", empresaId)
    .eq("propietario", propietario)
    .eq("periodo", periodoMes)
    .maybeSingle();

  if (!data) return null;
  return {
    montoCalculado: data.monto_calculado,
    saldoAnterior: data.saldo_anterior,
    montoRetencionGastos: data.monto_retencion_gastos,
    montoALiquidar: data.monto_a_liquidar,
    montoLiquidado: data.monto_liquidado,
    saldoPendiente: data.saldo_pendiente,
    fechaLiquidacion: data.fecha_liquidacion,
    registradoPor: data.registrado_por,
  };
}

export async function getPropietarios(empresaId: number): Promise<string[]> {
  const supabase = await createClient();
  const { data } = await supabase.from("propiedades").select("propietario").eq("empresa_id", empresaId);
  return Array.from(new Set((data ?? []).map((p) => p.propietario))).sort();
}
