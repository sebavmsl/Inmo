import { renderToBuffer } from "@react-pdf/renderer";
import { Document, Page, Text, View, StyleSheet } from "@react-pdf/renderer";
import { formatMoneda } from "@/lib/format";
import { createClient } from "@/lib/supabase/server";
import {
  getRendicionAgrupada,
  getDetalleRendicion,
  obtenerLiquidacionExistente,
  type FilaPropiedadRendicion,
  type FilaDetalleRendicion,
  type TotalesRendicion,
} from "@/lib/rendicion/queries";
import { CATEGORIAS_CONCEPTO, LABEL_CATEGORIA } from "@/lib/conceptos/categorias";

const CATEGORIAS_INFORMATIVAS_UI = CATEGORIAS_CONCEPTO.filter((c) => c !== "ingreso-base" && c !== "expensas");

/**
 * PDF de Rendición — puerto de `generar_pdf_rendicion()` (app.py líneas
 * 525-803): resumen, tabla por propiedad, informativo, liquidación y
 * "Detalle de Recibos Incluidos". Mismo motor (@react-pdf/renderer) que
 * ya usa el comprobante de pago (lib/pagos/pdf.tsx).
 */

const styles = StyleSheet.create({
  page: { padding: 32, fontSize: 9, fontFamily: "Helvetica" },
  titulo: { fontSize: 16, fontWeight: 700, marginBottom: 2, color: "#1a365d" },
  subtitulo: { fontSize: 9, color: "#666", marginBottom: 14 },
  seccionTitulo: { fontSize: 11, fontWeight: 700, color: "#1a365d", marginTop: 12, marginBottom: 6 },
  kpiFila: { flexDirection: "row", marginBottom: 10 },
  kpi: { flex: 1, backgroundColor: "#f0f4f8", borderRadius: 3, padding: 6, marginRight: 6 },
  kpiLabel: { fontSize: 7, color: "#666" },
  kpiValor: { fontSize: 11, fontWeight: 700, marginTop: 2 },
  informativo: { fontSize: 8, color: "#666", marginBottom: 8 },
  tablaHeader: { flexDirection: "row", backgroundColor: "#1a365d", paddingVertical: 3, paddingHorizontal: 2 },
  tablaHeaderTexto: { color: "#fff", fontSize: 7, fontWeight: 700 },
  tablaFila: { flexDirection: "row", borderBottomWidth: 0.5, borderBottomColor: "#ddd", paddingVertical: 3, paddingHorizontal: 2 },
  tablaFilaAlt: { backgroundColor: "#f7f9fb" },
  tablaTotales: { flexDirection: "row", backgroundColor: "#dce6f4", paddingVertical: 3, paddingHorizontal: 2 },
  celda: { fontSize: 7 },
  celdaBold: { fontSize: 7, fontWeight: 700 },
  cuadroLiquidacion: { backgroundColor: "#f0fdf4", borderRadius: 4, padding: 8, marginTop: 4 },
  filaLiquidacion: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 1.5 },
  footer: { marginTop: 16, fontSize: 7, color: "#888" },
});

