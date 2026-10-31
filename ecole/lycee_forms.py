# ecole/lycee_forms.py
"""
Formulaires du Lycée - INDÉPENDANTS des cycles 1er et 2e.

Contient :
- MatiereLyceeForm
- CoefficientLyceeForm
- ClasseLyceeForm
- EleveLyceeForm (avec matricule SAISI MANUELLEMENT)
- InscriptionLyceeForm
- NoteLyceeForm
- SaisieNotesLyceeFilterForm
- PaiementLyceeForm
- PlageHoraireLyceeForm
- MatiereClasseLyceeForm
"""
from django import forms
from django.core.exceptions import ValidationError
from datetime import date
from decimal import Decimal

from .lycee_models import (
    MatiereLycee, CoefficientLycee, ClasseLycee,
    EleveLycee, InscriptionLycee, NoteLycee, PaiementLycee,
    PlageHoraireLycee, MatiereClasseLycee,
)
from .models import AnneeScolaire, EcoleInfo


# =====================================================================
# 1. FORMULAIRE MATIÈRE
# =====================================================================
class MatiereLyceeForm(forms.ModelForm):
    """Formulaire de création/modification d'une matière du lycée."""

    class Meta:
        model = MatiereLycee
        fields = ['nom', 'nom_arabe', 'domaine', 'obligatoire', 'ordre_affichage', 'active']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex : Mathématiques",
            }),
            'nom_arabe': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Nom en arabe (optionnel)",
            }),
            'domaine': forms.Select(attrs={'class': 'form-control'}),
            'obligatoire': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordre_affichage': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0',
                'placeholder': "Ex : 1, 2, 3...",
            }),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ Masquer nom_arabe si école classique
        import logging
        logger = logging.getLogger(__name__)

        is_classique = False
        try:
            ecole = EcoleInfo.get_solo()
            if ecole and ecole.est_classique:
                is_classique = True
        except Exception as e:
            logger.error(f"[MatiereLyceeForm] Erreur récupération école : {e}")

        if is_classique:
            self.fields['nom_arabe'].widget = forms.HiddenInput()
            self.fields['nom_arabe'].required = False
            self.fields['nom_arabe'].label = ''


# =====================================================================
# 2. FORMULAIRE COEFFICIENT
# =====================================================================
class CoefficientLyceeForm(forms.ModelForm):
    """
    Formulaire de coefficients.
    Le coefficient peut être modifié par (matière, niveau, série).
    """

    class Meta:
        model = CoefficientLycee
        fields = ['matiere', 'niveau', 'serie', 'coefficient']
        widgets = {
            'matiere': forms.Select(attrs={'class': 'form-control'}),
            'niveau': forms.Select(attrs={'class': 'form-control', 'id': 'id_niveau'}),
            'serie': forms.Select(attrs={'class': 'form-control', 'id': 'id_serie'}),
            'coefficient': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.5', 'min': '0.5', 'max': '10',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['matiere'].queryset = MatiereLycee.objects.filter(
            active=True
        ).order_by('ordre_affichage', 'nom')

    def clean(self):
        cleaned = super().clean()
        niveau = cleaned.get('niveau')
        serie = cleaned.get('serie')

        # ✅ En 10ème : pas de série
        if niveau == '10' and serie:
            raise ValidationError("La 10ème Année n'a pas de série (Commune Générale).")

        # ✅ En 11ème et Terminale : série obligatoire
        if niveau in ('11', '12') and not serie:
            raise ValidationError("La série est obligatoire pour la 11ème Année et la Terminale.")

        # ✅ Vérifier que la série correspond au niveau
        series_11 = ['L', 'SES', 'S']
        series_12 = ['TLL', 'TAL', 'TSS', 'TSEco', 'TSExp', 'TSE']

        if niveau == '11' and serie not in series_11:
            raise ValidationError(
                f"Les séries valides pour la 11ème Année sont : {', '.join(series_11)}."
            )

        if niveau == '12' and serie not in series_12:
            raise ValidationError(
                f"Les séries valides pour la Terminale sont : {', '.join(series_12)}."
            )

        return cleaned


