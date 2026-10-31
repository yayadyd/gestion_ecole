import unicodedata

from django.db import models, IntegrityError, transaction
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from ..utils.validators import validate_file_extension, validate_file_size

# 1. ########## ANNEE SCOLAIRE ##########

from .base import *


class Classe(models.Model):
    """
    Classe = groupe d'élèves dans un niveau donné.

    Le mode de paiement (inscription, scolarité) est défini au niveau
    de l'école (EcoleInfo). Chaque classe précise juste ses MONTANTS.
    """

    CYCLE_CHOICES = [
        ('1er', '1er Cycle'),
        ('2e', '2e Cycle'),
    ]

    CLASSES_1ER_CYCLE = [
        ('1ère Année A', '1ère Année A'),
        ('1ère Année B', '1ère Année B'),
        ('2ème Année A', '2ème Année A'),
        ('2ème Année B', '2ème Année B'),
        ('3ème Année A', '3ème Année A'),
        ('3ème Année B', '3ème Année B'),
        ('4ème Année A', '4ème Année A'),
        ('4ème Année B', '4ème Année B'),
        ('5ème Année A', '5ème Année A'),
        ('5ème Année B', '5ème Année B'),
        ('6ème Année A', '6ème Année A'),
        ('6ème Année B', '6ème Année B'),
    ]

    CLASSES_2E_CYCLE = [
        ('7ème Année A', '7ème Année A'),
        ('7ème Année B', '7ème Année B'),
        ('8ème Année A', '8ème Année A'),
        ('8ème Année B', '8ème Année B'),
        ('9ème Année A', '9ème Année A'),
        ('9ème Année B', '9ème Année B'),
    ]

    CLASSE = CLASSES_1ER_CYCLE + CLASSES_2E_CYCLE

    idClasse = models.AutoField(primary_key=True)

    nomClasse = models.CharField(
        choices=CLASSE,
        unique=True,
        max_length=50,
        verbose_name="Nom de la classe"
    )

    cycle = models.CharField(
        max_length=3,
        choices=CYCLE_CHOICES,
        default='2e',
        verbose_name="Cycle",
        help_text="Détermine le mode de calcul des moyennes"
    )

    class Meta:
        ordering = ['cycle', 'nomClasse']
        verbose_name = "Classe"
        verbose_name_plural = "Classes"

    def __str__(self):
        return self.nomClasse

    # =================================================================
    # PROPRIÉTÉS UTILES
    # =================================================================

    @property
    def est_1er_cycle(self):
        return self.cycle == '1er'

    @property
    def est_2e_cycle(self):
        return self.cycle == '2e'

    @property
    def nom_niveau(self):
        return self.nomClasse.rsplit(' ', 1)[0] if ' ' in self.nomClasse else self.nomClasse

    @property
    def suffixe(self):
        parts = self.nomClasse.rsplit(' ', 1)
        return parts[1] if len(parts) > 1 else ''



class FraisClasseAnnee(models.Model):
    """
    Frais spécifiques à une classe pour une année scolaire donnée.
    Permet de modifier les frais chaque année sans impacter l'historique.
    """
    classe = models.ForeignKey(
        Classe, 
        on_delete=models.CASCADE, 
        related_name='frais_annee',
        verbose_name="Classe"
    )
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, 
        on_delete=models.CASCADE,
        verbose_name="Année scolaire"
    )
    frais_inscription = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        default=0,
        verbose_name="Frais d'inscription"
    )
    frais_scolarite = models.DecimalField(
        max_digits=12, 
        decimal_places=0, 
        default=0,
        verbose_name="Frais de scolarité (annuel)"
    )

    class Meta:
        unique_together = ('classe', 'annee_scolaire')
        verbose_name = "Frais par classe et année"
        verbose_name_plural = "Frais par classe et année"
        ordering = ['annee_scolaire__anneeScolaire', 'classe__nomClasse']

    def __str__(self):
        return f"{self.classe.nomClasse} - {self.annee_scolaire.anneeScolaire} : {self.frais_scolarite} FCFA"

# 3. ########## ELEVE ##########


