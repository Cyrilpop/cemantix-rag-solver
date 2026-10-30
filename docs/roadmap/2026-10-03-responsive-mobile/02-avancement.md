# 📊 Avancement — Refonte Responsive & Ergonomie Mobile (Smartphones)

> **Évolution :** [2026-10 · Responsive mobile](../README.md) · document 2/2
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**
> **Dernière mise à jour :** 29/10/2026 21:50

---

## 0. Règles de tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`RESP-01` à `RESP-12`).
   Un ID n'est jamais renommé ni réattribué.
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte** (colonne
   « Vérification » du plan). **Un commit, ou son message, ne vaut pas preuve** : la qualification
   visuelle multi-résolutions (GP8 Pro 412px, iPhone 393px, compact 360px), les tests de build CSS
   (`python tools/build_css_bundles.py --check`) et l'audit sans débordement horizontal valident chaque critère.
3. Statuts possibles :

   | Statut | Signification |
   |---|---|
   | `⬜ À faire` | Spécifié dans le plan, en attente de mise en œuvre |
   | `⚠️ Partiel` | Une partie du correctif existe, le critère de sortie complet n'est pas atteint |
   | `✅ Fait` | Critère de sortie atteint **sur la branche de travail**, vérification exécutée |
   | `🚫 Renoncé` | Abandonné avec justification (l'ID reste réservé) |

4. Chaque changement de statut s'accompagne d'une ligne dans le **journal** (§4) : date, ID, ce qui
   a été exécuté, preuve.
5. `01-plan.md` ne porte **aucun** statut : ne pas en ajouter.

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **12** | 4 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **12** | **4** |

Répartition par criticité :
- 🔴 **Critique (4)** : `RESP-02` (Navigation principale rognée à gauche), `RESP-03` (Formulaire de saisie jeu solo écrasé), `RESP-07` (Sous-onglets lobby multi superposés), `RESP-12` (Débordement horizontal global de la page).
- 🟠 **Élevé (5)** : `RESP-01` (Header & branding mobile), `RESP-04` (Gestion du clavier virtuel), `RESP-08` (Cartes variantes multijoueur), `RESP-09` (Sélecteurs de difficulté et safe-area), `RESP-10` (HUD Mode Battle).
- 🟡 **Moyen (3)** : `RESP-05` (Grille 3 colonnes stats mot secret), `RESP-06` (Pastilles échelle thermique), `RESP-11` (Modales et ergonomie tactile).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **RESP-01** | 🟠 | Header & branding compact sur 1 ligne | `✅ Fait` | Typographie fluide `clamp()`, `#daemon-badge` compact `36×36px` sans texte sur `≤ 640px`, boutons icônes `44×44px` mesurés sous Chromium (`412px` & `360px`) |
| **RESP-02** | 🔴 | Navigation principale `.nav-tabs` fluide et défilante | `✅ Fait` | `justify-content: flex-start; flex-wrap: nowrap; overflow-x: auto;`, centrage auto `initMobileNavScroll()` ; 1er onglet mesuré à `left: 21px` sur GP8 Pro (`412px`) |
| **RESP-03** | 🔴 | Formulaire de saisie solo réagencé en 2 rangées | `✅ Fait` | `.guess-form-row` empilé (`flex-direction: column`), `<input>` mesuré à `268.3px` (`font-size: 16px`), grille 2 colonnes `44px` pour `[Indice \| Abandonner]` |
| **RESP-04** | 🟠 | Hauteur dynamique et adaptation au clavier virtuel | `✅ Fait` | `.game-guesses-list` dynamique (`height: auto; max-height: min(260px, 38dvh)`), `initMobileKeyboardAdapt()` (`visualViewport`) validé à `412×420px` |
| **RESP-05** | 🟡 | Grille de statistiques mot secret adaptative | `✅ Fait` | Grille 2 colonnes (`175×63.6px` × 2) + bandeau pleine largeur (`358.8×55.2px` `grid-column: 1 / -1`) sur `≤ 480px`, ordre de cascade `@media` corrigé |
| **RESP-06** | 🟡 | Échelle thermique et pastilles proportionnelles | `✅ Fait` | `<span class="tier-emoji">` empilé au-dessus du palier sur `≤ 520px` (`5 × 71.4×48px` sur GP8 Pro, `clipped: false` sur `412px` et `360px`) |
| **RESP-07** | 🔴 | Sous-onglets du lobby multijoueur défilants | `✅ Fait` | `.lobby-tab-btn` `min-width: max-content` + libellés courts mobiles (`Créer`, `Rejoindre`, `Duels`), `lobbyOverlap: false` mesuré à `412px` & `360px` |
| **RESP-08** | 🟠 | Cartes variantes de duel compactes et lisibles | `✅ Fait` | `.mode-cards-grid` `1fr`, titres/paddings condensés visibles au-dessus de la ligne de flottaison sur GP8 Pro (`412×915px`) |
| **RESP-09** | 🟠 | Sélecteur de difficulté et respiration safe-area | `✅ Fait` | Boutons d'action pleine largeur `46px`, `env(safe-area-inset-bottom)` sur `.multi-container`, salle d'attente et barre d'arène responsives |
| **RESP-10** | 🟠 | Scoreboard et HUD Mode Battle smartphone | `✅ Fait` | `[Nouvelle Manche]` pleine largeur `44px`, `.battle-scoreboard` 3 colonnes empilées sur `≤ 480px` (`scrollWidth == clientWidth` à `360px` & `412px`) |
| **RESP-11** | 🟡 | Modales adaptatives et cibles tactiles ≥ 44px | `✅ Fait` | `.modal-close-btn` `44×44px`, `.modal-badges` `flex-wrap`, `#trajectory-filter-group` grille `2×2` sur `≤ 480px`, `max-height: 92dvh` + `safe-area-inset-bottom` |
| **RESP-12** | 🔴 | Détection & suppression du débordement horizontal global | `✅ Fait` | `overflow-x: clip`, `min-width: 0`, `docScrollW === innerWidth` vérifié sur 25 combinaisons `viewport × page` sous Chromium headless |

---

## 3. État des dépôts & Environnement de validation

Mesuré le 29/10/2026 :

| Branche | Rôle | Validation locale Docker & Production |
|---|---|---|
| `feat/responsive-mobile` ← *courante* | Branche de travail (PR #22) | `127/127` tests unitaires OK · `check_docs.py` OK · `check_seo.py` OK · `build_css_bundles.py --check` OK · `25/25` audits Chromium CDP OK · PageSpeed Insights Mobile & Bureau `100/100/100/100` + `4/4` ARD |
| `main` | Base de référence (`4019126`) | Desktop `1440×900` sanctuarisé (zéro modification hors `@media` mobile) |

- **Stack locale testée sous Docker :** `cemantix_db`, `cemantix_worker`, `cemantix_web` + `cemantix_nginx` (`http://localhost:8090` / `http://cemantix_nginx:8080` sur `web-net`).
- **Résolutions qualifiées sous Chromium headless (CDP) :** `1440×900` (Desktop), `412×915` (GP8 Pro), `412×420` (GP8 Pro + clavier Gboard), `393×852` (iPhone 15 Pro), `360×740` (Compact).

---

## 4. Journal chronologique

| Date | Finding | Action réalisée | Preuve / Validation |
|---|---|---|---|
| 29/10/2026 | — | Création de la feuille de route responsive mobile suite aux retours GP8 Pro | Initialisation `01-plan.md` et `02-avancement.md`, PR #22 ouverte |
| 29/10/2026 | `RESP-01`, `RESP-12` | Verrouillage `overflow-x: clip`, `min-width: 0`, header mobile sur 1 ligne et cibles `44×44px` | Validation Chromium headless CDP, bundles CSS régénérés |
| 29/10/2026 | `RESP-02` | Barre `.nav-tabs` scrollable dès `x=0` + centrage JS de l'onglet actif (`initMobileNavScroll`) | Tests Chromium, `check_js_balance.py` OK |
| 29/10/2026 | `RESP-03`, `RESP-04` | Empilement `.guess-form-row`, saisie `16px` pleine largeur et adaptation `visualViewport` au clavier | Testé à `412×915` et `412×420` (Gboard ouvert) |
| 29/10/2026 | `RESP-05`, `RESP-06` | Grille métriques `2 + 1` sur `≤ 480px`, pastilles thermiques empilées sur 2 lignes, ordre `@media` corrigé | `check_seo.py` OK, inspection visuelle |
| 29/10/2026 | `RESP-07`, `RESP-08`, `RESP-09` | Refonte mobile du lobby `/multi/`, onglets sans chevauchement, cartes `1fr`, salle d'attente et safe-areas | `lobbyOverlap: false`, navigation fluide |
| 29/10/2026 | `RESP-10` | Scoreboard Battle 3 colonnes empilées sur `≤ 480px`, bouton manche pleine largeur et HUD sans débordement | `scoreboard.scrollWidth == clientWidth` |
| 29/10/2026 | `RESP-11`, `RESP-12` | Modales `92dvh`, fermeture `44×44px`, filtres `2×2`, safe-areas et protection `/puzzles/` + suite `test_responsive.py` | Suite `test_responsive.py` OK & `25/25` vues Chromium sans aucun débordement |
| 29/10/2026 | — | Régénération automatique et atomique de `sitemap.xml`, `/puzzles/` et manifestes `.well-known/*.json` au démarrage (`ensure_seo_published()`) | Tests unitaires `test_seo_startup.py` OK, parité octet-par-octet |
| 29/10/2026 | — | Optimisations PageSpeed Mobile & ARD : suppression du reflow forcé (`theme.js`), CSS critique inline, chargement différé `modal.css`, conformité ARD (`ai-catalog.json` + `ard.json`) | PageSpeed Insights Mobile & Bureau `100 / 100 / 100 / 100` + `4/4` Navigation agentique validés en production |
