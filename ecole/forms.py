from django import forms
from .models import (
    AnneeScolaire, Classe, Eleve, Matiere,
    Inscription, Paiement, Evaluation, Note,
    ResultatTrimestre, DetailResultat, EcoleInfo,
    CertificatTransfert, CategorieDepense, Depense,
    CategorieRecette, Recette, PlageHoraire,
    EmploiTemps, CreneauEmploiTemps, MatiereClasse,
    FraisClasseAnnee
)
from django.db.models import Q
from .cycles import matieres_du_cycle
from datetime import date
from django.core.exceptions import ValidationError


# ==================== ANNEE SCOLAIRE ====================
class AnneeScolaireForm(forms.ModelForm):
    class Meta:
        model = AnneeScolaire
        fields = ['anneeScolaire', 'date_debut', 'date_fin']
        widgets = {
            'anneeScolaire': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 2025-2026'}),
            'date_debut': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
        }

    def clean_anneeScolaire(self):
        annee = self.cleaned_data.get('anneeScolaire')
        if not annee or len(annee) != 9 or annee[4] != '-':
            raise ValidationError("Le format doit être 'AAAA-AAAA' (ex: 2025-2026)")
        try:
            int(annee[:4])
            int(annee[5:9])
        except ValueError:
            raise ValidationError("Les années doivent être des nombres")
        return annee

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('date_debut')
        fin = cleaned.get('date_fin')
        if debut and fin and fin <= debut:
            raise ValidationError("La date de fin doit être postérieure à la date de début.")
        return cleaned


