"""
Tests de non-régression « socle » (Plan 2 — phase A).

But : détecter immédiatement toute casse d'import ou de routage
après l'éclatement des fichiers (phase B) et les évolutions
comptables / résultats (phases C et D).
"""
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import resolve

from ecole.models import AnneeScolaire, EcoleInfo

# Chemins représentatifs de chaque domaine fonctionnel.
# Si un import casse dans views/, models/ ou urls/, ces tests échouent.
URLS_ATTENDUES = [
    '/login/',
    '/fondamental/',
    '/fondamental/annees/',
    '/fondamental/classes/',
    '/fondamental/eleves/',
    '/fondamental/eleves/resultats/',
    '/fondamental/matieres/',
    '/fondamental/inscriptions/',
    '/fondamental/paiements/',
    '/fondamental/comptabilite/',
    '/fondamental/comptabilite/rapports/',
    '/fondamental/cycle1/notes/saisie/',
    '/fondamental/cycle2/notes/saisie/',
    '/fondamental/bulletins/',
    '/fondamental/resultats/',
    '/fondamental/emploi-temps/',
    '/lycee/',
    '/lycee/classes/',
    '/lycee/eleves/',
    '/lycee/inscriptions/',
    '/lycee/notes/saisie/',
    '/lycee/bulletins/',
    '/lycee/paiements/',
    '/lycee/comptabilite/',
    '/lycee/comptabilite/rapports/',
    '/lycee/emploi-temps/',
]

# Pages exécutées réellement (le rendu doit aboutir sans erreur 500).
PAGES_A_EXECUTER = [
    '/fondamental/',
    '/fondamental/annees/',
    '/fondamental/classes/',
    '/fondamental/eleves/',
    '/fondamental/eleves/resultats/',
    '/fondamental/matieres/',
    '/fondamental/inscriptions/',
    '/fondamental/paiements/',
    '/fondamental/comptabilite/',
    '/fondamental/comptabilite/rapports/',
    '/fondamental/bulletins/',
    '/fondamental/resultats/',
    '/fondamental/emploi-temps/',
    '/lycee/',
    '/lycee/classes/',
    '/lycee/eleves/',
    '/lycee/inscriptions/',
    '/lycee/paiements/',
    '/lycee/comptabilite/',
    '/lycee/comptabilite/rapports/',
    '/lycee/bulletins/',
    '/lycee/emploi-temps/',
]


class UrlconfTests(TestCase):
    """L'URLconf complète doit se charger et résoudre chaque route."""

    def test_toutes_les_urls_se_resolvent(self):
        for chemin in URLS_ATTENDUES:
            with self.subTest(chemin=chemin):
                match = resolve(chemin)
                self.assertIsNotNone(match.func)

    def test_page_login_accessible(self):
        reponse = Client().get('/login/')
        self.assertEqual(reponse.status_code, 200)

    def test_routes_protegees_redirigent(self):
        client = Client()
        for chemin in ['/fondamental/', '/lycee/', '/fondamental/comptabilite/']:
            with self.subTest(chemin=chemin):
                reponse = client.get(chemin)
                self.assertIn(reponse.status_code, (302, 301))


class SmokePagesTests(TestCase):
    """
    Exécute le corps des vues (pas seulement leur import).

    Sans cela, une fonction déplacée mais non importée ne serait
    détectée qu'en production, à l'ouverture de la page concernée.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username='smoke', email='smoke@example.com', password='smoke-pass-123'
        )
        info = EcoleInfo.get_solo()
        info.setup_complete = True
        info.save(update_fields=['setup_complete'])
        AnneeScolaire.objects.get_or_create(
            anneeScolaire='2025-2026',
            defaults={'date_debut': '2025-09-01', 'date_fin': '2026-06-30'},
        )

    def test_pages_principales_sans_erreur(self):
        client = Client()
        client.force_login(self.user)
        for chemin in PAGES_A_EXECUTER:
            with self.subTest(chemin=chemin):
                reponse = client.get(chemin, follow=False)
                self.assertNotEqual(
                    reponse.status_code, 500,
                    msg=f'{chemin} a renvoyé une erreur 500',
                )
                self.assertIn(reponse.status_code, (200, 302),
                              msg=f'{chemin} a renvoyé {reponse.status_code}')
