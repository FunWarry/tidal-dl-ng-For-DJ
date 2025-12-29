# Gestionnaire d'Appartenance aux Playlists (Playlist Membership Manager)

## Vue d'ensemble architecturale

### Problème utilisateur
L'application agit actuellement comme un silo de téléchargement. Pour organiser sa musique (ajouter à une playlist), l'utilisateur doit quitter l'app, ouvrir le client officiel Tidal, chercher à nouveau, puis agir. Ceci rompt le flux d'expérience.

### Solution proposée
Transformer chaque vue de résultats (Album, Recherche, Playlist) en tableau interactif avec :
- Une colonne dédiée "Playlists"
- Indicateur visuel instantané de l'appartenance
- Gestion d'ajout/retrait sans friction

---

## 1. Stratégie de Pré-chargement (Eager Loading & Caching)

### 1.1 Objectif de performance
Éliminer toute latence au clic. L'utilisateur accepte d'attendre le spinner au rechargement de la vue, mais pas l'ouverture du dialogue.

### 1.2 Architecture du Worker

```
Event: modelReset / layoutChanged (Main Table)
    ↓
Déclenche PlaylistContextLoader (QRunnable)
    ↓
Thread Pool Execution:
    ├─ Fetch User Playlists (GET /users/{userId}/playlists)
    │  └─ Pagination gérée (limit=50 par défaut)
    │  └─ Filtre des playlists éditables
    ├─ Parallèle : Fetch Playlist Contents
    │  ├─ Pour chaque playlist : GET /playlists/{id}/items?offset=0&limit=300
    │  └─ Accumule les Track IDs dans Set pour O(1) lookup
    └─ Spinlock/Event synchronisation
         ↓
    Construit: Cache = Dict[TrackID, Set[PlaylistID]]
         ↓
    Émet Signal: playlistCacheReady(cache_dict)
         ↓
    Tableau met à jour Delegate → Spinner OFF, Bouton ON
```

### 1.3 Structure de données

```python
# Cache structure
PlaylistCache = Dict[str, Set[str]]
# Exemple:
# {
#   "track_uuid_1": {"playlist_id_1", "playlist_id_2"},
#   "track_uuid_2": {"playlist_id_3"},
# }

# Thread-safe wrapper
class ThreadSafePlaylistCache:
    _lock: threading.RLock
    _data: Dict[str, Set[str]]
    _metadata: Dict[str, PlaylistMetadata]

    def get(self, track_id: str) -> Set[str]:
        """O(1) lookup with thread safety"""

    def update_track(self, track_id: str, playlist_ids: Set[str]):
        """Atomic update"""
```

### 1.4 Gestion d'erreurs et interruption

- **Interruptibilité** : Signal `abort_requested` pendant le chargement
- **Fail-silent** : Les erreurs réseau n'affichent pas de popup
- **Timeout** : Limite de 30s par playlistId
- **Limite de taux** : Max 5 requêtes parallèles (QThreadPool.maxThreadCount() = 5)

---

## 2. Interface - Colonne "Playlists" (Delegate & États)

### 2.1 Machine à états visuels

```
┌─────────────────────────────────────────────────────────┐
│ État 1: PENDING (Initial)                               │
├─────────────────────────────────────────────────────────┤
│ Trigger: Cache not ready for this track                 │
│ Visual: Spinner animé (SVG/QMovie), désactivé           │
│ Interaction: Désactivée (curseur "wait")                │
│ Durée: 0-5 secondes max                                 │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ État 2: READY (Normal)                                  │
├─────────────────────────────────────────────────────────┤
│ Trigger: Cache ready pour ce track                      │
│ Visual: Flat Button "📋 Playlists", gris neutre        │
│ Interaction: Cliquable (curseur "pointer")              │
│ Action: Ouvre PlaylistManagerDialog                     │
└─────────────────────────────────────────────────────────┘
                    ↙ (erreur lors du clic)
┌─────────────────────────────────────────────────────────┐
│ État 3: ERROR (Optionnel)                               │
├─────────────────────────────────────────────────────────┤
│ Trigger: Préchargement échoué (API down)                │
│ Visual: Icône d'avertissement ⚠️ grise                   │
│ Interaction: Désactivée avec tooltip                    │
│ Durée: Persistant jusqu'à reload                        │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Intégration QStyledItemDelegate

```
QTableView/QTreeView ModelReset
    ↓
