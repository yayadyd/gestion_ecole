import unicodedata

from django.db import models, IntegrityError, transaction
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from ..utils.validators import validate_file_extension, validate_file_size

# 1. ########## ANNEE SCOLAIRE ##########

from .base import *
from .scolarite import *


class Note(models.Model):
    idNote = models.AutoField(primary_key=True)
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE)
    anneeScolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    note = models.DecimalField(
        max_digits=4, decimal_places=2,
        verbose_name="Note de composition"
    )
    noteClasse = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        verbose_name="Note de classe",
        help_text="Note de classe (sur 20)"
    )

    class Meta:
        unique_together = ('eleve', 'matiere', 'evaluation', 'anneeScolaire')

    def __str__(self):
        return f"{self.eleve} - {self.matiere} : {self.note}"


# 10. ########## RESULTAT TRIMESTRE (2e cycle) ##########


class ResultatTrimestre(models.Model):
    """Résultats par trimestre pour un élève"""
    idResultat = models.AutoField(primary_key=True)
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE)
    trimestre = models.CharField(max_length=50, choices=Evaluation.TRIMESTRE)
    anneeScolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    moyenne_generale = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    rang = models.IntegerField(null=True, blank=True)
    appreciation = models.TextField(blank=True, null=True)
    date_calcul = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('inscription', 'trimestre', 'anneeScolaire')
        ordering = ['inscription__classe__nomClasse', '-moyenne_generale']

    def __str__(self):
        return f"{self.inscription} - {self.trimestre} : {self.moyenne_generale}"


# 11. ########## DETAIL RESULTAT (2e cycle) ##########


class DetailResultat(models.Model):
    """Détail des notes par matière pour un trimestre"""
    idDetail = models.AutoField(primary_key=True)
    resultat = models.ForeignKey(
        ResultatTrimestre, on_delete=models.CASCADE,
        related_name='details'
    )
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    note_classe = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Note de classe sur 20"
    )
    note_compo = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Note compo sur 40"
    )
    moyenne_generale = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Moyenne Générale = (Note_Classe + Note_Compo) / 3"
    )
    moyenne_coefficientee = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Moyenne Générale × Coeff"
    )
    coef = models.DecimalField(max_digits=3, decimal_places=1)
    appreciation = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        unique_together = ('resultat', 'matiere')

    def __str__(self):
        return f"{self.resultat} - {self.matiere} : {self.moyenne_generale}"


# 12. ########## ECOLE INFO ##########


class CompositionMensuelle(models.Model):
    """Remplace la notion de 'trimestre' pour le 1er cycle : une composition par mois"""
    MOIS_CHOICES = Paiement.MOIS_SCOLAIRES_ORDONNES

    idComposition = models.AutoField(primary_key=True)
    mois = models.IntegerField(choices=MOIS_CHOICES)
    anneeScolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('mois', 'anneeScolaire')
        ordering = ['anneeScolaire__anneeScolaire', 'mois']

    def __str__(self):
        return f"Composition {self.get_mois_display()} {self.anneeScolaire}"


# 14. ########## NOTE MENSUELLE (1er cycle) ##########


class NoteMensuelle(models.Model):
    """Note d'un élève dans une matière pour une composition mensuelle (1er cycle)"""
    idNoteMensuelle = models.AutoField(primary_key=True)
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    composition = models.ForeignKey(CompositionMensuelle, on_delete=models.CASCADE)
    note = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        unique_together = ('eleve', 'matiere', 'composition')

    def __str__(self):
        return f"{self.eleve} - {self.matiere} : {self.note} ({self.composition})"


# 15. ########## RESULTAT MENSUEL (1er cycle) ##########


class ResultatMensuel(models.Model):
    """Résultat global d'un élève pour une composition mensuelle"""
    idResultat = models.AutoField(primary_key=True)
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE)
    composition = models.ForeignKey(CompositionMensuelle, on_delete=models.CASCADE)
    moyenne_generale = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    rang = models.IntegerField(null=True, blank=True)
    appreciation = models.TextField(blank=True, null=True)
    date_calcul = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('inscription', 'composition')
        ordering = ['inscription__classe__nomClasse', '-moyenne_generale']

    def __str__(self):
        return f"{self.inscription} - {self.composition} : {self.moyenne_generale}"


# 16. ########## DETAIL RESULTAT MENSUEL (1er cycle) ##########


class DetailResultatMensuel(models.Model):
    """Détail des notes par matière pour une composition mensuelle (1er cycle)"""
    idDetail = models.AutoField(primary_key=True)
    resultat = models.ForeignKey(
        ResultatMensuel, on_delete=models.CASCADE,
        related_name='details'
    )
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    note = models.DecimalField(max_digits=5, decimal_places=2, help_text="Note sur 20")
    appreciation = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        unique_together = ('resultat', 'matiere')

    def __str__(self):
        return f"{self.resultat} - {self.matiere} : {self.note}"


# 17. ########## CERTIFICAT TRANSFERT ##########


