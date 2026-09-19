import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { obtenerIclBcraXls, obtenerIpcIndec, obtenerUvaBcraXls } from "@/lib/indices/fuentes";
import { calcularValorActualizado } from "@/lib/indices/calculo";
import { procesarRecordatoriosAutomaticos } from "@/lib/whatsapp/recordatorios";

/**
 * Cron diario consolidado — Módulo 3 + Módulo 8.
 * Orden fijo (ver docs/DESIGN_LOG.md): vencer → refrescar índices →
 * aplicar índices → recordatorios. Si un paso falla, los demás igual
 * corren — no se bloquean entre sí.
 *
 * Protegido por CRON_SECRET (header, comparado también dentro de cada
 * función SECURITY DEFINER — doble candado: Vercel Cron solo puede
 * llamar este endpoint con el secreto correcto en el header, y aunque
 * alguien más lo llamara, las funciones de Postgres igual lo exigen).
 *
 * Usa la ANON KEY, no service_role — el "cruce" entre empresas lo
 * resuelven las funciones SECURITY DEFINER de las migraciones 0004/0010,
 * no un privilegio amplio de este cliente.
 */
export async function GET(request: NextRequest) {
  const authHeader = request.headers.get("authorization");
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const secretCron = process.env.CRON_SECRET!;
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const resultado: Record<string, unknown> = {};

  // ── Paso 1: vencer contratos ──────────────────────────────────────
  try {
    const { data, error } = await supabase.rpc("vencer_contratos_automaticamente", {
      p_secret_cron: secretCron,
    });
    resultado.vencimiento = error ? { error: error.message } : { contratos_vencidos: data };
  } catch (e) {
    resultado.vencimiento = { error: e instanceof Error ? e.message : "Error desconocido" };
  }

  // ── Paso 2: refrescar índices (ICL/IPC/UVA) ───────────────────────
  try {
    const hoy = new Date();
    const [icl, ipc, uva] = await Promise.all([
      obtenerIclBcraXls(hoy.getFullYear()),
      obtenerIpcIndec(),
      obtenerUvaBcraXls(),
    ]);

    let puntosGuardados = 0;
    for (const [tipo, serie] of [
      ["ICL", icl],
      ["IPC", ipc],
      ["UVA", uva],
    ] as const) {
      // Se guarda la serie completa que trajo la fuente externa — el
      // upsert es idempotente, y conservar la historia completa (no solo
      // los últimos días) sirve como registro de referencia para el
      // futuro (paneles, auditoría), aunque el cálculo en sí ya no
      // depende de esta tabla (ver corrección de esta sesión en
      // docs/DESIGN_LOG.md).
      for (const fecha of Object.keys(serie)) {
        const { error } = await supabase.rpc("upsert_indice", {
          p_tipo: tipo,
          p_fecha: fecha,
          p_valor: serie[fecha],
        });
        if (!error) puntosGuardados += 1;
      }
    }
    resultado.indices = { puntos_guardados: puntosGuardados };
  } catch (e) {
    resultado.indices = { error: e instanceof Error ? e.message : "Error desconocido" };
  }

  // ── Paso 3: aplicar índices (modo global, solo empresas opt-in) ───
  try {
    const { data: elegibles, error: errElegibles } = await supabase.rpc(
      "contratos_elegibles_actualizacion",
      { p_empresa_id: null, p_solo_pendientes: true }
    );
    if (errElegibles) throw new Error(errElegibles.message);

    let aplicados = 0;
    let sinResultado = 0;
    for (const c of elegibles ?? []) {
      const valor = await calcularValorActualizado(
        c.indice as "ICL" | "IPC" | "UVA",
        c.monto_inicial,
        new Date(c.fecha_inicio),
        c.frecuencia_meses
      );
      if (valor === null) {
        sinResultado += 1;
        continue;
      }
      const { data: ok } = await supabase.rpc("aplicar_actualizacion_individual", {
        p_codigo_contrato: c.codigo,
        p_valor_calculado: valor,
        p_empresa_id: c.empresa_id,
        p_secret_cron: secretCron,
      });
      if (ok) aplicados += 1;
    }
    resultado.aplicacion_indices = { aplicados, sin_resultado: sinResultado, total: elegibles?.length ?? 0 };
  } catch (e) {
    resultado.aplicacion_indices = { error: e instanceof Error ? e.message : "Error desconocido" };
  }

  // ── Paso 4: recordatorios automáticos (Módulo 8) ──────────────────
  try {
    resultado.recordatorios = await procesarRecordatoriosAutomaticos(secretCron);
  } catch (e) {
    resultado.recordatorios = { error: e instanceof Error ? e.message : "Error desconocido" };
  }

  return NextResponse.json(resultado);
}

/** Configuración de Vercel Cron (vercel.json debe apuntar acá, 1x/día). */
export const maxDuration = 60; // segundos — a ajustar según cuánto tarde en la práctica (ver DESIGN_LOG.md)
