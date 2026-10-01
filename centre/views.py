from django.shortcuts import render
from django.db.models import Sum, Max, Count
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.core.cache import cache
from .models import Data, Centre
from django.conf import settings
import json
import os


# ─────────────────────────────────────────────
#  SERVICE
# ─────────────────────────────────────────────

class CentreDataService:
    """Service centralisé pour les données des centres"""

    DEFAULT_YEAR = '2022'

    # ── Helpers querysets ──────────────────────────────────────────────────

    @classmethod
    def apply_filters(cls, qs, region=None, delegation=None):
        """Applique les filtres région/délégation à un queryset."""
        if region:
            qs = qs.filter(id_region=region)
        if delegation:
            try:
                qs = qs.filter(id_delegation=int(delegation))
            except (ValueError, TypeError):
                pass
        return qs

    @classmethod
    def get_centre_queryset(cls, annee=None, region=None, delegation=None):
        """Queryset de base sur Centre avec filtres appliqués."""
        qs = Centre.objects.all()
        if annee:
            qs = qs.filter(id_periodicite=annee)
        return cls.apply_filters(qs, region, delegation)

    @classmethod
    def get_data_queryset(cls, annee=None, region=None, delegation=None):
        """Queryset de base sur Data avec filtres appliqués."""
        qs = Data.objects.all()
        if annee:
            qs = qs.filter(id_periodicite=annee)
        return cls.apply_filters(qs, region, delegation)

    # ── Options de filtrage (cachées 1 heure) ─────────────────────────────

    @classmethod
    def get_filter_options(cls):
        """
        ✅ OPTIMISÉ : Options de filtrage mises en cache 1 heure.
        """
        cache_key = 'centre_filter_options'
        options = cache.get(cache_key)

        if options is None:
            options = {
                'annees': list(
                    Centre.objects.exclude(id_periodicite__isnull=True)
                    .values('id_periodicite').distinct().order_by('id_periodicite')
                ),
                'regions': list(
                    Centre.objects.exclude(region__isnull=True)
                    .values('id_region', 'region').distinct().order_by('region')
                ),
                'delegations': list(
                    Centre.objects.exclude(delegation__isnull=True)
                    .values('id_delegation', 'delegation', 'id_region')
                    .distinct().order_by('delegation')
                )
            }
            cache.set(cache_key, options, 3600)

        return options

    # ── Statistiques milieu ────────────────────────────────────────────────

    @classmethod
    def get_milieu_stats(cls, qs):
        """
        ✅ OPTIMISÉ : Une seule requête pour toutes les stats milieu.
        Retourne total, urbain, rural, pourcentages et labels/valeurs pour graphique.
        """
        milieu_stats = list(
            qs.values('milieu')
            .annotate(total=Sum('nb_centres'))
            .exclude(milieu__isnull=True)
            .order_by('milieu')
        )

        milieu_totals = {
            entry['milieu'].lower(): entry['total'] or 0
            for entry in milieu_stats
        }

        total_centres  = sum(milieu_totals.values()) or 0
        total_urbain   = milieu_totals.get('urbain', 0)
        total_rural    = milieu_totals.get('rural', 0)
        safe_total     = total_centres or 1

        return {
            'total_centres':      total_centres,
            'total_urbain':       total_urbain,
            'total_rural':        total_rural,
            'pourcentage_urbain': round((total_urbain * 100) / safe_total, 2),
            'pourcentage_rural':  round((total_rural  * 100) / safe_total, 2),
            # Pour les graphiques
            'labels_milieu': [e['milieu'].capitalize() for e in milieu_stats],
            'total_milieu':  [e['total'] or 0          for e in milieu_stats],
        }

    # ── Évolution temporelle ───────────────────────────────────────────────

    @classmethod
    def get_evolution_stats(cls, region=None, delegation=None):
        """
        ✅ OPTIMISÉ : Deux requêtes au lieu de trois pour l'évolution.
        Retourne labels, centres par année, capacité par année, urbain/rural par année.
        """
        evo_qs = cls.apply_filters(Centre.objects.all(), region, delegation)

        # ✅ Requête 1 : évolution générale (centres + capacité)
        evolution = list(
            evo_qs.values('id_periodicite')
            .annotate(
                total_centre=Sum('nb_centres'),
                total_cap=Sum('capacite')
            )
            .order_by('id_periodicite')
        )

        labels_dates   = [e['id_periodicite'] for e in evolution if e['id_periodicite'] is not None]
        values_centre  = [e['total_centre'] or 0 for e in evolution]
        capacite_evol  = [e['total_cap']    or 0 for e in evolution]

        # ✅ Requête 2 : évolution par milieu (une seule requête groupée)
        milieu_evolution = list(
            evo_qs.values('id_periodicite', 'milieu')
            .annotate(total_centres=Sum('nb_centres'))
            .order_by('id_periodicite')
        )

        urbain_map, rural_map = {}, {}
        for entry in milieu_evolution:
            milieu = (entry['milieu'] or '').lower()
            if milieu == 'urbain':
                urbain_map[entry['id_periodicite']] = entry['total_centres'] or 0
            elif milieu == 'rural':
                rural_map[entry['id_periodicite']] = entry['total_centres'] or 0

        urbain_evol = [urbain_map.get(d, 0) for d in labels_dates]
        rural_evol  = [rural_map.get(d, 0)  for d in labels_dates]

        return {
            'labels_dates':  labels_dates,
            'values_centre': values_centre,
            'capacite_evol': capacite_evol,
            'urbain_evol':   urbain_evol,
            'rural_evol':    rural_evol,
        }

    # ── Nombre d'associations ─────────────────────────────────────────────

    @classmethod
    def get_nombre_associations(cls, data_qs):
        """Compte le nombre de structures distinctes (noms distincts hors null)."""
        return (
            data_qs
            .exclude(personnes_cibles__isnull=True)
            .values('nom')
            .distinct()
            .count()
        )

    # ── Capacité totale ────────────────────────────────────────────────────

    @classmethod
    def get_capacite_totale(cls, qs):
        return qs.aggregate(total_cap=Sum('capacite'))['total_cap'] or 0


