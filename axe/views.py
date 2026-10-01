from django.shortcuts import render
from django.db.models import Count, Sum, Max, Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from .models import Data, Axe, Activite, Centre
import json
from typing import Dict, List, Tuple, Any, Optional, Union


# ─────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────

class DataConstants:
    """Configuration centralisée pour les mappings et constantes"""

    PROGRAMME_CATEGORIE2_MAPPING = {
        "Centres d'Assistance Sociale (CAS)": "Centre d'assistance sociale ( CAS )",
        "Centre d'Orientation et d'Assistance pour les Personnes Handicapées (COAPH)": "COAPH",
        "Centres d'Accompagnement pour la Protection de l'Enfance (CAPE)": "Unité de Protection de l'Enfance (UPE)",
        "Espace Multifonctionnel de la Femme (EMF)": "Espace Multifonctionnel de la Femme (EMF)"
    }

    CAS_LABELS   = {"Centre d'assistance sociale ( CAS )", "Cellule d'assistance sociale ( CAS )", "CAS1"}
    CAPE_LABELS  = {"Unité de Protection de l'Enfance (UPE)", "Cellule d'unité de Protection de l'Enfance (UPE)"}
    COAPH_LABELS = {"COAPH", "Centre d'Orientation et Assistance pour Personnes en situation d'Handicap (COAPH)"}
    EMF_LABELS   = {"Espace Multifonctionnel de la Femme (EMF)"}

    SPECIAL_PROGRAMMES = {
        "Centres d'Assistance Sociale (CAS)": CAS_LABELS,
        "Centres d'Accompagnement pour la Protection de l'Enfance (CAPE)": CAPE_LABELS,
        "Centre d'Orientation et d'Assistance pour les Personnes Handicapées (COAPH)": COAPH_LABELS,
    }

    BENEF_FIELDS = {
        'total':  'nb_beneficiaires_t',
        'femmes': 'nb_beneficiaires_f',
        'hommes': 'nb_beneficiaires_m'
    }

    EXCLUDED_VALUES = {
        'general':    ['Non spécifié', 'non specifie', 'Non specifié', 'non spécifié', '', None],
        'programme':  ['SDF', 'sdf'],
        'population': ['TC', 'tc']
    }

    DEFAULT_YEAR = '2022'

    @classmethod
    def round_value(cls, value: Union[float, int, None]) -> int:
        if value is None:
            return 0
        return round(float(value))


# ─────────────────────────────────────────────
#  SERVICES FILTRES
# ─────────────────────────────────────────────

class DataFilterService:
    """Service pour gérer les filtres et requêtes"""

    @staticmethod
    def build_filters(annee: str = None, region: str = None, delegation: str = None) -> Dict[str, Any]:
        filters = {}
        if annee:
            filters["id_periodicite"] = annee
        if region:
            filters["id_region"] = region
        if delegation:
            try:
                filters["id_delegation"] = int(delegation)
            except (ValueError, TypeError):
                pass
        return filters

    @staticmethod
    def apply_region_delegation_filter(queryset, region: str = None, delegation: str = None):
        if region:
            queryset = queryset.filter(id_region=region)
        if delegation:
            try:
                queryset = queryset.filter(id_delegation=int(delegation))
            except (ValueError, TypeError):
                pass
        return queryset

    @staticmethod
    def apply_exclusion_filters(queryset, field_name: str, filter_type: str = 'general'):
        excluded_values = DataConstants.EXCLUDED_VALUES['general'].copy()
        if filter_type == 'programme':
            excluded_values.extend(DataConstants.EXCLUDED_VALUES['programme'])
        elif filter_type == 'population':
            excluded_values.extend(DataConstants.EXCLUDED_VALUES['population'])

        exclude_conditions = Q()
        for value in excluded_values:
            if value is None:
                exclude_conditions |= Q(**{f"{field_name}__isnull": True})
            elif value == '':
                exclude_conditions |= Q(**{f"{field_name}__exact": ''})
            else:
                exclude_conditions |= Q(**{f"{field_name}__iexact": value})

        return queryset.exclude(exclude_conditions)

    @staticmethod
    def is_old_model_year(annee: str) -> bool:
        return annee in ["2013", "2014"]

    @staticmethod
    def get_field_names(use_old_model: bool) -> Dict[str, str]:
        return {
            'axe':       "axe" if use_old_model else "axe_updated",
            'programme': "categorie2" if use_old_model else "programme_updated",
            'milieu':    None if use_old_model else "milieu"
        }


