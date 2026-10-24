// Observation de l'élève par la caméra, comme un enseignant qui lève les yeux vers lui.
// Tout est calculé dans ce navigateur (face-api, modèles locaux) : aucune image n'est
// enregistrée ni envoyée. Seuls trois signaux partent vers Kalan : présent, attentif, perplexe.

const MODELES = "/web/vendor/face-api/model";
const EXPRESSIONS = { neutral: "neutre", happy: "content", sad: "triste", angry: "fâché",
                      fearful: "inquiet", disgusted: "gêné", surprised: "surpris" };
const FENETRE = 6; // échantillons gardés (un toutes les 500 ms → 3 s)

export class Camera {
  constructor(video, signaux, envoyer) {
    this.video = video;
    this.signaux = signaux;
    this.envoyer = envoyer;
    this.historique = [];
    this.minuterie = null;
    this.flux = null;
    this.faceapi = null;
  }

  get active() { return Boolean(this.flux); }

  async demarrer() {
    this.flux = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: false });
    this.video.srcObject = this.flux;
    if (!this.faceapi) {
      this.faceapi = await import("/web/vendor/face-api/face-api.esm.js");
      const nets = this.faceapi.nets;
      await Promise.all([nets.tinyFaceDetector.loadFromUri(MODELES),
                         nets.faceLandmark68TinyNet.loadFromUri(MODELES),
                         nets.faceExpressionNet.loadFromUri(MODELES)]);
    }
    let n = 0;
    this.minuterie = setInterval(async () => {
      const obs = await this.analyser();
      if (obs && ++n % 2 === 0) this.envoyer(obs);
    }, 500);
  }

  arreter() {
    clearInterval(this.minuterie);
    this.flux?.getTracks().forEach((t) => t.stop());
    this.flux = null;
    this.historique = [];
  }

  async analyser() {
    if (this.video.readyState < 2) return null;
    const fa = this.faceapi;
    const det = await fa.detectSingleFace(this.video, new fa.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 }))
      .withFaceLandmarks(true).withFaceExpressions();
    const e = { present: Boolean(det), attentif: false, difficulte: 0, expression: null };
    if (det) {
      e.attentif = regardeEcran(det.landmarks.positions);
      const x = det.expressions;
      e.difficulte = x.sad + x.angry + x.fearful + x.disgusted;
      e.expression = Object.entries(x).sort((a, b) => b[1] - a[1])[0][0];
    }
    this.historique = [...this.historique, e].slice(-FENETRE);
    return this.resumer();
  }

  /** Signaux lissés sur 3 s : un clignement ou un regard d'une seconde ne compte pas. */
  resumer() {
    const h = this.historique;
    const recents = h.slice(-4);
    const present = recents.filter((e) => e.present).length >= 2;
    const vus = h.filter((e) => e.present);
    const attentif = !vus.length || vus.filter((e) => e.attentif).length >= vus.length / 2;
    const perplexe = h.length === FENETRE && h.every((e) => e.present && e.difficulte > 0.5);
    const derniere = vus.at(-1)?.expression;
    this.afficher("sig-present", present ? "Présent ✓" : "Absent", !present);
    this.afficher("sig-regard", attentif ? "Regarde l'écran ✓" : "Regarde ailleurs", !attentif);
    this.afficher("sig-expression", "Expression : " + (EXPRESSIONS[derniere] || "…") + (perplexe ? " (en difficulté)" : ""), perplexe);
    return { present, attentif, perplexe };
  }

  afficher(id, texte, alerte) {
    const li = this.signaux.querySelector("#" + id);
    li.textContent = texte;
    li.classList.toggle("alerte", alerte);
  }
}

/** La tête est-elle tournée vers l'écran ? Nez centré entre les yeux, ni trop haut ni trop bas. */
function regardeEcran(p) {
  const g = p[36], d = p[45], nez = p[30];
  const ecart = Math.hypot(d.x - g.x, d.y - g.y) || 1;
  const lacet = (nez.x - (g.x + d.x) / 2) / ecart;
  const tangage = (nez.y - (g.y + d.y) / 2) / ecart;
  return Math.abs(lacet) < 0.22 && tangage > 0.3 && tangage < 0.95;
}
