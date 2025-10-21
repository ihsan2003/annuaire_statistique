from django.shortcuts import render
from django.db.models import Count, Sum, Max, Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from .models import Data, Axe, Activite, Centre
import json
from typing import Dict, List, Tuple, Any, Optional, Union


class DataConstants:
    """Configuration centralisée pour les mappings et constantes"""
    
    # Mapping des programmes vers categorie2
    PROGRAMME_CATEGORIE2_MAPPING = {
        "Centres d'Assistance Sociale (CAS)": "Centre d'assistance sociale ( CAS )",
        "Centre d'Orientation et d'Assistance pour les Personnes Handicapées (COAPH)": "COAPH",
        "Centres d'Accompagnement pour la Protection de l'Enfance (CAPE)": "Unité de Protection de l'Enfance (UPE)",
        "Espace Multifonctionnel de la Femme (EMF)": "Espace Multifonctionnel de la Femme (EMF)"
    }
    
    # Labels legacy pour compatibilité
    CAS_LABELS = {
        "Centre d'assistance sociale ( CAS )",
        "Cellule d'assistance sociale ( CAS )",
        "CAS1"
    }
    
    CAPE_LABELS = {
        "Unité de Protection de l'Enfance (UPE)",
        "Cellule d'unité de Protection de l'Enfance (UPE)"
    }
    
    COAPH_LABELS = {
        "COAPH",
        "Centre d'Orientation et Assistance pour Personnes en situation d'Handicap (COAPH)"
    }
    
    EMF_LABELS = {
        "Espace Multifonctionnel de la Femme (EMF)"
    }
    
    SPECIAL_PROGRAMMES = {
        "Centres d'Assistance Sociale (CAS)": CAS_LABELS,
        "Centres d'Accompagnement pour la Protection de l'Enfance (CAPE)": CAPE_LABELS,
        "Centre d'Orientation et d'Assistance pour les Personnes Handicapées (COAPH)": COAPH_LABELS,
    }
    
    # Champs des bénéficiaires
    BENEF_FIELDS = {
        'total': 'nb_beneficiaires_t',
        'femmes': 'nb_beneficiaires_f',
        'hommes': 'nb_beneficiaires_m'
    }
    
    # Valeurs à exclure
    EXCLUDED_VALUES = {
        'general': ['Non spécifié', 'non specifie', 'Non specifié', 'non spécifié', '', None],
        'programme': ['SDF', 'sdf'],
        'population': ['TC', 'tc']
    }

    DEFAULT_YEAR = '2022'

    @classmethod
    def round_value(cls, value: Union[float, int, None]) -> int:
        """
        Arrondit une valeur à l'entier le plus proche
        
        Args:
            value: La valeur à arrondir (peut être None)
            
        Returns:
            int: La valeur arrondie à l'entier
        """
        if value is None:
            return 0
        return round(float(value))


class DataFilterService:
    """Service pour gérer les filtres et requêtes"""
    
    @staticmethod
    def build_filters(annee: str = None, region: str = None, delegation: str = None) -> Dict[str, Any]:
        """Construit le dictionnaire de filtres pour les requêtes"""
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
        """Applique les filtres région et délégation à un queryset"""
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
        """Applique les filtres d'exclusion selon le type"""
        excluded_values = DataConstants.EXCLUDED_VALUES['general'].copy()
        
        if filter_type == 'programme':
            excluded_values.extend(DataConstants.EXCLUDED_VALUES['programme'])
        elif filter_type == 'population':
            excluded_values.extend(DataConstants.EXCLUDED_VALUES['population'])
        
        # Créer les conditions d'exclusion
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
        """Détermine s'il faut utiliser l'ancien modèle"""
        return annee in ["2013", "2014"]
    
    @staticmethod
    def get_field_names(use_old_model: bool) -> Dict[str, str]:
        """Retourne les noms des champs selon le modèle utilisé"""
        return {
            'axe': "axe" if use_old_model else "axe_updated",
            'programme': "categorie2" if use_old_model else "programme_updated",
            'milieu': None if use_old_model else "milieu"
        }