# ─────────────────────────────────────────────
#  SERVICE GRAPHIQUES
# ─────────────────────────────────────────────

class ChartDataService:
    """Service pour préparer les données des graphiques"""

    @staticmethod
    def get_beneficiaires_par_milieu(queryset, group_field: str, milieu_field: str,
                                     benef_field: str) -> Tuple[List[str], List[int], List[int]]:
        """✅ OPTIMISÉ : Une seule requête groupée par milieu"""
        queryset = DataFilterService.apply_exclusion_filters(queryset, group_field, 'programme')

        if milieu_field is None:
            data = queryset.values(group_field).annotate(
                total=Sum(benef_field)
            ).order_by(group_field)
            labels = [item[group_field] for item in data if item[group_field]]
            return labels, [0] * len(labels), [0] * len(labels)

        # ✅ Une seule requête groupée (group_field + milieu_field)
        data = queryset.values(group_field, milieu_field).annotate(
            total=Sum(benef_field)
        ).order_by(group_field)

        result = {}
        for item in data:
            label = item[group_field]
            if not label:
                continue
            milieu = (item[milieu_field] or 'Inconnu').lower()
            total  = DataConstants.round_value(item['total'])
            result.setdefault(label, {'urbain': 0, 'rural': 0})
            if 'urb' in milieu:
                result[label]['urbain'] += total
            elif 'rur' in milieu:
                result[label]['rural'] += total

        labels        = list(result.keys())
        urbain_values = [result[l]['urbain'] for l in labels]
        rural_values  = [result[l]['rural']  for l in labels]
        return labels, urbain_values, rural_values

    @staticmethod
    def calculate_centres_data(queryset, use_old_model: bool,
                               field_names: Dict[str, str]) -> Tuple[List[str], List[int]]:
        """Calcule les données des centres par programme"""
        if use_old_model:
            centres_data = Activite.objects.filter(**DataFilterService.build_filters())
            centres_data = DataFilterService.apply_exclusion_filters(centres_data, "categorie2", 'programme')
            centres_data = centres_data.values("categorie2").annotate(
                total_centres=Sum("nb_centres")
            ).order_by("categorie2")
            labels = [d["categorie2"] for d in centres_data if d["categorie2"]]
            values = [DataConstants.round_value(d["total_centres"]) for d in centres_data if d["categorie2"]]
            return labels, values

        excluded_programmes = list(DataConstants.PROGRAMME_CATEGORIE2_MAPPING.keys())
        normal_data = queryset.exclude(programme_updated__in=excluded_programmes)
        normal_data = DataFilterService.apply_exclusion_filters(normal_data, field_names['programme'], 'programme')
        normal_data = normal_data.values(field_names['programme']).annotate(
            total_centres=Count("categorie2")
        ).order_by(field_names['programme'])

        special_data = []
        for prog_name, categorie2_value in DataConstants.PROGRAMME_CATEGORIE2_MAPPING.items():
            if prog_name not in DataConstants.EXCLUDED_VALUES['programme']:
                count = queryset.filter(categorie2=categorie2_value).count()
                if count > 0:
                    special_data.append({
                        field_names['programme']: prog_name,
                        'total_centres': count
                    })

        all_data = list(normal_data) + special_data
        labels   = [d[field_names['programme']] for d in all_data if d[field_names['programme']]]
        values   = [DataConstants.round_value(d['total_centres']) for d in all_data if d[field_names['programme']]]
        return labels, values