# =====================================================================
# 3. FORMULAIRE CLASSE
# =====================================================================
class ClasseLyceeForm(forms.ModelForm):
    """
    Formulaire de création/modification d'une classe du lycée.
    Ex : 10ème CG1, 11ème L2, TLL1, TSS2, etc.
    """

    class Meta:
        model = ClasseLycee
        fields = ['nom', 'niveau', 'serie', 'annee_scolaire', 'frais_inscription', 'frais_scolarite']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex : 10ème CG1, 11ème L2, TLL1...",
            }),
            'niveau': forms.Select(attrs={'class': 'form-control', 'id': 'id_niveau'}),
            'serie': forms.Select(attrs={'class': 'form-control', 'id': 'id_serie'}),
            'annee_scolaire': forms.Select(attrs={'class': 'form-control'}),
            'frais_inscription': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '100', 'min': '0',
                'placeholder': "Ex : 10000",
            }),
            'frais_scolarite': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '100', 'min': '0',
                'placeholder': "Montant annuel (ex : 90000)",
            }),
        }

    def clean(self):
        cleaned = super().clean()
        niveau = cleaned.get('niveau')
        serie = cleaned.get('serie')

        # ✅ En 10ème : pas de série
        if niveau == '10':
            cleaned['serie'] = ''

        # ✅ En 11ème et Terminale : série obligatoire
        elif niveau in ('11', '12') and not serie:
            self.add_error('serie', "La série est obligatoire pour ce niveau.")

        return cleaned


# =====================================================================
# 4. FORMULAIRE ÉLÈVE (MATRICULE SAISI MANUELLEMENT)
# =====================================================================
class EleveLyceeForm(forms.ModelForm):
    """
    Formulaire de création/modification d'un élève du lycée.
    ⚠️ Le matricule est SAISI MANUELLEMENT (pas de génération automatique).
    ⚠️ Une fois créé, le matricule ne peut plus être modifié.
    """

    class Meta:
        model = EleveLycee
        fields = [
            'matricule',
            'prenom', 'nom', 'sexe', 'date_naissance', 'lieu_naissance',
            'pere', 'mere', 'contact_tuteur', 'adresse', 'photo',
            'numero_acte_naissance', 'date_delivrance_acte',
            'ecole_provenance', 'annee_def', 'statut'
        ]
        widgets = {
            'matricule': forms.TextInput(attrs={
                'class': 'form-control font-monospace',
                'placeholder': "Ex : RC16CG18Q14Q14907M",
            }),
            'prenom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Prénom de l'élève"}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Nom de l'élève"}),
            'sexe': forms.Select(attrs={'class': 'form-control'}),
            'date_naissance': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'pere': forms.TextInput(attrs={'class': 'form-control'}),
            'mere': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_tuteur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Ex : 76 12 34 56"}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'numero_acte_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'date_delivrance_acte': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'ecole_provenance': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "École où l'élève a obtenu son DEF",
            }),
            'annee_def': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ex : 2024-2025",
                'pattern': r'\d{4}-\d{4}',
            }),
            'statut': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ Le matricule est en lecture seule UNIQUEMENT en modification
        is_edition = (
            self.instance is not None
            and self.instance.pk is not None
        )

        if is_edition:
            self.fields['matricule'].widget.attrs['readonly'] = True
            self.fields['matricule'].widget.attrs['class'] = 'form-control font-monospace bg-light'
            self.fields['matricule'].help_text = "Le matricule ne peut pas être modifié."
        else:
            self.fields['matricule'].widget.attrs.pop('readonly', None)
            self.fields['matricule'].widget.attrs['class'] = 'form-control font-monospace'
            self.fields['matricule'].required = True

    def clean_matricule(self):
        """Vérifier que le matricule est unique et non vide."""
        matricule = self.cleaned_data.get('matricule', '').strip()

        if not matricule:
            raise ValidationError("Le matricule est obligatoire.")

        qs = EleveLycee.objects.filter(matricule=matricule)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError(f"Le matricule '{matricule}' existe déjà. Il doit être unique.")

        return matricule

    def clean_date_naissance(self):
        """Vérifier que la date de naissance est cohérente."""
        d = self.cleaned_data.get('date_naissance')
        if d and d > date.today():
            raise ValidationError("La date de naissance ne peut pas être dans le futur.")
        return d


