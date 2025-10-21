from django.shortcuts import render
from django.db.models import Sum, Max, Count
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseServerError
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from .models import Data, Centre
from django.conf import settings
from django.contrib.staticfiles import finders
import json
import os


def filter_by_region_and_delegation(qs, region, delegation):
    """
    Applique les filtres de région et de délégation à une queryset donnée.

    Args:
        qs (QuerySet): La queryset à filtrer.
        region (str): L'identifiant de la région.
        delegation (str): L'identifiant de la délégation.

    Returns:
        QuerySet: La queryset filtrée selon les paramètres.
    """
    if region:
        qs = qs.filter(id_region=region)
    if delegation:
        try:
            qs = qs.filter(id_delegation=int(delegation))
        except (ValueError, TypeError):
            pass  # Ignore les erreurs de conversion
    return qs


@login_required
def get_delegations_by_region(request):
    """
    Vue AJAX qui retourne la liste des délégations pour une région donnée.

    Cette vue est utilisée dans les filtres dynamiques du frontend.
    """
    region_id = request.GET.get('region_id')
    delegations = []

    if region_id:
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
    return JsonResponse({'delegations': result})


@login_required
@require_GET
def repartition_centres_api(request):
    """
    Vue API pour retourner la répartition des centres :
    - Par région (si aucune région sélectionnée)
    - Par délégation (si une région est sélectionnée)
    Filtrée selon le milieu (total, urbain, rural).
    """

    milieu = request.GET.get('filtre', 'total').lower()  # total | urbain | rural
    region = request.GET.get('region')
    delegation = request.GET.get('delegation')
    annee = request.GET.get('annee', '2022')

    niveau = 'delegation' if region else 'region'

    # Requête de base
    qs = Centre.objects.filter(id_periodicite=annee)
    qs = filter_by_region_and_delegation(qs, region, delegation)

    # Calcul des statistiques globales par milieu
    milieu_stats = (
        qs.values('milieu')
        .annotate(total=Sum('nb_centres'))
        .exclude(milieu__isnull=True)
    )
    # dictionnaire: {'urbain': x, 'rural': y}
    milieu_totals = {entry['milieu'].lower(): entry['total'] or 0 for entry in milieu_stats}
    total_centres = sum(milieu_totals.values()) or 0
    total_urbain = milieu_totals.get('urbain', 0)
    total_rural = milieu_totals.get('rural', 0)

    # Appliquer filtre milieu
    if milieu == 'urbain':
        qs = qs.filter(milieu__iexact='urbain')
    elif milieu == 'rural':
        qs = qs.filter(milieu__iexact='rural')
    # sinon on garde tout pour "total"

    # Regrouper les résultats par région ou délégation
    if niveau == 'region':
        grouped = qs.values('region').annotate(total=Sum('nb_centres')).order_by('region')
        labels = [g['region'] for g in grouped]
    else:
        grouped = qs.values('delegation').annotate(total=Sum('nb_centres')).order_by('delegation')
        labels = [g['delegation'] for g in grouped]

    values = [g['total'] or 0 for g in grouped]

    return JsonResponse({
        'labels': labels,
        'data': values,
        'milieu_totals': {
            'total': total_centres,
            'urbain': total_urbain,
            'rural': total_rural,
        }
    })