class ChartDataService:
    """Service pour préparer les données des graphiques"""
    
    @staticmethod
    def filter_chart_data(labels: List[str], *data_arrays) -> Tuple[List[str], ...]:
        """Filtre les données des graphiques pour exclure les valeurs non désirées"""
        excluded_values = DataConstants.EXCLUDED_VALUES['general'] + DataConstants.EXCLUDED_VALUES['programme']
        
        filtered_indices = [
            i for i, label in enumerate(labels) 
            if label and label not in excluded_values and label.lower() not in [v.lower() if v else '' for v in excluded_values]
        ]
        
        filtered_labels = [labels[i] for i in filtered_indices]
        filtered_arrays = []
        
        for data_array in data_arrays:
            filtered_arrays.append([data_array[i] for i in filtered_indices])
        
        return (filtered_labels, *filtered_arrays)
        
    @staticmethod
    def get_beneficiaires_par_milieu(queryset, group_field: str, milieu_field: str, benef_field: str) -> Tuple[List[str], List[int], List[int]]:
        """Calcule la répartition des bénéficiaires par milieu"""
        # Appliquer les filtres d'exclusion
        queryset = DataFilterService.apply_exclusion_filters(queryset, group_field, 'programme')
        
        if milieu_field is None:
            data = queryset.values(group_field).annotate(total=Sum(benef_field)).order_by(group_field)
            labels = [item[group_field] for item in data if item[group_field]]
            urbain_values = [0] * len(labels)
            rural_values = [0] * len(labels)
            return labels, urbain_values, rural_values

        data = queryset.values(group_field, milieu_field).annotate(total=Sum(benef_field)).order_by(group_field)

        result = {}
        for item in data:
            label = item[group_field]
            if not label:
                continue
                
            milieu = item[milieu_field] or "Inconnu"
            total = DataConstants.round_value(item["total"])  # Arrondi appliqué

            result.setdefault(label, {"urbain": 0, "rural": 0})
            if "rur" in milieu.lower():
                result[label]["rural"] += total
            elif "urb" in milieu.lower():
                result[label]["urbain"] += total

        labels = list(result.keys())
        urbain_values = [result[l]["urbain"] for l in labels]
        rural_values = [result[l]["rural"] for l in labels]
        return labels, urbain_values, rural_values

    @staticmethod
    def calculate_centres_data(queryset, use_old_model: bool, field_names: Dict[str, str]) -> Tuple[List[str], List[int]]:
        """Calcule les données des centres par programme"""
        if use_old_model:
            centres_data = Activite.objects.filter(**DataFilterService.build_filters())
            centres_data = DataFilterService.apply_exclusion_filters(centres_data, "categorie2", 'programme')
            centres_data = centres_data.values("categorie2")\
                .annotate(total_centres=Sum("nb_centres")).order_by("categorie2")
            labels = [d["categorie2"] for d in centres_data if d["categorie2"]]
            values = [DataConstants.round_value(d["total_centres"]) for d in centres_data if d["categorie2"]]
            return labels, values
        
        # Programmes normaux
        excluded_programmes = list(DataConstants.PROGRAMME_CATEGORIE2_MAPPING.keys())
        normal_programmes_data = queryset.exclude(programme_updated__in=excluded_programmes)
        normal_programmes_data = DataFilterService.apply_exclusion_filters(normal_programmes_data, field_names['programme'], 'programme')
        normal_programmes_data = normal_programmes_data.values(field_names['programme'])\
            .annotate(total_centres=Count("categorie2"))\
            .order_by(field_names['programme'])

        # Programmes spéciaux - CORRECTION APPLIQUÉE
        special_data = []
        for prog_name, categorie2_value in DataConstants.PROGRAMME_CATEGORIE2_MAPPING.items():
            if prog_name not in DataConstants.EXCLUDED_VALUES['programme']:
                # Utiliser Count('id') au lieu de Count('nb_centres')
                count = queryset.filter(categorie2=categorie2_value).count()
                
                if count > 0:
                    special_data.append({
                        field_names['programme']: prog_name,
                        "total_centres": count  # Déjà un entier, pas besoin d'arrondir
                    })

        # Fusion des données
        all_data = list(normal_programmes_data) + special_data
        labels = [d[field_names['programme']] for d in all_data if d[field_names['programme']]]
        values = [DataConstants.round_value(d["total_centres"]) for d in all_data if d[field_names['programme']]]
        
        return labels, values

