from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.shortcuts import render
from django.db.models import Sum, Max, Q, QuerySet, Case, When, IntegerField, F
from django.http import JsonResponse
from django.core.cache import cache
from .models import Data
import json
from typing import Dict, List, Any, Optional, Union


class BeneficiaryDataService:
    """Service pour gérer les données des bénéficiaires avec logique métier centralisée"""
    
    # Configuration des pondérations pour la population cible "TC" (2022 et plus)
    TC_PONDERATIONS = {
        "Enfants en situation difficile": 0.28,
        "Femmes en situation difficile": 0.28,
        "Personnes en situation de handicap": 0.27,
        "Personnes âgées en situation difficile": 0.17
    }

    # Pondération uniforme pour les années 2021 et moins
    TC_PONDERATION_LEGACY = {
        "Enfants en situation difficile": 0.25,
        "Femmes en situation difficile": 0.25,
        "Personnes en situation de handicap": 0.25,
        "Personnes âgées en situation difficile": 0.25
    }
    
    DEFAULT_YEAR = '2022'
    
    # Mapping des filtres vers les champs de base de données
    FILTER_MAPPING = {
        'total': 'nb_beneficiaires_t',
        'hommes': 'nb_beneficiaires_m',
        'femmes': 'nb_beneficiaires_f',
        'urbain': ('milieu', 'Urbain'),
        'rural': ('milieu', 'Rural')
    }

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

    @classmethod
    def should_apply_2016_adjustment(cls, annee: Optional[str], region: Optional[str], 
                                     delegation: Optional[str]) -> bool:
        """
        Détermine si les ajustements 2016 doivent être appliqués
        """
        # Vérifier l'année
        if str(annee) != '2016':
            return False
        
        # Si une région spécifique est filtrée, elle doit correspondre
        if region and region != 'Tanger-Tétouan-Al Hoceïma':
            return False
        
        # Si une délégation spécifique est filtrée, elle doit correspondre
        if delegation:
            # Récupérer le nom de la délégation depuis la base
            try:
                del_obj = Data.objects.filter(id_delegation=int(delegation)).first()
                if del_obj and del_obj.delegation != 'Chefchaouen':
                    return False
            except (ValueError, TypeError, AttributeError):
                pass
        
        return True

    @classmethod
    def get_base_queryset(cls, annee: Optional[str] = None, region: Optional[str] = None, 
                         delegation: Optional[str] = None) -> 'QuerySet':
        """Construit le queryset de base avec les filtres appliqués"""
        qs = Data.objects.all()
        
        if annee:
            qs = qs.filter(id_periodicite=annee)
        if region:
            qs = qs.filter(id_region=region)
        if delegation:
            try:
                qs = qs.filter(id_delegation=int(delegation))
            except (ValueError, TypeError):
                pass  # Ignore le filtre si la délégation n'est pas valide
                
        return qs
    
    @classmethod
    def get_filter_options(cls) -> Dict[str, 'QuerySet']:
        """Retourne les options de filtrage disponibles"""
        return {
            'annees': Data.objects.values('id_periodicite').distinct().order_by('id_periodicite'),
            'regions': Data.objects.values('id_region', 'region').distinct().order_by('region'),
            'delegations': Data.objects.values('id_delegation', 'delegation', 'id_region')
                          .distinct().order_by('delegation')
        }
    
    @classmethod
    def get_tc_ponderation(cls, annee: str, population_cible: str) -> float:
        """
        Retourne la pondération TC appropriée selon l'année et la population cible
        
        Args:
            annee: L'année sous forme de chaîne
            population_cible: Le nom de la population cible
            
        Returns:
            float: Le coefficient de pondération à appliquer
        """
        try:
            # Nettoyer et convertir l'année - gestion plus robuste
            if annee is None:
                annee = cls.DEFAULT_YEAR
            
            # Nettoyer l'année de tous les caractères non-numériques
            annee_clean = ''.join(filter(str.isdigit, str(annee)))
            
            if not annee_clean:
                # Si pas de chiffres trouvés, utiliser l'année par défaut
                year_int = int(cls.DEFAULT_YEAR)
            else:
                year_int = int(annee_clean)
            
            # Comparer avec des entiers, pas des chaînes
            if year_int <= 2021: 
                # Pour 2021 et moins : utiliser la pondération uniforme
                return cls.TC_PONDERATION_LEGACY.get(population_cible, 0.0)
            else:
                # Pour 2022 et plus : utiliser les pondérations spécifiques
                return cls.TC_PONDERATIONS.get(population_cible, 0.0)
                
        except (ValueError, TypeError) as e:
            # En cas d'erreur, utiliser les pondérations actuelles par défaut
            return cls.TC_PONDERATIONS.get(population_cible, 0.0)

    @classmethod
    def calculate_tc_totals(cls, queryset: 'QuerySet', apply_adjustment: bool = False) -> Dict[str, int]:
        """Calcule les totaux pour la population cible TC avec arrondissement"""
        tc_data = queryset.filter(personnes_cibles='TC').aggregate(
            total=Sum('nb_beneficiaires_t'),
            hommes=Sum('nb_beneficiaires_m'),
            femmes=Sum('nb_beneficiaires_f')
        )
        return {
            'total': cls.round_value(tc_data['total']),
            'hommes': cls.round_value(tc_data['hommes']),
            'femmes': cls.round_value(tc_data['femmes'])
        }
    
    @classmethod
    def get_total_beneficiaries(cls, queryset: 'QuerySet', annee: Optional[str] = None,
                               region: Optional[str] = None, delegation: Optional[str] = None) -> int:
        """
        Calcule le nombre total de bénéficiaires avec ajustements 2016
        """
        total = queryset.aggregate(total=Sum('nb_beneficiaires_t'))['total']
        total_rounded = cls.round_value(total)
        
        # Appliquer les ajustements 2016 si nécessaire
        if cls.should_apply_2016_adjustment(annee, region, delegation):
            total_rounded -= 80
        
        return total_rounded
    
    @classmethod
    def get_population_target_data(cls, queryset: 'QuerySet', annee: Optional[str] = None,
                                  region: Optional[str] = None, delegation: Optional[str] = None) -> tuple:
        """
        Calcule les données par population cible avec pondération TC et ajustements 2016
        """
        # Utiliser l'année par défaut si non fournie
        if not annee:
            annee = cls.DEFAULT_YEAR
        
        apply_adjustment = cls.should_apply_2016_adjustment(annee, region, delegation)
            
        # Queryset excluant TC et les valeurs nulles
        qs_cible = queryset.exclude(
            Q(personnes_cibles='TC') | 
            Q(personnes_cibles='None') | 
            Q(personnes_cibles__isnull=True)
        )
        
        # Totaux TC pour pondération
        tc_totals = cls.calculate_tc_totals(queryset)
        
        # Regroupement par population cible
        grouped_data = qs_cible.values('personnes_cibles').annotate(
            total=Sum('nb_beneficiaires_t')
        )
        
        population_data = []
        total_final = 0
        
        for group in grouped_data:
            label = group['personnes_cibles']
            total_val = cls.round_value(group['total'])
            
            # Ajout de la pondération TC selon l'année
            ponderation = cls.get_tc_ponderation(annee, label)
            if ponderation > 0:
                tc_contribution = cls.round_value(tc_totals['total'] * ponderation)
                total_val += tc_contribution
            
            # Appliquer l'ajustement 2016 pour les enfants
            if apply_adjustment and label == 'Enfants en situation difficile':
                total_val -= 80
            
            population_data.append({'label': label, 'total': total_val})
            total_final += total_val
        
        return population_data, total_final, qs_cible
    
    @classmethod
    def calculate_gender_statistics(cls, qs_cible: 'QuerySet', queryset: 'QuerySet',
                                    annee: Optional[str] = None, region: Optional[str] = None,
                                    delegation: Optional[str] = None) -> Dict[str, Union[int, float]]:
        """Calcule les statistiques par genre avec pondération TC et ajustements 2016"""
        apply_adjustment = cls.should_apply_2016_adjustment(annee, region, delegation)
        
        # Totaux de base (hors TC)
        base_totals = qs_cible.aggregate(
            hommes=Sum('nb_beneficiaires_m'),
            femmes=Sum('nb_beneficiaires_f')
        )
        
        # Totaux TC
        tc_totals = cls.calculate_tc_totals(queryset)
        
        # Totaux finaux avec arrondissement
        hommes = cls.round_value(base_totals['hommes']) + tc_totals['hommes']
        femmes = cls.round_value(base_totals['femmes']) + tc_totals['femmes']
        
        # Appliquer les ajustements 2016
        if apply_adjustment:
            hommes -= 40
            femmes -= 40
        
        total = max(hommes + femmes, 1)  # Éviter division par zéro
        
        return {
            'hommes': hommes,
            'femmes': femmes,
            'total': total,
            'pourcentage_hommes': round((hommes / total) * 100, 1),
            'pourcentage_femmes': round((femmes / total) * 100, 1)
        }
    
    @classmethod
    def calculate_environment_statistics(cls, qs_cible: 'QuerySet', queryset: 'QuerySet',
                                        annee: Optional[str] = None, region: Optional[str] = None,
                                        delegation: Optional[str] = None) -> Dict[str, Any]:
        """Calcule les statistiques par milieu avec pondération TC et ajustements 2016"""
        apply_adjustment = cls.should_apply_2016_adjustment(annee, region, delegation)
        
        # Statistiques de base (hors TC)
        milieu_base = qs_cible.values('milieu').annotate(
            total=Sum('nb_beneficiaires_t')
        ).exclude(milieu__isnull=True)
        
        # Statistiques TC
        milieu_tc = queryset.filter(personnes_cibles='TC').values('milieu').annotate(
            total=Sum('nb_beneficiaires_t')
        ).exclude(milieu__isnull=True)
        
        def get_milieu_total(stats, milieu_type):
            value = next((x['total'] for x in stats if x['milieu'].lower() == milieu_type.lower()), 0)
            return cls.round_value(value)
        
        urbain_base = get_milieu_total(milieu_base, 'urbain')
        rural_base = get_milieu_total(milieu_base, 'rural')
        urbain_tc = get_milieu_total(milieu_tc, 'urbain')
        rural_tc = get_milieu_total(milieu_tc, 'rural')
        
        # Calcul avec ajustement 2016 (urbain uniquement)
        benefic_urbain = urbain_base + urbain_tc
        if apply_adjustment:
            benefic_urbain -= 80
        
        return {
            'benefic_urbain': benefic_urbain,
            'benefic_rural': rural_base + rural_tc,
            'milieu_stats': milieu_base
        }
    
    @classmethod
    def get_population_environment_data(cls, qs_cible: 'QuerySet', queryset: 'QuerySet',
                                       annee: Optional[str] = None, region: Optional[str] = None,
                                       delegation: Optional[str] = None) -> Dict[str, Any]:
        """Calcule les données urbain/rural par population cible avec ajustements 2016"""
        apply_adjustment = cls.should_apply_2016_adjustment(annee, region, delegation)
        populations = list(qs_cible.values_list('personnes_cibles', flat=True).distinct())
        
        urbain_data = {}
        rural_data = {}
        
        for pop in populations:
            urbain_total = qs_cible.filter(
                milieu='Urbain', personnes_cibles=pop
            ).aggregate(total=Sum('nb_beneficiaires_t'))['total']
            urbain_val = cls.round_value(urbain_total)
            
            # Appliquer l'ajustement 2016 pour les enfants en urbain
            if apply_adjustment and pop == 'Enfants en situation difficile':
                urbain_val -= 80
            
            urbain_data[pop] = urbain_val
            
            rural_total = qs_cible.filter(
                milieu='Rural', personnes_cibles=pop
            ).aggregate(total=Sum('nb_beneficiaires_t'))['total']
            rural_data[pop] = cls.round_value(rural_total)
        
        # Calcul des pourcentages
        total_par_pop = {pop: urbain_data[pop] + rural_data[pop] for pop in populations}
        
        pourcentage_urbain = {
            pop: round((urbain_data[pop] / total_par_pop[pop]) * 100, 1) 
            if total_par_pop[pop] else 0 
            for pop in populations
        }
        
        pourcentage_rural = {
            pop: round((rural_data[pop] / total_par_pop[pop]) * 100, 1) 
            if total_par_pop[pop] else 0 
            for pop in populations
        }
        
        return {
            'urbain_data': urbain_data,
            'rural_data': rural_data,
            'pourcentage_urbain': pourcentage_urbain,
            'pourcentage_rural': pourcentage_rural,
            'populations': populations
        }
    
    @classmethod
    def get_evolution_data(cls, region: Optional[str] = None, delegation: Optional[str] = None) -> Dict[str, Any]:
        """Calcule les données d'évolution temporelle avec pondération TC et ajustements 2016"""
        # Queryset de base pour l'évolution (exclut TC)
        evo_qs = cls.get_base_queryset(region=region, delegation=delegation).exclude(personnes_cibles='TC')
        
        # Queryset TC pour pondération
        tc_qs = cls.get_base_queryset(region=region, delegation=delegation).filter(personnes_cibles='TC')
        
        # Labels des années disponibles
        labels_dates = sorted([
            x for x in evo_qs.values_list('id_periodicite', flat=True).distinct() 
            if x is not None
        ])
        
        def get_evolution_for_field(field: str, filter_kwargs: Optional[Dict] = None) -> List[Dict]:
            """Retourne l'évolution pour un champ donné avec arrondissement"""
            q = evo_qs.filter(**filter_kwargs) if filter_kwargs else evo_qs
            evolution_data = list(q.values('id_periodicite').annotate(
                total=Sum(field)
            ).order_by('id_periodicite'))
            
            # Arrondir les totaux
            for item in evolution_data:
                item['total'] = cls.round_value(item['total'])
            
            return evolution_data
        
        # Vérifier si on doit appliquer l'ajustement 2016
        apply_adjustment = cls.should_apply_2016_adjustment('2016', region, delegation)
        
        # Évolutions principales
        evolutions = {
            'general': get_evolution_for_field('nb_beneficiaires_t'),
            'hommes': get_evolution_for_field('nb_beneficiaires_m'),
            'femmes': get_evolution_for_field('nb_beneficiaires_f'),
            'urbain': get_evolution_for_field('nb_beneficiaires_t', {'milieu': 'Urbain'}),
            'rural': get_evolution_for_field('nb_beneficiaires_t', {'milieu': 'Rural'})
        }
        
        # Appliquer les ajustements 2016 sur les évolutions
        if apply_adjustment:
            for evo in evolutions['general']:
                if evo['id_periodicite'] == '2016':
                    evo['total'] -= 80
            for evo in evolutions['hommes']:
                if evo['id_periodicite'] == '2016':
                    evo['total'] -= 40
            for evo in evolutions['femmes']:
                if evo['id_periodicite'] == '2016':
                    evo['total'] -= 40
            for evo in evolutions['urbain']:
                if evo['id_periodicite'] == '2016':
                    evo['total'] -= 80
        
        # Évolution par population cible avec pondération TC adaptée
        populations = evo_qs.values_list('personnes_cibles', flat=True).distinct()
        evolution_par_population = {}
        
        # Données TC par année pour pondération
        tc_par_annee = {}
        for tc_data in tc_qs.values('id_periodicite').annotate(total=Sum('nb_beneficiaires_t')):
            tc_par_annee[tc_data['id_periodicite']] = cls.round_value(tc_data['total'])
        
        for pop in populations:
            pop_evolution = evo_qs.filter(personnes_cibles=pop).values('id_periodicite').annotate(
                total=Sum('nb_beneficiaires_t')
            )
            pop_dict = {e['id_periodicite']: cls.round_value(e['total']) for e in pop_evolution}
            
            # Ajouter la pondération TC pour chaque année
            evolution_avec_tc = []
            for annee in labels_dates:
                base_total = pop_dict.get(annee, 0)
                tc_total = tc_par_annee.get(annee, 0)
                ponderation = cls.get_tc_ponderation(annee, pop)
                
                tc_contribution = cls.round_value(tc_total * ponderation)
                total_avec_tc = base_total + tc_contribution
                
                # Appliquer l'ajustement 2016 pour les enfants
                if apply_adjustment and annee == '2016' and pop == 'Enfants en situation difficile':
                    total_avec_tc -= 80
                
                evolution_avec_tc.append(total_avec_tc)
            
            evolution_par_population[pop] = evolution_avec_tc
        
        return {
            'labels_dates': labels_dates,
            'evolutions': evolutions,
            'evolution_par_population': evolution_par_population,
            'populations': list(populations)
        }


