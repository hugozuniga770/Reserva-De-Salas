// Puente para las pruebas: usa EXACTAMENTE docs/cifrado.js (el mismo que corre en el celular).
const path = require("path");
const C = require(path.join(__dirname, "..", "docs", "cifrado.js"));
const [, , modo, a, b] = process.argv;
(async () => {
  if (modo === "llaves") console.log(JSON.stringify(await C.generarLlaves()));
  else if (modo === "cifrar") console.log(await C.cifrar(JSON.parse(b), a));
  else if (modo === "descifrar") console.log(JSON.stringify(await C.descifrar(b, a)));
  else process.exit(2);
})().catch((e) => { console.error(e); process.exit(1); });
