/**
 * Parser de CSV chico y sin dependencias (no hay librería tipo Papaparse
 * instalada, y este entorno no puede instalar paquetes nuevos con
 * confianza — ver notas de sesión). Soporta:
 *   - Delimitador `,` o `;` — se detecta solo mirando la primera línea
 *     (v1 exportaba con `;`, plantillas propias de v2 usan `,` — así
 *     sirve cualquiera de los dos sin pedirle al usuario que elija).
 *   - Campos entre comillas dobles, con comas/punto y coma o saltos de
 *     línea adentro, y `""` como comilla escapada (estándar CSV/RFC 4180).
 *   - BOM de UTF-8 al principio del archivo (lo agrega Excel al exportar).
 */

function detectarDelimitador(primeraLinea: string): "," | ";" {
  const comas = (primeraLinea.match(/,/g) ?? []).length;
  const puntoYComa = (primeraLinea.match(/;/g) ?? []).length;
  return puntoYComa > comas ? ";" : ",";
}

/** Parsea el texto completo en una matriz de filas (cada fila = array de celdas), respetando comillas. */
function aFilas(texto: string, delimitador: string): string[][] {
  const filas: string[][] = [];
  let fila: string[] = [];
  let celda = "";
  let dentroDeComillas = false;

  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];

    if (dentroDeComillas) {
      if (c === '"') {
        if (texto[i + 1] === '"') {
          celda += '"';
          i++;
        } else {
          dentroDeComillas = false;
        }
      } else {
        celda += c;
      }
      continue;
    }

    if (c === '"') {
      dentroDeComillas = true;
    } else if (c === delimitador) {
      fila.push(celda);
      celda = "";
    } else if (c === "\n" || c === "\r") {
      // \r\n: el \r dispara el cierre de fila, el \n siguiente se ignora por quedar vacío
      if (c === "\r" && texto[i + 1] === "\n") continue;
      fila.push(celda);
      filas.push(fila);
      fila = [];
      celda = "";
    } else {
      celda += c;
    }
  }
  // última celda/fila si el archivo no termina con salto de línea
  if (celda.length > 0 || fila.length > 0) {
    fila.push(celda);
    filas.push(fila);
  }

  return filas.filter((f) => !(f.length === 1 && f[0].trim() === "")); // saltea líneas en blanco sueltas
}

export interface CsvParseado {
  headers: string[];
  filas: Record<string, string>[];
}

/** Punto de entrada — recibe el texto crudo del archivo (ya leído con .text() del lado del cliente). */
export function parsearCsv(textoOriginal: string): CsvParseado {
  const texto = textoOriginal.replace(/^﻿/, ""); // BOM de Excel
  const primerSalto = texto.indexOf("\n");
  const primeraLinea = primerSalto >= 0 ? texto.slice(0, primerSalto) : texto;
  const delimitador = detectarDelimitador(primeraLinea);

  const filasCrudas = aFilas(texto, delimitador);
  if (filasCrudas.length === 0) return { headers: [], filas: [] };

  const headers = (filasCrudas[0] ?? []).map((h) => h.trim());
  const filas = filasCrudas.slice(1).map((f) => {
    const registro: Record<string, string> = {};
    headers.forEach((h, idx) => {
      registro[h] = (f[idx] ?? "").trim();
    });
    return registro;
  });

  return { headers, filas };
}