class Eleve(models.Model):
    SEXE_CHOICES = [('M', 'Masculin'), ('F', 'Féminin')]

    matricule = models.CharField(
        max_length=100, unique=True, blank=True,
        verbose_name="Matricule",
        help_text="Généré automatiquement"
    )
    prenomEleve = models.CharField(max_length=100, verbose_name="Prénom")
    nomEleve = models.CharField(max_length=100, verbose_name="Nom")
    sexe = models.CharField(
        max_length=1, choices=SEXE_CHOICES, null=True, blank=True,
        verbose_name="Sexe"
    )
    dateNaiss = models.DateField(verbose_name="Date de naissance")
    lieuNaiss = models.CharField(max_length=100, verbose_name="Lieu de naissance")
    pere = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nom du père")
    mere = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nom de la mère")
    contactTuteur = models.CharField(max_length=40, blank=True, null=True, verbose_name="Contact du tuteur")
    adresseTuteur = models.TextField(max_length=150, blank=True, null=True, verbose_name="Adresse du tuteur")
    photo = models.ImageField(
        upload_to='photos/eleves/', blank=True, null=True,
        verbose_name="Photo"
    )

    # --- Acte de naissance ---
    numero_acte_naissance = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="Numéro de l'acte de naissance",
        help_text="Numéro de délivrance (acte de naissance)"
    )
    date_delivrance_acte = models.DateField(
        blank=True, null=True,
        verbose_name="Date de délivrance de l'acte",
        help_text="Date de délivrance (acte de naissance)"
    )

    # --- Scolarité (proposition de passage) ---
    scolarite_1er_cycle = models.PositiveIntegerField(
        default=0,
        verbose_name="Scolarité 1er cycle",
        help_text="Années de scolarité au 1er cycle (avant l'entrée dans cet établissement)"
    )
    scolarite_2e_cycle = models.PositiveIntegerField(
        default=0,
        verbose_name="Scolarité 2e cycle",
        help_text="Années de scolarité au 2e cycle. Saisie initiale manuelle, puis mise à jour automatique chaque année."
    )
    scolarite_totale = models.PositiveIntegerField(
        default=0, editable=False,
        verbose_name="Scolarité totale",
        help_text="Calculé automatiquement : 1er cycle + 2e cycle"
    )

    # --- Redoublements (détection automatique, 3 emplacements) ---
    redoublement_1 = models.CharField(
        max_length=100, blank=True, null=True, editable=False,
        verbose_name="1er redoublement"
    )
    redoublement_2 = models.CharField(
        max_length=100, blank=True, null=True, editable=False,
        verbose_name="2e redoublement"
    )
    redoublement_3 = models.CharField(
        max_length=100, blank=True, null=True, editable=False,
        verbose_name="3e redoublement"
    )

    # --- Parcours scolaire (SAISIE MANUELLE) ---
    annee_recrutement = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Année de recrutement",
        help_text="Année scolaire d'entrée en 1ère Année (ex: 2022-2023). "
                  "À renseigner manuellement, même si l'élève a commencé dans une autre école."
    )
    ecole_recrutement = models.CharField(
        max_length=150, blank=True, null=True,
        verbose_name="École de recrutement",
        help_text="École où l'élève a fait sa 1ère Année"
    )
    ecole_fin_1er_cycle = models.CharField(
        max_length=150, blank=True, null=True,
        verbose_name="École de fin de 1er cycle",
        help_text="École où l'élève a terminé sa 6ème Année"
    )
    annee_entree_7eme = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Année d'entrée en 7ème",
        help_text="Année scolaire d'entrée en 7ème Année (ex: 2024-2025). "
                  "À renseigner manuellement."
    )
    ecole_an_dernier = models.CharField(
        max_length=150, blank=True, null=True,
        verbose_name="École l'année précédente",
        help_text="École fréquentée l'année précédente (si transfert)"
    )

    class Meta:
        ordering = ['nomEleve', 'prenomEleve']

    def __str__(self):
        return f"{self.matricule} - {self.nomEleve} {self.prenomEleve}"

    def get_age(self):
        from datetime import date
        today = date.today()
        return today.year - self.dateNaiss.year - (
            (today.month, today.day) < (self.dateNaiss.month, self.dateNaiss.day)
        )

    @staticmethod
    def _prefixe_matricule(texte, longueur=2):
        """
        Retourne `longueur` lettres A-Z du texte : accents retirés, espaces,
        tirets et apostrophes ignorés, complété par « X » si trop court.
        Ex. « Éa » → « EA », « De Souza » → « DE », « N » → « NX ».
        """
        sans_accent = unicodedata.normalize('NFKD', texte or '')
        lettres = ''.join(
            c for c in sans_accent.upper()
            if 'A' <= c <= 'Z'
        )
        return (lettres + 'X' * longueur)[:longueur]

    def generer_matricule(self):
        """
        Calcule un matricule libre à partir du nom, du prénom et de la date
        de naissance. Toujours 8 caractères de base (AAAA + MM + AA), puis un
        numéro (2, 3, ...) en cas d'homonymes nés le même mois de la même année.
        """
        if not self.nomEleve or not self.prenomEleve or not self.dateNaiss:
            return None
        nom_prefix = self._prefixe_matricule(self.nomEleve)
        prenom_prefix = self._prefixe_matricule(self.prenomEleve)
        mois = f"{self.dateNaiss.month:02d}"
        annee = str(self.dateNaiss.year)[-2:]
        matricule_base = f"{nom_prefix}{prenom_prefix}{mois}{annee}"

        autres = Eleve.objects.all()
        if self.pk:
            autres = autres.exclude(pk=self.pk)

        if not autres.filter(matricule=matricule_base).exists():
            return matricule_base

        compteur = 2
        while autres.filter(matricule=f"{matricule_base}{compteur}").exists():
            compteur += 1
        return f"{matricule_base}{compteur}"

    def save(self, *args, **kwargs):
        """
        ✅ Le matricule est généré UNE SEULE FOIS (à la création, ou s'il est
        vide) puis il est FIGÉ : corriger un nom, un prénom ou une date de
        naissance ne le change plus (cartes et documents déjà remis restent
        valides). Pour le changer volontairement : `regenerer_matricule()`.
        """
        auto = not self.matricule
        if auto:
            self.matricule = self.generer_matricule()

        self.scolarite_totale = (self.scolarite_1er_cycle or 0) + (self.scolarite_2e_cycle or 0)

        # Deux enregistrements simultanés peuvent calculer le même matricule :
        # la contrainte unique protège la base ; on recalcule et on réessaie.
        for tentative in range(5):
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                return
            except IntegrityError:
                if not auto or tentative == 4:
                    raise
                self.matricule = self.generer_matricule()

    def regenerer_matricule(self, nouveau=None):
        """
        Change VOLONTAIREMENT le matricule (action réservée au directeur).

        - `nouveau` vide  → recalcul automatique depuis nom/prénom/naissance
        - `nouveau` donné → saisie manuelle (mise en majuscules)

        Garantit l'unicité (ValueError sinon). Retourne (ancien, nouveau).
        """
        ancien = self.matricule
        if nouveau is not None and nouveau.strip():
            candidat = nouveau.strip().upper()
            if len(candidat) > 100:
                raise ValueError("Le matricule ne doit pas dépasser 100 caractères.")
            if Eleve.objects.filter(matricule__iexact=candidat).exclude(pk=self.pk).exists():
                raise ValueError(f"Le matricule « {candidat} » est déjà utilisé par un autre élève.")
        else:
            candidat = self.generer_matricule()
            if not candidat:
                raise ValueError("Nom, prénom et date de naissance sont nécessaires pour générer un matricule.")

        self.matricule = candidat
        try:
            with transaction.atomic():
                super().save(update_fields=['matricule'])
        except IntegrityError:
            self.matricule = ancien
            raise ValueError("Ce matricule vient d'être attribué à un autre élève. Réessayez.")
        return ancien, candidat


