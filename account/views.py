# account/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import CustomUser
from .forms import CustomUserChangeForm
from django.views.generic import CreateView
from django.urls import reverse_lazy
from .forms import CustomUserCreationForm
from django.conf import settings
from django.contrib import messages
import os
from django.db import models 
from django.utils.decorators import method_decorator
from django.contrib.auth.views import PasswordChangeView
from django.db.models import Sum, Count, Q, Max, Avg
from .models import Data, Personnel, Centre, Programme, Axe, Activite, Historique
from django.core.cache import cache
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
import json
from django.http import JsonResponse
import psutil
import platform
from django.db import connection
import subprocess

class DashboardConstants:
    """Configuration centralisée pour le dashboard"""
    
    # Champs des bénéficiaires
    BENEF_FIELDS = {
        'total': 'nb_beneficiaires_t',
        'femmes': 'nb_beneficiaires_f',
        'hommes': 'nb_beneficiaires_m'
    }
    
    # Pondérations pour population cible "TC" (Toutes Catégories)
    PONDERATIONS_TC = {
        "Enfants en situation difficile": 0.28,
        "Femmes en situation difficile": 0.28,
        "Personnes en situation de handicap": 0.27,
        "Personnes âgées en situation difficile": 0.17
    }
    
    # Valeurs à exclure
    EXCLUDED_VALUES = {
        'general': ['Non spécifié', 'non specifie', 'Non specifié', 'non spécifié', '', None],
        'programme': ['SDF', 'sdf'],
        'region': ['test', 'Test', 'TEST']
    }
    
    # Cache keys
    CACHE_KEYS = {
        'dashboard_stats': 'dashboard_main_stats',
        'recent_activities': 'dashboard_recent_activities',
        'top_programs': 'dashboard_top_programs',
        'regional_stats': 'dashboard_regional_stats',
        'population_stats': 'dashboard_population_stats'
    }
    
    # Cache timeouts (en secondes)
    CACHE_TIMEOUTS = {
        'main': 3600,      # 1 heure
        'activities': 900,  # 15 minutes
        'stats': 1800      # 30 minutes
    }


class DashboardFilterService:
    """Service pour gérer les filtres du dashboard"""
    
    @staticmethod
    def apply_exclusion_filters(queryset, field_name: str, filter_type: str = 'general'):
        """Applique les filtres d'exclusion selon le type"""
        excluded_values = DashboardConstants.EXCLUDED_VALUES['general'].copy()
        
        if filter_type in DashboardConstants.EXCLUDED_VALUES:
            excluded_values.extend(DashboardConstants.EXCLUDED_VALUES[filter_type])
        
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
    def get_latest_year() -> str:
        """Récupère la dernière année disponible"""
        cache_key = "latest_year_dashboard"
        cached_year = cache.get(cache_key)
        
        if cached_year is None:
            data_years = Data.objects.values_list("id_periodicite", flat=True).distinct()
            activite_years = Activite.objects.values_list("id_periodicite", flat=True).distinct()
            all_years = [int(y) for y in set(list(data_years) + list(activite_years)) if y]
            cached_year = str(max(all_years)) if all_years else "2022"
            cache.set(cache_key, cached_year, DashboardConstants.CACHE_TIMEOUTS['main'])
        
        return cached_year


