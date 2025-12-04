# Architecture GUI Refactorée

## Vue d'ensemble

Le fichier `gui.py` a été refactorisé pour améliorer la maintenabilité en divisant la classe `MainWindow` monolithique (1837 lignes) en plusieurs modules organisés dans le dossier `gui/`.

## Structure des fichiers

```
tidal_dl_ng/
├── gui/
│   ├── __init__.py              # Point d'entrée du module GUI
│   ├── activate.py              # Fonction d'activation de l'application GUI
│   ├── main_window.py           # Classe MainWindow principale
│   ├── initialization.py        # Mixin: Initialisation des composants UI
│   ├── tidal_session.py         # Mixin: Gestion de la session Tidal
│   ├── signals.py               # Mixin: Gestion des signaux Qt
│   ├── progress.py              # Mixin: Barres de progression
│   ├── ui_helpers.py            # Mixin: Helpers UI (spinners, logs, statusbar)
│   ├── track_extras.py          # Mixin: Cache et gestion des extras de tracks
│   ├── updates.py               # Mixin: Vérification des mises à jour
│   ├── downloads.py             # Mixin: Gestion des téléchargements
│   ├── trees_results.py         # Mixin: Gestion des arbres et résultats
│   ├── context_menus.py         # Mixin: Menus contextuels et actions
│   ├── history.py               # Mixin: Historique et prévention des doublons
│   ├── covers.py                # Manager de couvertures
│   ├── playlist.py              # Manager de playlists
│   ├── queue.py                 # Manager de queue
│   └── search.py                # Manager de recherche
├── gui.py                       # Point de compatibilité (redirige vers gui/)
```

## Mixins et Responsabilités

### 1. InitializationMixin (`initialization.py`)

Responsable de l'initialisation de tous les composants de l'interface utilisateur.

**Méthodes:**

- `_init_gui()` - Configuration de la fenêtre principale
- `_init_threads()` - Initialisation du pool de threads
- `_init_dl()` - Configuration de l'objet Download
- `_init_progressbar()` - Initialisation des barres de progression
- `_init_info()` - Configuration de l'image de couverture par défaut
- `_init_tree_results()` - Configuration de l'arbre des résultats
- `_init_tree_results_model()` - Configuration du modèle de l'arbre
- `_init_tree_queue()` - Configuration de la queue de téléchargement
- `_init_tree_lists()` - Configuration de l'arbre des listes utilisateur
- `_init_menu_actions()` - Ajout d'actions de menu personnalisées
- `_populate_quality()` - Remplissage des options de qualité
- `_populate_search_types()` - Remplissage des types de recherche

### 2. TidalSessionMixin (`tidal_session.py`)

Gère l'authentification et la session Tidal.

**Méthodes:**

- `init_tidal()` - Initialisation de la session Tidal avec gestion du login
- `on_logout()` - Déconnexion de Tidal

### 3. SignalsMixin (`signals.py`)

Configure toutes les connexions de signaux Qt.

**Méthodes:**

- `_init_signals()` - Connexion de tous les signaux aux slots
- `on_result_item_clicked()` - Gestion du clic sur un élément de résultat
- `on_quality_set_audio()` - Configuration de la qualité audio
- `on_quality_set_video()` - Configuration de la qualité vidéo

### 4. ProgressMixin (`progress.py`)

Gère les barres de progression.

**Méthodes:**

- `on_progress_reset()` - Réinitialisation des barres de progression
- `on_progress_list()` - Mise à jour de la barre de progression de liste
- `on_progress_item()` - Mise à jour de la barre de progression d'élément
- `on_progress_item_name()` - Définition du nom d'élément
- `on_progress_list_name()` - Définition du nom de liste

### 5. UIHelpersMixin (`ui_helpers.py`)

Fournit des fonctions utilitaires pour l'interface utilisateur.

**Méthodes:**

- `on_spinner_start()` - Démarrage d'un spinner de chargement
- `on_spinner_stop()` - Arrêt de tous les spinners
- `on_statusbar_message()` - Affichage d'un message dans la barre d'état
- `_log_output()` - Redirection des logs vers l'interface
- `button_reload_status()` - Mise à jour du statut du bouton de rechargement

### 6. TrackExtrasMixin (`track_extras.py`)

Gère le cache et la récupération des informations supplémentaires des tracks.

**Méthodes:**

- `get_track_extras()` - Récupération des extras (avec cache)
- `_on_invoke_callback()` - Invocation du callback dans le thread principal
- `_decorate_extras()` - Ajout de champs formatés aux extras
- `preload_covers_for_playlist()` - Préchargement des couvertures

### 7. UpdatesMixin (`updates.py`)

Gère la vérification des mises à jour de l'application.

**Méthodes:**

