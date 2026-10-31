import unicodedata

from django.db import models, IntegrityError, transaction
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from ..utils.validators import validate_file_extension, validate_file_size

# 1. ########## ANNEE SCOLAIRE ##########


class AnneeScolaire(models.Model):
    idAnneeScolaire = models.AutoField(primary_key=True)
    anneeScolaire = models.CharField(
        max_length=9, unique=True,
        verbose_name="Année scolaire",
        help_text="Format : AAAA-AAAA (ex: 2025-2026)"
    )
    date_debut = models.DateField(null=True, blank=True, verbose_name="Date de début")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date de fin")

    class Meta:
        ordering = ['-anneeScolaire']

    def __str__(self):
        return self.anneeScolaire

    def get_annee_debut(self):
        return int(self.anneeScolaire[:4])

    def get_annee_fin(self):
        return int(self.anneeScolaire[5:9])

    def get_mois_scolaires(self):
        annee_debut = self.get_annee_debut()
        annee_fin = self.get_annee_fin()
        mois_debut = [
            (10, 'Octobre', annee_debut),
            (11, 'Novembre', annee_debut),
            (12, 'Décembre', annee_debut),
        ]
        mois_fin = [
            (1, 'Janvier', annee_fin),
            (2, 'Février', annee_fin),
            (3, 'Mars', annee_fin),
            (4, 'Avril', annee_fin),
            (5, 'Mai', annee_fin),
            (6, 'Juin', annee_fin),
        ]
        return mois_debut + mois_fin


# 2. ########## CLASSE ##########


class EcoleInfo(models.Model):
    """Informations de l'établissement (configuration unique par installation)"""
    nom = models.CharField(max_length=200)
    sigle = models.CharField(max_length=50, blank=True, null=True)
    ministere = models.CharField(
        max_length=200, blank=True, null=True,
        default="MINISTERE DE L'EDUCATION NATIONALE"
    )
    circonscription = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="Ex: CAP DE KALABAN COURA"
    )
    academie = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="Ex: Académie d'Enseignement de Bamako Rive Gauche"
    )
    republique = models.CharField(
        max_length=200, blank=True, null=True,
        default="REPUBLIQUE DU MALI"
    )
    devise = models.CharField(
        max_length=200, blank=True, null=True,
        default="UN PEUPLE - UN BUT - UNE FOI"
    )
    adresse = models.CharField(max_length=150, blank=True, null=True)
    ville = models.CharField(max_length=100, blank=True, null=True)
    pays = models.CharField(max_length=100, blank=True, null=True, default="Mali")
    boite_postale = models.CharField(max_length=50, blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    site_web = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to='ecole/logo/', blank=True, null=True)
    signature_directeur = models.ImageField(
            upload_to='ecole/signatures/', 
            blank=True, null=True, 
            verbose_name="Signature du directeur",
            help_text="Image de la signature (format PNG avec fond transparent de préférence)"
        )
    cachet_ecole = models.ImageField(
            upload_to='ecole/cachets/', 
            blank=True, null=True, 
            verbose_name="Cachet de l'école",
            help_text="Image du cachet officiel (format PNG avec fond transparent)"
        )
    nom_directeur = models.CharField(max_length=150, blank=True, null=True)
    numero_autorisation = models.CharField(max_length=100, blank=True, null=True)
    setup_complete = models.BooleanField(
        default=False,
        verbose_name="Configuration initiale effectuée",
        help_text="Coché automatiquement après l'assistant de première configuration"
    )
    TYPE_ECOLE = [
        ('classique', 'Classique'),
        ('franco_arabe', 'Franco-arabe'),
    ]
    type_ecole = models.CharField(
        max_length=20,
        choices=TYPE_ECOLE,
        default='franco_arabe',
        verbose_name="Type d'école",
        help_text="Détermine si le nom arabe des matières est utilisé "
                  "(Franco-arabe) ou non (Classique)."
    )
        # ... (après type_ecole par exemple)
    activer_fondamental = models.BooleanField(
        default=True,
        verbose_name="Activer le module Fondamental",
        help_text="Si décoché, le module Fondamental est masqué pour les utilisateurs."
    )
    activer_lycee = models.BooleanField(
        default=True,
        verbose_name="Activer le module Lycée",
        help_text="Si décoché, le module Lycée est masqué pour les utilisateurs."
    )
    
    # =================================================================
    # MODE FRAIS D'INSCRIPTION
    # =================================================================
    MODE_FRAIS_INSCRIPTION = [
        ('unique', "Une seule fois (à la 1ère inscription)"),
        ('annuel', "Chaque année (à chaque inscription)"),
    ]
    mode_frais_inscription = models.CharField(
        max_length=20,
        choices=MODE_FRAIS_INSCRIPTION,
        default='annuel',
        verbose_name="Mode des frais d'inscription",
        help_text="Comment sont payés les frais d'inscription"
    )

    # =================================================================
    # MODE FRAIS DE SCOLARITÉ
    # =================================================================
    MODE_FRAIS_SCOLARITE = [
        ('mensuel', "Mensuel (9 versements)"),
        ('trimestriel', "Trimestriel (3 versements)"),
        ('tranches', "Par tranches personnalisées"),
        ('annuel', "Annuel (1 versement par an)"),
        ('unique', "Unique (tout le cursus)"),
    ]
    mode_frais_scolarite = models.CharField(
        max_length=20,
        choices=MODE_FRAIS_SCOLARITE,
        default='mensuel',
        verbose_name="Mode des frais de scolarité",
        help_text="Comment sont payés les frais de scolarité"
    )

    nombre_tranches = models.PositiveIntegerField(
        default=4,
        verbose_name="Nombre de tranches",
        help_text="Utilisé uniquement si le mode est 'Par tranches' (2, 3, 4, 5...)"
    )

    class Meta:
        verbose_name = "Informations de l'établissement"
        verbose_name_plural = "Informations de l'établissement"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(
            pk=1, defaults={'nom': "Nom de l'établissement"}
        )
        return obj
    
    # ✅ Propriété pratique
    @property
    def est_franco_arabe(self):
        """True si l'école est franco-arabe (affiche le nom arabe)."""
        return self.type_ecole == 'franco_arabe'

    @property
    def est_classique(self):
        """True si l'école est classique (pas de nom arabe)."""
        return self.type_ecole == 'classique'