class DashboardPopulationService:
    """Service pour gérer les statistiques des populations cibles avec pondération"""
    
    @staticmethod
    def calculate_population_statistics() -> Dict[str, Any]:
        """Calcule les statistiques des populations cibles avec pondération TC"""
        cache_key = DashboardConstants.CACHE_KEYS['population_stats']
        cached_stats = cache.get(cache_key)
        
        if cached_stats is None:
            latest_year = DashboardFilterService.get_latest_year()
            
            # Queryset de base filtré
            qs = Data.objects.filter(id_periodicite=latest_year)
            qs = DashboardFilterService.apply_exclusion_filters(qs, 'region', 'region')
            
            # --- 1. Total des bénéficiaires "TC" (Toutes Catégories) ---
            total_tc = qs.filter(personnes_cibles='TC').aggregate(
                s=Sum(DashboardConstants.BENEF_FIELDS['total'])
            )['s'] or 0
            
            # --- 2. Queryset sans "TC" ni valeurs nulles ---
            qs_cible = qs.exclude(personnes_cibles='TC').exclude(personnes_cibles__isnull=True)
            
            # --- 3. Regroupement par population cible avec pondération ---
            grouped_data = qs_cible.values('personnes_cibles').annotate(
                total=Sum(DashboardConstants.BENEF_FIELDS['total'])
            )
            
            population_cible_data = []
            total_population_specifique = 0
            
            for g in grouped_data:
                label = g['personnes_cibles'] or "Non défini"
                total_val = g['total'] or 0
                
                # Application de la pondération TC si applicable
                if label in DashboardConstants.PONDERATIONS_TC:
                    ponderation = DashboardConstants.PONDERATIONS_TC[label]
                    total_val += total_tc * ponderation
                
                total_rounded = round(total_val)
                total_population_specifique += total_rounded
                
                population_cible_data.append({
                    'label': label,
                    'total': total_rounded,
                    'pourcentage': 0  # Calculé après
                })
            
            # --- 4. Calcul des pourcentages ---
            if total_population_specifique > 0:
                for pop_data in population_cible_data:
                    pop_data['pourcentage'] = round(
                        (pop_data['total'] / total_population_specifique) * 100, 1
                    )
            
            # --- 5. Tri par total décroissant ---
            population_cible_data.sort(key=lambda x: x['total'], reverse=True)
            
            # --- 6. Statistiques globales des populations ---
            stats_globales = {
                'total_tc_redistribue': total_tc,
                'total_population_specifique': total_population_specifique,
                'nb_categories_population': len(population_cible_data),
                'population_principale': population_cible_data[0] if population_cible_data else None,
                'repartition_detaillee': population_cible_data
            }
            
            cached_stats = stats_globales
            cache.set(cache_key, cached_stats, DashboardConstants.CACHE_TIMEOUTS['stats'])
        
        return cached_stats
    
    @staticmethod
    def get_demographic_breakdown_enhanced(total_beneficiaires: int, population_stats: Dict) -> Dict[str, Any]:
        """Calcule une répartition démographique enrichie basée sur les populations cibles"""
        
        # Récupération des totaux par catégorie depuis les stats de population
        repartition = population_stats.get('repartition_detaillee', [])
        
        # Mapping des populations aux catégories démographiques
        enfants = 0
        femmes = 0
        seniors = 0
        handicap = 0
        autres = 0
        
        for pop in repartition:
            label = pop['label'].lower()
            total = pop['total']
            
            if 'enfant' in label:
                enfants += total
            elif 'femme' in label:
                femmes += total
            elif 'âgée' in label or 'age' in label:
                seniors += total
            elif 'handicap' in label:
                handicap += total
            else:
                autres += total
        
        # Si pas assez de données spécifiques, utiliser les ratios par défaut
        if enfants == 0:
            enfants = int(total_beneficiaires * 0.27)
        if seniors == 0:
            seniors = int(total_beneficiaires * 0.18)
        if handicap == 0:
            handicap = int(total_beneficiaires * 0.15)
        
        # Ajustement pour éviter les dépassements
        total_specifique = enfants + femmes + seniors + handicap
        if total_specifique > total_beneficiaires:
            factor = total_beneficiaires / total_specifique
            enfants = int(enfants * factor)
            femmes = int(femmes * factor)
            seniors = int(seniors * factor)
            handicap = int(handicap * factor)
        
        autres = max(0, total_beneficiaires - enfants - femmes - seniors - handicap)
        
        return {
            'enfants': enfants,
            'femmes': femmes,
            'seniors': seniors,
            'handicap': handicap,
            'autres': autres,
            'total_verifie': enfants + femmes + seniors + handicap + autres
        }


