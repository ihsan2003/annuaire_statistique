from django.shortcuts import render, redirect, get_object_or_404
from django.forms import modelformset_factory
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
import json
from django.views import View
from django.apps import apps
from django.db.models import Count, Q, Sum
from django.core.paginator import Paginator
from django.db import models, connection
import plotly.express as px
import pandas as pd
from openpyxl import Workbook
from .models import Data, Personnel, Historique, Axe, Programme, Centre, Activite
from .forms import AxeForm, DataForm, PersonnelForm, ProgrammeForm, ImportAnnuaireForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.db import transaction
from difflib import get_close_matches
from datetime import datetime
import logging
import re
import html
from django.utils.decorators import method_decorator


# Tentative d'import du traducteur (optionnel)
TRANSLATOR_AVAILABLE = False
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Mapping des régions
REGION_MAPPING = {
    "Béni Mellal-Khénifra": 1,
    "Casablanca-Settat": 2,
    "Dakhla-Oued Ed-Dahab": 3,
    "Drâa-Tafilalet": 4,
    "Fès-Meknès": 5,
    "Guelmim-Oued Noun": 6,
    "L'Oriental": 7,
    "Laâyoune-Sakia El Hamra": 8,
    "Marrakech-Safi": 9,
    "Rabat-Salé-Kénitra": 10,
    "Souss-Massa": 11,
    "Tanger-Tétouan-Al Hoceïma": 12
}

# Mapping des délégations
DELEGATION_MAPPING = {
    "Agadir": 1, "Al Haouz": 2, "Al Hoceïma": 3, "Aousserd": 4, "Assa-Zag": 5,
    "Azilal": 6, "Aïn Chock": 7, "Aïn Sebaâ": 8, "Ben M'sick": 9, "Benslimane": 10,
    "Berkane": 11, "Berrechid": 12, "Boujdour": 13, "Boulemane": 14, "Béni-Mellal": 15,
    "Casablanca-Anfa": 17, "Chefchaouen": 18, "Chichaoua": 19, "Chtouka-Aït Baha": 20,
    "Dakhla": 21, "Driouch": 22, "El Hajeb": 23, "El Jadida": 24, "El Kelaâ des Sraghna": 25,
    "Errachidia": 26, "Es-Semara": 27, "Essaouira": 28, "Fahs-Anjra": 29, "Figuig": 30,
    "Fquih Ben Salah": 31, "Fès": 32, "Guelmim": 33, "Guercif": 34, "Hay hassani": 35,
    "Ifrane": 36, "Inezgane-Aït Melloul": 37, "Jerada": 38, "Khouribga": 39, "Khémisset": 40,
    "Khénifra": 41, "Kénitra": 42, "Larache": 43, "Laâyoune": 44, "M'diq-Fnideq": 45,
    "Marrakech": 46, "Meknès": 47, "Mers Sultan": 48, "Midelt": 49, "Mohammédia": 50,
    "Moulay Rachid": 51, "Moulay Yaâcoub": 52, "Médiouna": 53, "Nador": 54, "Nouaceur": 55,
    "Ouarzazate": 56, "Ouezzane": 57, "Oujda-Angad": 58, "Rabat": 59, "Rehamna": 60,
    "Safi": 61, "Salé": 62, "Settat": 63, "Sidi Bennour": 64, "Sidi Bernoussi": 65,
    "Sidi Ifni": 66, "Sidi Kacem": 67, "Sidi Slimane": 68, "Sefrou": 69, "Tan-Tan": 70,
    "Tanger": 71, "Taounate": 72, "Taourirt": 73, "Tarfaya": 74, "Taroudant": 75,
    "Tata": 76, "Taza": 77, "Tinghir": 78, "Tiznit": 79, "Témara": 80, "Tétouan": 81,
    "Youssoufia": 82, "Zagora": 83
}

# Mapping des délégations => regions
DELEGATION_TO_REGION_MAPPING = {
    # Béni Mellal-Khénifra
    "Azilal": "Béni Mellal-Khénifra",
    "Béni-Mellal": "Béni Mellal-Khénifra",
    "Fquih Ben Salah": "Béni Mellal-Khénifra",
    "Khouribga": "Béni Mellal-Khénifra",
    "Khénifra": "Béni Mellal-Khénifra",
    
    # Casablanca-Settat
    "Aïn Chock": "Casablanca-Settat",
    "Aïn Sebaâ": "Casablanca-Settat",
    "Ben M'sick": "Casablanca-Settat",
    "Benslimane": "Casablanca-Settat",
    "Berrechid": "Casablanca-Settat",
    "Casablanca-Anfa": "Casablanca-Settat",
    "Casablanca": "Casablanca-Settat",
    "El Jadida": "Casablanca-Settat",
    "Hay hassani": "Casablanca-Settat",
    "Mers Sultan": "Casablanca-Settat",
    "Mohammédia": "Casablanca-Settat",
    "Moulay Rachid": "Casablanca-Settat",
    "Médiouna": "Casablanca-Settat",
    "Nouaceur": "Casablanca-Settat",
    "Settat": "Casablanca-Settat",
    "Sidi Bennour": "Casablanca-Settat",
    "Sidi Bernoussi": "Casablanca-Settat",
    
    # Dakhla-Oued Ed-Dahab
    "Aousserd": "Dakhla-Oued Ed-Dahab",
    "Dakhla": "Dakhla-Oued Ed-Dahab",
    
    # Drâa-Tafilalet
    "Errachidia": "Drâa-Tafilalet",
    "Midelt": "Drâa-Tafilalet",
    "Ouarzazate": "Drâa-Tafilalet",
    "Tinghir": "Drâa-Tafilalet",
    "Zagora": "Drâa-Tafilalet",
    
    # Fès-Meknès
    "Boulemane": "Fès-Meknès",
    "El Hajeb": "Fès-Meknès",
    "Fès": "Fès-Meknès",
    "Ifrane": "Fès-Meknès",
    "Meknès": "Fès-Meknès",
    "Moulay Yaâcoub": "Fès-Meknès",
    "Séfrou": "Fès-Meknès",
    "Taounate": "Fès-Meknès",
    "Taza": "Fès-Meknès",
    
    # Guelmim-Oued Noun
    "Assa-Zag": "Guelmim-Oued Noun",
    "Guelmim": "Guelmim-Oued Noun",
    "Sidi Ifni": "Guelmim-Oued Noun",
    "Tan-Tan": "Guelmim-Oued Noun",
    
    # L'Oriental
    "Berkane": "L'Oriental",
    "Driouch": "L'Oriental",
    "Figuig": "L'Oriental",
    "Guercif": "L'Oriental",
    "Jerada": "L'Oriental",
    "Nador": "L'Oriental",
    "Oujda-Angad": "L'Oriental",
    "Taourirt": "L'Oriental",
    
    # Laâyoune-Sakia El Hamra
    "Boujdour": "Laâyoune-Sakia El Hamra",
    "Es-Semara": "Laâyoune-Sakia El Hamra",
    "Laâyoune": "Laâyoune-Sakia El Hamra",
    "Tarfaya": "Laâyoune-Sakia El Hamra",
    
    # Marrakech-Safi
    "Al Haouz": "Marrakech-Safi",
    "Chichaoua": "Marrakech-Safi",
    "Essaouira": "Marrakech-Safi",
    "Marrakech": "Marrakech-Safi",
    "Rehamna": "Marrakech-Safi",
    "Safi": "Marrakech-Safi",
    "Youssoufia": "Marrakech-Safi",
    "El Kelaâ des Sraghna": "Marrakech-Safi",
    
    # Rabat-Salé-Kénitra
    "Khémisset": "Rabat-Salé-Kénitra",
    "Kénitra": "Rabat-Salé-Kénitra",
    "Rabat": "Rabat-Salé-Kénitra",
    "Salé": "Rabat-Salé-Kénitra",
    "Sidi Slimane": "Rabat-Salé-Kénitra",
    "Témara": "Rabat-Salé-Kénitra",
    "Sidi Kacem": "Rabat-Salé-Kénitra",

    # Souss-Massa
    "Agadir": "Souss-Massa",
    "Chtouka-Aït Baha": "Souss-Massa",
    "Inezgane-Aït Melloul": "Souss-Massa",
    "Taroudant": "Souss-Massa",
    "Tiznit": "Souss-Massa",
    "Tata": "Souss-Massa",

    # Tanger-Tétouan-Al Hoceïma
    "Al Hoceïma": "Tanger-Tétouan-Al Hoceïma",
    "Chefchaouen": "Tanger-Tétouan-Al Hoceïma",
    "Fahs-Anjra": "Tanger-Tétouan-Al Hoceïma",
    "Larache": "Tanger-Tétouan-Al Hoceïma",
    "M'diq-Fnideq": "Tanger-Tétouan-Al Hoceïma",
    "Ouezzane": "Tanger-Tétouan-Al Hoceïma",
    "Tanger": "Tanger-Tétouan-Al Hoceïma",
    "Tétouan": "Tanger-Tétouan-Al Hoceïma",
}

