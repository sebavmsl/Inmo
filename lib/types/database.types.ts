/**
 * Tipos de la base de datos existente (Supabase/PostgreSQL).
 *
 * Este archivo es un punto de partida escrito a mano a partir de las
 * queries de app.py (v1.149) y de las migraciones agregadas en v2.
 * Antes de seguir sumando módulos conviene reemplazarlo por el archivo
 * generado automáticamente con:
 *
 *   npx supabase gen types typescript --project-id <ref> --schema public > lib/types/database.types.ts
 *
 * así queda 100% sincronizado con el esquema real.
 *
 * NOTA DE DISEÑO (corregido en esta sesión, ver conversación con el
 * usuario sobre el error de build "empresa_id does not exist in type
 * never[]"): cada tabla define su Row como un tipo NOMBRADO aparte
 * (ej. `PropiedadesRow`), y el objeto `Database` solo lo referencia.
 * La versión anterior escribía `Insert: Partial<Database["public"]["Tables"][...]["Row"]>`
 * — una referencia circular hacia el propio `Database` que se estaba
 * definiendo — y eso rompía la inferencia de tipos de Supabase-js en
 * `.insert()`, colapsando el tipo a `never[]`. Esta estructura evita
 * esa auto-referencia por completo.
 */

export type Rol = "superadmin" | "admin" | "propietario" | "user";

export type FrecuenciaActualizacion =
  | "mensual"
  | "bimestral"
  | "trimestral"
  | "cuatrimestral"
  | "semestral"
  | "anual"
  | "sin_actualizacion";

export type IndiceActualizacion = "ICL" | "IPC" | "UVA" | "Otro";

export type TipoPago = "Normal" | "Complemento" | "Corrección";

export type TipoRecordatorioWhatsapp = "vencimiento" | "actualizacion";

// =====================================================================
// Row types — uno por tabla, nombrados, sin referencias circulares.
// =====================================================================

export interface EmpresasRow {
  id: number;
  nombre_comercial: string;
  archivo_db: string;
  created_at: string;
}

export interface UsuariosCentralRow {
  id: number;
  username: string;
  email: string | null;
  auth_user_id: string | null; // uuid -> auth.users.id (agregado en v2)
  nombre_empresa: string;
  archivo_db: string;
  empresa_id: number | null;
  rol: Rol;
  propietario_filtro: string | null;
  terminos_aceptados: boolean;
  terminos_fecha: string | null;
}

export interface PermisosUsuarioRow {
  id: number;
  username: string;
  /**
   * "whatsapp" es una pestaña más acá (igual que "dashboard",
   * "planilla", etc.), no una columna booleana aparte — así lo
   * resolvió v1.184 y así lo replicamos en v2. Ver lib/auth/permissions.ts.
   */
  pestana: string;
}

export interface ConfiguracionesEmpresaRow {
  empresa_id: number;
  actualizar_alquiler_auto: boolean;
  // ── WhatsApp (agregado en app.py v1.15x-v1.176) ──
  whatsapp_habilitado: boolean;
  whatsapp_credenciales_propias: boolean;
  whatsapp_phone_id: string | null;
  whatsapp_token_secret_id: string | null; // referencia a Supabase Vault, no el token en texto plano
  whatsapp_numero_id: number | null; // FK -> whatsapp_numeros.id
  // Módulo 3 — motor de índices (migración 0004)
  cron_indices_habilitado: boolean;
}

export interface WhatsappNumerosRow {
  /** Pool de números compartidos que administra el superadmin para empresas sin credenciales propias. */
  id: number;
  nombre: string;
  phone_id: string;
  token_secret_id: string; // referencia a Supabase Vault
}

export interface WhatsappRecordatoriosRow {
  /** Configuración de recordatorios automáticos por empresa (Módulo 8). */
  id: number;
  empresa_id: number;
  tipo: TipoRecordatorioWhatsapp;
  dia_del_mes: number | null; // columna original de v1 — NO usar en v2, solo la lee/escribe v1
  dias_antes: number | null; // columna de v2: offset real de días antes del evento
  activo: boolean;
}

