"""
Cémantix Solver — Pages Hub Thématiques SEO (seo_hubs)
=====================================================
Génère les deux pages hub côté serveur ciblant les requêtes dominantes
Google Cémantix : « mot du jour » (/mot-du-jour/) et « méthode & indices » (/methode/).
"""
from html import escape
from typing import Optional

from .seo_templates import (
    METHODE_DIRNAME,
    MOT_DU_JOUR_DIRNAME,
    SITE_ORIGIN,
    _clue_rows,
    _json_ld_block,
    _rel_index,
    archive_anchor,
    format_clue_words_list,
    format_date_fr,
    format_duration_fr,
    hub_url,
    render_page,
)

_HUB_FAQ = (
    (
        "Quel est le mot du jour Cémantix ?",
        "Le mot secret est volontairement masqué tant que vous ne le demandez pas : c'est "
        "le principe anti-spoiler du site. Dépliez le bloc « Afficher la solution » pour le "
        "découvrir, ou utilisez les indices ci-dessus pour jouer sans révélation. Le "
        "Cémantix est renouvelé chaque nuit à minuit, heure de Paris.",
    ),
    (
        "Comment lire les indices du Cémantix du jour ?",
        "Chaque mot testé reçoit une similarité exprimée en pour mille : le mot secret vaut "
        "exactement 1000 ‰. Au-delà de 500 ‰ vous êtes dans le Top 1000 des mots les plus "
        "proches et le palier devient chaud ; sous 200 ‰, le champ lexical exploré est "
        "étranger à la cible. La méthode complète est détaillée dans le guide des indices.",
    ),
    (
        "Quels synonymes tester au Cémantix ?",
        "Partez du mot le plus chaud déjà obtenu, puis explorez ses synonymes, ses "
        "antonymes, sa famille grammaticale (pluriel, verbe, adjectif) et son champ lexical "
        "concret : objets, lieux, métiers, actions. Le moteur est entraîné sur frWac, un "
        "corpus de presse française : les associations les plus fréquentes dans la presse "
        "sont aussi les plus payantes en jeu.",
    ),
    (
        "Le Cémantix du jour a-t-il une solution unique ?",
        "Oui : un seul mot secret est publié chaque jour par Certitudes, l'éditeur du jeu. "
        "En revanche, il existe une infinité de trajectoires pour l'atteindre ; le nombre de "
        "coups affiché ici est celui du solveur automatique, pas un record à battre.",
    ),
)


def _faq_items_html(faq) -> str:
    """Accordéon HTML de la FAQ (aucun JavaScript : balises `<details>` natives)."""
    return "\n".join(
        f'      <details class="reveal">\n'
        f"        <summary>{escape(question)}</summary>\n"
        f"        <p>{escape(answer)}</p>\n"
        f"      </details>"
        for question, answer in faq
    )


def _faq_json_ld(faq, anchor: str) -> dict:
    """Bloc `FAQPage` Schema.org — c'est lui qui déclenche les résultats enrichis."""
    return {
        "@type": "FAQPage",
        "@id": f"{anchor}#faq",
        "inLanguage": "fr-FR",
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
            for question, answer in faq
        ],
    }


def _hub_breadcrumbs(label: str) -> str:
    """Fil d'Ariane d'une page hub (profondeur 1 : `../` mène à l'accueil)."""
    return (
        f'<a href="{escape(_rel_index(""), quote=True)}">Accueil</a>'
        f'<span class="crumb-sep">›</span>'
        f"<span>{escape(label)}</span>"
    )


def _hub_breadcrumb_json_ld(label: str, canonical: str) -> dict:
    return {
        "@type": "BreadcrumbList",
        "@id": f"{canonical}#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE_ORIGIN}/"},
            {"@type": "ListItem", "position": 2, "name": label, "item": canonical},
        ],
    }


