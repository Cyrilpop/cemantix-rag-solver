# 📊 Avancement — Unification du Layout, Navigation & Architecture Modulaire en 4 Briques

> **Évolution :** [2026-10 · Unification du layout & architecture modulaire](../README.md) · document 2/2
> **Compagnon de** [`01-plan.md`](01-plan.md) (référence de conception).
> **Ce fichier-ci est le seul endroit où l'état d'avancement est reporté.**
> **Branche :** `feature/ui-ux-improvements` (base `main`)
> **Dernière mise à jour :** 31/10/2026

---

## 0. Règles de tenue

1. Une ligne = un finding du plan, identifié par son **ID permanent** (`UX-01` à `UX-05`).
2. **Un finding ne passe en `✅ Fait` que si sa commande de vérification sort verte.**
3. Statuts possibles : `⬜ À faire`, `⚠️ Partiel`, `✅ Fait`, `🚫 Renoncé`.
4. Chaque changement de statut s'accompagne d'une entrée dans le **journal** (§3).

---

## 1. Tableau de bord

| Statut | Nombre | Dont 🔴 critique |
|---|---|---|
| ✅ Fait | **5** | 2 |
| ⚠️ Partiel | **0** | 0 |
| ⬜ À faire | **0** | 0 |
| **Total suivis** | **5** | **2** |

Répartition par criticité : 🔴 `UX-01` (Favicon transparent & marque), `UX-05` (Modularité 4 briques & sync conteneur) · 🟠 `UX-02` (Ordre & badges des onglets), `UX-03` (Hauteur uniforme 42px), `UX-04` (Restauration header/thème/largeur `/puzzles/`).

---

## 2. Suivi détaillé des findings

| ID | Sév. | Composant & Chantier | Statut | Résolution & Preuve |
|---|---|---|---|---|
| **UX-01** | 🔴 | Identité visuelle, Logo officiel & Header propre | `✅ Fait` | Remplacement de l'emoji générique par l'élément image `<img src="...favicon.png" alt="Cémantix Solver" class="brand-icon">` dans l'en-tête universel sur toutes les pages ; déclaration canonique des icônes de pages (`favicon.png`, `favicon.ico`, `apple-touch-icon.png`) dans `<head>` ; dimensions adaptatives et bundles CSS recompilés. |
| **UX-02** | 🟠 | Normalisation des onglets de navigation (`.nav-tabs`) | `✅ Fait` | Ordre canonique des 6 vues harmonisé sur toutes les pages (`dashboard`, `play`, `battle`, `multi`, `defi`, `archives`) ; badges *Versus IA*, *1v1 Ami*, *Live* normalisés ; classe `active` cohérente sur chaque page. |
| **UX-03** | 🟠 | Alignement dimensionnel des boutons du menu (Hauteur 42px) | `✅ Fait` | Hauteur uniforme verrouillée (`height: 42px; line-height: 1; box-sizing: border-box;`) sur `.nav-tab` dans `volumes/web/css/layout.css` et `PAGE_CSS` ; alignement centré des icônes et badges ; `tools/build_css_bundles.py --check` validé au vert. |
| **UX-04** | 🟠 | Restauration de l'en-tête, du thème, du footer et navigation sur `/puzzles/` | `✅ Fait` | Intégration de `.app-header` avec marque d'origine ; bouton `#theme-toggle` avec script de synchronisation du thème ; 6 onglets `.nav-tabs` (Archives actif) ; largeur maximale alignée à `1200px` ; intégration du footer universel `.app-footer` ; navigation par date repositionnée sous la solution avec des boutons pills ergonomiques ; fil d'ariane allégé en capsule discrète ; suppression de `interest-cohort` dans `Permissions-Policy` ; guide de déploiement VPS rédigé dans `README.md`. |
| **UX-05** | 🔴 | Architecture modulaire en 4 briques & synchronisation Python au démarrage | `✅ Fait` | Module `src/services/layout_sync.py` créé avec `render_header()` et `render_nav_tabs()` ; balisage `<!-- APP-HEADER:START -->` et `<!-- NAV-TABS:START -->` sur les 5 fichiers HTML fixes ; outil CLI `tools/sync_layout.py` ; branchement dans `ensure_seo_published()` au démarrage des conteneurs. |

---

## 3. Journal

| Date | ID | Action & preuve |
|---|---|---|
| 31/10/2026 | `UX-01` | Détourage et transparence alpha sur `favicon.png`, remplacement de l'emoji par l'image logo dans l'en-tête et déploiement du favicon sur toutes les pages statiques et dynamiques. |
| 31/10/2026 | `UX-02` | Normalisation de l'ordre des onglets sur `defi/index.html`, `play/index.html`, `multi/index.html`. |
| 31/10/2026 | `UX-04` | Réfection complète de `render_page` dans `src/services/seo_templates.py` : header, bouton thème, onglets et max-width 1200px. |
| 31/10/2026 | `UX-03` | Verrouillage `height: 42px` + `line-height: 1` sur `.nav-tab` dans `layout.css` et `PAGE_CSS`, bundles CSS recompilés. |
| 31/10/2026 | `UX-05` | Création de `layout_sync.py` et `tools/sync_layout.py`, branchement dans `ensure_seo_published()`. |
| 31/10/2026 | `UX-04` | Intégration du footer universel canonique, déplacement de la navigation par date sous la solution, pill breadcrumb discret, guide de déploiement Caddy/Docker sur VPS. |