export interface WhatsappRecordatoriosLogRow {
  /** Deduplicación: evita reenviar el mismo recordatorio el mismo día. */
  id: number;
  empresa_id: number;
  tipo: string;
  codigo_contrato: string;
  fecha_envio: string;
  enviado: boolean;
}

export interface PropiedadesRow {
  id: number;
  empresa_id: number;
  alias_propiedad: string; // clave real usada para relacionar con contratos, NO id
  calle: string;
  numero: string;
  departamento: string | null;
  propietario: string;
  grupo: string | null; // texto libre, agrupa propiedades para gastos compartidos (Módulo 7)
}

export interface InquilinosRow {
  id: number;
  empresa_id: number;
  dni: string;
  nombres: string;
  apellidos: string;
  telefono: string | null;
  email: string | null;
  auth_user_id: string | null; // Módulo 9 — Portal del Inquilino. Puede repetirse entre filas (multi-tenencia, ver DESIGN_LOG.md)
}

export interface ComprobantesInquilinoRow {
  id: number;
  empresa_id: number;
  codigo_contrato: string;
  storage_path: string;
  monto_declarado: number | null;
  fecha_subida: string;
  estado: "pendiente" | "aprobado" | "rechazado";
  revisado_por: string | null;
  fecha_revision: string | null;
}

export interface ReclamosInquilinoRow {
  id: number;
  empresa_id: number;
  codigo_contrato: string;
  descripcion: string;
  estado: "abierto" | "en_progreso" | "resuelto";
  fecha: string;
  respuesta_staff: string | null;
  gasto_id: number | null; // trazabilidad con gastos_propiedades — ver DESIGN_LOG.md
}

export interface ContratosRow {
  id: number;
  codigo: string;
  empresa_id: number;
  alias_propiedad: string; // FK real hacia propiedades.alias_propiedad (confirmado en app.py líneas 1995, 7012)
  dni_inquilino: string; // FK real hacia inquilinos.dni
  monto_inicial: number;
  fecha_inicio: string;
  fin_contrato: string | null;
  prox_actualizacion: string | null;
  indice: IndiceActualizacion;
  frecuencia_actualizacion: FrecuenciaActualizacion;
  estado: "Activo" | "Finalizado" | "Cancelado";
  // Vencimiento automático + archivado (ver 0003 y notas de diseño)
  fecha_finalizacion: string | null;
  finalizado_por: "auto_vencimiento" | "renovacion" | null;
  archivado: boolean;
  /**
   * Cuenta corriente del contrato, mantenida por el trigger
   * trg_recalcular_saldo (migración 0003_saldo_contratos.sql).
   * NO escribir desde la app — se actualiza sola al insertar en
   * pagos_historial, sin importar si el pago vino de v1 o v2.
   * Positivo = debe el inquilino. Negativo = a favor del inquilino.
   */
  saldo_actual: number;
  alquiler: number | null; // alquiler vigente (último cobrado), distinto de monto_inicial
  alquiler_calculado: number | null; // valor calculado por el motor de índices (Módulo 3)
  alquiler_calculado_fecha: string | null;
  honorarios_pagados_base: number;
  cuotas_honorarios_pagadas_base: number;
  garantia_pagada_base: number;
  cuotas_deposito_pagadas_base: number;
  /**
   * ⚠️ COLISIÓN DE NOMBRES: estas 2 columnas en `contratos` (total
   * PACTADO para todo el contrato) tienen el MISMO NOMBRE que las
   * columnas de `pagos_historial` (monto de ESE pago puntual) —
   * son conceptos distintos que casualmente comparten nombre.
   * Si NULL, v1 usa `monto_inicial` como valor por defecto (no
   * hay garantía/honorarios "sin pactar" salvo que explícitamente
   * se cargue 0). Ver docs/DESIGN_LOG.md.
   */
  monto_honorarios: number | null; // total pactado, NO el de un pago puntual
  cuota_honorarios: number; // cantidad de cuotas pactadas
  monto_garantia: number | null; // total pactado, NO el de un pago puntual
  cuotas_deposito: number; // cantidad de cuotas pactadas
  honorarios_pct: number; // % de comisión mensual — alimenta pagos_historial.monto_gasto_admin
  act_contrato: number | string | null; // campo viejo de v1 (Módulo 2/Dashboard) — puede ser número de meses o etiqueta de texto, ver lib/dashboard/metrics.ts
  // Módulo 5 — reemplazan el texto libre roto de `servicios` (migración 0008)
  cargo_electricidad: "Inquilino" | "Propietario";
  cargo_gas: "Inquilino" | "Propietario";
  cargo_municipalidad: "Inquilino" | "Propietario";
  cargo_ooss: "Inquilino" | "Propietario";
  cargo_expensas: "Inquilino" | "Propietario";
  cargo_imp_inmobiliario: "Inquilino" | "Propietario";
  cochera: number | null;
  calc_duracion: number | null; // duración total en meses, usado para la regla de renovación
  mes_contrato: number | null; // "mes vivo" actual del contrato
}