# ==================== CLASSE ====================
class ClasseForm(forms.ModelForm):
    """Formulaire de création/modification d'une classe."""

    class Meta:
        model = Classe
        fields = [
            'nomClasse',
            'cycle',
            # ❌ 'frais_inscription' et 'frais_scolarite' sont retirés
        ]
        widgets = {
            'nomClasse': forms.Select(attrs={'class': 'form-control'}),
            'cycle': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        cycle = kwargs.pop('cycle', None)
        super().__init__(*args, **kwargs)

        if cycle == '1er':
            self.fields['nomClasse'].choices = Classe.CLASSES_1ER_CYCLE
            self.fields['cycle'].initial = '1er'
            self.fields['cycle'].widget = forms.HiddenInput()
        elif cycle == '2e':
            self.fields['nomClasse'].choices = Classe.CLASSES_2E_CYCLE
            self.fields['cycle'].initial = '2e'
            self.fields['cycle'].widget = forms.HiddenInput()
        elif self.instance and self.instance.pk:
            cycle_instance = self.instance.cycle
            if cycle_instance == '1er':
                self.fields['nomClasse'].choices = Classe.CLASSES_1ER_CYCLE
            elif cycle_instance == '2e':
                self.fields['nomClasse'].choices = Classe.CLASSES_2E_CYCLE
        else:
            self.fields['nomClasse'].choices = Classe.CLASSE

    # ✅ Suppression de la méthode clean() qui vérifiait les frais




# ==================== ELEVE ====================
class EleveForm(forms.ModelForm):
    class Meta:
        model = Eleve
        fields = [
            # Identité
            'prenomEleve', 'nomEleve', 'sexe', 'dateNaiss', 'lieuNaiss',
            # Filiation / Tuteur
            'pere', 'mere', 'contactTuteur', 'adresseTuteur', 'photo',
            # Acte de naissance
            'numero_acte_naissance', 'date_delivrance_acte',
            # Scolarité
            'scolarite_1er_cycle', 'scolarite_2e_cycle',
            # ✅ NOUVEAUX : Parcours scolaire (saisie manuelle)
            'annee_recrutement', 'ecole_recrutement', 'ecole_fin_1er_cycle',
            'annee_entree_7eme', 'ecole_an_dernier',
        ]
        widgets = {
            'prenomEleve': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Prénom de l'élève"
            }),
            'nomEleve': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Nom de l'élève"
            }),
            'sexe': forms.Select(attrs={'class': 'form-control'}),
            'dateNaiss': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'lieuNaiss': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Lieu de naissance'
            }),
            'pere': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du père'
            }),
            'mere': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la mère'
            }),
            'contactTuteur': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 77 13 45 67 / 64 21 45 87'
            }),
            'adresseTuteur': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Adresse complète'
            }),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'numero_acte_naissance': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Numéro de l'acte"
            }),
            'date_delivrance_acte': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'scolarite_1er_cycle': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0'
            }),
            'scolarite_2e_cycle': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0'
            }),

            # ✅ NOUVEAUX WIDGETS pour les champs manuels
            'annee_recrutement': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 2020-2021',
                'pattern': r'\d{4}-\d{4}',
                'title': "Format : AAAA-AAAA (ex: 2020-2021)",
            }),
            'ecole_recrutement': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "École où l'élève a fait sa 1ère Année"
            }),
            'ecole_fin_1er_cycle': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "École où l'élève a terminé sa 6ème Année"
            }),
            'annee_entree_7eme': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 2024-2025',
                'pattern': r'\d{4}-\d{4}',
                'title': "Format : AAAA-AAAA (ex: 2024-2025)",
            }),
            'ecole_an_dernier': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "École fréquentée l'année précédente"
            }),
        }

    # ---------------------------------------------------------------
    # VALIDATION : DATE DE NAISSANCE
    # ---------------------------------------------------------------
    def clean_dateNaiss(self):
        d = self.cleaned_data.get('dateNaiss')
        if d and d > date.today():
            raise ValidationError("La date de naissance ne peut pas être dans le futur.")
        # Optionnel : âge minimum raisonnable (ex: pas né après 2010)
        # if d and d.year > 2015:
        #     raise ValidationError("Âge incohérent pour une inscription scolaire.")
        return d

    # ---------------------------------------------------------------
    # VALIDATION : FORMAT AAAA-AAAA (helper interne)
    # ---------------------------------------------------------------
    def _clean_annee_scolaire_format(self, value, champ_nom):
        """Valide qu'une année scolaire respecte le format AAAA-AAAA."""
        if not value:
            return value
        value = value.strip()

        if len(value) != 9 or value[4] != '-':
            raise ValidationError(
                f"{champ_nom} : le format doit être 'AAAA-AAAA' (ex: 2025-2026)."
            )
        try:
            debut = int(value[:4])
            fin = int(value[5:9])
        except ValueError:
            raise ValidationError(
                f"{champ_nom} : les années doivent être des nombres."
            )

        if fin != debut + 1:
            raise ValidationError(
                f"{champ_nom} : les deux années doivent se suivre "
                f"(ex: 2025-2026, pas 2025-2028)."
            )
        return value

    def clean_annee_recrutement(self):
        return self._clean_annee_scolaire_format(
            self.cleaned_data.get('annee_recrutement'),
            "Année de recrutement"
        )

    def clean_annee_entree_7eme(self):
        return self._clean_annee_scolaire_format(
            self.cleaned_data.get('annee_entree_7eme'),
            "Année d'entrée en 7ème"
        )

    # ---------------------------------------------------------------
    # VALIDATION CROISÉE : cohérence des années
    # ---------------------------------------------------------------
    def clean(self):
        cleaned = super().clean()

        annee_reclut = cleaned.get('annee_recrutement')
        annee_7eme = cleaned.get('annee_entree_7eme')
        date_naiss = cleaned.get('dateNaiss')

        # 1. annee_entree_7eme >= annee_recrutement
        if annee_reclut and annee_7eme:
            try:
                debut_reclut = int(annee_reclut[:4])
                debut_7eme = int(annee_7eme[:4])

                if debut_7eme < debut_reclut:
                    raise ValidationError(
                        "L'année d'entrée en 7ème ne peut pas être "
                        "antérieure à l'année de recrutement."
                    )

                # Optionnel : écart raisonnable (au moins 6 ans entre 1ère A et 7ème A)
                if debut_7eme - debut_reclut < 6:
                    self.add_error(
                        'annee_entree_7eme',
                        "L'écart entre l'année de recrutement et l'entrée en 7ème "
                        "doit être d'au moins 6 ans (6 années de 1er cycle)."
                    )
            except (ValueError, IndexError):
                pass

        # 2. annee_recrutement doit être cohérente avec la date de naissance
        if annee_reclut and date_naiss:
            try:
                debut_reclut = int(annee_reclut[:4])
                age_a_la_1ere_annee = debut_reclut - date_naiss.year

                # Un élève entre généralement en 1ère Année entre 5 et 9 ans
                if age_a_la_1ere_annee < 4:
                    self.add_error(
                        'annee_recrutement',
                        f"Âge incohérent : l'élève aurait eu "
                        f"{age_a_la_1ere_annee} ans en 1ère Année."
                    )
                elif age_a_la_1ere_annee > 12:
                    self.add_error(
                        'annee_recrutement',
                        f"Âge inhabituel : l'élève aurait eu "
                        f"{age_a_la_1ere_annee} ans en 1ère Année. "
                        f"Vérifiez les données."
                    )
            except (ValueError, IndexError):
                pass

        # 3. annee_entree_7eme doit être cohérente avec la date de naissance
        if annee_7eme and date_naiss:
            try:
                debut_7eme = int(annee_7eme[:4])
                age_en_7eme = debut_7eme - date_naiss.year

                # Un élève entre en 7ème Année entre 11 et 16 ans
                if age_en_7eme < 10:
                    self.add_error(
                        'annee_entree_7eme',
                        f"Âge incohérent : l'élève aurait eu "
                        f"{age_en_7eme} ans en 7ème Année."
                    )
                elif age_en_7eme > 18:
                    self.add_error(
                        'annee_entree_7eme',
                        f"Âge inhabituel : l'élève aurait eu "
                        f"{age_en_7eme} ans en 7ème Année. "
                        f"Vérifiez les données."
                    )
            except (ValueError, IndexError):
                pass

        # 4. Cohérence : si scolarite_2e_cycle > 0, annee_entree_7eme devrait exister
        scolarite_2e = cleaned.get('scolarite_2e_cycle')
        if scolarite_2e and scolarite_2e > 0 and not annee_7eme:
            self.add_error(
                'annee_entree_7eme',
                "L'élève a une scolarité au 2e cycle : "
                "l'année d'entrée en 7ème doit être renseignée."
            )

        return cleaned


