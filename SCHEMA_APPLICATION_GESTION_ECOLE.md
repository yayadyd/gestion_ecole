
---

## 3. Modèles de données (fondamental)

### 3.1 `AnneeScolaire`
| Champ | Type | Description |
|---|---|---|
| `idAnneeScolaire` | AutoField | PK |
| `anneeScolaire` | CharField(9) | Format `AAAA-AAAA` |
| `date_debut`, `date_fin` | DateField | Dates de début/fin |

**Méthodes** : `get_annee_debut()`, `get_annee_fin()`, `get_mois_scolaires()`.

---

### 3.2 `Classe`
| Champ | Type | Description |
|---|---|---|
| `idClasse` | AutoField | PK |
| `nomClasse` | CharField(choices) | 1ère A → 9ème B |
| `cycle` | CharField | `1er` ou `2e` |

**Propriétés** : `est_1er_cycle`, `est_2e_cycle`, `nom_niveau`, `suffixe`.

---

### 3.3 `FraisClasseAnnee`
| Champ | Type | Description |
|---|---|---|
| `classe` | FK Classe | |
| `annee_scolaire` | FK AnneeScolaire | |
| `frais_inscription` | Decimal | |
| `frais_scolarite` | Decimal | Montant annuel |

**Contrainte** : `unique_together = ('classe', 'annee_scolaire')`.

---

### 3.4 `Eleve`
| Champ | Type | Description |
|---|---|---|
| `matricule` | CharField unique | Généré auto (nom+prénom+date) |
| `prenomEleve`, `nomEleve` | CharField | |
| `sexe` | CharField(M/F) | |
| `dateNaiss`, `lieuNaiss` | | |
| `pere`, `mere`, `contactTuteur`, `adresseTuteur` | | |
| `photo` | ImageField | |
| `numero_acte_naissance`, `date_delivrance_acte` | | |
| `scolarite_1er_cycle`, `scolarite_2e_cycle` | PositiveInteger | Compteurs |
| `scolarite_totale` | PositiveInteger | Calculé |
| `redoublement_1`, `_2`, `_3` | CharField | Calculés |
| `annee_recrutement`, `ecole_recrutement`, `ecole_fin_1er_cycle`, `annee_entree_7eme`, `ecole_an_dernier` | CharField | Saisis manuellement |

**Méthodes** : `generer_matricule()`, `save()` (fige le matricule), `regenerer_matricule()`, `get_age()`.

---

### 3.5 `Matiere`
| Champ | Type | Description |
|---|---|---|
| `idMatiere` | AutoField | PK |
| `nomMatiere` | CharField | |
| `nomArabe` | CharField (optionnel) | |
| `coef` | Decimal | Coefficient (ignoré en 1er cycle) |
| `cycle` | CharField | `1er` ou `2e` |
| `tendance` | CharField | `litteraire` / `scientifique` (2e cycle) |

**Contrainte** : `unique_together = ('nomMatiere', 'cycle')`.

---

### 3.6 `Evaluation` (2e cycle)
| Champ | Type | Description |
|---|---|---|
| `nomEvaluation` | CharField | 3 trimestres |

---

### 3.7 `Inscription`
| Champ | Type | Description |
|---|---|---|
| `eleve` | FK Eleve | |
| `classe` | FK Classe | |
| `anneeScolaire` | FK AnneeScolaire | |
| `frais_inscription_historique` | Boolean | Payé avant l'app |

**Contrainte** : `unique_together = ('eleve', 'anneeScolaire')`.
**Effets** : `save()` incrémente la scolarité, `delete()` la décrémente.
**Propriétés** : `frais_unique_deja_paye`, `frais_inscription_attendu`, `frais_scolarite_attendu`, `montant_paye_total`.

---

### 3.8 `Paiement`
| Champ | Type | Description |
|---|---|---|
| `inscription` | FK Inscription | |
| `montant` | Decimal | |
| `date_paiement` | DateField auto | |
| `mois` | Integer (choices) | 10 → 6 (mensuel) |
| `annee_paiement` | Integer | Année réelle |
| `est_inscription` | Boolean | |
| `observation` | CharField | |

**Propriétés** : `montant_attendu`, `total_paye_pour_ce_mois()`.

---

### 3.9 `Note` (2e cycle)
| Champ | Type | Description |
|---|---|---|
| `eleve` | FK Eleve | |
| `matiere` | FK Matiere | |
| `evaluation` | FK Evaluation | |
| `anneeScolaire` | FK AnneeScolaire | |
| `note` | Decimal | Note de composition (sur 20) |
| `noteClasse` | Decimal | Note de classe (sur 20) |

**Formule** : `moyenne = (noteClasse + note*2) / 3`.

---

### 3.10 `ResultatTrimestre` (2e cycle)
| Champ | Type | Description |
|---|---|---|
| `inscription` | FK Inscription | |
| `trimestre` | CharField | |
| `anneeScolaire` | FK AnneeScolaire | |
| `moyenne_generale` | Decimal | |
| `rang` | Integer | |
| `appreciation` | TextField | |
| `date_calcul` | DateTime auto | |

**Contrainte** : `unique_together = ('inscription', 'trimestre', 'anneeScolaire')`.

---

### 3.11 `DetailResultat` (2e cycle)
| Champ | Type | Description |
|---|---|---|
| `resultat` | FK ResultatTrimestre | |
| `matiere` | FK Matiere | |
| `note_classe`, `note_compo` | Decimal | |
| `moyenne_generale`, `moyenne_coefficientee` | Decimal | |
| `coef` | Decimal | |
| `appreciation` | CharField | |

---

