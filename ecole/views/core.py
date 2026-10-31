"""Vues : core."""
from ._deps import *
from ._helpers import *


def serve_media(request, path):
    """
    Sert les fichiers MEDIA (logo école, photos, justificatifs).

    ✅ Nécessaire en mode packagé (DEBUG = False) car Django ne sert
    plus automatiquement les MEDIA.

    ✅ FIX sécurité :
    - connexion exigée (sauf logo de l'école, affiché sur la page de login)
    - contrôle de chemin par commonpath (l'ancien startswith laissait passer
      un dossier frère comme « media_evil »)
    - types non sûrs (html, svg...) forcés en téléchargement + nosniff
    """
    est_public = path.replace('\\', '/').startswith(_MEDIA_PUBLICS)
    if not est_public and not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    media_root = os.path.realpath(str(settings.MEDIA_ROOT))
    real_path = os.path.realpath(os.path.join(media_root, path))

    # Sécurité : empêcher la remontée de répertoire (y compris via liens)
    try:
        dans_media = os.path.commonpath([real_path, media_root]) == media_root
    except ValueError:  # ex. lecteurs différents sous Windows
        dans_media = False
    if not dans_media or real_path == media_root:
        raise Http404("Accès refusé")

    if not os.path.isfile(real_path):
        raise Http404("Fichier introuvable")

    content_type, _ = mimetypes.guess_type(real_path)
    if content_type is None:
        content_type = 'application/octet-stream'

    response = FileResponse(open(real_path, 'rb'), content_type=content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    est_image_sure = content_type.startswith('image/') and content_type != 'image/svg+xml'
    if not (est_image_sure or content_type == 'application/pdf'):
        response['Content-Disposition'] = (
            f'attachment; filename="{os.path.basename(real_path)}"'
        )
    return response


@login_required
def ouvrir_dossier_donnees(request):
    """Ouvre le dossier des données dans l'explorateur Windows."""
    import os
    
    dossier = os.path.join(os.path.expanduser("~"), ".gestion_ecole_data")
    
    try:
        if sys.platform == 'win32':
            os.startfile(dossier)
        elif sys.platform == 'darwin':  # macOS
            subprocess.Popen(['open', dossier])
        else:  # Linux
            subprocess.Popen(['xdg-open', dossier])
        
        messages.success(request, f"Dossier ouvert : {dossier}")
    except Exception as e:
        messages.error(request, f"Impossible d'ouvrir le dossier : {e}")
    
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


class CustomLoginView(LoginView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ecole'] = EcoleInfo.get_solo()
        return context


@login_required
def dashboard(request):
    peut_voir_paiements_globaux = request.user.has_perm('ecole.view_paiement_global')
    annee_param = request.GET.get('annee')
    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')

    if annee_param:
        annee_selectionnee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_param)
    else:
        annee_selectionnee = annees_scolaires.first()

    stats_eleves = {'1er': 0, '2e': 0, 'total': 0}
    stats_classes = {'1er': 0, '2e': 0, 'total': 0}
    stats_paiements = {'1er': 0, '2e': 0, 'total': 0}
    total_inscriptions = 0
    inscriptions_recentes = Inscription.objects.none()
    paiements_recents = None
    classes_annee = Classe.objects.none()

    if annee_selectionnee:
        inscriptions_qs = Inscription.objects.filter(
            anneeScolaire=annee_selectionnee
        ).select_related('classe')

        e1 = inscriptions_qs.filter(classe__cycle='1er').values('eleve').distinct().count()
        e2 = inscriptions_qs.filter(classe__cycle='2e').values('eleve').distinct().count()
        stats_eleves = {'1er': e1, '2e': e2, 'total': e1 + e2}

        c1 = inscriptions_qs.filter(classe__cycle='1er').values('classe').distinct().count()
        c2 = inscriptions_qs.filter(classe__cycle='2e').values('classe').distinct().count()
        stats_classes = {'1er': c1, '2e': c2, 'total': c1 + c2}

        total_inscriptions = inscriptions_qs.count()
        inscriptions_recentes = inscriptions_qs.select_related('eleve', 'classe').order_by('-idInscription')[:5]

        classes_annee = Classe.objects.filter(
            idClasse__in=inscriptions_qs.values_list('classe_id', flat=True).distinct()
        ).order_by('nomClasse')

        if peut_voir_paiements_globaux:
            paiements_qs = Paiement.objects.filter(
                inscription__anneeScolaire=annee_selectionnee
            ).select_related('inscription__classe')

            t1 = paiements_qs.filter(inscription__classe__cycle='1er').aggregate(Sum('montant'))['montant__sum'] or 0
            t2 = paiements_qs.filter(inscription__classe__cycle='2e').aggregate(Sum('montant'))['montant__sum'] or 0
            stats_paiements = {'1er': t1, '2e': t2, 'total': t1 + t2}

            paiements_recents = paiements_qs.select_related('inscription__eleve').order_by('-date_paiement')[:5]

    context = {
        'stats_eleves': stats_eleves,
        'stats_classes': stats_classes,
        'stats_paiements': stats_paiements,
        'total_inscriptions': total_inscriptions,
        'inscriptions_recentes': inscriptions_recentes,
        'paiements_recents': paiements_recents,
        'peut_voir_paiements_globaux': peut_voir_paiements_globaux,
        'annees_scolaires': annees_scolaires,
        'annee_selectionnee': annee_selectionnee,
        'annee_encours': annee_selectionnee.anneeScolaire if annee_selectionnee else None,
        'trimestres': dict(Evaluation.TRIMESTRE),
        'classes_annee': classes_annee,
    }
    return render(request, 'ecole/dashboard.html', context)


@login_required
@permission_required('ecole.view_paiement_global', raise_exception=True)
def api_stats_globales(request):
    eleves_par_classe = Inscription.objects.values('classe__nomClasse').annotate(total=Count('eleve'))
    moyennes_par_matiere = Note.objects.values('matiere__nomMatiere').annotate(moyenne=Avg('note'))
    paiements_par_mois = Paiement.objects.values('mois', 'annee_paiement').annotate(
        total=Sum('montant')
    ).order_by('annee_paiement', 'mois')

    return JsonResponse({
        'eleves_par_classe': list(eleves_par_classe),
        'moyennes_par_matiere': list(moyennes_par_matiere),
        'paiements_par_mois': list(paiements_par_mois),
    })


@login_required
@permission_required('ecole.change_ecoleinfo', raise_exception=True)
def parametres_ecole(request):
    ecole = EcoleInfo.get_solo()
    if request.method == 'POST':
        form = EcoleInfoForm(request.POST, request.FILES, instance=ecole)
        if form.is_valid():
            form.save()
            messages.success(request, "Informations mises à jour avec succès!")
            return redirect('parametres_ecole')
    else:
        form = EcoleInfoForm(instance=ecole)
    return render(request, 'ecole/parametres/ecole.html', {'form': form, 'ecole': ecole})


def licence_expiree(request):
    """Page affichée quand l'essai est terminé."""
    from ..models import Licence, EcoleInfo

    licence = Licence.get_licence()
    ecole = EcoleInfo.get_solo()

    context = {
        'licence': licence,
        'ecole': ecole,
        'jours_depuis_expiration': abs(licence.jours_restants_essai or 0),
    }
    return render(request, 'ecole/licence/expiree.html', context)


@login_required
def licence_activer(request):
    """
    Activation d'une licence signée : le client communique son CODE MACHINE au
    vendeur, reçoit une clé, la colle ici. Réservé au directeur.
    """
    from ..utils.licence import get_code_machine
    from ..utils.licence_signee import installer_cle, cle_signee_valide

    if not request.user.has_perm('ecole.change_ecoleinfo'):
        messages.error(request, "Action réservée au directeur.")
        return redirect('dashboard')

    if request.method == 'POST':
        ok, resultat = installer_cle(request.POST.get('cle', ''))
        if ok:
            messages.success(
                request,
                f"Licence activée pour « {resultat['client']} »."
                + (f" Valable jusqu'au {resultat['expire'].strftime('%d/%m/%Y')}."
                   if resultat['expire'] else " Licence illimitée.")
            )
        else:
            messages.error(request, resultat)
        return redirect('licence_activer')

    return render(request, 'ecole/licence/activer.html', {
        'code_machine': get_code_machine(),
        'licence_signee': cle_signee_valide(),
    })


def licence_machine_invalide(request):
    """Page affichée quand l'empreinte machine ne correspond pas."""
    from ..models import Licence
    from ..utils.licence import get_machine_id_lisible

    licence = Licence.get_licence()

    context = {
        'licence': licence,
        'machine_actuelle': get_machine_id_lisible(),
    }
    return render(request, 'ecole/licence/machine_invalide.html', context)


@login_required
def licence_info(request):
    """Page d'information sur la licence (visible par le directeur)."""
    from ..models import Licence

    licence = Licence.get_licence()

    context = {
        'licence': licence,
    }
    return render(request, 'ecole/licence/info.html', context)


def setup_step1(request):
    """Étape 1 : Informations de l'école."""
    ecole = EcoleInfo.get_solo()

    # ✅ VÉRIFICATION 1 : Setup déjà complété
    if ecole.setup_complete:
        messages.warning(
            request,
            "La configuration a déjà été effectuée. "
            "Vous ne pouvez plus y accéder."
        )
        return redirect('login')

    # ✅ VÉRIFICATION 2 : Clé de setup valide
    if request.method == 'GET':
        cle_url = request.GET.get('key')
        if cle_url:
            request.session['setup_key'] = cle_url

    cle = request.POST.get('key') or request.session.get('setup_key')

    from ..utils.setup import get_cle_setup
    cle_attendue = get_cle_setup()

    if cle_attendue and cle != cle_attendue:
        messages.error(
            request,
            "Accès refusé. Clé de configuration invalide ou manquante."
        )
        return redirect('login')

    # ✅ TRAITEMENT DU POST
    if request.method == 'POST':
        ecole.nom = request.POST.get('nom', '').strip()
        ecole.sigle = request.POST.get('sigle', '').strip()
        ecole.ministere = request.POST.get('ministere', '').strip() or "MINISTERE DE L'EDUCATION NATIONALE"
        ecole.circonscription = request.POST.get('circonscription', '').strip()
        ecole.academie = request.POST.get('academie', '').strip()
        ecole.republique = request.POST.get('republique', '').strip() or "REPUBLIQUE DU MALI"
        ecole.devise = request.POST.get('devise', '').strip() or "Un peuple - Un but - Une foi"
        ecole.adresse = request.POST.get('adresse', '').strip()
        ecole.ville = request.POST.get('ville', '').strip() or "Bamako"
        ecole.pays = request.POST.get('pays', '').strip() or "Mali"
        ecole.telephone = request.POST.get('telephone', '').strip()
        ecole.email = request.POST.get('email', '').strip()
        ecole.nom_directeur = request.POST.get('nom_directeur', '').strip()

        # Type d'école
        type_ecole = request.POST.get('type_ecole', '').strip()
        if type_ecole in ('classique', 'franco_arabe'):
            ecole.type_ecole = type_ecole

        # Modes de paiement
        mode_inscription = request.POST.get('mode_frais_inscription', 'annuel').strip()
        ecole.mode_frais_inscription = (
            mode_inscription if mode_inscription in ('unique', 'annuel') else 'annuel'
        )

        mode_scolarite = request.POST.get('mode_frais_scolarite', 'mensuel').strip()
        ecole.mode_frais_scolarite = (
            mode_scolarite
            if mode_scolarite in ('mensuel', 'trimestriel', 'tranches', 'annuel', 'unique')
            else 'mensuel'
        )

        if ecole.mode_frais_scolarite == 'tranches':
            try:
                nb = int(request.POST.get('nombre_tranches', '4'))
                ecole.nombre_tranches = max(2, min(12, nb))
            except (ValueError, TypeError):
                ecole.nombre_tranches = 4

        # Logo
        if 'logo' in request.FILES:
            ecole.logo = request.FILES['logo']

        ecole.save()

        messages.success(request, "✅ Étape 1 terminée avec succès !")
        return redirect('setup_step2')

    context = {
        'etape': 1,
        'total_etapes': 3,
        'ecole': ecole,
        'cle': cle,
    }
    return render(request, 'ecole/setup/step1.html', context)


def setup_step2(request):
    """Étape 2 : Création du compte administrateur (client)."""
    ecole = EcoleInfo.get_solo()

    if ecole.setup_complete:
        messages.warning(request, "Configuration déjà effectuée.")
        return redirect('login')

    cle = request.POST.get('key') or request.session.get('setup_key')

    from ..utils.setup import get_cle_setup
    cle_attendue = get_cle_setup()

    if not cle_attendue or cle != cle_attendue:
        messages.error(request, "Accès refusé. Clé invalide.")
        return redirect('setup_cle')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        errors = []

        if not username:
            errors.append("Le nom d'utilisateur est obligatoire.")
        elif username == 'systeme':
            errors.append("Ce nom d'utilisateur est réservé. Choisissez-en un autre.")
        elif User.objects.filter(username=username).exists():
            errors.append(f"L'utilisateur '{username}' existe déjà.")

        if len(password) < 8:
            errors.append("Le mot de passe doit faire au moins 8 caractères.")
        if password != password_confirm:
            errors.append("Les deux mots de passe ne correspondent pas.")

        if errors:
            context = {
                'etape': 2,
                'total_etapes': 3,
                'ecole': ecole,
                'errors': errors,
                'username': username,
                'email': email,
                'cle': cle,
            }
            return render(request, 'ecole/setup/step2.html', context)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )
        user.is_staff = True
        user.is_superuser = False
        user.save()

        # Attribution des permissions
        permissions_autorisees = [
            'add_classe', 'change_classe', 'delete_classe', 'view_classe',
            'add_eleve', 'change_eleve', 'delete_eleve', 'view_eleve',
            'add_inscription', 'change_inscription', 'delete_inscription', 'view_inscription',
            'add_paiement', 'change_paiement', 'delete_paiement', 'view_paiement',
            'view_paiement_global',
            'add_matiere', 'change_matiere', 'delete_matiere', 'view_matiere',
            'add_note', 'change_note', 'delete_note', 'view_note',
            'add_resultattrimestre', 'change_resultattrimestre',
            'delete_resultattrimestre', 'view_resultattrimestre',
            'add_detailresultat', 'change_detailresultat',
            'delete_detailresultat', 'view_detailresultat',
            'add_anneescolaire', 'change_anneescolaire',
            'delete_anneescolaire', 'view_anneescolaire',
            'add_evaluation', 'change_evaluation',
            'delete_evaluation', 'view_evaluation',
            'add_categoriedepense', 'change_categoriedepense',
            'delete_categoriedepense', 'view_categoriedepense',
            'add_depense', 'change_depense', 'delete_depense', 'view_depense',
            'add_categorierecette', 'change_categorierecette',
            'delete_categorierecette', 'view_categorierecette',
            'add_recette', 'change_recette', 'delete_recette', 'view_recette',
            'voir_comptabilite', 'gerer_depenses', 'gerer_recettes',
            'add_plagehoraire', 'change_plagehoraire',
            'delete_plagehoraire', 'view_plagehoraire',
            'add_emploidutemps', 'change_emploidutemps',
            'delete_emploidutemps', 'view_emploidutemps',
            'add_creneauemploidutemps', 'change_creneauemploidutemps',
            'delete_creneauemploidutemps', 'view_creneauemploidutemps',
            'change_ecoleinfo', 'view_ecoleinfo',
        ]

        for codename in permissions_autorisees:
            try:
                perm = Permission.objects.get(codename=codename)
                user.user_permissions.add(perm)
            except Permission.DoesNotExist:
                pass

        messages.success(request, "✅ Compte administrateur créé !")
        return redirect('setup_step3')

    context = {
        'etape': 2,
        'total_etapes': 3,
        'ecole': ecole,
        'cle': cle,
    }
    return render(request, 'ecole/setup/step2.html', context)