def _render_hub_page(*, titre, description, canonical, json_ld, entry, entries, date_fr) -> str:
    """Corps de la page hub « mot du jour » : résumé, indices, solution, FAQ, archives."""
    if entry:
        puzzle = entry.get("puzzle")
        word = str(entry.get("word") or "").strip()
        tries = entry.get("tries")
        duration = format_duration_fr(entry.get("duration_seconds"))
        guesses = [g for g in (entry.get("top_guesses") or []) if str(g.get("word", "")) != "••••••••"]
        source_label = "Hybride RAG + LLM" if entry.get("source") == "llm" else "100 % RAG pur"
        puzzle_label = f"Puzzle #{puzzle}" if puzzle else "Puzzle du jour"
        meta_items = [
            f"<li>{escape(puzzle_label)}</li>",
            f"<li>Mot du jour du <strong>{escape(date_fr)}</strong></li>",
            f"<li>Trouvé en <strong>{escape(str(tries or '--'))} coups</strong></li>",
            f"<li>Durée de calcul&nbsp;: <strong>{escape(duration)}</strong></li>",
            f"<li>Méthode&nbsp;: <strong>{escape(source_label)}</strong></li>",
        ]
        win_badge = (
            '<span class="badge badge-win">✓ Puzzle résolu</span>'
            if entry.get("win") is True
            else '<span class="badge">⏳ Puzzle non résolu</span>'
        )
        resume = (
            f"Le {escape(date_fr)}, le solveur a publié la trajectoire complète du "
            f"{escape(puzzle_label)} : les dix mots les plus proches du mot secret, leur "
            f"score en degrés Celsius et leur similarité en pour mille, puis la solution, "
            f"gardée derrière un bloc dépliable pour ne spoiler personne."
        )
        clues_html = f"""      <section class="card">
        <h2>🌡️ Les {min(len(guesses), 10)} indices du mot du jour</h2>
        <p>Le thermomètre sémantique officiel : plus le score en pour mille (‰) approche
        1000, plus le mot est proche du mot secret, qui vaut exactement 1000 ‰.
        <a href="{escape(_rel_index('methode/'), quote=True)}">Comment lire ces indices&nbsp;?</a></p>
        <table>
          <caption>Indices du {escape(date_fr)}, mesurés par le solveur RAG</caption>
          <thead>
            <tr><th scope="col">#</th><th scope="col">Mot</th><th scope="col">Score</th><th scope="col">Similarité</th></tr>
          </thead>
          <tbody>
{_clue_rows(guesses)}
          </tbody>
        </table>
      </section>
""" if guesses else ""
        solution_html = f"""      <details class="reveal">
        <summary>👁️ Afficher la solution du Cémantix du {escape(date_fr)}</summary>
        <p class="reveal-word">{escape(word.upper())}</p>
        <p>Le solveur a atteint ce mot en {escape(str(tries or '--'))} coups
        ({escape(duration)}) grâce à la régression Ridge sur l'espace vectoriel frWac. Les
        mots du jour déjà résolus sont conservés dans les
        <a href="{escape(_rel_index('puzzles/'), quote=True)}">archives Cémantix par date</a>.</p>
      </details>
""" if word else ""
    else:
        win_badge = '<span class="badge">⏳ Première publication à minuit</span>'
        resume = (
            "Le solveur résout automatiquement le Cémantix chaque nuit à minuit (heure de "
            "Paris) et publie ici le mot du jour, ses indices et sa solution. En attendant, "
            'les puzzles déjà résolus restent consultables dans les '
            f'<a href="{escape(_rel_index("puzzles/"), quote=True)}">archives par date</a>.'
        )
        clues_html = solution_html = ""
        meta_items = []

    meta_html = (
        '      <div class="card">\n        <ul class="meta-list">\n'
        + "\n".join("          " + item for item in meta_items)
        + "\n        </ul>\n      </div>\n"
    ) if meta_items else ""

    historique = "\n".join(
        f'          <li><a href="{escape(_rel_index(f"puzzles/{e.get("date")}/"), quote=True)}">'
        f"<span>{escape(archive_anchor(e.get('date')))}</span>"
        f"<span>{escape(f'{e.get("tries") or "--"} coups')}</span></a></li>"
        for e in entries[:5]
    )
    historique_html = f"""      <section class="card">
        <h2>📚 Archives récentes des mots du jour</h2>
        <ul class="archive-list">
{historique}
        </ul>
        <p>Voir <a href="{escape(_rel_index('puzzles/'), quote=True)}">toutes les archives des puzzles Cémantix</a>.</p>
      </section>
""" if historique else ""

    body = f"""      <h1>{escape(titre)}</h1>
      <p>{win_badge}</p>
      <p>{resume}</p>
{meta_html}{clues_html}{solution_html}      <section class="card">
        <h2>❓ Questions fréquentes sur le mot du jour Cémantix</h2>
{_faq_items_html(_HUB_FAQ)}
      </section>
{historique_html}"""

    return render_page(
        title=titre,
        description=description,
        canonical=canonical,
        json_ld=json_ld,
        body=body,
        breadcrumbs=_hub_breadcrumbs("Mot du jour"),
        resolve=_rel_index,
    )