# ─────────────────────────────────────────────
#  VUES
# ─────────────────────────────────────────────

@login_required
def get_delegations_by_region(request):
    """
    ✅ OPTIMISÉ : Vue AJAX pour les délégations d'une région — avec cache 1 heure.
    """
    region_id = request.GET.get('region_id')
    if not region_id:
        return JsonResponse({'delegations': []})

    cache_key = f'centre_delegations_region_{region_id}'
    result = cache.get(cache_key)

    if result is None:
        delegations = (
            Data.objects.filter(id_region=region_id)
            .values('id_delegation')
            .annotate(delegation_name=Max('delegation'))
            .order_by('delegation_name')
        )
        result = [
            {'id_delegation': d['id_delegation'], 'delegation': d['delegation_name']}
            for d in delegations if d['id_delegation'] is not None
        ]
        cache.set(cache_key, result, 3600)

    return JsonResponse({'delegations': result})


@login_required
@require_GET
def repartition_centres_api(request):
    """
    ✅ OPTIMISÉ : API répartition des centres avec cache par combinaison de filtres.
    """
    milieu     = request.GET.get('filtre', 'total').lower()
    region     = request.GET.get('region')
    delegation = request.GET.get('delegation')
    annee      = request.GET.get('annee', CentreDataService.DEFAULT_YEAR)

    cache_key = f'repartition_centres_{annee}_{region}_{delegation}_{milieu}'
    cached    = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)

    niveau = 'delegation' if region else 'region'
    qs     = CentreDataService.get_centre_queryset(annee, region, delegation)

    # ✅ Stats milieu calculées en une seule requête
    milieu_data = CentreDataService.get_milieu_stats(qs)

    # Appliquer le filtre milieu pour la répartition géographique
    if milieu == 'urbain':
        qs = qs.filter(milieu__iexact='urbain')
    elif milieu == 'rural':
        qs = qs.filter(milieu__iexact='rural')

    if niveau == 'region':
        grouped = qs.values('region').annotate(total=Sum('nb_centres')).order_by('region')
        labels  = [g['region'] for g in grouped]
    else:
        grouped = qs.values('delegation').annotate(total=Sum('nb_centres')).order_by('delegation')
        labels  = [g['delegation'] for g in grouped]

    values = [g['total'] or 0 for g in grouped]

    response_data = {
        'labels': labels,
        'data':   values,
        'milieu_totals': {
            'total':  milieu_data['total_centres'],
            'urbain': milieu_data['total_urbain'],
            'rural':  milieu_data['total_rural'],
        }
    }

    cache.set(cache_key, response_data, 600)
    return JsonResponse(response_data)


