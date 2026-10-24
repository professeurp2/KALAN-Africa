// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Lamine SACKO
// Observation de l'élève par la caméra, comme un enseignant qui lève les yeux vers lui.
// Tout est calculé dans ce navigateur, avec des modèles copiés sur l'appareil (face-api,
// MediaPipe). Aucune image n'est enregistrée ni envoyée : seuls des signaux oui/non partent
// vers Kalan (voir docs/CONFIDENTIALITE.md), et seulement après l'accord donné pour la séance.

const FACEAPI = "/web/vendor/face-api";
const MEDIAPIPE = "/web/vendor/mediapipe";
const EXPRESSIONS = { neutral: "neutre", happy: "content", sad: "triste", angry: "fâché",
                      fearful: "inquiet", disgusted: "gêné", surprised: "surpris" };
const FENETRE = 6;          // échantillons visage gardés (un toutes les 500 ms → 3 s)
const GESTE_STABLE = 3;     // images d'affilée (≈ 0,6 s) avant de croire à un geste
const GESTE_PAUSE_MS = 4000; // un geste au plus toutes les 4 s
const NOMS_GESTES = { main_levee: "✋ Main levée", pouce_haut: "👍 J'ai compris", pouce_bas: "👎 Réexplique" };

export class Camera {
  constructor(video, panneau, { observation, geste }) {
    this.video = video;
    this.panneau = panneau;
    this.envoyerObservation = observation;
    this.envoyerGeste = geste;
    this.historique = [];
    this.minuteries = [];
    this.flux = null;
    this.faceapi = null;
    this.gestes = null;
    this.candidat = { nom: null, n: 0 };
    this.dernierGeste = 0;
    this.lumiere = document.createElement("canvas");
    this.lumiere.width = 32;
    this.lumiere.height = 24;
    // Onglet caché : on n'analyse plus rien.
    document.addEventListener("visibilitychange", () => { this.enPause = document.hidden; });
  }

  get active() { return Boolean(this.flux); }

  async demarrer() {
    // 640×480 : assez net pour lire un cahier ; l'analyse du visage travaille sur une version réduite.
    this.flux = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
    this.video.srcObject = this.flux;
    await this.chargerModeles();
    let n = 0;
    this.minuteries = [
      setInterval(async () => {
        if (this.enPause) return;
        const obs = await this.analyserVisage();
        if (obs && ++n % 2 === 0) this.envoyerObservation(obs);
      }, 500),
      setInterval(() => !this.enPause && this.analyserMains(), 200),
    ];
  }

  async chargerModeles() {
    if (!this.faceapi) {
      this.faceapi = await import(`${FACEAPI}/face-api.esm.js`);
      const nets = this.faceapi.nets;
      await Promise.all([nets.tinyFaceDetector.loadFromUri(`${FACEAPI}/model`),
                         nets.faceLandmark68TinyNet.loadFromUri(`${FACEAPI}/model`),
                         nets.faceExpressionNet.loadFromUri(`${FACEAPI}/model`)]);
    }
    if (!this.gestes) {
      try {
        const { FilesetResolver, GestureRecognizer } = await import(`${MEDIAPIPE}/vision_bundle.mjs`);
        const fichiers = await FilesetResolver.forVisionTasks(`${MEDIAPIPE}/wasm`);
        this.gestes = await GestureRecognizer.createFromOptions(fichiers, {
          baseOptions: { modelAssetPath: `${MEDIAPIPE}/gesture_recognizer.task` },
          runningMode: "VIDEO", numHands: 2,
        });
      } catch (e) {
        // Appareil trop ancien pour MediaPipe : la caméra garde le visage, sans les gestes.
        console.warn("Gestes indisponibles :", e);
        this.afficher("sig-geste", "Gestes : indisponibles", false);
      }
    }
  }