playlistColumnDelegate.setModelData()
    ├─ row = model_index.row()
    ├─ track_id = model.data(row, TrackIdRole)
    ├─ state = cache.get_state(track_id) → [PENDING|READY|ERROR]
    └─ paint() selon state
        ├─ PENDING: drawSpinner()
        ├─ READY: drawButton()
        └─ ERROR: drawWarningIcon()
```

---

## 3. Fenêtre Modale : PlaylistManagerDialog

### 3.1 Design & Layout

```
╔════════════════════════════════════════════════════════════╗
║ Gérer les playlists pour: [TRACK_TITLE]                   ║ ← QLabel
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  ☐ Favorites                                       (16)    ║ ← QCheckBox + QLabel
║  ☐ Night Vibes                                     (42)    ║
║  ☐ Workout Mix                                     (103)   ║
║  ☐ Découvertes semaine                             (27)    ║
║                                                            ║
║  [Scroll Area: QScrollArea]                              ║
║                                                            ║
╠════════════════════════════════════════════════════════════╣
║                                       [Fermer]             ║ ← QPushButton
╚════════════════════════════════════════════════════════════╝
```

### 3.2 Composants

```python
class PlaylistManagerDialog(QDialog):
    """Dialogue de gestion des appartenance aux playlists."""

    # Signals
    playlist_added: QtCore.Signal = QtCore.Signal(str, str)  # track_id, playlist_id
    playlist_removed: QtCore.Signal = QtCore.Signal(str, str)

    def __init__(self,
                 track: Track,
                 cache: ThreadSafePlaylistCache,
                 tidal_session: Session,
                 parent: QWidget):
        """Initialisation du dialogue.

        Args:
            track: La piste courante
            cache: Le cache pré-chargé
            tidal_session: Session Tidal pour les appels API
            parent: Widget parent
        """

    def populate_playlists(self) -> None:
        """Remplit la liste des playlists depuis le cache.

        - Tri alphabétique
        - Récupère l'état d'appartenance du cache
        - Crée les checkboxes
        """

    def on_playlist_toggled(self, checkbox: QCheckBox,
                           playlist_id: str,
                           is_checked: bool) -> None:
        """Gère le changement d'état d'une checkbox.

        Flux:
        1. Désactiver checkbox + afficher spinner
        2. Appel API (POST/DELETE)
        3. Succès: Mettre à jour cache local
        4. Erreur: Rollback + Toast notification
        """
```

### 3.3 Logique transactionnelle

```
User clicks checkbox
    ↓
on_playlist_toggled(playlist_id, is_checked)
    ├─ Sauvegarder l'état précédent (rollback_state)
    ├─ Désactiver checkbox visuellement
    ├─ Afficher mini-spinner
    ├─ Déterminer l'action: ADD (POST) ou REMOVE (DELETE)
    ├─ Appel API threadé
    │   ├─ Succès (200 OK):
    │   │   ├─ Mettre à jour cache[track_id][playlist_id]
    │   │   ├─ Réactiver checkbox
    │   │   └─ Émettre signal (pour synchronisation UI)
    │   │
    │   └─ Échec (4xx/5xx):
    │       ├─ Restorer checkbox état = rollback_state
    │       ├─ Réactiver checkbox
    │       └─ Afficher Toast: "Impossible de modifier"
    │
    └─ [FIN]
