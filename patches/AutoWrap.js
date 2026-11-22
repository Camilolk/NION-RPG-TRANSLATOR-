/*:
 * @plugindesc NION AutoWrap v0.1 — ajuste visual de mensajes (RPG Maker MV/MZ)
 * @author NION
 * @help
 * Ajusta palabras y caracteres CJK al ancho del cuadro de diálogo.
 * Mantiene los códigos de escape procesados por el motor.
 * Plugin experimental: comprueba mensajes largos, elecciones y otros plugins.
 */
(function () {
  "use strict";
  if (typeof Window_Message === "undefined") return;
  var proto = Window_Message.prototype;
  var params = (typeof PluginManager !== "undefined" && PluginManager.parameters) ? PluginManager.parameters("NION_AutoWrap") : {};
  var fontSize = Number(params.fontSize || 0);
  if (fontSize >= 12 && fontSize <= 48) {
    proto.standardFontSize = function () { return fontSize; };
  }
  var original = proto.processNormalCharacter;
  if (typeof original !== "function") return;

  function isCJK(c) {
    return /[\u2e80-\u9fff\uac00-\ud7af\u3040-\u30ff\uff00-\uffef]/.test(c);
  }
  function width(win, str) {
    return win.textWidth(str);
  }
  proto.processNormalCharacter = function (state) {
    var text = state.text || "";
    var char = text[state.index] || "";
    if (!char) return original.call(this, state);
    var limit = this.contentsWidth() - (this.textPadding ? this.textPadding() : 0);
    if (char === " " && state.x <= state.left) {
      state.index++;
      return;
    }
    var piece = char;
    if (!isCJK(char) && !/\s/.test(char)) {
      var tail = text.slice(state.index).match(/^[^\s\x1b\u2e80-\u9fff\uac00-\ud7af\u3040-\u30ff\uff00-\uffef]+/);
      if (tail) piece = tail[0];
    }
    if (state.x > state.left && state.x + width(this, piece) > limit) {
      this.processNewLine(state);
    }
    original.call(this, state);
  };
})();
