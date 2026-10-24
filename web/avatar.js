// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Lamine SACKO
// L'avatar de Kalan : la bouche suit le volume de la voix, le bras pointe le tableau,
// la tête se penche quand il écoute, les yeux montent quand il réfléchit.

const ETATS = { parle: "parle", ecoute: "t'écoute", reflechit: "réfléchit…", pret: "prêt" };

export class Avatar {
  constructor(racine) {
    this.racine = racine;
    this.bouche = racine.querySelector("#bouche-ouverte");
    this.sourire = racine.querySelector("#sourire");
    this.etiquette = racine.querySelector("#etat-prof");
    this.raf = null;
    this.ouverture = 0;
  }

  etat(nom) {
    this.racine.classList.remove("parle", "ecoute", "reflechit");
    if (nom !== "pret") this.racine.classList.add(nom);
    this.etiquette.textContent = ETATS[nom] ?? nom;
  }

  /** Anime une phrase. `enveloppe` : volume toutes les `pas` secondes. Renvoie la durée en ms. */
  parler(texte, enveloppe, pas, pointe) {
    cancelAnimationFrame(this.raf);
    this.etat("parle");
    this.racine.classList.toggle("pointe", Boolean(pointe));
    this.racine.classList.toggle("question", texte.trim().endsWith("?"));
    const debut = performance.now();
    const image = (t) => {
      const k = Math.floor((t - debut) / (pas * 1000));
      if (k >= enveloppe.length) return this.finir();
      // lissage : une bouche ne s'ouvre pas en un dixième de seconde
      this.ouverture += (enveloppe[k] - this.ouverture) * 0.45;
      this.dessinerBouche(this.ouverture);
      this.raf = requestAnimationFrame(image);
    };
    this.raf = requestAnimationFrame(image);
    return enveloppe.length * pas * 1000;
  }

  dessinerBouche(v) {
    this.bouche.setAttribute("ry", (v * 13).toFixed(1));
    this.bouche.setAttribute("rx", (13 + v * 5).toFixed(1));
    this.sourire.style.opacity = v > 0.12 ? "0" : "1";
  }

  finir() {
    cancelAnimationFrame(this.raf);
    this.ouverture = 0;
    this.dessinerBouche(0);
    this.racine.classList.remove("pointe", "question");
    this.etat("ecoute");
  }
}