def setup_step3(request):
    """Étape 3 : Création de l'année scolaire et finalisation."""
    ecole = EcoleInfo.get_solo()

    if ecole.setup_complete:
        messages.warning(request, "Configuration déjà effectuée.")
        return redirect('login')

    cle = request.POST.get('key') or request.session.get('setup_key')

    from ..utils.setup import get_cle_setup
    cle_attendue = get_cle_setup()

    if not cle_attendue or cle != cle_attendue:
        messages.error(request, "Accès refusé. Clé invalide.")
        return redirect('setup_cle')

    if request.method == 'POST':
        annee_libelle = request.POST.get('annee_scolaire', '').strip()
        date_debut = request.POST.get('date_debut', '')
        date_fin = request.POST.get('date_fin', '')

        if not annee_libelle:
            messages.error(
                request,
                "L'année scolaire est obligatoire pour finaliser la configuration."
            )
            return render(request, 'ecole/setup/step3.html', {
                'etape': 3, 'total_etapes': 3, 'ecole': ecole,
                'annee_defaut': _annee_defaut(),
                'cle': cle,
            })

        AnneeScolaire.objects.get_or_create(
            anneeScolaire=annee_libelle,
            defaults={
                'date_debut': date_debut or None,
                'date_fin': date_fin or None,
            }
        )

        ecole.setup_complete = True
        ecole.save()

        if 'setup_key' in request.session:
            del request.session['setup_key']

        messages.success(
            request,
            "🎉 Configuration terminée ! Bienvenue dans Mali Kalanso."
        )
        return redirect('login')

    context = {
        'etape': 3,
        'total_etapes': 3,
        'ecole': ecole,
        'annee_defaut': _annee_defaut(),
        'cle': cle,
    }
    return render(request, 'ecole/setup/step3.html', context)


