// 29/10 (vérification des apps des TL au téléphone) : la barre d'onglets reste au-dessus du contenu qui défile, dont les
// boutons de période (« Auj. », « Hier »… en z-index 1) qui s'affichaient par-dessus les icônes.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const app = fs.readFileSync(path.join(__dirname, '../src/components/App.tsx'), 'utf8');
assert.match(app, /barre fixed bottom-0 inset-x-0 z-20/);
const css = fs.readFileSync(path.join(__dirname, '../src/app/globals.css'), 'utf8');
const z = Number((css.match(/\.segment button \{[^}]*z-index:\s*(\d+)/) || [])[1] || 0);
assert.ok(z < 20, 'les boutons de période restent sous la barre');
console.log("Barre d'onglets : au-dessus des boutons de période.");