  /** Une seule image du cahier, en JPEG, uniquement quand Kalan la demande (R13). */
  photo() {
    if (!this.active || this.video.readyState < 2) return null;
    const c = document.createElement("canvas");
    c.width = 640;
    c.height = 480;
    c.getContext("2d").drawImage(this.video, 0, 0, 640, 480);
    return c.toDataURL("image/jpeg", 0.85);
  }

  arreter() {
    this.minuteries.forEach(clearInterval);
    this.flux?.getTracks().forEach((t) => t.stop());
    this.flux = null;
    this.video.srcObject = null;
    this.historique = [];
  }

  async analyserVisage() {
    if (this.video.readyState < 2) return null;
    const fa = this.faceapi;
    const visages = await fa.detectAllFaces(this.video, new fa.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 }))
      .withFaceLandmarks(true).withFaceExpressions();
    // Plusieurs visages : on observe le plus proche, et on note qu'ils sont plusieurs.
    const det = visages.sort((a, b) => b.detection.box.area - a.detection.box.area)[0];
    const e = { present: Boolean(det), plusieurs: visages.length > 1, attentif: false, difficulte: 0,
                yeuxFermes: false, baille: false, tropPres: false, expression: null, sombre: this.estSombre() };
    if (det) {
      const p = det.landmarks.positions;
      e.attentif = regardeEcran(p);
      e.yeuxFermes = (ouvertureOeil(p, 36) + ouvertureOeil(p, 42)) / 2 < 0.2;
      e.baille = ouvertureBouche(p) > 0.65;
      e.tropPres = det.detection.box.width / this.video.videoWidth > 0.55;
      const x = det.expressions;
      e.difficulte = x.sad + x.angry + x.fearful + x.disgusted;
      e.expression = Object.entries(x).sort((a, b) => b[1] - a[1])[0][0];
    }
    this.historique = [...this.historique, e].slice(-FENETRE);
    return this.resumer();
  }

  /** Luminosité moyenne de l'image, réduite à 32 × 24 points : sous 50/255, la pièce est trop sombre. */
  estSombre() {
    const ctx = this.lumiere.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(this.video, 0, 0, 32, 24);
    const d = ctx.getImageData(0, 0, 32, 24).data;
    let somme = 0;
    for (let i = 0; i < d.length; i += 4) somme += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
    return somme / (d.length / 4) < 50;
  }

  /** Signaux lissés sur 3 s : un clignement ou un regard d'une seconde ne compte pas. */
  resumer() {
    const h = this.historique;
    const present = h.slice(-4).filter((e) => e.present).length >= 2;
    const vus = h.filter((e) => e.present);
    const majorite = (f) => vus.length > 0 && vus.filter(f).length > vus.length / 2;
    const plein = h.length === FENETRE;
    const obs = {
      present,
      attentif: !vus.length || vus.filter((e) => e.attentif).length >= vus.length / 2,
      perplexe: plein && h.every((e) => e.present && e.difficulte > 0.5),
      fatigue: plein && vus.length >= 4 && (vus.filter((e) => e.yeuxFermes).length >= 4 || vus.some((e) => e.baille)),
      trop_pres: majorite((e) => e.tropPres),
      sombre: plein && h.every((e) => e.sombre),
      plusieurs: majorite((e) => e.plusieurs),
    };
    const derniere = vus.at(-1)?.expression;
    this.afficher("sig-present", present ? (obs.plusieurs ? "Plusieurs élèves ✓" : "Présent ✓") : "Absent", !present);
    this.afficher("sig-regard", obs.attentif ? "Regarde l'écran ✓" : "Regarde ailleurs", !obs.attentif);
    this.afficher("sig-expression", "Expression : " + (EXPRESSIONS[derniere] || "…") + (obs.perplexe ? " (en difficulté)" : ""), obs.perplexe);
    this.afficher("sig-fatigue", obs.fatigue ? "Semble fatigué" : "Éveillé ✓", obs.fatigue);
    this.afficher("sig-distance", obs.trop_pres ? "Trop près de l'écran" : "Distance ✓", obs.trop_pres);
    this.afficher("sig-lumiere", obs.sombre ? "Pièce trop sombre" : "Lumière ✓", obs.sombre);
    return obs;
  }

  analyserMains() {
    if (!this.gestes || this.video.readyState < 2) return;
    let r;
    try {
      r = this.gestes.recognizeForVideo(this.video, performance.now());
    } catch (e) {
      // Ne jamais échouer en silence : l'élève doit voir que les gestes ne marchent pas.
      console.warn("Gestes :", e);
      this.afficher("sig-geste", "Gestes : erreur", true);
      return;
    }
    const { nom, vu } = lireGeste(r);
    this.candidat = nom === this.candidat.nom ? { nom, n: this.candidat.n + 1 } : { nom, n: 1 };
    const maintenant = performance.now();
    if (nom && this.candidat.n === GESTE_STABLE && maintenant - this.dernierGeste > GESTE_PAUSE_MS) {
      this.dernierGeste = maintenant;
      this.afficher("sig-geste", NOMS_GESTES[nom] + " ✓", false);
      this.envoyerGeste(nom);
    } else if (maintenant - this.dernierGeste > 1500) {
      // Retour en direct : ce que la caméra voit des mains, même sans geste reconnu.
      this.afficher("sig-geste", vu, false);
    }
  }

  afficher(id, texte, alerte) {
    const li = this.panneau.querySelector("#" + id);
    if (!li) return;
    li.textContent = texte;
    li.classList.toggle("alerte", alerte);
  }
}