function TablaPropiedades({ filas, totales }: { filas: FilaPropiedadRendicion[]; totales: { alquiler: number; cochera: number; expensas: number; cobrado: number; comision: number; neto: number } }) {
  const cols: [string, number][] = [
    ["Propiedad", 3],
    ["Alquiler", 1.4],
    ["Cochera", 1.2],
    ["Expensas", 1.4],
    ["Total Cobrado", 1.6],
    ["Comisión (−)", 1.4],
    ["Neto a Rendir", 1.6],
  ];
  return (
    <View>
      <View style={styles.tablaHeader}>
        {cols.map(([label, flex]) => (
          <Text key={label} style={[styles.tablaHeaderTexto, { flex }]}>
            {label}
          </Text>
        ))}
      </View>
      {filas.map((f, i) => (
        <View key={f.propiedad} style={[styles.tablaFila, i % 2 === 1 ? styles.tablaFilaAlt : {}]}>
          <Text style={[styles.celda, { flex: 3 }]}>{f.propiedad}</Text>
          <Text style={[styles.celda, { flex: 1.4 }]}>{formatMoneda(f.alquiler)}</Text>
          <Text style={[styles.celda, { flex: 1.2 }]}>{formatMoneda(f.cochera)}</Text>
          <Text style={[styles.celda, { flex: 1.4 }]}>{formatMoneda(f.expensas)}</Text>
          <Text style={[styles.celda, { flex: 1.6 }]}>{formatMoneda(f.totalCobrado)}</Text>
          <Text style={[styles.celda, { flex: 1.4 }]}>{formatMoneda(f.comision)}</Text>
          <Text style={[styles.celdaBold, { flex: 1.6 }]}>{formatMoneda(f.netoARendir)}</Text>
        </View>
      ))}
      <View style={styles.tablaTotales}>
        <Text style={[styles.celdaBold, { flex: 3 }]}>TOTALES</Text>
        <Text style={[styles.celdaBold, { flex: 1.4 }]}>{formatMoneda(totales.alquiler)}</Text>
        <Text style={[styles.celdaBold, { flex: 1.2 }]}>{formatMoneda(totales.cochera)}</Text>
        <Text style={[styles.celdaBold, { flex: 1.4 }]}>{formatMoneda(totales.expensas)}</Text>
        <Text style={[styles.celdaBold, { flex: 1.6 }]}>{formatMoneda(totales.cobrado)}</Text>
        <Text style={[styles.celdaBold, { flex: 1.4 }]}>{formatMoneda(totales.comision)}</Text>
        <Text style={[styles.celdaBold, { flex: 1.6 }]}>{formatMoneda(totales.neto)}</Text>
      </View>
    </View>
  );
}

function TablaDetalle({ filas }: { filas: FilaDetalleRendicion[] }) {
  const cols: [string, number][] = [
    ["Fecha", 1.1],
    ["Propiedad", 1.8],
    ["Inquilino", 1.8],
    ["Período", 1.3],
    ["Alquiler", 1],
    ["Cochera", 0.9],
    ["Expensas", 1],
    ["Comisión", 1],
    ["Neto", 1],
    ["Imp.Inmob.", 1],
    ["Luz", 0.8],
    ["Gas", 0.8],
    ["Municip.", 0.9],
    ["OO.SS.", 0.8],
    ["Honor.", 0.9],
    ["Garant.", 0.9],
  ];
  return (
    <View>
      <View style={styles.tablaHeader}>
        {cols.map(([label, flex]) => (
          <Text key={label} style={[styles.tablaHeaderTexto, { flex, fontSize: 6 }]}>
            {label}
          </Text>
        ))}
      </View>
      {filas.map((f, i) => (
        <View key={`${f.propiedad}-${f.periodo}-${i}`} style={[styles.tablaFila, i % 2 === 1 ? styles.tablaFilaAlt : {}]} wrap={false}>
          <Text style={[styles.celda, { flex: 1.1, fontSize: 6 }]}>{new Date(f.fecha).toLocaleDateString("es-AR")}</Text>
          <Text style={[styles.celda, { flex: 1.8, fontSize: 6 }]}>{f.propiedad}</Text>
          <Text style={[styles.celda, { flex: 1.8, fontSize: 6 }]}>{f.inquilino}</Text>
          <Text style={[styles.celda, { flex: 1.3, fontSize: 6 }]}>{f.periodo}</Text>
          <Text style={[styles.celda, { flex: 1, fontSize: 6 }]}>{formatMoneda(f.alquiler)}</Text>
          <Text style={[styles.celda, { flex: 0.9, fontSize: 6 }]}>{formatMoneda(f.cochera)}</Text>
          <Text style={[styles.celda, { flex: 1, fontSize: 6 }]}>{formatMoneda(f.expensas)}</Text>
          <Text style={[styles.celda, { flex: 1, fontSize: 6 }]}>{formatMoneda(f.comision)}</Text>
          <Text style={[styles.celdaBold, { flex: 1, fontSize: 6 }]}>{formatMoneda(f.neto)}</Text>
          <Text style={[styles.celda, { flex: 1, fontSize: 6 }]}>{formatMoneda(f.impInmobiliario)}</Text>
          <Text style={[styles.celda, { flex: 0.8, fontSize: 6 }]}>{formatMoneda(f.edesal)}</Text>
          <Text style={[styles.celda, { flex: 0.8, fontSize: 6 }]}>{formatMoneda(f.gas)}</Text>
          <Text style={[styles.celda, { flex: 0.9, fontSize: 6 }]}>{formatMoneda(f.municipalidad)}</Text>
          <Text style={[styles.celda, { flex: 0.8, fontSize: 6 }]}>{formatMoneda(f.ooss)}</Text>
          <Text style={[styles.celda, { flex: 0.9, fontSize: 6 }]}>{formatMoneda(f.honorarios)}</Text>
          <Text style={[styles.celda, { flex: 0.9, fontSize: 6 }]}>{formatMoneda(f.garantia)}</Text>
        </View>
      ))}
    </View>
  );
}