class BeneficiaryViewHelpers:
    """Helpers pour la construction des contextes de templates"""
    
    @staticmethod
    def prepare_json_context(data: Dict[str, Any]) -> Dict[str, str]:
        """Prépare les données pour le contexte JSON du template"""
        json_context = {}
        
        # Données de population
        if 'population_data' in data:
            json_context.update({
                'labels_population': json.dumps([x['label'] for x in data['population_data']]),
                'values_population': json.dumps([x['total'] for x in data['population_data']])
            })
        
        # Données de milieu
        if 'environment_data' in data:
            env_data = data['environment_data']
            if 'milieu_stats' in env_data:
                json_context.update({
                    'labels_milieu': json.dumps([x['milieu'].capitalize() for x in env_data['milieu_stats'] if x['milieu']]),
                    'total_milieu': json.dumps([x['total'] for x in env_data['milieu_stats'] if x['milieu']])
                })
            
            if 'populations' in env_data:
                sorted_pops = sorted(env_data['populations'])
                json_context.update({
                    'labels_milieu_pop': json.dumps(sorted_pops),
                    'urbain_values': json.dumps([env_data['urbain_data'].get(k, 0) for k in sorted_pops]),
                    'rural_values': json.dumps([env_data['rural_data'].get(k, 0) for k in sorted_pops]),
                    'pourcentage_urbain': json.dumps([env_data['pourcentage_urbain'].get(k, 0) for k in sorted_pops]),
                    'pourcentage_rural': json.dumps([env_data['pourcentage_rural'].get(k, 0) for k in sorted_pops])
                })
        
        # Données d'évolution
        if 'evolution_data' in data:
            evo_data = data['evolution_data']
            json_context.update({
                'values_benef': json.dumps([x['total'] or 0 for x in evo_data['evolutions']['general']]),
                'hommes_evol': json.dumps([x['total'] or 0 for x in evo_data['evolutions']['hommes']]),
                'femmes_evol': json.dumps([x['total'] or 0 for x in evo_data['evolutions']['femmes']]),
                'urbain_evol': json.dumps([x['total'] or 0 for x in evo_data['evolutions']['urbain']]),
                'rural_evol': json.dumps([x['total'] or 0 for x in evo_data['evolutions']['rural']]),
                'evolution_par_population': json.dumps(evo_data['evolution_par_population'])
            })
        
        return json_context