- `on_update_check()` - Vérification des mises à jour disponibles
- `on_version()` - Affichage du dialogue de version

### 8. DownloadsMixin (`downloads.py`)

Gère la queue de téléchargement et les opérations de téléchargement.

**Méthodes:**

- `on_download_results()` - Téléchargement des résultats sélectionnés
- `queue_download_media()` - Ajout d'un élément à la queue
- `watcher_queue_download()` - Surveillance de la queue
- `on_queue_download()` - Exécution d'un téléchargement
- `download()` - Téléchargement d'un élément média
- Méthodes de gestion de statut: `on_queue_download_item_downloading()`, etc.

### 9. TreesResultsMixin (`trees_results.py`)

Gère les arbres de vue et l'affichage des résultats.

**Méthodes:**

- `handle_filter_activated()` - Gestion des filtres d'en-tête
- `populate_tree_results()` - Remplissage de l'arbre des résultats
- `populate_tree_result_child()` - Création d'un élément enfant
- `on_tr_results_expanded()` - Gestion de l'expansion des résultats
- `tr_results_expanded()` - Chargement des enfants d'un élément
- `list_items_show_result()` - Affichage des éléments d'une liste
- `tidal_user_lists()` - Récupération des listes utilisateur
- `on_populate_tree_lists()` - Remplissage de l'arbre des listes
- `on_track_hover_confirmed()` - Gestion du survol d'un track
- `on_track_hover_left()` - Gestion de la sortie du survol

### 10. ContextMenusMixin (`context_menus.py`)

Gère les menus contextuels et leurs actions.

**Méthodes:**

- `menu_context_tree_results()` - Menu contextuel pour les résultats
- `menu_context_queue_download()` - Menu contextuel pour la queue
- `on_copy_url_share()` - Copie de l'URL de partage
- `on_download_album_from_track()` - Téléchargement de l'album d'un track
- `on_download_all_albums_from_playlist()` - Téléchargement de tous les albums
- `_extract_album_ids_from_tracks()` - Extraction des IDs d'albums
- `_load_albums_with_rate_limiting()` - Chargement avec limitation de débit
- `on_search_in_app()` - Recherche dans l'application
- `on_search_in_browser()` - Ouverture de recherche dans le navigateur

### 11. HistoryMixin (`history.py`)

Gère l'historique des téléchargements et la prévention des doublons.

**Méthodes:**

- `on_view_history()` - Affichage du dialogue d'historique
- `on_toggle_duplicate_prevention()` - Activation/désactivation de la prévention
- `on_mark_track_as_downloaded()` - Marquer un track comme téléchargé
- `on_mark_track_as_not_downloaded()` - Retirer le marquage
- `_update_downloaded_column()` - Mise à jour de la colonne UI
- `on_preferences()` - Ouverture du dialogue de préférences
- `on_settings_save()` - Sauvegarde des paramètres

## Classe MainWindow

La classe `MainWindow` hérite de tous les mixins et de `QtWidgets.QMainWindow` + `Ui_MainWindow`:

```python
class MainWindow(
    QtWidgets.QMainWindow,
    Ui_MainWindow,
    InitializationMixin,
    TidalSessionMixin,
    SignalsMixin,
    ProgressMixin,
    UIHelpersMixin,
    TrackExtrasMixin,
    UpdatesMixin,
    DownloadsMixin,
    TreesResultsMixin,
    ContextMenusMixin,
    HistoryMixin,
):
    ...
```

## Compatibilité

Le fichier `gui.py` original est maintenu comme point de compatibilité :

- Redirige les imports vers `tidal_dl_ng.gui`
- Conserve les directives de compilation nuitka
- Permet une migration progressive

## Avantages de cette architecture

1. **Maintenabilité** : Chaque mixin a une responsabilité claire et limitée
2. **Lisibilité** : Fichiers plus petits et focalisés (100-300 lignes vs 1837)
3. **Testabilité** : Les mixins peuvent être testés individuellement
4. **Extensibilité** : Facile d'ajouter de nouvelles fonctionnalités
5. **Réutilisabilité** : Les mixins peuvent être réutilisés si nécessaire
6. **Organisation** : Structure logique par fonctionnalité

## Migration

Pour utiliser la nouvelle structure :

```python
# Ancienne méthode (toujours supportée)
from tidal_dl_ng.gui import gui_activate

# Nouvelle méthode recommandée
from tidal_dl_ng.gui import MainWindow
from tidal_dl_ng.gui.activate import gui_activate
```

## Notes

- Les avertissements IDE sur les "unresolved attributes" dans les mixins sont normaux
- Les mixins accèdent à `self` qui sera fourni par `MainWindow` via l'héritage multiple
- L'ordre des mixins dans l'héritage est important pour la résolution de méthode (MRO)