function RendicionPdf({
  propietario,
  periodoMes,
  nombreEmpresa,
  fechaEmision,
  filas,
  totales,
  detalle,
  saldoAnterior,
  gastosRetencion,
  montoRetencionGastos,
  montoALiquidar,
  montoLiquidado,
  saldoPendiente,
}: {
  propietario: string;
  periodoMes: string;
  nombreEmpresa: string;
  fechaEmision: string;
  filas: FilaPropiedadRendicion[];
  totales: TotalesRendicion;
  detalle: FilaDetalleRendicion[];
  saldoAnterior: number;
  gastosRetencion: { id: number; descripcion: string; monto: number }[];
  montoRetencionGastos: number;
  montoALiquidar: number;
  montoLiquidado: number;
  saldoPendiente: number;
}) {
  return (
    <Document>
      {/* Horizontal (a diferencia de v1, que usa A4 vertical): la tabla de
          "Detalle de Recibos Incluidos" tiene 16 columnas y no entra
          legible en un A4 vertical — decisión de esta sesión. */}
      <Page size="A4" orientation="landscape" style={styles.page}>
        <Text style={styles.titulo}>Rendición a Propietario</Text>
        <Text style={styles.subtitulo}>
          {propietario} · Período {periodoMes} · {nombreEmpresa} · Emitido el {fechaEmision}
        </Text>

        <View style={styles.kpiFila}>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>TOTAL COBRADO</Text>
            <Text style={styles.kpiValor}>{formatMoneda(totales.totalCobrado)}</Text>
          </View>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>COMISIÓN ADM. (−)</Text>
            <Text style={styles.kpiValor}>{formatMoneda(totales.totalComision)}</Text>
          </View>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>NETO A RENDIR</Text>
            <Text style={styles.kpiValor}>{formatMoneda(totales.totalNeto)}</Text>
          </View>
          <View style={[styles.kpi, { marginRight: 0 }]}>
            <Text style={styles.kpiLabel}>PROPIEDADES</Text>
            <Text style={styles.kpiValor}>{filas.length}</Text>
          </View>
        </View>

        <Text style={styles.informativo}>
          Informativo — no forma parte del Neto a Rendir:{" "}
          {CATEGORIAS_INFORMATIVAS_UI.filter((cat) => (totales.informativoPorCategoria[cat] ?? 0) > 0)
            .map((cat) => `${LABEL_CATEGORIA[cat]} ${formatMoneda(totales.informativoPorCategoria[cat] ?? 0)}`)
            .join(" · ") || "sin conceptos informativos en este período"}
          {totales.totalExpensasInformativas > 0 && ` · Expensas administradas por el propietario ${formatMoneda(totales.totalExpensasInformativas)}`}
        </Text>

        <Text style={styles.seccionTitulo}>Detalle por Propiedad</Text>
        <TablaPropiedades
          filas={filas}
          totales={{
            alquiler: totales.totalAlquiler,
            cochera: totales.totalCochera,
            expensas: totales.totalExpensas,
            cobrado: totales.totalCobrado,
            comision: totales.totalComision,
            neto: totales.totalNeto,
          }}
        />

        <Text style={styles.seccionTitulo}>Liquidación</Text>
        <View style={styles.cuadroLiquidacion}>
          <View style={styles.filaLiquidacion}>
            <Text>Saldo pendiente anterior</Text>
            <Text>{formatMoneda(saldoAnterior)}</Text>
          </View>
          <View style={styles.filaLiquidacion}>
            <Text>Retención por gastos extraordinarios (−)</Text>
            <Text>{formatMoneda(montoRetencionGastos)}</Text>
          </View>
          <View style={styles.filaLiquidacion}>
            <Text style={{ fontWeight: 700 }}>Monto total a liquidar</Text>
            <Text style={{ fontWeight: 700 }}>{formatMoneda(montoALiquidar)}</Text>
          </View>
          <View style={styles.filaLiquidacion}>
            <Text>Monto efectivamente liquidado</Text>
            <Text>{formatMoneda(montoLiquidado)}</Text>
          </View>
          <View style={styles.filaLiquidacion}>
            <Text style={{ fontWeight: 700 }}>Saldo pendiente nuevo</Text>
            <Text style={{ fontWeight: 700 }}>{formatMoneda(saldoPendiente)}</Text>
          </View>
        </View>

        {gastosRetencion.length > 0 && (
          <>
            <Text style={styles.seccionTitulo}>Gastos Retenidos</Text>
            {gastosRetencion.map((g) => (
              <View key={g.id} style={styles.filaLiquidacion}>
                <Text>{g.descripcion}</Text>
                <Text>{formatMoneda(g.monto)}</Text>
              </View>
            ))}
          </>
        )}

        <Text style={styles.seccionTitulo}>Detalle de Recibos Incluidos</Text>
        <Text style={{ fontSize: 7, color: "#666", marginBottom: 4 }}>
          Cada fila es un recibo emitido. Incluye, a modo informativo, los demás conceptos cobrados al inquilino que no forman parte del neto del propietario.
        </Text>
        <TablaDetalle filas={detalle} />

        <Text style={styles.footer}>Generado el {fechaEmision} — {nombreEmpresa} — Documento de rendición de cuentas emitido de manera electrónica.</Text>
      </Page>
    </Document>
  );
}

