import { renderToBuffer } from "@react-pdf/renderer";
import { Document, Page, Text, View, StyleSheet } from "@react-pdf/renderer";
import { createClient } from "@/lib/supabase/server";
import { formatMoneda } from "@/lib/format";

/**
 * Generación del PDF de comprobante — extraído de
 * app/api/pagos/comprobante-pdf/route.ts a una función compartida.
 *
 * Motivo (hallazgo de esta sesión, al escribir el envío por WhatsApp):
 * un Server Action que necesita el PDF NO puede simplemente hacerle un
 * fetch() interno a la ruta HTTP — esa ruta está protegida por sesión, y
 * un fetch server-to-server no reenvía las cookies del usuario
 * automáticamente. La solución correcta es que ambos (la ruta HTTP y el
 * Server Action de WhatsApp) llamen a esta misma función directamente,
 * en vez de que uno le pegue por HTTP al otro.
 */

const styles = StyleSheet.create({
  page: { padding: 40, fontSize: 10, fontFamily: "Helvetica" },
  titulo: { fontSize: 18, fontWeight: 700, marginBottom: 2 },
  subtitulo: { fontSize: 10, color: "#666", marginBottom: 16 },
  seccion: { marginBottom: 14 },
  filaConcepto: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 2 },
  separador: { borderTopWidth: 1, borderTopColor: "#333", marginTop: 4, paddingTop: 4 },
  total: { flexDirection: "row", justifyContent: "space-between", fontSize: 13, fontWeight: 700 },
  cuadroVerde: { backgroundColor: "#f0fdf4", padding: 10, borderRadius: 4, marginTop: 10 },
  cuadroRojo: { backgroundColor: "#fef2f2", padding: 10, borderRadius: 4, marginTop: 6 },
  contexto: { backgroundColor: "#f5f5f5", padding: 10, borderRadius: 4, marginBottom: 10, fontSize: 9 },
});

interface FilaPago {
  nro_comprobante: string;
  codigo_contrato: string;
  periodo: string;
  fecha: string;
  tipo_pago: string;
  propiedad: string;
  monto_alquiler: number;
  monto_expensas: number;
  monto_edesal: number;
  monto_gas: number;
  monto_municipalidad: number;
  monto_cochera: number;
  monto_ooss: number;
  monto_imp_inmobiliario: number;
  monto_concepto_extra: number;
  monto_abonado: number;
  saldo_pendiente: number;
  metodo_pago: string | null;
  comprobante_referencia: string | null;
}

function ComprobantePdf({
  pago,
  nombreInquilino,
  comprobanteAnterior,
}: {
  pago: FilaPago;
  nombreInquilino: string;
  comprobanteAnterior: { total: number; abonado: number } | null;
}) {
  const esComplemento = pago.tipo_pago === "Complemento";

  const conceptos = (
    esComplemento
      ? []
      : ([
          ["Alquiler", pago.monto_alquiler],
          ["Expensas", pago.monto_expensas],
          ["Edesal", pago.monto_edesal],
          ["Gas", pago.monto_gas],
          ["Municipalidad", pago.monto_municipalidad],
          ["Cochera", pago.monto_cochera],
          ["OO.SS.", pago.monto_ooss],
          ["Impuesto Inmobiliario", pago.monto_imp_inmobiliario],
          ["Concepto extra", pago.monto_concepto_extra],
        ] as [string, number][])
  ).filter(([, v]) => v > 0);

  const totalConceptos = conceptos.reduce((a, [, v]) => a + v, 0);

  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <Text style={styles.titulo}>Comprobante de Pago</Text>
        <Text style={styles.subtitulo}>
          {pago.nro_comprobante} · {new Date(pago.fecha).toLocaleDateString("es-AR")}
        </Text>

        <View style={styles.seccion}>
          <Text>Inquilino: {nombreInquilino}</Text>
          <Text>Propiedad: {pago.propiedad}</Text>
          <Text>Período: {pago.periodo}</Text>
          <Text>Tipo: {pago.tipo_pago}</Text>
        </View>

        {esComplemento && comprobanteAnterior && (
          <View style={styles.contexto}>
            <Text>Total del período: {formatMoneda(comprobanteAnterior.total)}</Text>
            <Text>
              Ya abonado {pago.comprobante_referencia ? `(Comprobante ${pago.comprobante_referencia})` : ""}: −
              {formatMoneda(comprobanteAnterior.abonado)}
            </Text>
            <Text style={{ fontWeight: 700, marginTop: 2 }}>
              Este pago cubre el saldo pendiente: {formatMoneda(pago.monto_abonado)}
            </Text>
          </View>
        )}

        {!esComplemento && (
          <View style={styles.seccion}>
            {conceptos.map(([nombre, valor]) => (
              <View key={nombre} style={styles.filaConcepto}>
                <Text>{nombre}</Text>
                <Text>{formatMoneda(valor)}</Text>
              </View>
            ))}
            <View style={[styles.filaConcepto, styles.separador]}>
              <Text style={{ fontWeight: 700 }}>Total Consolidado Percibido</Text>
              <Text style={{ fontWeight: 700 }}>{formatMoneda(totalConceptos)}</Text>
            </View>
          </View>
        )}

        <View style={styles.cuadroVerde}>
          <Text style={styles.total}>
            <Text>Monto Abonado por el Inquilino</Text>
            <Text>{formatMoneda(pago.monto_abonado)}</Text>
          </Text>
        </View>

        {pago.saldo_pendiente > 0 && (
          <View style={styles.cuadroRojo}>
            <Text style={{ fontWeight: 700 }}>Saldo Pendiente: {formatMoneda(pago.saldo_pendiente)}</Text>
          </View>
        )}

        <Text style={{ marginTop: 20, fontSize: 8, color: "#888" }}>
          Método de pago: {pago.metodo_pago ?? "-"}
        </Text>
      </Page>
    </Document>
  );
}