@login_required
def list_centre(request):
    """
    Vue principale pour afficher les statistiques sur les centres :
    - Répartition par milieu (urbain/rural)
    - Capacités totales
    - Évolution sur plusieurs années
    - Nombre de populations cibles
    """
    # --- Récupération des filtres depuis la requête (avec valeur par défaut pour l'année) ---
    selected_annee = request.GET.get('annee') or '2022'
    selected_region = request.GET.get('region')
    selected_delegation = request.GET.get('delegation')

    # --- Initialisation des querysets ---
    queryset = Centre.objects.all()
    data_queryset = Data.objects.all()

    # --- Application des filtres sur l'année, région et délégation ---
    queryset = queryset.filter(id_periodicite=selected_annee)
    data_queryset = data_queryset.filter(id_periodicite=selected_annee)

    queryset = filter_by_region_and_delegation(queryset, selected_region, selected_delegation)
    data_queryset = filter_by_region_and_delegation(data_queryset, selected_region, selected_delegation)

    # --- Récupération des valeurs uniques pour les filtres dropdown ---
    annees = Centre.objects.exclude(id_periodicite__isnull=True).values('id_periodicite').distinct().order_by('id_periodicite')
    regions = Centre.objects.exclude(region__isnull=True).values('id_region', 'region').distinct().order_by('region')
    delegations = Centre.objects.exclude(delegation__isnull=True).values('id_delegation', 'delegation', 'id_region').distinct().order_by('delegation')

    # --- Statistiques globales par milieu (urbain/rural) ---
    milieu_stats = (
        queryset.values('milieu')
        .annotate(total=Sum('nb_centres'))
        .exclude(milieu__isnull=True)
        .order_by('milieu')
    )

    labels_milieu = [entry['milieu'].capitalize() for entry in milieu_stats]
    total_milieu = [entry['total'] or 0 for entry in milieu_stats]
    milieu_totals = {entry['milieu']: entry['total'] or 0 for entry in milieu_stats}

    total_centres = sum(milieu_totals.values()) or 0
    total_urbain = milieu_totals.get('urbain', 0)
    total_rural = milieu_totals.get('rural', 0)

    pourcentage_urbain = round((total_urbain * 100) / (total_centres or 1), 2)
    pourcentage_rural = round((total_rural * 100) / (total_centres or 1), 2)

    # --- Somme des capacités autorisées ---
    capacite_autorisee_totale = queryset.aggregate(total_cap=Sum('capacite'))['total_cap'] or 0

    # --- Évolution des centres par année ---
    evolution_queryset = Centre.objects.all()
    evolution_queryset = filter_by_region_and_delegation(evolution_queryset, selected_region, selected_delegation)

    evolution = (
        evolution_queryset
        .values('id_periodicite')
        .annotate(total_centre=Sum('nb_centres'), total_cap=Sum('capacite'))
        .order_by('id_periodicite')
    )
    labels_dates = [e['id_periodicite'] for e in evolution if e['id_periodicite'] is not None]
    values_centre = [e['total_centre'] or 0 for e in evolution]
    capacite_evol = [e['total_cap'] or 0 for e in evolution]

    # --- Évolution des centres selon le milieu ---
    milieu_evolution = (
        evolution_queryset
        .values('id_periodicite', 'milieu')
        .annotate(total_centres=Sum('nb_centres'))
        .order_by('id_periodicite')
    )
    urbain_map, rural_map = {}, {}
    for entry in milieu_evolution:
        if entry['milieu'] == 'urbain':
            urbain_map[entry['id_periodicite']] = entry['total_centres'] or 0
        elif entry['milieu'] == 'rural':
            rural_map[entry['id_periodicite']] = entry['total_centres'] or 0

    urbain_evol = [urbain_map.get(date, 0) for date in labels_dates]
    rural_evol = [rural_map.get(date, 0) for date in labels_dates]

    # --- Nombre de types des associations ---
    nombre_ass = (
        data_queryset
        .exclude(personnes_cibles__isnull=True)
        .values('nom')
        .distinct()
        .count()
    )

    # --- Transmission des données au template ---
    context = {
        # Filtres sélectionnés et listes déroulantes
        'annees': annees,
        'regions': regions,
        'delegations': delegations,
        'selected_annee': selected_annee,
        'selected_region': selected_region,
        'selected_delegation': selected_delegation,

        # Indicateurs clés
        'centres_count': total_centres,
        'pourcentage_urbain': pourcentage_urbain,
        'pourcentage_rural': pourcentage_rural,
        'capacite_autorisee_totale': capacite_autorisee_totale,
        'nombre_ass': nombre_ass,

        # Données pour les graphiques
        'labels_dates': json.dumps(labels_dates),
        'values_centre': json.dumps(values_centre),
        'urbain_evol': json.dumps(urbain_evol),
        'rural_evol': json.dumps(rural_evol),
        'capacite_evol': json.dumps(capacite_evol),

        'labels_milieu': json.dumps(labels_milieu),
        'total_milieu': json.dumps(total_milieu),
    }

    return render(request, 'centre.html', context)



"""
def centres_api(request):
    delegation = request.GET.get("delegation")
    centres = Data.objects.all()

    if delegation:
        centres = centres.filter(delegation=delegation)
    
    data = [
        {
            "nom": c.nom,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "axe_updated": c.axe_updated,
            "programme_updated": c.programme_updated,
            "nb_beneficiaires_t": c.nb_beneficiaires_t,
            "delegation": c.delegation
        }
        for c in centres
    ]
    
    return JsonResponse(data, safe=False)
"""

def _read_geojson_static(path_in_static):
    """
    Lit un fichier static (geojson/json) via staticfiles.finders et renvoie le dict JSON.
    """
    full_path = finders.find(path_in_static)
    if not full_path or not os.path.exists(full_path):
        raise FileNotFoundError(f"Fichier introuvable: {path_in_static}")
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)

@login_required
def regions_api(request):
    try:
        geojson_path = os.path.join(settings.BASE_DIR, 'centre', 'static', 'geojson', 'region.geojson')

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
        geojson_path = os.path.join(settings.BASE_DIR, 'centre', 'static', 'geojson', 'delegations.geojson')

        if not os.path.exists(geojson_path):
            return JsonResponse({'error': f'Fichier non trouvé : {geojson_path}'}, status=404)

        with open(geojson_path, encoding='utf-8') as f:
            data = json.load(f)

        # Si une région est spécifiée, filtrer les délégations
        if region_name:
            features = [
                feat for feat in data["features"]
                if feat["properties"].get("region") == region_name
            ]
            data["features"] = features

        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@login_required
def centres_api(request):
    delegation_name = request.GET.get("delegation")
    centres = Data.objects.all()

    if delegation_name:
        centres = centres.filter(delegation=delegation_name)

    data = [
        {
            "nom": c.nom,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "axe_updated": c.axe_updated,
            "programme_updated": c.programme_updated,
            "nb_beneficiaires_t": c.nb_beneficiaires_t,
            "delegation": c.delegation
        }
        for c in centres
    ]

    return JsonResponse(data, safe=False)