/**
 * Genera el PDF de rendición para un propietario + período específicos.
 * Devuelve null si no hay ninguna liquidación registrada todavía para
 * esa combinación (mismo gate que v1: hay que "Registrar Liquidación"
 * antes de poder descargar el PDF — ver obtenerLiquidacionExistente).
 */
export async function generarPdfRendicion(
  empresaId: number,
  propietario: string,
  periodoMes: string,
  nombreEmpresa: string
): Promise<Buffer | null> {
  const liquidacion = await obtenerLiquidacionExistente(empresaId, propietario, periodoMes);
  if (!liquidacion) return null;

  const supabase = await createClient();

  const [{ filas, totales }, detalle, { data: propiedadesConId }] = await Promise.all([
    getRendicionAgrupada(empresaId, propietario, periodoMes),
    getDetalleRendicion(empresaId, propietario, periodoMes),
    supabase.from("propiedades").select("id").eq("empresa_id", empresaId).eq("propietario", propietario),
  ]);

  // Los gastos que esta liquidación retuvo ya quedaron marcados `cobrado
  // = true` por registrar_liquidacion_propietario() — se identifican acá
  // por `periodo_cobrado` para poder listarlos en el PDF después de
  // registrada la liquidación (calcularResumenRendicion ya no los ve,
  // porque esa consulta filtra `cobrado = false`).
  const idsPropiedades = (propiedadesConId ?? []).map((p) => p.id);
  const { data: gastosRetenidos } =
    idsPropiedades.length > 0
      ? await supabase
          .from("gastos_propiedades")
          .select("id, descripcion, monto")
          .eq("empresa_id", empresaId)
          .in("propiedad_id", idsPropiedades)
          .eq("cobrado", true)
          .eq("periodo_cobrado", periodoMes)
      : { data: [] };

  return renderToBuffer(
    <RendicionPdf
      propietario={propietario}
      periodoMes={periodoMes}
      nombreEmpresa={nombreEmpresa}
      fechaEmision={new Date().toLocaleDateString("es-AR")}
      filas={filas}
      totales={totales}
      detalle={detalle}
      saldoAnterior={liquidacion.saldoAnterior}
      gastosRetencion={gastosRetenidos ?? []}
      montoRetencionGastos={liquidacion.montoRetencionGastos}
      montoALiquidar={liquidacion.montoALiquidar}
      montoLiquidado={liquidacion.montoLiquidado}
      saldoPendiente={liquidacion.saldoPendiente}
    />
  );
}