# ==================== MATIERE ====================
class MatiereForm(forms.ModelForm):
    """Formulaire de création/modification d'une matière."""

    COEF_CHOICES = [
        ('0.5', '0,5'),
        ('1', '1'),
        ('1.5', '1,5'),
        ('2', '2'),
        ('2.5', '2,5'),
        ('3', '3'),
        ('4', '4'),
    ]

    coef = forms.ChoiceField(
        choices=COEF_CHOICES,
        initial='1',
        label="Coefficient",
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Matiere
        fields = ['nomMatiere', 'nomArabe', 'coef', 'cycle', 'tendance']
        widgets = {
            'nomMatiere': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Nom de la matière",
            }),
            'nomArabe': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Nom en arabe (optionnel)",
            }),
            'cycle': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_cycle',
            }),
            'tendance': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_tendance',
            }),
        }

    def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            # ✅ FIX: logique robuste, sans print de debug
            import logging
            logger = logging.getLogger(__name__)

            is_classique = False
            try:
                from .models import EcoleInfo
                ecole = EcoleInfo.get_solo()
                if ecole and ecole.type_ecole == 'classique':
                    is_classique = True
            except Exception as e:
                logger.error(f"[MatiereForm] Erreur récupération école : {e}")

            # ✅ Masquer nomArabe uniquement si explicitement classique
            if is_classique:
                self.fields['nomArabe'].widget = forms.HiddenInput()
                self.fields['nomArabe'].required = False
                self.fields['nomArabe'].label = ''

            # Tendance optionnelle
            self.fields['tendance'].required = False
            self.fields['tendance'].choices = [
                ('', '— Non spécifiée —'),
                ('litteraire', 'Littéraire'),
                ('scientifique', 'Scientifique'),
            ]

    def clean_coef(self):
        """Convertir la valeur du ChoiceField en Decimal."""
        from decimal import Decimal
        coef = self.cleaned_data.get('coef')
        if coef is not None:
            try:
                return Decimal(str(coef))
            except (ValueError, TypeError):
                raise ValidationError("Coefficient invalide.")
        return Decimal('1.0')

    def clean(self):
        """
        Validation croisée :
        - Si cycle = 1er → tendance forcée à None
        - Si cycle = 2e → tendance optionnelle
        """
        cleaned = super().clean()
        cycle = cleaned.get('cycle')
        tendance = cleaned.get('tendance')

        if cycle == '1er':
            cleaned['tendance'] = None

        return cleaned


