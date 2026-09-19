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