# 4. ########## LES MATIERES ##########


class Matiere(models.Model):
    TENDANCE_CHOICES = [
        ('litteraire', 'Littéraire'),
        ('scientifique', 'Scientifique'),
    ]

    idMatiere = models.AutoField(primary_key=True)
    nomMatiere = models.CharField(max_length=100, verbose_name="Nom de la matière")
    nomArabe = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nom en arabe")
    coef = models.DecimalField(
        max_digits=3, decimal_places=1, default=1.0,
        verbose_name="Coefficient",
        help_text="Ignoré pour le 1er cycle (pas de coefficient)"
    )
    cycle = models.CharField(
        max_length=3, choices=Classe.CYCLE_CHOICES, default='2e',
        verbose_name="Cycle"
    )

    tendance = models.CharField(
        max_length=20,
        choices=TENDANCE_CHOICES,
        blank=True,
        null=True,
        verbose_name="Tendance",
        help_text="Littéraire ou scientifique. Concern uniquement le 2e cycle."
    )

    class Meta:
        unique_together = ('nomMatiere', 'cycle')
        ordering = ['nomMatiere']

    def __str__(self):
        if self.cycle == '2e' and self.tendance:
            return f"{self.nomMatiere} ({self.get_cycle_display()} - {self.get_tendance_display()})"
        return f"{self.nomMatiere} ({self.get_cycle_display()})"

    @property
    def est_1er_cycle(self):
        return self.cycle == '1er'

    @property
    def est_2e_cycle(self):
        return self.cycle == '2e'

    @property
    def a_tendance(self):
        return bool(self.tendance)

    @property
    def tendance_courte(self):
        if self.tendance == 'litteraire':
            return 'L'
        elif self.tendance == 'scientifique':
            return 'S'
        return ''