@login_required
@require_POST
def setup_finalise(request):
    """Page de confirmation finale (protégée par POST)."""
    ecole = EcoleInfo.get_solo()
    if ecole.setup_complete:
        messages.warning(request, "Configuration déjà effectuée.")
        return redirect('login')

    if not verifier_cle_setup(request):
        messages.error(request, "Accès refusé. Clé de configuration invalide ou manquante.")
        return redirect('login')
        
    ecole.setup_complete = True
    ecole.save()

    messages.success(request, "🎉 Configuration terminée avec succès !")
    return render(request, 'ecole/setup/finalise.html', {'ecole': ecole})


def afficher_cle_setup_view(request):
    """Affiche la clé de setup uniquement si l'école n'est pas encore configurée."""
    ecole = EcoleInfo.get_solo()
    
    if ecole.setup_complete:
        messages.info(request, "L'application est déjà configurée.")
        return redirect('login')
    
    # ✅ FIX : Si une école existe et a déjà un nom, on exige d'être connecté pour voir la clé
    if ecole.nom and not request.user.is_authenticated:
        messages.error(request, "Vous devez être connecté pour accéder à cette page.")
        return redirect('login')

    cle = get_cle_setup()
    if not cle:
        from ..utils.setup import generer_cle_setup
        cle = generer_cle_setup()
    
    context = {
        'cle': cle,
        'ecole': ecole,
    }
    return render(request, 'ecole/setup/cle_setup.html', context)


