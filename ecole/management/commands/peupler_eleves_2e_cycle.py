# ecole/management/commands/peupler_eleves_2e_cycle.py
"""
Commande Django pour créer 90 élèves de test au 2e cycle.
30 élèves par classe (7ème A, 8ème A, 9ème A).
Chaque élève a des notes dans chaque trimestre.

Usage :
    python manage.py peupler_eleves_2e_cycle
    python manage.py peupler_eleves_2e_cycle --reset
    python manage.py peupler_eleves_2e_cycle --avec-notes
    python manage.py peupler_eleves_2e_cycle --avec-paiements
    python manage.py peupler_eleves_2e_cycle --par-classe 30
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from ecole.models import (
    AnneeScolaire, Classe, Eleve, Inscription, Matiere,
    MatiereClasse, Note, Evaluation, Paiement,
)


# =====================================================================
# DONNÉES DE TEST
# =====================================================================

NOMS_MALIENS = [
    'Traoré', 'Diarra', 'Coulibaly', 'Konaté', 'Keita', 'Touré',
    'Diallo', 'Sidibé', 'Maïga', 'Cissé', 'Camara', 'Doumbia',
    'Sissoko', 'Bagayoko', 'Sanogo', 'Berthé', 'Dembélé', 'Kouyaté',
    'Fofana', 'Kanté', 'Samaké', 'Togola', 'Tangara', 'Bah',
    'Barry', 'Sylla', 'Condé', 'Dagnoko', 'Kouma', 'Diarra',
]

PRENOMS_MASCULINS = [
    'Amadou', 'Moussa', 'Ibrahim', 'Seydou', 'Modibo', 'Oumar',
    'Bakary', 'Boubacar', 'Souleymane', 'Mamadou', 'Adama', 'Sékou',
    'Abdoulaye', 'Cheick', 'Yacouba', 'Drissa', 'Lassine', 'Alassane',
    'Baba', 'Karim', 'Issa', 'Ousmane', 'Sory', 'Youssouf',
]

PRENOMS_FEMININS = [
    'Fatoumata', 'Aïssata', 'Kadiatou', 'Mariam', 'Awa', 'Oumou',
    'Rokia', 'Djeneba', 'Assitan', 'Bintou', 'Sitan', 'Nana',
    'Aminata', 'Hawa', 'Sira', 'Koumba', 'Fanta', 'Salimata',
    'Oumou', 'Nènè', 'Kadidia', 'Sitan', 'Ramata', 'Astan',
]

LIEUX_NAISSANCE = [
    'Bamako', 'Ségou', 'Sikasso', 'Mopti', 'Kayes', 'Gao',
    'Koulikoro', 'Tombouctou', 'Kidal', 'Kita', 'San', 'Bougouni',
    'Koutiala', 'Nioro', 'Niono', 'Markala', 'Kati', 'Kolokani',
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
    'École Fondamentale de Missira',
    'École Fondamentale de Sotuba',
    'École Privée Les Étoiles',
    'École Fondamentale de Darsalam',
]

# Répartition : 30 élèves par classe du 2e cycle
CLASSES_2E_CYCLE = {
    '7ème Année A': 30,
    '8ème Année A': 30,
    '9ème Année A': 30,
}


class Command(BaseCommand):
    help = "Crée 90 élèves de test au 2e cycle (30 par classe) avec notes dans chaque trimestre."

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help="Supprime les élèves de test 2e cycle avant de recréer.")
        parser.add_argument('--avec-notes', action='store_true', default=True,
                            help="Génère des notes pour chaque trimestre (activé par défaut).")
        parser.add_argument('--sans-notes', action='store_true',
                            help="Ne pas générer de notes.")
        parser.add_argument('--avec-paiements', action='store_true', default=True,
                            help="Génère des paiements (activé par défaut).")
        parser.add_argument('--sans-paiements', action='store_true',
                            help="Ne pas générer de paiements.")
        parser.add_argument('--par-classe', type=int, default=30,
                            help="Nombre d'élèves par classe (défaut: 30).")

    # =================================================================
    # POINT D'ENTRÉE
    # =================================================================

    def handle(self, *args, **options):
        reset = options['reset']
        avec_notes = not options['sans_notes']
        avec_paiements = not options['sans_paiements']
        par_classe = options['par_classe']

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n╔══════════════════════════════════════════════════════════╗\n"
            "║   CRÉATION D'ÉLÈVES DE TEST - 2e CYCLE                   ║\n"
            "╚══════════════════════════════════════════════════════════╝\n"
        ))

        # =============================================================
        # 1. VÉRIFICATIONS
        # =============================================================
        annee_scolaire = AnneeScolaire.objects.order_by('-anneeScolaire').first()
        if not annee_scolaire:
            self.stdout.write(self.style.ERROR(
                "❌ Aucune année scolaire. Créez-en une d'abord."
            ))
            return

        self.stdout.write(
            f"📅 Année scolaire : {self.style.SUCCESS(annee_scolaire.anneeScolaire)}\n"
        )

        # Vérifier les classes du 2e cycle
        classes_2e = Classe.objects.filter(cycle='2e')
        if classes_2e.count() < 3:
            self.stdout.write(self.style.ERROR(
                f"❌ Il faut au moins 3 classes de 2e cycle.\n"
                f"   Actuellement : {classes_2e.count()}."
            ))
            return

        # Vérifier les matières pour le 2e cycle
        if avec_notes:
            for nom_classe in CLASSES_2E_CYCLE.keys():
                try:
                    classe = Classe.objects.get(nomClasse=nom_classe)
                    nb_matieres = MatiereClasse.objects.filter(classe=classe).count()
                    if nb_matieres == 0:
                        self.stdout.write(self.style.WARNING(
                            f"⚠️  La classe '{nom_classe}' n'a aucune matière associée."
                        ))
                        self.stdout.write(self.style.WARNING(
                            f"   → Lancez d'abord : python manage.py configurer_matieres --cycle 2e"
                        ))
                except Classe.DoesNotExist:
                    pass

        # =============================================================
        # 2. RESET
        # =============================================================
        if reset:
            anciens = Eleve.objects.filter(matricule__startswith='TEST2')
            nb = anciens.count()
            if nb > 0:
                anciens.delete()
                self.stdout.write(self.style.WARNING(
                    f"🗑️  {nb} ancien(s) élève(s) de test 2e cycle supprimé(s).\n"
                ))

        # =============================================================
        # 3. CRÉATION DES ÉLÈVES
        # =============================================================
        self.stdout.write(self.style.HTTP_INFO(
            f"👥 Création de {par_classe} élèves par classe (2e cycle)...\n"
        ))

        eleves_crees = []
        erreurs = 0
        index_global = 0

        for nom_classe, _ in CLASSES_2E_CYCLE.items():
            try:
                classe = Classe.objects.get(nomClasse=nom_classe)
            except Classe.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠️  Classe '{nom_classe}' introuvable, ignorée."
                ))
                continue

            self.stdout.write(f"\n  📚 {nom_classe} ({classe.cycle})")

            for i in range(par_classe):
                index_global += 1
                try:
                    with transaction.atomic():
                        eleve = self._creer_eleve_avec_inscription(
                            classe=classe,
                            annee_scolaire=annee_scolaire,
                            index=index_global,
                        )
                        eleves_crees.append(eleve)
                    # Affichage compact (1 ligne tous les 5 élèves)
                    if (i + 1) % 5 == 0 or i == par_classe - 1:
                        self.stdout.write(
                            f"    ✅ {i + 1}/{par_classe} élèves créés "
                            f"(jusqu'à {eleve.matricule})"
                        )
                except Exception as e:
                    erreurs += 1
                    self.stdout.write(self.style.ERROR(
                        f"    ❌ Erreur pour {nom_classe} #{i + 1} : {e}"
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
        # 4. NOTES POUR CHAQUE TRIMESTRE
        # =============================================================
        if avec_notes and eleves_crees:
            self.stdout.write(self.style.HTTP_INFO(
                "📝 Génération des notes pour chaque trimestre...\n"
            ))

            nb_notes = 0
            nb_erreurs_notes = 0
            trimestres = [t[0] for t in Evaluation.TRIMESTRE]

            for eleve in eleves_crees:
                try:
                    with transaction.atomic():
                        nb_notes += self._generer_notes_pour_eleve(
                            eleve, annee_scolaire, trimestres
                        )
                except Exception as e:
                    nb_erreurs_notes += 1
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠️  Notes pour {eleve.matricule} : {e}"
                    ))

            self.stdout.write(self.style.SUCCESS(
                f"✅ {nb_notes} note(s) créée(s) sur {len(trimestres)} trimestre(s)"
            ))
            if nb_erreurs_notes:
                self.stdout.write(self.style.WARNING(
                    f"   ⚠️  {nb_erreurs_notes} élève(s) avec erreurs"
                ))
            self.stdout.write("")

        # =============================================================
        # 5. PAIEMENTS
        # =============================================================
        if avec_paiements and eleves_crees:
            self.stdout.write(self.style.HTTP_INFO("💰 Génération des paiements...\n"))

            nb_paiements = 0
            nb_erreurs_paiements = 0

            for eleve in eleves_crees:
                try:
                    with transaction.atomic():
                        nb_paiements += self._generer_paiements_pour_eleve(
                            eleve, annee_scolaire
                        )
                except Exception as e:
                    nb_erreurs_paiements += 1
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠️  Paiements pour {eleve.matricule} : {e}"
                    ))

            self.stdout.write(self.style.SUCCESS(
                f"✅ {nb_paiements} paiement(s) créé(s)"
            ))
            self.stdout.write("")

        # =============================================================
        # 6. RÉSUMÉ FINAL
        # =============================================================
        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(self.style.SUCCESS("✅ TERMINÉ"))
        self.stdout.write("═" * 60)
        self.stdout.write(f"  Élèves 2e cycle créés : {len(eleves_crees)}")

        # Détail par classe
        for nom_classe in CLASSES_2E_CYCLE.keys():
            nb = Inscription.objects.filter(
                classe__nomClasse=nom_classe,
                eleve__matricule__startswith='TEST2',
                anneeScolaire=annee_scolaire,
            ).count()
            self.stdout.write(f"    - {nom_classe:10} : {nb} élève(s)")

        if avec_notes:
            from ecole.models import Note
            self.stdout.write(
                f"  Notes créées          : "
                f"{Note.objects.filter(eleve__matricule__startswith='TEST2').count()}"
            )
        if avec_paiements:
            self.stdout.write(
                f"  Paiements créés       : "
                f"{Paiement.objects.filter(inscription__eleve__matricule__startswith='TEST2').count()}"
            )

        self.stdout.write(self.style.SUCCESS(
            "\n🎉 Vous pouvez maintenant tester le 2e cycle !\n"
        ))

    # =================================================================
    # CRÉATION D'UN ÉLÈVE + INSCRIPTION
    # =================================================================

    def _creer_eleve_avec_inscription(self, classe, annee_scolaire, index):
        """Crée un élève du 2e cycle et son inscription."""
        sexe = random.choice(['M', 'F'])
        nom = random.choice(NOMS_MALIENS)
        prenom = random.choice(
            PRENOMS_MASCULINS if sexe == 'M' else PRENOMS_FEMININS
        )

        # Âge cohérent selon la classe
        age = self._age_pour_classe(classe.nomClasse)
        date_naiss = date(
            year=date.today().year - age,
            month=random.randint(1, 12),
            day=random.randint(1, 28),
        )
        lieu_naiss = random.choice(LIEUX_NAISSANCE)

        # Acte de naissance
        numero_acte = f"ACT-{random.randint(10000, 99999)}-{date_naiss.year}"
        date_delivrance = date_naiss + timedelta(days=random.randint(30, 730))

        # Parents
        pere_nom = (
            f"{random.choice(PRENOMS_MASCULINS)} "
            f"{random.choice(NOMS_MALIENS)}"
        )
        mere_nom = (
            f"{random.choice(PRENOMS_FEMININS)} "
            f"{random.choice(NOMS_MALIENS)}"
        )

        # Contact tuteur (format Mali)
        contact = (
            f"+223 {random.randint(60, 79)} "
            f"{random.randint(10, 99)} {random.randint(10, 99)} "
            f"{random.randint(10, 99)}"
        )
        quartiers = [
            'Badalabougou', 'Sabalibougou', 'Kalaban Coura',
            'Yirimadio', 'Magnambougou', 'Niamakoro', 'Missira',
            'Sotuba', 'Darsalam', 'Faladié',
        ]
        adresse = (
            f"Quartier {random.choice(quartiers)}, "
            f"Rue {random.randint(1, 999)}, "
            f"Porte {random.randint(1, 500)}"
        )

        # Écoles du parcours (élève du 2e cycle = a déjà fait son 1er cycle)
        ecole_recrutement = random.choice(ECOLES_ANTERIEURES)
        ecole_fin_1er_cycle = random.choice(ECOLES_ANTERIEURES)
        ecole_an_dernier = random.choice(ECOLES_ANTERIEURES)

        # Parcours scolaire
        annee_recrutement = self._annee_recrutement_2e_cycle(
            classe, annee_scolaire
        )
        annee_entree_7eme = self._annee_entree_7eme(classe, annee_scolaire)

        scolarite_1er = 6  # Le 1er cycle est complet
        scolarite_2e = self._scolarite_2e_cycle(classe.nomClasse)

        # Création de l'élève
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

        # Matricule unique pour identifier les élèves de test 2e cycle
        eleve.matricule = f"TEST2{index:03d}"
        eleve.save(update_fields=['matricule'])

        # Inscription
        Inscription.objects.create(
            eleve=eleve,
            classe=classe,
            anneeScolaire=annee_scolaire,
        )

        return eleve

    # =================================================================
    # HELPERS
    # =================================================================

    def _age_pour_classe(self, nom_classe):
        """Âge cohérent pour un élève du 2e cycle."""
        ages = {
            '7ème A': 12,
            '8ème A': 13,
            '9ème A': 14,
        }
        return ages.get(nom_classe, 13) + random.randint(0, 2)

    def _scolarite_2e_cycle(self, nom_classe):
        """Années déjà effectuées au 2e cycle."""
        ordre = {
            '7ème A': 0,
            '8ème A': 1,
            '9ème A': 2,
        }
        return ordre.get(nom_classe, 0)

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
    # NOTES POUR CHAQUE TRIMESTRE
    # =================================================================

    def _generer_notes_pour_eleve(self, eleve, annee_scolaire, trimestres):
        """Génère les notes pour TOUS les trimestres. Retourne le nombre de notes."""
        nb_notes = 0

        inscription = Inscription.objects.filter(
            eleve=eleve, anneeScolaire=annee_scolaire
        ).first()
        if not inscription:
            return 0

        classe = inscription.classe
        matieres_classe = MatiereClasse.objects.filter(
            classe=classe
        ).select_related('matiere')

        if not matieres_classe.exists():
            return 0

        for trimestre in trimestres:
            evaluation, _ = Evaluation.objects.get_or_create(
                nomEvaluation=trimestre
            )
            for mc in matieres_classe:
                # Notes entre 6.0 et 19.5 sur 20 (par pas de 0.25)
                note_val = Decimal(random.randint(24, 78)) / Decimal('4')
                note_classe_val = Decimal(random.randint(24, 78)) / Decimal('4')

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
    # PAIEMENTS
    # =================================================================

    def _generer_paiements_pour_eleve(self, eleve, annee_scolaire):
        """Génère les paiements pour un élève du 2e cycle."""
        nb_paiements = 0

        inscription = Inscription.objects.filter(
            eleve=eleve, anneeScolaire=annee_scolaire
        ).first()
        if not inscription:
            return 0

        classe = inscription.classe

        # Frais d'inscription
        Paiement.objects.create(
            inscription=inscription,
            montant=classe.frais_inscription,
            est_inscription=True,
            annee_paiement=annee_scolaire.get_annee_debut(),
            observation="Frais d'inscription",
        )
        nb_paiements += 1

        # Mensualités (entre 4 et 8 mois payés)
        nb_mois_payes = random.randint(4, 8)
        mois_a_payer = random.sample(
            [10, 11, 12, 1, 2, 3, 4, 5, 6],
            k=nb_mois_payes
        )

        for mois in mois_a_payer:
            annee_paiement = (
                annee_scolaire.get_annee_debut()
                if mois in [10, 11, 12]
                else annee_scolaire.get_annee_fin()
            )

            # 85% complet, 15% partiel
            if random.random() < 0.85:
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
