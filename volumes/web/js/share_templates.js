/**
 * Cémantix Solver — Modèles des messages de partage Multijoueur 1v1
 * =================================================================
 * Ce fichier centralise tous les textes et messages d'invitation partagés
 * via WhatsApp, SMS, Telegram ou le presse-papier.
 * 
 * 👉 Pour modifier ou ajouter un message, éditez directement les fonctions ci-dessous.
 */

export const DIFFICULTY_LABELS = {
  facile: "🟢 Facile (mot du quotidien)",
  moyen: "🟡 Moyen (mot standard)",
  difficile: "🌶️ Difficile (mot subtil ou technique)",
  expert: "🔴 Expert (mot complexe ou rare)",
};

export const SHARE_MESSAGES = {
  /**
   * 1. Mode « Même Mot » (mode standard)
   * Les deux joueurs s'affrontent au tour par tour sur le même mot secret.
   */
  same_word: {
    title: "⚔️ Défi Cémantix 1v1",
    buildText: ({ username, url, difficulty }) => {
      const diffLabel = DIFFICULTY_LABELS[difficulty] || DIFFICULTY_LABELS.moyen;
      const player = username || "Un ami";
      return (
        `⚔️ Défi Cémantix 1v1 !\n` +
        `${player} te défie en duel sur le même mot secret.\n` +
        `🎚️ Niveau : ${diffLabel}\n\n` +
        `Qui aura la meilleure intuition pour trouver le mot en premier ? 🎯\n\n` +
        `👉 Rejoins le salon : ${url}`
      );
    },
  },

  /**
   * 2. Mode « Mots Choisis » (mode provocation / sur mesure)
   * Chaque joueur choisit le mot secret que son adversaire doit deviner.
   */
  custom_words: {
    title: "🔥 Duel Cémantix — Tu penses pouvoir me coller ?",
    buildText: ({ username, url }) => {
      const player = username || "Un ami";
      return (
        `🔥 Duel Cémantix — Tu penses pouvoir me coller ?\n` +
        `${player} t'affronte en 1v1 où chacun choisit le mot secret de l'autre !\n\n` +
        `Je t'ai déjà préparé un piège sémantique introuvable… Voyons voir si ton mot tiendra le choc face à moi ! 😏\n\n` +
        `👉 Entre dans l'arène si tu l'oses : ${url}`
      );
    },
  },
};