# ─────────────────────────────────────────────
#  SERVICE ÉVOLUTION  ✅ OPTIMISÉ
# ─────────────────────────────────────────────

class EvolutionDataService:
    """Service pour les données d'évolution temporelle"""

    @staticmethod
    def get_all_years() -> List[int]:
        """✅ OPTIMISÉ : Années mises en cache 1 heure"""
        cache_key = "all_years_data"
        cached_years = cache.get(cache_key)
        if cached_years is None:
            activite_years = [
                int(y) for y in Activite.objects.values_list("id_periodicite", flat=True).distinct() if y
            ]
            data_years = [
                int(y) for y in Data.objects.values_list("id_periodicite", flat=True).distinct() if y
            ]
            cached_years = sorted(set(activite_years + data_years))
            cache.set(cache_key, cached_years, 3600)
        return cached_years

    @staticmethod
    def get_evolution_data(region: str = None,
                           delegation: str = None) -> Tuple[Dict, Dict, Dict, List[str]]:
        """
        ✅ OPTIMISÉ :
        - Données 2013-2014 : 2 requêtes groupées (au lieu de 2×N)
        - Données 2015+     : 1 seule requête groupée par année (au lieu de N×années)
        - Résultat mis en cache 10 minutes par combinaison région/délégation
        """
        cache_key = f'evolution_data_{region}_{delegation}'
        cached = cache.get(cache_key)
        if cached:
            return cached['prog'], cached['axe'], cached['total'], cached['years']

        all_years     = EvolutionDataService.get_all_years()
        all_years_str = [str(y) for y in all_years]

        evolution_prog = {}
        evolution_axe  = {}

        # ── Données 2013-2014 ─────────────────────────────────────────────

        # ✅ Une seule requête pour toutes les années legacy (programmes)
        qs_activite = Activite.objects.filter(id_periodicite__in=["2013", "2014"])
        qs_activite = DataFilterService.apply_region_delegation_filter(qs_activite, region, delegation)
        qs_activite = DataFilterService.apply_exclusion_filters(qs_activite, "categorie2", 'programme')

        yearly_prog_legacy = qs_activite.values("id_periodicite", "categorie2").annotate(
            hommes=Sum(DataConstants.BENEF_FIELDS['hommes']),
            femmes=Sum(DataConstants.BENEF_FIELDS['femmes']),
            total=Sum(DataConstants.BENEF_FIELDS['total'])
        )
        for item in yearly_prog_legacy:
            year_index = all_years.index(int(item["id_periodicite"]))
            EvolutionDataService._upsert_evolution(
                evolution_prog, item["categorie2"], year_index, item, all_years
            )

        # ✅ Une seule requête pour toutes les années legacy (axes)
        qs_axe_legacy = Data.objects.filter(id_periodicite__in=["2013", "2014"])
        qs_axe_legacy = DataFilterService.apply_region_delegation_filter(qs_axe_legacy, region, delegation)
        qs_axe_legacy = DataFilterService.apply_exclusion_filters(qs_axe_legacy, "axe", 'general')

        yearly_axe_legacy = qs_axe_legacy.values("id_periodicite", "axe").annotate(
            hommes=Sum(DataConstants.BENEF_FIELDS['hommes']),
            femmes=Sum(DataConstants.BENEF_FIELDS['femmes']),
            total=Sum(DataConstants.BENEF_FIELDS['total'])
        )
        for item in yearly_axe_legacy:
            year_index = all_years.index(int(item["id_periodicite"]))
            EvolutionDataService._upsert_evolution(
                evolution_axe, item["axe"], year_index, item, all_years
            )

        # ── Données 2015+ ─────────────────────────────────────────────────

        recent_years = [str(y) for y in all_years if str(y) not in ["2013", "2014"]]

        # ✅ Une seule requête pour TOUS les programmes récents
        qs_prog_recent = Data.objects.filter(id_periodicite__in=recent_years)
        qs_prog_recent = DataFilterService.apply_region_delegation_filter(qs_prog_recent, region, delegation)
        qs_prog_recent = DataFilterService.apply_exclusion_filters(qs_prog_recent, "programme_updated", 'programme')

        yearly_prog_recent = qs_prog_recent.values("id_periodicite", "programme_updated").annotate(
            hommes=Sum(DataConstants.BENEF_FIELDS['hommes']),
            femmes=Sum(DataConstants.BENEF_FIELDS['femmes']),
            total=Sum(DataConstants.BENEF_FIELDS['total'])
        )
        for item in yearly_prog_recent:
            year_index = all_years.index(int(item["id_periodicite"]))
            EvolutionDataService._upsert_evolution(
                evolution_prog, item["programme_updated"], year_index, item, all_years
            )

        # ✅ Une seule requête pour TOUS les axes récents
        qs_axe_recent = Data.objects.filter(id_periodicite__in=recent_years)
        qs_axe_recent = DataFilterService.apply_region_delegation_filter(qs_axe_recent, region, delegation)
        qs_axe_recent = DataFilterService.apply_exclusion_filters(qs_axe_recent, "axe_updated", 'general')

        yearly_axe_recent = qs_axe_recent.values("id_periodicite", "axe_updated").annotate(
            hommes=Sum(DataConstants.BENEF_FIELDS['hommes']),
            femmes=Sum(DataConstants.BENEF_FIELDS['femmes']),
            total=Sum(DataConstants.BENEF_FIELDS['total'])
        )
        for item in yearly_axe_recent:
            year_index = all_years.index(int(item["id_periodicite"]))
            EvolutionDataService._upsert_evolution(
                evolution_axe, item["axe_updated"], year_index, item, all_years
            )

        evolution_total = {**evolution_prog, **evolution_axe}

        # ✅ Mise en cache 10 minutes
        cache.set(cache_key, {
            'prog': evolution_prog,
            'axe':  evolution_axe,
            'total': evolution_total,
            'years': all_years_str
        }, 600)

        return evolution_prog, evolution_axe, evolution_total, all_years_str

    @staticmethod
    def _upsert_evolution(evolution_dict: Dict, key: str, year_index: int,
                          item: Dict, all_years: List[int]):
        """Insère ou met à jour une entrée dans le dictionnaire d'évolution"""
        if not key:
            return
        if key not in evolution_dict:
            evolution_dict[key] = {
                'total':  [0] * len(all_years),
                'hommes': [0] * len(all_years),
                'femmes': [0] * len(all_years)
            }
        evolution_dict[key]['total'][year_index]  = DataConstants.round_value(item['total'])
        evolution_dict[key]['hommes'][year_index] = DataConstants.round_value(item['hommes'])
        evolution_dict[key]['femmes'][year_index] = DataConstants.round_value(item['femmes'])