export interface PagosHistorialRow {
  id: number;
  empresa_id: number;
  codigo_contrato: string;
  propiedad: string; // alias_propiedad, no FK numérica (ver app.py línea 1493)
  tipo_pago: TipoPago;
  periodo: string; // "Mes N de M", relativo al contrato — ver nota en planilla_verificaciones
  inquilino: string;
  fecha: string;
  username: string | null;
  // Conceptos (columnas reales confirmadas vía volcado CSV de producción)
  monto_alquiler: number;
  monto_expensas: number;
  monto_edesal: number;
  monto_gas: number;
  monto_municipalidad: number;
  monto_cochera: number;
  monto_ooss: number;
  monto_imp_inmobiliario: number;
  monto_honorarios: number; // fee de gestión en cuotas — NO es la comisión (ver monto_gasto_admin)
  monto_garantia: number;
  monto_gasto_admin: number; // comisión real de la inmobiliaria = monto_abonado * honorarios_pct/100 (ver Módulo 6)
  concepto_extra_desc: string | null;
  monto_concepto_extra: number;
  monto_abonado: number;
  saldo_pendiente: number; // cuenta corriente (ver 0003_saldo_contratos.sql) — NO aislado por período
  metodo_pago: string | null;
  cotizacion_usd: number | null;
  registrado_por: string | null;
  nro_comprobante: string | null;
  comentario: string | null;
  /**
   * Solo se completa en pagos tipo Complemento: nro_comprobante
   * de la fila Normal que dejó el saldo pendiente de ese mismo
   * período. Permite mostrar contexto en el PDF ("este pago
   * cubre el saldo del Comprobante RC-...") en vez del "$0,00"
   * desconectado que muestra v1. Ver docs/DESIGN_LOG.md.
   */
  comprobante_referencia: string | null;
}

export interface GastosPropiedadesRow {
  id: number;
  empresa_id: number;
  propiedad_id: number; // FK numérica real (distinto de contratos, que usa alias_propiedad)
  fecha: string;
  categoria: string;
  descripcion: string;
  monto: number;
  proveedor: string | null;
  comprobante: string | null;
  pagado_por: "Inmobiliaria" | "Propietario" | "Inquilino" | "Otro";
  observaciones: string | null;
  tipo_gasto: string; // p.ej. "Extraordinario" — determina si es candidato a retención en Rendición
  cotizacion_usd: number | null;
  cobrado: boolean; // true = ya retenido en una liquidación (ver Módulo 7)
  periodo_cobrado: string | null;
}

export interface LiquidacionesPropietariosRow {
  id: number;
  empresa_id: number;
  propietario: string;
  periodo: string;
  monto_calculado: number;
  saldo_anterior: number;
  monto_retencion_gastos: number;
  monto_a_liquidar: number;
  monto_liquidado: number;
  saldo_pendiente: number;
  fecha_liquidacion: string;
  registrado_por: string;
}

// =====================================================================
// Database — cada tabla referencia su Row nombrado, sin auto-referencia.
// =====================================================================