def build_mot_du_jour_page(entry: Optional[dict], entries: list) -> str:
    """Page hub `/mot-du-jour/` : la requête dominante de la tendance Google."""
    canonical = hub_url(MOT_DU_JOUR_DIRNAME)
    date_fr = format_date_fr(entry.get("date")) if entry else ""
    if entry:
        titre = f"Indice Cémantix du jour ({date_fr}) : indices, synonymes et mot du jour"
        puzzle = entry.get("puzzle")
        word = str(entry.get("word") or "").strip()
        win = entry.get("win") is True
        tries = entry.get("tries")
        duration = format_duration_fr(entry.get("duration_seconds"))
        guesses = [g for g in (entry.get("top_guesses") or []) if str(g.get("word", "")) != "••••••••"]
        source_label = "Hybride RAG + LLM" if entry.get("source") == "llm" else "100 % RAG pur"
        puzzle_label = f"Puzzle #{puzzle}" if puzzle else "Puzzle du jour"
        puzzle_part = f" du puzzle #{puzzle}" if puzzle else ""
        mots_indices = format_clue_words_list(guesses, limit=10)
        clue_paren = f" ({mots_indices})" if mots_indices else ""
        description = (
            f"Indice Cémantix du jour du {date_fr} : consultez les 10 indices thermiques{clue_paren}, "
            f"les synonymes à explorer et la solution dépliable{puzzle_part}."
        )
    else:
        titre = "Indice Cémantix du jour : indices, synonymes et mot du jour"
        description = (
            "Indice Cémantix du jour, ses indices thermiques et sa solution : publication "
            "automatique chaque nuit à minuit (heure de Paris), sans spoiler avant demande."
        )

    json_ld = _json_ld_block({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Article",
                "@id": f"{canonical}#article",
                "headline": titre,
                "description": description,
                "inLanguage": "fr-FR",
                "datePublished": f"{entry.get('date')}T00:00:01+01:00" if entry else "",
                "dateModified": (entry.get("timestamp") if entry else "") or "",
                "image": f"{SITE_ORIGIN}/og-image.jpg",
                "author": {
                    "@type": "Person",
                    "name": "Cyril Randon",
                    "url": "https://cyril-randon.fr",
                    "sameAs": [
                        "https://github.com/Cyrilpop/cemantix-rag-solver",
                        "https://www.linkedin.com/in/cyril-randon",
                    ],
                },
                "publisher": {
                    "@type": "Person",
                    "name": "Cyril Randon",
                    "url": "https://cyril-randon.fr",
                },
                "isPartOf": {"@type": "WebSite", "@id": f"{SITE_ORIGIN}/#website"},
                "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
            },
            _hub_breadcrumb_json_ld("Mot du jour", canonical),
            _faq_json_ld(_HUB_FAQ, canonical),
        ],
    })
    return _render_hub_page(
        titre=titre,
        description=description,
        canonical=canonical,
        json_ld=json_ld,
        entry=entry,
        entries=entries,
        date_fr=date_fr,
    )