# ==================== INSCRIPTION ====================
class InscriptionForm(forms.ModelForm):
    recherche_eleve = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom, prénom ou matricule...',
            'id': 'rechercheEleve',
            'autocomplete': 'off',
        })
    )

    eleve_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'eleveId'})
    )

    class Meta:
        model = Inscription
        fields = ['eleve', 'classe', 'anneeScolaire', 'frais_inscription_historique']
        widgets = {
            'eleve': forms.HiddenInput(),
            'classe': forms.Select(attrs={
                'class': 'form-control',
                'id': 'classeSelect',
            }),
            'anneeScolaire': forms.Select(attrs={'class': 'form-control'}),
            'frais_inscription_historique': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_frais_historique',
            }),
        }

    def __init__(self, *args, **kwargs):
        cycle = kwargs.pop('cycle', None)
        super().__init__(*args, **kwargs)

        self.fields['eleve'].queryset = Eleve.objects.all().order_by('nomEleve', 'prenomEleve')
        self.fields['eleve'].label_from_instance = (
            lambda e: f"{e.matricule} — {e.nomEleve} {e.prenomEleve}"
        )

        if cycle:
            self.fields['classe'].queryset = Classe.objects.filter(cycle=cycle).order_by('nomClasse')
        else:
            self.fields['classe'].queryset = Classe.objects.all().order_by('nomClasse')

        if self.instance and self.instance.pk and self.instance.classe:
            cycle_instance = self.instance.classe.cycle
            self.fields['classe'].queryset = Classe.objects.filter(cycle=cycle_instance).order_by('nomClasse')

        if self.instance and self.instance.pk and self.instance.eleve:
            eleve = self.instance.eleve
            self.fields['recherche_eleve'].initial = (
                f"{eleve.matricule} — {eleve.nomEleve} {eleve.prenomEleve}"
            )
            self.fields['eleve_id'].initial = eleve.pk


    def clean(self):
        cleaned = super().clean()
        eleve = cleaned.get('eleve')
        annee = cleaned.get('anneeScolaire')

        if eleve and annee:
            existing = Inscription.objects.filter(eleve=eleve, anneeScolaire=annee)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(
                    f"L'élève {eleve.nomEleve} {eleve.prenomEleve} est déjà inscrit "
                    f"pour l'année {annee.anneeScolaire}."
                )
        return cleaned


