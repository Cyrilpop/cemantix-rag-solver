"""
Cémantix Solver — Gestion Sécurisée des Adresses IP et Reverse Proxies
======================================================================
Module de résolution sécurisée de l'adresse IP client (fail-closed) :
- Ne fait confiance aux en-têtes d'acheminement (`X-Forwarded-For`) QUE si la
  connexion TCP directe provient d'un reverse-proxy explicitement déclaré de confiance
  (variable d'environnement `TRUSTED_PROXIES`).
- Parcourt la chaîne de relais de droite à gauche (du proxy le plus proche vers le
  client) et extrait la première adresse IP non comprise dans le réseau de confiance.
- Rejette de façon étanche toute tentative d'usurpation (spoofing) par injection
  d'en-tête ou chaîne de proxys malformée.
- Anonymisation RGPD (/24 en IPv4, /48 en IPv6).
"""
import ipaddress
import os
from typing import List, Optional, Union

# Types d'IP acceptés pour les listes de proxys de confiance
TrustedEntry = Union[
    ipaddress.IPv4Network,
    ipaddress.IPv6Network,
    ipaddress.IPv4Address,
    ipaddress.IPv6Address,
]


def parse_ip(raw: Optional[str]) -> Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]:
    """Parse une adresse IPv4 ou IPv6, en retirant les crochets et ports optionnels.

    Renvoie None en cas d'adresse malformée ou vide.
    """
    if not raw:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None

    # IPv6 entre crochets : [2001:db8::1] ou [2001:db8::1]:8080
    if cleaned.startswith("["):
        end = cleaned.find("]")
        if end != -1:
            cleaned = cleaned[1:end]
    elif ":" in cleaned and cleaned.count(":") == 1:
        # IPv4 avec port : 192.0.2.1:8080
        cleaned = cleaned.split(":")[0]

    try:
        return ipaddress.ip_address(cleaned)
    except ValueError:
        return None


def parse_trusted_proxies(raw_str: str) -> List[TrustedEntry]:
    """Parse une chaîne de proxys/sous-réseaux séparés par des virgules."""
    if not raw_str:
        return []
    result: List[TrustedEntry] = []
    for item in raw_str.split(","):
        token = item.strip()
        if not token:
            continue
        try:
            if "/" in token:
                result.append(ipaddress.ip_network(token, strict=False))
            else:
                result.append(ipaddress.ip_address(token))
        except ValueError:
            pass
    return result


def is_ip_in_trusted(
    ip_obj: Union[ipaddress.IPv4Address, ipaddress.IPv6Address],
    trusted_list: List[TrustedEntry],
) -> bool:
    """Vérifie si une adresse IP est présente dans la liste de confiance."""
    for entry in trusted_list:
        if isinstance(entry, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
            if ip_obj.version == entry.version and ip_obj in entry:
                return True
        elif isinstance(entry, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            if ip_obj == entry:
                return True
    return False


def get_trusted_proxies() -> List[TrustedEntry]:
    """Charge la configuration des proxys de confiance depuis l'environnement."""
    raw = os.getenv("TRUSTED_PROXIES", "").strip()
    return parse_trusted_proxies(raw)


def extract_client_ip(
    peer_ip_str: Optional[str],
    forwarded_header: Optional[str] = None,
    trusted_proxies: Optional[List[TrustedEntry]] = None,
) -> str:
    """Détermine l'adresse IP effective du client de façon sécurisée (fail-closed).

    Règles :
    1. Si peer_ip_str est manquant ou invalide, renvoie l'original ou 'unknown'.
    2. Si le pair TCP direct (peer) n'est PAS un proxy de confiance, ignorer
       strictement tout en-tête d'acheminement et renvoyer le pair TCP.
    3. Si le pair TCP est de confiance et qu'un en-tête `X-Forwarded-For` est présent :
       - Parcourir les relais de droite à gauche.
       - Rejeter fail-closed (repli sur peer TCP) si un segment est syntaxiquement invalide.
       - Renvoyer la première adresse qui n'appartient PAS aux proxys de confiance.
       - Si tous les relais sont de confiance, renvoyer le premier relais de la chaîne.
    """
    parsed_peer = parse_ip(peer_ip_str)
    if not parsed_peer:
        return peer_ip_str.strip() if peer_ip_str else "unknown"

    trusted = trusted_proxies if trusted_proxies is not None else get_trusted_proxies()

    # Si le pair direct n'est pas un proxy de confiance, aucune confiance dans les en-têtes
    if not is_ip_in_trusted(parsed_peer, trusted):
        return str(parsed_peer)

    # Le pair direct est de confiance : inspecter la chaîne transmise
    if not forwarded_header or not forwarded_header.strip():
        return str(parsed_peer)

    raw_hops = [h.strip() for h in forwarded_header.split(",") if h.strip()]
    if not raw_hops:
        return str(parsed_peer)

    parsed_hops = []
    for h in raw_hops:
        pip = parse_ip(h)
        if not pip:
            # En-tête malformé ou tentative d'injection : fail-closed vers le pair TCP
            return str(parsed_peer)
        parsed_hops.append(pip)

    # Dépilage de droite à gauche (du proxy le plus proche vers le client d'origine)
    for hop in reversed(parsed_hops):
        if not is_ip_in_trusted(hop, trusted):
            return str(hop)

    # Si tous les sauts étaient des proxys de confiance, l'origine est le premier
    return str(parsed_hops[0])


def anonymize_ip(ip_str: str) -> str:
    """Anonymise l'adresse IP pour conformité RGPD (/24 en IPv4, /48 en IPv6)."""
    parsed = parse_ip(ip_str)
    if not parsed:
        return ip_str.strip() if ip_str else "unknown"

    if parsed.version == 4:
        parts = str(parsed).split(".")
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0"
    else:
        net = ipaddress.ip_network(f"{parsed}/48", strict=False)
        # Format compact standard /48 (trois premiers hextets suivis de ::)
        exploded = net.network_address.exploded.split(":")
        return f"{exploded[0].lstrip('0') or '0'}:{exploded[1].lstrip('0') or '0'}:{exploded[2].lstrip('0') or '0'}::"
