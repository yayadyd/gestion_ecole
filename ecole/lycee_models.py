# ecole/lycee_models.py
"""
Modèles du Lycée - INDÉPENDANT des cycles 1er et 2e.
Gère : 10ème CG, 11ème séries, Terminale séries.
Matricule SAISI MANUELLEMENT (jamais régénéré).
Formule moyenne : (Composition × 2 + Note de classe) / 3.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from .models import AnneeScolaire, EcoleInfo


# =====================================================================
# 1. CATALOGUE DES MATIÈRES DU LYCÉE
# =====================================================================
class MatiereLycee(models.Model):
    """Catalogue des matières du lycée (indépendant du fondamental)."""
    
    DOMAINE_CHOICES = [
        ('LC', 'Langues et Communication'),
        ('SMT', 'Sciences, Mathématiques et Technologies'),
        ('SH', 'Sciences Humaines'),
        ('DP', 'Développement de la Personne'),
        ('OP', 'Orientation Professionnelle'),
    ]
    
    id_matiere = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=100, verbose_name="Nom de la matière")
    nom_arabe = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nom en arabe")
    domaine = models.CharField(max_length=5, choices=DOMAINE_CHOICES, verbose_name="Domaine")
    obligatoire = models.BooleanField(default=True, verbose_name="Matière obligatoire")
    ordre_affichage = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")
    active = models.BooleanField(default=True, verbose_name="Active")
    
    class Meta:
        verbose_name = "Matière (Lycée)"
        verbose_name_plural = "Matières (Lycée)"
        ordering = ['ordre_affichage', 'nom']
    
    def __str__(self):
        return self.nom


# =====================================================================
# 2. COEFFICIENTS PAR (MATIÈRE, NIVEAU, SÉRIE)
# =====================================================================
class CoefficientLycee(models.Model):
    """
    Coefficients des matières par niveau et série.
    Modifiables par le directeur (Option C).
    """
    
    NIVEAU_CHOICES = [
        ('10', '10ème Année'),
        ('11', '11ème Année'),
        ('12', 'Terminale'),
    ]
    
    SERIE_CHOICES = [
        ('', 'Aucune (10ème CG)'),
        # 11ème Année
        ('L', '11ème Lettres'),
        ('SES', '11ème Sciences Économiques et Sociales'),
        ('S', '11ème Sciences'),
        # Terminale
        ('TLL', 'Terminale Langues-Littératures'),
        ('TAL', 'Terminale Arts-Lettres'),
        ('TSS', 'Terminale Sciences Sociales'),
        ('TSEco', 'Terminale Sciences Économiques'),
        ('TSExp', 'Terminale Sciences Expérimentales'),
        ('TSE', 'Terminale Sciences Exactes'),
    ]
    
    id_coefficient = models.AutoField(primary_key=True)
    matiere = models.ForeignKey(MatiereLycee, on_delete=models.CASCADE, related_name='coefficients')
    niveau = models.CharField(max_length=2, choices=NIVEAU_CHOICES, verbose_name="Niveau")
    serie = models.CharField(max_length=10, choices=SERIE_CHOICES, blank=True, verbose_name="Série")
    coefficient = models.DecimalField(
        max_digits=3, decimal_places=1, default=1,
        verbose_name="Coefficient",
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('10'))]
    )
    
    class Meta:
        verbose_name = "Coefficient (Lycée)"
        verbose_name_plural = "Coefficients (Lycée)"
        unique_together = ('matiere', 'niveau', 'serie')
        ordering = ['niveau', 'serie', 'matiere__ordre_affichage']
    
    def __str__(self):
        return f"{self.matiere.nom} - {self.get_niveau_display()} {self.serie or 'CG'} (coef {self.coefficient})"


# =====================================================================
# 3. CLASSE DU LYCÉE
# =====================================================================
class ClasseLycee(models.Model):
    """
    Classe du lycée : 10ème CG1, 11ème L2, TLL1, TSS2, etc.
    Les indices (1, 2, ...) sont ajoutés si plusieurs classes du même niveau/série.
    """
    
    NIVEAU_CHOICES = [
        ('10', '10ème Année'),
        ('11', '11ème Année'),
        ('12', 'Terminale'),
    ]
    
    SERIE_CHOICES = [
        ('', 'Aucune (10ème CG)'),
        ('L', 'Lettres'),
        ('SES', 'Sciences Économiques et Sociales'),
        ('S', 'Sciences'),
        ('TLL', 'Terminale Langues-Littératures'),
        ('TAL', 'Terminale Arts-Lettres'),
        ('TSS', 'Terminale Sciences Sociales'),
        ('TSEco', 'Terminale Sciences Économiques'),
        ('TSExp', 'Terminale Sciences Expérimentales'),
        ('TSE', 'Terminale Sciences Exactes'),
    ]
    
    id_classe = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=50, verbose_name="Nom de la classe")
    niveau = models.CharField(max_length=2, choices=NIVEAU_CHOICES, verbose_name="Niveau")
    serie = models.CharField(max_length=10, choices=SERIE_CHOICES, blank=True, verbose_name="Série")
    annee_scolaire = models.ForeignKey(
        'AnneeScolaire', on_delete=models.CASCADE,
        verbose_name="Année scolaire", related_name='classes_lycee'
    )
    frais_inscription = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Frais d'inscription")
    frais_scolarite = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Frais de scolarité (annuel)")
    
    class Meta:
        verbose_name = "Classe (Lycée)"
        verbose_name_plural = "Classes (Lycée)"
        ordering = ['niveau', 'serie', 'nom']
        unique_together = ('nom', 'annee_scolaire')
    
    def __str__(self):
        return f"{self.nom} ({self.annee_scolaire})"
    
    @property
    def libelle_complet(self):
        if self.serie:
            return f"{self.get_niveau_display()} {self.serie} - {self.nom}"
        return f"{self.get_niveau_display()} CG - {self.nom}"


# =====================================================================
# 4. ÉLÈVE DU LYCÉE (MATRICULE SAISI MANUELLEMENT)
# =====================================================================
class EleveLycee(models.Model):
    """
    Élève du lycée. Le matricule est SAISI MANUELLEMENT.
    Il est unique et ne change JAMAIS.
    """
    
    SEXE_CHOICES = [('M', 'Masculin'), ('F', 'Féminin')]
    # Statut d'orientation
    STATUT_CHOICES = [
        ('oriente', 'Orienté par l\'État (gratuit)'),
        ('payant', 'Payant (frais à la charge des parents)'),
    ]

    id_eleve = models.AutoField(primary_key=True)
    matricule = models.CharField(
        max_length=50, unique=True,
        verbose_name="Matricule",
        help_text="Saisi manuellement. Unique et permanent."
    )
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, verbose_name="Sexe")
    date_naissance = models.DateField(verbose_name="Date de naissance")
    lieu_naissance = models.CharField(max_length=100, verbose_name="Lieu de naissance")
    pere = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nom du père")
    mere = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nom de la mère")
    contact_tuteur = models.CharField(max_length=40, blank=True, null=True, verbose_name="Contact du tuteur")
    adresse = models.TextField(max_length=200, blank=True, null=True, verbose_name="Adresse")
    photo = models.ImageField(upload_to='lycee/photos/', blank=True, null=True, verbose_name="Photo")
    
    # Acte de naissance
    numero_acte_naissance = models.CharField(max_length=100, blank=True, null=True, verbose_name="N° acte de naissance")
    date_delivrance_acte = models.DateField(blank=True, null=True, verbose_name="Date de délivrance")
    
    # Provenance
    ecole_provenance = models.CharField(max_length=150, blank=True, null=True, verbose_name="École de provenance (DEF)")
    annee_def = models.CharField(max_length=9, blank=True, null=True, verbose_name="Année du DEF")
    
    date_inscription = models.DateTimeField(auto_now_add=True)

    statut = models.CharField(
            max_length=20,
            choices=STATUT_CHOICES,
            default='payant',
            verbose_name="Statut",
            help_text="Orienté = l'État paie les frais. Payant = les parents paient."
        )
    
    class Meta:
        verbose_name = "Élève (Lycée)"
        verbose_name_plural = "Élèves (Lycée)"
        ordering = ['nom', 'prenom']
    
    def __str__(self):
        return f"{self.matricule} - {self.nom} {self.prenom}"
    
    def get_age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_naissance.year - (
            (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
        )


# =====================================================================
# 5. INSCRIPTION AU LYCÉE
# =====================================================================
class InscriptionLycee(models.Model):
    """Inscription d'un élève du lycée pour une année scolaire."""
        
    id_inscription = models.AutoField(primary_key=True)
    eleve = models.ForeignKey(EleveLycee, on_delete=models.CASCADE, verbose_name="Élève")
    classe = models.ForeignKey(ClasseLycee, on_delete=models.CASCADE, verbose_name="Classe")
    annee_scolaire = models.ForeignKey(
        'AnneeScolaire', on_delete=models.CASCADE,
        verbose_name="Année scolaire", related_name='inscriptions_lycee'
    )
    date_inscription = models.DateTimeField(auto_now_add=True)
    
    # Frais d'inscription historiques (comme pour le fondamental)
    frais_inscription_historique = models.BooleanField(
        default=False,
        verbose_name="Frais d'inscription déjà payés (avant l'app)"
    )
        
    class Meta:
        verbose_name = "Inscription (Lycée)"
        verbose_name_plural = "Inscriptions (Lycée)"
        unique_together = ('eleve', 'annee_scolaire')
        ordering = ['-annee_scolaire__anneeScolaire', 'eleve__nom']
    
    def __str__(self):
        return f"{self.eleve} - {self.classe} ({self.annee_scolaire})"

    @property
    def est_gratuite(self):
        """True si l'élève est orienté (pas de frais)."""
        return self.eleve.statut == 'oriente'
    
    @property
    def montant_attendu(self):
        """Montant total attendu pour cette inscription."""
        from decimal import Decimal
        if self.est_gratuite:
            return Decimal('0')
        return (
            Decimal(str(self.classe.frais_inscription or 0)) +
            Decimal(str(self.classe.frais_scolarite or 0))
        )

