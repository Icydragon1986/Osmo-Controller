# Osmo Controller — Boccia Canada

Logiciel pour contrôler à distance plusieurs caméras **DJI Osmo Action 5 Pro**
(une par terrain de Boccia) : démarrer/arrêter l'enregistrement, suivre la
batterie, le temps restant, l'espace SD et la température — le tout depuis un
ordinateur (Mac ou PC), avec reconnexion automatique « erreur proof ».

## Lancement rapide (double-clic)

- **Windows** : `Lancer Osmo Controller.bat` (réel) / `Demo (simulation).bat`
- **Mac** : `Lancer Osmo Controller.command` (réel) / `Demo (simulation).command`
  Si un double-clic ouvre le fichier dans un éditeur de texte au lieu de le
  lancer, fais un clic droit → Ouvrir, ou une fois dans un Terminal :
  `chmod +x "Lancer Osmo Controller.command"`.

## Vraies caméras (Bluetooth)

```bash
pip install bleak                 # une seule fois (Mac : pip3 install bleak)
python hardware/scan_ble.py       # trouve l'adresse BLE de chaque caméra (Mac : python3)
python launcher.py --real         # pilote les caméras listées dans cameras.json (Mac : python3)
```

Sur Mac, bleak utilise CoreBluetooth : l'« adresse » de chaque caméra dans
`cameras.json` est un identifiant système (UUID), pas une adresse MAC comme sur
Windows — c'est normal, `hardware/scan_ble.py` (ou le scan depuis l'UI) donne
la bonne valeur à utiliser dans les deux cas, aucune différence de format à
gérer à la main.

`cameras.json` liste les caméras (nom + adresse BLE) :

```json
[
  { "name": "Terrain 1", "address": "8C:58:23:2B:25:23", "model": "osmo_action_5_pro" }
]
```

Connexion automatique (sans code à confirmer), statut en direct (batterie,
temps restant, température) et enregistrement à distance. ⚠️ La caméra n'accepte
qu'**un** contrôleur : coupe le Bluetooth du téléphone (fermer l'app Mimo ne
suffit pas).

## Démo sans matériel (mode simulation)

Des caméras virtuelles remplacent le vrai matériel — utile pour l'interface et
le développement :

```bash
python launcher.py                 # 3 terrains simulés, ouvre le navigateur
python launcher.py --cameras 5     # 5 terrains
python launcher.py --no-browser    # ne pas ouvrir le navigateur (API sur :8765)
```

(Pour itérer rapidement pendant le développement, sans passer par le lanceur
ni la vérification de mise à jour : `python app/app.py [...]` fait exactement
la même chose, juste sans le lanceur autour.)

Puis ouvre <http://127.0.0.1:8765/>. Tu peux démarrer/arrêter chaque terrain
ou tout d'un coup, et voir la batterie/durée/SD bouger en direct.

## Tests (purs, sans matériel)

```bash
cd app
python test_protocol.py     # moteur de protocole vs trame de référence DJI
python test_simulator.py    # caméra simulée
python test_connection.py   # connexion + reconnexion auto « erreur proof »
python test_manager.py      # gestion multi-caméras
python test_updater.py      # mise à jour automatique (manifeste + zip)
```

Aucune dépendance externe : tout utilise la bibliothèque standard de Python 3.

## Mise à jour automatique

L'app est du Python pur (quelques dizaines de Ko), donc une mise à jour ne
retélécharge que le code, jamais l'environnement.

`launcher.py`, à la racine, ne change quasiment jamais et fait tout le travail :

1. au démarrage, applique une mise à jour déjà téléchargée lors de la session
   précédente (échange de dossiers `app/` ↔ `app.next` — voir
   `app/osmo_controller/updater.py`, testé dans `app/test_updater.py`) ;
2. démarre l'app (`app/app.py`, importé et exécuté dans le même processus —
   nécessaire une fois packagé en `.exe`/`.app`, où il n'y a plus de `python.exe`
   séparé à invoquer) ;
3. en arrière-plan, pendant que l'app tourne, vérifie s'il existe une version
   plus récente et, si oui, la télécharge + vérifie son **SHA-256** + la met
   en attente (`app.next`) pour le **prochain** démarrage.

Seul `app/` est remplacé par une mise à jour — `cameras.json` et
`update_config.json` restent à la racine, à côté de `launcher.py`, donc rien
n'est perdu.

**Configuration** (`update_config.json`, à la racine) :

```json
{ "manifest_url": "https://raw.githubusercontent.com/<user>/<repo>/main/manifest.json" }
```

`manifest_url` absent ou `null` = vérification désactivée (c'est l'état par
défaut du dépôt tant qu'il n'y a pas encore de dépôt GitHub public). Si le
manifeste est injoignable (pas de Wi-Fi, mauvaise URL…), l'app continue de
fonctionner normalement — l'échec est seulement journalisé dans la console.

Le dossier `releases/` du dépôt contient `manifest.json` + le zip de chaque
version publiée (juste le contenu de `app/`, testé de bout en bout — téléchargement,
vérification SHA-256, application — contre ces vrais fichiers). Pas besoin de
GitHub Releases : un simple `git push` avec ces fichiers suffit, servis ensuite
via `raw.githubusercontent.com`.

