// Écran de classe : reçoit les évènements du cours (kalan/web.py) et les répartit
// entre l'avatar, le tableau, les sous-titres et la caméra.
// Pour ajouter une fonctionnalité (révision, tableau de bord enseignant…), écouter
// un nouveau type d'évènement dans GESTES et lui donner son propre module.

import { Avatar } from "./avatar.js";
import { Tableau } from "./tableau.js";
import { Camera } from "./camera.js";

const $ = (id) => document.getElementById(id);
const avatar = new Avatar(document.querySelector(".prof"));
const tableau = new Tableau();
let ws;
const camera = new Camera($("video"), $("camera"), (obs) => envoyer({ type: "observation", ...obs }));

function envoyer(msg) {
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

function toast(texte, ms = 4000) {
  const t = $("toast");
  t.textContent = texte;
  t.hidden = false;
  clearTimeout(toast.minuterie);
  toast.minuterie = setTimeout(() => (t.hidden = true), ms);
}

/** Sous-titres : les mots s'allument au rythme de la voix. */
function sousTitrer(texte, dureeMs) {
  const p = $("sous-titre");
  const mots = texte.split(/\s+/);
  p.replaceChildren(...mots.map((m) => Object.assign(document.createElement("span"), { className: "mot", textContent: m + " " })));
  const total = texte.length || 1;
  let cumul = 0;
  clearTimeout(sousTitrer.fin);
  sousTitrer.minuteries?.forEach(clearTimeout);
  sousTitrer.minuteries = [...p.children].map((span, i) => {
    const t = (cumul / total) * dureeMs;
    cumul += mots[i].length + 1;
    return setTimeout(() => span.classList.add("dit"), t);
  });
}

let bulleMinuterie;
const GESTES = {
  seance(m) {
    tableau.seance(m);
    $("accueil-chapitre").textContent = m.chapitre;
    $("commencer").disabled = false;
    $("commencer").textContent = "Commencer le cours";
  },
  lecon(m) {
    $("accueil").hidden = true; // page rouverte en plein cours
    tableau.lecon(m);
  },
  dit(m) {
    const duree = avatar.parler(m.texte, m.enveloppe, m.pas, m.pointe);
    tableau.dit(m.texte, m.pointe);
    sousTitrer(m.texte, duree);
  },
  coupe() {
    avatar.finir();
    sousTitrer.minuteries?.forEach(clearTimeout);
  },
  eleve(m) {
    const b = $("eleve");
    b.textContent = m.texte;
    b.hidden = false;
    avatar.etat("reflechit");
    clearTimeout(bulleMinuterie);
    bulleMinuterie = setTimeout(() => (b.hidden = true), 12000);
  },
  source: (m) => tableau.source(m.texte),
  fin() {
    avatar.etat("pret");
    toast("Fin du cours. Bravo !", 6000);
    $("commencer").textContent = "Recommencer le cours";
    $("accueil").hidden = false;
  },
  erreur(m) {
    avatar.etat("pret");
    toast("⚠️ " + m.texte + " — le LLM local tourne-t-il ? (ollama serve)", 10000);
  },
};

function connecter() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    GESTES[m.type]?.(m);
  };
  ws.onclose = () => {
    $("commencer").disabled = true;
    $("commencer").textContent = "Connexion à Kalan…";
    setTimeout(connecter, 1500);
  };
}

async function basculerCamera(activer) {
  const bouton = $("puce-camera");
  try {
    if (activer) {
      $("camera").hidden = false;
      bouton.textContent = "📷 Caméra : chargement…";
      await camera.demarrer();
    } else {
      camera.arreter();
      $("camera").hidden = true;
    }
  } catch (e) {
    camera.arreter();
    $("camera").hidden = true;
    toast("Caméra indisponible : " + e.message);
  }
  bouton.textContent = "📷 Caméra : " + (camera.active ? "oui" : "non");
  bouton.classList.toggle("actif", camera.active);
}

$("commencer").addEventListener("click", () => {
  $("accueil").hidden = true;
  $("puce-micro").textContent = "🎤 Micro ouvert";
  $("puce-micro").classList.add("actif");
  avatar.etat("reflechit");
  envoyer({ type: "commencer" });
  if ($("opt-camera").checked && !camera.active) basculerCamera(true);
});
$("puce-camera").addEventListener("click", () => basculerCamera(!camera.active));

connecter();
