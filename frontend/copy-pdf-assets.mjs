import { cp, mkdir } from "node:fs/promises";
await mkdir(new URL("./public/pdfjs/", import.meta.url), { recursive: true });
for (const name of ["cmaps", "standard_fonts"]) {
  await cp(
    new URL("./node_modules/pdfjs-dist/" + name, import.meta.url),
    new URL("./public/pdfjs/" + name, import.meta.url),
    { recursive: true },
  );
}
console.log("Local PDF.js assets ready");