class DashboardStatisticsService:
    """Service pour calculer les statistiques principales du dashboard"""
    
    @staticmethod
    def calculate_main_statistics() -> Dict[str, Any]:
        """Calcule les statistiques principales avec cache"""
        cache_key = DashboardConstants.CACHE_KEYS['dashboard_stats']
        cached_stats = cache.get(cache_key)
        
        if cached_stats is None:
            latest_year = DashboardFilterService.get_latest_year()
            
            # Requête principale pour les données les plus récentes
            data_qs = Data.objects.filter(id_periodicite=latest_year)
            data_qs = DashboardFilterService.apply_exclusion_filters(data_qs, 'region', 'region')
            
            # Statistiques principales
            stats = {
                'total_beneficiaires': data_qs.aggregate(
                    total=Sum(DashboardConstants.BENEF_FIELDS['total'])
                )['total'] or 0,
                
                'beneficiaires_hommes': data_qs.aggregate(
                    total=Sum(DashboardConstants.BENEF_FIELDS['hommes'])
                )['total'] or 0,
                
                'beneficiaires_femmes': data_qs.aggregate(
                    total=Sum(DashboardConstants.BENEF_FIELDS['femmes'])
                )['total'] or 0,
                
                'total_centres': data_qs.aggregate(
                    total=Sum('nb_centres')
                )['total'] or 0,
                
                'nb_regions': data_qs.values('region').distinct().count(),
                
                'nb_delegations': data_qs.values('delegation').distinct().count(),
                
                'total_programmes': data_qs.filter(
                    programme_updated__isnull=False
                ).exclude(
                    programme_updated__in=DashboardConstants.EXCLUDED_VALUES['programme']
                ).values('programme_updated').distinct().count(),
                
                'nb_axes': data_qs.filter(
                    axe_updated__isnull=False
                ).exclude(
                    axe_updated__in=DashboardConstants.EXCLUDED_VALUES['general']
                ).values('axe_updated').distinct().count(),
                
                'total_personnel': Personnel.objects.filter(
                    id_periodicite=latest_year
                ).count(),
                
                'latest_year': latest_year
            }
            
            # Calcul des évolutions (comparaison avec année précédente)
            previous_year = str(int(latest_year) - 1)
            previous_data = Data.objects.filter(id_periodicite=previous_year)
            previous_data = DashboardFilterService.apply_exclusion_filters(previous_data, 'region', 'region')
            
            previous_benef = previous_data.aggregate(
                total=Sum(DashboardConstants.BENEF_FIELDS['total'])
            )['total'] or 1  # Éviter division par zéro
            
            previous_personnel = Personnel.objects.filter(id_periodicite=previous_year).count() or 1
            
            # Calcul des pourcentages d'évolution
            stats['evolution_beneficiaires'] = round(
                ((stats['total_beneficiaires'] - previous_benef) / previous_benef) * 100, 1
            )
            stats['evolution_personnel'] = round(
                ((stats['total_personnel'] - previous_personnel) / previous_personnel) * 100, 1
            )
            
            # Evolution mensuelle approximative
            stats['evolution_mensuelle'] = int(stats['total_beneficiaires'] * 0.08)  # 8% approximatif
            
            cached_stats = stats
            cache.set(cache_key, cached_stats, DashboardConstants.CACHE_TIMEOUTS['main'])
        
        return cached_stats
    
    @staticmethod
    def calculate_demographic_breakdown(total_beneficiaires: int, beneficiaires_femmes: int) -> Dict[str, int]:
        """Calcule la répartition démographique approximative (méthode legacy)"""
        return {
            'enfants': int(total_beneficiaires * 0.27),  # 27% d'enfants
            'femmes': beneficiaires_femmes,
            'seniors': int(total_beneficiaires * 0.18),  # 18% de seniors
            'hommes_adultes': int(total_beneficiaires * 0.35)  # 35% d'hommes adultes
        }
    
    @staticmethod
    def get_regional_statistics() -> List[Dict]:
        """Récupère les statistiques par région avec cache"""
        cache_key = DashboardConstants.CACHE_KEYS['regional_stats']
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            latest_year = DashboardFilterService.get_latest_year()
            
            regional_stats = Data.objects.filter(id_periodicite=latest_year)
            regional_stats = DashboardFilterService.apply_exclusion_filters(regional_stats, 'region', 'region')
            regional_stats = regional_stats.values('region', 'id_region').annotate(
                beneficiaires=Sum(DashboardConstants.BENEF_FIELDS['total']),
                centres=Sum('nb_centres'),
                delegations=Count('delegation', distinct=True),
                programmes=Count('programme_updated', distinct=True)
            ).order_by('-beneficiaires')[:10]  # Top 10 régions
            
            cached_data = list(regional_stats)
            cache.set(cache_key, cached_data, DashboardConstants.CACHE_TIMEOUTS['stats'])
        
        return cached_data


