/**
 * Replica el formato `f"$ {valor:,.2f}"` de app.py: separador de miles
 * con coma, 2 decimales con punto — ej. "$ 1,234,567.89".
 */
export function formatMoneda(valor: number): string {
  const partes = valor.toFixed(2).split(".");
  const parteEntera = partes[0] ?? "0";
  const parteDecimal = partes[1] ?? "00";
  const entero = parteEntera.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `$ ${entero}.${parteDecimal}`;
}

/**
 * Replica el formato `f"{valor:,.0f}"` de app.py: separador de miles,
 * SIN decimales y SIN signo "$" — es el formato que usan las variables
 * de las plantillas de WhatsApp (recibo preliminar, etc.), distinto de
 * formatMoneda() que sí lleva "$" y 2 decimales.
 */
export function formatMontoEntero(valor: number): string {
  return Math.round(valor)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

const MESES_ES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
] as const;

/** "Septiembre 2026" — mismo formato que `_nombre_mes` en app.py. */
export function nombreMesAnio(fecha: Date = new Date()): string {
  return `${MESES_ES[fecha.getMonth()]} ${fecha.getFullYear()}`;
}

/**
 * Día 10 del mes actual, dd/mm/yyyy — misma "fecha límite" fija que
 * usa v1 en el recibo preliminar (`datetime.now().date().replace(day=10)`).
 */
export function fechaLimiteDia10(fecha: Date = new Date()): string {
  const limite = new Date(fecha.getFullYear(), fecha.getMonth(), 10);
  const dd = String(limite.getDate()).padStart(2, "0");
  const mm = String(limite.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${limite.getFullYear()}`;
}