# =====================================================================
# 6. NOTES DU LYCÉE
# =====================================================================
class NoteLycee(models.Model):
    """
    Notes d'un élève du lycée pour un trimestre.
    - note_classe : moyenne des devoirs de classe (sur 20)
    - note_composition : note de composition (sur 20)
    - Moyenne matière = (Composition × 2 + Note de classe) / 3
    """
    
    TRIMESTRE_CHOICES = [
        ('Premier trimestre', 'Premier trimestre'),
        ('Deuxieme trimestre', 'Deuxieme trimestre'),
        ('Troisieme trimestre', 'Troisieme trimestre'),
    ]
    
    id_note = models.AutoField(primary_key=True)
    inscription = models.ForeignKey(InscriptionLycee, on_delete=models.CASCADE, related_name='notes')
    matiere = models.ForeignKey(MatiereLycee, on_delete=models.CASCADE, verbose_name="Matière")
    trimestre = models.CharField(max_length=50, choices=TRIMESTRE_CHOICES, verbose_name="Trimestre")
    note_classe = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        verbose_name="Note de classe",
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    note_composition = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        verbose_name="Note de composition",
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    
    class Meta:
        verbose_name = "Note (Lycée)"
        verbose_name_plural = "Notes (Lycée)"
        unique_together = ('inscription', 'matiere', 'trimestre')
        ordering = ['inscription', 'matiere__ordre_affichage']
    
    def __str__(self):
        return f"{self.inscription.eleve} - {self.matiere.nom} : {self.moyenne_matiere}"
    
    @property
    def moyenne_matiere(self):
        """Moyenne = (Composition × 2 + Note de classe) / 3."""
        return round((self.note_composition * Decimal('2') + self.note_classe) / Decimal('3'), 2)


