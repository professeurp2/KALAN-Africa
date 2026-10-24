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
let cameraAutorisee = true;
const camera = new Camera($("video"), $("camera"), {
  observation: (obs) => envoyer({ type: "observation", ...obs }),
  geste: (nom) => envoyer({ type: "geste", nom }),
});

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
  sousTitrer.minuteries?.forEach(clearTimeout);
  sousTitrer.minuteries = [...p.children].map((span, i) => {
    const t = (cumul / total) * dureeMs;
    cumul += mots[i].length + 1;
    return setTimeout(() => span.classList.add("dit"), t);
  });
}

const NOMS_GESTES = { main_levee: "✋", pouce_haut: "👍", pouce_bas: "👎" };
let bulleMinuterie;
const GESTES = {
  seance(m) {
    tableau.seance(m);
    cameraAutorisee = m.camera_autorisee !== false;
    $("option-camera").hidden = !cameraAutorisee;
    $("puce-camera").hidden = !cameraAutorisee;
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
  geste(m) {
    const bulle = Object.assign(document.createElement("div"), { className: "geste-bulle", textContent: NOMS_GESTES[m.nom] || "✋" });
    document.querySelector(".scene").append(bulle);
    setTimeout(() => bulle.remove(), 2500);
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
    basculerCamera(false); // l'accord valait pour cette séance
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
  ws.onopen = () => camera.active && envoyer({ type: "consentement_camera", accord: true });
  ws.onclose = () => {
    $("commencer").disabled = true;
    $("commencer").textContent = "Connexion à Kalan…";
    setTimeout(connecter, 1500);
  };
}

/** Demande l'accord à chaque séance : il n'est jamais mémorisé. */
function demanderAccord() {
  const d = $("consentement");
  $("accord-famille").checked = false;
  $("accepter-camera").disabled = true;
  d.showModal();
  return new Promise((resoudre) => {
    $("accepter-camera").onclick = () => { d.close(); resoudre(true); };
    $("refuser-camera").onclick = () => { d.close(); resoudre(false); };
    d.oncancel = () => resoudre(false);
  });
}
$("accord-famille").addEventListener("change", (e) => ($("accepter-camera").disabled = !e.target.checked));

async function basculerCamera(activer) {
  const bouton = $("puce-camera");
  if (activer && (!cameraAutorisee || !(await demanderAccord()))) activer = false;
  try {
    if (activer) {
      $("camera").hidden = false;
      bouton.textContent = "📷 Caméra : chargement…";
      await camera.demarrer();
      envoyer({ type: "consentement_camera", accord: true });
    } else if (camera.active || !$("camera").hidden) {
      envoyer({ type: "consentement_camera", accord: false });
      camera.arreter();
      $("camera").hidden = true;
    }
  } catch (e) {
    envoyer({ type: "consentement_camera", accord: false });
    camera.arreter();
    $("camera").hidden = true;
    toast("Caméra indisponible : " + e.message);
  }
  bouton.textContent = camera.active ? "● Caméra active" : "📷 Caméra : non";
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
$("couper-camera").addEventListener("click", () => basculerCamera(false));

connecter();
