import { NextRequest, NextResponse } from "next/server";
import { requirePermisoAction } from "@/lib/auth/session";
import { generarPdfRendicion } from "@/lib/rendicion/pdf";

/**
 * Descarga del PDF de Rendición — habilitado solo cuando ya se registró
 * una liquidación para ese propietario+período exactos (generarPdfRendicion
 * devuelve null si no, ver lib/rendicion/pdf.tsx). El rol `propietario`
 * también tiene acceso de solo lectura a esta pestaña (igual que v1),
 * pero solo puede pedir el PDF de su propio `propietarioFiltro` — el
 * chequeo de abajo lo hace explícito además del RLS subyacente.
 */
export async function GET(request: NextRequest) {
  let perfil;
  try {
    perfil = await requirePermisoAction("rendicion");
  } catch {
    return NextResponse.json({ error: "No autenticado o sin permiso." }, { status: 403 });
  }
  if (!perfil.empresaId) {
    return NextResponse.json({ error: "Usuario sin empresa asociada." }, { status: 400 });
  }

  const propietario = request.nextUrl.searchParams.get("propietario");
  const periodo = request.nextUrl.searchParams.get("periodo");
  if (!propietario || !periodo) {
    return NextResponse.json({ error: "Faltan los parámetros 'propietario' y 'periodo'." }, { status: 400 });
  }
  if (perfil.rol === "propietario" && perfil.propietarioFiltro && propietario !== perfil.propietarioFiltro) {
    return NextResponse.json({ error: "No tenés acceso a la rendición de otro propietario." }, { status: 403 });
  }

  const buffer = await generarPdfRendicion(perfil.empresaId, propietario, periodo, perfil.nombreEmpresa);
  if (!buffer) {
    return NextResponse.json({ error: "Todavía no hay una liquidación registrada para ese propietario y período." }, { status: 404 });
  }

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="rendicion_${propietario.replace(/\s+/g, "_")}_${periodo}.pdf"`,
    },
  });
}
