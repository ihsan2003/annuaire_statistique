from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission

class CustomUser(AbstractUser):
    first_name = models.CharField(max_length=30, blank=False, verbose_name="Prénom")
    last_name = models.CharField(max_length=30, blank=False, verbose_name="Nom")
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True, verbose_name="Téléphone")
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True, verbose_name="Photo de profil")

    # Résolution des conflits ici :
    groups = models.ManyToManyField(
        Group,
        related_name='customuser_groups',
        blank=True,
        verbose_name='groups',
        help_text='The groups this user belongs to.',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_permissions',
        blank=True,
        verbose_name='user permissions',
        help_text='Specific permissions for this user.',
    )

    def __str__(self):
        return self.username


class Axe(models.Model):
    region = models.TextField(blank=True, null=True)
    delegation = models.TextField(blank=True, null=True)
    axe = models.TextField(blank=True, null=True)
    nb_centres = models.IntegerField(blank=True, null=True)
    nb_beneficiaires_m = models.IntegerField(db_column='nb_beneficiaires_m', blank=True, null=True)  # Field name made lowercase.
    nb_beneficiaires_f = models.IntegerField(db_column='nb_beneficiaires_f', blank=True, null=True)  # Field name made lowercase.
    nb_beneficiaires_t = models.IntegerField(db_column='nb_beneficiaires_t', blank=True, null=True)  # Field name made lowercase.
    id_periodicite = models.IntegerField(blank=True, null=True)
    id_region = models.IntegerField(blank=True, null=True)
    id_delegation = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'axe'


