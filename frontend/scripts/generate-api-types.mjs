/**
 * Render `types/api.ts` from the backend's OpenAPI document.
 *
 * The API contract has one authority — the FastAPI schemas — and a hand-copied
 * TypeScript mirror of 118 models drifts the first time a field is renamed.
 * This reads the published document instead, so a drifted type is a diff in
 * version control rather than a runtime surprise.
 *
 *   node scripts/generate-api-types.mjs                       # from a running API
 *   node scripts/generate-api-types.mjs ../openapi.json       # from a dumped file
 *
 * The API base URL comes from OPENAPI_URL, defaulting to the local backend.
 */

import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUTPUT = path.join(HERE, "..", "types", "api.ts");
const DEFAULT_URL = process.env.OPENAPI_URL ?? "http://localhost:8000/openapi.json";

/** Multipart bodies are sent as `FormData`, never as one of these objects. */
const SKIP = (name) => name.startsWith("Body_");

/** `Page[GraphSummary]` becomes `Page<GraphSummary>` over one generic. */
const PAGE = /^Page_(.+)_$/;

const RESERVED = /^[A-Za-z_$][A-Za-z0-9_$]*$/;

function ref(name) {
  const paged = PAGE.exec(name);
  return paged ? `Page<${ref(paged[1])}>` : name;
}

function scalar(schema) {
  switch (schema.format) {
    case "uuid":
      return "UUID";
    case "date":
      return "DateString";
    case "date-time":
      return "DateTimeString";
    default:
      break;
  }
  switch (schema.type) {
    case "string":
      return "string";
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "null":
      return "null";
    default:
      return null;
  }
}

function render(schema) {
  if (!schema || Object.keys(schema).length === 0) return "unknown";
  if (schema.$ref) return ref(schema.$ref.split("/").pop());

  if (schema.anyOf || schema.oneOf) {
    const parts = (schema.anyOf ?? schema.oneOf).map(render);
    // `X | null` reads better with the null last, however Pydantic ordered it.
    const nulls = parts.filter((p) => p === "null");
    const rest = [...new Set(parts.filter((p) => p !== "null"))];
    return [...rest, ...nulls.slice(0, 1)].join(" | ");
  }

  if (schema.type === "array") return `${wrap(render(schema.items))}[]`;

  if (schema.type === "object" || schema.properties) {
    if (schema.additionalProperties && schema.additionalProperties !== true) {
      return `Record<string, ${render(schema.additionalProperties)}>`;
    }
    if (!schema.properties) return "Record<string, unknown>";
  }

  if (schema.enum) return schema.enum.map((v) => JSON.stringify(v)).join(" | ");

  return scalar(schema) ?? "unknown";
}

/** `(A | null)[]`, not `A | null[]`. */
function wrap(rendered) {
  return rendered.includes(" | ") ? `(${rendered})` : rendered;
}

function docComment(schema, indent = "") {
  const lines = [];
  if (schema.description) lines.push(...schema.description.split("\n"));
  if (lines.length === 0) return "";
  if (lines.length === 1) return `${indent}/** ${lines[0].trim()} */\n`;
  return [
    `${indent}/**`,
    ...lines.map((l) => `${indent} * ${l}`.trimEnd()),
    `${indent} */`,
    "",
  ].join("\n");
}

function renderInterface(name, schema) {
  const required = new Set(schema.required ?? []);
  const body = Object.entries(schema.properties ?? {}).map(([key, property]) => {
    const optional = required.has(key) ? "" : "?";
    const quoted = RESERVED.test(key) ? key : JSON.stringify(key);
    return `${docComment(property, "  ")}  ${quoted}${optional}: ${render(property)};`;
  });

  // `ChartData` is `additionalProperties: true` so a teacher can pass Chart.js
  // options the schema does not name.
  if (schema.additionalProperties === true) body.push("  [key: string]: unknown;");

  return `${docComment(schema)}export interface ${name} {\n${body.join("\n")}\n}`;
}

function renderSchema(name, schema) {
  if (schema.enum && !schema.properties) {
    return `${docComment(schema)}export type ${name} = ${render(schema)};`;
  }
  if (schema.properties || schema.type === "object") return renderInterface(name, schema);
  return `${docComment(schema)}export type ${name} = ${render(schema)};`;
}

async function loadSpec(source) {
  if (source) return JSON.parse(await readFile(source, "utf8"));
  const response = await fetch(DEFAULT_URL);
  if (!response.ok) {
    throw new Error(`${DEFAULT_URL} answered ${response.status}. Is the API running?`);
  }
  return response.json();
}

const spec = await loadSpec(process.argv[2]);
const schemas = spec.components?.schemas ?? {};

const aliases = [];
const declarations = [];

for (const name of Object.keys(schemas).sort()) {
  if (SKIP(name)) continue;
  const paged = PAGE.exec(name);
  if (paged) {
    aliases.push(`export type ${name.replace(/_/g, "")} = Page<${ref(paged[1])}>;`);
    continue;
  }
  declarations.push(renderSchema(name, schemas[name]));
}

const header = `/**
 * Types mirroring the API schemas — generated, do not edit by hand.
 *
 * Source: ${spec.info?.title ?? "API"} ${spec.info?.version ?? ""} OpenAPI document.
 * Regenerate with \`npm run api:types\` against a running backend.
 *
 * Formats are aliased rather than erased: a \`UUID\` and a \`DateTimeString\` are
 * both strings to the compiler, but the alias says which one an endpoint wants.
 */

/** A UUID in canonical hyphenated form. */
export type UUID = string;
/** An ISO-8601 date, \`YYYY-MM-DD\`. */
export type DateString = string;
/** An ISO-8601 timestamp with an offset. */
export type DateTimeString = string;

/** The collection envelope every list endpoint returns (04-api-design §5.1). */
export interface Page<T> {
  items: T[];
  /** 1-indexed. */
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
`;

const body = [header, ...declarations, "", "/* Paged collections. */", ...aliases, ""].join("\n\n");

await writeFile(OUTPUT, body, "utf8");
console.log(
  `Wrote ${path.relative(process.cwd(), OUTPUT)}: ` +
    `${declarations.length} models, ${aliases.length} paged collections.`,
);
