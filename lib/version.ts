/**
 * Versión del sistema v2. A partir de V2.001 se numera cada entrega de
 * archivos de la sesión de depuración (un incremento por cada tanda de
 * archivos entregada), reemplazando el esquema de numeración anterior
 * (V.201/V.202). Se muestra como sello fijo en el Sidebar y en el pie
 * del login.
 *
 * V2.001 — primera entrega de la depuración: bug de seguridad de
 * permisos no validados del lado del servidor (páginas + Server
 * Actions de planilla, pagos, carga, auxiliares, gastos, rendición;
 * rutas de PDF; envío de comprobante por WhatsApp), más el fix del link
 * roto de "Descargar comprobante" en el Portal del Inquilino.
 *
 * V2.002 — segunda entrega:
 *   - Módulo 5 (WhatsApp masivo, Planilla): 3 bugs corregidos (filtro de
 *     saldo, cochera faltante en el total, variables incompletas del
 *     template de WhatsApp).
 *   - Historial de Pagos: tabla ampliada a paridad con v1 + Reporte de
 *     Cobros (filtro por fecha/usuario, export CSV).
 *   - Rendición a Propietarios: reescrita — PDF horizontal, detalle de
 *     recibos, flag nueva "expensas administradas por el propietario".
 *   - Categorización transversal de conceptos (lib/conceptos/categorias.ts)
 *     — corrige un doble conteo en el total "Servicios" que arrastraban
 *     Historial de Pagos y Rendición.
 *   - Portal Inquilino: bandejas de staff para Comprobantes (aprobar/
 *     rechazar) y Reclamos (estado, respuesta, vínculo con Gastos) +
 *     fix de UX en el lado del inquilino (selector de contrato en vez
 *     de texto libre).
 *   - Panel de Gestión: migración masiva por CSV (importar/exportar
 *     Propiedades, Inquilinos, Contratos, Gastos; exportar además Pagos
 *     y Permisos), y selector de empresa agregado a Borrado en Bloque.
 *
 * V2.003 — tercera entrega:
 *   - Planilla de Contratos: para superadmin (que no tiene empresa_id
 *     propio) ya no se mezclan los contratos de todas las inmobiliarias
 *     en una sola tabla — por defecto se muestran los contratos sin
 *     empresa asignada ("huérfanos"), con un desplegable para elegir una
 *     empresa puntual. El PDF ("Descargar PDF") respeta el mismo filtro.
 */
export const APP_VERSION = "V2.003";
