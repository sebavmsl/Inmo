/**
 * Tipos compartidos del alta de contratos (Entrega 2 — V2.018).
 * Sin dependencias de servidor: los usan tanto los Server Actions como
 * los componentes de cliente.
 */
import type { IndiceActualizacion } from "@/lib/types/database.types";
import type { Cargo, TipoGarantia } from "@/lib/carga/calculoContrato";

export type EstadoContrato = "Activo" | "Finalizado" | "Cancelado";
export const ESTADOS_CONTRATO: EstadoContrato[] = ["Activo", "Finalizado", "Cancelado"];

export const INDICES: IndiceActualizacion[] = ["ICL", "IPC", "UVA", "Otro"];

/** contratos.act_contrato guarda la frecuencia en meses; 0 = sin actualización (como Python). */
export const FRECUENCIAS: { meses: number; label: string }[] = [
  { meses: 1, label: "Mensual" },
  { meses: 2, label: "Bimestral" },
  { meses: 3, label: "Trimestral" },
  { meses: 4, label: "Cuatrimestral" },
  { meses: 6, label: "Semestral" },
  { meses: 12, label: "Anual" },
  { meses: 24, label: "Bianual" },
  { meses: 0, label: "Sin actualización" },
];

export const CARGOS: Cargo[] = ["Inquilino", "Propietario"];

export const METODOS_PAGO = ["Transferencia Bancaria", "Efectivo", "Depósito", "Cheque"];

export interface ServiciosContrato {
  expensas: number;
  edesal: number;
  gas: number;
  municipalidad: number;
  ooss: number;
  impInmobiliario: number;
}

export interface CargosContrato {
  electricidad: Cargo;
  gas: Cargo;
  municipalidad: Cargo;
  ooss: Cargo;
  expensas: Cargo;
  impInmobiliario: Cargo;
}

/** Lista de servicios con su monto y su "a cargo de", en el orden de pantalla. */
export const SERVICIOS: { monto: keyof ServiciosContrato; cargo: keyof CargosContrato; label: string }[] = [
  { monto: "edesal", cargo: "electricidad", label: "Electricidad" },
  { monto: "gas", cargo: "gas", label: "Gas" },
  { monto: "municipalidad", cargo: "municipalidad", label: "Municipalidad" },
  { monto: "ooss", cargo: "ooss", label: "OO.SS." },
  { monto: "expensas", cargo: "expensas", label: "Expensas" },
  { monto: "impInmobiliario", cargo: "impInmobiliario", label: "Imp. Inmobiliario" },
];

export interface DatosAltaContrato {
  aliasPropiedad: string;
  dniInquilino: string;
  estado: EstadoContrato;
  fechaInicio: string; // YYYY-MM-DD
  finContrato: string; // YYYY-MM-DD
  diaVencimiento: number; // 1-31
  montoInicial: number;
  indice: IndiceActualizacion;
  frecuenciaMeses: number; // 0 = sin actualización
  honorariosPct: number; // % de comisión mensual (a cargo del propietario)
  montoHonorarios: number; // total de honorarios del contrato (a cargo del inquilino)
  cuotaHonorarios: number;
  tipoGarantia: TipoGarantia;
  montoGarantia: number; // depósito
  cuotasDeposito: number;
  montoPagare: number;
  servicios: ServiciosContrato;
  cargos: CargosContrato;
  cargoGeneralServicios: number;
  cochera: number; // monto inicial de la cochera
  cocheraActualizaConIndice: boolean;
  /** Alquiler vigente hoy. null = usar el que calcula el sistema con el índice. */
  alquilerVigente: number | null;
  /** Solo en una renovación: el contrato que se renueva (informativo). */
  codigoAnterior: string | null;
}

/** Un mes ya transcurrido, con los montos que calcula el sistema. */
export interface MesCalculado {
  nro: number;
  periodo: string; // "Mes N de M"
  mesCalendario: string; // "Marzo 2026"
  vencimiento: string; // YYYY-MM-DD
  alquiler: number;
  cochera: number;
  expensas: number;
  edesal: number;
  gas: number;
  municipalidad: number;
  ooss: number;
  impInmobiliario: number;
  cargoGeneral: number;
  honorarios: number;
  garantia: number;
  subtotal: number;
  /** false si no se pudo consultar el índice y se usó el último monto conocido. */
  indiceOk: boolean;
}

/** Lo que el usuario decide para cada mes antes de confirmar. */
export interface MesConfirmado extends MesCalculado {
  estado: "Pagado" | "Adeudado";
  ajuste: number; // ± intereses, gastos
  comision: boolean;
  pagaAhora: boolean;
  montoPagado: number;
  fechaPago: string; // YYYY-MM-DD
  metodoPago: string;
}

export interface PrevisualizacionAlta {
  duracion: number;
  mesActual: number;
  proxActualizacion: string; // YYYY-MM-DD
  necesitaRenovacion: boolean;
  alquilerVigenteCalculado: number;
  cocheraVigente: number;
  meses: MesCalculado[];
  avisos: string[];
}

export interface OpcionesAlta {
  propiedades: { alias: string; direccion: string; propietario: string; contratoActivo: string | null }[];
  inquilinos: { dni: string; nombre: string }[];
}