```

---

## 4. Implémentation API & Services

### 4.1 PlaylistContextLoader (Worker Thread)

```python
class PlaylistContextLoader(QtCore.QRunnable):
    """Charge les contextes de playlists de manière concurrente."""

    # Signals (communiquent du worker thread → main thread)
    started: QtCore.Signal = QtCore.Signal()
    progress: QtCore.Signal = QtCore.Signal(int, int)  # current, total
    cache_ready: QtCore.Signal = QtCore.Signal(dict)  # ThreadSafePlaylistCache
    error: QtCore.Signal = QtCore.Signal(str)
    finished: QtCore.Signal = QtCore.Signal()

    def __init__(self,
                 session: Session,
                 user_id: str,
                 max_workers: int = 5):
        """Initialise le loader.

        Args:
            session: Session Tidal authentifiée
            user_id: ID de l'utilisateur courant
            max_workers: Nombre de threads concurrents pour les requêtes
        """

    def run(self) -> None:
        """Point d'entrée du thread worker.

        Séquence:
        1. Fetch all user playlists (pagination)
        2. Pour chaque playlist (parallèle):
           - Fetch all items (pagination)
           - Extract track IDs
        3. Build cache Dict[track_id, Set[playlist_id]]
        4. Émettre signal cache_ready avec cache
        """

    def _fetch_user_playlists(self) -> list[Playlist]:
        """Récupère toutes les playlists de l'utilisateur.

        Gère la pagination (offset/limit).
        Filtre les playlists éditables uniquement.
        """

    def _fetch_playlist_items(self,
                             playlist_id: str,
                             limit: int = 300) -> set[str]:
        """Récupère tous les IDs de pistes d'une playlist.

        Gère la pagination automatique.
        Retourne un Set pour O(1) lookup.
        """

    def request_abort(self) -> None:
        """Demande l'interruption du loader.

        Interruptibilité: Finit la requête en cours, puis s'arrête.
        """
```

### 4.2 Endpoints Tidal utilisés

```
# 1. Récupérer les playlists
GET /users/{userId}/playlists
    ?offset=0
    &limit=50
    &includeOnly=EDITORIAL,COLLABORATIVE

Response: {"items": [...], "totalNumberOfItems": N}

# 2. Récupérer les items d'une playlist
GET /playlists/{playlistId}/items
    ?offset=0
    &limit=300
    &includeOnly=TRACKS,VIDEOS

Response: {"items": [...], "totalNumberOfItems": M}
           où items[i].item.id = track_uuid

# 3. Ajouter une piste à une playlist
POST /playlists/{playlistId}/items
    Content-Type: application/json
    {"trackIds": ["uuid1", "uuid2"]}

# 4. Supprimer une piste d'une playlist
DELETE /playlists/{playlistId}/items/{itemId}
       OU
DELETE /playlists/{playlistId}/items?itemIds=uuid1,uuid2
```

### 4.3 Rate Limiting & Timeout

- **Timeout par requête** : 30 secondes
- **Max concurrent requests** : 5 (limité par QThreadPool)
- **Backoff strategy** : Exponentiel (1s → 2s → 4s) sur 429/503
- **Fail-silent** : Log warning, pas de popup utilisateur

---

## 5. Intégration dans MainWindow

### 5.1 Initialization Flow

```python
class MainWindow:
    def init_playlist_membership_manager(self):
        """Initialise le gestionnaire d'appartenance aux playlists."""

        # 1. Créer le cache thread-safe
        self.playlist_cache = ThreadSafePlaylistCache()

        # 2. Créer le worker (pas de démarrage encore)
        self.playlist_loader = PlaylistContextLoader(
            session=self.tidal.session,
            user_id=self.tidal.user_id,
            max_workers=5
        )

        # 3. Connecter les signaux du worker
        self.playlist_loader.cache_ready.connect(self.on_playlist_cache_ready)
        self.playlist_loader.error.connect(self.on_playlist_loader_error)
        self.playlist_loader.progress.connect(self.on_playlist_loader_progress)

        # 4. Connecter les signaux du tableau
        self.model_tr_results.modelReset.connect(self.on_results_layout_changed)
        self.proxy_tr_results.layoutChanged.connect(self.on_results_layout_changed)

        # 5. Ajouter le delegate personnalisé
        self.playlist_column_delegate = PlaylistColumnDelegate(
            parent=self.tr_results
        )
        self.tr_results.setItemDelegateForColumn(PLAYLIST_COLUMN_INDEX,
                                               self.playlist_column_delegate)

    def on_results_layout_changed(self) -> None:
        """Déclenche le pré-chargement lors d'un changement de résultats."""

        # 1. Réinitialiser le cache
        self.playlist_cache.clear()

        # 2. Lancer le worker de pré-chargement
        self.threadpool.start(self.playlist_loader)

    def on_playlist_cache_ready(self, cache: dict) -> None:
        """Appelé quand le cache est prêt.

        Notifie le delegate que le cache a changé.
        """
        self.playlist_cache.update_from_dict(cache)
        self.playlist_column_delegate.setCacheReady(True)
        self.tr_results.viewport().update()  # Redessine les cellules