class EvolutionDataService:
    """Service pour les données d'évolution temporelle"""
    
    @staticmethod
    def get_all_years() -> List[int]:
        """Récupère toutes les années disponibles"""
        cache_key = "all_years_data"
        cached_years = cache.get(cache_key)
        
        if cached_years is None:
            activite_years = [int(y) for y in Activite.objects.values_list("id_periodicite", flat=True).distinct() if y]
            data_years = [int(y) for y in Data.objects.values_list("id_periodicite", flat=True).distinct() if y]
            cached_years = sorted(set(activite_years + data_years))
            cache.set(cache_key, cached_years, 3600)  
        
        return cached_years
    
    @staticmethod
    def get_evolution_data(region: str = None, delegation: str = None) -> Tuple[Dict, Dict, Dict, List[str]]:
        """Calcule l'évolution des données par année"""
        all_years = EvolutionDataService.get_all_years()
        all_years_str = [str(y) for y in all_years]
        
        evolution_prog = {}
        evolution_axe = {}
        
        # Données 2013-2014
        for year in ["2013", "2014"]:
            year_index = all_years.index(int(year))
            
            # Programmes
            qs_activite = Activite.objects.filter(id_periodicite=year)
            qs_activite = DataFilterService.apply_region_delegation_filter(qs_activite, region, delegation)
            qs_activite = DataFilterService.apply_exclusion_filters(qs_activite, "categorie2", 'programme')
            
            yearly_prog = qs_activite.values("categorie2").annotate(
                hommes=Sum(DataConstants.BENEF_FIELDS['hommes']),
                femmes=Sum(DataConstants.BENEF_FIELDS['femmes']),
                total=Sum(DataConstants.BENEF_FIELDS['total'])
            )
            
            EvolutionDataService._process_yearly_data(yearly_prog, evolution_prog, "categorie2", year_index, all_years)
            
            # Axes
            qs_data = Data.objects.filter(id_periodicite=year)
            qs_data = DataFilterService.apply_region_delegation_filter(qs_data, region, delegation)
            qs_data = DataFilterService.apply_exclusion_filters(qs_data, "axe", 'general')
            
            yearly_axe = qs_data.values("axe").annotate(
                hommes=Sum(DataConstants.BENEF_FIELDS['hommes']),
                femmes=Sum(DataConstants.BENEF_FIELDS['femmes']),
                total=Sum(DataConstants.BENEF_FIELDS['total'])
            )
            
            EvolutionDataService._process_yearly_data(yearly_axe, evolution_axe, "axe", year_index, all_years)
        
        # Données 2015+
        for year in [y for y in all_years if str(y) not in ["2013", "2014"]]:
            year_index = all_years.index(year)
            
            qs = Data.objects.filter(id_periodicite=str(year))
            qs = DataFilterService.apply_region_delegation_filter(qs, region, delegation)
            
            # Programmes
            qs_prog = DataFilterService.apply_exclusion_filters(qs, "programme_updated", 'programme')
            yearly_prog = qs_prog.values("programme_updated").annotate(
                hommes=Sum(DataConstants.BENEF_FIELDS['hommes']),
                femmes=Sum(DataConstants.BENEF_FIELDS['femmes']),
                total=Sum(DataConstants.BENEF_FIELDS['total'])
            )
            
            EvolutionDataService._process_yearly_data(yearly_prog, evolution_prog, "programme_updated", year_index, all_years)
            
            # Axes
            qs_axe = DataFilterService.apply_exclusion_filters(qs, "axe_updated", 'general')
            yearly_axe = qs_axe.values("axe_updated").annotate(
                hommes=Sum(DataConstants.BENEF_FIELDS['hommes']),
                femmes=Sum(DataConstants.BENEF_FIELDS['femmes']),
                total=Sum(DataConstants.BENEF_FIELDS['total'])
            )
            
            EvolutionDataService._process_yearly_data(yearly_axe, evolution_axe, "axe_updated", year_index, all_years)
        
        evolution_total = {**evolution_prog, **evolution_axe}
        
        return evolution_prog, evolution_axe, evolution_total, all_years_str

    @staticmethod
    def _process_yearly_data(yearly_data, evolution_dict: Dict, key_field: str, year_index: int, all_years: List[int]):
        """Traite les données annuelles pour l'évolution avec arrondi"""
        for item in yearly_data:
            key = item[key_field]
            if not key:  # Skip si vide/None
                continue
            
            if key not in evolution_dict:
                evolution_dict[key] = {
                    'total': [0] * len(all_years),
                    'hommes': [0] * len(all_years),
                    'femmes': [0] * len(all_years)
                }
            
            # Arrondi appliqué aux valeurs d'évolution
            evolution_dict[key]['total'][year_index] = DataConstants.round_value(item["total"])
            evolution_dict[key]['hommes'][year_index] = DataConstants.round_value(item["hommes"])
            evolution_dict[key]['femmes'][year_index] = DataConstants.round_value(item["femmes"])