@login_required
@require_GET
def get_delegations_by_region(request):
    """
    API pour récupérer les délégations d'une région.
    Utilise le cache pour optimiser les performances.
    """
    region_id = request.GET.get('region_id')
    
    if not region_id:
        return JsonResponse({'delegations': []})
    
    # Clé de cache
    cache_key = f'delegations_region_{region_id}'
    delegations = cache.get(cache_key)
    
    if delegations is None:
        delegations = list(
            Data.objects.filter(id_region=region_id)
            .values('id_delegation')
            .annotate(delegation_name=Max('delegation'))
            .order_by('delegation_name')
        )
        
        # Cache pour 1 heure
        cache.set(cache_key, delegations, 3600)
    
    result = [
        {'id_delegation': d['id_delegation'], 'delegation': d['delegation_name']}
        for d in delegations if d['id_delegation']
    ]
    
    return JsonResponse({'delegations': result})


@login_required
@require_GET
def repartition_beneficiaires_api(request):
    """
    API pour la répartition des bénéficiaires - VERSION SIMPLIFIÉE
    """
    # Récupération et validation des paramètres
    filtre = request.GET.get('filtre', 'total')
    region = request.GET.get('region')
    delegation = request.GET.get('delegation')
    annee = request.GET.get('annee', BeneficiaryDataService.DEFAULT_YEAR)
    
    # Détermination du niveau de regroupement
    niveau = 'delegation' if region else 'region'
    
    # Construction du queryset de base
    qs = BeneficiaryDataService.get_base_queryset(annee=annee, region=region, delegation=delegation)
    
    # Application du filtre
    if filtre in BeneficiaryDataService.FILTER_MAPPING:
        filter_config = BeneficiaryDataService.FILTER_MAPPING[filtre]
        
        if isinstance(filter_config, tuple):
            # Filtre sur un champ spécifique (ex: milieu)
            field, value = filter_config
            qs = qs.filter(**{field + '__iexact': value})
            champ_aggregation = 'nb_beneficiaires_t'
        else:
            # Filtre direct sur un champ
            champ_aggregation = filter_config
    else:
        # Filtre personnalisé = population cible
        qs = qs.filter(personnes_cibles=filtre)
        champ_aggregation = 'nb_beneficiaires_t'
    
    # Regroupement et agrégation
    if niveau == 'region':
        grouped = qs.values('region').annotate(
            total=Sum(champ_aggregation)
        ).order_by('region')
        labels = [g['region'] for g in grouped]
    else:
        grouped = qs.values('delegation').annotate(
            total=Sum(champ_aggregation)
        ).order_by('delegation')
        labels = [g['delegation'] for g in grouped]
    
    values = [g['total'] or 0 for g in grouped]
    
    return JsonResponse({'labels': labels, 'data': values})


