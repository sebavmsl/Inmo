import { NextResponse } from "next/server";
import { renderToBuffer } from "@react-pdf/renderer";
import { Document, Page, Text, View, StyleSheet } from "@react-pdf/renderer";
import { requireSessionProfile } from "@/lib/auth/session";
import { getCobranzasDelMes } from "@/lib/planilla/queries";
import { formatMoneda } from "@/lib/format";
import type { FilaPlanilla } from "@/lib/planilla/types";

/**
 * Exportación en PDF de la Planilla — mismo contenido y código de
 * colores que la tabla en pantalla (ver components/planilla/TablaCobranzas.tsx).
 */

const COLOR_URGENCIA: Record<FilaPlanilla["urgencia"], string> = {
  actualizar_este_mes: "#fffbeb", // amber-50
  actualizar_mes_proximo: "#eff6ff", // blue-50
  renovar: "#fef2f2", // red-50
  normal: "#ffffff",
};

const styles = StyleSheet.create({
  page: { padding: 30, fontSize: 9, fontFamily: "Helvetica" },
  titulo: { fontSize: 16, marginBottom: 4, fontWeight: 700 },
  subtitulo: { fontSize: 10, color: "#666", marginBottom: 12 },
  resumen: { flexDirection: "row", gap: 16, marginBottom: 10, fontSize: 10 },
  fila: { flexDirection: "row", borderBottomWidth: 0.5, borderBottomColor: "#e5e5e5", paddingVertical: 4 },
  filaHeader: { flexDirection: "row", borderBottomWidth: 1, borderBottomColor: "#333", paddingVertical: 4, fontWeight: 700 },
  celda: { flex: 1, paddingHorizontal: 3 },
  celdaChica: { width: 24, paddingHorizontal: 3 },
  leyenda: { flexDirection: "row", gap: 12, marginTop: 12, fontSize: 8, color: "#888" },
});

function PlanillaPdf({ filas, empresa }: { filas: FilaPlanilla[]; empresa: string }) {
  const activos = filas.filter((f) => !f.estadoVencido);
  const pagaron = activos.filter((f) => f.pagado).length;
  const faltan = activos.length - pagaron;
  const hoy = new Date().toLocaleDateString("es-AR");

  return (
    <Document>
      <Page size="A4" orientation="landscape" style={styles.page}>
        <Text style={styles.titulo}>Planilla de Cobranzas</Text>
        <Text style={styles.subtitulo}>
          {empresa} · {hoy}
        </Text>
        <View style={styles.resumen}>
          <Text>✓ {pagaron} pagaron</Text>
          <Text>⏳ {faltan} faltan</Text>
          <Text>{activos.length} total</Text>
        </View>

        <View style={styles.filaHeader}>
          <Text style={styles.celdaChica}></Text>
          <Text style={styles.celda}>Propiedad</Text>
          <Text style={styles.celda}>Inquilino</Text>
          <Text style={styles.celda}>Alquiler</Text>
          <Text style={styles.celda}>Saldo</Text>
          <Text style={styles.celda}>Vencimiento</Text>
          <Text style={styles.celda}>Próx. Actualización</Text>
        </View>

        {filas.map((f) => (
          <View key={f.codigo} style={[styles.fila, { backgroundColor: COLOR_URGENCIA[f.urgencia] }]}>
            <Text style={styles.celdaChica}>{f.pagado ? "✓" : "○"}</Text>
            <Text style={styles.celda}>
              {f.aliasPropiedad}
              {f.estadoVencido ? " [VENCIDO]" : ""}
            </Text>
            <Text style={styles.celda}>{f.inquilino}</Text>
            <Text style={styles.celda}>{formatMoneda(f.alquilerMostrar)}</Text>
            <Text style={styles.celda}>{f.saldoActual > 0 ? formatMoneda(f.saldoActual) : "-"}</Text>
            <Text style={styles.celda}>{f.finContrato ?? "-"}</Text>
            <Text style={styles.celda}>{f.proxActualizacion ?? "-"}</Text>
          </View>
        ))}

        <View style={styles.leyenda}>
          <Text>■ Amarillo: actualizar este mes</Text>
          <Text>■ Celeste: actualizar mes próximo</Text>
          <Text>■ Rojo: renovar contrato</Text>
        </View>
      </Page>
    </Document>
  );
}

export async function GET() {
  const perfil = await requireSessionProfile();

  const propietarioFiltro =
    perfil.rol === "propietario" && perfil.propietarioFiltro ? perfil.propietarioFiltro : undefined;

  const filas = await getCobranzasDelMes(propietarioFiltro);
  const buffer = await renderToBuffer(<PlanillaPdf filas={filas} empresa={perfil.nombreEmpresa} />);

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="planilla-${new Date().toISOString().slice(0, 10)}.pdf"`,
    },
  });
}