_METHODE_SECTIONS_A = (
    (
        "un-indice-cemantix",
        "Un indice Cémantix, qu'est-ce que c'est exactement ?",
        """<p>Un <strong>indice Cémantix</strong>, c'est la distance de sens entre un mot que
        vous testez et le mot secret du jour. Le jeu ne vous dit jamais « tu brûles » : il
        renvoie un nombre, calculé par <em>similarité distributionnelle</em> — deux mots sont
        proches s'ils apparaissent dans les mêmes contextes. <em>Pluie</em> et
        <em>parapluie</em> partagent des milliers de phrases ; <em>pluie</em> et
        <em>comptable</em> presque aucune. Le premier couple est chaud, le second est glacé.</p>
        <p>C'est pour cela que Cémantix se joue avec le vocabulaire plutôt qu'avec
        l'orthographe : contrairement à un jeu de lettres, aucune position, aucune lettre
        commune n'est révélée. Tout se joue sur le champ lexical, les synonymes, les
        antonymes et les stéréotypes culturels (quels mots viennent avec <em>noël</em> ?
        <em>fête</em>, <em>cadeau</em>, <em>hiver</em>, <em>bûche</em>…).</p>""",
    ),
    (
        "lire-thermometre",
        "Lire le thermomètre : pour mille, degrés Celsius et paliers",
        """<p>Deux échelles cohabitent sur ce site, et il faut les comprendre pour ne pas
        jouer à l'aveugle :</p>
        <ul class="archive-list">
          <li><span><strong>Le pour mille (‰)</strong> — l'échelle du jeu : le mot secret vaut
            exactement 1000 ‰. Au-dessus de 500 ‰, vous êtes dans le Top 1000 des mots les plus
            proches du moteur officiel.</span></li>
          <li><span><strong>Le degré Celsius</strong> — l'échelle du tableau de bord, plus
            parlante à l'œil : elle est décroissante et relative, le mot cible étant au sommet
            de la jauge. Elle sert à comparer deux coups entre eux très vite.</span></li>
        </ul>
        <table>
          <caption>Paliers du thermomètre et conduite à tenir</caption>
          <thead>
            <tr><th scope="col">Palier</th><th scope="col">Similarité</th><th scope="col">Lecture</th><th scope="col">Action</th></tr>
          </thead>
          <tbody>
            <tr><td>🧊 Glacé</td><td>&lt; 0 ‰</td><td>Aucun lien contextuel</td><td>Changer radicalement de catégorie</td></tr>
            <tr><td>❄️ Froid</td><td>0 à 200 ‰</td><td>Hors du champ lexical</td><td>Élargir : autre thème, autre nature de mot</td></tr>
            <tr><td>🌤️ Tiède</td><td>200 à 500 ‰</td><td>Thématique proche</td><td>Explorer la famille et les usages</td></tr>
            <tr><td>🔥 Chaud</td><td>&gt; 500 ‰</td><td>Top 1000 des mots proches</td><td>Synonymes, diminutifs, composés</td></tr>
          </tbody>
        </table>
        <p>Règle simple : un mot <em>glacé</em> est une information, pas un échec. Il élimine
        une famille entière et vous rapproche mathématiquement de la cible.</p>""",
    ),
    (
        "synonymes-cemantix",
        "Synonymes, antonymes et champs lexicaux : ce qui fait gagner des coups",
        """<p>Le cluster « synonyme » arrive dans les recherches Cémantix parce que c'est
        exactement le levier n° 1 en jeu. Quatre familles à explorer systématiquement autour du
        mot le plus chaud obtenu :</p>
        <ul class="archive-list">
          <li><span><strong>Les synonymes stricts</strong> — <em>voiture → automobile, auto,
            bagnole</em>. Le moteur ne les traite pas pareil : l'usage de presse les place à
            des distances différentes.</span></li>
          <li><span><strong>Les antonymes</strong> — <em>chaud → froid</em>. Très rentables :
            ils partagent le même contexte et obtiennent souvent un score élevé.</span></li>
          <li><span><strong>La famille grammaticale</strong> — pluriel, verbe, adjectif,
            diminutif : <em>jardin → jardiner, jardinage, jardinet</em>.</span></li>
          <li><span><strong>Le champ lexical concret</strong> — objets, lieux, métiers,
            actions liés : <em>hôpital → médecin, lit, urgence, infirmière</em>.</span></li>
        </ul>
        <p>Le corpus d'entraînement du solveur est <strong>frWac</strong>, un grand corpus de
        presse francophone : les associations qui <em>fonctionnent</em> sont donc celles de la
        presse. Un mot technique ou familier peut être mal noté, là où une tournure de
        titre d'article sera très bien notée.</p>""",
    ),
)

