# cache_utils.py
from django.core.cache import cache

def invalidate_dashboard_cache():
    """
    À appeler après toute modification des données.
    Sur Memurai/Redis, cache.delete_pattern() fonctionne avec django-redis.
    """
    try:
        # Vider toutes les clés du dashboard
        cache.delete_pattern('dashboard_benefic_*')
    except Exception:
        # Fallback si delete_pattern non supporté
        cache.clear()
    
    # Vider aussi les options de filtrage
    cache.delete('filter_options')