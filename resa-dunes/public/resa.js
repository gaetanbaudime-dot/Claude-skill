// Réservation : disponibilités en direct + sélection de créneau. Vanilla, sans dépendance.
(function () {
  var champDate = document.getElementById('champ-date');
  var champCouverts = document.getElementById('champ-couverts');
  var champService = document.getElementById('champ-service');
  var champHeure = document.getElementById('champ-heure');
  var btnValider = document.getElementById('btn-valider');
  var note = document.getElementById('note-creneaux');
  if (!champDate || !btnValider) return;

  // Date minimale : aujourd'hui.
  var auj = new Date();
  var iso = auj.toISOString().slice(0, 10);
  champDate.min = iso;
  if (!champDate.value) champDate.value = iso;

  function majBouton() {
    var ok = champService.value && champHeure.value;
    btnValider.disabled = !ok;
    btnValider.textContent = ok
      ? 'Confirmer — ' + (champService.value === 'midi' ? 'midi ' : 'soir ') + champHeure.value
      : 'Choisissez un créneau';
  }

  function chargeDispos() {
    champService.value = '';
    champHeure.value = '';
    majBouton();
    if (!champDate.value) return;
    note.textContent = 'Vérification des disponibilités…';
    fetch('/api/disponibilites?date=' + encodeURIComponent(champDate.value) + '&couverts=' + encodeURIComponent(champCouverts.value))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ferme) {
          note.textContent = d.ferme;
          document.querySelectorAll('.creneau').forEach(function (b) { b.disabled = true; b.classList.remove('choisi'); });
          return;
        }
        var restants = 0;
        ['midi', 'soir'].forEach(function (service) {
          (d.services[service] || []).forEach(function (c) {
            var btn = document.querySelector('.creneau[data-service="' + service + '"][data-heure="' + c.heure + '"]');
            if (btn) { btn.disabled = !c.dispo; btn.classList.remove('choisi'); if (c.dispo) restants++; }
          });
        });
        note.textContent = restants
          ? 'Créneaux disponibles pour ' + champCouverts.value + ' couvert(s) — touchez pour choisir.'
          : 'Complet à cette date pour ce nombre de couverts — essayez une autre date ou appelez-nous.';
      })
      .catch(function () { note.textContent = 'Impossible de vérifier les disponibilités — le créneau sera validé à l’envoi.'; });
  }

  document.querySelectorAll('.creneau').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.creneau').forEach(function (b) { b.classList.remove('choisi'); });
      btn.classList.add('choisi');
      champService.value = btn.dataset.service;
      champHeure.value = btn.dataset.heure;
      majBouton();
    });
  });

  champDate.addEventListener('change', chargeDispos);
  champCouverts.addEventListener('change', chargeDispos);
  chargeDispos();
})();