# ─────────────────────────────────────────────
#  SERVICE MENUS  ✅ OPTIMISÉ
# ─────────────────────────────────────────────

class MenuDataService:
    """Service pour les données des menus déroulants"""

    @staticmethod
    def get_menu_data() -> Dict[str, Any]:
        """✅ OPTIMISÉ : Données converties en list() avant mise en cache"""
        cache_key = "menu_data"
        cached_data = cache.get(cache_key)
        if cached_data is None:
            cached_data = {
                'annees': list(
                    Data.objects.values_list("id_periodicite", flat=True)
                    .distinct().order_by("id_periodicite")
                ),
                'regions': list(
                    Data.objects.values("id_region", "region")
                    .distinct().order_by("region")
                ),
                'delegations': list(
                    Data.objects.values("id_delegation", "delegation", "id_region")
                    .distinct().order_by("delegation")
                )
            }
            cache.set(cache_key, cached_data, 1800)
        return cached_data


# ─────────────────────────────────────────────
#  SERVICE STATISTIQUES  ✅ OPTIMISÉ
# ─────────────────────────────────────────────

class StatisticsService:
    """Service pour les statistiques et KPI"""

    @staticmethod
    def calculate_kpis(queryset, data_queryset, annee: str = None,
                       region: str = None, delegation: str = None) -> Dict[str, int]:
        """
        ✅ OPTIMISÉ : nombre_pop mis en cache car il ne dépend d'aucun filtre.
        """
        if not annee:
            annee = DataConstants.DEFAULT_YEAR

        centres_qs = Centre.objects.filter(id_periodicite=annee)
        if region:
            centres_qs = centres_qs.filter(id_region=region)
        if delegation:
            try:
                centres_qs = centres_qs.filter(id_delegation=int(delegation))
            except (ValueError, TypeError):
                pass

        centres_total = centres_qs.aggregate(total=Sum("nb_centres"))["total"]
        benefic_total = queryset.aggregate(
            total=Sum(DataConstants.BENEF_FIELDS['total'])
        )["total"]

        nombre_axes = data_queryset.exclude(
            axe_updated__isnull=True
        ).values('axe_updated').distinct().count()

        # ✅ nombre_pop indépendant des filtres → mise en cache 1 heure
        nombre_pop = cache.get('nombre_pop_distinct')
        if nombre_pop is None:
            nombre_pop = (
                Data.objects.values("personnes_cibles")
                .distinct()
                .exclude(personnes_cibles__in=['TC', 'tc', 'None', ''])
                .exclude(personnes_cibles__isnull=True)
                .count()
            )
            cache.set('nombre_pop_distinct', nombre_pop, 3600)

        return {
            'centres_count': DataConstants.round_value(centres_total),
            'benefic_count': DataConstants.round_value(benefic_total),
            'nombre_axes':   nombre_axes,
            'nombre_pop':    nombre_pop
        }

    @staticmethod
    def get_programmes_par_axe(data_queryset, use_old_model: bool,
                               field_names: Dict[str, str]) -> Dict[str, List[str]]:
        """
        ✅ OPTIMISÉ : Une seule requête groupée au lieu de requêtes séparées
        pour axes et programmes.
        """
        programmes_par_axe = {}
        data_queryset = DataFilterService.apply_exclusion_filters(
            data_queryset, field_names['axe'], 'general'
        )

        if use_old_model:
            axes_values = list(
                data_queryset.values_list(field_names['axe'], flat=True).distinct()
            )
            activite_qs = Activite.objects.filter(**DataFilterService.build_filters())
            activite_qs = DataFilterService.apply_exclusion_filters(
                activite_qs, field_names['programme'], 'programme'
            )
            programme_list = [
                p for p in activite_qs.values_list(field_names['programme'], flat=True).distinct() if p
            ]
            for axe in axes_values:
                if axe and axe.strip().lower() != "non spécifié":
                    programmes_par_axe[axe] = programme_list
        else:
            # ✅ Une seule requête groupée axe + programme
            data_queryset = DataFilterService.apply_exclusion_filters(
                data_queryset, field_names['programme'], 'programme'
            )
            axe_programmes = data_queryset.values(
                field_names['axe'], field_names['programme']
            ).distinct()

            for item in axe_programmes:
                axe  = item[field_names['axe']]
                prog = item[field_names['programme']]
                if axe and prog and str(axe).strip().lower() != "non spécifié":
                    programmes_par_axe.setdefault(axe, []).append(prog)

        return programmes_par_axe

    @staticmethod
    def get_axes_programmes_classification() -> Dict[str, List[str]]:
        """
        ✅ OPTIMISÉ : Classification axes/programmes anciens et récents
        mise en cache 1 heure (données qui ne changent jamais).
        """
        cache_key = 'axes_programmes_classification'
        cached = cache.get(cache_key)
        if cached:
            return cached

        # Axes anciens
        axes_anciens_qs = Data.objects.filter(id_periodicite__in=["2013", "2014"])
        axes_anciens_qs = DataFilterService.apply_exclusion_filters(axes_anciens_qs, 'axe', 'general')

        # Axes récents
        axes_recents_qs = Data.objects.filter(id_periodicite__gte='2015')
        axes_recents_qs = DataFilterService.apply_exclusion_filters(axes_recents_qs, 'axe_updated', 'general')

        # Programmes anciens
        programmes_anciens_qs = Activite.objects.filter(id_periodicite__in=["2013", "2014"])
        programmes_anciens_qs = DataFilterService.apply_exclusion_filters(
            programmes_anciens_qs, 'categorie2', 'programme'
        )

        # Programmes récents
        programmes_recents_qs = Data.objects.filter(id_periodicite__gte='2015')
        programmes_recents_qs = DataFilterService.apply_exclusion_filters(
            programmes_recents_qs, 'programme_updated', 'programme'
        )

        result = {
            'axes_anciens':       list(set(axes_anciens_qs.values_list('axe', flat=True))),
            'axes_recents':       list(set(axes_recents_qs.values_list('axe_updated', flat=True))),
            'programmes_anciens': list(set(programmes_anciens_qs.values_list('categorie2', flat=True))),
            'programmes_recents': list(set(programmes_recents_qs.values_list('programme_updated', flat=True))),
        }

        # ✅ Cache 1 heure — ces données sont historiques et ne changent pas
        cache.set(cache_key, result, 3600)
        return result


