import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { generarPdfComprobante } from "@/lib/pagos/pdf";

/**
 * Esta ruta la usan DOS audiencias distintas: el staff (desde Pagos,
 * tiene fila en usuarios_central) y el inquilino (desde su Portal,
 * tiene fila en inquilinos, NO en usuarios_central). Por eso acá no se
 * puede usar requireSessionProfile()/requirePermisoAction() — esas
 * funciones exigen una fila en usuarios_central, y un inquilino nunca
 * la tiene, así que su propio link de "Descargar comprobante" en
 * /portal/mi-cuenta rompía siempre (bug encontrado al blindar esta
 * ruta, ver docs/DESIGN_LOG.md).
 *
 * El chequeo real de "puede ver ESTE comprobante puntual" ya lo hace
 * RLS sobre `pagos_historial` (generarPdfComprobante usa el cliente con
 * sesión, no service_role): staff ve solo los de su empresa, inquilino
 * ve solo los de su propio contrato. Acá alcanza con exigir que haya
 * ALGUNA sesión de Supabase válida (staff o inquilino) antes de generar
 * el PDF — RLS hace el resto.
 */
export async function GET(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "No autenticado." }, { status: 401 });
  }

  const nroComprobante = request.nextUrl.searchParams.get("comprobante");
  if (!nroComprobante) {
    return NextResponse.json({ error: "Falta el parámetro 'comprobante'." }, { status: 400 });
  }

  const buffer = await generarPdfComprobante(nroComprobante);
  if (!buffer) {
    return NextResponse.json({ error: "Comprobante no encontrado." }, { status: 404 });
  }

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${nroComprobante}.pdf"`,
    },
  });
}