# =====================================================================
# 5. FORMULAIRE INSCRIPTION
# =====================================================================
class InscriptionLyceeForm(forms.ModelForm):
    """
    Formulaire d'inscription d'un élève du lycée.
    ✅ Avec recherche AJAX pour sélectionner l'élève.
    """

    recherche_eleve = forms.CharField(
        required=False,
        label="Rechercher un élève",
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
        model = InscriptionLycee
        fields = ['eleve', 'classe', 'annee_scolaire', 'frais_inscription_historique']
        widgets = {
            'eleve': forms.Select(attrs={
                'class': 'form-control',
                'id': 'eleveSelect',
            }),
            'classe': forms.Select(attrs={
                'class': 'form-control',
                'id': 'classeSelect',
            }),
            'annee_scolaire': forms.Select(attrs={
                'class': 'form-control',
                'id': 'anneeSelect',
            }),
            'frais_inscription_historique': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_frais_historique',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['eleve'].queryset = EleveLycee.objects.all().order_by('nom', 'prenom')
        self.fields['classe'].queryset = ClasseLycee.objects.all().order_by('niveau', 'serie', 'nom')
        self.fields['annee_scolaire'].queryset = AnneeScolaire.objects.all().order_by('-anneeScolaire')

        # ✅ En modification : pré-remplir le champ de recherche
        if self.instance and self.instance.pk and self.instance.eleve:
            eleve = self.instance.eleve
            self.fields['recherche_eleve'].initial = (
                f"{eleve.matricule} — {eleve.nom} {eleve.prenom}"
            )
            self.fields['eleve_id'].initial = eleve.id_eleve

    def clean(self):
        cleaned = super().clean()
        eleve = cleaned.get('eleve')
        annee = cleaned.get('annee_scolaire')

        # ✅ Vérifier que l'élève n'est pas déjà inscrit cette année
        if eleve and annee:
            qs = InscriptionLycee.objects.filter(eleve=eleve, annee_scolaire=annee)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError(
                    f"L'élève {eleve.nom} {eleve.prenom} est déjà inscrit "
                    f"pour l'année {annee.anneeScolaire}."
                )

        return cleaned


# =====================================================================
# 6. FORMULAIRE NOTES
# =====================================================================
class NoteLyceeForm(forms.ModelForm):
    """Formulaire de saisie d'une note du lycée."""

    class Meta:
        model = NoteLycee
        fields = ['inscription', 'matiere', 'trimestre', 'note_classe', 'note_composition']
        widgets = {
            'inscription': forms.Select(attrs={'class': 'form-control'}),
            'matiere': forms.Select(attrs={'class': 'form-control'}),
            'trimestre': forms.Select(attrs={'class': 'form-control'}),
            'note_classe': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.25', 'min': '0', 'max': '20',
            }),
            'note_composition': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.25', 'min': '0', 'max': '20',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inscription'].queryset = InscriptionLycee.objects.select_related(
            'eleve', 'classe'
        ).order_by('eleve__nom')
        self.fields['matiere'].queryset = MatiereLycee.objects.filter(
            active=True
        ).order_by('ordre_affichage', 'nom')

    def clean(self):
        cleaned = super().clean()
        note_classe = cleaned.get('note_classe')
        note_compo = cleaned.get('note_composition')

        if note_classe is not None and (note_classe < 0 or note_classe > 20):
            self.add_error('note_classe', "La note doit être comprise entre 0 et 20.")

        if note_compo is not None and (note_compo < 0 or note_compo > 20):
            self.add_error('note_composition', "La note doit être comprise entre 0 et 20.")

        return cleaned