### 3.12 `EcoleInfo` (singleton)
| Champ | Type | Description |
|---|---|---|
| `nom`, `sigle` | CharField | |
| `ministere`, `circonscription`, `academie`, `republique`, `devise` | | |
| `adresse`, `ville`, `pays`, `boite_postale`, `telephone`, `email`, `site_web` | | |
| `logo`, `signature_directeur`, `cachet_ecole` | ImageField | |
| `nom_directeur`, `numero_autorisation` | | |
| `setup_complete` | Boolean | |
| `type_ecole` | CharField | `classique` ou `franco_arabe` |
| `mode_frais_inscription` | CharField | `unique` ou `annuel` |
| `mode_frais_scolarite` | CharField | `mensuel`, `trimestriel`, `tranches`, `annuel`, `unique` |
| `nombre_tranches` | PositiveInteger | |
| `activer_fondamental`, `activer_lycee` | Boolean | (à ajouter) |

**Méthode** : `get_solo()` force `pk=1`.

---

### 3.13 `CompositionMensuelle` (1er cycle)
| Champ | Type | Description |
|---|---|---|
| `mois` | Integer | 10 → 6 |
| `anneeScolaire` | FK | |

**Contrainte** : `unique_together = ('mois', 'anneeScolaire')`.

---

### 3.14 `NoteMensuelle` (1er cycle)
| Champ | Type | Description |
|---|---|---|
| `eleve` | FK Eleve | |
| `matiere` | FK Matiere | |
| `composition` | FK CompositionMensuelle | |
| `note` | Decimal | Sur 10 |

**Contrainte** : `unique_together = ('eleve', 'matiere', 'composition')`.

---

### 3.15 `ResultatMensuel` (1er cycle)
| Champ | Type | Description |
|---|---|---|
| `inscription` | FK Inscription | |
| `composition` | FK CompositionMensuelle | |
| `moyenne_generale` | Decimal | |
| `rang`, `appreciation` | | |

---

### 3.16 `DetailResultatMensuel` (1er cycle)
| Champ | Type | Description |
|---|---|---|
| `resultat` | FK ResultatMensuel | |
| `matiere` | FK Matiere | |
| `note`, `appreciation` | | |

---

### 3.17 `CertificatTransfert`
| Champ | Type | Description |
|---|---|---|
| `inscription` | FK Inscription | |
| `travail`, `conduite`, `decision_conseil_maitres`, `motif_transfert`, `ecole_destination` | CharField | |
| `date_delivrance` | DateField auto | |

---

### 3.18 `CategorieDepense`, `Depense`
Catégories et dépenses. `Depense` porte un champ **`section`**
(`1er` | `2e` | `lycee` | `commun`, défaut `commun`) qui détermine
l'imputation comptable. `CategorieDepense` porte `section_defaut`
(pré-remplissage du formulaire).

### 3.19 `CategorieRecette`, `Recette`
Catégories et recettes hors paiements. Mêmes champs `section` /
`section_defaut` que les dépenses.

### 3.18bis `Section` (TextChoices, modèle dans `finances.py`)
Dimension d'analyse de la comptabilité : `1er`, `2e`, `lycee`, `commun`.
Chaque mouvement (dépense/recette) n'appartient qu'à **une** section.
Les paiements d'élèves n'utilisent pas ce champ : leur section est
**dérivée** (`inscription.classe.cycle`) ou vaut `lycee`.

### 3.20 `PlageHoraire`
| Champ | Type | Description |
|---|---|---|
| `cycle` | CharField | `1er` ou `2e` |
| `ordre`, `heure_debut`, `heure_fin`, `libelle`, `est_pause` | | |

---

### 3.21 `EmploiTemps`, `CreneauEmploiTemps`
Emploi du temps par classe et année scolaire.

---

### 3.22 `Licence` (singleton)
| Champ | Type | Description |
|---|---|---|
| `cle_licence`, `mode`, `date_debut_essai`, `date_fin_essai`, `date_paiement`, `montant_paye`, `empreinte_machine`, `nom_client`, `contact_client`, `notes` | | |