```

---

## 6. Tests & Qualité

### 6.1 Fichier de tests: tests/test_playlist_manager.py

```python
class TestPlaylistContextLoader(unittest.TestCase):
    """Tests du worker de pré-chargement."""

    def test_fetch_user_playlists_pagination(self):
        """Vérifie la gestion de la pagination."""

    def test_build_cache_structure(self):
        """Vérifie la construction correcte du cache."""

    def test_thread_safety_concurrent_updates(self):
        """Vérifie la thread-safety lors d'accès concurrents."""

    def test_abort_request(self):
        """Vérifie l'interruption du worker."""

    def test_error_handling_api_failure(self):
        """Vérifie la gestion des erreurs API."""


class TestPlaylistManagerDialog(unittest.TestCase):
    """Tests du dialogue modal."""

    def test_dialog_initialization(self):
        """Vérifie l'initialisation correcte du dialogue."""

    def test_checkbox_state_from_cache(self):
        """Vérifie que les checkboxes reflètent l'état du cache."""

    def test_add_playlist_transaction(self):
        """Vérifie l'ajout d'une piste à une playlist."""

    def test_remove_playlist_transaction(self):
        """Vérifie le retrait d'une piste d'une playlist."""

    def test_api_error_rollback(self):
        """Vérifie le rollback en cas d'erreur API."""


class TestPlaylistColumnDelegate(unittest.TestCase):
    """Tests du delegate personnalisé."""

    def test_state_pending_spinner_rendering(self):
        """Vérifie le rendu du spinner en état PENDING."""

    def test_state_ready_button_rendering(self):
        """Vérifie le rendu du bouton en état READY."""

    def test_state_transition_pending_to_ready(self):
        """Vérifie la transition d'état PENDING → READY."""

    def test_click_opens_dialog(self):
        """Vérifie que le clic ouvre le dialogue."""


class TestThreadSafePlaylistCache(unittest.TestCase):
    """Tests du cache thread-safe."""

    def test_concurrent_reads_no_deadlock(self):
        """Vérifie les lectures concurrentes."""

    def test_add_track_to_playlist(self):
        """Vérifie l'ajout d'une piste."""

    def test_remove_track_from_playlist(self):
        """Vérifie le retrait d'une piste."""

    def test_contains_check_o1_performance(self):
        """Vérifie la complexité O(1) des vérifications."""
```

### 6.2 Métriques de qualité

- **Coverage cible** : ≥ 85% (tests/test_playlist_manager.py)
- **Linting** : `make check` doit passer (Black, isort, Flake8)
- **Type checking** : `mypy` sans errors
- **Performance** : Cache lookup < 1ms, Dialog appearance < 50ms

---

## 7. Dictionnaire d'erreurs

| Code | Signification | Action |
|------|---------------|--------|
| 401  | Non authentifié | Redirection login |
| 403  | Pas de permission | Toast silencieux |
| 404  | Playlist non trouvée | Log + continue |
| 429  | Rate limited | Backoff exponentiel |
| 500+ | Erreur serveur | Retry automatique (3x) |
| Timeout | Dépassement délai | Abort + log |

---

## 8. Résumé des fichiers à créer

1. **tidal_dl_ng/gui/playlist_membership.py**
   - `ThreadSafePlaylistCache`
   - `PlaylistContextLoader`
   - `PlaylistColumnDelegate`

2. **tidal_dl_ng/gui/dialog_playlist_manager.py**
   - `PlaylistManagerDialog`

3. **tests/test_playlist_manager.py**
   - Tests exhaustifs

4. **docs/playlist_membership_manager.md** (ce fichier)

5. **Modifications à tidal_dl_ng/gui/main_window.py**
   - Intégration des signaux et initialization

---

## 9. Chronologie estimée

- **Phase 1** : Backend (Worker + Cache) : 4-5h
- **Phase 2** : UI (Delegate + Dialog) : 3-4h
- **Phase 3** : Tests + Intégration : 2-3h
- **Total** : ~10-12h