# =====================================================================
# 7. FORMULAIRE DE FILTRAGE POUR LA SAISIE PAR CLASSE
# =====================================================================
class SaisieNotesLyceeFilterForm(forms.Form):
    """
    Formulaire de filtrage pour la saisie des notes par classe.
    Permet de sélectionner : Classe + Matière + Trimestre + Année.

    ✅ FIX: les matières sont filtrées selon la classe sélectionnée.
    ✅ FIX: les classes sont filtrées selon l'année scolaire sélectionnée.
    """

    classe = forms.ModelChoiceField(
        queryset=ClasseLycee.objects.none(),
        label="Classe",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_classe',
        })
    )
    matiere = forms.ModelChoiceField(
        queryset=MatiereLycee.objects.none(),
        label="Matière",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_matiere',
        })
    )
    trimestre = forms.ChoiceField(
        choices=[('', '--- Choisir un trimestre ---')] + NoteLycee.TRIMESTRE_CHOICES,
        label="Trimestre",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_trimestre',
        })
    )
    annee_scolaire = forms.ModelChoiceField(
        queryset=AnneeScolaire.objects.none(),
        label="Année scolaire",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_annee_scolaire',
            'onchange': 'this.form.submit()',
        })
    )

    def __init__(self, *args, **kwargs):
        niveau = kwargs.pop('niveau', None)
        serie = kwargs.pop('serie', None)
        super().__init__(*args, **kwargs)

        # Récupérer l'année scolaire sélectionnée
        annee_selectionnee = self._get_annee_selectionnee()

        # ============================================================
        # 1. CLASSES : filtrées par année scolaire si sélectionnée
        # ============================================================
        classes = ClasseLycee.objects.all().order_by('niveau', 'serie', 'nom')
        if annee_selectionnee:
            classes = classes.filter(annee_scolaire=annee_selectionnee)
        if niveau:
            classes = classes.filter(niveau=niveau)
        if serie:
            classes = classes.filter(serie=serie)
        self.fields['classe'].queryset = classes

        # Si la classe sélectionnée n'appartient pas à l'année choisie, la réinitialiser
        classe_selectionnee = self._get_classe_selectionnee()
        if classe_selectionnee and annee_selectionnee and classe_selectionnee.annee_scolaire_id != annee_selectionnee.idAnneeScolaire:
            if self.data:
                # Créer une copie mutable des données
                data = self.data.copy()
                data.pop('classe', None)
                self.data = data
            if self.initial and self.initial.get('classe') == classe_selectionnee.pk:
                self.initial.pop('classe', None)


        # ============================================================
        # 2. MATIÈRES : filtrées selon la classe sélectionnée
        # ============================================================
        # ✅ FIX: récupérer la classe depuis les données du formulaire
        # (initial ou data selon GET/POST)
        classe_selectionnee = self._get_classe_selectionnee()

        if classe_selectionnee:
            # Récupérer les matières associées à cette classe
            matieres_classe = MatiereClasseLycee.objects.filter(
                classe=classe_selectionnee
            ).select_related('matiere').order_by(
                'ordre_affichage', 'matiere__nom'
            )
            matieres_ids = [mc.matiere_id for mc in matieres_classe]

            if matieres_ids:
                # Filtrer uniquement les matières de la classe
                self.fields['matiere'].queryset = MatiereLycee.objects.filter(
                    id_matiere__in=matieres_ids,
                    active=True,
                ).order_by('ordre_affichage', 'nom')
            else:
                # La classe n'a aucune matière associée → queryset vide
                self.fields['matiere'].queryset = MatiereLycee.objects.none()
                self.fields['matiere'].help_text = (
                    "⚠️ Aucune matière n'est associée à cette classe. "
                    "Configurez-les dans « Matières par classe »."
                )
        else:
            # Aucune classe sélectionnée → aucune matière affichée
            self.fields['matiere'].queryset = MatiereLycee.objects.none()

        # ============================================================
        # 3. ANNÉES SCOLAIRES
        # ============================================================
        self.fields['annee_scolaire'].queryset = AnneeScolaire.objects.all().order_by(
            '-anneeScolaire'
        )

    def _get_classe_selectionnee(self):
        """
        Récupère la classe sélectionnée depuis :
        1. self.data (POST/GET) si le formulaire est lié
        2. self.initial (pré-remplissage)
        3. self.fields['classe'].initial
        """
        classe_id = None

        # Cas 1 : formulaire lié (données soumises)
        if self.data and self.data.get('classe'):
            classe_id = self.data.get('classe')

        # Cas 2 : pré-remplissage via initial
        elif self.initial and self.initial.get('classe'):
            classe_val = self.initial.get('classe')
            # Peut être un objet ClasseLycee ou un ID
            if hasattr(classe_val, 'pk'):
                return classe_val
            classe_id = classe_val

        # Cas 3 : initial du champ
        elif self.fields.get('classe') and self.fields['classe'].initial:
            classe_val = self.fields['classe'].initial
            if hasattr(classe_val, 'pk'):
                return classe_val
            classe_id = classe_val

        if not classe_id:
            return None

        try:
            return ClasseLycee.objects.get(id_classe=classe_id)
        except (ClasseLycee.DoesNotExist, ValueError, TypeError):
            return None

    def _get_annee_selectionnee(self):
        """
        Récupère l'année scolaire sélectionnée depuis les données ou initial.
        """
        annee_id = None

        if self.data and self.data.get('annee_scolaire'):
            annee_id = self.data.get('annee_scolaire')
        elif self.initial and self.initial.get('annee_scolaire'):
            annee_val = self.initial.get('annee_scolaire')
            if hasattr(annee_val, 'pk'):
                return annee_val
            annee_id = annee_val
        elif self.fields.get('annee_scolaire') and self.fields['annee_scolaire'].initial:
            annee_val = self.fields['annee_scolaire'].initial
            if hasattr(annee_val, 'pk'):
                return annee_val
            annee_id = annee_val

        if not annee_id:
            return None

        try:
            return AnneeScolaire.objects.get(idAnneeScolaire=annee_id)
        except (AnneeScolaire.DoesNotExist, ValueError, TypeError):
            return None


