# Architecture des appels API pour les playlists

## Vue d'ensemble

Tous les appels API liés aux playlists ont été centralisés dans un seul module pour une meilleure maintenabilité et cohérence.

## Fichier centralisé : `tidal_dl_ng/helper/playlist_api.py`

Ce module contient toutes les fonctions d'interaction avec l'API Tidal pour les playlists :

### Fonctions disponibles

#### 1. `get_user_playlists(session: Session) -> list[UserPlaylist]`
- **Description**: Récupère toutes les playlists de l'utilisateur
- **Paramètres**: Session Tidal authentifiée
- **Retour**: Liste d'objets UserPlaylist
- **Exceptions**: RequestException, ValueError

#### 2. `get_playlist_items(playlist: UserPlaylist) -> list[Track]`
- **Description**: Récupère tous les morceaux d'une playlist
- **Paramètres**: Objet UserPlaylist
- **Retour**: Liste d'objets Track
- **Exceptions**: RequestException

#### 3. `add_track_to_playlist(session: Session, playlist_id: str, track_id: str) -> None`
- **Description**: Ajoute un morceau à une playlist
- **Paramètres**:
  - session: Session Tidal
  - playlist_id: UUID de la playlist
  - track_id: UUID du morceau
- **Exceptions**: RequestException, ValueError

#### 4. `remove_track_from_playlist(session: Session, playlist_id: str, track_id: str) -> None`
- **Description**: Retire un morceau d'une playlist
- **Paramètres**:
  - session: Session Tidal
  - playlist_id: UUID de la playlist
  - track_id: UUID du morceau
- **Exceptions**: RequestException, ValueError
- **Note**: Gère automatiquement la recherche de l'index du morceau

#### 5. `get_playlist_metadata(playlist: UserPlaylist) -> dict[str, str | int]`
- **Description**: Extrait les métadonnées d'une playlist
- **Paramètres**: Objet UserPlaylist
- **Retour**: Dictionnaire avec `name`, `item_count`, `id`

## Modules utilisant l'API centralisée

### 1. `tidal_dl_ng/gui/dialog_playlist_manager.py`
Utilise :
- `add_track_to_playlist()` - Pour ajouter des morceaux via l'interface
- `remove_track_from_playlist()` - Pour retirer des morceaux via l'interface

### 2. `tidal_dl_ng/gui/playlist_membership.py`
Utilise :
- `get_user_playlists()` - Pour charger les playlists au démarrage
- `get_playlist_items()` - Pour construire le cache de memberships
- `get_playlist_metadata()` - Pour afficher les noms et comptes

## Avantages de cette architecture

1. **Maintenabilité** : Un seul endroit pour modifier la logique API
2. **Cohérence** : Même gestion d'erreurs partout
3. **Testabilité** : Facile de mocker les fonctions API
4. **Logging centralisé** : Tous les logs API au même endroit
5. **Évolutivité** : Facile d'ajouter de nouvelles fonctions

## Gestion des erreurs

Toutes les fonctions :
- Loggent les erreurs avec `logger_gui`
- Propagent les exceptions (RequestException) pour que l'appelant puisse gérer
- Gèrent automatiquement les cas limites (playlist vide, morceau non trouvé, etc.)

## Exemple d'utilisation

```python
from tidal_dl_ng.helper.playlist_api import add_track_to_playlist, get_user_playlists

# Récupérer les playlists
playlists = get_user_playlists(session)

# Ajouter un morceau
try:
    add_track_to_playlist(session, playlist_id="abc123", track_id="def456")
    print("Morceau ajouté avec succès")
except RequestException as e:
    print(f"Erreur: {e}")
```

## Migration future

Si besoin de passer à une autre bibliothèque API ou d'ajouter un cache HTTP, il suffit de modifier `playlist_api.py` sans toucher aux autres fichiers.
