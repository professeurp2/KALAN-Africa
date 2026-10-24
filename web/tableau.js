// La diapositive : elle avance toute seule avec le cours. Les points apparaissent au fil
// de la parole et le schéma s'allume sur l'élément dont Kalan parle (R7).

const $ = (id) => document.getElementById(id);

export class Tableau {
  constructor() {
    this.points = [];
    this.svg = null;
    this.elements = {};
    this.pointeActuel = null;
    addEventListener("resize", () => this.placerLaser());
  }

  async seance({ chapitre, lecons, schema, elements }) {
    $("chapitre").textContent = chapitre;
    this.lecons = lecons;
    this.elements = elements || {};
    this.progression(0);
    if (schema) {
      $("schema-svg").innerHTML = await (await fetch(schema)).text();
      this.svg = $("schema-svg").querySelector("svg");
      this.svg.removeAttribute("width");
      this.svg.removeAttribute("height");
    } else {
      $("schema").hidden = true;
    }
  }

  progression(numero) {
    const p = $("progression");
    p.replaceChildren();
    (this.lecons || []).forEach((_, i) => {
      const pas = document.createElement("span");
      pas.className = "pas" + (i + 1 < numero ? " fait" : i + 1 === numero ? " actuel" : "");
      p.append(pas);
    });
    if (numero) p.append(Object.assign(document.createElement("span"), { textContent: `Leçon ${numero} / ${this.lecons.length}` }));
  }

  lecon({ numero, titre, citation, points }) {
    this.progression(numero);
    const h1 = $("titre-lecon");
    h1.textContent = titre.replace(/^Leçon \d+ — /, "");
    h1.classList.remove("entre");
    void h1.offsetWidth; // relancer l'animation d'entrée
    h1.classList.add("entre");
    this.points = points;
    $("points").replaceChildren(...points.map((t) => Object.assign(document.createElement("li"), { textContent: t })));
    $("source").textContent = "📖 " + citation;
    this.pointer(null);
  }

  dit(texte, pointe) {
    const i = this.points.indexOf(texte);
    if (i >= 0) {
      [...$("points").children].forEach((li, k) => {
        li.classList.toggle("vu", k < i);
        li.classList.toggle("actuel", k === i);
      });
    }
    this.pointer(pointe);
  }

  pointer(id) {
    this.pointeActuel = id;
    if (!this.svg) return;
    this.svg.querySelectorAll("g.actif").forEach((g) => g.classList.remove("actif"));
    const g = id && this.svg.querySelector("#" + CSS.escape(id));
    this.svg.classList.toggle("focus", Boolean(g));
    $("schema-legende").textContent = g ? "👉 " + (this.elements[id] || id) : "";
    if (g) g.classList.add("actif");
    this.placerLaser();
  }

  placerLaser() {
    const laser = $("laser");
    const g = this.pointeActuel && this.svg?.querySelector("#" + CSS.escape(this.pointeActuel));
    if (!g) { laser.hidden = true; return; }
    const cadre = $("schema").getBoundingClientRect();
    const r = g.getBoundingClientRect();
    laser.hidden = false;
    laser.style.left = `${r.left + r.width / 2 - cadre.left}px`;
    laser.style.top = `${r.top + r.height / 2 - cadre.top}px`;
  }

  source(texte) {
    $("source").textContent = "📖 " + texte;
  }
}
