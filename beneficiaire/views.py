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
    
    TC_PONDERATIONS = {
        "Enfants en situation difficile": 0.28,
        "Femmes en situation difficile": 0.28,
        "Personnes en situation de handicap": 0.27,
        "Personnes âgées en situation difficile": 0.17
    }

    TC_PONDERATION_LEGACY = {
        "Enfants en situation difficile": 0.25,
        "Femmes en situation difficile": 0.25,
        "Personnes en situation de handicap": 0.25,
        "Personnes âgées en situation difficile": 0.25
    }
    
    DEFAULT_YEAR = '2022'
    
    FILTER_MAPPING = {
        'total': 'nb_beneficiaires_t',
        'hommes': 'nb_beneficiaires_m',
        'femmes': 'nb_beneficiaires_f',
        'urbain': ('milieu', 'Urbain'),
        'rural': ('milieu', 'Rural')
    }

    @classmethod
    def round_value(cls, value: Union[float, int, None]) -> int:
        if value is None:
            return 0
        return round(float(value))

    @classmethod
    def should_apply_2016_adjustment(cls, annee: Optional[str], region: Optional[str] = None,
                                     delegation_name: Optional[str] = None) -> bool:
        """
        ✅ OPTIMISÉ : Reçoit delegation_name (string) directement.
        Plus aucune requête SQL à l'intérieur.
        """
        if str(annee) != '2016':
            return False
        if region and region != 'Tanger-Tétouan-Al Hoceïma':
            return False
        if delegation_name and delegation_name != 'Chefchaouen':
            return False
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
                pass
        return qs
    
    @classmethod
    def get_filter_options(cls) -> Dict[str, Any]:
        """
        ✅ OPTIMISÉ : Retourne les options de filtrage avec cache 1 heure.
        """
        cache_key = 'filter_options'
        options = cache.get(cache_key)

        if options is None:
            options = {
                'annees': list(
                    Data.objects.values('id_periodicite')
                    .distinct().order_by('id_periodicite')
                ),
                'regions': list(
                    Data.objects.values('id_region', 'region')
                    .distinct().order_by('region')
                ),
                'delegations': list(
                    Data.objects.values('id_delegation', 'delegation', 'id_region')
                    .distinct().order_by('delegation')
                )
            }
            cache.set(cache_key, options, 3600)

        return options
    
    @classmethod
    def get_tc_ponderation(cls, annee: str, population_cible: str) -> float:
        """Retourne la pondération TC appropriée selon l'année et la population cible"""
        try:
            if annee is None:
                annee = cls.DEFAULT_YEAR
            annee_clean = ''.join(filter(str.isdigit, str(annee)))
            if not annee_clean:
                year_int = int(cls.DEFAULT_YEAR)
            else:
                year_int = int(annee_clean)
            if year_int <= 2021:
                return cls.TC_PONDERATION_LEGACY.get(population_cible, 0.0)
            else:
                return cls.TC_PONDERATIONS.get(population_cible, 0.0)
        except (ValueError, TypeError):
            return cls.TC_PONDERATIONS.get(population_cible, 0.0)

    @classmethod
    def calculate_tc_totals(cls, queryset: 'QuerySet') -> Dict[str, int]:
        """Calcule les totaux pour la population cible TC"""
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
                                region: Optional[str] = None,
                                delegation_name: Optional[str] = None) -> int:
        """
        ✅ OPTIMISÉ : Reçoit delegation_name au lieu de delegation (ID).
        """
        total = queryset.aggregate(total=Sum('nb_beneficiaires_t'))['total']
        total_rounded = cls.round_value(total)
        if cls.should_apply_2016_adjustment(annee, region, delegation_name):
            total_rounded -= 80
        return total_rounded
    
    @classmethod
    def get_population_target_data(cls, queryset: 'QuerySet', annee: Optional[str] = None,
                                   region: Optional[str] = None,
                                   delegation_name: Optional[str] = None,
                                   tc_totals: Optional[Dict] = None) -> tuple:
        """
        ✅ OPTIMISÉ : Accepte tc_totals en paramètre pour éviter le recalcul.
        Reçoit delegation_name au lieu de delegation (ID).
        """
        if not annee:
            annee = cls.DEFAULT_YEAR

        apply_adjustment = cls.should_apply_2016_adjustment(annee, region, delegation_name)

        qs_cible = queryset.exclude(
            Q(personnes_cibles='TC') |
            Q(personnes_cibles='None') |
            Q(personnes_cibles__isnull=True)
        )

        # ✅ Utiliser tc_totals passé en paramètre si disponible
        if tc_totals is None:
            tc_totals = cls.calculate_tc_totals(queryset)

        grouped_data = qs_cible.values('personnes_cibles').annotate(
            total=Sum('nb_beneficiaires_t')
        )

        population_data = []
        total_final = 0

        for group in grouped_data:
            label = group['personnes_cibles']
            total_val = cls.round_value(group['total'])
            ponderation = cls.get_tc_ponderation(annee, label)
            if ponderation > 0:
                tc_contribution = cls.round_value(tc_totals['total'] * ponderation)
                total_val += tc_contribution
            if apply_adjustment and label == 'Enfants en situation difficile':
                total_val -= 80
            population_data.append({'label': label, 'total': total_val})
            total_final += total_val

        return population_data, total_final, qs_cible
    
    @classmethod
    def calculate_gender_statistics(cls, qs_cible: 'QuerySet', queryset: 'QuerySet',
                                    annee: Optional[str] = None, region: Optional[str] = None,
                                    delegation_name: Optional[str] = None,
                                    tc_totals: Optional[Dict] = None) -> Dict[str, Union[int, float]]:
        """
        ✅ OPTIMISÉ : Accepte tc_totals en paramètre pour éviter le recalcul.
        Reçoit delegation_name au lieu de delegation (ID).
        """
        apply_adjustment = cls.should_apply_2016_adjustment(annee, region, delegation_name)

        base_totals = qs_cible.aggregate(
            hommes=Sum('nb_beneficiaires_m'),
            femmes=Sum('nb_beneficiaires_f')
        )

        # ✅ Utiliser tc_totals passé en paramètre si disponible
        if tc_totals is None:
            tc_totals = cls.calculate_tc_totals(queryset)

        hommes = cls.round_value(base_totals['hommes']) + tc_totals['hommes']
        femmes = cls.round_value(base_totals['femmes']) + tc_totals['femmes']

        if apply_adjustment:
            hommes -= 40
            femmes -= 40

        total = max(hommes + femmes, 1)

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
                                         delegation_name: Optional[str] = None) -> Dict[str, Any]:
        """
        ✅ OPTIMISÉ : Reçoit delegation_name au lieu de delegation (ID).
        """
        apply_adjustment = cls.should_apply_2016_adjustment(annee, region, delegation_name)

        milieu_base = qs_cible.values('milieu').annotate(
            total=Sum('nb_beneficiaires_t')
        ).exclude(milieu__isnull=True)

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

        benefic_urbain = urbain_base + urbain_tc
        if apply_adjustment:
            benefic_urbain -= 80

        return {
            'benefic_urbain': benefic_urbain,
            'benefic_rural': rural_base + rural_tc,
            'milieu_stats': list(milieu_base)
        }
    
    @classmethod
    def get_population_environment_data(cls, qs_cible: 'QuerySet', queryset: 'QuerySet',
                                        annee: Optional[str] = None, region: Optional[str] = None,
                                        delegation_name: Optional[str] = None) -> Dict[str, Any]:
        """
        ✅ OPTIMISÉ : Une seule requête groupée au lieu de N requêtes en boucle.
        Reçoit delegation_name au lieu de delegation (ID).
        """
        apply_adjustment = cls.should_apply_2016_adjustment(annee, region, delegation_name)

        # ✅ UNE seule requête groupée
        milieu_pop_stats = (
            qs_cible
            .values('personnes_cibles', 'milieu')
            .annotate(total=Sum('nb_beneficiaires_t'))
            .exclude(milieu__isnull=True)
        )

        urbain_data, rural_data = {}, {}
        populations = set()

        for stat in milieu_pop_stats:
            pop = stat['personnes_cibles']
            milieu = (stat['milieu'] or '').lower()
            val = cls.round_value(stat['total'])
            populations.add(pop)

            if milieu == 'urbain':
                if apply_adjustment and pop == 'Enfants en situation difficile':
                    val -= 80
                urbain_data[pop] = val
            elif milieu == 'rural':
                rural_data[pop] = val

        populations = list(populations)
        total_par_pop = {
            pop: urbain_data.get(pop, 0) + rural_data.get(pop, 0)
            for pop in populations
        }

        pourcentage_urbain = {
            pop: round((urbain_data.get(pop, 0) / total_par_pop[pop]) * 100, 1)
            if total_par_pop[pop] else 0
            for pop in populations
        }
        pourcentage_rural = {
            pop: round((rural_data.get(pop, 0) / total_par_pop[pop]) * 100, 1)
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
    def get_evolution_data(cls, region: Optional[str] = None,
                           delegation: Optional[str] = None,
                           delegation_name: Optional[str] = None) -> Dict[str, Any]:
        """
        ✅ OPTIMISÉ : Reçoit delegation_name pour éviter les requêtes SQL répétées.
        """
        evo_qs_complet = cls.get_base_queryset(region=region, delegation=delegation)

        evo_qs = evo_qs_complet.exclude(
            Q(personnes_cibles='TC') |
            Q(personnes_cibles='None') |
            Q(personnes_cibles__isnull=True)
        )

        tc_qs = cls.get_base_queryset(
            region=region, delegation=delegation
        ).filter(personnes_cibles='TC')

        labels_dates = sorted([
            x for x in evo_qs_complet.values_list('id_periodicite', flat=True).distinct()
            if x is not None
        ])

        def get_evolution_for_field(field: str, filter_kwargs: Optional[Dict] = None,
                                    use_complete_qs: bool = False) -> List[Dict]:
            q = evo_qs_complet if use_complete_qs else evo_qs
            if filter_kwargs:
                q = q.filter(**filter_kwargs)
            evolution_data = list(q.values('id_periodicite').annotate(
                total=Sum(field)
            ).order_by('id_periodicite'))
            for item in evolution_data:
                item['total'] = cls.round_value(item['total'])
            return evolution_data

        apply_adjustment = cls.should_apply_2016_adjustment('2016', region, delegation_name)

        evolutions = {
            'general': get_evolution_for_field('nb_beneficiaires_t', use_complete_qs=True),
            'hommes':  get_evolution_for_field('nb_beneficiaires_m', use_complete_qs=True),
            'femmes':  get_evolution_for_field('nb_beneficiaires_f', use_complete_qs=True),
            'urbain':  get_evolution_for_field('nb_beneficiaires_t', {'milieu': 'Urbain'}, use_complete_qs=True),
            'rural':   get_evolution_for_field('nb_beneficiaires_t', {'milieu': 'Rural'}, use_complete_qs=True)
        }

        if apply_adjustment:
            for key, adj in [('general', 80), ('hommes', 40), ('femmes', 40), ('urbain', 80)]:
                for evo in evolutions[key]:
                    if str(evo['id_periodicite']) == '2016':
                        evo['total'] -= adj

        populations = evo_qs.values_list('personnes_cibles', flat=True).distinct()

        tc_par_annee = {
            tc['id_periodicite']: cls.round_value(tc['total'])
            for tc in tc_qs.values('id_periodicite').annotate(total=Sum('nb_beneficiaires_t'))
        }

        evolution_par_population = {}
        for pop in populations:
            pop_evolution = evo_qs.filter(personnes_cibles=pop).values('id_periodicite').annotate(
                total=Sum('nb_beneficiaires_t')
            )
            pop_dict = {e['id_periodicite']: cls.round_value(e['total']) for e in pop_evolution}

            evolution_avec_tc = []
            for annee in labels_dates:
                base_total = pop_dict.get(annee, 0)
                tc_total = tc_par_annee.get(annee, 0)
                ponderation = cls.get_tc_ponderation(str(annee), pop)
                tc_contribution = cls.round_value(tc_total * ponderation)
                total_avec_tc = base_total + tc_contribution
                if apply_adjustment and str(annee) == '2016' and pop == 'Enfants en situation difficile':
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
        json_context = {}

        if 'population_data' in data:
            json_context.update({
                'labels_population': json.dumps([x['label'] for x in data['population_data']]),
                'values_population': json.dumps([x['total'] for x in data['population_data']])
            })

        if 'environment_data' in data:
            env_data = data['environment_data']
            if 'milieu_stats' in env_data:
                json_context.update({
                    'labels_milieu': json.dumps([
                        x['milieu'].capitalize() for x in env_data['milieu_stats'] if x['milieu']
                    ]),
                    'total_milieu': json.dumps([
                        x['total'] for x in env_data['milieu_stats'] if x['milieu']
                    ])
                })
            if 'populations' in env_data:
                sorted_pops = sorted(env_data['populations'])
                json_context.update({
                    'labels_milieu_pop':  json.dumps(sorted_pops),
                    'urbain_values':      json.dumps([env_data['urbain_data'].get(k, 0) for k in sorted_pops]),
                    'rural_values':       json.dumps([env_data['rural_data'].get(k, 0) for k in sorted_pops]),
                    'pourcentage_urbain': json.dumps([env_data['pourcentage_urbain'].get(k, 0) for k in sorted_pops]),
                    'pourcentage_rural':  json.dumps([env_data['pourcentage_rural'].get(k, 0) for k in sorted_pops])
                })

        if 'evolution_data' in data:
            evo_data = data['evolution_data']
            json_context.update({
                'values_benef':            json.dumps([x['total'] or 0 for x in evo_data['evolutions']['general']]),
                'hommes_evol':             json.dumps([x['total'] or 0 for x in evo_data['evolutions']['hommes']]),
                'femmes_evol':             json.dumps([x['total'] or 0 for x in evo_data['evolutions']['femmes']]),
                'urbain_evol':             json.dumps([x['total'] or 0 for x in evo_data['evolutions']['urbain']]),
                'rural_evol':              json.dumps([x['total'] or 0 for x in evo_data['evolutions']['rural']]),
                'evolution_par_population': json.dumps(evo_data['evolution_par_population'])
            })

        return json_context


# ─────────────────────────────────────────────
#  VUES
# ─────────────────────────────────────────────

@login_required
@require_GET
def get_delegations_by_region(request):
    """API pour récupérer les délégations d'une région — déjà optimisée avec cache."""
    region_id = request.GET.get('region_id')
    if not region_id:
        return JsonResponse({'delegations': []})

    cache_key = f'delegations_region_{region_id}'
    delegations = cache.get(cache_key)

    if delegations is None:
        delegations = list(
            Data.objects.filter(id_region=region_id)
            .values('id_delegation')
            .annotate(delegation_name=Max('delegation'))
            .order_by('delegation_name')
        )
        cache.set(cache_key, delegations, 3600)

    result = [
        {'id_delegation': d['id_delegation'], 'delegation': d['delegation_name']}
        for d in delegations if d['id_delegation']
    ]
    return JsonResponse({'delegations': result})


@login_required
@require_GET
def repartition_beneficiaires_api(request):
    """API pour la répartition des bénéficiaires."""
    filtre    = request.GET.get('filtre', 'total')
    region    = request.GET.get('region')
    delegation = request.GET.get('delegation')
    annee     = request.GET.get('annee', BeneficiaryDataService.DEFAULT_YEAR)

    niveau = 'delegation' if region else 'region'
    qs = BeneficiaryDataService.get_base_queryset(annee=annee, region=region, delegation=delegation)

    if filtre in BeneficiaryDataService.FILTER_MAPPING:
        filter_config = BeneficiaryDataService.FILTER_MAPPING[filtre]
        if isinstance(filter_config, tuple):
            field, value = filter_config
            qs = qs.filter(**{field + '__iexact': value})
            champ_aggregation = 'nb_beneficiaires_t'
        else:
            champ_aggregation = filter_config
    else:
        qs = qs.filter(personnes_cibles=filtre)
        champ_aggregation = 'nb_beneficiaires_t'

    if niveau == 'region':
        grouped = qs.values('region').annotate(total=Sum(champ_aggregation)).order_by('region')
        labels  = [g['region'] for g in grouped]
    else:
        grouped = qs.values('delegation').annotate(total=Sum(champ_aggregation)).order_by('delegation')
        labels  = [g['delegation'] for g in grouped]

    values = [g['total'] or 0 for g in grouped]
    return JsonResponse({'labels': labels, 'data': values})


@login_required
def list_benefic(request):
    """
    ✅ VUE PRINCIPALE OPTIMISÉE :
    - delegation_name résolu une seule fois (plus de requête dans should_apply_2016_adjustment)
    - tc_totals calculé une seule fois et partagé entre toutes les méthodes
    - get_filter_options mis en cache 1 heure
    - Contexte complet mis en cache 10 minutes par combinaison de filtres
    """
    annee      = request.GET.get('annee') or BeneficiaryDataService.DEFAULT_YEAR
    region     = request.GET.get('region')
    delegation = request.GET.get('delegation')

    # ─── Clé de cache unique par combinaison de filtres ───
    cache_key = f'dashboard_benefic_{annee}_{region}_{delegation}'
    context   = cache.get(cache_key)

    if context is None:

        # ✅ 1. Résolution du nom de délégation UNE SEULE FOIS
        delegation_name = None
        if delegation:
            try:
                del_obj = Data.objects.filter(
                    id_delegation=int(delegation)
                ).values('delegation').first()
                delegation_name = del_obj['delegation'] if del_obj else None
            except (ValueError, TypeError):
                pass

        # ✅ 2. Queryset principal
        main_queryset = BeneficiaryDataService.get_base_queryset(annee, region, delegation)

        # ✅ 3. Options de filtrage (cachées séparément 1 heure)
        filter_options = BeneficiaryDataService.get_filter_options()

        # ✅ 4. tc_totals calculé UNE SEULE FOIS, partagé entre toutes les méthodes
        tc_totals = BeneficiaryDataService.calculate_tc_totals(main_queryset)

        # ✅ 5. Calculs principaux — tous utilisent delegation_name et tc_totals
        total_beneficiaires = BeneficiaryDataService.get_total_beneficiaries(
            main_queryset, annee, region, delegation_name
        )

        population_data, _, qs_cible = BeneficiaryDataService.get_population_target_data(
            main_queryset, annee, region, delegation_name, tc_totals=tc_totals
        )

        gender_stats = BeneficiaryDataService.calculate_gender_statistics(
            qs_cible, main_queryset, annee, region, delegation_name, tc_totals=tc_totals
        )

        environment_data = BeneficiaryDataService.calculate_environment_statistics(
            qs_cible, main_queryset, annee, region, delegation_name
        )

        pop_env_data = BeneficiaryDataService.get_population_environment_data(
            qs_cible, main_queryset, annee, region, delegation_name
        )

        evolution_data = BeneficiaryDataService.get_evolution_data(
            region, delegation, delegation_name
        )

        # ✅ 6. Fusion des données d'environnement
        environment_data.update(pop_env_data)

        context_data = {
            'population_data':  population_data,
            'environment_data': environment_data,
            'evolution_data':   evolution_data
        }

        # ✅ 7. Construction du contexte final
        context = {
            # Options de filtrage
            **filter_options,

            # Filtres sélectionnés
            'selected_annee':       annee,
            'selected_region':      region,
            'selected_delegation':  delegation,

            # Statistiques principales
            'beneficiaires_count':  total_beneficiaires,
            **gender_stats,
            'benefic_urbain':       environment_data['benefic_urbain'],
            'benefic_rural':        environment_data['benefic_rural'],

            # Données structurées
            'nombre_pop':           len(environment_data['populations']),
            'population_cible_data': population_data,
            'labels_dates':         evolution_data['labels_dates'],
            'populations_labels':   evolution_data['populations'],

            # Données JSON pour les graphiques
            **BeneficiaryViewHelpers.prepare_json_context(context_data)
        }

        # ✅ 8. Mise en cache du contexte complet — 10 minutes
        cache.set(cache_key, context, 600)

    return render(request, 'beneficiaire.html', context)