# Définir les mappings des programmes spéciaux
SPECIAL_PROGRAMMES = {
        'Prise en charge des Enfants en situation difficile': 'EPS pour enfants en situation difficile',
        'Prise en charge des Personnes en situation difficile': 'EPS pour personnes en situation difficile', 
        'EPS personnes agées': 'EPS pour personnes âgées',
        'Centre pour femmes en situation difficile': 'EPS pour femmes en situation difficile',
        'EPS pour personnes handicapées': 'EPS pour personnes en situation de Handicap',
        'Centre d\'assistance sociale ( CAS )': 'Centres d\'Assistance Sociale (CAS)',
        'Cellule d\'assistance sociale ( CAS )': 'Centres d\'Assistance Sociale (CAS)',
        'CAS1': 'Centres d\'Assistance Sociale (CAS)',
        'Ecoute et Orientation': 'Centres d\'Assistance Sociale (CAS)',
        'Centre d\'assistance sociale ( CAS )_x000D_': 'Centres d\'Assistance Sociale (CAS)',
        'Unité de Protection de l\'Enfance (UPE)': 'Centres d\'Accompagnement pour la Protection de l\'Enfance (CAPE)',
        'Cellule d\'unité de Protection de l\'Enfance (UPE)': 'Centres d\'Accompagnement pour la Protection de l\'Enfance (CAPE)',
        'COAPH': 'Centre d\'Orientation et d\'Assistance pour les Personnes Handicapées (COAPH)',
        'Centre d\'Orientation et Assistance pour Personnes en situation d\'Handicap (COAPH)': 'Centre d\'Orientation et d\'Assistance pour les Personnes Handicapées (COAPH)',
        'Espace Multifonctionnel de la Femme (EMF)': 'Espace Multifonctionnel de la Femme (EMF)',
        'aide_alimentaire': 'Aide en nature pour personnes en situation de Handicap',
        'appui_scol2015': 'Appui à la scolarisation des enfants en situation de Handicap',
        'secours': 'Aides d\'urgence',
        'Animation Sociale': 'Dar Al Mouwaten(DAM)'
}
    
# Mapping programme vers axe
PROGRAMME_TO_AXE = {
        'Centres d\'Education et de Formation': 'Assistance à l\'inclusion et à l\'insertion sociale',
        'Espaces Alphabétisation': 'Assistance à l\'inclusion et à l\'insertion sociale',
        'Centres de Formation Professionnelle': 'Assistance à l\'inclusion et à l\'insertion sociale',
        'Jardins d\'Enfants': 'Assistance à l\'inclusion et à l\'insertion sociale',
        'EPS d\'appui à la scolarisation': 'Assistance à l\'inclusion et à l\'insertion sociale',
        'Dar Al Mouwaten(DAM)': 'Assistance à l\'inclusion et à l\'insertion sociale',
        'Centres pour personnes en situation de Handicap': 'Assistance à l\'inclusion et à l\'insertion sociale',
        'Appui à la scolarisation des enfants en situation de Handicap': 'Assistance à l\'inclusion et à l\'insertion sociale',
        
        'Centres d\'Assistance Sociale (CAS)': 'Assistance Sociale',
        'Centre d\'Orientation et d\'Assistance pour les Personnes Handicapées (COAPH)': 'Assistance Sociale',
        'Centres d\'Accompagnement pour la Protection de l\'Enfance (CAPE)': 'Assistance Sociale',
        'Espace Multifonctionnel de la Femme (EMF)': 'Assistance Sociale',
        
        'EPS pour personnes en situation difficile': 'Prestations sociales de prise en charge pour personnes en situation difficile',
        'EPS pour personnes en situation de Handicap': 'Prestations sociales de prise en charge pour personnes en situation difficile',
        'EPS pour personnes âgées': 'Prestations sociales de prise en charge pour personnes en situation difficile',
        'EPS pour femmes en situation difficile': 'Prestations sociales de prise en charge pour personnes en situation difficile',
        'EPS pour enfants en situation difficile': 'Prestations sociales de prise en charge pour personnes en situation difficile',
        
        'Aide en nature pour personnes en situation de Handicap': 'Solidarité et action humanitaire',
        'Aides d\'urgence': 'Solidarité et action humanitaire'
    }