# ==================== PAIEMENT ====================
class PaiementForm(forms.ModelForm):
    """
    Formulaire de paiement.
    S'adapte au mode de scolarité de l'école :
    - mensuel    : mois obligatoire
    - trimestriel/tranches/annuel/unique : mois masqué
    """

    # Champ de filtrage par année scolaire
    annee_scolaire_filter = forms.ModelChoiceField(
        queryset=AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        required=False,
        label="Année scolaire",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'anneeFilter',
        })
    )

    # Champ de recherche d'élève
    recherche_inscription = forms.CharField(
        required=False,
        label="Rechercher un élève inscrit",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tapez un nom, prénom ou matricule...',
            'id': 'rechercheInscription',
            'autocomplete': 'off',
        })
    )

    class Meta:
        model = Paiement
        fields = [
            'inscription',
            'montant',
            'mois',
            'annee_paiement',
            'est_inscription',
            'observation',
        ]
        widgets = {
            'inscription': forms.HiddenInput(attrs={'id': 'id_inscription'}),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '100',
                'min': '0',
                'placeholder': 'Ex : 5000',
            }),
            'mois': forms.Select(attrs={'class': 'form-control', 'id': 'id_mois'}),
            'annee_paiement': forms.HiddenInput(),
            'est_inscription': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'estInscription',
            }),
            'observation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex : Reste 4500 à payer, Versement du père...",
            }),
        }

    def __init__(self, *args, **kwargs):
        cycle = kwargs.pop('cycle', None)
        super().__init__(*args, **kwargs)

        self.fields['mois'].choices = Paiement.MOIS_SCOLAIRES_ORDONNES
        self.fields['mois'].required = False
        self.fields['annee_paiement'].required = False

        # Filtrer les inscriptions selon le cycle
        queryset = Inscription.objects.select_related(
            'eleve', 'classe', 'anneeScolaire'
        )
        if cycle:
            queryset = queryset.filter(classe__cycle=cycle)
        self.fields['inscription'].queryset = queryset.order_by('eleve__nomEleve')

        # En modification : pré-remplir
        if self.instance and self.instance.pk and self.instance.inscription_id:
            ins = self.instance.inscription
            self.fields['recherche_inscription'].initial = (
                f"{ins.eleve.matricule} - "
                f"{ins.eleve.nomEleve} {ins.eleve.prenomEleve} "
                f"({ins.classe.nomClasse})"
            )
            self.fields['annee_scolaire_filter'].initial = ins.anneeScolaire_id

    def clean(self):
        """
        Validation adaptée au mode de scolarité de l'école.
        """
        cleaned = super().clean()
        inscription = cleaned.get('inscription')
        mois = cleaned.get('mois')
        est_inscription = cleaned.get('est_inscription')
        montant = cleaned.get('montant')

        if not inscription:
            raise ValidationError("Veuillez sélectionner un élève via la recherche.")

        # Récupérer les modes de l'école
        ecole = EcoleInfo.get_solo()
        annee_scolaire_obj = inscription.anneeScolaire

        # ============================================================
        # CAS 1 : PAIEMENT DES FRAIS D'INSCRIPTION
        # ============================================================
        if est_inscription:
            if not montant or montant <= 0:
                raise ValidationError(
                    "Veuillez renseigner le montant des frais d'inscription."
                )
            cleaned['mois'] = None
            cleaned['annee_paiement'] = annee_scolaire_obj.get_annee_debut()
            return cleaned

        # ============================================================
        # CAS 2 : PAIEMENT DE LA SCOLARITÉ
        # ============================================================

        # Mode mensuel : mois obligatoire
        if ecole.mode_frais_scolarite == 'mensuel':
            if not mois:
                self.add_error('mois', "Le mois est obligatoire pour une mensualité.")
                return cleaned

            # Calcul de l'année du paiement
            if mois in (10, 11, 12):
                annee_paiement = annee_scolaire_obj.get_annee_debut()
            else:
                annee_paiement = annee_scolaire_obj.get_annee_fin()
            cleaned['annee_paiement'] = annee_paiement

            # Vérifier qu'il n'y a pas déjà un paiement pour ce mois
            existing = Paiement.objects.filter(
                inscription=inscription,
                mois=mois,
                annee_paiement=annee_paiement,
                est_inscription=False,
            )
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                nom_mois = dict(Paiement.MOIS_SCOLAIRES).get(mois)
                raise ValidationError(
                    f"Un paiement existe déjà pour {nom_mois} {annee_paiement}."
                )

        # Autres modes : pas de mois
        else:
            cleaned['mois'] = None
            cleaned['annee_paiement'] = annee_scolaire_obj.get_annee_debut()

        # Vérification du montant
        if not montant or montant <= 0:
            raise ValidationError("Veuillez renseigner le montant du paiement.")

        return cleaned