# ─────────────────────────────────────────────
#  VUES
# ─────────────────────────────────────────────

@login_required
def get_delegations_by_region(request):
    """✅ OPTIMISÉ : Vue AJAX avec cache 30 minutes"""
    region_id = request.GET.get('region_id')
    if not region_id:
        return JsonResponse({'delegations': []})

    cache_key = f"delegations_region_{region_id}"
    cached_delegations = cache.get(cache_key)

    if cached_delegations is None:
        delegations = (
            Data.objects.filter(id_region=region_id)
            .values('id_delegation')
            .annotate(delegation_name=Max('delegation'))
            .order_by('delegation_name')
        )
        cached_delegations = [
            {'id_delegation': d['id_delegation'], 'delegation': d['delegation_name']}
            for d in delegations if d['id_delegation']
        ]
        cache.set(cache_key, cached_delegations, 1800)

    return JsonResponse({'delegations': cached_delegations})


@login_required
def list_axe(request):
    """
    ✅ VUE PRINCIPALE OPTIMISÉE :
    - Évolution : 4 requêtes groupées au lieu de 2×N requêtes en boucle
    - Classification axes/programmes mise en cache 1 heure
    - nombre_pop mis en cache 1 heure
    - Contexte complet mis en cache 10 minutes par combinaison de filtres
    - menu_data converti en list() avant mise en cache
    """
    selected_annee      = request.GET.get("annee") or DataConstants.DEFAULT_YEAR
    selected_region     = request.GET.get("region")
    selected_delegation = request.GET.get("delegation")

    # ─── Clé de cache unique ──────────────────────────────────────────────
    cache_key = f'dashboard_axe_{selected_annee}_{selected_region}_{selected_delegation}'
    context   = cache.get(cache_key)

    if context is None:

        filters        = DataFilterService.build_filters(selected_annee, selected_region, selected_delegation)
        use_old_model  = DataFilterService.is_old_model_year(selected_annee)
        field_names    = DataFilterService.get_field_names(use_old_model)

        # ✅ Querysets de base
        queryset_programme = (Activite if use_old_model else Data).objects.filter(**filters)
        queryset_programme = DataFilterService.apply_exclusion_filters(
            queryset_programme, field_names['programme'], 'programme'
        )

        data_queryset = Data.objects.filter(**filters)
        data_queryset = DataFilterService.apply_exclusion_filters(
            data_queryset, field_names['axe'], 'general'
        )

        # ✅ Menus (cachés 30 min)
        menu_data = MenuDataService.get_menu_data()

        # ── Graphiques ────────────────────────────────────────────────────

        # Bénéficiaires axe/milieu — 1 requête groupée
        labels_axe_milieu, urbain_axe, rural_axe = ChartDataService.get_beneficiaires_par_milieu(
            data_queryset, field_names['axe'], "milieu", DataConstants.BENEF_FIELDS['total']
        )

        # Bénéficiaires programme/milieu — 1 requête groupée
        labels_prog_milieu, urbain_prog, rural_prog = ChartDataService.get_beneficiaires_par_milieu(
            queryset_programme, field_names['programme'],
            field_names['milieu'], DataConstants.BENEF_FIELDS['total']
        )

        # Bénéficiaires par axe (total + genre) — 1 requête
        benef_data = data_queryset.values(field_names['axe']).annotate(
            total_benef=Sum(DataConstants.BENEF_FIELDS['total']),
            total_benef_f=Sum(DataConstants.BENEF_FIELDS['femmes']),
            total_benef_m=Sum(DataConstants.BENEF_FIELDS['hommes']),
        ).order_by(field_names['axe'])

        axes          = [d[field_names['axe']] for d in benef_data if d[field_names['axe']]]
        totals        = [DataConstants.round_value(d['total_benef'])   for d in benef_data if d[field_names['axe']]]
        totals_femmes = [DataConstants.round_value(d['total_benef_f']) for d in benef_data if d[field_names['axe']]]
        totals_hommes = [DataConstants.round_value(d['total_benef_m']) for d in benef_data if d[field_names['axe']]]

        # Centres par programme — 1 requête
        centres_qs = Data.objects.filter(**filters) if not use_old_model else queryset_programme
        prog_centres_labels, prog_centres_values = ChartDataService.calculate_centres_data(
            centres_qs, use_old_model, field_names
        )

        # Centres par axe — 1 requête
        if use_old_model:
            centres_data = Axe.objects.filter(**filters)
            centres_data = DataFilterService.apply_exclusion_filters(centres_data, "axe", 'general')
            centres_data = list(centres_data.values("axe").annotate(
                total_centres=Sum("nb_centres")
            ).order_by("axe"))
            axes_centres_labels = [d["axe"] for d in centres_data if d["axe"]]
        else:
            centres_data = list(data_queryset.values(field_names['axe']).annotate(
                total_centres=Count("nb_centres")
            ).order_by(field_names['axe']))
            axes_centres_labels = [d[field_names['axe']] for d in centres_data if d[field_names['axe']]]

        axes_centres_values = [
            DataConstants.round_value(d["total_centres"]) for d in centres_data
            if d.get(field_names['axe'] if not use_old_model else "axe")
        ]

        # Bénéficiaires par programme (doughnut + genre) — 1 requête
        programme_data = list(queryset_programme.values(field_names['programme']).annotate(
            total=Sum(DataConstants.BENEF_FIELDS['total']),
            hommes=Sum(DataConstants.BENEF_FIELDS['hommes']),
            femmes=Sum(DataConstants.BENEF_FIELDS['femmes'])
        ))

        doughnut_data, sexe_data = {}, {}
        for item in programme_data:
            prog = item[field_names['programme']]
            if not prog:
                continue
            t = DataConstants.round_value(item['total'])
            h = DataConstants.round_value(item['hommes'])
            f = DataConstants.round_value(item['femmes'])
            doughnut_data[prog] = doughnut_data.get(prog, 0) + t
            sexe_data.setdefault(prog, {'hommes': 0, 'femmes': 0})
            sexe_data[prog]['hommes'] += h
            sexe_data[prog]['femmes'] += f

        chart_labels       = list(doughnut_data.keys())
        chart_data         = list(doughnut_data.values())
        chart_sexe_labels  = list(sexe_data.keys())
        chart_sexe_hommes  = [v['hommes'] for v in sexe_data.values()]
        chart_sexe_femmes  = [v['femmes'] for v in sexe_data.values()]

        # Centres par programme (count) — 1 requête
        centres_counts      = list(queryset_programme.values(field_names['programme']).annotate(
            total=Count(field_names['programme'])
        ))
        chart_centres_labels = [i[field_names['programme']] for i in centres_counts if i[field_names['programme']]]
        chart_centres_counts = [DataConstants.round_value(i['total']) for i in centres_counts if i[field_names['programme']]]

        # ── KPIs ─────────────────────────────────────────────────────────
        kpis = StatisticsService.calculate_kpis(
            queryset_programme, data_queryset,
            selected_annee, selected_region, selected_delegation
        )

        # ── Programmes par axe ────────────────────────────────────────────
        programmes_par_axe = StatisticsService.get_programmes_par_axe(
            data_queryset, use_old_model, field_names
        )

        # ── Évolution ✅ 4 requêtes groupées au lieu de 2×N ───────────────
        evolution_sexe_programme, evolution_sexe_axe, evolution_sexe_total, all_years_str = \
            EvolutionDataService.get_evolution_data(selected_region, selected_delegation)

        # ── Classification axes/programmes ✅ mis en cache 1 heure ────────
        classification = StatisticsService.get_axes_programmes_classification()

        # ── Contexte final ────────────────────────────────────────────────
        context = {
            # Menus
            "annees":      menu_data['annees'],
            "regions":     menu_data['regions'],
            "delegations": menu_data['delegations'],
            "selected_annee":      selected_annee,
            "selected_region":     selected_region,
            "selected_delegation": selected_delegation,

            # Axes — bénéficiaires
            "axes":          axes,
            "totals":        totals,
            "totals_hommes": totals_hommes,
            "totals_femmes": totals_femmes,

            # Axes — centres
            "axes_centres_labels": json.dumps(axes_centres_labels),
            "axes_centres_values": json.dumps(axes_centres_values),

            # Programmes — centres
            "prog_centres_labels": json.dumps(prog_centres_labels),
            "prog_centres_values": json.dumps(prog_centres_values),

            # Programmes — bénéficiaires
            "chart_labels":        chart_labels,
            "chart_data":          chart_data,
            "chart_sexe_labels":   chart_sexe_labels,
            "chart_sexe_hommes":   chart_sexe_hommes,
            "chart_sexe_femmes":   chart_sexe_femmes,
            "chart_centres_labels": chart_centres_labels,
            "chart_centres_counts": chart_centres_counts,

            # Milieu
            "labels_axe_milieu":  json.dumps(labels_axe_milieu),
            "urbain_axe":         json.dumps(urbain_axe),
            "rural_axe":          json.dumps(rural_axe),
            "labels_prog_milieu": json.dumps(labels_prog_milieu),
            "urbain_prog":        json.dumps(urbain_prog),
            "rural_prog":         json.dumps(rural_prog),

            # Relations et évolution
            "programmes_par_axe":      programmes_par_axe,
            "evolution_sexe_programme": evolution_sexe_programme,
            "evolution_sexe_axe":       evolution_sexe_axe,
            "evolution_sexe_total":     json.dumps(evolution_sexe_total),
            "labels_annees":            all_years_str,

            # Classification
            "axes_anciens":       classification['axes_anciens'],
            "axes_recents":       classification['axes_recents'],
            "programmes_anciens": classification['programmes_anciens'],
            "programmes_recents": classification['programmes_recents'],

            # KPIs
            **kpis
        }

        # ✅ Mise en cache 10 minutes
        cache.set(cache_key, context, 600)

    return render(request, "axe.html", context)