**Méthodes** : `get_licence()` (crée l'instance), `activer_licence()`, `licence_signee`, `paiement_reconnu`, `est_valide`, `empreinte_valide`.

---

### 3.23 `MatiereClasse`
| Champ | Type | Description |
|---|---|---|
| `classe`, `matiere`, `annee_scolaire` | FK | |
| `ordre_affichage`, `obligatoire` | | |

**Contrainte** : `unique_together = ('classe', 'matiere', 'annee_scolaire')`.

---

## 4. Modèles spécifiques au lycée

### 4.1 `MatiereLycee`
Matières du lycée (indépendantes du fondamental). Champs : `nom`, `nom_arabe`, `domaine`, `obligatoire`, `ordre_affichage`, `active`.

### 4.2 `CoefficientLycee`
Coefficients par (matière, niveau, série). Niveaux : 10, 11, 12. Séries : L, SES, S, TLL, TAL, TSS, TSEco, TSExp, TSE.

### 4.3 `ClasseLycee`
Champs : `nom`, `niveau`, `serie`, `annee_scolaire`, `frais_inscription`, `frais_scolarite`.

### 4.4 `EleveLycee`
Matricule **saisi manuellement**. Statut : `oriente` (gratuit) ou `payant`. Champs : identité, filiation, acte de naissance, provenance DEF, statut.

### 4.5 `InscriptionLycee`
Inscription d'un élève à une classe de lycée. Statut de gratuité via l'élève.

### 4.6 `NoteLycee`
Notes par matière et trimestre. Formule : `(Composition*2 + NoteClasse) / 3`.

### 4.7 `ResultatTrimestreLycee`, `DetailResultatLycee`
Résultats trimestriels du lycée.

### 4.8 `PaiementLycee`
Même logique que `Paiement`, adapté au lycée.

### 4.9 `PlageHoraireLycee`, `EmploiTempsLycee`, `CreneauEmploiTempsLycee`
Emploi du temps du lycée.

### 4.10 `MatiereClasseLycee`
Association matière / classe du lycée.

---

## 5. Services et logique métier

### 5.1 `services/moyennes.py`

| Fonction | Rôle |
|---|---|
| `_get_matieres_classe(classe, cycle, annee)` | Matières d'une classe pour une année. |
| `_calcul_trimestriel(matieres, notes)` | Calcul 2e cycle. |
| `_calcul_mensuel(matieres, notes)` | Calcul 1er cycle. |
| `_persister(...)` | Écritures en lot. |
| `calculer_moyennes_classe_bulk(classe, unite, annee)` | Calcule les moyennes d'une classe. |
| `calculer_moyennes_inscription(inscription, unite, annee)` | Calcule pour une inscription. |
| `classer_inscriptions(inscriptions, unite)` | Classement avec ex æquo. |

**Règles** :
- Une matière sans note est ignorée (ni numérateur, ni dénominateur).
- Les matières proviennent de `MatiereClasse` pour l'année concernée.
- Arrondi scolaire (`ROUND_HALF_UP`).

---

### 5.2 `services/paiements.py`

| Fonction | Rôle |
|---|---|
| `_get_frais_classe(classe, annee)` | Récupère les frais depuis `FraisClasseAnnee`. |
| `_repartir(total, nb)` | Répartition en `nb` parts entières. |
| `calculer_echeances(ecole, classe, annee)` | Liste des échéances selon le mode. |
| `_deja_paye_avant(inscription, est_inscription)` | Frais uniques déjà payés. |
| `_allouer_paiements(echeances, paiements)` | Répartition des paiements sur les échéances. |
| `calculer_montants_inscription(inscription)` | Retourne un dictionnaire complet (frais attendus, payés, détail des échéances). |

**Modes gérés** : `mensuel` (9 versements), `trimestriel` (3), `tranches` (N), `annuel` (1), `unique` (1 pour tout le cursus).

---

### 5.3 `cycles.py`

Centralise la logique des cycles.

| Élément | Rôle |
|---|---|
| `Cycle.PREMIER`, `Cycle.SECOND` | Enum |
| `Cycle.calculer_moyenne_matiere(note_classe, note_compo, coef)` | 1er : note = compo ; 2e : `(noteClasse + compo*2) / 3`. |
| `Cycle.appreciation(moyenne)` | Échelle sur 10 (1er) ou 20 (2e). |
| `attribuer_rangs(resultats_tries)` | Ex æquo (1, 2, 2, 4). |
| `arrondir_moyenne(valeur)` | `ROUND_HALF_UP`. |
| `STRUCTURE_TENTATIVES_2E_CYCLE` | `{'7ème A': 2, '8ème A': 2, '9ème A': 3}`. |

---

### 5.4 `services/comptabilite.py`

Source de vérité **unique** de la comptabilité. Aucune vue n'agrège des montants.

| Fonction | Rôle |
|---|---|
| `etat_comptable(annee)` | Recettes / dépenses / résultat des 4 sections + global. |
| `detail_financier(annee, section)` | Frais/scolarité, catégories, compteurs, dernières dépenses. |
| `evolution_mensuelle(annee, section)` | Série sur les 12 mois scolaires. |
| `section_valide(code)` | Valide le code de section (ou `None` = global). |

**Invariant** : `global == 1er + 2e + lycee + commun` (aucun double comptage).
Les paiements du fondamental sont répartis par `inscription.classe.cycle` ;
ceux du lycée (via `PaiementLycee`) vont dans la section `lycee`.

---

### 5.5 `services/resultats.py`

Façade de **lecture** des résultats (aucun recalcul).

| Fonction | Rôle |
|---|---|
| `periodes(annee, section)` | Compositions mensuelles (1er) ou trimestres (2e/lycée). |
| `resultats(annee, section, periode, classe)` | Lignes normalisées : élève, matricule, classe, moyenne, rang, appréciation, lien bulletin, statut. |
| `resume_global(annee)` | Synthèse par section (nb résultats, inscriptions, moyenne, état). |

---

## 6. Vues (fondamental)

### 6.1 Authentification
- `CustomLoginView` (page de login avec `EcoleInfo`).

### 6.2 Dashboard
- `dashboard` : statistiques globales par cycle, paiements, inscriptions récentes.

### 6.3 CRUD génériques (ListView, CreateView, UpdateView, DeleteView)
| Modèle | Vues |
|---|---|
| `AnneeScolaire` | List, Create, Update, Delete |
| `Classe` | List, Create, Update, Delete |
| `Eleve` | List, Detail, Create, Update, Delete, `eleve_regenerer_matricule` |
| `Matiere` | List, Create, Update, Delete |
| `MatiereClasse` | List, Create, Update, Delete, `matiere_classe_copier_annee`, `matiere_classe_copier_pour_classe`, `matiere_classe_copier_depuis_classe` |
| `Inscription` | List, Create, Update, Delete |
| `Paiement` | List (fonction), Create, Update, Delete |
| `Evaluation` | List, Create, Update, Delete |
| `Note` | List, Create, Update, Delete |
| `PlageHoraire` | List, Create, Update, Delete |
| `Depense`, `Recette` | List, Create, Update, Delete |

### 6.4 Cycle 1er
- `cycle1_saisie_notes` : saisie des notes mensuelles.
- `cycle1_enregistrer_notes` : enregistrement.
- `cycle1_calculer_moyennes` : calcul des moyennes.
- `cycle1_classer_eleves` : classement.
- `cycle1_notes_list` : liste des notes.
- `cycle1_bulletins_index` : page d'accueil des bulletins.
- `cycle1_bulletin_classe` : bulletins de la classe.
- `cycle1_bulletin_eleve` : bulletin individuel (HTML).
- `cycle1_bulletin_eleve_pdf` : bulletin PDF.
- `cycle1_bulletins_eleve_annee` : historique par année.
- `cycle1_exporter_bulletins_pdf` : export PDF de la classe.

### 6.5 Cycle 2e
- `cycle2_saisie_notes`, `cycle2_enregistrer_notes` : saisie des notes trimestrielles.
- `cycle2_calculer_moyennes`, `cycle2_classer_eleves` : calculs.
- `cycle2_bulletins_index`, `cycle2_bulletins_classe`, `cycle2_bulletin_eleve` : bulletins.
- `cycle2_bulletin_eleve_pdf`, `cycle2_exporter_bulletins_pdf` : PDF.
- `cycle2_bulletins_eleve_annee` : historique.

### 6.6 Documents officiels
- `dossier_scolaire_eleve` : dossier complet.
- `certificat_frequentation`, `certificat_frequentation_pdf` : certificat de fréquentation.
- `proposition_passage_index`, `proposition_passage`, `proposition_passage_pdf` : proposition de passage.
- `certificat_transfert_form`, `certificat_transfert_preview`, `certificat_transfert_pdf`, `certificat_transfert_dossier_complet_pdf` : certificat de transfert.
- `fiche_suivi_second_cycle_preview`, `fiche_suivi_second_cycle_pdf` : fiche de suivi 2e cycle.
- `dossiers_scolaires_index` : index des dossiers.

### 6.7 Comptabilité
- `depense_list`, `DepenseCreateView`, `DepenseUpdateView`, `DepenseDeleteView` (filtre `section`).
- `recette_list`, `RecetteCreateView`, `RecetteUpdateView`, `RecetteDeleteView` (filtre `section`).
- `comptabilite_dashboard` : vue **unifiée** avec sélecteur `?section=1er|2e|lycee|commun|global` + tableau « Répartition par section ».
- `lycee_comptabilite_dashboard` : **redirige** vers `?section=lycee` (supprime le double comptage).
- `rapports_comptables`, `rapport_pdf`, `rapport_csv` : rapports.

### 6.15 Résultats unifiés
- `resultats_index` : `/fondamental/resultats/?section=…&periode=…&classe=…`.
- Onglets : 1er cycle (compositions), 2e cycle (trimestres), lycée (trimestres), Synthèse.
- Tableau + lien vers le bulletin PDF existant + indicateur « calculé / à calculer ».

### 6.8 Emploi du temps
- `plage_horaire_list`, `PlageHoraireCreateView`, etc.
- `emploi_temps_index`, `emploi_temps_gestion`, `emploi_temps_enregistrer_creneau`, `emploi_temps_reconduire`, `emploi_temps_pdf`, `emploi_temps_tous_pdf`.

### 6.9 Cartes scolaires
- `carte_scolaire_preview`, `carte_scolaire_pdf`, `carte_scolaire_classe_pdf`.

### 6.10 API JSON
- `api_eleves_par_classe`, `api_notes_eleve`, `api_recherche_inscriptions`, `api_recherche_eleves`, `api_classe_info`, `api_stats_globales`, `api_matieres_par_classe`, `api_detail_paiements_mois`.

### 6.11 Licence
- `licence_expiree`, `licence_activer`, `licence_machine_invalide`, `licence_info`.

### 6.12 Setup (assistant)
- `setup_step1`, `setup_step2`, `setup_step3`, `setup_finalise`, `afficher_cle_setup_view`.

### 6.13 Utilisateurs
- Voir `views_utilisateurs.py`.

### 6.14 Frais et matières par classe
- `frais_classe_annee_edit` : édition des frais par année.

---

## 7. Vues (lycée)

### 7.1 Dashboard
- `dashboard_lycee` : statistiques du lycée.

### 7.2 CRUD (génériques)
| Modèle | Vues |
|---|---|
| `MatiereLycee` | List, Create, Update, Delete |
| `CoefficientLycee` | List, Create, Update, Delete |
| `ClasseLycee` | List, Create, Update, Delete, `classe_lycee_dupliquer_annee` |
| `EleveLycee` | List, Detail, Create, Update, Delete |
| `InscriptionLycee` | List, Create, Update, Delete |
| `PaiementLycee` | List (fonction), Create, Update, Delete, `paiement_lycee_detail` |
| `PlageHoraireLycee` | List, Create, Update, Delete |
| `MatiereClasseLycee` | List, Create, Update, Delete, `matiere_classe_lycee_copier` |

### 7.3 Notes / bulletins
- `saisie_notes_par_classe`, `notes_list`.
- `calculer_moyennes_trimestre`, `classer_eleves_trimestre`.
- `bulletins_index`, `bulletins_classe`, `bulletin_eleve`, `bulletin_eleve_pdf`, `bulletins_classe_pdf`.

### 7.4 API JSON
- `api_recherche_eleves_lycee`, `api_recherche_inscriptions_lycee`, `api_matieres_par_classe_lycee`, `api_matieres_par_serie`, `api_notes_eleve_lycee`, `api_info_inscription_lycee`, `api_matieres_par_classe_lycee_avec_coef`.

### 7.5 Emploi du temps
- `plage_lycee_list`, `emploi_temps_lycee_index`, `emploi_temps_lycee_gestion`, `emploi_temps_lycee_enregistrer_creneau`, `emploi_temps_lycee_reconduire`, `emploi_temps_lycee_pdf`, `emploi_temps_lycee_tous_pdf`.

### 7.6 Paramètres partagés
- `AnneeLyceeListView`, `AnneeLyceeCreateView`, etc.
- `parametres_ecole_lycee`.

### 7.7 Cartes scolaires (lycée)
- `carte_scolaire_lycee_preview`, `carte_scolaire_lycee_pdf`, `carte_scolaire_lycee_classe_pdf`.

---

## 8. Templates (résumé)

### 8.1 Fondamental
- `ecole/base.html` : layout de base.
- `ecole/dashboard.html` : tableau de bord.
- `ecole/annee_scolaire/*`, `ecole/classe/*`, `ecole/eleve/*`, `ecole/matiere/*`, `ecole/matiere_classe/*`.
- `ecole/inscription/*`, `ecole/paiement/*`.
- `ecole/cycle1/*`, `ecole/cycle2/*`.
- `ecole/certificats/*`, `ecole/dossier/*`, `ecole/proposition_passage/*`.
- `ecole/comptabilite/*`, `ecole/emploi_temps/*`.
- `ecole/carte_scolaire/*`.
- `ecole/note/*`, `ecole/licence/*`.
- `ecole/setup/*` (step1, step2, step3, finalise, cle_setup).
- `ecole/parametres/ecole.html`.

### 8.2 Lycée
- `lycee/base_lycee.html` : layout lycée.
- `lycee/dashboard.html`, `lycee/matiere/*`, `lycee/classe/*`, `lycee/eleve/*`, `lycee/inscription/*`, `lycee/notes/*`, `lycee/bulletins/*`, `lycee/paiement/*`, `lycee/emploi_temps/*`, `lycee/matiere_classe/*`, `lycee/parametres/*`.

### 8.3 Erreurs
- `erreurs/404.html`, `erreurs/500.html`, `erreurs/403.html`.

---

## 9. Context processors (variables dans tous les templates)

| Nom | Variable injectée | Cache |
|---|---|---|
| `parametres_globaux` | `ACTIVER_FONDAMENTAL`, `ACTIVER_LYCEE` | Non |
| `annee_encours` | `annee_encours` (année courante) | 1h |
| `trimestres` | `trimestres` (liste des trimestres) | Non |
| `cycle_courant` | `cycle_courant`, `peut_gerer_1er`, `peut_gerer_2e` | Non |
| `licence_context` | `licence` (objet Licence) | 5min |
| `alertes_configuration` | `classes_sans_matieres` | 5min |
| `ecole_info` | `ecole` (objet EcoleInfo), raccourcis modes de paiement | Non |
| `stats_lycee_header` | `nb_eleves`, `nb_classes`, `annee_encours` (lycée) | Non |

---

## 10. Middlewares

| Middleware | Rôle |
|---|---|
| `LicenceMiddleware` | Vérifie la validité de la licence (redirige vers `licence_expiree` ou `licence_machine_invalide`). |
| `SetupRedirectMiddleware` | Redirige vers le setup si `setup_complete` est `False`. |
| `ModuleAccessMiddleware` | Bloque l'accès aux modules désactivés (fondamental/lycée). |

**URLs exemptées** : `/licence/`, `/login/`, `/logout/`, `/admin/`, `/static/`, `/media/`, `/setup/`.

---

## 11. Utilitaires et services

### 11.1 Licence (`utils/licence.py`)
- `get_user_data_dir()` : dossier `~/.gestion_ecole_data`.
- `get_machine_fingerprint()` : empreinte unique (machine_id + MAC + hostname + OS).
- `get_code_machine()` : code à communiquer au vendeur.
- `get_machine_id_lisible()` : 8 premiers caractères.
- `date_effective()` : `max(aujourd'hui, dernière_date_vue)`.
- `debut_essai_reel()` : date de première utilisation.
- Témoin de première utilisation (fichier + registre Windows).

### 11.2 Licence signée (`utils/licence_signee.py`)
- Format : `GE1.base64(payload).base64(signature)`.
- Payload : `{"v":1, "m":"<code_machine>", "c":"<client>", "t":"payee", "e":<expiration>, "i":<émission>, "n":<n°>}`.
- `fabriquer_cle(secret, code_machine, client, expire, numero, emise)` : côté vendeur.
- `verifier_cle(cle, code_machine, public)` : vérifie signature + machine.
- `installer_cle(cle)` : enregistre la clé dans `~/.gestion_ecole_data/licence.key`.

### 11.3 Cryptographie (`utils/ed25519.py`)
Implémentation RFC 8032 en Python pur.

### 11.4 Setup (`utils/setup.py`)
- `generer_cle_setup(force=False)`.
- `get_cle_setup()`.
- `verifier_cle_setup(request)` : vérifie la clé passée en GET ou POST.

### 11.5 PDF (`utils/pdf_generator.py`)
| Fonction | Document |
|---|---|
| `generer_bulletin_pdf_eleve` | Bulletin trimestriel (2e cycle) |
| `generer_certificat_frequentation_pdf` | Certificat de fréquentation |
| `generer_proposition_passage_pdf` | Proposition de passage |
| `generer_bulletin_mensuel_pdf_eleve` | Bulletin mensuel (1er cycle) |
| `generer_certificat_transfert_pdf` | Certificat de transfert |
| `generer_fiche_suivi_second_cycle_pdf` | Fiche de suivi 2e cycle |
| `generer_emploi_temps_pdf` | Emploi du temps |
| `generer_liste_eleves_pdf` | Liste des élèves (portrait) |
| `generer_carte_scolaire_pdf` | Carte scolaire individuelle |
| `generer_planche_cartes_classe_pdf` | Planche A4 de 8 cartes |

**Polices** : Amiri (arabe) enregistrée une fois au chargement du module.

### 11.6 QR code (`utils/qr_code.py`)
- `generer_qr_code_base64(texte)` : retourne `data:image/png;base64,...`.

### 11.7 Cartes (`utils/cartes.py`)
- `couleur_valide(valeur, defaut)` : valide `#RRGGBB`.
- `fond_valide(valeur, defaut)` : valide nom de fichier simple.

### 11.8 Dates (`utils/dates.py`)
- `MOIS_ORDRE_SCOLAIRE` : 12 mois (Sept → Août).
- `get_mois_annee_scolaire(annee_scolaire_obj)` : liste des 12 mois avec leur année réelle.
- `get_annee_reelle_mois(mois, annee)` : année réelle pour un mois.

---

## 12. Formulaires

### 12.1 `forms.py`
- `AnneeScolaireForm`, `ClasseForm`, `EleveForm`, `MatiereForm`.
- `InscriptionForm`, `PaiementForm`, `EvaluationForm`, `NoteForm`.
- `EcoleInfoForm`, `CertificatTransfertForm`.
- `DepenseForm`, `RecetteForm`, `PlageHoraireForm`.
- `MatiereClasseForm`, `FraisClasseAnneeForm`.

### 12.2 `lycee_forms.py`
- `MatiereLyceeForm`, `CoefficientLyceeForm`, `ClasseLyceeForm`.
- `EleveLyceeForm` (matricule saisi manuellement, verrouillé en modification).
- `InscriptionLyceeForm`, `NoteLyceeForm`, `SaisieNotesLyceeFilterForm`.
- `PaiementLyceeForm`, `PlageHoraireLyceeForm`, `MatiereClasseLyceeForm`.

---

## 13. Admin

### 13.1 `admin.py`
- `CategorieDepenseAdmin`, `DepenseAdmin`, `CategorieRecetteAdmin`, `RecetteAdmin`.
- `PlageHoraireAdmin`, `EmploiTempsAdmin`, `CreneauEmploiTempsAdmin`.
- `LicenceAdmin` (actions : activer, prolonger, réinitialiser l'empreinte).
- `CustomUserAdmin` (masque le compte `systeme`).
- `MatiereClasseAdmin`.

### 13.2 `lycee_admin.py`
- `MatiereLyceeAdmin`, `CoefficientLyceeAdmin`, `ClasseLyceeAdmin`, `EleveLyceeAdmin`, `InscriptionLyceeAdmin`, `NoteLyceeAdmin`, `ResultatTrimestreLyceeAdmin`, `DetailResultatLyceeAdmin`, `PaiementLyceeAdmin`, `PlageHoraireLyceeAdmin`, `EmploiTempsLyceeAdmin`, `CreneauEmploiTempsLyceeAdmin`, `MatiereClasseLyceeAdmin`.

---

## 14. Gestion des utilisateurs

### 14.1 Rôles prédéfinis (`views_utilisateurs.py`)
| Rôle | Description | Permissions |
|---|---|---|
| `directeur` | Accès complet | ALL |
| `censeur` | Notes, bulletins, emploi du temps | `view_note`, `add_note`, `change_note`, `view_emploitemps`, etc. |
| `secretaire` | Inscriptions, élèves, paiements | `add_eleve`, `add_inscription`, `add_paiement`, `view_paiement_global`, etc. |
| `comptable` | Gestion financière | `voir_comptabilite`, `gerer_depenses`, `gerer_recettes`, etc. |
| `enseignant` | Saisie des notes | `add_note`, `change_note`, `view_note`, `view_eleve`, `view_classe`. |
| `lecteur` | Consultation seule | `view_eleve`, `view_note`, `view_paiement`. |

### 14.2 Fonctions
- `est_administrateur(user)` : superuser ou groupe `directeur`.
- `synchroniser_permissions_role(role_key)` : aligne les permissions du groupe.
- `_attribuer_role(user, role_key)` : attribue un rôle.

### 14.3 Vues
- `utilisateur_list`, `utilisateur_create`, `utilisateur_update`, `utilisateur_delete`, `utilisateur_reset_password`, `utilisateur_toggle_active`.

---

## 15. Comptabilité

### 15.1 Modèles
- `Section` (TextChoices) : `1er`, `2e`, `lycee`, `commun`.
- `CategorieDepense`, `Depense` (+ `section`, `section_defaut`).
- `CategorieRecette`, `Recette` (+ `section`, `section_defaut`).
- Les paiements (`Paiement`, `PaiementLycee`) n'ont pas de colonne : section dérivée.

### 15.2 Service
- `services/comptabilite.py` : `etat_comptable()`, `detail_financier()`, `evolution_mensuelle()`.
- Invariant : `global == 1er + 2e + lycee + commun`.

### 15.3 Vues
- `depense_list`, `DepenseCreateView`, `DepenseUpdateView`, `DepenseDeleteView` (filtre `section`).
- `recette_list`, `RecetteCreateView`, `RecetteUpdateView`, `RecetteDeleteView` (filtre `section`).
- `comptabilite_dashboard` : sélecteur de section + tableau de répartition + global.
- `lycee_comptabilite_dashboard` : redirection vers `?section=lycee`.
- `rapports_comptables`, `rapport_pdf`, `rapport_csv`.

### 15.4 Permissions
- `voir_comptabilite`, `gerer_depenses`, `gerer_recettes`.

---

## 16. Emploi du temps

### 16.1 Plages horaires
- `PlageHoraire` (cycle, ordre, heures, libellé, pause).
- `PlageHoraireLycee` (lycée).

### 16.2 Emploi du temps
- `EmploiTemps` (classe + année scolaire).
- `CreneauEmploiTemps` (jour, plage, matière, salle).
- `EmploiTempsLycee`, `CreneauEmploiTempsLycee`.

### 16.3 Vues
- `plage_horaire_list`, `PlageHoraireCreateView`, etc.
- `emploi_temps_index`, `emploi_temps_gestion`, `emploi_temps_enregistrer_creneau`, `emploi_temps_reconduire`, `emploi_temps_pdf`, `emploi_temps_tous_pdf`.
- Équivalents lycée.

---

## 17. Cartes scolaires

### 17.1 Format
- Carte individuelle (85,6 mm × 54 mm).
- Planche A4 de 8 cartes (2×4).
- Personnalisation : couleur (`#RRGGBB`) et fond (nom de fichier).

### 17.2 Vues
- `carte_scolaire_preview`, `carte_scolaire_pdf`, `carte_scolaire_classe_pdf`.
- Équivalents lycée.

### 17.3 QR code
Contient : `"{prenom} {nom} - {matricule}"`.

---

## 18. Comptes et authentification

### 18.1 Création du compte support
- `creer_support.py` : crée `systeme` (superuser, staff) avec mot de passe en variable d'environnement.
- `SUPPORT_USERNAME = 'systeme'`.
- `has_module_permission` pour `LicenceAdmin` : seul `systeme` voit la licence.

### 18.2 Utilisateurs standards
- Créés par le directeur via `views_utilisateurs.py`.
- Permissions attribuées par rôle.
- Connexion via `/login/` (CustomLoginView).

---

## 19. Setup (assistant de première configuration)

### 19.1 Étapes
1. **`setup_step1`** : informations de l'école (nom, ministère, type, modes de paiement, logo).
2. **`setup_step2`** : création du compte administrateur (client) avec permissions limitées.
3. **`setup_step3`** : création de l'année scolaire initiale.
4. **`setup_finalise`** : marque `setup_complete = True` (POST).

### 19.2 Clé de setup
- `afficher_cle_setup_view` : affiche la clé (protégée).
- `verifier_cle_setup` : vérifie la clé (stricte après la première installation).

### 19.3 Redirection
- `SetupRedirectMiddleware` : redirige vers `/setup/` tant que `setup_complete = False`.

---

## 20. Middleware de licence

### 20.1 `LicenceMiddleware`
- Vérifie `licence.empreinte_valide` (empreinte de la machine).
- Vérifie `licence.est_valide` (essai non expiré ou payée).
- URLs exemptées : `/licence/`, `/login/`, `/logout/`, `/admin/`, `/static/`, `/media/`, `/setup/`.

### 20.2 Mode "essai"
- 30 jours à partir de la **première utilisation** (témoin).
- `date_effective()` : `max(aujourd'hui, dernière date vue)`.

### 20.3 Licence payée
- Deux systèmes : `mode='payee'` en base, ou clé signée Ed25519.
- `signature_obligatoire()` : active la vérification stricte via `GESTION_ECOLE_LICENCE_SIGNEE=1`.
- `cle_signee_valide()` : vérifie la clé installée et son expiration.

---

## 21. Configuration (settings.py)

### 21.1 Détection de l'environnement
- `IS_FROZEN` (PyInstaller) / `IS_PYINSTALLER`.
- `BASE_DIR` = `_MEIPASS` (packagé) ou racine du projet.
- `USER_DATA_DIR` = `~/.gestion_ecole_data/` (toujours).
- `DATABASE_PATH` = SQLite dans `USER_DATA_DIR` (packagé) ou projet (dev).

### 21.2 Fichiers
- `SECRET_KEY` : générée une fois et stockée dans `~/.gestion_ecole_data/.secret_key`.
- `STATIC_ROOT` = `BASE_DIR / 'staticfiles'`.
- `MEDIA_ROOT` = `USER_DATA_DIR / 'media'`.
- `LOGGING` : fichier rotatif dans `USER_DATA_DIR/logs/`.

### 21.3 Bases de données (prévu multi-écoles)
- SQLite par défaut.
- PostgreSQL si `DATABASE_URL` défini (Vercel).

### 21.4 Sécurité
- `ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']` (à adapter en prod).
- `CSRF_TRUSTED_ORIGINS` : localhost uniquement.
- `SESSION_COOKIE_AGE` : 7 jours.
- `DEBUG = not IS_FROZEN`.

### 21.5 Context processors
- `annee_encours`, `trimestres`, `cycle_courant`, `licence_context`, `alertes_configuration`, `ecole_info`, `stats_lycee_header`, `parametres_globaux`.

### 21.6 Middlewares
- Sécurité, WhiteNoise, Sessions, Common, CSRF, Auth, Messages, Clickjacking.
- `LicenceMiddleware`, `SetupRedirectMiddleware`, `ModuleAccessMiddleware`.

---

## 22. Fonctionnalités transverses

### 22.1 Recherche et filtres
- Chaque liste (élèves, paiements, notes, dépenses) a des filtres (classe, année, cycle, mois, recherche textuelle).
- Pagination (généralement 20-25 par page).

### 22.2 Actions POST sécurisées
- `matiere_classe_copier_annee`, `matiere_classe_copier_pour_classe`, `classe_lycee_dupliquer_annee`, `cycle1_calculer_moyennes`, `setup_finalise` : `@require_POST`.
- Formulaires CSRF dans les templates.

### 22.3 Cache
- `annee_encours` : 1h.
- `licence_context` : 5min.
- `alertes_configuration` : 5min.

### 22.4 Gestion des erreurs
- `views_erreurs.py` : `custom_404`, `custom_500`, `custom_403`.

### 22.5 Formatage
- `floatformat:0` pour les montants.
- `date:"d/m/Y"` pour les dates.
- `floatformat:2` pour les moyennes.
- `stringformat:"s"` / `stringformat:"d"` pour les IDs.

### 22.6 Impression
- Boutons "Imprimer" dans les pages de documents.
- CSS `@media print` pour masquer les boutons.

---

## 23. Extensions et évolutions prévues

### 23.1 Multi-écoles (multi-tenant)
- Créer un modèle `Ecole` (remplaçant `EcoleInfo.get_solo()`).
- Ajouter `ecole = ForeignKey(Ecole)` sur tous les modèles métier.
- Middleware pour identifier l'école courante (sous-domaine ou chemin).
- Manager personnalisé pour filtrer automatiquement.
- Adapter les licences (par école).

### 23.2 Vercel (hébergement en ligne)
- `DATABASE_URL` → PostgreSQL.
- Fichiers médias → stockage externe (S3 / Cloudinary).
- Wildcard `*.monapp.com` pour les sous-domaines.

### 23.3 Modules désactivables
- `activer_fondamental`, `activer_lycee` dans `EcoleInfo` (à ajouter).
- `ModuleAccessMiddleware` pour bloquer l'accès.

### 23.4 Notifications
- Possibilité d'envoyer des SMS/emails aux parents (à prévoir).

### 23.5 Sauvegarde
- Script de sauvegarde automatique de la base SQLite.

---

## 24. Règles métier clés (à ne pas oublier)

1. **Matricule** :
   - Fondamental : généré automatiquement (2 lettres nom + 2 lettres prénom + MM + AA), figé après création.
   - Lycée : saisi manuellement, unique, figé après création.

2. **Calcul des moyennes** :
   - 1er cycle : `note = composition` (sur 10).
   - 2e cycle : `(noteClasse + noteCompo × 2) / 3` (sur 20).
   - Lycée : identique au 2e cycle.
   - Arrondi scolaire `ROUND_HALF_UP`.
   - Matière sans note : ignorée (ni numérateur, ni dénominateur).

3. **Rangs** :
   - Ex æquo partagent le même rang (1, 2, 2, 4).
   - Tri déterministe par nom puis prénom.

4. **Modes de paiement** :
   - Inscription : `unique` (une fois dans le cursus) ou `annuel` (chaque année).
   - Scolarité : `mensuel` (9 versements), `trimestriel` (3), `tranches` (N), `annuel` (1), `unique` (1 cursus).
   - Répartition : somme toujours égale au total.

5. **Élève orienté** (lycée) : gratuit, aucun paiement.

6. **Frais historiques** : si `frais_inscription_historique = True`, les frais sont considérés payés.

7. **Licence** : empreinte machine + clé Ed25519, essai 30 jours avec témoin anti-recul d'horloge.

8. **Scolarité** : compteurs recalculés depuis les inscriptions (source de vérité).

9. **Redoublements** : calculés depuis les inscriptions (max 3 stockés).

10. **Tentatives 2e cycle** : 7ème (2 max), 8ème (2 max), 9ème (3 max).

11. **Comptabilité par section** :
    - Chaque dépense/recette appartient à UNE section (`1er`, `2e`, `lycee`, `commun`).
    - Section des paiements : dérivée de `inscription.classe.cycle` (ou `lycee`).
    - Invariant : `global == 1er + 2e + lycee + commun`.

12. **Résultats** : les moyennes/rangs sont stockés dans les tables `Resultat*` ;
    la façade `services/resultats.py` ne fait que les relire (pas de recalcul).

---

## 25. Sécurité (résumé)

| Aspect | Implémentation |
|---|---|
| Authentification | Django `auth` + `LoginRequiredMixin` |
| Permissions | Django permissions + rôles prédéfinis |
| CSRF | Activé par défaut, `{% csrf_token %}` dans les formulaires |
| XSS | Templates Django (auto-escape) + `escapeHtml` en JS |
| Traversée de répertoire | `cartes.py` + `serve_media` (commonpath) |
| Injection de fichiers | Validation des extensions + `nosniff` |
| Licence | Ed25519 + empreinte machine |
| Compte support | Caché dans l'admin, superuser uniquement |
| Mots de passe | Validateurs Django (min 8 caractères) |
| Actions POST | `@require_POST` sur les vues critiques |

---

## 26. Ce qui reste à faire (rappel de l'audit)

### ✅ Fait (refonte Plan 2 — 2026)
- Découpage de `models.py` et `views.py` en packages (`models/`, `views/`).
- Comptabilité multi-sections (`Section` + service + dashboard unifié).
- Résultats unifiés (compositions 1er cycle, trimestres 2e/lycée).
- Tests de non-régression + comptabilité + résultats (17 tests).
- Correction de la migration `0017` (installation neuve impossible).
- Correction du filtre année lycée (`int.isdigit`).

### 🟠 Priorité moyenne
- **Multi-écoles** : refonte majeure (voir section 23.1).
- **Vercel** : configuration PostgreSQL + stockage médias.
- **Modules désactivables** : ajouter `activer_fondamental` et `activer_lycee` dans `EcoleInfo`.
- **Cache** : améliorer les context processors.
- **Reclassement des mouvements comptables existants** (actuellement `commun`).
- **Rapports PDF/CSV** : ajouter le filtre par section.
- **Tests** : poursuivre sur arrondi, répartition, allocation, licence.

### 🟢 Priorité basse
- **`except:` nus** dans `pdf_generator.py` (images des cartes).
- **Doublons de fichiers** (`*_1.py`).
- **`max_length`** sur `Classe.nomClasse` et `Evaluation.nomEvaluation`.
- **Sémantique** : renommer `frais_unique_deja_paye`.
- **Nettoyage** : supprimer les `print` de debug.
- **Extraction en apps Django séparées** (`core`/`fondamental`/`lycee`) : optionnelle.

---

## 27. Résumé exécutif

Votre application `gestion_ecole` est **complète et fonctionnelle** pour une école unique. Elle couvre :

- **Gestion des élèves** (fondamental + lycée) avec matricules, photos, filiation.
- **Gestion des classes** (1ère → 9ème, 10ème → Terminale).
- **Gestion des matières** (avec noms arabes et coefficients).
- **Inscriptions** par année scolaire.
- **Paiements** avec 5 modes de scolarité et 2 modes d'inscription.
- **Notes** (mensuelles 1er cycle, trimestrielles 2e cycle et lycée).
- **Résultats unifiés** (compositions et trimestres, vue par section).
- **Bulletins** (PDF avec en-tête d'école, arabe optionnel).
- **Documents officiels** (certificats de fréquentation, de transfert, proposition de passage, fiche de suivi).
- **Cartes scolaires** (individuelles et planches de 8).
- **Emploi du temps** (plages horaires, créneaux, PDF).
- **Comptabilité** (dépenses, recettes, rapports PDF/CSV, **4 sections + global**).
- **Gestion des utilisateurs** (rôles prédéfinis, permissions).
- **Licence** (essai 30 jours, clé Ed25519, empreinte machine).
- **Assistant de configuration** initiale.
- **Multi-cycles** (1er / 2e / Lycée).
- **Compatible local (PyInstaller) et cloud (Vercel prévu)**.

Ce schéma vous servira de **référence** pour toute future évolution, notamment le passage au multi-écoles. Gardez-le précieusement : il décrit **l'intégralité** de la logique métier, des modèles, des vues et des règles à respecter, sans avoir besoin de copier le code source.
