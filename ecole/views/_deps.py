"""Imports et constantes partagés par les modules de vues."""
# ecole/views.py
import io
import os
import json
import csv
import logging
from urllib.parse import urlencode
from datetime import date
from django.forms import modelformset_factory

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Sum, Avg, Count, Q
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.contrib.auth.models import User, Permission

from ..models import (
    AnneeScolaire, Classe, Eleve, Matiere,
    Inscription, Paiement, Evaluation, Note,
    ResultatTrimestre, DetailResultat, EcoleInfo,
    CompositionMensuelle, NoteMensuelle, ResultatMensuel,
    DetailResultatMensuel, CertificatTransfert,
    CategorieDepense, Depense, CategorieRecette, Recette,
    PlageHoraire, EmploiTemps, CreneauEmploiTemps, MatiereClasse,FraisClasseAnnee
)
from ..forms import (
    AnneeScolaireForm, ClasseForm, EleveForm,
    MatiereForm, InscriptionForm, PaiementForm,
    EvaluationForm, NoteForm, EcoleInfoForm, PlageHoraireForm,
    CertificatTransfertForm, DepenseForm, RecetteForm,
    MatiereClasseForm, FraisClasseAnneeForm
)
from ..cycles import (
    Cycle, matieres_du_cycle, classes_du_cycle, arrondir_moyenne,
    STRUCTURE_TENTATIVES_2E_CYCLE,
    MOIS_SCOLAIRES,
    MOIS_CALENDAIRES,
)
from ..services.moyennes import calculer_moyennes_classe_bulk, classer_inscriptions, LIBELLE_NON_SAISIE
from ..services.paiements import (
    calculer_montants_inscription,
    calculer_echeances,
)
from ..utils.pdf_generator import (
    generer_bulletin_pdf_eleve,
    generer_certificat_frequentation_pdf,
    generer_proposition_passage_pdf,
    generer_bulletin_mensuel_pdf_eleve,
    generer_certificat_transfert_pdf,
    generer_fiche_suivi_second_cycle_pdf,
    generer_liste_eleves_pdf,
    generer_emploi_temps_pdf,
    generer_carte_scolaire_pdf,          
    generer_planche_cartes_classe_pdf,
)
from ..mixins import RetourAvecCycleMixin
import subprocess
import sys
from ..utils.setup import verifier_cle_setup, get_cle_setup
from django.http import FileResponse, Http404
import mimetypes
from django.conf import settings
from ..utils.qr_code import generer_qr_code_base64
from ..utils.cartes import couleur_valide, fond_valide

# Dossiers MEDIA lisibles SANS connexion (nécessaires à la page de login).
_MEDIA_PUBLICS = ('ecole/logo/',)
logger = logging.getLogger(__name__)
MOIS_ABREGES = {
    10: 'Oct', 11: 'Nov', 12: 'Dec',
    1: 'Jan', 2: 'Fev', 3: 'Mar',
    4: 'Avr', 5: 'Mai', 6: 'Juin',
}
from django.contrib.auth.views import LoginView
PREFIXES_NIVEAU_FICHE = {'7ème A': '7ème', '8ème A': '8ème', '9ème A': '9ème'}
from ..utils.qr_code import generer_qr_code_base64
from ..utils.pdf_generator import generer_carte_scolaire_pdf