const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const BOUTS_DES_DOIGTS = [8, 12, 16, 20];

/**
 * Lit les mains vues par MediaPipe. Main levée : main droite (doigts au-dessus du poignet)
 * et haute dans l'image, quelle que soit sa forme (paume, un doigt, deux doigts…) ; avec
 * une webcam de portable, le poignet d'une main levée est souvent bas, voire hors champ.
 * Les pouces passent après la main levée, poing fermé exclu.
 */
export function lireGeste(r) {
  let nom = null;
  const vus = [];
  r.gestures.forEach((g, i) => {
    const cat = g[0];
    const lm = r.landmarks[i];
    if (!cat || !lm) return;
    const poignet = lm[0];
    const haut = Math.min(...BOUTS_DES_DOIGTS.map((k) => lm[k].y));
    const droite = poignet.y - haut > 0.08;
    vus.push(cat.categoryName === "None" ? "main" : cat.categoryName);
    if (cat.categoryName === "Thumb_Up" && cat.score >= 0.5) nom ??= "pouce_haut";
    else if (cat.categoryName === "Thumb_Down" && cat.score >= 0.5) nom ??= "pouce_bas";
    else if (cat.categoryName !== "Closed_Fist" && droite && haut < 0.5) nom = "main_levee";
  });
  return { nom, vu: vus.length ? "Main vue : " + vus.join(", ") : "Gestes : aucune main vue" };
}

/** La tête est-elle tournée vers l'écran ? Nez centré entre les yeux, ni trop haut ni trop bas. */
function regardeEcran(p) {
  const g = p[36], d = p[45], nez = p[30];
  const ecart = dist(g, d) || 1;
  const lacet = (nez.x - (g.x + d.x) / 2) / ecart;
  const tangage = (nez.y - (g.y + d.y) / 2) / ecart;
  return Math.abs(lacet) < 0.22 && tangage > 0.3 && tangage < 0.95;
}

/** Ouverture de l'œil (points 36-41 ou 42-47) : sous 0,2, il est fermé. */
function ouvertureOeil(p, i) {
  return (dist(p[i + 1], p[i + 5]) + dist(p[i + 2], p[i + 4])) / (2 * dist(p[i], p[i + 3]) || 1);
}

/** Ouverture de la bouche (lèvres intérieures) : au-delà de 0,65, c'est un bâillement. */
function ouvertureBouche(p) {
  return dist(p[62], p[66]) / (dist(p[60], p[64]) || 1);
}