**Reste à faire, de ton côté (compte/dépôt GitHub — je ne peux pas le faire à
ta place)** :
1. créer un dépôt GitHub **public** (ex. nom `Osmo-Controller`) ;
2. me dire son URL pour que je fasse `git push` (avec ta confirmation) ;
3. mettre l'URL brute du manifeste
   (`https://raw.githubusercontent.com/<toi>/<repo>/main/releases/manifest.json`)
   dans `update_config.json` — je peux le faire une fois l'URL connue.

À chaque nouvelle version ensuite : zipper le contenu de `app/` dans
`releases/osmo-X.Y.Z.zip`, recalculer son SHA-256, mettre à jour
`releases/manifest.json` (version/url/sha256), commit + push.

## Packager en .exe (Windows)

```bash
pip install pyinstaller
build_launcher.bat
```

Construit `dist/OsmoController/OsmoController.exe` + un dossier `app/` +
`cameras.json`/`update_config.json` à côté — le dossier `dist/OsmoController/`
au complet est ce qu'on distribue (zippé) : double-clic sur `OsmoController.exe`,
pas besoin d'installer Python ni `bleak` sur le poste cible.

Ce qui est figé dans l'exe (change rarement, nécessite un rebuild) :
Python + `bleak`/`winrt`. Ce qui reste à côté, en `.py` non compilé, et que
l'auto-update peut remplacer sans rebuild : `app/` (tout le code de l'app).
**Vérifié sur ce poste** : simulation, mode réel (scan BLE réel a bien trouvé
BCC-3), et fermeture propre — tous fonctionnent depuis l'exe construit.

**macOS (`.app`)** : pas faisable depuis Windows, PyInstaller ne fait pas de
compilation croisée. Il faudra relancer `pip install pyinstaller` + une
commande équivalente sur un vrai Mac quand tu en auras un.

## Architecture

```
launcher.py            <- racine, ne change quasiment jamais (mises à jour + démarrage)
cameras.json            <- config, survit aux mises à jour
update_config.json      <- config (URL du manifeste), survit aux mises à jour
app/                     <- REMPLACÉ à chaque mise à jour
  app.py                    point d'entrée (assemble tout)
  osmo_controller/          voir tableau ci-dessous
  webui/                    interface (HTML/CSS/JS)
```

| Fichier (dans `app/osmo_controller/`) | Rôle |
|---|---|
| `protocol.py` | Trames & CRC du **DJI R SDK** (vérifiés au bit près), `FrameReassembler` (fragmentation BLE) |
| `simulator.py` | Fausse caméra qui parle ce protocole |
| `connection.py` | Machine à états d'**une** caméra (reconnexion auto) + interface `Transport` |
| `sim_transport.py` | Transport simulé (branche le simulateur, sait simuler des pannes) |
| `bleak_transport.py` | Vrai transport BLE (`bleak`), implémente la même interface `Transport` |
| `manager.py` | Gestion **multi-caméras** (contrôle par caméra + global) |
| `camera_admin.py` / `config.py` | Scan/ajout/retrait de caméras depuis l'UI + persistance `cameras.json` |
| `webserver.py` | Serveur web local (pont navigateur ↔ asyncio) |
| `updater.py` | Mise à jour automatique (manifeste, téléchargement, échange de dossiers) |

Le découplage clé : `connection.py` parle à une interface `Transport`
abstraite. `SimulatedTransport` pour la démo, `BleakTransport` pour le vrai
matériel — le reste de la pile ne change pas selon le transport utilisé.

## Reste à faire

- **Transport BLE réel, appairage, device_id** : faits et **prouvés sur
  caméra physique** (voir `bleak_transport.py`).
- Valider **3+ caméras en BLE simultané** (testé jusqu'à présent avec 1).
- **Support Mac** : le code est prêt côté logiciel (bleak est multiplateforme,
  la réception BLE ré-assemble maintenant les trames quel que soit le MTU —
  voir `FrameReassembler` dans `protocol.py` — et les adresses/UUID macOS sont
  traitées comme de simples identifiants opaques). Reste à **valider sur une
  vraie machine Mac + vraie caméra** (aucun Mac disponible pour l'instant) :
  connexion, statut en direct, enregistrement, déconnexion propre.
- **Mise à jour automatique** : le mécanisme est écrit et branché
  (`launcher.py`), reste à créer le dépôt GitHub et y publier manifeste + zip
  (voir section « Mise à jour automatique » ci-dessus).
- **Packaging** : `.exe` Windows fait et vérifié (voir section ci-dessus,
  `build_launcher.bat`). `.app` macOS : pas faisable sans un vrai Mac.
- **Vérification du cadrage (aperçu vidéo)** : mise en pause (bouton « à venir »,
  désactivé). Le flux vidéo sans fil (RTMP par WiFi) demande un gros travail de
  reverse-engineering non résolu ; à reprendre plus tard.
- **Appli iPad** : Python/bleak ne fonctionne pas sur iOS — à discuter (piste
  envisagée : relais réseau plutôt qu'une appli Swift native).
