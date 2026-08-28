// Carte extraite du site actuel (atmospheredesdunes.fr/menus) le 28/08/2026.
// Prix réels publiés par le restaurant — À FAIRE VALIDER par le restaurateur avant mise en ligne.
module.exports = [
  {
    id: 'formules',
    titre: 'Formules',
    items: [
      { nom: 'Formule Midi (jusqu’à 13h15)', detail: 'Pizza Régina, tenders ou moules + dessert (2 boules)', prix: '18,00 €' },
      { nom: 'Menu Enfant (jusqu’à 10 ans)', detail: 'Plat + dessert', prix: '10,90 €' },
    ],
  },
  {
    id: 'planches',
    titre: 'Pour l’apéro',
    items: [
      { nom: 'Planche croquante', detail: '15 bouchées à partager', prix: '14,90 €' },
      { nom: 'Notre Préfou maison', detail: 'La spécialité vendéenne — demi 7,00 € / entier', prix: '11,50 €' },
      { nom: 'Saucisson au choix', detail: '', prix: '7,90 €' },
    ],
  },
  {
    id: 'plats',
    titre: 'À la carte',
    items: [
      { nom: 'Salade César', detail: 'Petite 11,90 € / grande', prix: '18,90 €' },
      { nom: 'Pièce du boucher', detail: 'VBF 180 g', prix: '22,00 €' },
      { nom: 'Andouillette artisanale', detail: '', prix: '18,90 €' },
      { nom: 'Fish and chips', detail: '', prix: '14,90 €' },
      { nom: 'Tenders de poulet', detail: '', prix: '14,90 €' },
    ],
  },
  {
    id: 'burgers',
    titre: 'Burgers maison',
    items: [
      { nom: 'Classico', detail: 'Bœuf ou poulet', prix: '18,90 €' },
      { nom: 'Végétarien', detail: '', prix: '16,90 €' },
    ],
  },
  {
    id: 'moules',
    titre: 'Moules-frites (~800 g)',
    items: [
      { nom: 'Marinière', detail: '', prix: '14,90 €' },
      { nom: 'À la crème', detail: '', prix: '16,00 €' },
      { nom: 'Curry-piment', detail: 'La signature citée dans les avis', prix: '16,90 €' },
      { nom: 'Au bleu AOP', detail: '', prix: '17,50 €' },
    ],
  },
  {
    id: 'pizzas',
    titre: 'Pizzas (pâte fine)',
    items: [
      { nom: 'Régina · Napolitaine · Végétarienne · Flammekueche', detail: '', prix: '13,80 €' },
      { nom: 'Espagnole', detail: '', prix: '15,90 €' },
      { nom: 'Poulet', detail: '', prix: '15,50 €' },
      { nom: '4 Fromages · Nordique', detail: '', prix: '16,00 €' },
      { nom: 'Burrata', detail: '', prix: '18,50 €' },
    ],
  },
  {
    id: 'glaces',
    titre: 'Glaces artisanales & coupes',
    items: [
      { nom: 'Boules au choix', detail: '12 parfums crème + 5 sorbets plein fruit — 1 boule 3,00 € / 2 boules 5,50 €', prix: '3 boules 8,00 €' },
      { nom: 'Coupes glacées', detail: 'Dame Blanche, Liégeois, Banana Split, Fleur des Îles…', prix: '9,90 – 10,90 €' },
      { nom: 'Coupes alcoolisées', detail: 'After Eight, Colonel, L’Antillaise', prix: '10,90 €' },
    ],
  },
  {
    id: 'cocktails',
    titre: 'Cocktails (~25 cl)',
    items: [
      { nom: 'Sans alcool', detail: 'Virgin Mojito, Paradise Dream, Coconut King…', prix: '6,50 €' },
      { nom: 'Avec alcool', detail: 'Mojito, Spritz, Pina Colada, Sex on the Beach…', prix: '8,90 €' },
    ],
  },
];