export type Database = {
  // Requerido por versiones nuevas de @supabase/supabase-js (2.50.4+) —
  // sin esto, la inferencia de tipos de TODO el cliente se rompe
  // (issue conocido: github.com/supabase/supabase-js/issues/1483).
  // Nuestro package.json fija "^2.75.0", así que npm puede instalar
  // cualquier versión 2.x más nueva — este campo lo deja compatible con
  // todas, viejas y nuevas (las viejas simplemente lo ignoran).
  __InternalSupabase: {
    PostgrestVersion: "12";
  };
  public: {
    Tables: {
      empresas: {
        Row: EmpresasRow;
        Insert: Partial<EmpresasRow>;
        Update: Partial<EmpresasRow>;
        Relationships: [];
      };
      usuarios_central: {
        Row: UsuariosCentralRow;
        Insert: Partial<UsuariosCentralRow>;
        Update: Partial<UsuariosCentralRow>;
        Relationships: [];
      };
      permisos_usuario: {
        Row: PermisosUsuarioRow;
        Insert: Partial<PermisosUsuarioRow>;
        Update: Partial<PermisosUsuarioRow>;
        Relationships: [];
      };
      configuraciones_empresa: {
        Row: ConfiguracionesEmpresaRow;
        Insert: Partial<ConfiguracionesEmpresaRow>;
        Update: Partial<ConfiguracionesEmpresaRow>;
        Relationships: [];
      };
      whatsapp_numeros: {
        Row: WhatsappNumerosRow;
        Insert: Partial<WhatsappNumerosRow>;
        Update: Partial<WhatsappNumerosRow>;
        Relationships: [];
      };
      whatsapp_recordatorios: {
        Row: WhatsappRecordatoriosRow;
        Insert: Partial<WhatsappRecordatoriosRow>;
        Update: Partial<WhatsappRecordatoriosRow>;
        Relationships: [];
      };
      whatsapp_recordatorios_log: {
        Row: WhatsappRecordatoriosLogRow;
        Insert: Partial<WhatsappRecordatoriosLogRow>;
        Update: Partial<WhatsappRecordatoriosLogRow>;
        Relationships: [];
      };
      propiedades: {
        Row: PropiedadesRow;
        Insert: Partial<PropiedadesRow>;
        Update: Partial<PropiedadesRow>;
        Relationships: [];
      };
      inquilinos: {
        Row: InquilinosRow;
        Insert: Partial<InquilinosRow>;
        Update: Partial<InquilinosRow>;
        Relationships: [];
      };
      comprobantes_inquilino: {
        Row: ComprobantesInquilinoRow;
        Insert: Partial<ComprobantesInquilinoRow>;
        Update: Partial<ComprobantesInquilinoRow>;
        Relationships: [];
      };
      reclamos_inquilino: {
        Row: ReclamosInquilinoRow;
        Insert: Partial<ReclamosInquilinoRow>;
        Update: Partial<ReclamosInquilinoRow>;
        Relationships: [];
      };
      contratos: {
        Row: ContratosRow;
        Insert: Partial<ContratosRow>;
        Update: Partial<ContratosRow>;
        Relationships: [];
      };
      pagos_historial: {
        Row: PagosHistorialRow;
        Insert: Partial<PagosHistorialRow>;
        Update: Partial<PagosHistorialRow>;
        Relationships: [];
      };
      gastos_propiedades: {
        Row: GastosPropiedadesRow;
        Insert: Partial<GastosPropiedadesRow>;
        Update: Partial<GastosPropiedadesRow>;
        Relationships: [];
      };
      liquidaciones_propietarios: {
        Row: LiquidacionesPropietariosRow;
        Insert: Partial<LiquidacionesPropietariosRow>;
        Update: Partial<LiquidacionesPropietariosRow>;
        Relationships: [];
      };
    };
    // Las 4 secciones de abajo las exige la maquinaria de tipos genéricos
    // de @supabase/postgrest-js (GenericSchema) para que .insert()/.select()
    // se resuelvan bien — sin ellas, la inferencia colapsaba a `never[]`
    // (hallazgo real de esta sesión, viendo el error de build en Vercel).
    // Vacías por ahora: las funciones RPC siguen llamándose igual que
    // hasta ahora, solo quedan sin tipado estricto de parámetros.
    Views: {
      [_ in never]: never;
    };
    Functions: {
      [_ in never]: never;
    };
    Enums: {
      [_ in never]: never;
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
};