# ==================== EVALUATION ====================
class EvaluationForm(forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = ['nomEvaluation']
        widgets = {
            'nomEvaluation': forms.Select(attrs={'class': 'form-control'}),
        }


# ==================== NOTE ====================
class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['eleve', 'matiere', 'evaluation', 'anneeScolaire', 'note', 'noteClasse']
        widgets = {
            'eleve': forms.Select(attrs={'class': 'form-control'}),
            'matiere': forms.Select(attrs={'class': 'form-control'}),
            'evaluation': forms.Select(attrs={'class': 'form-control'}),
            'anneeScolaire': forms.Select(attrs={'class': 'form-control'}),
            'note': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.25', 'min': '0', 'max': '20'
            }),
            'noteClasse': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.25', 'min': '0', 'max': '20'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['matiere'].queryset = matieres_du_cycle('2e')

    def clean_note(self):
        note = self.cleaned_data.get('note')
        if note is not None and (note < 0 or note > 20):
            raise ValidationError("La note doit être comprise entre 0 et 20.")
        return note

    def clean_noteClasse(self):
        noteClasse = self.cleaned_data.get('noteClasse')
        if noteClasse is not None and (noteClasse < 0 or noteClasse > 20):
            raise ValidationError("La note de classe doit être comprise entre 0 et 20.")
        return noteClasse


# ==================== ECOLE INFO ====================
class EcoleInfoForm(forms.ModelForm):
    """Formulaire de configuration de l'école (informations + modes de paiement)."""

    class Meta:
        model = EcoleInfo
        fields = [
            # --- Identité ---
            'nom', 'sigle',
            'ministere', 'circonscription', 'academie',
            'republique', 'devise',
            'adresse', 'ville', 'pays', 'boite_postale',
            'telephone', 'email', 'site_web',
            'logo', 'signature_directeur', 
            'cachet_ecole',         
            'nom_directeur', 'numero_autorisation',
            'type_ecole',
            'mode_frais_inscription',
            'mode_frais_scolarite',
            'nombre_tranches',
        ]
        widgets = {
            # --- Identité ---
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'sigle': forms.TextInput(attrs={'class': 'form-control'}),
            'ministere': forms.TextInput(attrs={'class': 'form-control'}),
            'circonscription': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex : CAP DE KALABAN COURA"
            }),
            'academie': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex : Académie d'Enseignement de Bamako Rive Gauche"
            }),
            'republique': forms.TextInput(attrs={'class': 'form-control'}),
            'devise': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.TextInput(attrs={'class': 'form-control'}),
            'ville': forms.TextInput(attrs={'class': 'form-control'}),
            'pays': forms.TextInput(attrs={'class': 'form-control'}),
            'boite_postale': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'site_web': forms.URLInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'signature_directeur': forms.FileInput(attrs={'class': 'form-control'}),
            'cachet_ecole': forms.FileInput(attrs={'class': 'form-control'}),
            'nom_directeur': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_autorisation': forms.TextInput(attrs={'class': 'form-control'}),
            'type_ecole': forms.Select(attrs={'class': 'form-control', 'id': 'id_type_ecole',}),
            # --- Modes de paiement ---
            'mode_frais_inscription': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_mode_frais_inscription',
            }),
            'mode_frais_scolarite': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_mode_frais_scolarite',
            }),
            'nombre_tranches': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2',
                'max': '12',
                'id': 'id_nombre_tranches',
            }),
        }

    def clean(self):
        """Validation : nombre_tranches obligatoire si mode = 'tranches'."""
        cleaned = super().clean()
        mode_scolarite = cleaned.get('mode_frais_scolarite')
        nb_tranches = cleaned.get('nombre_tranches')

        if mode_scolarite == 'tranches':
            if not nb_tranches or nb_tranches < 2:
                self.add_error(
                    'nombre_tranches',
                    "Renseignez un nombre de tranches (minimum 2)."
                )
            elif nb_tranches > 12:
                self.add_error(
                    'nombre_tranches',
                    "Le nombre de tranches ne peut pas dépasser 12."
                )

        return cleaned


