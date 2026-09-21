import { NextRequest, NextResponse } from "next/server";
import { requireSessionProfile } from "@/lib/auth/session";
import { generarPdfComprobante } from "@/lib/pagos/pdf";

export async function GET(request: NextRequest) {
  await requireSessionProfile();

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
