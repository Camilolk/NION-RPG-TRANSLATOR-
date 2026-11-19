/*:
 * @target MZ
 * @plugindesc AutoWrap v2: ajuste dinamico de dialogos.
 * @author Camilo
 * @help Une lineas y ajusta por ancho real. Solo RPG Maker MZ.
 */
(() => {
"use strict";
const CJK = /[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]/;
const ESC = /\x1b(?:[A-Za-z]+\[\d*\]|[{}.|!><^$\\])/g;
const _create = Window_Message.prototype.createTextState;
Window_Message.prototype.createTextState = function(text,x,y,width) {
 text=text.replace(/[ \t]*\n[ \t]*/g,(m,off,str)=>{
  const prev=str[off-1]||"", next=str[off+m.length]||"";
  return (CJK.test(prev)||CJK.test(next))?"":" ";
 });
 return _create.call(this,text,x,y,width);
};
const _process=Window_Message.prototype.processCharacter;
Window_Message.prototype.processCharacter=function(state) {
 const text=state.text,i=state.index,c=text[i],noInicio=state.x>state.startX;
 if(c===" ") {
  const m=text.slice(i+1).match(/^[^ \n\f]+/);
  if(m) {
   const w=this.textWidth(" ")+this.textWidth(m[0].replace(ESC,""));
   if(state.x+w>this.innerWidth) {
    state.index++;this.processNewLine(state);return;
   }
  }
 } else if(c&&CJK.test(c)) {
  if(noInicio&&state.x+this.textWidth(c)>this.innerWidth) {
   this.processNewLine(state);return;
  }
 } else if(c&&/[A-Za-z0-9]/.test(c)&&i>0&&CJK.test(text[i-1])) {
  const m=text.slice(i).match(/^[A-Za-z0-9'’\-]+/);
  if(m&&noInicio&&state.x+this.textWidth(m[0])>this.innerWidth) {
   this.processNewLine(state);return;
  }
 }
 _process.call(this,state);
};
})();