# 5. ########## RECALCUL PARCOURS (REDOUBLEMENTS UNIQUEMENT) ##########


def recalculer_parcours_eleve(eleve):
    """
    Recalcule UNIQUEMENT les redoublements à partir des inscriptions.
    """
    inscriptions = Inscription.objects.filter(eleve=eleve).select_related(
        'classe', 'anneeScolaire'
    ).order_by('anneeScolaire__anneeScolaire')

    classes_vues = []
    redoublements = []

    for ins in inscriptions:
        nom_classe = ins.classe.nomClasse
        if nom_classe in classes_vues:
            redoublements.append(nom_classe)
        classes_vues.append(nom_classe)

    eleve.redoublement_1 = redoublements[0] if len(redoublements) > 0 else None
    eleve.redoublement_2 = redoublements[1] if len(redoublements) > 1 else None
    eleve.redoublement_3 = redoublements[2] if len(redoublements) > 2 else None


# 6. ########## LES EVALUATIONS ##########


class Evaluation(models.Model):
    TRIMESTRE = [
        ('Premier trimestre', 'Premier trimestre'),
        ('Deuxieme trimestre', 'Deuxieme trimestre'),
        ('Troisieme trimestre', 'Troisieme trimestre'),
    ]
    idEvaluation = models.AutoField(primary_key=True)
    nomEvaluation = models.CharField(
    choices=TRIMESTRE,
    max_length=50,  # ✅ Ajout
    help_text="Trimestre",
    verbose_name="Evaluation ou Trimestre"
    )

    class Meta:
        ordering = ['idEvaluation']

    def __str__(self):
        return self.nomEvaluation



def recalculer_scolarite_eleve(eleve):
    """
    Recalcule scolarite_1er_cycle et scolarite_2e_cycle en comptant 
    les inscriptions réelles de l'élève.
    """
    from django.db.models import Count

    compteurs = (
        Inscription.objects
        .filter(eleve=eleve)
        .values('classe__cycle')
        .annotate(nb=Count('idInscription'))
    )
    par_cycle = {item['classe__cycle']: item['nb'] for item in compteurs}

    eleve.scolarite_1er_cycle = par_cycle.get('1er', 0)
    eleve.scolarite_2e_cycle = par_cycle.get('2e', 0)
    eleve.scolarite_totale = eleve.scolarite_1er_cycle + eleve.scolarite_2e_cycle

# 7. ########## INSCRIPTION ##########