# =====================================================================
# 7. RÉSULTAT TRIMESTRIEL (LYCÉE)
# =====================================================================
class ResultatTrimestreLycee(models.Model):
    """Résultat trimestriel d'un élève du lycée."""
    
    id_resultat = models.AutoField(primary_key=True)
    inscription = models.ForeignKey(InscriptionLycee, on_delete=models.CASCADE, related_name='resultats')
    trimestre = models.CharField(max_length=50, choices=NoteLycee.TRIMESTRE_CHOICES, verbose_name="Trimestre")
    moyenne_generale = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Moyenne générale")
    total_coefficients = models.DecimalField(max_digits=5, decimal_places=1, default=0, verbose_name="Total coefficients")
    total_notes_coefficientees = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Total notes coefficientées")
    rang = models.IntegerField(null=True, blank=True, verbose_name="Rang")
    effectif_classe = models.IntegerField(default=0, verbose_name="Effectif de la classe")
    appreciation = models.TextField(blank=True, null=True, verbose_name="Appréciation générale")
    date_calcul = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Résultat trimestriel (Lycée)"
        verbose_name_plural = "Résultats trimestriels (Lycée)"
        unique_together = ('inscription', 'trimestre')
        ordering = ['inscription__classe__nom', '-moyenne_generale']
    
    def __str__(self):
        return f"{self.inscription.eleve} - {self.trimestre} : {self.moyenne_generale}"