class DashboardActivitiesService:
    """Service pour gérer les activités récentes"""
    
    @staticmethod
    def get_recent_activities() -> List[Dict]:
        """Récupère les activités récentes avec cache"""
        cache_key = DashboardConstants.CACHE_KEYS['recent_activities']
        cached_activities = cache.get(cache_key)
        
        if cached_activities is None:
            latest_year = DashboardFilterService.get_latest_year()
            
            # Centres récents (simulation basée sur les données disponibles)
            recent_centres = Data.objects.filter(
                id_periodicite=latest_year,
                nom__isnull=False
            ).exclude(nom='').values(
                'nom', 'region', 'delegation', 'nb_centres'
            ).distinct().order_by('-id')[:7]
    
            activities = []
            
            # Activités centres
            for centre in recent_centres:
                activities.append({
                    'type': 'centre',
                    'icon': 'fa-building',
                    'color': 'green',
                    'title': f"Centre: {centre['nom'][:30]}..." if len(centre['nom']) > 30 else centre['nom'],
                    'description': f"{centre['region']} - {centre['delegation']}",
                    'time': 'Récemment'
                })
        
            
            cached_activities = activities[:7]  # Limiter à 7 activités
            cache.set(cache_key, cached_activities, DashboardConstants.CACHE_TIMEOUTS['activities'])
        
        return cached_activities
    
    @staticmethod
    def get_top_programmes() -> List[Dict]:
        """Récupère les programmes les plus actifs avec cache"""
        cache_key = DashboardConstants.CACHE_KEYS['top_programs']
        cached_programs = cache.get(cache_key)
        
        if cached_programs is None:
            latest_year = DashboardFilterService.get_latest_year()
            
            top_programmes = Data.objects.filter(id_periodicite=latest_year)
            top_programmes = DashboardFilterService.apply_exclusion_filters(top_programmes, 'programme_updated', 'programme')
            top_programmes = top_programmes.values('programme_updated').annotate(
                total_benef=Sum(DashboardConstants.BENEF_FIELDS['total']),
                total_centres=Sum('nb_centres'),
                nb_delegations=Count('delegation', distinct=True)
            ).order_by('-total_benef')[:5]
            
            cached_programs = list(top_programmes)
            cache.set(cache_key, cached_programs, DashboardConstants.CACHE_TIMEOUTS['stats'])
        
        return cached_programs