# 13. ########## COMPOSITION MENSUELLE (1er cycle) ##########


class Licence(models.Model):
    """
    Licence d'utilisation. Une par installation.
    Deux modes : essai (30j) puis payée (illimitée).
    """
    MODE_LICENCE = [
        ('essai', 'Période d\'essai'),
        ('payee', 'Licence payée'),
    ]

    cle_licence = models.CharField(
        max_length=100, unique=True,
        verbose_name="Clé de licence",
        help_text="Générée automatiquement"
    )
    mode = models.CharField(
        max_length=20, choices=MODE_LICENCE, default='essai',
        verbose_name="Mode"
    )

    date_debut_essai = models.DateField(
        verbose_name="Début de l'essai",
        auto_now_add=True
    )
    date_fin_essai = models.DateField(
        verbose_name="Fin de l'essai",
        help_text="30 jours après le début"
    )

    date_paiement = models.DateField(
        null=True, blank=True,
        verbose_name="Date de paiement"
    )
    montant_paye = models.DecimalField(
        max_digits=10, decimal_places=0, default=0,
        verbose_name="Montant payé (FCFA)"
    )

    empreinte_machine = models.CharField(
        max_length=64,
        verbose_name="Empreinte de la machine",
        help_text="Unique pour cette installation"
    )

    nom_client = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name="Nom du client"
    )
    contact_client = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="Contact du client"
    )
    notes = models.TextField(
        blank=True, null=True,
        verbose_name="Notes internes"
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Licence"
        verbose_name_plural = "Licence"

    def __str__(self):
        if self.mode == 'essai':
            return f"Essai jusqu'au {self.date_fin_essai}"
        return f"Licence payée ({self.nom_client or 'Client'})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @staticmethod
    def aujourdhui():
        """
        Date utilisée pour juger l'essai : jamais antérieure à la dernière date
        vue par l'application (reculer l'horloge du PC ne redonne aucun jour).
        """
        from ..utils.licence import date_effective
        return date_effective()

    @property
    def licence_signee(self):
        """Infos de la clé de licence signée installée et valide, sinon None."""
        from ..utils.licence_signee import cle_signee_valide
        return cle_signee_valide()

    @property
    def paiement_reconnu(self):
        """
        True si la licence payée est reconnue :
        - une clé SIGNÉE valide est installée (non falsifiable), ou
        - (compatibilité) mode='payee' en base, tant que la signature n'est pas
          obligatoire (GESTION_ECOLE_LICENCE_SIGNEE / LICENCE_SIGNEE_OBLIGATOIRE).
        """
        from ..utils.licence_signee import cle_signee_valide, signature_obligatoire
        if cle_signee_valide():
            return True
        return self.mode == 'payee' and not signature_obligatoire()

    @property
    def jours_restants_essai(self):
        if self.est_payee:
            return None
        delta = self.date_fin_essai - self.aujourdhui()
        return max(0, delta.days)

    @property
    def est_en_essai(self):
        return not self.est_payee

    @property
    def est_payee(self):
        return self.paiement_reconnu

    @property
    def essai_expire(self):
        if self.est_payee:
            return False
        return self.aujourdhui() > self.date_fin_essai

    @property
    def est_valide(self):
        return self.est_payee or not self.essai_expire

    @property
    def empreinte_valide(self):
        from ..utils.licence import get_machine_fingerprint
        # Une clé signée est liée à la machine réelle (pas à la valeur en base,
        # modifiable) : si elle est valide, la machine est la bonne.
        if self.licence_signee:
            return True
        return self.empreinte_machine == get_machine_fingerprint()

    def activer_licence(self, nom_client='', contact='', montant=0, notes=''):
        self.mode = 'payee'
        self.date_paiement = timezone.now().date()
        self.nom_client = nom_client or self.nom_client
        self.contact_client = contact or self.contact_client
        self.montant_paye = montant
        if notes:
            self.notes = (self.notes or '') + f"\n[{timezone.now().strftime('%d/%m/%Y')}] {notes}"
        self.save()

    @classmethod
    def get_licence(cls):
        from ..utils.licence import (
            get_machine_fingerprint, debut_essai_reel, DUREE_ESSAI_JOURS,
        )

        # ✅ L'essai court depuis la PREMIÈRE utilisation sur ce poste (témoin),
        # pas depuis la création de la base : supprimer db.sqlite3 ne relance
        # plus 30 jours d'essai.
        licence, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'cle_licence': cls.generer_cle(),
                'mode': 'essai',
                'date_fin_essai': debut_essai_reel() + timedelta(days=DUREE_ESSAI_JOURS),
                'empreinte_machine': get_machine_fingerprint(),
            }
        )
        return licence

    @staticmethod
    def generer_cle():
        import secrets
        return secrets.token_hex(16).upper()


# 26. ########## MATIERE PAR CLASSE ##########