# =====================================================================
# 8. FORMULAIRE DES PAIEMENTS (MIROIR DU FONDAMENTAL)
# =====================================================================
class PaiementLyceeForm(forms.ModelForm):
    """
    Formulaire de paiement pour le lycée.
    ✅ Miroir EXACT de PaiementForm (fondamental).
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

    # ✅ FIX: Champ de recherche (comme dans PaiementForm du fondamental)
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
        model = PaiementLycee
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
        super().__init__(*args, **kwargs)

        self.fields['mois'].choices = PaiementLycee.MOIS_SCOLAIRES_ORDONNES
        self.fields['mois'].required = False
        self.fields['annee_paiement'].required = False

        # Filtrer les inscriptions
        self.fields['inscription'].queryset = InscriptionLycee.objects.select_related(
            'eleve', 'classe', 'annee_scolaire'
        ).order_by('eleve__nom')

        # ✅ En modification : pré-remplir les champs de recherche
        if self.instance and self.instance.pk and self.instance.inscription_id:
            ins = self.instance.inscription
            self.fields['recherche_inscription'].initial = (
                f"{ins.eleve.matricule} - "
                f"{ins.eleve.nom} {ins.eleve.prenom} "
                f"({ins.classe.nom})"
            )
            self.fields['annee_scolaire_filter'].initial = ins.annee_scolaire_id

    def clean(self):
            """
            Validation adaptée au mode de scolarité de l'école.

            ✅ FIX: Vérification intelligente des doublons (miroir du fondamental).
            - Autorise les paiements partiels (versements multiples pour la même échéance)
            - Refuse si le total des paiements dépasse le montant attendu
            """
            from .lycee_services import calculer_montants_inscription_lycee

            cleaned = super().clean()
            inscription = cleaned.get('inscription')
            mois = cleaned.get('mois')
            est_inscription = cleaned.get('est_inscription')
            montant = cleaned.get('montant')

            if not inscription:
                raise ValidationError("Veuillez sélectionner un élève.")

            # ✅ Vérifier si l'élève est orienté
            if inscription.eleve.statut == 'oriente':
                raise ValidationError(
                    "Cet élève est orienté par l'État. "
                    "Aucun paiement ne peut être enregistré."
                )

            ecole = EcoleInfo.get_solo()
            annee_scolaire_obj = inscription.annee_scolaire

            # ============================================================
            # CAS 1 : PAIEMENT DES FRAIS D'INSCRIPTION
            # ============================================================
            if est_inscription:
                if not montant or montant <= 0:
                    raise ValidationError(
                        "Veuillez renseigner le montant des frais d'inscription."
                    )

                # ✅ FIX: Vérifier que le total ne dépasse pas l'attendu
                montants = calculer_montants_inscription_lycee(inscription)

                total_apres = montants['frais_inscription_paye'] + Decimal(str(montant))
                if self.instance and self.instance.pk and self.instance.est_inscription:
                    total_apres -= Decimal(str(self.instance.montant))

                if total_apres > montants['frais_inscription_attendu']:
                    reste = max(
                        Decimal('0'),
                        montants['frais_inscription_attendu'] - montants['frais_inscription_paye']
                    )
                    if self.instance and self.instance.pk and self.instance.est_inscription:
                        reste += Decimal(str(self.instance.montant))

                    raise ValidationError(
                        f"Le montant total dépasserait les frais d'inscription attendus "
                        f"({montants['frais_inscription_attendu']:,.0f} FCFA). "
                        f"Reste à payer : {reste:,.0f} FCFA."
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

                if mois in (10, 11, 12):
                    annee_paiement = annee_scolaire_obj.get_annee_debut()
                else:
                    annee_paiement = annee_scolaire_obj.get_annee_fin()
                cleaned['annee_paiement'] = annee_paiement

                # ✅ FIX: Vérification intelligente des doublons
                montants = calculer_montants_inscription_lycee(inscription)

                echeance_concernee = None
                for ech in montants['detail_echeances']:
                    if ech.get('mois') == mois:
                        echeance_concernee = ech
                        break

                if echeance_concernee:
                    total_apres = echeance_concernee['paye'] + Decimal(str(montant))
                    if (self.instance and self.instance.pk
                            and not self.instance.est_inscription
                            and self.instance.mois == mois
                            and self.instance.annee_paiement == annee_paiement):
                        total_apres -= Decimal(str(self.instance.montant))

                    if total_apres > echeance_concernee['attendu']:
                        reste = max(
                            Decimal('0'),
                            echeance_concernee['attendu'] - echeance_concernee['paye']
                        )
                        if (self.instance and self.instance.pk
                                and not self.instance.est_inscription
                                and self.instance.mois == mois
                                and self.instance.annee_paiement == annee_paiement):
                            reste += Decimal(str(self.instance.montant))

                        nom_mois = dict(PaiementLycee.MOIS_SCOLAIRES).get(mois)
                        raise ValidationError(
                            f"Le montant total pour {nom_mois} {annee_paiement} "
                            f"dépasserait le montant attendu "
                            f"({echeance_concernee['attendu']:,.0f} FCFA). "
                            f"Reste à payer : {reste:,.0f} FCFA."
                        )

            # Autres modes : pas de mois
            else:
                cleaned['mois'] = None
                cleaned['annee_paiement'] = annee_scolaire_obj.get_annee_debut()

                # ✅ FIX: Vérification intelligente pour les modes non mensuels
                montants = calculer_montants_inscription_lycee(inscription)

                echeance_cible = None
                for ech in montants['detail_echeances']:
                    if ech['reste'] > 0:
                        echeance_cible = ech
                        break

                if echeance_cible:
                    total_apres = echeance_cible['paye'] + Decimal(str(montant))
                    if (self.instance and self.instance.pk
                            and not self.instance.est_inscription):
                        total_apres -= Decimal(str(self.instance.montant))

                    if total_apres > echeance_cible['attendu']:
                        reste = max(
                            Decimal('0'),
                            echeance_cible['attendu'] - echeance_cible['paye']
                        )
                        if (self.instance and self.instance.pk
                                and not self.instance.est_inscription):
                            reste += Decimal(str(self.instance.montant))

                        raise ValidationError(
                            f"Le montant total dépasserait l'échéance "
                            f"« {echeance_cible['libelle']} » "
                            f"({echeance_cible['attendu']:,.0f} FCFA). "
                            f"Reste à payer : {reste:,.0f} FCFA."
                        )

            # Vérification du montant
            if not montant or montant <= 0:
                raise ValidationError("Veuillez renseigner le montant du paiement.")

            return cleaned


# =====================================================================
# 9. FORMULAIRE PLAGE HORAIRE LYCÉE
# =====================================================================
class PlageHoraireLyceeForm(forms.ModelForm):
    """Formulaire de création/modification d'une plage horaire du lycée."""

    class Meta:
        model = PlageHoraireLycee
        fields = ['ordre', 'heure_debut', 'heure_fin', 'libelle', 'est_pause']
        widgets = {
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
        debut = cleaned_data.get('heure_debut')
        fin = cleaned_data.get('heure_fin')

        if not (debut and fin):
            return cleaned_data

        # 1. Fin > début
        if fin <= debut:
            raise ValidationError(
                "L'heure de fin doit être postérieure à l'heure de début."
            )

        # 2. Vérifier les chevauchements (avec toutes les plages, y compris les pauses)
        plages_qs = PlageHoraireLycee.objects.all()

        # Exclure l'instance en cours de modification
        if self.instance and self.instance.pk:
            plages_qs = plages_qs.exclude(pk=self.instance.pk)

        for p in plages_qs:
            # Chevauchement : debut < fin_autre ET fin > debut_autre
            if debut < p.heure_fin and fin > p.heure_debut:
                raise ValidationError(
                    f"Cette plage chevauche la plage existante : "
                    f"{p.heure_debut.strftime('%H:%M')} - "
                    f"{p.heure_fin.strftime('%H:%M')}"
                    + (f" ({p.libelle})" if p.libelle else "")
                )

        return cleaned_data


# =====================================================================
# 10. FORMULAIRE MATIÈRE PAR CLASSE LYCÉE
# =====================================================================
class MatiereClasseLyceeForm(forms.ModelForm):
    """Formulaire d'association d'une matière à une classe du lycée."""

    class Meta:
        model = MatiereClasseLycee
        fields = ['classe', 'matiere', 'ordre_affichage', 'obligatoire']
        widgets = {
            'classe': forms.Select(attrs={'class': 'form-control'}),
            'matiere': forms.Select(attrs={'class': 'form-control'}),
            'ordre_affichage': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0',
                'placeholder': 'Ex: 1, 2, 3...'
            }),
            'obligatoire': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrer les classes et matières
        self.fields['classe'].queryset = ClasseLycee.objects.all().order_by('niveau', 'serie', 'nom')
        self.fields['matiere'].queryset = MatiereLycee.objects.filter(
            active=True
        ).order_by('ordre_affichage', 'nom')

        if self.instance and self.instance.pk:
            if self.instance.classe:
                self.fields['matiere'].queryset = MatiereLycee.objects.filter(
                    active=True
                ).order_by('ordre_affichage', 'nom')