# =====================================================================
# 8. DÉTAIL DU RÉSULTAT (LYCÉE)
# =====================================================================
class DetailResultatLycee(models.Model):
    """Détail par matière d'un résultat trimestriel du lycée."""
    
    id_detail = models.AutoField(primary_key=True)
    resultat = models.ForeignKey(ResultatTrimestreLycee, on_delete=models.CASCADE, related_name='details')
    matiere = models.ForeignKey(MatiereLycee, on_delete=models.CASCADE, verbose_name="Matière")
    note_classe = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Note de classe")
    note_composition = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Note de composition")
    moyenne_matiere = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Moyenne de la matière")
    coefficient = models.DecimalField(max_digits=3, decimal_places=1, verbose_name="Coefficient")
    moyenne_coefficientee = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Moyenne coefficientée")
    appreciation = models.CharField(max_length=50, blank=True, null=True, verbose_name="Appréciation")
    
    class Meta:
        verbose_name = "Détail résultat (Lycée)"
        verbose_name_plural = "Détails résultats (Lycée)"
        unique_together = ('resultat', 'matiere')
        ordering = ['resultat', 'matiere__ordre_affichage']
    
    def __str__(self):
        return f"{self.resultat} - {self.matiere.nom} : {self.moyenne_matiere}"

# =====================================================================
# 9. PAIEMENT DU LYCÉE (aligné sur le modèle Paiement du fondamental)
# =====================================================================
class PaiementLycee(models.Model):
    """
    Paiement d'un élève du lycée.
    Système identique à Paiement (fondamental), mais indépendant.
    
    - est_inscription=True  → frais d'inscription
    - est_inscription=False → frais de scolarité
    - mois : utilisé pour le mode mensuel (comme le fondamental)
    """
    
    MOIS_SCOLAIRES = [
        (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
        (1, 'Janvier'), (2, 'Février'), (3, 'Mars'),
        (4, 'Avril'), (5, 'Mai'), (6, 'Juin'),
    ]
    MOIS_SCOLAIRES_ORDONNES = MOIS_SCOLAIRES
    
    id_paiement = models.AutoField(primary_key=True)
    inscription = models.ForeignKey(
        InscriptionLycee, on_delete=models.CASCADE,
        verbose_name="Inscription", related_name='paiements'
    )
    montant = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name="Montant (FCFA)"
    )
    date_paiement = models.DateField(
        auto_now_add=True, verbose_name="Date de paiement"
    )
    mois = models.IntegerField(
        choices=MOIS_SCOLAIRES, null=True, blank=True,
        verbose_name="Mois"
    )
    annee_paiement = models.IntegerField(
        default=2025, verbose_name="Année"
    )
    est_inscription = models.BooleanField(
        default=False,
        verbose_name="Paiement d'inscription"
    )
    observation = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name="Observation"
    )
    
    class Meta:
        verbose_name = "Paiement (Lycée)"
        verbose_name_plural = "Paiements (Lycée)"
        ordering = ['annee_paiement', 'mois', 'date_paiement']
    
    def __str__(self):
        if self.est_inscription:
            return f"{self.inscription} - Frais d'inscription: {self.montant} FCFA"
        return f"{self.inscription} - {self.montant} FCFA ({self.get_mois_display()} {self.annee_paiement})"
    
    @property
    def montant_attendu(self):
        """Montant attendu selon le type (frais d'inscription ou échéance)."""
        from decimal import Decimal
        from .lycee_services import calculer_echeances_lycee
        
        classe = self.inscription.classe
        ecole = EcoleInfo.get_solo()
        
        if self.est_inscription:
            return Decimal(str(classe.frais_inscription or 0))
        
        # Scolarité : chercher l'échéance correspondante
        echeances = calculer_echeances_lycee(ecole, classe, self.inscription.annee_scolaire)
        
        if self.mois:
            for ech in echeances:
                if ech.get('mois') == self.mois:
                    return ech['montant']
        
        return echeances[0]['montant'] if echeances else Decimal('0')
    
    def total_paye_pour_ce_mois(self):
        """Somme des paiements pour ce mois."""
        from django.db.models import Sum
        from decimal import Decimal
        
        if self.est_inscription:
            result = PaiementLycee.objects.filter(
                inscription=self.inscription,
                est_inscription=True,
                annee_paiement=self.annee_paiement,
            ).aggregate(Sum('montant'))['montant__sum']
            return result if result is not None else Decimal('0')
        
        result = PaiementLycee.objects.filter(
            inscription=self.inscription,
            est_inscription=False,
            mois=self.mois,
            annee_paiement=self.annee_paiement,
        ).aggregate(Sum('montant'))['montant__sum']
        return result if result is not None else Decimal('0')