class MenuDataService:
    """Service pour les données des menus déroulants"""
    
    @staticmethod
    def get_menu_data() -> Dict[str, Any]:
        """Récupère les données pour les menus déroulants"""
        cache_key = "menu_data"
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            cached_data = {
                'annees': Data.objects.values_list("id_periodicite", flat=True).distinct().order_by("id_periodicite"),
                'regions': Data.objects.values("id_region", "region").distinct().order_by("region"),
                'delegations': Data.objects.values("id_delegation", "delegation", "id_region").distinct().order_by("delegation")
            }
            cache.set(cache_key, cached_data, 1800)  # Cache 30 minutes
        
        return cached_data


class StatisticsService:
    """Service pour les statistiques et KPI"""
    
    def calculate_kpis(queryset, data_queryset, annee: str = None, region: str = None, delegation: str = None) -> Dict[str, int]:
        """Calcule les KPIs principaux avec arrondi - utilise le modèle Centre"""
        
        # Calcul des centres à partir du modèle Centre
        centres_queryset = Centre.objects.all()
        
        # Application des filtres sur le modèle Centre selon les champs disponibles
        if annee:
            centres_queryset = centres_queryset.filter(id_periodicite=annee)
        if region:
            centres_queryset = centres_queryset.filter(id_region=region)
        if delegation:
            try:
                centres_queryset = centres_queryset.filter(id_delegation=int(delegation))
            except (ValueError, TypeError):
                pass
        
        # CORRECTION: Si aucune année n'est fournie, utiliser l'année par défaut
        if not annee:
            annee = DataConstants.DEFAULT_YEAR
        
        # Appliquer le filtre par année (soit celle fournie, soit celle par défaut)
        centres_queryset = centres_queryset.filter(id_periodicite=annee)
        
        # Compte total des centres - utilise le champ nb_centres du modèle Centre
        centres_total = centres_queryset.aggregate(total=Sum("nb_centres"))["total"]
        
        # Calcul des bénéficiaires (reste inchangé)
        benefic_total = queryset.aggregate(total=Sum(DataConstants.BENEF_FIELDS['total']))["total"]
        
        return {
            'centres_count': DataConstants.round_value(centres_total),
            'benefic_count': DataConstants.round_value(benefic_total),
            'nombre_axes': data_queryset.exclude(axe_updated__isnull=True).values('axe_updated').distinct().count(),
            'nombre_pop': Data.objects.values("personnes_cibles").distinct().exclude(personnes_cibles__in =['TC', 'tc', 'None', '']).exclude(personnes_cibles__isnull=True).count()
        }
    @staticmethod
    def get_programmes_par_axe(data_queryset, use_old_model: bool, field_names: Dict[str, str]) -> Dict[str, List[str]]:
        """Récupère les programmes par axe"""
        programmes_par_axe = {}
        
        # Appliquer les filtres d'exclusion
        data_queryset = DataFilterService.apply_exclusion_filters(data_queryset, field_names['axe'], 'general')
        
        if use_old_model:
            axes_values = data_queryset.values_list(field_names['axe'], flat=True).distinct()
            
            activite_qs = Activite.objects.filter(**DataFilterService.build_filters())
            activite_qs = DataFilterService.apply_exclusion_filters(activite_qs, field_names['programme'], 'programme')
            programmes_values = activite_qs.values_list(field_names['programme'], flat=True).distinct()
            programme_list = [p for p in programmes_values if p]
            
            for axe in axes_values:
                if axe and axe.strip().lower() != "non spécifié":
                    programmes_par_axe[axe] = programme_list
        else:
            data_queryset = DataFilterService.apply_exclusion_filters(data_queryset, field_names['programme'], 'programme')
            axe_programmes = data_queryset.values(field_names['axe'], field_names['programme']).distinct()
            
            for item in axe_programmes:
                axe = item[field_names['axe']]
                prog = item[field_names['programme']]
                
                if axe and prog and str(axe).strip().lower() != "non spécifié":
                    programmes_par_axe.setdefault(axe, []).append(prog)
        
        return programmes_par_axe


