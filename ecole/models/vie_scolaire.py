import unicodedata

from django.db import models, IntegrityError, transaction
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from ..utils.validators import validate_file_extension, validate_file_size

# 1. ########## ANNEE SCOLAIRE ##########

from .base import *
from .scolarite import *


class CertificatTransfert(models.Model):
    """Certificat de transfert"""
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE)
    travail = models.CharField(max_length=20, blank=True, null=True, help_text="Ex: 14,26")
    conduite = models.CharField(max_length=50, blank=True, null=True, help_text="Ex: Bien")
    decision_conseil_maitres = models.CharField(
        max_length=100, blank=True, null=True, help_text="Ex: Favorable"
    )
    motif_transfert = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Ex: À la demande des parents"
    )
    ecole_destination = models.CharField(max_length=150, blank=True, null=True)
    date_delivrance = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-date_delivrance']

    def __str__(self):
        return f"Certificat de transfert - {self.inscription.eleve} ({self.date_delivrance})"


# 18. ########## CATEGORIE DEPENSE ##########


class PlageHoraire(models.Model):
    """
    Plage horaire standard de l'école.
    Différenciée par cycle (1er / 2e).
    """
    CYCLE_CHOICES = [
        ('1er', '1er Cycle'),
        ('2e', '2e Cycle'),
    ]

    idPlage = models.AutoField(primary_key=True)

    cycle = models.CharField(
        max_length=3,
        choices=CYCLE_CHOICES,
        default='1er',
        verbose_name="Cycle",
        help_text="À quel cycle s'applique cette plage horaire"
    )

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
        verbose_name = "Plage horaire"
        verbose_name_plural = "Plages horaires"
        ordering = ['cycle', 'ordre', 'heure_debut']
        unique_together = ('cycle', 'heure_debut', 'heure_fin')

    def __str__(self):
        base = (
            f"[{self.get_cycle_display()}] "
            f"{self.heure_debut.strftime('%H:%M')} - "
            f"{self.heure_fin.strftime('%H:%M')}"
        )
        return f"{base} ({self.libelle})" if self.libelle else base


# 23. ########## EMPLOI DU TEMPS ##########


class EmploiTemps(models.Model):
    """Emploi du temps d'une classe pour une année scolaire donnée."""
    classe = models.ForeignKey(
        Classe, on_delete=models.CASCADE,
        verbose_name="Classe",
        related_name='emplois_temps'
    )
    anneeScolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE,
        verbose_name="Année scolaire",
        related_name='emplois_temps'
    )
    reconduit_depuis = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Reconduit depuis",
        help_text="Emploi du temps de l'année précédente dont celui-ci a été copié"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Emploi du temps"
        verbose_name_plural = "Emplois du temps"
        unique_together = ('classe', 'anneeScolaire')
        ordering = ['-anneeScolaire__anneeScolaire', 'classe__nomClasse']

    def __str__(self):
        return f"Emploi du temps {self.classe.nomClasse} - {self.anneeScolaire.anneeScolaire}"

    @property
    def nb_creneaux_remplis(self):
        return self.creneaux.exclude(matiere__isnull=True).count()


# 24. ########## CRENEAU EMPLOI DU TEMPS ##########


class CreneauEmploiTemps(models.Model):
    """Un créneau dans un emploi du temps."""
    JOURS = [
        (1, 'Lundi'), (2, 'Mardi'), (3, 'Mercredi'),
        (4, 'Jeudi'), (5, 'Vendredi'), (6, 'Samedi'),
    ]

    emploi_temps = models.ForeignKey(
        EmploiTemps, on_delete=models.CASCADE,
        verbose_name="Emploi du temps",
        related_name='creneaux'
    )
    jour = models.IntegerField(choices=JOURS, verbose_name="Jour de la semaine")
    plage = models.ForeignKey(
        PlageHoraire, on_delete=models.CASCADE,
        verbose_name="Plage horaire",
        related_name='creneaux'
    )
    matiere = models.ForeignKey(
        Matiere, on_delete=models.SET_NULL, null=True, blank=True,
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
        verbose_name = "Créneau d'emploi du temps"
        verbose_name_plural = "Créneaux d'emploi du temps"
        ordering = ['jour', 'plage__ordre', 'plage__heure_debut']
        unique_together = ('emploi_temps', 'jour', 'plage')

    def __str__(self):
        matiere_str = self.matiere.nomMatiere if self.matiere else "(vide)"
        return f"{self.get_jour_display()} {self.plage} : {matiere_str}"


# 25. ########## LICENCE ##########