_METHODE_ETAPES = (
    (
        "Ouvrir large avec des mots pivots",
        "Testez cinq catégories différentes (nature, corps, objet, émotion, action) plutôt "
        "que cinq synonymes d'un seul mot : vous couvrez l'espace sémantique en cinq coups.",
    ),
    (
        "Identifier le palier le plus chaud",
        "Gardez le meilleur mot obtenu comme boussole : un mot à 480 ‰ vaut davantage que "
        "trois mots à 100 ‰, même s'ils sont plus jolis.",
    ),
    (
        "Explorer synonymes, antonymes et famille",
        "Autour du mot chaud, testez l'antonyme, le pluriel, le verbe de la même famille et "
        "un synonyme familier : c'est là que se cachent les bonds de 300 à 400 ‰.",
    ),
    (
        "Descendre dans le concret",
        "Le moteur adore les objets et les lieux. Si le mot chaud est abstrait (liberté, "
        "effort), testez ce que l'on touche : porte, atelier, ticket, bureau.",
    ),
    (
        "Valider avant de crier victoire",
        "Un mot au-dessus de 900 ‰ n'est pas la cible. Testez le mot le plus proche restant "
        "plutôt que son quasi-synonyme : un seul mot vaut 1000 ‰.",
    ),
)

_METHODE_FAQ = (
    (
        "Comment avoir un indice Cémantix sans être spoilé ?",
        "Le tableau de bord masque le mot secret et n'affiche que les mots déjà testés et "
        "leur score. Le mode solo propose un bouton « Indice » qui révèle un mot chaud du "
        "Top 1000 contre un coup supplémentaire : vous obtenez une piste sans jamais voir la "
        "solution.",
    ),
    (
        "Que signifie un score négatif au Cémantix ?",
        "Un score négatif (palier glacé) indique que le mot testé appartient à un contexte "
        "opposé ou sans rapport avec la cible. Ce n'est pas une erreur : le mot élimine une "
        "hypothèse entière et fait gagner du temps sur les coups suivants.",
    ),
    (
        "Les synonymes suffisent-ils à trouver le mot du jour ?",
        "Non, et c'est le piège classique. Les synonymes ne couvrent qu'une petite partie de "
        "l'espace sémantique : il faut aussi tester les antonymes, les mots de la même scène "
        "(un hôpital, ce sont des lits, des médecins, une urgence) et les mots de la même "
        "famille grammaticale.",
    ),
    (
        "Comment le thermomètre Cémantix est-il calculé ?",
        "Par similarité cosinus entre plongements vectoriels : chaque mot est représenté par "
        "un vecteur appris sur de très grands corpus, et le score mesure l'angle entre deux "
        "vecteurs. Le solveur de ce site utilise le corpus public frWac (500 dimensions) et "
        "le dictionnaire Lexique 3.83, d'où de petites différences avec le moteur officiel.",
    ),
)


