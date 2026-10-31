import unicodedata

from django.db import models, IntegrityError, transaction
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from ..utils.validators import validate_file_extension, validate_file_size

# 1. ########## ANNEE SCOLAIRE ##########

from .base import *


class Section(models.TextChoices):
    """
    Dimension d'analyse de la comptabilité.

    Un mouvement (dépense ou recette) n'appartient qu'à UNE section.
    « commun » regroupe les charges et produits de l'établissement
    qui ne sont pas imputables à un cycle précis (loyer, direction...).

    Les paiements d'élèves n'utilisent pas ce champ : leur section est
    dérivée de l'inscription (classe.cycle) ou vaut 'lycee'.
    """
    PREMIER = '1er', '1er cycle'
    SECOND = '2e', '2e cycle'
    LYCEE = 'lycee', 'Lycée'
    COMMUN = 'commun', 'Commun / établissement'


class CategorieDepense(models.Model):
    """Catégories de dépenses (salaires, loyer, électricité, fournitures, etc.)"""
    nom = models.CharField(
        max_length=100, unique=True,
        verbose_name="Nom de la catégorie"
    )
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    ordre_affichage = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage",
        help_text="Plus petit = affiché en premier"
    )
    active = models.BooleanField(
        default=True,
        verbose_name="Active",
        help_text="Désactiver pour masquer sans supprimer"
    )
    section_defaut = models.CharField(
        max_length=10, choices=Section.choices, default=Section.COMMUN,
        blank=True,
        verbose_name="Section par défaut",
        help_text="Pré-remplit la section lors de la saisie d'une dépense"
    )

    class Meta:
        verbose_name = "Catégorie de dépense"
        verbose_name_plural = "Catégories de dépenses"
        ordering = ['ordre_affichage', 'nom']

    def __str__(self):
        return self.nom


# 19. ########## DEPENSE ##########


class Depense(models.Model):
    """Dépense de l'établissement"""
    MODE_PAIEMENT = [
        ('especes', 'Espèces'),
        ('cheque', 'Chèque'),
        ('virement', 'Virement'),
        ('mobile', 'Mobile Money'),
    ]

    categorie = models.ForeignKey(
        CategorieDepense, on_delete=models.PROTECT,
        verbose_name="Catégorie",
        related_name='depenses'
    )
    libelle = models.CharField(
        max_length=200,
        verbose_name="Libellé",
        help_text="Description courte de la dépense"
    )
    montant = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name="Montant (FCFA)"
    )
    date_depense = models.DateField(verbose_name="Date de la dépense")
    beneficiaire = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name="Bénéficiaire",
        help_text="Personne ou organisme payé"
    )
    mode_paiement = models.CharField(
        max_length=20, choices=MODE_PAIEMENT, default='especes',
        verbose_name="Mode de paiement"
    )
    numero_piece = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name="N° de pièce justificative",
        help_text="Numéro de reçu ou facture"
    )
    justificatif = models.FileField(
    upload_to='depenses/justificatifs/',
    blank=True, null=True,
    verbose_name="Justificatif scanné",
    help_text="Photo ou PDF du reçu/facture",
    validators=[validate_file_extension, validate_file_size]  # ✅ Ajout
    )
    anneeScolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.PROTECT,
        verbose_name="Année scolaire",
        related_name='depenses'
    )
    section = models.CharField(
        max_length=10, choices=Section.choices, default=Section.COMMUN,
        db_index=True,
        verbose_name="Section",
        help_text="Cycle concerné, ou « Commun » si la charge est partagée"
    )
    observation = models.TextField(blank=True, null=True, verbose_name="Observation")
    date_saisie = models.DateTimeField(auto_now_add=True, verbose_name="Date de saisie")
    saisi_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Saisi par",
        related_name='depenses_saisies'
    )

    class Meta:
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"
        ordering = ['-date_depense', '-id']
        permissions = [
            ('voir_comptabilite', "Peut voir la comptabilité"),
            ('gerer_depenses', "Peut gérer les dépenses"),
        ]

    def __str__(self):
        return f"{self.date_depense} - {self.libelle} : {self.montant} FCFA"


# 20. ########## CATEGORIE RECETTE ##########


class CategorieRecette(models.Model):
    """Catégories de recettes hors paiements d'élèves (subventions, dons, etc.)"""
    nom = models.CharField(
        max_length=100, unique=True,
        verbose_name="Nom de la catégorie"
    )
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    ordre_affichage = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage"
    )
    active = models.BooleanField(default=True, verbose_name="Active")
    section_defaut = models.CharField(
        max_length=10, choices=Section.choices, default=Section.COMMUN,
        blank=True,
        verbose_name="Section par défaut",
        help_text="Pré-remplit la section lors de la saisie d'une recette"
    )

    class Meta:
        verbose_name = "Catégorie de recette"
        verbose_name_plural = "Catégories de recettes"
        ordering = ['ordre_affichage', 'nom']

    def __str__(self):
        return self.nom


# 21. ########## RECETTE ##########


class Recette(models.Model):
    """Recette hors paiements d'élèves (subvention, don, location, etc.)"""
    MODE_PAIEMENT = [
        ('especes', 'Espèces'),
        ('cheque', 'Chèque'),
        ('virement', 'Virement'),
        ('mobile', 'Mobile Money'),
    ]

    categorie = models.ForeignKey(
        CategorieRecette, on_delete=models.PROTECT,
        verbose_name="Catégorie",
        related_name='recettes'
    )
    libelle = models.CharField(
        max_length=200,
        verbose_name="Libellé",
        help_text="Description courte de la recette"
    )
    montant = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name="Montant (FCFA)"
    )
    date_recette = models.DateField(verbose_name="Date de la recette")
    source = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name="Source",
        help_text="Personne ou organisme émetteur"
    )
    mode_paiement = models.CharField(
        max_length=20, choices=MODE_PAIEMENT, default='especes',
        verbose_name="Mode de réception"
    )
    numero_piece = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name="N° de pièce justificative",
        help_text="Numéro de reçu ou référence"
    )
    justificatif = models.FileField(
    upload_to='recettes/justificatifs/',
    blank=True, null=True,
    verbose_name="Justificatif scanné",
    validators=[validate_file_extension, validate_file_size]  # ✅ Ajout
    )
    anneeScolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.PROTECT,
        verbose_name="Année scolaire",
        related_name='recettes'
    )
    section = models.CharField(
        max_length=10, choices=Section.choices, default=Section.COMMUN,
        db_index=True,
        verbose_name="Section",
        help_text="Cycle concerné, ou « Commun » si la recette est partagée"
    )
    observation = models.TextField(blank=True, null=True, verbose_name="Observation")
    date_saisie = models.DateTimeField(auto_now_add=True, verbose_name="Date de saisie")
    saisi_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Saisi par",
        related_name='recettes_saisies'
    )

    class Meta:
        verbose_name = "Recette (hors paiements)"
        verbose_name_plural = "Recettes (hors paiements)"
        ordering = ['-date_recette', '-id']
        permissions = [
            ('gerer_recettes', "Peut gérer les recettes"),
        ]

    def __str__(self):
        return f"{self.date_recette} - {self.libelle} : {self.montant} FCFA"


# 22. ########## PLAGE HORAIRE ##########