class DashboardSystemService:
    """Service pour les informations système dynamiques"""
    
    @staticmethod
    def get_database_status() -> Dict[str, str]:
        """Vérifie le statut de la base de données"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return {
                'status': 'En ligne',
                'color': 'text-green-600',
                'icon': 'fa-check-circle'
            }
        except Exception:
            return {
                'status': 'Hors ligne',
                'color': 'text-red-600',
                'icon': 'fa-exclamation-triangle'
            }
    
    @staticmethod
    def get_active_users_count() -> int:
        """Compte les utilisateurs actifs basé sur les sessions"""
        try:
            # Sessions actives dans les dernières 30 minutes
            cutoff_time = timezone.now() - timedelta(minutes=30)
            active_sessions = Session.objects.filter(
                expire_date__gte=timezone.now()
            ).count()
            
            # Minimum 1 (utilisateur actuel)
            return max(active_sessions, 1)
        except Exception:
            return 1
    
    @staticmethod
    def get_system_version() -> str:
        """Récupère la version du système depuis settings ou fichier"""
        try:
            # Option 1: Depuis Django settings
            from django.conf import settings
            if hasattr(settings, 'APP_VERSION'):
                return settings.APP_VERSION
                
        except Exception:
            pass
        
        # Version par défaut
        return 'v0.0.0'
    
    @staticmethod
    def get_last_migration_date() -> str:
        """Récupère la date de la dernière migration"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT MAX(applied) 
                    FROM django_migrations 
                    WHERE app != 'sessions'
                """)
                result = cursor.fetchone()
                if result and result[0]:
                    return result[0].strftime('%d/%m/%Y à %H:%M')
        except Exception:
            pass
        
        return timezone.now().strftime('%d/%m/%Y à %H:%M')
    
    @staticmethod
    def get_server_uptime() -> str:
        """Calcule l'uptime du serveur"""
        try:
            if platform.system() == "Linux":
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.readline().split()[0])
                    uptime_days = int(uptime_seconds // 86400)
                    uptime_hours = int((uptime_seconds % 86400) // 3600)
                    return f"{uptime_days}j {uptime_hours}h"
            else:
                # Pour Windows/Mac, approximation basée sur psutil
                boot_time = psutil.boot_time()
                uptime_seconds = timezone.now().timestamp() - boot_time
                uptime_days = int(uptime_seconds // 86400)
                uptime_hours = int((uptime_seconds % 86400) // 3600)
                return f"{uptime_days}j {uptime_hours}h"
        except Exception:
            return "Indisponible"
    
    @staticmethod
    def get_memory_usage() -> Dict[str, Any]:
        """Récupère l'utilisation mémoire"""
        try:
            memory = psutil.virtual_memory()
            return {
                'used_percent': round(memory.percent, 1),
                'used_gb': round(memory.used / (1024**3), 1),
                'total_gb': round(memory.total / (1024**3), 1),
                'available_gb': round(memory.available / (1024**3), 1)
            }
        except Exception:
            return {
                'used_percent': 0,
                'used_gb': 0,
                'total_gb': 0,
                'available_gb': 0
            }
    
    @staticmethod
    def get_disk_usage() -> Dict[str, Any]:
        """Récupère l'utilisation du disque"""
        try:
            disk = psutil.disk_usage('/')
            return {
                'used_percent': round((disk.used / disk.total) * 100, 1),
                'used_gb': round(disk.used / (1024**3), 1),
                'total_gb': round(disk.total / (1024**3), 1),
                'free_gb': round(disk.free / (1024**3), 1)
            }
        except Exception:
            return {
                'used_percent': 0,
                'used_gb': 0,
                'total_gb': 0,
                'free_gb': 0
            }
    
    @staticmethod
    def get_cpu_usage() -> float:
        """Récupère l'utilisation CPU"""
        try:
            return round(psutil.cpu_percent(interval=1), 1)
        except Exception:
            return 0.0
    
    @staticmethod
    def get_database_size() -> Dict[str, Any]:
        """Récupère la taille de la base de données"""
        try:
            with connection.cursor() as cursor:
                # Pour PostgreSQL
                if 'postgresql' in connection.vendor:
                    cursor.execute("""
                        SELECT pg_size_pretty(pg_database_size(current_database()))
                    """)
                # Pour MySQL
                elif 'mysql' in connection.vendor:
                    cursor.execute("""
                        SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'DB Size in MB'
                        FROM information_schema.tables 
                        WHERE table_schema = DATABASE()
                    """)
                # Pour SQLite
                elif 'sqlite' in connection.vendor:
                    db_path = connection.settings_dict['NAME']
                    if os.path.exists(db_path):
                        size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
                        return {
                            'size_display': f"{size_mb} MB",
                            'size_mb': size_mb
                        }
                
                result = cursor.fetchone()
                if result:
                    return {
                        'size_display': str(result[0]),
                        'size_mb': 0  # Parsing complexe selon le SGBD
                    }
        except Exception:
            pass
        
        return {
            'size_display': "Indisponible",
            'size_mb': 0
        }
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Récupère toutes les informations système dynamiques"""
        cache_key = "system_info_dynamic"
        cached_info = cache.get(cache_key)
        
        if cached_info is None:
            db_status = DashboardSystemService.get_database_status()
            memory_info = DashboardSystemService.get_memory_usage()
            disk_info = DashboardSystemService.get_disk_usage()
            db_size = DashboardSystemService.get_database_size()
            
            cached_info = {
                # Informations de base
                'version_systeme': DashboardSystemService.get_system_version(),
                'derniere_maj': DashboardSystemService.get_last_migration_date(),
                'statut_bd': db_status['status'],
                'statut_bd_color': db_status['color'],
                'statut_bd_icon': db_status['icon'],
                'utilisateurs_connectes': DashboardSystemService.get_active_users_count(),
                
                # Informations serveur étendues
                'server_uptime': DashboardSystemService.get_server_uptime(),
                'cpu_usage': DashboardSystemService.get_cpu_usage(),
                'memory_usage': memory_info['used_percent'],
                'memory_used_gb': memory_info['used_gb'],
                'memory_total_gb': memory_info['total_gb'],
                'disk_usage': disk_info['used_percent'],
                'disk_used_gb': disk_info['used_gb'],
                'disk_total_gb': disk_info['total_gb'],
                'database_size': db_size['size_display'],
                
                # Métadonnées
                'platform': platform.system(),
                'python_version': platform.python_version(),
                'last_check': timezone.now().strftime('%d/%m/%Y à %H:%M:%S')
            }
            
            # Cache court pour les infos système (5 minutes)
            cache.set(cache_key, cached_info, 300)
        
        # Toujours mettre à jour les utilisateurs connectés (pas de cache)
        cached_info['utilisateurs_connectes'] = DashboardSystemService.get_active_users_count()
        
        return cached_info


    # Ajout pour la compatibilité avec votre code existant
    @staticmethod
    def get_performance_metrics() -> Dict[str, Any]:
        """Calcule des métriques de performance dynamiques"""
        from .models import Data  # Import local
        
        latest_year = DashboardFilterService.get_latest_year()
        system_info = DashboardSystemService.get_system_info()
        
        # Moyennes par centre (existant)
        avg_benef_par_centre = Data.objects.filter(
            id_periodicite=latest_year,
            nb_centres__gt=0
        ).aggregate(
            avg=models.Avg('nb_beneficiaires_t')
        )['avg'] or 0
        
        # Nouvelles métriques basées sur les ressources système
        total_centres = Data.objects.filter(id_periodicite=latest_year).aggregate(
            total=models.Sum('nb_centres')
        )['total'] or 1
        
        # Score d'efficacité basé sur les performances système
        cpu_score = max(0, 100 - system_info['cpu_usage'])
        memory_score = max(0, 100 - system_info['memory_usage'])
        disk_score = max(0, 100 - system_info['disk_usage'])
        
        efficiency_score = round((cpu_score + memory_score + disk_score) / 3, 1)
        
        return {
            'avg_benef_par_centre': round(avg_benef_par_centre),
            'taux_occupation': round((total_centres * 0.85), 1),
            'score_efficacite': efficiency_score,
            'performance_status': 'Optimal' if efficiency_score > 80 else 'Moyen' if efficiency_score > 60 else 'Attention'
        }



@login_required
def dashboard_api_stats(request):
    """API pour récupérer les stats en temps réel (AJAX)"""
    try:
        stats = DashboardStatisticsService.calculate_main_statistics()
        population_stats = DashboardPopulationService.calculate_population_statistics()
        
        return JsonResponse({
            'success': True,
            'data': {
                'main_stats': stats,
                'population_stats': population_stats
            },
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required 
def dashboard_clear_cache(request):
    """Vue pour vider le cache du dashboard (admin seulement)"""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    try:
        # Vider tous les caches du dashboard
        for cache_key in DashboardConstants.CACHE_KEYS.values():
            cache.delete(cache_key)
        
        # Vider aussi les caches auxiliaires
        cache.delete("latest_year_dashboard")
        
        return JsonResponse({
            'success': True, 
            'message': 'Cache dashboard vidé avec succès'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def dashboard_api_system_info(request):
    """API pour récupérer les infos système en temps réel (AJAX) — accès réservé aux superusers."""
    # Autorisation serveur : uniquement les superusers peuvent obtenir ces données
    if not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied'
        }, status=403)

    try:
        system_info = DashboardSystemService.get_system_info()
        return JsonResponse({
            'success': True,
            'data': system_info,
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



# Vérifie si l'utilisateur appartient à un groupe
def in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


# Vue pour l'admin
@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    """Vue principale du dashboard - Version optimisée avec services et populations cibles"""
    
    # === STATISTIQUES PRINCIPALES ===
    main_stats = DashboardStatisticsService.calculate_main_statistics()
    
    # === STATISTIQUES DES POPULATIONS CIBLES (avec pondération TC) ===
    population_stats = DashboardPopulationService.calculate_population_statistics()
    
    # === RÉPARTITION DÉMOGRAPHIQUE ENRICHIE ===
    demographic_stats_enhanced = DashboardPopulationService.get_demographic_breakdown_enhanced(
        main_stats['total_beneficiaires'], 
        population_stats
    )
    
    # === DONNÉES RÉGIONALES ===
    regional_stats = DashboardStatisticsService.get_regional_statistics()
    
    # === ACTIVITÉS RÉCENTES ===
    recent_activities = DashboardActivitiesService.get_recent_activities()
    
    # === PROGRAMMES ACTIFS ===
    top_programmes = DashboardActivitiesService.get_top_programmes()
    
    # === INFORMATIONS SYSTÈME DYNAMIQUES ===
    system_info = DashboardSystemService.get_system_info()
    
    # === MÉTRIQUES DE PERFORMANCE ===
    performance_metrics = DashboardSystemService.get_performance_metrics()
    
    # === DONNÉES POUR GRAPHIQUES (JSON) ===
    chart_data = {
        'regional_labels': [r['region'] for r in regional_stats],
        'regional_beneficiaires': [r['beneficiaires'] for r in regional_stats],
        'regional_centres': [r['centres'] for r in regional_stats],
        'programs_labels': [p['programme_updated'] for p in top_programmes],
        'programs_beneficiaires': [p['total_benef'] for p in top_programmes],
        # Nouvelles données pour les populations cibles
        'population_labels': [p['label'] for p in population_stats.get('repartition_detaillee', [])],
        'population_totaux': [p['total'] for p in population_stats.get('repartition_detaillee', [])],
        'population_pourcentages': [p['pourcentage'] for p in population_stats.get('repartition_detaillee', [])]
    }
    
    # === CONTEXTE COMPLET ===
    context = {
        # Statistiques principales
        'total_beneficiaires': main_stats['total_beneficiaires'],
        'total_centres': main_stats['total_centres'],
        'total_programmes': main_stats['total_programmes'],
        'total_personnel': main_stats['total_personnel'],
        'nb_regions': main_stats['nb_regions'],
        'nb_delegations': main_stats['nb_delegations'],
        'nb_axes': main_stats['nb_axes'],
        'latest_year': main_stats['latest_year'],
        
        # Évolutions
        'evolution_mensuelle': main_stats['evolution_mensuelle'],
        'evolution_beneficiaires': main_stats['evolution_beneficiaires'],
        'evolution_personnel': main_stats['evolution_personnel'],
        
        # Répartition démographique classique
        'beneficiaires_hommes': main_stats['beneficiaires_hommes'],
        'beneficiaires_femmes': main_stats['beneficiaires_femmes'],
        
        # Répartition démographique enrichie
        'enfants': demographic_stats_enhanced['enfants'],
        'femmes': demographic_stats_enhanced['femmes'],
        'seniors': demographic_stats_enhanced['seniors'],
        'handicap': demographic_stats_enhanced['handicap'],
        'autres_categories': demographic_stats_enhanced['autres'],
        
        # Statistiques des populations cibles
        'population_cible_data': population_stats.get('repartition_detaillee', []),
        'total_tc_redistribue': population_stats.get('total_tc_redistribue', 0),
        'nb_categories_population': population_stats.get('nb_categories_population', 0),
        'population_principale': population_stats.get('population_principale'),
        
        # Données régionales et programmes
        'regional_stats': regional_stats,
        'top_programmes': top_programmes,
        
        # Activités récentes
        'recent_activities': recent_activities,
        
        # Informations système
        **system_info,
        
        # Métriques de performance
        **performance_metrics,
        
        # Données pour graphiques (JSON)
        'chart_data': json.dumps(chart_data),
        
        # Métadonnées
        'page_title': 'Dashboard - Entraide Nationale',
        'last_updated': timezone.now().strftime('%d/%m/%Y à %H:%M'),
        
        # Informations sur la pondération TC
        'ponderations_tc': DashboardConstants.PONDERATIONS_TC,
    }
    
    return render(request, 'home_admin.html', context)



# Vue pour l'utilisateur
@login_required
def user_dashboard(request):
    """Vue principale du dashboard - Version optimisée avec services et populations cibles"""
    
    # === STATISTIQUES PRINCIPALES ===
    main_stats = DashboardStatisticsService.calculate_main_statistics()
    
    # === STATISTIQUES DES POPULATIONS CIBLES (avec pondération TC) ===
    population_stats = DashboardPopulationService.calculate_population_statistics()
    
    # === RÉPARTITION DÉMOGRAPHIQUE ENRICHIE ===
    demographic_stats_enhanced = DashboardPopulationService.get_demographic_breakdown_enhanced(
        main_stats['total_beneficiaires'], 
        population_stats
    )
    
    # === DONNÉES RÉGIONALES ===
    regional_stats = DashboardStatisticsService.get_regional_statistics()
    
    
    # === PROGRAMMES ACTIFS ===
    top_programmes = DashboardActivitiesService.get_top_programmes()
    
    
    # === DONNÉES POUR GRAPHIQUES (JSON) ===
    chart_data = {
        'regional_labels': [r['region'] for r in regional_stats],
        'regional_beneficiaires': [r['beneficiaires'] for r in regional_stats],
        'regional_centres': [r['centres'] for r in regional_stats],
        'programs_labels': [p['programme_updated'] for p in top_programmes],
        'programs_beneficiaires': [p['total_benef'] for p in top_programmes],
        # Nouvelles données pour les populations cibles
        'population_labels': [p['label'] for p in population_stats.get('repartition_detaillee', [])],
        'population_totaux': [p['total'] for p in population_stats.get('repartition_detaillee', [])],
        'population_pourcentages': [p['pourcentage'] for p in population_stats.get('repartition_detaillee', [])]
    }
    
    # === CONTEXTE COMPLET ===
    context = {
        # Statistiques principales
        'total_beneficiaires': main_stats['total_beneficiaires'],
        'total_centres': main_stats['total_centres'],
        'total_programmes': main_stats['total_programmes'],
        'total_personnel': main_stats['total_personnel'],
        'nb_regions': main_stats['nb_regions'],
        'nb_delegations': main_stats['nb_delegations'],
        'nb_axes': main_stats['nb_axes'],
        'latest_year': main_stats['latest_year'],
        
        # Évolutions
        'evolution_mensuelle': main_stats['evolution_mensuelle'],
        'evolution_beneficiaires': main_stats['evolution_beneficiaires'],
        'evolution_personnel': main_stats['evolution_personnel'],
        
        # Répartition démographique classique
        'beneficiaires_hommes': main_stats['beneficiaires_hommes'],
        'beneficiaires_femmes': main_stats['beneficiaires_femmes'],
        
        # Répartition démographique enrichie
        'enfants': demographic_stats_enhanced['enfants'],
        'femmes': demographic_stats_enhanced['femmes'],
        'seniors': demographic_stats_enhanced['seniors'],
        'handicap': demographic_stats_enhanced['handicap'],
        'autres_categories': demographic_stats_enhanced['autres'],
        
        # Statistiques des populations cibles
        'population_cible_data': population_stats.get('repartition_detaillee', []),
        'total_tc_redistribue': population_stats.get('total_tc_redistribue', 0),
        'nb_categories_population': population_stats.get('nb_categories_population', 0),
        'population_principale': population_stats.get('population_principale'),
        
        # Données régionales et programmes
        'regional_stats': regional_stats,
        'top_programmes': top_programmes,
        
        # Données pour graphiques (JSON)
        'chart_data': json.dumps(chart_data),
        
        # Métadonnées
        'page_title': 'Dashboard - Entraide Nationale',
        'last_updated': timezone.now().strftime('%d/%m/%Y à %H:%M'),
        
        # Informations sur la pondération TC
        'ponderations_tc': DashboardConstants.PONDERATIONS_TC,
    }
    
    return render(request, 'home_user.html', context)



# Redirection a l'acceuil selon rôle
@login_required
def home_view(request):
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    else:
        return redirect('user_dashboard')



@login_required
def profile_view(request):
    user = request.user  # Utilisateur connecté
    
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, request.FILES, instance=user)

        # Suppression de la photo de profil si l'utilisateur le demande
        if request.POST.get('remove_profile_picture'):
            if user.profile_picture and user.profile_picture.name:
                image_path = user.profile_picture.path
                if os.path.exists(image_path):
                    os.remove(image_path)

            user.profile_picture.delete(save=False)  # Supprime la photo sans enregistrer immédiatement
            user.save()
            messages.success(request, "Votre photo de profil a été supprimée avec succès.")
            return redirect('profile')

        # Vérification et mise à jour des informations
        if form.is_valid():
            user = form.save(commit=False)  # Ne sauvegarde pas encore pour modifier is_superuser
            
            role = request.POST.get('role')  # Récupérer le rôle sélectionné
            if role is not None:
                user.is_superuser = role == 'True'
                user.is_staff = user.is_superuser  # Nécessaire pour l'accès à l'admin Django

            user.save()  # Sauvegarde finale
            messages.success(request, "Votre profil a été mis à jour avec succès.")
            return redirect('profile')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")

    else:
        form = CustomUserChangeForm(instance=user)

    return render(request, 'profile.html', {'form': form})


@user_passes_test(lambda u: u.is_superuser)
def user_list(request):
    users = CustomUser.objects.all()
    return render(request, 'users/user_list.html', {'users': users})

@user_passes_test(lambda u: u.is_superuser)
def add_user(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('user_list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/user_form.html', {'form': form, 'title': 'Ajouter un utilisateur'})

@user_passes_test(lambda u: u.is_superuser)
def edit_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('user_list')
    else:
        form = CustomUserChangeForm(instance=user)
    return render(request, 'users/user_form.html', {'form': form, 'title': 'Modifier un utilisateur'})

@user_passes_test(lambda u: u.is_superuser)
def delete_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        user.delete()
        return redirect('user_list')
    return render(request, 'users/user_confirm_delete.html', {'user': user})


@method_decorator(login_required, name='dispatch')
class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'users/password_change.html'
    success_url = reverse_lazy('user_password_change_done')