def build_methode_page() -> str:
    """Page `/methode/` : le guide des indices, cluster « indice » + « synonyme »."""
    canonical = hub_url(METHODE_DIRNAME)
    titre = "Indice Cémantix : lire le thermomètre, les scores et les synonymes"
    description = (
        "Comment lire un indice Cémantix : paliers du thermomètre, pour mille, synonymes, "
        "antonymes et méthode en 5 étapes pour trouver le mot du jour en moins de coups."
    )

    etapes_html = "\n".join(
        f"            <li><strong>{escape(nom)}</strong> — {escape(texte)}</li>"
        for nom, texte in _METHODE_ETAPES
    )
    sections_html = "\n".join(
        f'      <section class="card" id="{ident}">\n'
        f"        <h2>{escape(titre_section)}</h2>\n"
        f"{html}\n"
        f"      </section>"
        for ident, titre_section, html in _METHODE_SECTIONS_A
    )

    json_ld = _json_ld_block({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "HowTo",
                "@id": f"{canonical}#howto",
                "name": "Méthode pour trouver le mot du jour Cémantix grâce aux indices",
                "description": description,
                "inLanguage": "fr-FR",
                "totalTime": "PT3M",
                "step": [
                    {
                        "@type": "HowToStep",
                        "position": index,
                        "name": nom,
                        "text": texte,
                    }
                    for index, (nom, texte) in enumerate(_METHODE_ETAPES, start=1)
                ],
            },
            _hub_breadcrumb_json_ld("Méthode & indices", canonical),
            _faq_json_ld(_METHODE_FAQ, canonical),
        ],
    })

    body = f"""      <h1>{escape(titre)}</h1>
      <p>Ce guide explique ce que mesure réellement un <strong>indice Cémantix</strong>,
      comment lire le thermomètre sans se fier à la seule intuition, et quelles familles de
      mots — synonymes, antonymes, champs lexicaux — font gagner le plus de coups. Le
      <a href="{escape(_rel_index('mot-du-jour/'), quote=True)}">mot du jour Cémantix</a> et ses
      indices mesurés sont publiés chaque nuit sur une page dédiée.</p>
{sections_html}
      <section class="card" id="methode-5-etapes">
        <h2>La méthode en 5 étapes</h2>
        <ul class="archive-list">
{etapes_html}
        </ul>
        <p>Appliquée par le solveur automatique, cette méthode résout le puzzle en une
        dizaine de coups ; appliquée par un joueur régulier, elle tient en cinq à sept
        essais. Pour s'exercer sans risque sur le mot du jour, le
        <a href="{escape(_rel_index('play/'), quote=True)}">mode solo illimité</a> propose des
        parties infinies avec le même thermomètre.</p>
      </section>
      <section class="card">
        <h2>❓ Questions fréquentes sur les indices Cémantix</h2>
{_faq_items_html(_METHODE_FAQ)}
      </section>
      <section class="card">
        <h2>🔎 Aller plus loin</h2>
        <ul class="archive-list">
          <li><a href="{escape(_rel_index('mot-du-jour/'), quote=True)}"><span>Mot du jour Cémantix : indices et solution</span><span>publié à minuit</span></a></li>
          <li><a href="{escape(_rel_index('puzzles/'), quote=True)}"><span>Archives des puzzles Cémantix par date</span><span>indices &amp; solutions</span></a></li>
          <li><a href="{escape(_rel_index('battle/'), quote=True)}"><span>Jouer au Cémantix contre l'IA (mode Battle)</span><span>duel en direct</span></a></li>
        </ul>
      </section>
"""

    return render_page(
        title=titre,
        description=description,
        canonical=canonical,
        json_ld=json_ld,
        body=body,
        breadcrumbs=_hub_breadcrumbs("Méthode & indices"),
        resolve=_rel_index,
    )


__all__ = [
    "_HUB_FAQ",
    "_METHODE_SECTIONS_A",
    "_METHODE_ETAPES",
    "_METHODE_FAQ",
    "build_mot_du_jour_page",
    "build_methode_page",
]