# =====================================================================
# 10. EMPLOI DU TEMPS DU LYCÉE
# =====================================================================

class PlageHoraireLycee(models.Model):
    """
    Plage horaire du lycée (une seule liste pour tout le lycée).
    """
    id_plage = models.AutoField(primary_key=True)
    
    ordre = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage",
        help_text="Plus petit = affiché en premier"
    )
    
    heure_debut = models.TimeField(verbose_name="Heure de début")
    heure_fin = models.TimeField(verbose_name="Heure de fin")
    
    libelle = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name="Libellé",
        help_text="Ex: Récréation, Pause déjeuner"
    )
    
    est_pause = models.BooleanField(
        default=False,
        verbose_name="Est une pause",
        help_text="Cocher si c'est une pause (pas de matière possible)"
    )
    
    class Meta:
        verbose_name = "Plage horaire (Lycée)"
        verbose_name_plural = "Plages horaires (Lycée)"
        ordering = ['ordre', 'heure_debut']
        unique_together = ('heure_debut', 'heure_fin')
    
    def __str__(self):
        base = (
            f"{self.heure_debut.strftime('%H:%M')} - "
            f"{self.heure_fin.strftime('%H:%M')}"
        )
        return f"{base} ({self.libelle})" if self.libelle else base


class EmploiTempsLycee(models.Model):
    """Emploi du temps d'une classe du lycée pour une année scolaire."""
    
    id_emploi_temps = models.AutoField(primary_key=True)
    
    classe = models.ForeignKey(
        ClasseLycee, on_delete=models.CASCADE,
        verbose_name="Classe",
        related_name='emplois_temps'
    )
    
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE,
        verbose_name="Année scolaire",
        related_name='emplois_temps_lycee'
    )
    
    reconduit_depuis = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Reconduit depuis",
        help_text="Emploi du temps de l'année précédente dont celui-ci a été copié"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Emploi du temps (Lycée)"
        verbose_name_plural = "Emplois du temps (Lycée)"
        unique_together = ('classe', 'annee_scolaire')
        ordering = ['-annee_scolaire__anneeScolaire', 'classe__nom']
    
    def __str__(self):
        return f"Emploi du temps {self.classe.nom} - {self.annee_scolaire.anneeScolaire}"
    
    @property
    def nb_creneaux_remplis(self):
        return self.creneaux.exclude(matiere__isnull=True).count()