@login_required
def list_benefic(request):
    """
    Vue principale pour l'affichage des bénéficiaires avec ajustements 2016
    TOTAL BÉNÉFICIAIRES : calcul direct avec Sum('nb_beneficiaires_t')
    POPULATIONS CIBLES : gardent la logique de pondération TC
    """
    # Récupération et validation des paramètres
    annee = request.GET.get('annee') or BeneficiaryDataService.DEFAULT_YEAR
    region = request.GET.get('region')
    delegation = request.GET.get('delegation')
    
    # Construction du queryset principal
    main_queryset = BeneficiaryDataService.get_base_queryset(annee, region, delegation)
    
    # Récupération des options de filtrage
    filter_options = BeneficiaryDataService.get_filter_options()
    
    # Calcul du total de bénéficiaires avec ajustements 2016
    total_beneficiaires = BeneficiaryDataService.get_total_beneficiaries(
        main_queryset, annee, region, delegation
    )
    
    # Les populations cibles avec pondération TC et ajustements 2016
    population_data, _, qs_cible = BeneficiaryDataService.get_population_target_data(
        main_queryset, annee, region, delegation
    )
    gender_stats = BeneficiaryDataService.calculate_gender_statistics(
        qs_cible, main_queryset, annee, region, delegation
    )
    environment_data = BeneficiaryDataService.calculate_environment_statistics(
        qs_cible, main_queryset, annee, region, delegation
    )
    pop_env_data = BeneficiaryDataService.get_population_environment_data(
        qs_cible, main_queryset, annee, region, delegation
    )
    evolution_data = BeneficiaryDataService.get_evolution_data(region, delegation)
    
    # Combinaison des données d'environnement
    environment_data.update(pop_env_data)
    
    # Préparation des données pour le contexte
    context_data = {
        'population_data': population_data,
        'environment_data': environment_data,
        'evolution_data': evolution_data
    }
    
    # Construction du contexte final
    context = {
        # Données de base
        'data': main_queryset,
        **filter_options,
        
        # Filtres sélectionnés
        'selected_annee': annee,
        'selected_region': region,
        'selected_delegation': delegation,
        
        # Statistiques principales
        'beneficiaires_count': total_beneficiaires,
        **gender_stats,
        'benefic_urbain': environment_data['benefic_urbain'],
        'benefic_rural': environment_data['benefic_rural'],
        
        # Données structurées
        'nombre_pop': len(environment_data['populations']),
        'population_cible_data': population_data,
        'labels_dates': evolution_data['labels_dates'],
        'populations_labels': evolution_data['populations'],
        
        # Données JSON pour les graphiques
        **BeneficiaryViewHelpers.prepare_json_context(context_data)
    }
    
    return render(request, 'beneficiaire.html', context)