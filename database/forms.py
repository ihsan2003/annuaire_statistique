from django import forms
from datetime import datetime
from .models import Data, Axe, Personnel, Programme


class AxeForm(forms.ModelForm):
    class Meta:
        model = Axe
        fields = '__all__'
        widgets = {
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'delegation': forms.TextInput(attrs={'class': 'form-control'}),
            'axe': forms.TextInput(attrs={'class': 'form-control'}),
            'nb_centres': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_benef_m': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_benef_f': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_benef_t': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_periodicite': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_region': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_delegation': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class DataForm(forms.ModelForm):
    class Meta:
        model = Data
        fields = '__all__'
        widgets = {
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'delegation': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'date_construction': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'tel': forms.TextInput(attrs={'class': 'form-control'}),
            'fax': forms.TextInput(attrs={'class': 'form-control'}),
            'id_province': forms.NumberInput(attrs={'class': 'form-control'}),
            'addresse': forms.TextInput(attrs={'class': 'form-control'}),
            'id_str_superv': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_responsable': forms.NumberInput(attrs={'class': 'form-control'}),
            'milieu': forms.TextInput(attrs={'class': 'form-control'}),
            'superficie': forms.NumberInput(attrs={'class': 'form-control'}),
            'propriete': forms.TextInput(attrs={'class': 'form-control'}),
            'utilisation': forms.TextInput(attrs={'class': 'form-control'}),
            'etat': forms.TextInput(attrs={'class': 'form-control'}),
            'date_saisie': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'date_modif': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'id_commune': forms.NumberInput(attrs={'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'type_centre': forms.TextInput(attrs={'class': 'form-control'}),
            'nb_prn': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_sec': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_aux': forms.NumberInput(attrs={'class': 'form-control'}),
            'capacite': forms.NumberInput(attrs={'class': 'form-control'}),
            'date_ouvert_act': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'date_cessation': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'superficie_ac': forms.NumberInput(attrs={'class': 'form-control'}),
            'gestion': forms.TextInput(attrs={'class': 'form-control'}),
            'association': forms.TextInput(attrs={'class': 'form-control'}),
            'activite': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'id_service': forms.NumberInput(attrs={'class': 'form-control'}),
            'sous_categorie': forms.TextInput(attrs={'class': 'form-control'}),
            'type_activite': forms.TextInput(attrs={'class': 'form-control'}),
            'methode_calcul_benef': forms.TextInput(attrs={'class': 'form-control'}),
            'programme': forms.TextInput(attrs={'class': 'form-control'}),
            'sousaxe': forms.TextInput(attrs={'class': 'form-control'}),
            'axe': forms.TextInput(attrs={'class': 'form-control'}),
            'categorie': forms.TextInput(attrs={'class': 'form-control'}),
            'categorie2': forms.TextInput(attrs={'class': 'form-control'}),
            'abrev': forms.TextInput(attrs={'class': 'form-control'}),
            'cat': forms.TextInput(attrs={'class': 'form-control'}),
            'cat_programme': forms.TextInput(attrs={'class': 'form-control'}),
            'id_structure': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_centre': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_activite': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_periodicite': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_beneficiaires_m': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_beneficiaires_f': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_pers_entraide_tit': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'nb_pers_entraide_vac': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'nb_pers_entraide_vol': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'nb_pers_part': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'nb_pers_prom': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'nb_apparition': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_centres': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_beneficiaires_t': forms.NumberInput(attrs={'class': 'form-control'}),
            'fact_ben': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'taux_pauvre_reg': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'taux_pauvre_prov': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'taux_pauvre_comm': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'commune': forms.TextInput(attrs={'class': 'form-control'}),
            'priorite': forms.NumberInput(attrs={'class': 'form-control'}),
            'personnes_cibles': forms.TextInput(attrs={'class': 'form-control'}),
            'fcs': forms.NumberInput(attrs={'class': 'form-control'}),
            'categorie2aux': forms.TextInput(attrs={'class': 'form-control'}),
        }


class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = '__all__'
        widgets = {
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'delegation': forms.TextInput(attrs={'class': 'form-control'}),
            'som': forms.NumberInput(attrs={'class': 'form-control'}),
            'nom_prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'libelle_grade': forms.TextInput(attrs={'class': 'form-control'}),
            'echelle': forms.NumberInput(attrs={'class': 'form-control'}),
            'echellon': forms.NumberInput(attrs={'class': 'form-control'}),
            'indice': forms.NumberInput(attrs={'class': 'form-control'}),
            'fonction': forms.TextInput(attrs={'class': 'form-control'}),
            'lib_loc': forms.TextInput(attrs={'class': 'form-control'}),
            'sexe': forms.TextInput(attrs={'class': 'form-control'}),
            'date_de_naissance': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'type': forms.TextInput(attrs={'class': 'form-control'}),
            'id_periodicite': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_region': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_delegation': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ProgrammeForm(forms.ModelForm):
    class Meta:
        model = Programme
        fields = '__all__'
        widgets = {
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'delegation': forms.TextInput(attrs={'class': 'form-control'}),
            'cat_programme': forms.TextInput(attrs={'class': 'form-control'}),
            'nb_centres': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_benef_m': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_benef_f': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_benef_t': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_periodicite': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_region': forms.TextInput(attrs={'class': 'form-control'}),
            'id_delegation': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ImportAnnuaireForm(forms.Form):
    excel_file = forms.FileField(
        help_text='',
        widget=forms.FileInput(attrs={
            'accept': '.xlsx,.xls',
            'class': 'form-control'
        })
    )
    
    replace_existing = forms.BooleanField(
        label='Remplacer les données existantes',
        help_text='Cochez pour supprimer et remplacer toutes les données existantes',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    selected_year = forms.IntegerField(
        label='Année de référence (périodicité)',
        help_text='Sélectionnez l\'année si aucune colonne "id_periodicite" n\'existe dans le fichier',
        initial=datetime.now().year,
        min_value=2000,
        max_value=2050,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: 2025'
        })
    )
    
    def clean_excel_file(self):
        file = self.cleaned_data.get('excel_file')
        if file:
            if not file.name.endswith(('.xlsx', '.xls')):
                raise forms.ValidationError('Le fichier doit être au format Excel (.xlsx ou .xls)')
            
            # Limite de taille de fichier (ex: 10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Le fichier ne peut pas dépasser 10MB')
        
        return file
    
    def clean_selected_year(self):
        year = self.cleaned_data.get('selected_year')
        if year and (year < 2000 or year > 2050):
            raise forms.ValidationError('L\'année doit être entre 2000 et 2050')
        return year