class CreneauEmploiTempsLycee(models.Model):
    """Un créneau dans un emploi du temps du lycée."""
    
    JOURS = [
        (1, 'Lundi'), (2, 'Mardi'), (3, 'Mercredi'),
        (4, 'Jeudi'), (5, 'Vendredi'), (6, 'Samedi'),
    ]
    
    id_creneau = models.AutoField(primary_key=True)
    
    emploi_temps = models.ForeignKey(
        EmploiTempsLycee, on_delete=models.CASCADE,
        verbose_name="Emploi du temps",
        related_name='creneaux'
    )
    
    jour = models.IntegerField(
        choices=JOURS, verbose_name="Jour de la semaine"
    )
    
    plage = models.ForeignKey(
        PlageHoraireLycee, on_delete=models.CASCADE,
        verbose_name="Plage horaire",
        related_name='creneaux'
    )
    
    matiere = models.ForeignKey(
        MatiereLycee, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Matière",
        related_name='creneaux_emploi'
    )
    
    salle = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name="Salle",
        help_text="Ex: Salle 1, Bâtiment B"
    )
    
    observation = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name="Observation",
        help_text="Note particulière (ex: Devoir surveillé)"
    )
    
    class Meta:
        verbose_name = "Créneau d'emploi du temps (Lycée)"
        verbose_name_plural = "Créneaux d'emploi du temps (Lycée)"
        ordering = ['jour', 'plage__ordre', 'plage__heure_debut']
        unique_together = ('emploi_temps', 'jour', 'plage')
    
    def __str__(self):
        matiere_str = self.matiere.nom if self.matiere else "(vide)"
        return f"{self.get_jour_display()} {self.plage} : {matiere_str}"


class MatiereClasseLycee(models.Model):
    """
    Matière enseignée dans une classe spécifique du lycée.
    Permet d'avoir des matières différentes selon les classes.
    """
    
    id_matiere_classe = models.AutoField(primary_key=True)
    
    classe = models.ForeignKey(
        ClasseLycee, on_delete=models.CASCADE,
        verbose_name="Classe",
        related_name='matieres_classe'
    )
    
    matiere = models.ForeignKey(
        MatiereLycee, on_delete=models.CASCADE,
        verbose_name="Matière",
        related_name='classes_concernees'
    )
    
    ordre_affichage = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage"
    )
    
    obligatoire = models.BooleanField(
        default=True,
        verbose_name="Matière obligatoire"
    )
    
    date_ajout = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Matière par classe (Lycée)"
        verbose_name_plural = "Matières par classe (Lycée)"
        unique_together = ('classe', 'matiere')
        ordering = ['classe__nom', 'ordre_affichage', 'matiere__nom']
    
    def __str__(self):
        return f"{self.classe.nom} - {self.matiere.nom}"