/* Cifrado de solicitudes: AES-256-GCM para los datos + RSA-OAEP-SHA256 para la llave.
   Mismo formato que solicitudes.py (bot). Funciona en el navegador y en Node 18+. */
(function (raiz) {
  "use strict";
  const cripto = () => raiz.crypto || globalThis.crypto;
  const RSA = { name: "RSA-OAEP", hash: "SHA-256" };
  const PATRON = /upbv1\.([A-Za-z0-9+/=]+)\.([A-Za-z0-9+/=]+)\.([A-Za-z0-9+/=]+)/;

  function b64(buf) {
    const a = new Uint8Array(buf);
    let s = "";
    for (let i = 0; i < a.length; i++) s += String.fromCharCode(a[i]);
    return btoa(s);
  }
  function deB64(s) {
    return Uint8Array.from(atob(String(s).replace(/\s/g, "")), (c) => c.charCodeAt(0));
  }

  async function generarLlaves() {
    const par = await cripto().subtle.generateKey(
      { ...RSA, modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]) }, true, ["encrypt", "decrypt"]);
    return {
      publica: b64(await cripto().subtle.exportKey("spki", par.publicKey)),
      privada: b64(await cripto().subtle.exportKey("pkcs8", par.privateKey)),
    };
  }

  async function cifrar(datos, publicaB64) {
    const s = cripto().subtle;
    const pub = await s.importKey("spki", deB64(publicaB64), RSA, false, ["encrypt"]);
    const aes = await s.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt"]);
    const iv = cripto().getRandomValues(new Uint8Array(12));
    const datosCifrados = await s.encrypt({ name: "AES-GCM", iv }, aes, new TextEncoder().encode(JSON.stringify(datos)));
    const llaveEnvuelta = await s.encrypt({ name: "RSA-OAEP" }, pub, await s.exportKey("raw", aes));
    return `upbv1.${b64(llaveEnvuelta)}.${b64(iv)}.${b64(datosCifrados)}`;
  }

  async function descifrar(texto, privadaB64) {
    const m = PATRON.exec(texto || "");
    if (!m) throw new Error("No hay una solicitud cifrada en ese texto.");
    const s = cripto().subtle;
    const priv = await s.importKey("pkcs8", deB64(privadaB64), RSA, false, ["decrypt"]);
    const llave = await s.decrypt({ name: "RSA-OAEP" }, priv, deB64(m[1]));
    const aes = await s.importKey("raw", llave, "AES-GCM", false, ["decrypt"]);
    const claro = await s.decrypt({ name: "AES-GCM", iv: deB64(m[2]) }, aes, deB64(m[3]));
    return JSON.parse(new TextDecoder().decode(claro));
  }

  const api = { generarLlaves, cifrar, descifrar, PATRON };
  raiz.UPBCifrado = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