class Inscription(models.Model):
    idInscription = models.AutoField(primary_key=True)
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, verbose_name="Élève")
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, verbose_name="Classe")
    anneeScolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE,
        verbose_name="Année scolaire"
    )

    # =================================================================
    # ✅ NOUVEAU : frais d'inscription payés AVANT l'utilisation de l'app
    # =================================================================
    frais_inscription_historique = models.BooleanField(
        default=False,
        verbose_name="Frais d'inscription déjà payés (avant l'app)",
        help_text="Cocher si l'élève a déjà payé ses frais d'inscription "
                  "AVANT l'utilisation de cette application. "
                  "Utilisé uniquement si l'école est en mode 'Unique'. "
                  "Cela empêche de réclamer à nouveau ces frais."
    )

    class Meta:
        unique_together = ('eleve', 'anneeScolaire')
        ordering = ['-anneeScolaire__anneeScolaire', 'eleve__nomEleve']

    def __str__(self):
        return f"{self.eleve} - {self.classe} ({self.anneeScolaire})"

    def save(self, *args, **kwargs):
        ancien_eleve = None
        if self.pk:
            ancien_eleve = Inscription.objects.filter(pk=self.pk).values_list('eleve_id', flat=True).first()

        super().save(*args, **kwargs)

        # Recalculer pour l'élève actuel
        recalculer_scolarite_eleve(self.eleve)
        recalculer_parcours_eleve(self.eleve) # pour les redoublements
        self.eleve.save(update_fields=['scolarite_1er_cycle', 'scolarite_2e_cycle', 'scolarite_totale', 'redoublement_1', 'redoublement_2', 'redoublement_3'])

        # Si l'élève a changé, recalculer pour l'ancien élève aussi
        if ancien_eleve and ancien_eleve != self.eleve_id:
            ancien = Eleve.objects.filter(pk=ancien_eleve).first()
            if ancien:
                recalculer_scolarite_eleve(ancien)
                recalculer_parcours_eleve(ancien)
                ancien.save(update_fields=['scolarite_1er_cycle', 'scolarite_2e_cycle', 'scolarite_totale', 'redoublement_1', 'redoublement_2', 'redoublement_3'])

    def delete(self, *args, **kwargs):
        eleve = self.eleve
        super().delete(*args, **kwargs)
        
        recalculer_scolarite_eleve(eleve)
        recalculer_parcours_eleve(eleve)
        eleve.save(update_fields=['scolarite_1er_cycle', 'scolarite_2e_cycle', 'scolarite_totale', 'redoublement_1', 'redoublement_2', 'redoublement_3'])

    # =================================================================
    # ✅ CORRIGÉ : frais_unique_deja_paye
    # =================================================================
    @property
    def frais_unique_deja_paye(self):
        """
        Vérifie si l'élève a déjà payé les frais uniques
        (dans une inscription précédente du même cycle).

        ✅ Utilise le MODE DE L'ÉCOLE (EcoleInfo.mode_frais_scolarite)
        au lieu de classe.mode_paiement (champ inexistant).
        """
        # Import tardif pour éviter les imports circulaires
        from ..services.paiements import _scolarite_unique_deja_payee
        from ..models import EcoleInfo

        ecole = EcoleInfo.get_solo()

        # Si l'école n'est PAS en mode 'unique', la propriété ne s'applique pas
        if ecole.mode_frais_scolarite != 'unique':
            return False

        return _scolarite_unique_deja_payee(self)

    # =================================================================
    # ✅ CORRIGÉ : montant_attendu_total
    # =================================================================
    @property
    def frais_inscription_attendu(self):
        """Récupère les frais d'inscription pour cette classe ET cette année."""
        frais = FraisClasseAnnee.objects.filter(
            classe=self.classe, 
            annee_scolaire=self.anneeScolaire
        ).first()
        return frais.frais_inscription if frais else 0

    @property
    def frais_scolarite_attendu(self):
        """Récupère les frais de scolarité pour cette classe ET cette année."""
        frais = FraisClasseAnnee.objects.filter(
            classe=self.classe, 
            annee_scolaire=self.anneeScolaire
        ).first()
        return frais.frais_scolarite if frais else 0

    # =================================================================
    # montant_paye_total (inchangé, juste Decimal par cohérence)
    # =================================================================
    @property
    def montant_paye_total(self):
        """Somme de tous les paiements pour cette inscription."""
        from django.db.models import Sum
        from decimal import Decimal
        result = Paiement.objects.filter(
            inscription=self
        ).aggregate(Sum('montant'))['montant__sum']
        return result if result is not None else Decimal('0')


# 8. ########## PAIEMENT ##########