@login_required
def list_centre(request):
    """
    ✅ VUE PRINCIPALE OPTIMISÉE :
    - Toutes les stats milieu calculées en UNE seule requête via get_milieu_stats()
    - Évolution calculée en DEUX requêtes au lieu de trois
    - Options de filtrage cachées 1 heure
    - Contexte complet caché 10 minutes par combinaison de filtres
    """
    selected_annee      = request.GET.get('annee') or CentreDataService.DEFAULT_YEAR
    selected_region     = request.GET.get('region')
    selected_delegation = request.GET.get('delegation')

    # ─── Clé de cache unique par combinaison de filtres ───────────────────
    cache_key = f'dashboard_centre_{selected_annee}_{selected_region}_{selected_delegation}'
    context   = cache.get(cache_key)

    if context is None:

        # ✅ 1. Querysets principaux
        centre_qs = CentreDataService.get_centre_queryset(
            selected_annee, selected_region, selected_delegation
        )
        data_qs = CentreDataService.get_data_queryset(
            selected_annee, selected_region, selected_delegation
        )

        # ✅ 2. Options de filtrage (cachées séparément 1 heure)
        filter_options = CentreDataService.get_filter_options()

        # ✅ 3. Stats milieu — UNE seule requête pour tout
        milieu_data = CentreDataService.get_milieu_stats(centre_qs)

        # ✅ 4. Capacité totale
        capacite_autorisee_totale = CentreDataService.get_capacite_totale(centre_qs)

        # ✅ 5. Évolution — DEUX requêtes au lieu de trois
        evolution_data = CentreDataService.get_evolution_stats(
            selected_region, selected_delegation
        )

        # ✅ 6. Nombre d'associations
        nombre_ass = CentreDataService.get_nombre_associations(data_qs)

        # ✅ 7. Construction du contexte final
        context = {
            # Options de filtrage
            **filter_options,
            'selected_annee':      selected_annee,
            'selected_region':     selected_region,
            'selected_delegation': selected_delegation,

            # Indicateurs clés
            'centres_count':             milieu_data['total_centres'],
            'pourcentage_urbain':        milieu_data['pourcentage_urbain'],
            'pourcentage_rural':         milieu_data['pourcentage_rural'],
            'capacite_autorisee_totale': capacite_autorisee_totale,
            'nombre_ass':                nombre_ass,

            # Données JSON pour les graphiques
            'labels_dates':   json.dumps(evolution_data['labels_dates']),
            'values_centre':  json.dumps(evolution_data['values_centre']),
            'urbain_evol':    json.dumps(evolution_data['urbain_evol']),
            'rural_evol':     json.dumps(evolution_data['rural_evol']),
            'capacite_evol':  json.dumps(evolution_data['capacite_evol']),
            'labels_milieu':  json.dumps(milieu_data['labels_milieu']),
            'total_milieu':   json.dumps(milieu_data['total_milieu']),
        }

        # ✅ 8. Mise en cache 10 minutes
        cache.set(cache_key, context, 600)

    return render(request, 'centre.html', context)


# ─────────────────────────────────────────────
#  VUES GEOJSON / CARTE  (inchangées, lecture fichier)
# ─────────────────────────────────────────────

@login_required
def regions_api(request):
    try:
        geojson_path = os.path.join(
            settings.BASE_DIR, 'centre', 'static', 'geojson', 'region.geojson'
        )
        if not os.path.exists(geojson_path):
            return JsonResponse({'error': f'Fichier non trouvé : {geojson_path}'}, status=404)
        with open(geojson_path, encoding='utf-8') as f:
            data = json.load(f)
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def delegations_api(request):
    region_name = request.GET.get('region')
    try:
        geojson_path = os.path.join(
            settings.BASE_DIR, 'centre', 'static', 'geojson', 'delegations.geojson'
        )
        if not os.path.exists(geojson_path):
            return JsonResponse({'error': f'Fichier non trouvé : {geojson_path}'}, status=404)
        with open(geojson_path, encoding='utf-8') as f:
            data = json.load(f)
        if region_name:
            data['features'] = [
                feat for feat in data['features']
                if feat['properties'].get('region') == region_name
            ]
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def centres_api(request):
    """
    ✅ OPTIMISÉ : Utilise values() pour ne charger que les champs nécessaires
    au lieu de charger les objets complets.
    """
    delegation_name = request.GET.get('delegation')
    programme       = request.GET.get('programme')

    qs = Data.objects.all()
    if delegation_name:
        qs = qs.filter(delegation=delegation_name)
    if programme:
        qs = qs.filter(programme_updated=programme)

    # ✅ values() évite de charger tous les champs inutiles de Data
    data = list(
        qs.values(
            'nom', 'latitude', 'longitude',
            'axe_updated', 'programme_updated',
            'nb_beneficiaires_t', 'delegation'
        )
    )

    return JsonResponse(data, safe=False)


@login_required
def programmes_api(request):
    """
    ✅ OPTIMISÉ : Mise en cache de la liste des programmes (données statiques).
    """
    cache_key = 'programmes_list'
    programmes = cache.get(cache_key)

    if programmes is None:
        programmes = list(
            Data.objects.values_list('programme_updated', flat=True)
            .distinct().order_by('programme_updated')
        )
        cache.set(cache_key, programmes, 3600)

    return JsonResponse(programmes, safe=False)