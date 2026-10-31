# ecole/management/commands/peupler_eleves.py
"""
Commande Django pour créer 27 élèves de test (18 au 1er cycle, 9 au 2e cycle).

Usage :
    python manage.py peupler_eleves
    python manage.py peupler_eleves --reset
    python manage.py peupler_eleves --avec-notes
    python manage.py peupler_eleves --avec-paiements
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from ecole.models import (
    AnneeScolaire, Classe, Eleve, Inscription, Matiere,
    MatiereClasse, Note, NoteMensuelle, Evaluation,
    CompositionMensuelle, Paiement,
)


# =====================================================================
# DONNÉES DE TEST
# =====================================================================

NOMS_MALIENS = [
    'Traoré', 'Diarra', 'Coulibaly', 'Konaté', 'Keita', 'Touré',
    'Diallo', 'Sidibé', 'Maïga', 'Cissé', 'Camara', 'Doumbia',
    'Sissoko', 'Bagayoko', 'Sanogo', 'Berthé', 'Dembélé', 'Kouyaté',
    'Fofana', 'Kanté', 'Samaké', 'Togola', 'Tangara', 'Bah',
    'Barry', 'Sylla', 'Condé',
]

PRENOMS_MASCULINS = [
    'Amadou', 'Moussa', 'Ibrahim', 'Seydou', 'Modibo', 'Oumar',
    'Bakary', 'Boubacar', 'Souleymane', 'Mamadou', 'Adama', 'Sékou',
    'Abdoulaye', 'Cheick', 'Yacouba', 'Drissa', 'Lassine', 'Alassane',
]

PRENOMS_FEMININS = [
    'Fatoumata', 'Aïssata', 'Kadiatou', 'Mariam', 'Awa', 'Oumou',
    'Rokia', 'Djeneba', 'Assitan', 'Bintou', 'Sitan', 'Nana',
    'Aminata', 'Hawa', 'Sira', 'Koumba', 'Fanta', 'Salimata',
]

LIEUX_NAISSANCE = [
    'Bamako', 'Ségou', 'Sikasso', 'Mopti', 'Kayes', 'Gao',
    'Koulikoro', 'Tombouctou', 'Kidal', 'Kita', 'San', 'Bougouni',
]

ECOLES_ANTERIEURES = [
    'École Fondamentale de Badalabougou',
    'École Fondamentale de Sabalibougou',
    'École Fondamentale de Kalaban Coura',
    'École Privée Les Palmiers',
    'École Fondamentale de Yirimadio',
    'École Privée Notre Dame',
    'École Fondamentale de Magnambougou',
    'École Fondamentale de Niamakoro',
]

REPARTITION_1ER_CYCLE = {
    '1ère Année': 3,
    '2ème Année': 3,
    '3ème Année': 3,
    '4ème Année': 3,
    '5ème Année': 3,
    '6ème Année': 3,
}

REPARTITION_2E_CYCLE = {
    '7ème A': 3,
    '8ème A': 3,
    '9ème A': 3,
}


class Command(BaseCommand):
    help = "Crée 27 élèves de test (18 au 1er cycle, 9 au 2e cycle)."

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help="Supprime les élèves de test avant de recréer.")
        parser.add_argument('--avec-notes', action='store_true',
                            help="Génère aussi des notes pour chaque élève.")
        parser.add_argument('--avec-paiements', action='store_true',
                            help="Génère aussi des paiements pour chaque élève.")

    # =================================================================
    # POINT D'ENTRÉE
    # =================================================================

    def handle(self, *args, **options):
        reset = options['reset']
        avec_notes = options['avec_notes']
        avec_paiements = options['avec_paiements']

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n╔══════════════════════════════════════════════════════════╗\n"
            "║   CRÉATION DE 27 ÉLÈVES DE TEST                          ║\n"
            "╚══════════════════════════════════════════════════════════╝\n"
        ))

        # =============================================================
        # 1. VÉRIFICATIONS PRÉALABLES
        # =============================================================
        annee_scolaire = AnneeScolaire.objects.order_by('-anneeScolaire').first()
        if not annee_scolaire:
            self.stdout.write(self.style.ERROR(
                "❌ Aucune année scolaire. Créez-en une d'abord."
            ))
            return

        self.stdout.write(f"📅 Année scolaire : {self.style.SUCCESS(annee_scolaire.anneeScolaire)}\n")

        # Vérifier les classes
        classes_1er = Classe.objects.filter(cycle='1er')
        classes_2e = Classe.objects.filter(cycle='2e')

        if classes_1er.count() < 6 or classes_2e.count() < 3:
            self.stdout.write(self.style.ERROR(
                f"❌ Il faut au moins 6 classes de 1er cycle et 3 de 2e cycle.\n"
                f"   Actuellement : {classes_1er.count()} (1er), {classes_2e.count()} (2e)."
            ))
            return

        # =============================================================
        # 2. RESET (si demandé)
        # =============================================================
        if reset:
            anciens = Eleve.objects.filter(matricule__startswith='TEST')
            nb = anciens.count()
            if nb > 0:
                anciens.delete()
                self.stdout.write(self.style.WARNING(
                    f"🗑️  {nb} ancien(s) élève(s) de test supprimé(s).\n"
                ))

        # =============================================================
        # 3. CRÉATION DES 27 ÉLÈVES
        # =============================================================
        self.stdout.write(self.style.HTTP_INFO("👥 Création des élèves...\n"))

        eleves_crees = []
        erreurs = 0

        # --- 18 élèves du 1er cycle ---
        for nom_classe, nb_eleves in REPARTITION_1ER_CYCLE.items():
            try:
                classe = Classe.objects.get(nomClasse=nom_classe)
            except Classe.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠️  Classe '{nom_classe}' introuvable, ignorée."
                ))
                continue

            for i in range(nb_eleves):
                try:
                    # ✅ Savepoint par élève : isole les erreurs
                    with transaction.atomic():
                        eleve = self._creer_eleve_avec_inscription(
                            classe=classe,
                            annee_scolaire=annee_scolaire,
                            index=len(eleves_crees) + 1,
                        )
                        eleves_crees.append(eleve)
                    self.stdout.write(
                        f"  ✅ {eleve.matricule} | "
                        f"{eleve.nomEleve} {eleve.prenomEleve} | "
                        f"{classe.nomClasse}"
                    )
                except Exception as e:
                    erreurs += 1
                    self.stdout.write(self.style.ERROR(
                        f"  ❌ Erreur pour {classe.nomClasse} #{i+1} : {e}"
                    ))

        # --- 9 élèves du 2e cycle ---
        for nom_classe, nb_eleves in REPARTITION_2E_CYCLE.items():
            try:
                classe = Classe.objects.get(nomClasse=nom_classe)
            except Classe.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠️  Classe '{nom_classe}' introuvable, ignorée."
                ))
                continue

            for i in range(nb_eleves):
                try:
                    with transaction.atomic():
                        eleve = self._creer_eleve_avec_inscription(
                            classe=classe,
                            annee_scolaire=annee_scolaire,
                            index=len(eleves_crees) + 1,
                        )
                        eleves_crees.append(eleve)
                    self.stdout.write(
                        f"  ✅ {eleve.matricule} | "
                        f"{eleve.nomEleve} {eleve.prenomEleve} | "
                        f"{classe.nomClasse}"
                    )
                except Exception as e:
                    erreurs += 1
                    self.stdout.write(self.style.ERROR(
                        f"  ❌ Erreur pour {classe.nomClasse} #{i+1} : {e}"
                    ))

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ {len(eleves_crees)} élève(s) créé(s) et inscrit(s)"
        ))
        if erreurs:
            self.stdout.write(self.style.WARNING(
                f"   ⚠️  {erreurs} erreur(s) rencontrée(s)"
            ))
        self.stdout.write("")

        # =============================================================
        # 4. NOTES (optionnel)
        # =============================================================
        if avec_notes and eleves_crees:
            self.stdout.write(self.style.HTTP_INFO("📝 Génération des notes...\n"))

            nb_notes = 0
            nb_erreurs_notes = 0

            for eleve in eleves_crees:
                try:
                    with transaction.atomic():
                        nb_notes += self._generer_notes_pour_eleve(eleve, annee_scolaire)
                except Exception as e:
                    nb_erreurs_notes += 1
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠️  Notes pour {eleve.matricule} : {e}"
                    ))

            self.stdout.write(self.style.SUCCESS(
                f"✅ {nb_notes} note(s) créée(s)"
            ))
            if nb_erreurs_notes:
                self.stdout.write(self.style.WARNING(
                    f"   ⚠️  {nb_erreurs_notes} élève(s) avec erreurs de notes"
                ))
            self.stdout.write("")

        # =============================================================
        # 5. PAIEMENTS (optionnel)
        # =============================================================
        if avec_paiements and eleves_crees:
            self.stdout.write(self.style.HTTP_INFO("💰 Génération des paiements...\n"))

            nb_paiements = 0
            nb_erreurs_paiements = 0

            for eleve in eleves_crees:
                try:
                    with transaction.atomic():
                        nb_paiements += self._generer_paiements_pour_eleve(eleve, annee_scolaire)
                except Exception as e:
                    nb_erreurs_paiements += 1
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠️  Paiements pour {eleve.matricule} : {e}"
                    ))

            self.stdout.write(self.style.SUCCESS(
                f"✅ {nb_paiements} paiement(s) créé(s)"
            ))
            if nb_erreurs_paiements:
                self.stdout.write(self.style.WARNING(
                    f"   ⚠️  {nb_erreurs_paiements} élève(s) avec erreurs de paiements"
                ))
            self.stdout.write("")

        # =============================================================
        # 6. RÉSUMÉ FINAL
        # =============================================================
        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(self.style.SUCCESS("✅ TERMINÉ"))
        self.stdout.write("═" * 60)
        self.stdout.write(f"  Élèves créés          : {len(eleves_crees)}")
        self.stdout.write(f"  - 1er cycle           : {sum(1 for e in eleves_crees if e.inscription_set.first().classe.cycle == '1er')}")
        self.stdout.write(f"  - 2e cycle            : {sum(1 for e in eleves_crees if e.inscription_set.first().classe.cycle == '2e')}")

        if avec_notes:
            self.stdout.write(
                f"  Notes 1er cycle       : "
                f"{NoteMensuelle.objects.filter(eleve__matricule__startswith='TEST').count()}"
            )
            self.stdout.write(
                f"  Notes 2e cycle        : "
                f"{Note.objects.filter(eleve__matricule__startswith='TEST').count()}"
            )
        if avec_paiements:
            self.stdout.write(
                f"  Paiements             : "
                f"{Paiement.objects.filter(inscription__eleve__matricule__startswith='TEST').count()}"
            )

        self.stdout.write(self.style.SUCCESS("\n🎉 Vous pouvez maintenant tester l'application !\n"))

    # =================================================================
    # CRÉATION D'UN ÉLÈVE + INSCRIPTION
    # =================================================================

    def _creer_eleve_avec_inscription(self, classe, annee_scolaire, index):
        """Crée un élève et son inscription. Lève une exception si erreur."""
        sexe = random.choice(['M', 'F'])
        nom = random.choice(NOMS_MALIENS)
        prenom = random.choice(PRENOMS_MASCULINS if sexe == 'M' else PRENOMS_FEMININS)

        age = self._age_pour_classe(classe.nomClasse)
        date_naiss = date(
            year=date.today().year - age,
            month=random.randint(1, 12),
            day=random.randint(1, 28),
        )
        lieu_naiss = random.choice(LIEUX_NAISSANCE)

        numero_acte = f"ACT-{random.randint(1000, 9999)}-{date_naiss.year}"
        date_delivrance = date_naiss + timedelta(days=random.randint(30, 365))

        pere_nom = f"{random.choice(PRENOMS_MASCULINS)} {random.choice(NOMS_MALIENS)}"
        mere_nom = f"{random.choice(PRENOMS_FEMININS)} {random.choice(NOMS_MALIENS)}"

        contact = f"+223 {random.randint(70, 79)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}"
        adresse = (
            f"Quartier "
            f"{random.choice(['Badalabougou', 'Sabalibougou', 'Kalaban Coura', 'Yirimadio', 'Magnambougou'])}, "
            f"Rue {random.randint(1, 999)}"
        )

        ecole_recrutement = random.choice(ECOLES_ANTERIEURES)
        ecole_fin_1er_cycle = None
        ecole_an_dernier = None

        if classe.cycle == '1er':
            annee_recrutement = self._annee_recrutement_1er_cycle(classe, annee_scolaire)
            annee_entree_7eme = None
        else:
            annee_recrutement = self._annee_recrutement_2e_cycle(classe, annee_scolaire)
            annee_entree_7eme = self._annee_entree_7eme(classe, annee_scolaire)
            ecole_fin_1er_cycle = random.choice(ECOLES_ANTERIEURES)
            ecole_an_dernier = random.choice(ECOLES_ANTERIEURES)

        scolarite_1er = self._scolarite_1er_cycle(classe.nomClasse)
        scolarite_2e = self._scolarite_2e_cycle(classe.nomClasse)

        # Création de l'élève (peut lever une exception)
        eleve = Eleve.objects.create(
            nomEleve=nom,
            prenomEleve=prenom,
            sexe=sexe,
            dateNaiss=date_naiss,
            lieuNaiss=lieu_naiss,
            pere=pere_nom,
            mere=mere_nom,
            contactTuteur=contact,
            adresseTuteur=adresse,
            numero_acte_naissance=numero_acte,
            date_delivrance_acte=date_delivrance,
            scolarite_1er_cycle=scolarite_1er,
            scolarite_2e_cycle=scolarite_2e,
            annee_recrutement=annee_recrutement,
            ecole_recrutement=ecole_recrutement,
            ecole_fin_1er_cycle=ecole_fin_1er_cycle,
            annee_entree_7eme=annee_entree_7eme,
            ecole_an_dernier=ecole_an_dernier,
        )

        # Matricule de test unique
        eleve.matricule = f"TEST{index:03d}"
        eleve.save(update_fields=['matricule'])

        # Inscription
        Inscription.objects.create(
            eleve=eleve,
            classe=classe,
            anneeScolaire=annee_scolaire,
        )

        return eleve

    # =================================================================
    # HELPERS : ÂGE / SCOLARITÉ / ANNÉES
    # =================================================================

    def _age_pour_classe(self, nom_classe):
        """Retourne un âge cohérent selon la classe."""
        ages = {
            '1ère Année': 6, '2ème Année': 7, '3ème Année': 8,
            '4ème Année': 9, '5ème Année': 10, '6ème Année': 11,
            '7ème A': 12, '8ème A': 13, '9ème A': 14,
        }
        return ages.get(nom_classe, 10) + random.randint(0, 1)

    def _scolarite_1er_cycle(self, nom_classe):
        """Années déjà effectuées au 1er cycle."""
        ordre = {
            '1ère Année': 0, '2ème Année': 1, '3ème Année': 2,
            '4ème Année': 3, '5ème Année': 4, '6ème Année': 5,
            '7ème A': 6, '8ème A': 6, '9ème A': 6,
        }
        return ordre.get(nom_classe, 0)

    def _scolarite_2e_cycle(self, nom_classe):
        """Années déjà effectuées au 2e cycle."""
        ordre = {
            '1ère Année': 0, '2ème Année': 0, '3ème Année': 0,
            '4ème Année': 0, '5ème Année': 0, '6ème Année': 0,
            '7ème A': 0, '8ème A': 1, '9ème A': 2,
        }
        return ordre.get(nom_classe, 0)

    def _annee_recrutement_1er_cycle(self, classe, annee_scolaire):
        """Année de recrutement (1ère Année) pour un élève du 1er cycle."""
        ordre = {
            '1ère Année': 0, '2ème Année': 1, '3ème Année': 2,
            '4ème Année': 3, '5ème Année': 4, '6ème Année': 5,
        }
        decalage = ordre.get(classe.nomClasse, 0)
        debut = annee_scolaire.get_annee_debut() - decalage
        return f"{debut}-{debut + 1}"

    def _annee_recrutement_2e_cycle(self, classe, annee_scolaire):
        """Année de recrutement (1ère Année) pour un élève du 2e cycle."""
        ordre = {'7ème A': 6, '8ème A': 7, '9ème A': 8}
        decalage = ordre.get(classe.nomClasse, 6)
        debut = annee_scolaire.get_annee_debut() - decalage
        return f"{debut}-{debut + 1}"

    def _annee_entree_7eme(self, classe, annee_scolaire):
        """Année d'entrée en 7ème Année."""
        ordre = {'7ème A': 0, '8ème A': 1, '9ème A': 2}
        decalage = ordre.get(classe.nomClasse, 0)
        debut = annee_scolaire.get_annee_debut() - decalage
        return f"{debut}-{debut + 1}"

    # =================================================================
    # NOTES PAR ÉLÈVE
    # =================================================================

    def _generer_notes_pour_eleve(self, eleve, annee_scolaire):
        """Génère les notes pour UN élève. Retourne le nombre de notes créées."""
        nb_notes = 0
        trimestres = [t[0] for t in Evaluation.TRIMESTRE]
        mois_scolaires = [10, 11, 12, 1, 2, 3]

        inscription = Inscription.objects.filter(
            eleve=eleve, anneeScolaire=annee_scolaire
        ).first()
        if not inscription:
            return 0

        classe = inscription.classe
        matieres = MatiereClasse.objects.filter(
            classe=classe
        ).select_related('matiere')

        if not matieres.exists():
            return 0

        if classe.cycle == '1er':
            # Notes mensuelles (1er cycle : notes sur 10)
            nb_mois = min(3, len(mois_scolaires))
            for mois in random.sample(mois_scolaires, k=nb_mois):
                composition, _ = CompositionMensuelle.objects.get_or_create(
                    mois=mois, anneeScolaire=annee_scolaire
                )
                for mc in matieres:
                    # Notes entre 3.0 et 9.5 sur 10 (par pas de 0.25)
                    note_val = Decimal(random.randint(12, 38)) / Decimal('4')
                    NoteMensuelle.objects.get_or_create(
                        eleve=eleve,
                        matiere=mc.matiere,
                        composition=composition,
                        defaults={'note': note_val},
                    )
                    nb_notes += 1
        else:
            # Notes trimestrielles (2e cycle : notes sur 20)
            nb_trimestres = min(2, len(trimestres))
            for trimestre in random.sample(trimestres, k=nb_trimestres):
                evaluation, _ = Evaluation.objects.get_or_create(
                    nomEvaluation=trimestre
                )
                for mc in matieres:
                    # Notes entre 6.0 et 19.0 sur 20 (par pas de 0.25)
                    note_val = Decimal(random.randint(24, 76)) / Decimal('4')
                    note_classe_val = Decimal(random.randint(24, 76)) / Decimal('4')
                    Note.objects.get_or_create(
                        eleve=eleve,
                        matiere=mc.matiere,
                        evaluation=evaluation,
                        anneeScolaire=annee_scolaire,
                        defaults={
                            'note': note_val,
                            'noteClasse': note_classe_val,
                        },
                    )
                    nb_notes += 1

        return nb_notes

    # =================================================================
    # PAIEMENTS PAR ÉLÈVE
    # =================================================================

    def _generer_paiements_pour_eleve(self, eleve, annee_scolaire):
        """Génère les paiements pour UN élève. Retourne le nombre de paiements."""
        nb_paiements = 0

        inscription = Inscription.objects.filter(
            eleve=eleve, anneeScolaire=annee_scolaire
        ).first()
        if not inscription:
            return 0

        classe = inscription.classe

        # Frais d'inscription (toujours payés)
        Paiement.objects.create(
            inscription=inscription,
            montant=classe.frais_inscription,
            est_inscription=True,
            annee_paiement=annee_scolaire.get_annee_debut(),
            observation="Frais d'inscription",
        )
        nb_paiements += 1

        # Mensualités (2 à 6 mois payés)
        nb_mois_payes = random.randint(2, 6)
        mois_a_payer = random.sample([10, 11, 12, 1, 2, 3, 4, 5, 6], k=nb_mois_payes)

        for mois in mois_a_payer:
            annee_paiement = (
                annee_scolaire.get_annee_debut()
                if mois in [10, 11, 12]
                else annee_scolaire.get_annee_fin()
            )

            # 80% complet, 20% partiel
            if random.random() < 0.8:
                montant = classe.mensualite
            else:
                montant = classe.mensualite * Decimal(
                    str(random.choice([0.3, 0.5, 0.7]))
                )

            Paiement.objects.create(
                inscription=inscription,
                montant=montant,
                mois=mois,
                annee_paiement=annee_paiement,
                est_inscription=False,
            )
            nb_paiements += 1

        return nb_paiements