@method_decorator(csrf_protect, name='dispatch')
class ImportAnnuaireView(View):
    """Vue pour importer un annuaire depuis un fichier Excel avec prétraitements avancés"""
    
    template_name = 'add_annuaire.html'
    form_class = ImportAnnuaireForm
    
    # Mapping des feuilles Excel vers les modèles Django
    SHEET_MODEL_MAPPING = {
        'data': Data,
        'Prestations': Data,
        'par_axe': Axe,
        'Axe': Axe,
        'par_programme': Programme,
        'Programme': Programme,
        'nb_centres': Centre,
        'Locaux': Centre,
        'Activite': Activite,
        'Personnel': Personnel
    }
    
    # Mapping des colonnes Excel vers les champs des modèles
    COLUMN_MAPPINGS = {
        'data' or 'Base': {
            'id_region': 'id_region',
            'region': 'region',
            'id_delegation': 'id_delegation',
            'delegation': 'delegation',
            'code': 'code',
            'nom': 'nom',
            'date_construction': 'date_construction',
            'tel': 'tel',
            'fax': 'fax',
            'id_province': 'id_province',
            'addresse': 'addresse',
            'id_str_superv': 'id_str_superv',
            'id_responsable': 'id_responsable',
            'milieu': 'milieu',
            'superficie': 'superficie',
            'propriete': 'propriete',
            'utilisation': 'utilisation',
            'etat': 'etat',
            'date_saisie': 'date_saisie',
            'date_modif': 'date_modif',
            'id_commune': 'id_commune',
            'latitude': 'latitude',
            'longitude': 'longitude',
            'type_centre': 'type_centre',
            'nb_prn': 'nb_prn',
            'nb_sec': 'nb_sec',
            'nb_aux': 'nb_aux',
            'capacite': 'capacite',
            'date_ouvert_act': 'date_ouvert_act',
            'date_cessation': 'date_cessation',
            'superficie_ac': 'superficie_ac',
            'gestion': 'gestion',
            'association': 'association',
            'activite': 'activite',
            'description': 'description',
            'id_service': 'id_service',
            'sous_categorie': 'sous_categorie',
            'type_activite': 'type_activite',
            'methode_calcul_benef': 'methode_calcul_benef',
            'programme': 'programme',
            'sousaxe': 'sousaxe',
            'axe': 'axe',
            'categorie': 'categorie',
            'categorie2': 'categorie2',
            'abrev': 'abrev',
            'CAT': 'cat',
            'cat_programme': 'cat_programme',
            'id_structure': 'id_structure',
            'id_centre': 'id_centre',
            'id_activite': 'id_activite',
            'id_periodicite': 'id_periodicite',
            'nb_centres': 'nb_centres',
            'nb_beneficiaires_m': 'nb_beneficiaires_m',
            'nb_beneficiaires_f': 'nb_beneficiaires_f',
            'nb_beneficiaires_t': 'nb_beneficiaires_t',
            'commune': 'commune',
            'priorite': 'priorite',
            'nb_pers_entraide_tit':	'nb_pers_entraide_tit',
            'nb_pers_entraide_vac':	'nb_pers_entraide_vac',
            'nb_pers_entraide_vol':	'nb_pers_entraide_vol',
            'nb_pers_part':	'nb_pers_part',
            'nb_pers_prom': 'nb_pers_prom',
            'personnes_cibles': 'personnes_cibles',
            'fcs': 'fcs',
            'categorie2aux': 'categorie2aux',
            'axe_updated': 'axe_updated',
            'programme_updated': 'programme_updated',
        },
        'par_axe' or 'Axe': {
            'region': 'region',
            'delegation': 'delegation',
            'axe': 'axe',
            'nb_centres': 'nb_centres',
            'nb_benef_M': 'nb_beneficiaires_m',
            'nb_benef_F': 'nb_beneficiaires_f',
            'nb_benef_T': 'nb_beneficiaires_t',
            'id_periodicite': 'id_periodicite',
            'id_region': 'id_region',
            'id_delegation': 'id_delegation',
        },
        'par_programme' or 'Programme': {
            'region': 'region',
            'delegation': 'delegation',
            'cat_programme': 'cat_programme',
            'nb_centres': 'nb_centres',
            'nb_benef_M': 'nb_beneficiaires_m',
            'nb_benef_F': 'nb_beneficiaires_f',
            'nb_benef_T': 'nb_beneficiaires_t',
            'id_periodicite': 'id_periodicite',
            'id_region': 'id_region',
            'id_delegation': 'id_delegation',
        },
        'nb_centres' or 'Locaux': {
            'region': 'region',
            'delegation': 'delegation',
            'nom': 'nom',
            'milieu': 'milieu',
            'propriete': 'propriete',
            'capacite': 'capacite',
            'id_centre': 'id_centre',
            'nb_centres': 'nb_centres',
            'id_periodicite': 'id_periodicite',
            'id_delegation': 'id_delegation',
            'id_region': 'id_region',
        },
        'Activite': {
            'region': 'region',
            'delegation': 'delegation',
            'nb_beneficiaires_m': 'nb_beneficiaires_m',
            'nb_beneficiaires_f': 'nb_beneficiaires_f',
            'nb_beneficiaires_t': 'nb_beneficiaires_t',
            'categorie2': 'categorie2',
            'nb_centres': 'nb_centres',
            'id_periodicite': 'id_periodicite',
            'id_delegation': 'id_delegation',
            'id_region': 'id_region',
        },
        'Personnel': {
            'region': 'region',
            'delegation': 'delegation',
            'som': 'som',
            'nom_prenom': 'nom_prenom',
            'libelle_grade': 'libelle_grade',
            'echelle': 'echelle', 
            'echellon': 'echellon',
            'indice': 'indice',
            'fonction': 'fonction',
            'lib_loc': 'lib_loc', 
            'sexe': 'sexe', 
            'date_de_naissance': 'date_de_naissance',
            'type': 'type', 
            'id_periodicite': 'id_periodicite', 
            'id_region': 'id_region', 
            'id_delegation':'id_delegation' 
        }
    }

    # Ajout des mappings pour les noms alternatifs
    COLUMN_MAPPINGS['Prestations'] = COLUMN_MAPPINGS['data']
    COLUMN_MAPPINGS['Axe'] = COLUMN_MAPPINGS['par_axe'] 
    COLUMN_MAPPINGS['Programme'] = COLUMN_MAPPINGS['par_programme']
    COLUMN_MAPPINGS['Locaux'] = COLUMN_MAPPINGS['nb_centres']

    # Ajouter cette méthode à votre classe pour récupérer le mapping
    def get_column_mapping(self, sheet_name):
        """Récupère le mapping des colonnes pour une feuille donnée"""
        return self.COLUMN_MAPPINGS.get(sheet_name, {})
    
    def get(self, request):
        """Affiche le formulaire d'import"""
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        """Traite l'import du fichier Excel avec prétraitements"""
        form = self.form_class(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                excel_file = form.cleaned_data['excel_file']
                selected_year = form.cleaned_data.get('selected_year')
                replace_existing = form.cleaned_data.get('replace_existing', False)
                
                # Traitement du fichier Excel avec prétraitements
                results = self.process_excel_file_with_preprocessing(
                    excel_file, selected_year, replace_existing
                )
                
                # Messages de succès
                total_imported = sum(results.values())
                messages.success(
                    request, 
                    f'Import réussi avec prétraitements ! {total_imported} enregistrements importés au total.'
                )
                
                # Détail par table
                for sheet_name, count in results.items():
                    if count > 0:
                        messages.info(request, f'- {sheet_name}: {count} enregistrements')
                
                return redirect('add_annuaire')
                
            except Exception as e:
                logger.error(f'Erreur lors de l\'import: {str(e)}', exc_info=True)
                messages.error(request, f'Erreur lors de l\'import: {str(e)}')
        
        return render(request, self.template_name, {'form': form})
    
    def process_excel_file_with_preprocessing(self, excel_file, selected_year=None, replace_existing=False):
        """Traite le fichier Excel avec tous les prétraitements"""
        results = {}
        
        try:
            # Lecture du fichier Excel
            excel_data = pd.read_excel(excel_file, sheet_name=None)
            logger.info(f"Feuilles trouvées dans le fichier: {list(excel_data.keys())}")
            
            with transaction.atomic():
                # Si remplacer les données existantes
                if replace_existing:
                    self.clear_existing_data(selected_year)
                
                # Traitement de chaque feuille avec préprocessing
                for sheet_name, df in excel_data.items():
                    if sheet_name in self.SHEET_MODEL_MAPPING:
                        logger.info(f"=== TRAITEMENT DE LA FEUILLE: {sheet_name} ===")
                        
                        # Appliquer tous les prétraitements
                        df_processed = self.preprocess_dataframe(df, sheet_name, selected_year)
                        
                        # Import des données prétraitées
                        count = self.import_sheet_data(
                            sheet_name, 
                            df_processed, 
                            selected_year
                        )
                        results[sheet_name] = count
                        logger.info(f"Feuille '{sheet_name}': {count} enregistrements importés")
                    else:
                        logger.warning(f"Feuille '{sheet_name}' ignorée (pas de mapping défini)")
                
            # Correction post-import des données région/délégation (en dehors de la transaction)
            try:
                self.fix_existing_region_delegation_data()
                logger.info("Correction post-import des régions/délégations effectuée")
            except Exception as fix_error:
                logger.warning(f"Erreur lors de la correction post-import: {str(fix_error)}")
                
        except Exception as e:
            logger.error(f'Erreur lors du traitement du fichier Excel: {str(e)}')
            raise
        
        return results
    
    def preprocess_dataframe(self, df, sheet_name, selected_year=None):
        """Applique tous les prétraitements sur un DataFrame"""
        logger.info(f"Début du préprocessing pour la feuille: {sheet_name}")
        logger.info(f"DataFrame initial - Lignes: {len(df)}, Colonnes: {len(df.columns)}")
        
        # 1. Nettoyage de base
        df = df.dropna(how='all')  # Supprime les lignes entièrement vides
        logger.info(f"Après suppression lignes vides: {len(df)} lignes")
        
        # 2. Correction des régions et délégations
        df = self.correct_regions_delegations(df)
        
        # 3. Traitement des colonnes spécifiques
        if 'nom' in df.columns:
            df['nom'] = self.traiter_colonne_nom(df['nom'])
            logger.info("Traitement colonne 'nom' effectué")
        
        if 'personnes_cibles' in df.columns:
            df['personnes_cibles'] = self.traiter_colonne_personnes_cibles(df['personnes_cibles'])
            logger.info("Traitement colonne 'personnes_cibles' effectué")
        
        # 4. Calcul des bénéficiaires totaux
        df = self.calculer_beneficiaires_total(df)
        
        # 5. Traitement programme_updated et axe_updated (pour la feuille data)
        if sheet_name == 'data':
            df = self.traiter_programme_et_axe_updated(df)
        
        # 6. Ajout de l'année si nécessaire
        if selected_year and 'id_periodicite' not in df.columns:
            df['id_periodicite'] = selected_year
            logger.info(f"Ajout id_periodicite: {selected_year}")
        
        # 7. Nettoyage final
        df = df.fillna('')  # Remplace NaN restants par des chaînes vides
        
        logger.info(f"Préprocessing terminé - DataFrame final: {len(df)} lignes, {len(df.columns)} colonnes")
        return df
    
    def normalize_text(self, text):
        """Normalise le texte pour la comparaison"""
        if pd.isna(text) or text is None:
            return ""
        
        text = str(text).strip()
        # Supprimer les accents et caractères spéciaux pour la comparaison
        replacements = {
            'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a',
            'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
            'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
            'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
            'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
            'ç': 'c', 'ñ': 'n',
            '-': ' ', '_': ' ', '.': ' '
        }
        
        text_norm = text.lower()
        for old, new in replacements.items():
            text_norm = text_norm.replace(old, new)
        
        # Supprimer les espaces multiples
        text_norm = re.sub(r'\s+', ' ', text_norm).strip()
        return text_norm

    def get_region_from_delegation(self, delegation_name):
        """Récupère la région correcte à partir du nom de la délégation"""
        if pd.isna(delegation_name) or delegation_name is None:
            return None, None
        
        delegation_name = str(delegation_name).strip()
        
        # Recherche exacte d'abord
        if delegation_name in DELEGATION_TO_REGION_MAPPING:
            region_name = DELEGATION_TO_REGION_MAPPING[delegation_name]
            region_id = REGION_MAPPING.get(region_name)
            return region_name, region_id
        
        # Recherche par similarité
        delegation_names = list(DELEGATION_TO_REGION_MAPPING.keys())
        normalized_input = self.normalize_text(delegation_name)
        normalized_delegations = [self.normalize_text(d) for d in delegation_names]
        
        matches = get_close_matches(normalized_input, normalized_delegations, n=1, cutoff=0.6)
        if matches:
            # Trouver la délégation originale correspondante
            matched_index = normalized_delegations.index(matches[0])
            correct_delegation = delegation_names[matched_index]
            region_name = DELEGATION_TO_REGION_MAPPING[correct_delegation]
            region_id = REGION_MAPPING.get(region_name)
            return region_name, region_id
        
        logger.warning(f"Région non trouvée pour la délégation: {delegation_name}")
        return None, None

    def correct_region_name(self, region_name):
        """Corrige le nom de la région en utilisant la similarité"""
        if pd.isna(region_name) or region_name is None:
            return None, None
        
        region_name = str(region_name).strip()
        
        # Recherche exacte d'abord
        for correct_region in REGION_MAPPING.keys():
            if self.normalize_text(region_name) == self.normalize_text(correct_region):
                return correct_region, REGION_MAPPING[correct_region]
        
        # Recherche par similarité
        region_names = list(REGION_MAPPING.keys())
        normalized_input = self.normalize_text(region_name)
        normalized_regions = [self.normalize_text(r) for r in region_names]
        
        matches = get_close_matches(normalized_input, normalized_regions, n=1, cutoff=0.6)
        if matches:
            # Trouver la région originale correspondante
            matched_index = normalized_regions.index(matches[0])
            correct_region = region_names[matched_index]
            return correct_region, REGION_MAPPING[correct_region]
        
        logger.warning(f"Région non trouvée: {region_name}")
        return None, None

    def correct_delegation_name(self, delegation_name):
        """Corrige le nom de la délégation en utilisant la similarité"""
        if pd.isna(delegation_name) or delegation_name is None:
            return None, None
        
        delegation_name = str(delegation_name).strip()
        
        # Recherche exacte d'abord
        for correct_delegation in DELEGATION_MAPPING.keys():
            if self.normalize_text(delegation_name) == self.normalize_text(correct_delegation):
                return correct_delegation, DELEGATION_MAPPING[correct_delegation]
        
        # Recherche par similarité
        delegation_names = list(DELEGATION_MAPPING.keys())
        normalized_input = self.normalize_text(delegation_name)
        normalized_delegations = [self.normalize_text(d) for d in delegation_names]
        
        matches = get_close_matches(normalized_input, normalized_delegations, n=1, cutoff=0.6)
        if matches:
            # Trouver la délégation originale correspondante
            matched_index = normalized_delegations.index(matches[0])
            correct_delegation = delegation_names[matched_index]
            return correct_delegation, DELEGATION_MAPPING[correct_delegation]
        
        logger.warning(f"Délégation non trouvée: {delegation_name}")
        return None, None

    def correct_regions_delegations(self, df):
        """Corrige les noms des régions et délégations dans le DataFrame"""
        corrections_count = 0
        
        # S'assurer que les colonnes id_region et id_delegation existent
        if 'id_region' not in df.columns:
            df['id_region'] = None
        if 'id_delegation' not in df.columns:
            df['id_delegation'] = None
        
        # Correction des régions
        if 'region' in df.columns:
            logger.info("Correction des noms de régions...")
            for index, row in df.iterrows():
                if pd.notna(row['region']):
                    original_region = str(row['region']).strip()
                    
                    # Si la région est déjà un ID numérique, la convertir en nom
                    if original_region.isdigit():
                        region_id = int(original_region)
                        # Trouver le nom correspondant à cet ID
                        region_name = None
                        for name, id_val in REGION_MAPPING.items():
                            if id_val == region_id:
                                region_name = name
                                break
                        
                        if region_name:
                            df.at[index, 'region'] = region_name
                            df.at[index, 'id_region'] = region_id
                            corrections_count += 1
                            logger.debug(f"Région ID {region_id} convertie en '{region_name}'")
                        else:
                            logger.warning(f"ID région {region_id} non trouvé dans le mapping")
                    else:
                        # Correction du nom de région
                        correct_region, region_id = self.correct_region_name(original_region)
                        if correct_region:
                            if correct_region != original_region:
                                df.at[index, 'region'] = correct_region
                                corrections_count += 1
                                logger.debug(f"Région '{original_region}' corrigée en '{correct_region}'")
                            
                            # Assigner l'ID correspondant
                            if region_id:
                                df.at[index, 'id_region'] = region_id
                
            logger.info(f"Corrections régions: {corrections_count}")
        
        # Correction des délégations et cohérence région-délégation
        corrections_count = 0
        if 'delegation' in df.columns:
            logger.info("Correction des noms de délégations et cohérence région-délégation...")
            for index, row in df.iterrows():
                if pd.notna(row['delegation']):
                    original_delegation = str(row['delegation']).strip()
                    
                    # Si la délégation est déjà un ID numérique, la convertir en nom
                    if original_delegation.isdigit():
                        delegation_id = int(original_delegation)
                        # Trouver le nom correspondant à cet ID
                        delegation_name = None
                        for name, id_val in DELEGATION_MAPPING.items():
                            if id_val == delegation_id:
                                delegation_name = name
                                break
                        
                        if delegation_name:
                            df.at[index, 'delegation'] = delegation_name
                            df.at[index, 'id_delegation'] = delegation_id
                            corrections_count += 1
                            logger.debug(f"Délégation ID {delegation_id} convertie en '{delegation_name}'")
                            
                            # Correction automatique de la région basée sur la délégation
                            correct_region, correct_region_id = self.get_region_from_delegation(delegation_name)
                            if correct_region:
                                df.at[index, 'region'] = correct_region
                                if correct_region_id:
                                    df.at[index, 'id_region'] = correct_region_id
                        else:
                            logger.warning(f"ID délégation {delegation_id} non trouvé dans le mapping")
                    else:
                        # Correction du nom de délégation
                        correct_delegation, delegation_id = self.correct_delegation_name(original_delegation)
                        if correct_delegation:
                            if correct_delegation != original_delegation:
                                df.at[index, 'delegation'] = correct_delegation
                                corrections_count += 1
                                logger.debug(f"Délégation '{original_delegation}' corrigée en '{correct_delegation}'")
                            
                            # Assigner l'ID correspondant
                            if delegation_id:
                                df.at[index, 'id_delegation'] = delegation_id
                            
                            # Vérification cohérence région-délégation
                            correct_region, correct_region_id = self.get_region_from_delegation(correct_delegation)
                            if correct_region:
                                current_region = str(row.get('region', '')).strip() if pd.notna(row.get('region')) else ''
                                
                                # Si la région est vide, manquante ou incohérente
                                if not current_region or current_region != correct_region:
                                    df.at[index, 'region'] = correct_region
                                    if correct_region_id:
                                        df.at[index, 'id_region'] = correct_region_id
                                    corrections_count += 1
                                    logger.debug(f"Région mise à jour de '{current_region}' vers '{correct_region}' "
                                            f"pour la délégation '{correct_delegation}'")
            
            logger.info(f"Corrections délégations et cohérence: {corrections_count}")
        
        return df

    def traiter_colonne_nom(self, colonne):
        """Traite la colonne nom avec nettoyage, traduction et normalisation"""
        def traitement_texte(texte):
            # S'assurer que c'est une chaîne
            if pd.isna(texte) or texte is None:
                return None
            
            if not isinstance(texte, str):
                texte = str(texte)
            
            # Supprimer les espaces en début/fin
            texte = texte.strip()
            
            # Si vide après strip, retourner None
            if not texte:
                return None
            
            # Mettre la première lettre en majuscule
            texte = texte.capitalize()
            
            # Décoder les entités HTML
            texte = html.unescape(texte)
            
            # Traduire de l'arabe vers le français si nécessaire et disponible
            if TRANSLATOR_AVAILABLE and re.search(r'[\u0600-\u06FF]', texte):
                try:
                    texte = GoogleTranslator(source='ar', target='fr').translate(texte)
                    logger.debug(f"Traduction effectuée pour: {texte}")
                except Exception as e:
                    logger.debug(f"Erreur de traduction: {e}")
                    pass  # garder le texte tel quel en cas d'erreur
            
            # Supprimer les caractères spéciaux sauf les lettres, chiffres, espaces et tirets
            texte = re.sub(r'[^\w\s\-]', '', texte)
            
            # Supprimer les espaces multiples
            texte = re.sub(r'\s+', ' ', texte).strip()
            
            return texte if texte else None
        
        # Appliquer le traitement
        colonne_traitee = colonne.apply(traitement_texte)
        
        # Afficher les statistiques
        nb_valeurs_avec_interrogation = colonne_traitee.astype(str).str.contains(r'\?', regex=True, na=False).sum()
        nb_valeurs_nulles = colonne_traitee.isna().sum()
        nb_valeurs_traitees = len(colonne_traitee) - nb_valeurs_nulles
        
        logger.info(f"Traitement colonne nom - Valeurs traitées: {nb_valeurs_traitees}, "
                   f"Valeurs nulles: {nb_valeurs_nulles}, Valeurs avec '?': {nb_valeurs_avec_interrogation}")
        
        return colonne_traitee

    def traiter_colonne_personnes_cibles(self, colonne):
        """Traite la colonne personnes_cibles avec corrections standardisées"""
        
        # Dictionnaire des remplacements à effectuer
        corrections_pop = {
            'Enfants en sit. diff.': 'Enfants en situation difficile',
            'Femmes en sit. diff.': 'Femmes en situation difficile', 
            'Pers. en sit . hand.': 'Personnes en situation de handicap',        
            'Pers. âgés en sit. diff.': 'Personnes âgées en situation difficile',
            'Pers en sit hand': 'Personnes en situation de handicap',
            'Pers âgés en sit diff': 'Personnes âgées en situation difficile',
            'Enfants en sit diff': 'Enfants en situation difficile',
            'Femmes en sit diff': 'Femmes en situation difficile',
            'Enfance': 'Enfants en situation difficile',
            'Personnes Handicapées': 'Personnes en situation de handicap',
            '3ème âge': 'Personnes âgées en situation difficile'
        }
        
        # Nettoyer d'abord la colonne
        colonne_nettoyee = colonne.astype(str).str.strip()
        colonne_nettoyee = colonne_nettoyee.replace('nan', None)
        
        # Appliquer les corrections exactes
        colonne_corrigee = colonne_nettoyee.replace(corrections_pop)
        
        # Appliquer des corrections basées sur la similarité pour les variantes
        def correction_similarite(texte):
            if pd.isna(texte) or texte == 'None':
                return None
                
            texte = str(texte).strip()
            if not texte:
                return None
                
            # Recherche par similarité pour les variantes non exactes
            texte_norm = texte.lower().replace('.', '').replace(' ', '')
            
            for key, value in corrections_pop.items():
                key_norm = key.lower().replace('.', '').replace(' ', '')
                if key_norm in texte_norm or texte_norm in key_norm:
                    return value
            
            return texte
        
        colonne_finale = colonne_corrigee.apply(correction_similarite)
        
        # Afficher les valeurs corrigées et statistiques
        valeurs_uniques = colonne_finale.dropna().unique()
        logger.info(f"Traitement personnes_cibles - Valeurs uniques trouvées: {len(valeurs_uniques)}")
        for valeur in sorted(valeurs_uniques):
            logger.info(f"  - {valeur}")
        
        return colonne_finale

    def calculer_beneficiaires_total(self, df):
        """Calcule automatiquement nb_beneficiaires_t en sommant nb_beneficiaires_f et nb_beneficiaires_m"""
        
        # Identifier les colonnes de bénéficiaires
        beneficiaires_f_cols = []
        beneficiaires_m_cols = []
        beneficiaires_t_cols = []
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'nb_beneficiaires_f' in col_lower or 'nb_benef_f' in col_lower:
                beneficiaires_f_cols.append(col)
            elif 'nb_beneficiaires_m' in col_lower or 'nb_benef_m' in col_lower:
                beneficiaires_m_cols.append(col)
            elif 'nb_beneficiaires_t' in col_lower or 'nb_benef_t' in col_lower:
                beneficiaires_t_cols.append(col)
        
        if not beneficiaires_f_cols and not beneficiaires_m_cols:
            logger.info("Aucune colonne de bénéficiaires masculins/féminins trouvée pour le calcul")
            return df
        
        # Calculer pour chaque ensemble de colonnes trouvé
        for i, (col_f, col_m) in enumerate(zip(beneficiaires_f_cols, beneficiaires_m_cols)):
            # Déterminer le nom de la colonne total correspondante
            if i < len(beneficiaires_t_cols):
                col_t = beneficiaires_t_cols[i]
            else:
                # Créer une nouvelle colonne total si elle n'existe pas
                if 'nb_beneficiaires_f' in col_f:
                    col_t = col_f.replace('nb_beneficiaires_f', 'nb_beneficiaires_t')
                elif 'nb_benef_f' in col_f:
                    col_t = col_f.replace('nb_benef_f', 'nb_benef_t')
                else:
                    col_t = 'nb_beneficiaires_t'
            
            logger.info(f"Calcul des bénéficiaires totaux: {col_f} + {col_m} = {col_t}")
            
            # S'assurer que les colonnes sont numériques pour le calcul
            df[col_f] = pd.to_numeric(df[col_f], errors='coerce').fillna(0)
            df[col_m] = pd.to_numeric(df[col_m], errors='coerce').fillna(0)
            
            # Calculer la somme
            df[col_t] = df[col_f] + df[col_m]
            
            # Statistiques
            nb_calcules = (df[col_t] > 0).sum()
            total_f = df[col_f].sum()
            total_m = df[col_m].sum()
            total_t = df[col_t].sum()
            
            logger.info(f"Calcul terminé - Lignes avec total > 0: {nb_calcules}")
            logger.info(f"Totaux: F={total_f}, M={total_m}, T={total_t}")
        
        return df

    def traiter_programme_et_axe_updated(self, df):
        """Traite les colonnes programme_updated et axe_updated basées sur categorie2"""
        logger.info("Début du traitement programme_updated et axe_updated")
        
        # Créer les colonnes si elles n'existent pas
        if 'programme_updated' not in df.columns:
            df['programme_updated'] = None
        if 'axe_updated' not in df.columns:
            df['axe_updated'] = None
        
        # Chercher la colonne categorie2
        categorie2_col = None
        for col in df.columns:
            col_str = str(col).strip()
            col_lower = str(col).lower()
            if (col_lower == 'categorie2' or 'categorie2' in col_lower or col_str == 'categorie2'):
                categorie2_col = col
                break
        
        if categorie2_col is None:
            logger.warning("Colonne categorie2 non trouvée")
            return df
        
        logger.info(f"Colonne categorie2 trouvée: {categorie2_col}")
        
        # Compteurs pour statistiques
        programme_updated_count = 0
        axe_updated_count = 0
        
        # Traitement ligne par ligne
        for index, row in df.iterrows():
            categorie2_value = row[categorie2_col]
            
            if pd.isna(categorie2_value) or categorie2_value == '':
                df.at[index, 'programme_updated'] = 'Non spécifié'
                continue
            
            categorie2_str = str(categorie2_value).strip()
            
            # 1. Traitement programme_updated
            if categorie2_str in SPECIAL_PROGRAMMES:
                df.at[index, 'programme_updated'] = SPECIAL_PROGRAMMES[categorie2_str]
                programme_updated_count += 1
            else:
                # Pour tous les autres cas, programme_updated = categorie2
                df.at[index, 'programme_updated'] = categorie2_str
                programme_updated_count += 1
            
            # 2. Traitement axe_updated basé sur programme_updated
            programme_value = df.at[index, 'programme_updated']
            if programme_value and programme_value in PROGRAMME_TO_AXE:
                df.at[index, 'axe_updated'] = PROGRAMME_TO_AXE[programme_value]
                axe_updated_count += 1
        
        logger.info(f"Traitement terminé: {programme_updated_count} programmes mis à jour, {axe_updated_count} axes mis à jour")
        
        # Statistiques finales
        programmes_uniques = df['programme_updated'].nunique()
        axes_uniques = df['axe_updated'].nunique()
        logger.info(f"Programmes uniques: {programmes_uniques}, Axes uniques: {axes_uniques}")
        
        return df

    def fix_existing_region_delegation_data(self):
        """
        Fonction utilitaire pour corriger les données déjà importées
        où region/delegation contiennent des IDs au lieu de noms
        ET pour corriger les incohérences région-délégation
        """
        models_to_fix = [Data, Axe, Centre, Programme]
        reverse_region_mapping = {v: k for k, v in REGION_MAPPING.items()}
        reverse_delegation_mapping = {v: k for k, v in DELEGATION_MAPPING.items()}
        
        for model in models_to_fix:
            try:
                with transaction.atomic():  # Transaction séparée pour chaque modèle
                    model_name = model.__name__
                    logger.info(f"Correction des données pour le modèle {model_name}")
                    
                    # Correction des délégations d'abord
                    if hasattr(model, 'delegation'):
                        records_updated = 0
                        queryset = model.objects.all()
                        
                        for obj in queryset:
                            delegation_updated = False
                            
                            # Vérifier si delegation contient un ID numérique
                            if obj.delegation and str(obj.delegation).strip().isdigit():
                                delegation_id = int(str(obj.delegation).strip())
                                delegation_name = reverse_delegation_mapping.get(delegation_id)
                                
                                if delegation_name:
                                    obj.delegation = delegation_name
                                    # Mettre à jour id_delegation si le champ existe et qu'il est vide/incorrect
                                    if hasattr(obj, 'id_delegation'):
                                        if not obj.id_delegation or obj.id_delegation != delegation_id:
                                            obj.id_delegation = delegation_id
                                    delegation_updated = True
                            
                            # Si delegation contient un nom, vérifier que id_delegation est correct
                            elif obj.delegation and not str(obj.delegation).strip().isdigit():
                                delegation_name = str(obj.delegation).strip()
                                delegation_id = DELEGATION_MAPPING.get(delegation_name)
                                
                                if delegation_id and hasattr(obj, 'id_delegation'):
                                    if not obj.id_delegation or obj.id_delegation != delegation_id:
                                        obj.id_delegation = delegation_id
                                        delegation_updated = True
                            
                            if delegation_updated:
                                try:
                                    obj.save()
                                    records_updated += 1
                                except Exception as e:
                                    logger.error(f"Erreur sauvegarde {model_name} ID {obj.pk}: {e}")
                        
                        if records_updated > 0:
                            logger.info(f"{model_name}: {records_updated} délégations corrigées")
                    
                    # Correction des régions ensuite
                    if hasattr(model, 'region'):
                        records_updated = 0
                        queryset = model.objects.all()
                        
                        for obj in queryset:
                            region_updated = False
                            
                            # Vérifier si region contient un ID numérique
                            if obj.region and str(obj.region).strip().isdigit():
                                region_id = int(str(obj.region).strip())
                                region_name = reverse_region_mapping.get(region_id)
                                
                                if region_name:
                                    obj.region = region_name
                                    # Mettre à jour id_region si le champ existe et qu'il est vide/incorrect
                                    if hasattr(obj, 'id_region'):
                                        if not obj.id_region or obj.id_region != region_id:
                                            obj.id_region = region_id
                                    region_updated = True
                            
                            # Si region contient un nom, vérifier que id_region est correct
                            elif obj.region and not str(obj.region).strip().isdigit():
                                region_name = str(obj.region).strip()
                                region_id = REGION_MAPPING.get(region_name)
                                
                                if region_id and hasattr(obj, 'id_region'):
                                    if not obj.id_region or obj.id_region != region_id:
                                        obj.id_region = region_id
                                        region_updated = True
                            
                            if region_updated:
                                try:
                                    obj.save()
                                    records_updated += 1
                                except Exception as e:
                                    logger.error(f"Erreur sauvegarde {model_name} ID {obj.pk}: {e}")
                        
                        if records_updated > 0:
                            logger.info(f"{model_name}: {records_updated} régions corrigées")
                    
                    # Correction des incohérences région-délégation
                    if hasattr(model, 'region') and hasattr(model, 'delegation'):
                        records_updated = 0
                        queryset = model.objects.all()
                        
                        for obj in queryset:
                            if obj.delegation and obj.region:
                                # Obtenir la région correcte basée sur la délégation
                                correct_region, correct_region_id = self.get_region_from_delegation(obj.delegation)
                                
                                if correct_region and str(obj.region).strip() != correct_region:
                                    logger.warning(f"{model_name} ID {obj.pk}: Incohérence - Délégation '{obj.delegation}' "
                                                f"devrait être dans '{correct_region}' et non '{obj.region}'")
                                    
                                    # Corriger la région
                                    obj.region = correct_region
                                    if hasattr(obj, 'id_region') and correct_region_id:
                                        obj.id_region = correct_region_id
                                    
                                    try:
                                        obj.save()
                                        records_updated += 1
                                    except Exception as e:
                                        logger.error(f"Erreur correction cohérence {model_name} ID {obj.pk}: {e}")
                        
                        if records_updated > 0:
                            logger.info(f"{model_name}: {records_updated} incohérences région-délégation corrigées")
                            
            except Exception as e:
                logger.error(f"Erreur lors de la correction du modèle {model_name}: {str(e)}")

    def import_sheet_data(self, sheet_name, df, selected_year=None):
        """Importe les données d'une feuille spécifique"""
        model_class = self.SHEET_MODEL_MAPPING[sheet_name]
        column_mapping = self.COLUMN_MAPPINGS[sheet_name]
        
        # Le DataFrame est déjà prétraité
        imported_count = 0
        batch_size = 1000
        objects_to_create = []
        
        for index, row in df.iterrows():
            try:
                # Création de l'objet avec mapping des colonnes
                obj_data = {}
                
                for excel_col, model_field in column_mapping.items():
                    if excel_col in df.columns:
                        value = row[excel_col]
                        obj_data[model_field] = self.clean_value_for_model(value, model_field)
                
                # Ajout de l'année si pas présente dans les données
                if selected_year and 'id_periodicite' not in obj_data:
                    obj_data['id_periodicite'] = selected_year
                
                # Validation des données avant création
                self.validate_obj_data(obj_data, model_class, sheet_name, index + 1)
                
                # Création de l'objet
                obj = model_class(**obj_data)
                objects_to_create.append(obj)
                
                # Import par batch pour optimiser les performances
                if len(objects_to_create) >= batch_size:
                    try:
                        model_class.objects.bulk_create(objects_to_create, ignore_conflicts=True)
                        imported_count += len(objects_to_create)
                    except Exception as e:
                        logger.error(f'Erreur lors de l\'import batch dans {sheet_name}: {str(e)}')
                        # Essai d'import individuel en cas d'erreur de batch
                        for obj in objects_to_create:
                            try:
                                obj.save()
                                imported_count += 1
                            except Exception as individual_error:
                                logger.error(f'Erreur import individuel dans {sheet_name}: {str(individual_error)}')
                    finally:
                        objects_to_create = []
                    
            except Exception as e:
                logger.error(f'Erreur ligne {index + 1} dans {sheet_name}: {str(e)}')
                continue
        
        # Import des objets restants
        if objects_to_create:
            try:
                model_class.objects.bulk_create(objects_to_create, ignore_conflicts=True)
                imported_count += len(objects_to_create)
            except Exception as e:
                logger.error(f'Erreur lors de l\'import final dans {sheet_name}: {str(e)}')
                # Import individuel en cas d'erreur
                for obj in objects_to_create:
                    try:
                        obj.save()
                        imported_count += 1
                    except Exception as individual_error:
                        logger.error(f'Erreur import final individuel dans {sheet_name}: {str(individual_error)}')
        
        return imported_count
    
    def clean_value_for_model(self, value, field_name):
        """Nettoie et convertit les valeurs pour les modèles Django"""
        if pd.isna(value) or value == '' or str(value).strip() == '':
            return None
        
        # Liste des champs entiers
        integer_fields = [
            'id_region', 'id_delegation', 'id_province', 'id_str_superv', 'id_responsable',
            'id_commune', 'nb_prn', 'nb_sec', 'nb_aux', 'capacite', 'id_service',
            'id_structure', 'id_centre', 'id_activite', 'id_periodicite',
            'nb_apparition', 'nb_centres', 'fact_ben', 'nb_count', 'priorite', 'fcs',
            'echelle', 'echellon', 'indice', 'som'
        ]
        
        # Liste des champs flottants
        float_fields = [
            'superficie', 'superficie_ac', 'latitude', 'longitude', 
            'taux_pauvre_reg', 'taux_pauvre_prov', 'taux_pauvre_comm',
            'nb_pers_entraide_tit', 'nb_pers_entraide_vac', 'nb_pers_entraide_vol',
            'nb_pers_part', 'nb_pers_prom','nb_beneficiaires_m', 'nb_beneficiaires_f', 'nb_beneficiaires_t',
            'nb_benef_m', 'nb_benef_f', 'nb_benef_t'
        ]
        
        # Conversion des entiers
        if field_name in integer_fields:
            try:
                # Nettoyage de la valeur
                if isinstance(value, (int, float)):
                    if pd.isna(value):
                        return None
                    return int(value)
                else:
                    str_value = str(value).strip()
                    
                    # Supprimer les suffixes comme '.0'
                    if str_value.endswith('.0'):
                        str_value = str_value[:-2]
                    
                    # Vérifier si c'est vide après nettoyage
                    if not str_value or str_value.lower() in ['nan', 'none', 'null']:
                        return None
                    
                    # Conversion en entier
                    try:
                        return int(str_value)
                    except ValueError:
                        return int(float(str_value))
                        
            except (ValueError, TypeError) as e:
                logger.warning(f'Impossible de convertir "{value}" en entier pour le champ {field_name}: {e}')
                return None
        
        # Conversion des flottants
        elif field_name in float_fields:
            try:
                if isinstance(value, (int, float)):
                    return float(value) if not pd.isna(value) else None
                else:
                    str_value = str(value).strip()
                    if not str_value or str_value.lower() in ['nan', 'none', 'null']:
                        return None
                    return float(str_value)
            except (ValueError, TypeError) as e:
                logger.warning(f'Impossible de convertir "{value}" en flottant pour le champ {field_name}: {e}')
                return None
        
        # Conversion des dates
        elif field_name.startswith('date_'):
            try:
                if pd.notna(value) and str(value).strip() != '':
                    if isinstance(value, str):
                        str_value = str(value).strip()
                        if str_value.lower() in ['nan', 'none', 'null']:
                            return None
                        
                        # Gestion des formats de date courants
                        date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']
                        for fmt in date_formats:
                            try:
                                return datetime.strptime(str_value, fmt).date()
                            except ValueError:
                                continue
                    
                    # Utiliser pandas pour la conversion
                    return pd.to_datetime(value).date()
                return None
            except Exception as e:
                logger.warning(f'Impossible de convertir "{value}" en date pour le champ {field_name}: {e}')
                return None
        
        # Pour les champs texte
        else:
            if value is None or pd.isna(value):
                return None
            
            str_value = str(value).strip()
            if not str_value or str_value.lower() in ['nan', 'none', 'null']:
                return None
            
            return str_value

    def validate_obj_data(self, obj_data, model_class, sheet_name, row_number):
        """Valide les données avant création de l'objet"""
        try:
            # Création temporaire pour validation
            temp_obj = model_class(**obj_data)
            temp_obj.clean_fields(exclude=['id'])
        except ValidationError as e:
            logger.warning(f'Données invalides ligne {row_number} dans {sheet_name}: {e}')
            # Nettoyage des champs problématiques
            for field_name, errors in e.error_dict.items():
                if field_name in obj_data:
                    logger.warning(f'Suppression du champ problématique {field_name}: {obj_data[field_name]}')
                    obj_data[field_name] = None
        except Exception as e:
            logger.warning(f'Erreur de validation ligne {row_number} dans {sheet_name}: {str(e)}')
    
    def clear_existing_data(self, selected_year=None):
        """Supprime les données existantes selon l'année"""
        logger.info("Suppression des données existantes...")
        
        if selected_year:
            # Suppression par année
            Data.objects.filter(id_periodicite=selected_year).delete()
            Axe.objects.filter(id_periodicite=selected_year).delete()
            Programme.objects.filter(id_periodicite=selected_year).delete()
            Centre.objects.filter(id_periodicite=selected_year).delete()
        else:
            # Suppression complète
            Data.objects.all().delete()
            Axe.objects.all().delete()
            Programme.objects.all().delete()
            Centre.objects.all().delete()
        
        logger.info("Données existantes supprimées")


@csrf_exempt
def add_annuaire_corrected(request):
    """Vue fonction avec prétraitements intégrés"""
    if request.method == 'POST':
        form = ImportAnnuaireForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                excel_file = form.cleaned_data['excel_file']
                selected_year = form.cleaned_data.get('selected_year')
                replace_existing = form.cleaned_data.get('replace_existing', False)
                
                # Utiliser la vue classe pour le traitement
                view = ImportAnnuaireView()
                results = view.process_excel_file_with_preprocessing(
                    excel_file, selected_year, replace_existing
                )
                
                total_imported = sum(results.values())
                if total_imported > 0:
                    messages.success(request, 
                        f"Import réussi avec prétraitements ! {total_imported} enregistrements importés.")
                    for sheet_name, count in results.items():
                        if count > 0:
                            messages.info(request, f"- {sheet_name}: {count} enregistrements")
                else:
                    messages.warning(request, 'Aucune donnée importée.')
                
                return redirect('add_annuaire')
                
            except Exception as e:
                logger.error(f"Erreur lors de l'import : {str(e)}")
                messages.error(request, f"Erreur lors de l'import : {str(e)}")
    else:
        form = ImportAnnuaireForm()
    
    # Statistiques actuelles
    try:
        stats = {
            'axes': Axe.objects.count(),
            'centres': Centre.objects.count(),
            'programmes': Programme.objects.count(),
            'data': Data.objects.count(),
            'Activite': Activite.objects.count(),
            'Personnel': Personnel.objects.count(),
        }
    except:
        stats = {'axes': 0, 'centres': 0, 'programmes': 0, 'data': 0, 'Activite': 0, 'Personnel': 0}
    
    context = {
        'form': form,
        'stats': stats,
        'title': 'Import Annuaire Statistique avec Prétraitements'
    }
    
    return render(request, 'add_annuaire.html', context)

# Vue AJAX pour la progression (optionnelle)
@csrf_exempt
def import_progress(request):
    """API pour suivre la progression de l'import"""
    if request.method == 'POST':
        # Cette vue pourrait être utilisée pour un import asynchrone avec Celery
        # Pour l'instant, elle retourne un statut simple
        return JsonResponse({
            'status': 'processing',
            'progress': 50,
            'message': 'Import en cours...'
        })
    
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@login_required
def get_tables(request):
    """
    Vue principale pour afficher et gérer les tables avec pagination
    """
    allowed_tables = ['data', 'personnel', 'historique', 'axe', 'programme']

    # Récupération de toutes les tables existantes dans la DB
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            raw_tables = cursor.fetchall()
            all_tables = [t[0] for t in raw_tables]
    except Exception as e:
        messages.error(request, f"Erreur lors de l'accès à la base de données: {e}")
        return render(request, 'db.html', {'tables': [], 'selected_table': None})

    # Filtrer uniquement celles autorisées
    table_names = [t for t in all_tables if t in allowed_tables]

    # Table sélectionnée : via paramètre ou par défaut la première autorisée
    selected_table = request.GET.get("table", "").lower()
    if not selected_table and table_names:
        selected_table = table_names[0]
    elif selected_table not in table_names:
        selected_table = None

    rows = []
    columns = []
    
    if selected_table:
        try:
            with connection.cursor() as cursor:
                # Utiliser ORDER BY pour avoir un ordre cohérent pour la pagination
                cursor.execute(f"SELECT * FROM `{selected_table}` ORDER BY id ASC")
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
        except Exception as e:
            messages.error(request, f"Erreur lors de l'accès à la table {selected_table}: {e}")
            rows = []
            columns = []
            selected_table = None

    # Gestion des paramètres de pagination
    try:
        limit = int(request.GET.get("limit", 10))
        if limit <= 0 or limit > 100:  # Limiter pour éviter les abus
            limit = 10
    except (ValueError, TypeError):
        limit = 10

    # Gestion de la pagination
    page_obj = None
    has_data = bool(rows)
    
    if rows:
        paginator = Paginator(rows, limit)
        
        try:
            page_number = int(request.GET.get("page", 1))
            if page_number <= 0:
                page_number = 1
        except (ValueError, TypeError):
            page_number = 1

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            # Si la page demandée est trop élevée, aller à la dernière page
            page_obj = paginator.page(paginator.num_pages)

    context = {
        'tables': table_names,
        'selected_table': selected_table,
        'columns': columns,
        'rows': page_obj,  # C'est un objet Page maintenant
        'current_limit': limit,
        'has_data': has_data,
    }

    return render(request, 'db.html', context)


def get_model_by_name(table_name):
    # Capitalize juste la première lettre
    model_name = table_name.capitalize()  
    try:
        model = apps.get_model('database', model_name)
        return model
    except LookupError:
        return None

def get_pk_field_name(model):
    return model._meta.pk.name

FORM_MAP = {
    'axe': AxeForm,
    'data': DataForm,
    'personnel': PersonnelForm,
    'programme': ProgrammeForm,
}

@login_required
def insert_data(request):
    table_name = request.GET.get('table')
    form_class = FORM_MAP.get(table_name)

    if table_name == 'revenu':
        if request.method == 'POST':
            form = RevenuForm(request.POST)
            if form.is_valid():
                revenu_instance = form.save(commit=False)

                # Calcul du total des revenus
                fields_to_sum = [
                    revenu_instance.cotisations_membres,
                    revenu_instance.cotisations_beneficiaires,
                    revenu_instance.subvention_entraide,
                    revenu_instance.soutien_mds,
                    revenu_instance.soutien_menfp,
                    revenu_instance.soutien_indh,
                    revenu_instance.soutien_etab_publiques,
                    revenu_instance.subventions_collectivites,
                    revenu_instance.taxe_abattage,
                    revenu_instance.dons_bienfaiteurs,
                    revenu_instance.revenus_fixes,
                    revenu_instance.revenus_divers,
                ]

                revenu_instance.total_revenus = sum([f or 0 for f in fields_to_sum])
                revenu_instance.total_general_revenu = (revenu_instance.total_revenus or 0) + (revenu_instance.solde_annee_prec or 0)

                revenu_instance.save()

                messages.success(request, f"Enregistrement inséré avec succès dans la table {table_name}.")
                return redirect(f"/db/tables/?table={table_name}")
        else:
            form = RevenuForm()

    elif table_name == 'depense':
        if request.method == 'POST':
            form = DepenseForm(request.POST)
            if form.is_valid():
                depense = form.save(commit=False)
                depense.total_depenses_fonction = sum([
                    depense.achat_denrees_alimentaires or 0,
                    depense.salaires_indemnites or 0,
                    depense.abonnement or 0,
                    depense.activites_educatives or 0,
                    depense.autres_frais or 0
                ])
                depense.total_depenses = (depense.total_depenses_fonction or 0) + (depense.equip_entretien_construction or 0)
                depense.total_general_depenses = (depense.total_depenses or 0) + (depense.total_dettes or 0)
                depense.save()

                messages.success(request, f"Enregistrement inséré avec succès dans la table {table_name}.")
                return redirect(f"/db/tables/?table={table_name}")
        else:
            form = DepenseForm()

    elif table_name == 'finance':
        if request.method == 'POST':
            form = FinanceForm(request.POST)
            if form.is_valid():
                finance = form.save(commit=False)
                revenu = finance.id_revenu
                depense = finance.id_depense
                total_rev = revenu.total_general_revenu or 0
                total_dep = depense.total_general_depenses or 0

                if total_rev >= total_dep:
                    finance.excedent = total_rev - total_dep
                    finance.deficit = 0
                else:
                    finance.deficit = total_dep - total_rev
                    finance.excedent = 0

                finance.save()

                messages.success(request, f"Enregistrement inséré avec succès dans la table {table_name}.")
                return redirect(f"/db/tables/?table={table_name}")
        else:
            form = FinanceForm()

    elif form_class:
        form = form_class(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            form.save()

            messages.success(request, f"Enregistrement inséré avec succès dans la table {table_name}.")
            return redirect(f"/db/tables/?table={table_name}")

    return render(request, 'insert_data.html', {
        'form': form,
        'table_name': table_name,
        'error': None if form else f"Table inconnue : '{table_name}'"
    })

@login_required
def update_data(request):
    table_name = request.GET.get('table')
    record_id = request.GET.get('id')
    form_class = FORM_MAP.get(table_name)

    if not form_class or not record_id:
        messages.error(request, f"Erreur : table inconnue ou ID manquant ('{table_name}').")
        return redirect('/db/tables/')

    model_class = form_class._meta.model
    try:
        instance = get_object_or_404(model_class, pk=record_id)
    except:
        messages.error(request, f"L'enregistrement avec ID {record_id} est introuvable.")
        return redirect(f"/db/tables/?table={table_name}")

    if request.method == 'POST':
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Mise à jour effectuée avec succès.")
            return redirect(f"/db/tables/?table={table_name}")
        else:
            messages.warning(request, "Le formulaire contient des erreurs. Veuillez les corriger.")
    else:
        form = form_class(instance=instance)

    return render(request, 'insert_data.html', {
        'form': form,
        'table_name': table_name,
        'is_update': True,
    })

@login_required
def update_multiple(request):
    table_name = request.GET.get('table')
    ids = request.GET.get('ids')

    if not table_name:
        messages.error(request, "Paramètres manquants pour la mise à jour multiple.")
        return redirect('/db/tables/')

    if not ids:
        messages.warning(request, "Veuillez sélectionner au moins un enregistrement.")
        return redirect('/db/tables/')

    form_class = FORM_MAP.get(table_name)
    if not form_class:
        messages.error(request, f"Formulaire introuvable pour la table '{table_name}'.")
        return redirect('/db/tables/')

    model_class = form_class._meta.model
    id_list = ids.split(',')
    instances = model_class.objects.filter(pk__in=id_list)

    if not instances.exists():
        messages.error(request, "Aucun enregistrement correspondant aux IDs fournis.")
        return redirect(f'/db/tables/?table={table_name}')

    FormSet = modelformset_factory(model_class, form=form_class, extra=0)

    if request.method == 'POST':
        
        formset = FormSet(request.POST, queryset=instances)
        if formset.is_valid():
            for form in formset:
                obj = form.save(commit=False)
                obj.save()

            messages.success(request, "Mise à jour multiple effectuée avec succès.")
            return redirect(f"/db/tables/?table={table_name}")
        else:
            messages.warning(request, "Certaines données sont invalides.")
            for form in formset:
                print("Form errors:", form.errors)
    else:
        formset = FormSet(queryset=instances)

    return render(request, 'insert_data.html', {
        'formset': formset,
        'table_name': table_name,
        'ids': ids,
        'is_update': True,
        'is_multiple_update': True
    })

@login_required
def delete_data(request):
    table_name = request.GET.get('table')
    pk = request.GET.get('id')

    if not table_name or not pk:
        messages.error(request, "Paramètres manquants pour la suppression.")
        return redirect('/db/tables/')

    model_class = get_model_by_name(table_name)
    if not model_class:
        messages.error(request, f"Table inconnue : '{table_name}'.")
        return redirect('/db/tables/')

    try:
        instance = get_object_or_404(model_class, pk=pk)
    except Exception as e:
        messages.error(request, f"Erreur lors de la récupération de l'enregistrement : {str(e)}")
        return redirect(f"/db/tables/?table={table_name}")

    if request.method == 'POST':
        try:
            instance.delete()
            messages.success(request, f"L’enregistrement de la table '{table_name}' a été supprimé avec succès.")
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression : {str(e)}")
        return redirect(f"/db/tables/?table={table_name}")

    return render(request, 'db.html', {
        'object': instance,
        'table_name': table_name
    })

@login_required
def bulk_delete_data(request):
    if request.method != "POST":
        messages.error(request, "Méthode non autorisée. Utilisez POST.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    table_name = request.POST.get("table")
    ids_json = request.POST.get("ids")

    if not table_name:
        messages.error(request, "Le nom de la table est manquant.")
        return redirect(request.META.get('HTTP_REFERER', '/'))
    if not ids_json:
        messages.error(request, "Aucun identifiant fourni pour la suppression.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    try:
        ids = json.loads(ids_json)
    except json.JSONDecodeError:
        messages.error(request, "Format JSON des identifiants invalide.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    if not ids:
        messages.warning(request, "Veuillez sélectionner au moins un enregistrement.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    model = get_model_by_name(table_name)
    if not model:
        messages.error(request, f"Table inconnue : '{table_name}'.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    pk_field = get_pk_field_name(model)

    try:
        # Utilisation ORM pour supprimer en masse
        model.objects.filter(**{f"{pk_field}__in": ids}).delete()
        messages.success(request, f"{len(ids)} enregistrement(s) supprimé(s) avec succès de la table '{table_name}'.")
    except Exception as e:
        messages.error(request, f"Erreur lors de la suppression : {str(e)}")

    return redirect(request.META.get('HTTP_REFERER', f'/?table={table_name}'))


@login_required
def export_table_to_excel(request): 
    table_name = request.GET.get('table')
    if not table_name:
        return HttpResponse("Table non spécifiée", status=400)

    model = get_model_by_name(table_name)
    if not model:
        return HttpResponse("Modèle introuvable", status=404)

    queryset = model.objects.all()
    if not queryset.exists():
        return HttpResponse("Pas de données à exporter.", status=404)

    df = pd.DataFrame(list(queryset.values()))

    # Convertir les objets non exportables en chaîne
    for col in df.columns:
        df[col] = df[col].apply(lambda x: str(x) if isinstance(x, object) and not isinstance(x, (int, float, str, bool)) else x)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{table_name}.xlsx"'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=table_name)

    return response


@login_required
def export_multiple(request):
    table_name = request.GET.get('table')
    ids = request.GET.get('ids')

    if not table_name or not ids:
        messages.error(request, "Paramètres manquants pour l'exportation.")
        return redirect('/db/tables/')

    model = get_model_by_name(table_name)
    if not model:
        messages.error(request, f"Modèle introuvable pour la table '{table_name}'.")
        return redirect('/db/tables/')

    id_list = [int(pk) for pk in ids.split(',') if pk.isdigit()]
    pk_field = get_pk_field_name(model)

    queryset = model.objects.filter(**{f"{pk_field}__in": id_list})
    if not queryset.exists():
        messages.error(request, "Aucun enregistrement correspondant aux IDs fournis.")
        return redirect(f'/db/tables/?table={table_name}')

    df = pd.DataFrame(list(queryset.values()))
    for col in df.columns:
        df[col] = df[col].apply(lambda x: str(x) if isinstance(x, object) and not isinstance(x, (int, float, str, bool)) else x)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{table_name}_selection.xlsx"'
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Sélection")

    return response

    table_name = request.GET.get('table')
    ids = request.GET.get('ids')

    if not table_name :
        messages.error(request, "Paramètres manquants pour l'exportation.")
        return redirect('/db/tables/')

    if not ids:
        messages.warning(request, "Veuillez sélectionner au moins un enregistrement.")
        return redirect(f'/db/tables/?table={table_name}')


    try:
        # Obtenir dynamiquement le modèle
        model = apps.get_model('databases', table_name.lower().capitalize())
    except LookupError:
        messages.error(request, f"Module introuvable pour la table '{table_name}'.")
        return redirect('/db/tables/')

    # Liste des IDs valides
    id_list = [int(pk) for pk in ids.split(',') if pk.isdigit()]

    # Récupérer dynamiquement le nom du champ de la clé primaire
    pk_field_name = model._meta.pk.name

    # Filtrer dynamiquement selon le nom du champ de la clé primaire
    queryset = model.objects.filter(**{f"{pk_field_name}__in": id_list})

    if not queryset.exists():
        messages.error(request, "Aucun enregistrement correspondant aux IDs fournis.")
        return redirect(f'/db/tables/?table={table_name}')


    df = pd.DataFrame(list(queryset.values()))

    # Convertir objets complexes en chaînes
    for column in df.columns:
        df[column] = df[column].apply(lambda x: str(x) if isinstance(x, object) and not isinstance(x, (int, float, str, bool)) else x)

    # Préparer la réponse Excel
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{table_name}_selection.xlsx"'
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Sélection")

    return response