class Data(models.Model):
    id_region = models.IntegerField(blank=True, null=True)
    region = models.TextField(blank=True, null=True)
    id_delegation = models.IntegerField(blank=True, null=True)
    delegation = models.TextField(blank=True, null=True)
    code = models.TextField(blank=True, null=True)
    nom = models.TextField(blank=True, null=True)
    date_construction = models.DateTimeField(blank=True, null=True)
    tel = models.TextField(blank=True, null=True)
    fax = models.TextField(blank=True, null=True)
    id_province = models.IntegerField(blank=True, null=True)
    addresse = models.TextField(blank=True, null=True)
    id_str_superv = models.IntegerField(blank=True, null=True)
    id_responsable = models.IntegerField(blank=True, null=True)
    milieu = models.TextField(blank=True, null=True)
    superficie = models.FloatField(blank=True, null=True)
    propriete = models.TextField(blank=True, null=True)
    utilisation = models.TextField(blank=True, null=True)
    etat = models.TextField(blank=True, null=True)
    date_saisie = models.DateTimeField(blank=True, null=True)
    date_modif = models.DateTimeField(blank=True, null=True)
    id_commune = models.IntegerField(blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    type_centre = models.TextField(blank=True, null=True)
    nb_prn = models.IntegerField(blank=True, null=True)
    nb_sec = models.IntegerField(blank=True, null=True)
    nb_aux = models.IntegerField(blank=True, null=True)
    capacite = models.IntegerField(blank=True, null=True)
    date_ouvert_act = models.DateTimeField(blank=True, null=True)
    date_cessation = models.DateTimeField(blank=True, null=True)
    superficie_ac = models.FloatField(blank=True, null=True)
    gestion = models.TextField(blank=True, null=True)
    association = models.TextField(blank=True, null=True)
    activite = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    id_service = models.IntegerField(blank=True, null=True)
    sous_categorie = models.TextField(blank=True, null=True)
    type_activite = models.TextField(blank=True, null=True)
    methode_calcul_benef = models.TextField(blank=True, null=True)
    programme = models.TextField(blank=True, null=True)
    sousaxe = models.TextField(blank=True, null=True)
    axe = models.TextField(blank=True, null=True)
    categorie = models.TextField(blank=True, null=True)
    categorie2 = models.TextField(blank=True, null=True)
    abrev = models.TextField(blank=True, null=True)
    cat = models.TextField(db_column='CAT', blank=True, null=True)  # Field name made lowercase.
    cat_programme = models.TextField(blank=True, null=True)
    id_structure = models.IntegerField(blank=True, null=True)
    id_centre = models.IntegerField(blank=True, null=True)
    id_activite = models.IntegerField(blank=True, null=True)
    id_periodicite = models.IntegerField(blank=True, null=True)
    nb_beneficiaires_m = models.FloatField(blank=True, null=True)
    nb_beneficiaires_f = models.FloatField(blank=True, null=True)
    nb_pers_entraide_tit = models.FloatField(blank=True, null=True)
    nb_pers_entraide_vac = models.FloatField(blank=True, null=True)
    nb_pers_entraide_vol = models.FloatField(blank=True, null=True)
    nb_pers_part = models.FloatField(blank=True, null=True)
    nb_pers_prom = models.FloatField(blank=True, null=True)
    nb_apparition = models.IntegerField(blank=True, null=True)
    nb_centres = models.IntegerField(blank=True, null=True)
    nb_beneficiaires_t = models.FloatField(blank=True, null=True)
    fact_ben = models.IntegerField(blank=True, null=True)
    nb_count = models.IntegerField(blank=True, null=True)
    taux_pauvre_reg = models.FloatField(blank=True, null=True)
    taux_pauvre_prov = models.FloatField(blank=True, null=True)
    taux_pauvre_comm = models.FloatField(blank=True, null=True)
    commune = models.TextField(blank=True, null=True)
    priorite = models.IntegerField(blank=True, null=True)
    personnes_cibles = models.TextField(blank=True, null=True)
    fcs = models.IntegerField(blank=True, null=True)
    categorie2aux = models.TextField(blank=True, null=True)
    axe_updated = models.CharField(max_length=100, blank=True, null=True)
    programme_updated = models.CharField(max_length=255, blank=True, null=True)


    class Meta:
        managed = False
        db_table = 'data'

class Historique(models.Model):
    cat_programme = models.CharField(max_length=16, blank=True, null=True)
    nb_centre = models.CharField(max_length=5, blank=True, null=True)
    nb_beneficiaires_t = models.CharField(max_length=7, blank=True, null=True)
    id_periodicite = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'historique'


class Personnel(models.Model):
    region = models.TextField(blank=True, null=True)
    delegation = models.TextField(blank=True, null=True)
    som = models.IntegerField(blank=True, null=True)
    nom_prenom = models.TextField(blank=True, null=True)
    libelle_grade = models.TextField(blank=True, null=True)
    echelle = models.IntegerField(blank=True, null=True)
    echellon = models.IntegerField(blank=True, null=True)
    indice = models.IntegerField(blank=True, null=True)
    fonction = models.TextField(blank=True, null=True)
    lib_loc = models.TextField(blank=True, null=True)
    sexe = models.TextField(blank=True, null=True)
    date_de_naissance = models.DateTimeField(blank=True, null=True)
    type = models.TextField(blank=True, null=True)
    id_periodicite = models.IntegerField(blank=True, null=True)
    id_region = models.IntegerField(blank=True, null=True)
    id_delegation = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'personnel'


class Programme(models.Model):
    region = models.TextField(blank=True, null=True)
    delegation = models.TextField(blank=True, null=True)
    cat_programme = models.TextField(blank=True, null=True)
    nb_centres = models.IntegerField(blank=True, null=True)
    nb_benef_m = models.IntegerField(db_column='nb_benef_M', blank=True, null=True)  # Field name made lowercase.
    nb_benef_f = models.IntegerField(db_column='nb_benef_F', blank=True, null=True)  # Field name made lowercase.
    nb_benef_t = models.IntegerField(db_column='nb_benef_T', blank=True, null=True)  # Field name made lowercase.
    id_periodicite = models.IntegerField(blank=True, null=True)
    id_region = models.TextField(blank=True, null=True)
    id_delegation = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'programme'


class Centre(models.Model):
    region = models.TextField(blank=True, null=True)
    delegation = models.TextField(blank=True, null=True)
    nom = models.TextField(blank=True, null=True)
    milieu = models.TextField(blank=True, null=True)
    propriete = models.TextField(blank=True, null=True)
    capacite = models.IntegerField(blank=True, null=True)
    id_centre = models.TextField(blank=True, null=True)
    nb_centres = models.IntegerField(blank=True, null=True)
    id_periodicite = models.IntegerField(blank=True, null=True)
    id_delegation = models.IntegerField(blank=True, null=True)
    id_region = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'centre'


class Activite(models.Model):
    categorie2 = models.TextField(blank=True, null=True)
    nb_centres = models.TextField(blank=True, null=True)
    nb_beneficiaires_m = models.TextField(db_column='nb_beneficiaires_m', blank=True, null=True)  # Field name made lowercase.
    nb_beneficiaires_f = models.TextField(db_column='nb_beneficiaires_f', blank=True, null=True)  # Field name made lowercase.
    nb_beneficiaires_t = models.TextField(db_column='nb_beneficiaires_t', blank=True, null=True)  # Field name made lowercase.
    id_periodicite = models.TextField(blank=True, null=True)
    region = models.TextField(blank=True, null=True)
    delegation = models.TextField(blank=True, null=True)
    id_region = models.IntegerField(blank=True, null=True)
    id_delegation = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'activite'