@login_required
def get_delegations_by_region(request):
    """Vue AJAX pour récupérer les délégations d'une région"""
    region_id = request.GET.get('region_id')
    
    if not region_id:
        return JsonResponse({'delegations': []})
    
    cache_key = f"delegations_region_{region_id}"
    cached_delegations = cache.get(cache_key)
    
    if cached_delegations is None:
        delegations = Data.objects.filter(id_region=region_id)\
            .values('id_delegation')\
            .annotate(delegation_name=Max('delegation'))\
            .order_by('delegation_name')
        
        cached_delegations = [
            {'id_delegation': d['id_delegation'], 'delegation': d['delegation_name']}
            for d in delegations if d['id_delegation']
        ]
        cache.set(cache_key, cached_delegations, 1800)  # Cache 30 minutes
    
    return JsonResponse({'delegations': cached_delegations})


@login_required
def list_axe(request):
    """Vue principale pour les axes et programmes - Version optimisée avec filtres"""
    
    # Récupération des paramètres
    selected_annee = request.GET.get("annee") or '2022'
    selected_region = request.GET.get("region")
    selected_delegation = request.GET.get("delegation")
    
    # Configuration des filtres et modèles
    filters = DataFilterService.build_filters(selected_annee, selected_region, selected_delegation)
    use_old_model = DataFilterService.is_old_model_year(selected_annee)
    field_names = DataFilterService.get_field_names(use_old_model)
    
    # Requêtes de base avec filtres d'exclusion
    queryset_programme = (Activite if use_old_model else Data).objects.filter(**filters)
    queryset_programme = DataFilterService.apply_exclusion_filters(queryset_programme, field_names['programme'], 'programme')
    
    data_queryset = Data.objects.filter(**filters)
    data_queryset = DataFilterService.apply_exclusion_filters(data_queryset, field_names['axe'], 'general')
    
    # Données des menus
    menu_data = MenuDataService.get_menu_data()
    
    # === DONNÉES DES GRAPHIQUES ===
    
    # Bénéficiaires par axe et milieu (déjà géré dans ChartDataService)
    labels_axe_milieu, urbain_axe, rural_axe = ChartDataService.get_beneficiaires_par_milieu(
        data_queryset, field_names['axe'], "milieu", DataConstants.BENEF_FIELDS['total']
    )

    # Bénéficiaires par programme et milieu (déjà géré dans ChartDataService)
    labels_prog_milieu, urbain_prog, rural_prog = ChartDataService.get_beneficiaires_par_milieu(
        queryset_programme, field_names['programme'], field_names['milieu'], DataConstants.BENEF_FIELDS['total']
    )

    # Données bénéficiaires par axe AVEC ARRONDI
    benef_data = data_queryset.values(field_names['axe']).annotate(
        total_benef=Sum(DataConstants.BENEF_FIELDS['total']),
        total_benef_f=Sum(DataConstants.BENEF_FIELDS['femmes']),
        total_benef_m=Sum(DataConstants.BENEF_FIELDS['hommes']),
    ).order_by(field_names['axe'])

    axes = [d[field_names['axe']] for d in benef_data if d[field_names['axe']]]
    totals = [DataConstants.round_value(d["total_benef"]) for d in benef_data if d[field_names['axe']]]
    totals_femmes = [DataConstants.round_value(d["total_benef_f"]) for d in benef_data if d[field_names['axe']]]
    totals_hommes = [DataConstants.round_value(d["total_benef_m"]) for d in benef_data if d[field_names['axe']]]

    # Centres par programme et par axe (déjà géré dans ChartDataService)
    centres_queryset = Data.objects.filter(**filters) if not use_old_model else queryset_programme
    prog_centres_labels, prog_centres_values = ChartDataService.calculate_centres_data(
        centres_queryset, 
        use_old_model, 
        field_names
    )

    # Centres par axe AVEC ARRONDI
    if use_old_model:
        centres_data = Axe.objects.filter(**filters)
        centres_data = DataFilterService.apply_exclusion_filters(centres_data, "axe", 'general')
        centres_data = centres_data.values("axe").annotate(total_centres=Sum("nb_centres")).order_by("axe")
        axes_centres_labels = [d["axe"] for d in centres_data if d["axe"]]
    else:
        centres_data = data_queryset.values(field_names['axe'])\
            .annotate(total_centres=Count("nb_centres")).order_by(field_names['axe'])
        axes_centres_labels = [d[field_names['axe']] for d in centres_data if d[field_names['axe']]]

    axes_centres_values = [DataConstants.round_value(d["total_centres"]) for d in centres_data 
                        if d.get(field_names['axe'] if not use_old_model else "axe")]

    # === DONNÉES POUR LES GRAPHIQUES DE PROGRAMMES AVEC ARRONDI ===

    programme_data = queryset_programme.values(field_names['programme']).annotate(
        total=Sum(DataConstants.BENEF_FIELDS['total']),
        hommes=Sum(DataConstants.BENEF_FIELDS['hommes']),
        femmes=Sum(DataConstants.BENEF_FIELDS['femmes'])
    )

    doughnut_data = {}
    sexe_data = {}

    for item in programme_data:
        prog = item[field_names['programme']]
        if not prog:
            continue
            
        # Application de l'arrondi
        total_rounded = DataConstants.round_value(item["total"])
        hommes_rounded = DataConstants.round_value(item["hommes"])
        femmes_rounded = DataConstants.round_value(item["femmes"])
        
        doughnut_data[prog] = doughnut_data.get(prog, 0) + total_rounded
        sexe_data.setdefault(prog, {"hommes": 0, "femmes": 0})
        sexe_data[prog]["hommes"] += hommes_rounded
        sexe_data[prog]["femmes"] += femmes_rounded

    chart_labels = list(doughnut_data.keys())
    chart_data = list(doughnut_data.values())  # Déjà arrondies
    chart_sexe_labels = list(sexe_data.keys())
    chart_sexe_hommes = [v["hommes"] for v in sexe_data.values()]  # Déjà arrondies
    chart_sexe_femmes = [v["femmes"] for v in sexe_data.values()]  # Déjà arrondies

    centres_counts = queryset_programme.values(field_names['programme']).annotate(total=Count(field_names['programme']))
    chart_centres_labels = [item[field_names['programme']] for item in centres_counts if item[field_names['programme']]]
    chart_centres_counts = [DataConstants.round_value(item["total"]) for item in centres_counts 
                        if item[field_names['programme']]]
    
    # === DONNÉES COMPLÉMENTAIRES ===
    
    # KPIs
    kpis = StatisticsService.calculate_kpis(queryset_programme, data_queryset, selected_annee, selected_region, selected_delegation)
    
    # Programmes par axe
    programmes_par_axe = StatisticsService.get_programmes_par_axe(data_queryset, use_old_model, field_names)
    
    # Évolution temporelle
    evolution_sexe_programme, evolution_sexe_axe, evolution_sexe_total, all_years_str = \
        EvolutionDataService.get_evolution_data(selected_region, selected_delegation)
    
    # Clés pour les anciens/nouveaux axes et programmes (avec filtres)
    axes_anciens_qs = Data.objects.filter(id_periodicite__in=["2013", "2014"])
    axes_anciens_qs = DataFilterService.apply_exclusion_filters(axes_anciens_qs, 'axe', 'general')
    axes_anciens = set(axes_anciens_qs.values_list('axe', flat=True))
    
    axes_recents_qs = Data.objects.filter(id_periodicite__gte='2015')
    axes_recents_qs = DataFilterService.apply_exclusion_filters(axes_recents_qs, 'axe_updated', 'general')
    axes_recents = set(axes_recents_qs.values_list('axe_updated', flat=True))
    
    programmes_anciens_qs = Activite.objects.filter(id_periodicite__in=["2013", "2014"])
    programmes_anciens_qs = DataFilterService.apply_exclusion_filters(programmes_anciens_qs, 'categorie2', 'programme')
    programmes_anciens = set(programmes_anciens_qs.values_list('categorie2', flat=True))
    
    programmes_recents_qs = Data.objects.filter(id_periodicite__gte='2015')
    programmes_recents_qs = DataFilterService.apply_exclusion_filters(programmes_recents_qs, 'programme_updated', 'programme')
    programmes_recents = set(programmes_recents_qs.values_list('programme_updated', flat=True))
    
    # === CONTEXTE DE RENDU ===
    
    context = {
        "data": queryset_programme,
        "annees": menu_data['annees'],
        "regions": menu_data['regions'],
        "delegations": menu_data['delegations'],
        "selected_annee": selected_annee,
        "selected_region": selected_region,
        "selected_delegation": selected_delegation,
        
        # Données des axes
        "axes": axes,
        "totals": totals,
        "totals_hommes": totals_hommes,
        "totals_femmes": totals_femmes,
        "axes_centres_labels": json.dumps(axes_centres_labels),
        "axes_centres_values": json.dumps(axes_centres_values),
        
        # Données des programmes
        "prog_centres_labels": json.dumps(prog_centres_labels),
        "prog_centres_values": json.dumps(prog_centres_values),
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        "chart_sexe_labels": chart_sexe_labels,
        "chart_sexe_hommes": chart_sexe_hommes,
        "chart_sexe_femmes": chart_sexe_femmes,
        "chart_centres_labels": chart_centres_labels,
        "chart_centres_counts": chart_centres_counts,
        
        # Données milieu
        "labels_axe_milieu": json.dumps(labels_axe_milieu),
        "urbain_axe": json.dumps(urbain_axe),
        "rural_axe": json.dumps(rural_axe),
        "labels_prog_milieu": json.dumps(labels_prog_milieu),
        "urbain_prog": json.dumps(urbain_prog),
        "rural_prog": json.dumps(rural_prog),
        
        # Relations et évolution
        "programmes_par_axe": programmes_par_axe,
        'evolution_sexe_programme': evolution_sexe_programme,
        'evolution_sexe_axe': evolution_sexe_axe,
        'evolution_sexe_total': json.dumps(evolution_sexe_total),
        'labels_annees': all_years_str,
        
        # Classification des données
        'axes_anciens': list(axes_anciens),
        'axes_recents': list(axes_recents),
        'programmes_anciens': list(programmes_anciens),
        'programmes_recents': list(programmes_recents),
        
        # KPIs
        **kpis
    }
    
    return render(request, "axe.html", context)