/**
 * Genera el buffer del PDF para un comprobante — usado tanto por la
 * ruta de descarga (app/api/pagos/comprobante-pdf/route.ts) como por el
 * envío de WhatsApp (lib/whatsapp/comprobante.ts). Devuelve null si el
 * comprobante no existe.
 */
export async function generarPdfComprobante(nroComprobante: string): Promise<Buffer | null> {
  const supabase = await createClient();

  const { data: pago, error } = await supabase
    .from("pagos_historial")
    .select(
      "nro_comprobante, codigo_contrato, periodo, fecha, tipo_pago, propiedad, monto_alquiler, monto_expensas, monto_edesal, monto_gas, monto_municipalidad, monto_cochera, monto_ooss, monto_imp_inmobiliario, monto_concepto_extra, monto_abonado, saldo_pendiente, metodo_pago, comprobante_referencia"
    )
    .eq("nro_comprobante", nroComprobante)
    .single();

  if (error || !pago) return null;

  const { data: contrato } = await supabase
    .from("contratos")
    .select("dni_inquilino")
    .eq("codigo", pago.codigo_contrato)
    .single();
  const { data: inquilino } = contrato
    ? await supabase.from("inquilinos").select("nombres, apellidos").eq("dni", contrato.dni_inquilino).single()
    : { data: null };

  let comprobanteAnterior: { total: number; abonado: number } | null = null;
  if (pago.tipo_pago === "Complemento" && pago.comprobante_referencia) {
    const { data: filaAnterior } = await supabase
      .from("pagos_historial")
      .select(
        "monto_alquiler, monto_expensas, monto_edesal, monto_gas, monto_municipalidad, monto_cochera, monto_ooss, monto_imp_inmobiliario, monto_concepto_extra, monto_abonado"
      )
      .eq("nro_comprobante", pago.comprobante_referencia)
      .single();
    if (filaAnterior) {
      const total =
        filaAnterior.monto_alquiler +
        filaAnterior.monto_expensas +
        filaAnterior.monto_edesal +
        filaAnterior.monto_gas +
        filaAnterior.monto_municipalidad +
        filaAnterior.monto_cochera +
        filaAnterior.monto_ooss +
        filaAnterior.monto_imp_inmobiliario +
        filaAnterior.monto_concepto_extra;
      comprobanteAnterior = { total, abonado: filaAnterior.monto_abonado };
    }
  }

  const nombreInquilino = `${inquilino?.nombres ?? ""} ${inquilino?.apellidos ?? ""}`.trim();

  return renderToBuffer(
    <ComprobantePdf pago={pago} nombreInquilino={nombreInquilino} comprobanteAnterior={comprobanteAnterior} />
  );
}
