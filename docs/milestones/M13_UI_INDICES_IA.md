# Jalon M13 — Affichage des Indices IA Gemini sur la Page Mot du Jour avec Double Commutateur Dynamique

**Dépôt :** `Cyrilpop/cemantix-rag-solver`  
**Branche visée :** `feature/m13-ui-indices-ia` (base `main`)  
**Statut :** 🟢 Validé  
**Périmètre de réalisation :** `src/services/seo_hubs.py`, `src/services/seo_templates.py`, `src/services/seo_archives.py`, `volumes/web/css/`, `tests/test_ui_indices_ia.py`, `docs/roadmap/`, `README.md`, `CHANGELOG.md`.  
**Périmètre exclu pour ce jalon :** Aucune modification de l'algorithme RAG ni du modèle de données (schémas SQL figés en M12).  
**Suite de validation requise :** Tests unitaires sous Docker Python 3.12, `tools/check_docs.py`, `tools/check_seo.py`, `tools/build_css_bundles.py --check`.  
**Règle d'or environnement :** L'intégralité du projet s'exécute sous Docker. Aucune commande Python, pip ou test ne doit être exécutée directement sur la machine hôte.

---

## 1. Objectifs Métier et Expérience Utilisateur (UX)

Le **Jalon M12** a mis en place la génération automatique et la persistance relationnelle d'indices gradués IA par Google Gemini (`daily_puzzle_ai_hints`).  
Le **Jalon M13** concrétise cette avancée côté interface utilisateur en enrichissant la page hub à forte audience **`/mot-du-jour/`** (et les pages d'archives quotidiennes associées) d'un système de consultation d'indices intelligent, interactif et respectueux du plaisir de jeu (zéro spoiler involontaire).

### 1.1 Exigences Fonctionnelles Clés

1. **Double Commutateur Dynamique (Switches UI) :**
   - **Commutateur 1 — Source d'Indices :**
     - Option A : `🤖 Indices IA (Google Gemini)` (**active par défaut**).
     - Option B : `🌡️ Indices Sémantiques (Solveur RAG / Mots calculés)`.
     - *Repli gracieux :* Si un puzzle ne possède pas encore d'indices IA en base, le commutateur bascule automatiquement sur les indices calculés du solveur.
   - **Commutateur 2 — Format de Rendu IA (disponible uniquement en mode IA) :**
     - Option A : `📝 Phrases d'énigme` (**active par défaut**) — phrases évocatrices et stimulantes.
     - Option B : `🎯 Mots repères` — mots uniques balisant l'espace sémantique.

2. **Masquage Absolu par Défaut (Politique Anti-Spoiler) :**
   - Aucun indice (qu'il s'agisse de la phrase IA, du mot IA ou des mots du solveur) n'apparaît en clair au chargement initial de la page.
   - Chaque indice est encapsulé dans une zone floutée/masquée (`filter: blur(8px)`, classe `.spoiler-hidden`) ou un accordéon interactif (`<details class="reveal">`) exigeant une action explicite du joueur pour être révélé.
   - Bouton d'action ou clic direct permettant de révéler l'indice choisi à la demande.

3. **Ordonnancement Sémantique & Graduation en Mode IA :**
   - En mode IA, la numérotation suit la règle d'éloignement progressif :
     - **Indice #1 (Poids 0.33) : Le plus éloigné** — Toile de fond abstraite, univers culturel ou époque historique (Zone Froide ~20%).
     - **Indice #2 (Poids 0.66) : Intermédiaire** — Vocation, usage courant ou fonction sociétale (Zone Tiède/Chaude ~45%).
     - **Indice #3 (Poids 1.00) : Proche / Le Déclic** — Analogie déterminante ou composant emblématique (Zone Brûlante / Top 1000).

4. **Performance, Accessibilité & SEO :**
   - Rendu hybride SSR : contenu pré-généré dans le HTML avec attributs ARIA complets (`role="tab"`, `aria-selected`, `aria-controls`).
   - Interaction fluide sans aucun rechargement de page (JavaScript vanilla ultra-léger ou contrôle CSS natif).
   - Aucun impact négatif sur le Cumulative Layout Shift (CLS = 0) et score PageSpeed maintenu à 100/100.

---

## 2. Spécification Technique & Architecture

### 2.1 Extraction des Données Backend (`src/services/seo_hubs.py`)

Lors de la construction de la page `/mot-du-jour/` (via `build_mot_du_jour_page`), le service injecte les indices IA récupérés depuis la base :

```python
from src.db import get_daily_ai_hints

# Récupération des indices IA pour la date du puzzle
ai_hints = get_daily_ai_hints(puzzle_date) if puzzle_date else []
# ai_hints contient une liste de 3 dictionnaires ordonnés par hint_level ASC :
# [{"hint_level": 1, "weight": 0.33, "hint_word": "...", "hint_phrase": "..."}, ...]
```

### 2.2 Structure HTML Cible (Composant d'Indices Hybride)

```html
<section class="card hints-section" id="hints-hub">
  <h2>💡 Indices du mot du jour</h2>
  <p class="hints-intro">
    Besoin d'un coup de pouce sans gâcher votre partie ? Choisissez votre type d'aide.
    Tous les indices sont masqués par défaut pour éviter tout spoiler.
  </p>

  <!-- Commutateur 1 : Source d'indices -->
  <div class="hints-toolbar">
    <div class="segmented-control" role="tablist" aria-label="Source des indices">
      <button type="button" class="segment-btn active" id="tab-hints-ai" role="tab" aria-selected="true" aria-controls="panel-hints-ai">
        <span class="btn-icon">🤖</span> Indices IA (Gemini)
      </button>
      <button type="button" class="segment-btn" id="tab-hints-rag" role="tab" aria-selected="false" aria-controls="panel-hints-rag">
        <span class="btn-icon">🌡️</span> Mots du solveur RAG
      </button>
    </div>

    <!-- Commutateur 2 : Format d'indice IA (affiché si IA actif) -->
    <div class="segmented-control format-control" id="hints-ai-format" role="radiogroup" aria-label="Format des indices IA">
      <button type="button" class="segment-btn active" id="btn-format-phrase" role="radio" aria-checked="true">
        <span class="btn-icon">📝</span> Énigmes (Phrases)
      </button>
      <button type="button" class="segment-btn" id="btn-format-word" role="radio" aria-checked="false">
        <span class="btn-icon">🎯</span> Mots repères
      </button>
    </div>
  </div>

  <!-- Panneau 1 : Indices IA (par défaut) -->
  <div class="hints-panel active" id="panel-hints-ai" role="tabpanel" aria-labelledby="tab-hints-ai">
    <div class="ai-hints-grid">
      <!-- Carte Indice #1 (Le plus éloigné) -->
      <article class="ai-hint-card tier-cold" data-level="1">
        <header class="ai-hint-header">
          <span class="hint-badge">Indice #1 · Éloigné</span>
          <span class="hint-weight">Similarité ~20%</span>
        </header>
        <div class="ai-hint-content spoiler-box">
          <div class="hint-view-phrase active">
            <span class="spoiler-text" data-spoiler="true">« Phrase d'ambiance lointaine... »</span>
          </div>
          <div class="hint-view-word">
            <span class="spoiler-text" data-spoiler="true">MotRepère</span>
          </div>
          <button type="button" class="btn-reveal" aria-label="Révéler l'indice 1">👁️ Révéler l'indice</button>
        </div>
      </article>

      <!-- Carte Indice #2 (Intermédiaire) -->
      <article class="ai-hint-card tier-warm" data-level="2">
        <header class="ai-hint-header">
          <span class="hint-badge">Indice #2 · Intermédiaire</span>
          <span class="hint-weight">Similarité ~45%</span>
        </header>
        <div class="ai-hint-content spoiler-box">
          <div class="hint-view-phrase active">
            <span class="spoiler-text" data-spoiler="true">« Phrase décrivant l'usage... »</span>
          </div>
          <div class="hint-view-word">
            <span class="spoiler-text" data-spoiler="true">MotFonction</span>
          </div>
          <button type="button" class="btn-reveal" aria-label="Révéler l'indice 2">👁️ Révéler l'indice</button>
        </div>
      </article>

      <!-- Carte Indice #3 (Le Déclic / Proche) -->
      <article class="ai-hint-card tier-fire" data-level="3">
        <header class="ai-hint-header">
          <span class="hint-badge">Indice #3 · Proche</span>
          <span class="hint-weight">Zone brûlante</span>
        </header>
        <div class="ai-hint-content spoiler-box">
          <div class="hint-view-phrase active">
            <span class="spoiler-text" data-spoiler="true">« Analogie forte ou composant distinctif... »</span>
          </div>
          <div class="hint-view-word">
            <span class="spoiler-text" data-spoiler="true">MotDéclic</span>
          </div>
          <button type="button" class="btn-reveal" aria-label="Révéler l'indice 3">👁️ Révéler l'indice</button>
        </div>
      </article>
    </div>
  </div>

  <!-- Panneau 2 : Mots calculés du solveur RAG (secondaire) -->
  <div class="hints-panel" id="panel-hints-rag" role="tabpanel" aria-labelledby="tab-hints-rag" hidden>
    <div class="table-responsive">
      <table>
        <!-- Tableau des 10 mots les plus proches du solveur -->
      </table>
    </div>
  </div>
</section>
```

---

## 3. Plan de Découpage des Tâches (Findings UI-01 à UI-05)

| ID | Domaine | Intitulé & Description |
|---|---|---|
| **UI-01** | Backend / Services | **Injection des indices IA dans le rendu de `mot-du-jour`** : Appel de `get_daily_ai_hints()` dans `src/services/seo_hubs.py`, extraction sécurisée et préparation des structures de données (fallback gracieux si indices absents). |
| **UI-02** | Template & HTML | **Structure HTML du composant d'indices avec double commutateur** : Rendu des contrôles segmentés accessibles, conteneurs de panneaux IA / RAG et cartes d'indices ordonnées (#1 = le plus éloigné). |
| **UI-03** | Frontend / Script | **Logique interactive JavaScript vanilla** : Gestion des événements de commutation de source (IA vs RAG), de format (Phrase vs Mot), et bascule individuelle / globale des spoilers sans rechargement. |
| **UI-04** | Style CSS & Design System | **Styles des commutateurs, cartes et effets spoiler-blur** : Design responsive adapté au mode sombre et clair, alignement des hauteurs et animations fluides sans impact CLS. |
| **UI-05** | Qualité & Non-Régression | **Suite de tests unitaires et contrôles d'intégrité** : Création de `tests/test_ui_indices_ia.py`, validation sous conteneur Docker Python 3.12 (413+ tests), `check_docs.py`, `check_seo.py`, `build_css_bundles.py --check`. |

---

## 4. Critères d'Acceptation Exécutables

1. **Par défaut, la source active est l'IA :** À l'ouverture de la page `/mot-du-jour/`, le panneau des indices IA est sélectionné et affiché par défaut si les données existent.
2. **Par défaut, le format actif est la Phrase :** Les phrases d'énigme sont visibles (sous masque spoiler), et le switch permet de basculer instantanément sur les mots repères.
3. **Protection anti-spoiler totale :** Aucun mot ni phrase d'indice n'est lisible sans un clic de démasquage explicite.
4. **Graduation respectée :** L'indice `#1` est obligatoirement l'indice de niveau 1 (poids 0.33, le plus éloigné / froid), `#2` l'intermédiaire, `#3` le plus proche.
5. **Repli RAG fonctionnel :** Le commutateur permet de basculer sur le tableau classique des mots calculés du solveur, et si les indices IA sont inexistants, le mode RAG s'affiche sans erreur.
6. **Contrôles de validation 100% verts :** `check_docs.py`, `check_seo.py`, `build_css_bundles.py --check` et tests unitaires Docker.
