"""
Cémantix Solver — Services d'Arrière-Plan & Synchronisation (src.services)
==========================================================================
Sous-paquet assurant l'exécution permanente et la publication des données :
- daemon : Démon planificateur 24h/24, veille automatique et réveil de minuit
- web    : Agrégation et écriture atomique de data.json pour le serveur Caddy
- seo    : Génération des pages d'archives indexables, de l'index paginé et du sitemap
"""
from .daemon import (
    DAILY_HISTORY_FILE,
    HEARTBEAT_FILE,
    PARIS_TZ,
    check_health,
    format_duration,
    get_next_run,
    has_solved_today,
    load_history,
    save_history,
    run_daemon_loop,
    run_daily_solver,
    start_heartbeat_monitor,
    stop_heartbeat_monitor,
    update_heartbeat,
)
from .web import (
    DASHBOARD_DATA_FILE,
    WEB_DATA_FILE,
    build_web_data,
    export_web_data,
)
from .hints import (
    DEFAULT_TIER_TARGETS,
    backfill_puzzle_hints,
    bootstrap_database,
    generate_hints_for_word,
)
from .seo import (
    SITE_ORIGIN,
    build_agent_card,
    build_archive_page,
    build_archives_index_page,
    build_ard_manifest,
    build_sitemap,
    ensure_seo_published,
    format_date_fr,
    format_duration_fr,
    prerender_dashboard,
    publish_ard_manifests,
    publish_seo_pages,
)

__all__ = [
    "PARIS_TZ",
    "DAILY_HISTORY_FILE",
    "HEARTBEAT_FILE",
    "DASHBOARD_DATA_FILE",
    "WEB_DATA_FILE",
    "load_history",
    "save_history",
    "has_solved_today",
    "get_next_run",
    "format_duration",
    "start_heartbeat_monitor",
    "stop_heartbeat_monitor",
    "update_heartbeat",
    "check_health",
    "run_daily_solver",
    "run_daemon_loop",
    "build_web_data",
    "export_web_data",
    "SITE_ORIGIN",
    "build_agent_card",
    "build_archive_page",
    "build_archives_index_page",
    "build_ard_manifest",
    "build_sitemap",
    "ensure_seo_published",
    "format_date_fr",
    "format_duration_fr",
    "prerender_dashboard",
    "publish_ard_manifests",
    "publish_seo_pages",
    "DEFAULT_TIER_TARGETS",
    "generate_hints_for_word",
    "backfill_puzzle_hints",
]