# ==================== CERTIFICAT TRANSFERT ====================
class CertificatTransfertForm(forms.ModelForm):
    class Meta:
        model = CertificatTransfert
        fields = ['conduite', 'decision_conseil_maitres', 'motif_transfert', 'ecole_destination']
        widgets = {
            'conduite': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ex: Bien'
            }),
            'decision_conseil_maitres': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ex: Favorable'
            }),
            'motif_transfert': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: À la demande des parents'
            }),
            'ecole_destination': forms.TextInput(attrs={'class': 'form-control'}),
        }


# ==================== COMPTABILITÉ : DÉPENSE ====================
class DepenseForm(forms.ModelForm):
    class Meta:
        model = Depense
        fields = [
            'categorie', 'libelle', 'montant', 'date_depense',
            'beneficiaire', 'mode_paiement', 'numero_piece',
            'justificatif', 'anneeScolaire', 'section', 'observation',
        ]
        widgets = {
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'libelle': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex: Salaire Octobre 2025, Facture électricité..."
            }),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '100', 'min': '0',
                'placeholder': 'Ex: 250000'
            }),
            'date_depense': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'beneficiaire': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex: M. Diallo, SOMAGEP, etc."
            }),
            'mode_paiement': forms.Select(attrs={'class': 'form-control'}),
            'numero_piece': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex: REC-2025-001"
            }),
            'justificatif': forms.FileInput(attrs={'class': 'form-control'}),
            'anneeScolaire': forms.Select(attrs={'class': 'form-control'}),
            'section': forms.Select(attrs={'class': 'form-control'}),
            'observation': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': "Notes complémentaires (facultatif)"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categorie'].queryset = CategorieDepense.objects.filter(
            active=True
        ).order_by('ordre_affichage', 'nom')
        self.fields['anneeScolaire'].queryset = AnneeScolaire.objects.all().order_by('-anneeScolaire')

    def clean_montant(self):
        montant = self.cleaned_data.get('montant')
        if montant is not None and montant <= 0:
            raise ValidationError("Le montant doit être supérieur à 0.")
        return montant

    def clean_date_depense(self):
        d = self.cleaned_data.get('date_depense')
        if d and d > date.today():
            raise ValidationError("La date de dépense ne peut pas être dans le futur.")
        return d


# ==================== COMPTABILITÉ : RECETTE ====================
class RecetteForm(forms.ModelForm):
    class Meta:
        model = Recette
        fields = [
            'categorie', 'libelle', 'montant', 'date_recette',
            'source', 'mode_paiement', 'numero_piece',
            'justificatif', 'anneeScolaire', 'section', 'observation',
        ]
        widgets = {
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'libelle': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex: Subvention État, Don association..."
            }),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '100', 'min': '0'
            }),
            'date_recette': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex: Ministère, Association..."
            }),
            'mode_paiement': forms.Select(attrs={'class': 'form-control'}),
            'numero_piece': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex: SUBV-2025-001"
            }),
            'justificatif': forms.FileInput(attrs={'class': 'form-control'}),
            'anneeScolaire': forms.Select(attrs={'class': 'form-control'}),
            'section': forms.Select(attrs={'class': 'form-control'}),
            'observation': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categorie'].queryset = CategorieRecette.objects.filter(
            active=True
        ).order_by('ordre_affichage', 'nom')
        self.fields['anneeScolaire'].queryset = AnneeScolaire.objects.all().order_by('-anneeScolaire')

    def clean_montant(self):
        montant = self.cleaned_data.get('montant')
        if montant is not None and montant <= 0:
            raise ValidationError("Le montant doit être supérieur à 0.")
        return montant

    def clean_date_recette(self):
        d = self.cleaned_data.get('date_recette')
        if d and d > date.today():
            raise ValidationError("La date de recette ne peut pas être dans le futur.")
        return d