class Paiement(models.Model):
    MOIS_SCOLAIRES = [
        (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
        (1, 'Janvier'), (2, 'Février'), (3, 'Mars'),
        (4, 'Avril'), (5, 'Mai'), (6, 'Juin'),
    ]
    MOIS_SCOLAIRES_ORDONNES = MOIS_SCOLAIRES

    idPaiement = models.AutoField(primary_key=True)
    inscription = models.ForeignKey(
        'Inscription', on_delete=models.CASCADE,
        verbose_name="Inscription",
    )
    montant = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name="Montant (FCFA)"
    )
    date_paiement = models.DateField(auto_now_add=True, verbose_name="Date de paiement")
    mois = models.IntegerField(
        choices=MOIS_SCOLAIRES, null=True, blank=True,
        verbose_name="Mois"
    )
    annee_paiement = models.IntegerField(
        default=2024, verbose_name="Année"
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
        ordering = ['annee_paiement', 'mois', 'date_paiement']
        permissions = [
            ('view_paiement_global', "Peut voir les paiements globaux de l'établissement"),
        ]

    def __str__(self):
        if self.est_inscription:
            return f"{self.inscription} - Frais d'inscription: {self.montant} FCFA"
        return f"{self.inscription} - {self.montant} FCFA ({self.get_mois_display()} {self.annee_paiement})"

    # =================================================================
    # ✅ CORRIGÉ : montant_attendu
    # =================================================================
    @property
    def montant_attendu(self):
        """
        Montant attendu pour ce paiement.

        - Frais d'inscription  → montant exact (classe.frais_inscription)
        - Scolarité            → montant de l'échéance selon le mode de l'école
                                  (mensuel / trimestriel / tranches / annuel / unique)

        ✅ Utilise le service calculer_echeances.
        """
        from decimal import Decimal
        from ..services.paiements import calculer_echeances
        from ..models import EcoleInfo

        classe = self.inscription.classe
        ecole = EcoleInfo.get_solo()

        # Cas 1 : Frais d'inscription
        # ✅ FIX: Classe n'a plus de champ frais_inscription ; les frais
        # sont dans FraisClasseAnnee (par classe ET par année).
        if self.est_inscription:
            frais = FraisClasseAnnee.objects.filter(
                classe=classe,
                annee_scolaire=self.inscription.anneeScolaire,
            ).first()
            return Decimal(str(frais.frais_inscription)) if frais else Decimal('0')

        # Cas 2 : Scolarité → chercher l'échéance correspondante
        echeances = calculer_echeances(ecole, classe, self.inscription.anneeScolaire)

        # Mode mensuel : chercher par mois + année
        if self.mois:
            for ech in echeances:
                if ech.get('mois') == self.mois:
                    return ech['montant']
            # Fallback : première échéance
            return echeances[0]['montant'] if echeances else Decimal('0')

        # Autres modes : retourner le montant de la 1ère échéance
        # (le calcul exact dépend du numéro d'échéance qui n'est pas stocké)
        return echeances[0]['montant'] if echeances else Decimal('0')

    # =================================================================
    # ✅ CORRIGÉ : total_paye_pour_ce_mois (Decimal au lieu de float)
    # =================================================================
    def total_paye_pour_ce_mois(self):
        """Somme de tous les paiements pour ce mois + cette inscription."""
        from django.db.models import Sum
        from decimal import Decimal

        if self.est_inscription:
            result = Paiement.objects.filter(
                inscription=self.inscription,
                est_inscription=True,
                annee_paiement=self.annee_paiement,
            ).aggregate(Sum('montant'))['montant__sum']
            return result if result is not None else Decimal('0')

        result = Paiement.objects.filter(
            inscription=self.inscription,
            est_inscription=False,
            mois=self.mois,
            annee_paiement=self.annee_paiement,
        ).aggregate(Sum('montant'))['montant__sum']
        return result if result is not None else Decimal('0')


# 9. ########## NOTES DES ELEVES (2e cycle) ##########


class MatiereClasse(models.Model):
    classe = models.ForeignKey(
        Classe, on_delete=models.CASCADE,
        verbose_name="Classe",
        related_name='matieres_classe'
    )
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, 
        on_delete=models.CASCADE,
        verbose_name="Année scolaire",
        related_name='matieres_classe',
    )
    
    matiere = models.ForeignKey(
        Matiere, on_delete=models.CASCADE,
        verbose_name="Matière",
        related_name='classes_concernees'
    )
    ordre_affichage = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage",
        help_text="Plus petit = affiché en premier sur le bulletin"
    )
    obligatoire = models.BooleanField(
        default=True,
        verbose_name="Matière obligatoire",
        help_text="Si coché, le bulletin signale les notes manquantes"
    )
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Matière par classe"
        verbose_name_plural = "Matières par classe"
        unique_together = ('classe', 'matiere', 'annee_scolaire')  # ✅ Modifié
        ordering = ['classe__nomClasse', 'ordre_affichage', 'matiere__nomMatiere']

    def __str__(self):
        return f"{self.classe.nomClasse} - {self.matiere.nomMatiere}"

