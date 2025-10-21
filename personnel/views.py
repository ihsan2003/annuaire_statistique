from django.shortcuts import render
from django.template import loader
from django.db.models import Count, Sum, Avg, Max, F, FloatField, Q
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from datetime import date
from collections import defaultdict
import json
from .models import Data, Personnel


def get_delegations_by_region(request):
    """API pour récupérer les délégations d'une région"""
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
        {
            'id_delegation': d['id_delegation'],
            'delegation': d['delegation_name']
        }
        for d in delegations if d['id_delegation'] is not None
    ]

    return JsonResponse({'delegations': result})


def calculate_age(birthdate):
    """Calcule l'âge à partir d'une date de naissance"""
    today = date.today()
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


@login_required
def list_personnel(request):
    # Récupération des filtres avec valeur par défaut 2022
    selected_annee = request.GET.get('annee', '2022')
    selected_region = request.GET.get('region')
    selected_delegation = request.GET.get('delegation')

    # Construction du queryset de base
    queryset = Personnel.objects.all()
    queryset_data = Data.objects.all()
    
    # Application des filtres (2022 par défaut)
    if selected_annee:
        queryset = queryset.filter(id_periodicite=selected_annee)
        queryset_data = queryset_data.filter(id_periodicite=selected_annee)
    if selected_region:
        queryset = queryset.filter(id_region=selected_region)
        queryset_data = queryset_data.filter(id_region=selected_region)
    if selected_delegation:
        try:
            queryset = queryset.filter(id_delegation=int(selected_delegation))
            queryset_data = queryset_data.filter(id_delegation=int(selected_delegation))
        except (ValueError, TypeError):
            pass

    # ==================== KPI CARDS ====================
    
    # 1. Total des Personnels
    Personnels_count = queryset.count()
    
    # 2. Pourcentage Femmes/Hommes
    total_personnel = queryset.count()
    nb_femmes = queryset.filter(sexe='F').count()
    nb_hommes = queryset.filter(sexe='M').count()
    
    pourcentage_filles = round((nb_femmes / total_personnel * 100), 2) if total_personnel > 0 else 0
    pourcentage_garcons = round((nb_hommes / total_personnel * 100), 2) if total_personnel > 0 else 0
    
    # 3. Type Intérieur vs Extérieur
    nb_interieur = queryset.filter(type='intérieur').count()
    nb_exterieur = queryset.filter(type='extérieur').count()
    
    interieur = nb_interieur
    exterieur = nb_exterieur
    
    # 4. Taux d'encadrement dans les EPS
    # Calcul: nombre total des beneficiaires / nombre du personnel si cat_programme = "EPS"
    eps_data = queryset_data.filter(cat_programme='EPS')
    
    nb_beneficiaires_t = eps_data.aggregate(total=Sum('nb_beneficiaires_t'))['total'] or 0
    
    personnel_totals = eps_data.aggregate(
        tit=Sum('nb_pers_entraide_tit'),
        part=Sum('nb_pers_part')
    )
    nb_personnel = (personnel_totals['tit'] or 0) + (personnel_totals['part'] or 0)
    
    taux_encadre = round((nb_beneficiaires_t / nb_personnel), 2) if nb_personnel > 0 else 0

    # ==================== MENUS DÉROULANTS ====================
    annees = Personnel.objects.values('id_periodicite').distinct().order_by('id_periodicite')
    regions = Personnel.objects.values('id_region', 'region').distinct().order_by('region')
    delegations = Personnel.objects.values('id_delegation', 'delegation', 'id_region').distinct().order_by('delegation')

    # ==================== GRAPHIQUES ====================
    
    # 1. Répartition du personnel par sexe
    data_sexe = (
        queryset
        .values('sexe')
        .annotate(count=Count('id'))
        .order_by('sexe')
    )
    labels_sexe = [item['sexe'] if item['sexe'] else "Non spécifié" for item in data_sexe]
    values_sexe = [item['count'] for item in data_sexe]

    # 2. Répartition par type (Intérieur/Extérieur)
    type_data = (
        queryset
        .values('type')
        .annotate(count=Count('id'))
        .order_by('type')
    )
    labels_type = [item['type'] if item['type'] else "Non spécifié" for item in type_data]
    values_type = [item['count'] for item in type_data]

    # 3. Distribution par âge
    age_groups = {
        'Moins de 26 ans': 0,
        '26-29 ans': 0,
        '30-39 ans': 0,
        '40-49 ans': 0,
        '50-59 ans': 0,
        '60-62 ans': 0,
        '63 ans et plus': 0
    }

    for person in queryset:
        if person.date_de_naissance:
            age = calculate_age(person.date_de_naissance)
            if age < 26:
                age_groups['Moins de 26 ans'] += 1
            elif age < 30:
                age_groups['26-29 ans'] += 1
            elif age < 40:
                age_groups['30-39 ans'] += 1
            elif age < 50:
                age_groups['40-49 ans'] += 1
            elif age < 60:
                age_groups['50-59 ans'] += 1
            elif age < 63:
                age_groups['60-62 ans'] += 1
            else:
                age_groups['63 ans et plus'] += 1

    labels_age = list(age_groups.keys())
    values_age = list(age_groups.values())

    # 4. Répartition par grade
    grades_data = (
        queryset
        .values('libelle_grade')
        .annotate(total=Count('id'))
        .order_by('-total')  # Tri par total décroissant
    )

    labels_grades = [item['libelle_grade'] if item['libelle_grade'] else "Non spécifié" for item in grades_data]
    values_grades = [item['total'] for item in grades_data]

    # 5. Répartition par nature de personnel
    nature_totals = queryset_data.aggregate(
        titulaires=Sum('nb_pers_entraide_tit'),
        vacataires=Sum('nb_pers_entraide_vac'),
        volontaires=Sum('nb_pers_entraide_vol'),
        partenaires=Sum('nb_pers_part'),
        promoteurs=Sum('nb_pers_prom')
    )

    labels_nature = ['Titulaires', 'Vacataires', 'Volontaires', 'Partenaires', 'Promoteurs']
    values_nature = [
        int(nature_totals['titulaires'] or 0),
        int(nature_totals['vacataires'] or 0),
        int(nature_totals['volontaires'] or 0),
        int(nature_totals['partenaires'] or 0),
        int(nature_totals['promoteurs'] or 0)
    ]

    # 6. Répartition géographique du personnel avec sous-catégories
    geo_categories = {}

    if selected_delegation:
        # Si une délégation est sélectionnée, on groupe par année
        base_query = Personnel.objects.filter(id_delegation=int(selected_delegation))
        annees_list = base_query.values_list('id_periodicite', flat=True).distinct().order_by('id_periodicite')
        labels_geo = [str(annee) for annee in annees_list]
        geo_label = f"Délégation: {queryset.first().delegation if queryset.exists() else 'Sélectionnée'}"
        
        # Total
        geo_categories['total'] = []
        for annee in annees_list:
            geo_categories['total'].append(base_query.filter(id_periodicite=annee).count())
        
        # Par sexe
        geo_categories['homme'] = []
        geo_categories['femme'] = []
        for annee in annees_list:
            q = base_query.filter(id_periodicite=annee)
            geo_categories['homme'].append(q.filter(sexe='M').count())
            geo_categories['femme'].append(q.filter(sexe='F').count())
        
        # Par type
        geo_categories['interieur'] = []
        geo_categories['exterieur'] = []
        for annee in annees_list:
            q = base_query.filter(id_periodicite=annee)
            geo_categories['interieur'].append(q.filter(type='intérieur').count())
            geo_categories['exterieur'].append(q.filter(type='extérieur').count())
        
        # Par tranches d'âge
        age_keys = ['Moins de 26 ans', '26-29 ans', '30-39 ans', '40-49 ans', '50-59 ans', '60-62 ans', '63 ans et plus']
        for key in age_keys:
            geo_categories[key] = []
        
        for annee in annees_list:
            q = base_query.filter(id_periodicite=annee)
            age_counts = {key: 0 for key in age_keys}
            for person in q:
                if person.date_de_naissance:
                    age = calculate_age(person.date_de_naissance)
                    if age < 26:
                        age_counts['Moins de 26 ans'] += 1
                    elif age < 30:
                        age_counts['26-29 ans'] += 1
                    elif age < 40:
                        age_counts['30-39 ans'] += 1
                    elif age < 50:
                        age_counts['40-49 ans'] += 1
                    elif age < 60:
                        age_counts['50-59 ans'] += 1
                    elif age < 63:
                        age_counts['60-62 ans'] += 1
                    else:
                        age_counts['63 ans et plus'] += 1
            for key in age_keys:
                geo_categories[key].append(age_counts[key])
        
        # Par nature (depuis Data)
        nature_keys = ['Titulaires', 'Vacataires', 'Volontaires', 'Partenaires', 'Promoteurs']
        for key in nature_keys:
            geo_categories[key] = []
        
        for annee in annees_list:
            q_data = Data.objects.filter(id_delegation=int(selected_delegation), id_periodicite=annee)
            if selected_region:
                q_data = q_data.filter(id_region=selected_region)
            
            geo_categories['Titulaires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_tit'))['total'] or 0))
            geo_categories['Vacataires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_vac'))['total'] or 0))
            geo_categories['Volontaires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_vol'))['total'] or 0))
            geo_categories['Partenaires'].append(int(q_data.aggregate(total=Sum('nb_pers_part'))['total'] or 0))
            geo_categories['Promoteurs'].append(int(q_data.aggregate(total=Sum('nb_pers_prom'))['total'] or 0))

    elif selected_region:
        # Si une région est sélectionnée, on groupe par délégation
        delegations_list = queryset.values('id_delegation', 'delegation').distinct().order_by('delegation')
        labels_geo = [d['delegation'] if d['delegation'] else "Non spécifié" for d in delegations_list]
        delegation_ids = [d['id_delegation'] for d in delegations_list]
        geo_label = f"Région: {queryset.first().region if queryset.exists() else 'Sélectionnée'}"
        
        # Total
        geo_categories['total'] = []
        for deleg_id in delegation_ids:
            geo_categories['total'].append(queryset.filter(id_delegation=deleg_id).count())
        
        # Par sexe
        geo_categories['homme'] = []
        geo_categories['femme'] = []
        for deleg_id in delegation_ids:
            q = queryset.filter(id_delegation=deleg_id)
            geo_categories['homme'].append(q.filter(sexe='M').count())
            geo_categories['femme'].append(q.filter(sexe='F').count())
        
        # Par type
        geo_categories['interieur'] = []
        geo_categories['exterieur'] = []
        for deleg_id in delegation_ids:
            q = queryset.filter(id_delegation=deleg_id)
            geo_categories['interieur'].append(q.filter(type='intérieur').count())
            geo_categories['exterieur'].append(q.filter(type='extérieur').count())
        
        # Par tranches d'âge
        age_keys = ['Moins de 26 ans', '26-29 ans', '30-39 ans', '40-49 ans', '50-59 ans', '60-62 ans', '63 ans et plus']
        for key in age_keys:
            geo_categories[key] = []
        
        for deleg_id in delegation_ids:
            q = queryset.filter(id_delegation=deleg_id)
            age_counts = {key: 0 for key in age_keys}
            for person in q:
                if person.date_de_naissance:
                    age = calculate_age(person.date_de_naissance)
                    if age < 26:
                        age_counts['Moins de 26 ans'] += 1
                    elif age < 30:
                        age_counts['26-29 ans'] += 1
                    elif age < 40:
                        age_counts['30-39 ans'] += 1
                    elif age < 50:
                        age_counts['40-49 ans'] += 1
                    elif age < 60:
                        age_counts['50-59 ans'] += 1
                    elif age < 63:
                        age_counts['60-62 ans'] += 1
                    else:
                        age_counts['63 ans et plus'] += 1
            for key in age_keys:
                geo_categories[key].append(age_counts[key])
        
        # Par nature
        nature_keys = ['Titulaires', 'Vacataires', 'Volontaires', 'Partenaires', 'Promoteurs']
        for key in nature_keys:
            geo_categories[key] = []
        
        for deleg_id in delegation_ids:
            q_data = queryset_data.filter(id_delegation=deleg_id)
            geo_categories['Titulaires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_tit'))['total'] or 0))
            geo_categories['Vacataires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_vac'))['total'] or 0))
            geo_categories['Volontaires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_vol'))['total'] or 0))
            geo_categories['Partenaires'].append(int(q_data.aggregate(total=Sum('nb_pers_part'))['total'] or 0))
            geo_categories['Promoteurs'].append(int(q_data.aggregate(total=Sum('nb_pers_prom'))['total'] or 0))

    else:
        # Par défaut, on groupe par région
        regions_list = queryset.values('id_region', 'region').distinct().order_by('region')
        labels_geo = [r['region'] if r['region'] else "Non spécifié" for r in regions_list]
        region_ids = [r['id_region'] for r in regions_list]
        geo_label = "Toutes les régions"
        
        # Total
        geo_categories['total'] = []
        for reg_id in region_ids:
            geo_categories['total'].append(queryset.filter(id_region=reg_id).count())
        
        # Par sexe
        geo_categories['homme'] = []
        geo_categories['femme'] = []
        for reg_id in region_ids:
            q = queryset.filter(id_region=reg_id)
            geo_categories['homme'].append(q.filter(sexe='M').count())
            geo_categories['femme'].append(q.filter(sexe='F').count())
        
        # Par type
        geo_categories['interieur'] = []
        geo_categories['exterieur'] = []
        for reg_id in region_ids:
            q = queryset.filter(id_region=reg_id)
            geo_categories['interieur'].append(q.filter(type='intérieur').count())
            geo_categories['exterieur'].append(q.filter(type='extérieur').count())
        
        # Par tranches d'âge
        age_keys = ['Moins de 26 ans', '26-29 ans', '30-39 ans', '40-49 ans', '50-59 ans', '60-62 ans', '63 ans et plus']
        for key in age_keys:
            geo_categories[key] = []
        
        for reg_id in region_ids:
            q = queryset.filter(id_region=reg_id)
            age_counts = {key: 0 for key in age_keys}
            for person in q:
                if person.date_de_naissance:
                    age = calculate_age(person.date_de_naissance)
                    if age < 26:
                        age_counts['Moins de 26 ans'] += 1
                    elif age < 30:
                        age_counts['26-29 ans'] += 1
                    elif age < 40:
                        age_counts['30-39 ans'] += 1
                    elif age < 50:
                        age_counts['40-49 ans'] += 1
                    elif age < 60:
                        age_counts['50-59 ans'] += 1
                    elif age < 63:
                        age_counts['60-62 ans'] += 1
                    else:
                        age_counts['63 ans et plus'] += 1
            for key in age_keys:
                geo_categories[key].append(age_counts[key])
        
        # Par nature
        nature_keys = ['Titulaires', 'Vacataires', 'Volontaires', 'Partenaires', 'Promoteurs']
        for key in nature_keys:
            geo_categories[key] = []
        
        for reg_id in region_ids:
            q_data = queryset_data.filter(id_region=reg_id)
            geo_categories['Titulaires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_tit'))['total'] or 0))
            geo_categories['Vacataires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_vac'))['total'] or 0))
            geo_categories['Volontaires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_vol'))['total'] or 0))
            geo_categories['Partenaires'].append(int(q_data.aggregate(total=Sum('nb_pers_part'))['total'] or 0))
            geo_categories['Promoteurs'].append(int(q_data.aggregate(total=Sum('nb_pers_prom'))['total'] or 0))

    # ==================== ÉVOLUTION TEMPORELLE ====================
    
    # Récupérer toutes les années disponibles
    annee_ids = Personnel.objects.values_list('id_periodicite', flat=True).distinct().order_by('id_periodicite')
    labels_annees = [str(annee) for annee in annee_ids if annee is not None]

    # Initialiser les séries d'évolution
    evolution = {
        'total': [],
        'homme': [],
        'femme': [],
        'Titulaires': [],
        'Vacataires': [],
        'Volontaires': [],
        'Partenaires': [],
        'Promoteurs': [],
        'Extérieur': [],   
        'Intérieur': [],  
        'Moins de 26 ans': [],
        '26-29 ans': [],
        '30-39 ans': [],
        '40-49 ans': [],
        '50-59 ans': [],
        '60-62 ans': [],
        '63 ans et plus': [],
    }

    # Calculer les données pour chaque année
    for annee in annee_ids:
        # Filtres de base pour l'année
        q_pers = Personnel.objects.filter(id_periodicite=annee)
        q_data = Data.objects.filter(id_periodicite=annee)
        
        # Appliquer les mêmes filtres région/délégation si présents
        if selected_region:
            q_pers = q_pers.filter(id_region=selected_region)
            q_data = q_data.filter(id_region=selected_region)
        if selected_delegation:
            try:
                q_pers = q_pers.filter(id_delegation=int(selected_delegation))
                q_data = q_data.filter(id_delegation=int(selected_delegation))
            except (ValueError, TypeError):
                pass

        # Total
        evolution['total'].append(q_pers.count())

        # Sexe
        evolution['homme'].append(q_pers.filter(sexe='M').count())
        evolution['femme'].append(q_pers.filter(sexe='F').count())

        # Type 
        evolution['Extérieur'].append(q_pers.filter(type='extérieur').count())
        evolution['Intérieur'].append(q_pers.filter(type='intérieur').count())

        # Nature (depuis Data model)
        evolution['Titulaires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_tit'))['total'] or 0))
        evolution['Vacataires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_vac'))['total'] or 0))
        evolution['Volontaires'].append(int(q_data.aggregate(total=Sum('nb_pers_entraide_vol'))['total'] or 0))
        evolution['Partenaires'].append(int(q_data.aggregate(total=Sum('nb_pers_part'))['total'] or 0))
        evolution['Promoteurs'].append(int(q_data.aggregate(total=Sum('nb_pers_prom'))['total'] or 0))

        # Tranches d'âge
        age_counts = {
            'Moins de 26 ans': 0,
            '26-29 ans': 0,
            '30-39 ans': 0,
            '40-49 ans': 0,
            '50-59 ans': 0,
            '60-62 ans': 0,
            '63 ans et plus': 0,
        }

        for person in q_pers:
            if person.date_de_naissance:
                age = calculate_age(person.date_de_naissance)
                if age < 26:
                    age_counts['Moins de 26 ans'] += 1
                elif age < 30:
                    age_counts['26-29 ans'] += 1
                elif age < 40:
                    age_counts['30-39 ans'] += 1
                elif age < 50:
                    age_counts['40-49 ans'] += 1
                elif age < 60:
                    age_counts['50-59 ans'] += 1
                elif age < 63:
                    age_counts['60-62 ans'] += 1
                else:
                    age_counts['63 ans et plus'] += 1

        for key in age_counts:
            evolution[key].append(age_counts[key])

    # ==================== CONTEXTE ====================
    context = {
        # Données principales
        'data': queryset,
        
        # KPI Cards
        'Personnels_count': Personnels_count,
        'pourcentage_filles': pourcentage_filles,
        'pourcentage_garcons': pourcentage_garcons,
        'interieur': interieur,
        'exterieur': exterieur,
        'taux_encadre': taux_encadre,
        
        # Filtres
        'annees': annees,
        'regions': regions,
        'delegations': delegations,
        'selected_annee': selected_annee,
        'selected_region': selected_region,
        'selected_delegation': selected_delegation,
        
        # Graphiques
        'labels_sexe': labels_sexe,
        'values_sexe': values_sexe,
        'labels_type': labels_type,
        'values_type': values_type,
        'labels_age': labels_age,
        'values_age': values_age,
        'labels_grades': labels_grades,
        'values_grades': values_grades,
        'labels_nature': labels_nature,
        'values_nature': values_nature,
        'labels_geo': labels_geo,
        'geo_label': geo_label,
        'geo_categories_json': json.dumps(geo_categories),
        'geo_categories_keys': list(geo_categories.keys()),
        
        # Évolution
        'labels_annees': labels_annees,
        'evolution_json': json.dumps(evolution),
        'evolution_keys': list(evolution.keys())
    }

    return render(request, 'personnel.html', context)