# ==================== EMPLOI DU TEMPS : PLAGE HORAIRE ====================
class PlageHoraireForm(forms.ModelForm):
    class Meta:
        model = PlageHoraire
        fields = ['cycle', 'ordre', 'heure_debut', 'heure_fin', 'libelle', 'est_pause']
        widgets = {
            'cycle': forms.Select(attrs={'class': 'form-control'}),
            'ordre': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0',
                'placeholder': "Ex: 1, 2, 3..."
            }),
            'heure_debut': forms.TimeInput(
                format='%H:%M',
                attrs={'class': 'form-control', 'type': 'time'}
            ),
            'heure_fin': forms.TimeInput(
                format='%H:%M',
                attrs={'class': 'form-control', 'type': 'time'}
            ),
            'libelle': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex: Récréation (optionnel)"
            }),
            'est_pause': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        cycle = cleaned_data.get('cycle')
        debut = cleaned_data.get('heure_debut')
        fin = cleaned_data.get('heure_fin')

        if not (debut and fin and cycle):
            return cleaned_data

        # 1. Fin > début
        if fin <= debut:
            raise ValidationError(
                "L'heure de fin doit être postérieure à l'heure de début."
            )

        # 2. Vérifier les chevauchements dans le MÊME cycle
        plages_qs = PlageHoraire.objects.filter(cycle=cycle)

        # ✅ Exclure l'instance en cours de modification
        if self.instance and self.instance.pk:
            plages_qs = plages_qs.exclude(pk=self.instance.pk)

        # ✅ Ne comparer qu'aux plages de cours (pas les pauses)
        # pour éviter les faux positifs si la plage en cours est une pause
        for p in plages_qs:
            # Chevauchement : debut < fin_autre ET fin > debut_autre
            if debut < p.heure_fin and fin > p.heure_debut:
                raise ValidationError(
                    f"Cette plage chevauche la plage existante du "
                    f"{p.get_cycle_display()} : "
                    f"{p.heure_debut.strftime('%H:%M')} - "
                    f"{p.heure_fin.strftime('%H:%M')}"
                    + (f" ({p.libelle})" if p.libelle else "")
                )

        return cleaned_data

# ==================== MATIÈRE PAR CLASSE ====================
class MatiereClasseForm(forms.ModelForm):
    class Meta:
        model = MatiereClasse
        fields = ['classe', 'annee_scolaire', 'matiere', 'ordre_affichage', 'obligatoire'] # ✅ Ajout de annee_scolaire
        widgets = {
            'classe': forms.Select(attrs={'class': 'form-control'}),
            'annee_scolaire': forms.Select(attrs={'class': 'form-control'}), # ✅ Nouveau widget
            'matiere': forms.Select(attrs={'class': 'form-control'}),
            'ordre_affichage': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0',
                'placeholder': 'Ex: 1, 2, 3...'
            }),
            'obligatoire': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        cycle = kwargs.pop('cycle', None)
        super().__init__(*args, **kwargs)

        # Filtrer les classes et matières
        if cycle:
            self.fields['classe'].queryset = Classe.objects.filter(cycle=cycle).order_by('nomClasse')
            self.fields['matiere'].queryset = Matiere.objects.filter(cycle=cycle).order_by('nomMatiere')
        else:
            self.fields['classe'].queryset = Classe.objects.all().order_by('nomClasse')
            self.fields['matiere'].queryset = Matiere.objects.all().order_by('nomMatiere')

        # Filtrer les années
        self.fields['annee_scolaire'].queryset = AnneeScolaire.objects.all().order_by('-anneeScolaire')

        # En modification : filtrer les matières selon le cycle de la classe
        if self.instance and self.instance.pk:
            cycle_instance = self.instance.classe.cycle
            self.fields['matiere'].queryset = Matiere.objects.filter(
                cycle=cycle_instance
            ).order_by('nomMatiere')

class FraisClasseAnneeForm(forms.ModelForm):
    """Formulaire pour modifier les frais d'une classe (utilisé dans un formset)."""
    class Meta:
        model = FraisClasseAnnee
        fields = ['frais_inscription', 'frais_scolarite']
        widgets = {
            'frais_inscription': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0', 'step': '100'}),
            'frais_scolarite': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0', 'step': '100'}),
        }