# Osmo Controller — Boccia Canada

Logiciel pour contrôler à distance plusieurs caméras **DJI Osmo Action 5 Pro**
(une par terrain de Boccia) : démarrer/arrêter l'enregistrement, suivre la
batterie, le temps restant, l'espace SD et la température — le tout depuis un
ordinateur (Mac ou PC), avec reconnexion automatique « erreur proof ».

## Télécharger (pas besoin de Python ni de code)

👉 **[Dernière version — github.com/Icydragon1986/Osmo-Controller/releases](https://github.com/Icydragon1986/Osmo-Controller/releases/latest)**

Choisis le fichier pour ton appareil (`OsmoController-Windows.zip` ou
`OsmoController-Mac.zip`), dézippe-le, double-clique `OsmoController.exe`
(Windows) ou `OsmoController.app` (Mac — clic droit → Ouvrir la toute première
fois). Mac uniquement : lance `xattr -cr OsmoController.app` une fois, pendant
que tu as encore internet, pour que l'app puisse s'ouvrir même sans connexion
plus tard (voir « Packager en .app » plus bas).

Au tout premier lancement, aucun compte n'existe — voir la section
« Comptes » plus bas pour en créer un.

## Lancer depuis le code source (pour développer)

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

## Accès depuis un iPad (ou tout appareil sur le même Wi-Fi)

Aucune appli native n'est nécessaire — Safari sur iPad ne supporte pas le
Bluetooth de toute façon (Apple ne l'implémente pas). À la place, le PC/laptop
qui contrôle déjà les caméras en Bluetooth sert de relais : les autres
appareils (iPad, téléphone…) ouvrent simplement la page web du PC par le
Wi-Fi — ils ne font jamais de Bluetooth eux-mêmes.

**1. Comptes** (`users.json`, à la racine — jamais de mot de passe en clair,
haché avec PBKDF2). Deux façons de les gérer :

- **Depuis l'interface** (bouton « 👤 Comptes », admin seulement) : liste des
  comptes existants avec un bouton Retirer chacun, et un formulaire
  nom/mot de passe/rôle pour ajouter un compte — **retaper le nom d'un compte
  existant change simplement son mot de passe/rôle** (pas besoin d'un bouton
  « modifier » séparé). Impossible de retirer son propre compte par erreur
  (protection intégrée).
- **En ligne de commande** (utile pour le tout premier compte, avant d'avoir
  accès à l'interface) :
  ```bash
  python manage_users.py add jonathan motdepasse --role admin
  python manage_users.py add coach1 motdepasse2 --role operator
  python manage_users.py list
  python manage_users.py remove coach1
  ```

Deux rôles :
- **admin** : tout (enregistrement, gérer les caméras/comptes, quitter l'app).
- **operator** : juste démarrer/arrêter l'enregistrement et voir le statut —
  ne peut pas scanner/ajouter/retirer de caméra, gérer les comptes, ni fermer
  l'app pour tout le monde.

Si aucun compte n'existe, l'app le rappelle au démarrage et personne ne peut
se connecter tant que tu n'en as pas ajouté au moins un (par CLI la première
fois, forcément — sans compte, impossible d'atteindre le bouton).

**Partager les mêmes comptes entre plusieurs machines** (ton PC, un Mac, un
autre laptop…) : `users.json` est local à chaque installation, il n'est pas
synchronisé automatiquement. Le plus simple est de **copier ton fichier
`users.json`** (celui où tu as déjà créé tous les comptes) dans le dossier de
chaque nouvelle installation — les mots de passe hachés sont portables d'une
machine à l'autre sans rien recalculer. `build_launcher.bat` et
`build_launcher_mac.sh` le font automatiquement s'il est présent à la racine
au moment du build (voir sections packaging plus bas), pour que la personne
qui reçoit l'app puisse se connecter directement, sans jamais toucher à un
terminal.

**2. Rendre le PC accessible sur le réseau** : lance avec `--host 0.0.0.0`
(déjà fait dans `Lancer Osmo Controller.bat`/`.command`). Le PC affiche alors
dans sa console les adresses à utiliser (ex. `http://10.0.0.212:8765/`) —
tape-la dans Safari sur l'iPad, puis « Ajouter à l'écran d'accueil » pour une
icône comme une vraie appli.

**3. Encore plus simple : le bouton « 📶 Connexion iPad »** — une fois connecté
sur le PC, ce bouton affiche :
- un code QR **« rejoindre le Wi-Fi »** (format `WIFI:`, reconnu par
  l'appareil photo native d'iOS/Android — pas besoin de Safari pour celui-là) ;
- puis un code QR **par adresse réseau détectée** pour ouvrir la page.

Scanner les deux, dans l'ordre, connecte l'iPad sans jamais taper une adresse
ni un mot de passe Wi-Fi à la main. Nécessite `pip install qrcode` sur le PC
(sinon le reste de l'app fonctionne quand même, juste sans ce bouton).

Le QR Wi-Fi vient de trois sources, dans cet ordre de priorité :
1. **Le point d'accès du PC, s'il est actif** (voir bouton hotspot ci-dessous)
   — c'est la vérité du terrain, il prime sur tout le reste.
2. **Une config manuelle** (rare, pour un cas particulier) :
   ```bash
   python manage_wifi.py set MonHotspot motdepasse123
   python manage_wifi.py show
   python manage_wifi.py clear
   ```
3. **Le Wi-Fi normal du lieu**, détecté automatiquement (`netsh`) s'il est connecté.

**4. Encore mieux : démarrer/arrêter le point d'accès du PC depuis l'appli**
(bouton admin dans la modale « Connexion iPad »). Contrairement à ce que je
pensais au départ, Windows expose bien une API pour ça
(`NetworkOperatorTetheringManager` — le paquet s'appelle
`winrt-Windows.Networking.NetworkOperators`, au PLURIEL, une coquille de ma
part m'avait fait croire le contraire) : le PC peut configurer, démarrer et
arrêter son propre hotspot sans jamais ouvrir les Réglages Windows. **Vérifié
réellement** : démarrage confirmé (adresse `192.168.137.1` active), lecture
du SSID/mot de passe réels, arrêt propre, à répétition.

```bash
pip install "winrt-Windows.Networking.NetworkOperators" "winrt-Windows.Networking.Connectivity"
```

⚠️ Ne reconfigure pas le nom/mot de passe existant du hotspot — démarre/arrête
juste avec ce qui est déjà défini dans Windows (Paramètres > Réseau et
Internet > Point d'accès mobile), pour ne pas casser un mot de passe déjà
communiqué à l'équipe.

⚠️ **Limite vécue en tournoi** : cette API Windows (Mobile Hotspot) exige une
connexion internet déjà active à partager — sans Ethernet ni autre Wi-Fi
connecté, elle refuse de démarrer, même si les appareils qui rejoignent le
hotspot n'ont pas besoin d'internet. Dans ce cas, l'app bascule automatiquement
sur le **réseau hébergé legacy** (`netsh wlan hostednetwork`), qui ne dépend
d'aucune connexion existante — seulement du SSID/mot de passe déjà réglés via
`manage_wifi.py set`. Si l'adaptateur Wi-Fi de la machine ne supporte plus
cette fonctionnalité (fréquent sur du matériel récent, vérifiable avec
`netsh wlan show drivers`, ligne « Réseau hébergé pris en charge »), le bouton
renverra une erreur claire plutôt que d'échouer en silence.

**5. Sans Wi-Fi de tournoi fiable** : le PC peut créer son propre point d'accès
Wi-Fi (hotspot), sans avoir besoin d'internet — c'est un réseau local comme un
routeur maison, les appareils s'y voient entre eux même hors ligne. Tout le
monde (y compris le PC lui-même, si besoin) s'y connecte à la place ; ça reste
un seul réseau, un seul PC-relais.

**Sur Mac** : pas de bouton hotspot automatique (Apple n'expose aucune API/CLI
publique pour "Internet Sharing" — contrairement à Windows). La marche à
suivre :
1. Réglages Système > Général > Partage (ou "Partage de connexion internet"
   selon la version macOS) : partage depuis n'importe quelle interface (même
   débranchée, ex. Ethernet ou Pont Thunderbolt) vers "Wi-Fi" — ça marche
   sans connexion internet réelle en amont, seul le partage local aux
   appareils compte. Choisis un nom de réseau et un mot de passe dans
   "Options Wi-Fi" en activant le partage.
2. `python manage_wifi.py set <nom> <mot de passe>` (une seule fois, avec le
   nom/mot de passe choisis à l'étape 1) — le code QR « Connexion iPad »
   utilisera ensuite automatiquement ce réseau.

⚠️ **L'iPad ne peut pas remplacer ce PC-relais** : Safari (et iOS en général)
n'a aucun accès au Bluetooth bas niveau que `bleak` utilise — ce n'est pas une
histoire de permission mais une limite d'iOS. Une appli native (Swift) pourrait
le faire, mais redemande un Mac + une réécriture complète du protocole ; **un
seul PC/laptop suffit pour toute l'équipe**, pas besoin d'un par personne.

⚠️ **Limite connue** : la connexion se fait en HTTP simple (pas HTTPS) sur le
réseau local — quelqu'un qui écoute activement ce même réseau pourrait
intercepter un mot de passe ou une session. Sur un Wi-Fi de tournoi partagé,
c'est un risque réel mais faible (ça demande un attaquant actif sur le même
réseau, pas juste quelqu'un « à portée »). Passer en HTTPS demanderait de
gérer des certificats — pas fait pour l'instant.

⚠️ **Portée Bluetooth** : le PC doit rester physiquement à portée BLE de
chaque caméra (environ 10-30 m selon les obstacles) pendant tout
l'enregistrement — ça ne se contourne pas par le Wi-Fi. Si les terrains sont
trop éloignés pour qu'un seul PC les couvre tous, il en faudra plusieurs
(chacun avec sa propre config/comptes) ; à valider sur le terrain.

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
python test_auth.py         # comptes/sessions (hachage, rôles, expiration)
python test_wifi_info.py    # code QR Wi-Fi (format, échappement, détection)
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
compilation croisée. Voir la section dédiée ci-dessous.

## Packager en .app (macOS)

```bash
pip3 install pyinstaller
./build_launcher_mac.sh
```

Construit `dist/OsmoController.app` — un vrai bundle macOS, avec `app/` +
`cameras.json`/`update_config.json` **à l'intérieur** (`Contents/MacOS/`, à
côté de l'exécutable réel — c'est là que `sys.executable` pointe une fois
packagé, pas à côté du `.app` lui-même). Le dossier `dist/OsmoController.app`
au complet est ce qu'on distribue (zippé) : double-clic, pas besoin
d'installer Python ni `bleak` sur le poste cible.

Ce qui est figé dans l'app (change rarement, nécessite un rebuild) : Python +
`bleak` (CoreBluetooth/pyobjc, collecté automatiquement par le script). Ce qui
reste à côté, non compilé, et que l'auto-update peut remplacer sans rebuild :
`app/`.

**Vérifié sur matériel réel** (Mac + caméra BCC-3) : double-clic Finder (pas
de blocage Gatekeeper — le build est fait localement, pas de quarantaine ;
sur une AUTRE machine où l'app a été téléchargée/copiée, clic droit > Ouvrir
la première fois si macOS refuse), pas de fenêtre console visible (c'est
`--windowed`, volontaire — sinon PyInstaller ne produit pas un vrai `.app` du
tout sur macOS), navigateur ouvert automatiquement, mode simulation, mode réel
(connexion, statut en direct, démarrage/arrêt d'enregistrement, fermeture
propre via « Quitter »).

⚠️ **Vécu en compétition : l'app refuse de s'ouvrir sans connexion internet,
sur une machine où elle vient d'être copiée/transférée.** Cause : la
signature est "ad hoc" (pas de compte Apple Developer, `TeamIdentifier=not
set` — vérifiable avec `codesign -dv --verbose=4 OsmoController.app`). macOS
marque tout `.app` fraîchement copié/téléchargé/transféré (AirDrop, clé USB,
cloud…) comme "en quarantaine" ; au tout premier lancement, Gatekeeper essaie
de contacter les serveurs Apple pour vérifier l'app — sans internet, ça peut
échouer au lieu de se rabattre proprement, et l'app ne s'ouvre juste pas
(aucune erreur visible, `--windowed` oblige).

**Checklist avant de partir en compétition**, pour chaque machine/copie de
l'app :
```bash
xattr -cr "/chemin/vers/OsmoController.app"   # retire la quarantaine
```
Ça enlève le marqueur une fois pour toutes — plus aucune vérification
Gatekeeper ensuite, réseau ou pas. **À refaire à chaque nouvelle copie** de
l'app (nouveau build, nouveau transfert sur une machine). Sinon, lancer l'app
une fois avec internet (clic droit > Ouvrir, approuver) avant de partir suffit
aussi dans la plupart des cas, mais `xattr -cr` est plus fiable et
définitif.

Solution durable (mais payante, $99/an) : signer avec un vrai compte Apple
Developer + notariser + "stapler" le ticket (`xcrun stapler staple`) — une
app stapled se vérifie 100% localement, pour toujours, même au tout premier
lancement sur une machine neuve. Pas fait actuellement.

⚠️ **Si tu oublies le bouton « Quitter » de l'interface web** : l'app
packagée (`--windowed`) n'a ni icône Dock ni barre de menu — rien à fermer,
rien sur quoi faire Cmd+Q. Le seul moyen de l'arrêter proprement est
**Moniteur d'activité → sélectionner OsmoController → Quitter** (pas
« Forcer à quitter », qui ne laisse aucune chance de déconnecter les caméras
proprement — vrai aussi côté Windows). Fermer une fenêtre de Terminal si tu
lances l'app en ligne de commande déclenche déjà une déconnexion propre
automatique (testé sur matériel réel).

Trois pièges macOS trouvés et corrigés en cours de route (aucun n'existe côté
Windows) :
1. **Permission Bluetooth par app** : chaque `.app` (identité/signature
   distincte) a sa propre entrée dans Réglages Système → Confidentialité et
   sécurité → Bluetooth — celle donnée à Terminal ne s'applique pas à
   `OsmoController.app`. `Info.plist` doit aussi déclarer
   `NSBluetoothAlwaysUsageDescription`, sinon CoreBluetooth échoue sans même
   déclencher de popup de permission (ni erreur claire) ; `build_launcher_mac.sh`
   génère un `.spec` patché pour l'inclure automatiquement.
2. **Boucle d'événements CoreBluetooth plus lente en `--windowed`** : sans
   fenêtre/`NSApplication` au premier plan, la connexion BLE peut prendre
   jusqu'à ~20 s au lieu de 2-3 s. `bleak_transport.py` utilise maintenant un
   délai de 25 s (`_HANDSHAKE_TIMEOUT`, appliqué aussi au `connect()` de
   `bleak` lui-même) au lieu de 8 s.
3. **`asyncio.Event()` créé trop tôt (bug réel, pas juste macOS/packaging)** :
   sous Python 3.9, un `asyncio.Event()` construit avant que la boucle
   `asyncio.run(...)` existe se lie à la mauvaise boucle
   (`RuntimeError: ... attached to a different loop`), et l'erreur était
   silencieusement avalée par `CameraConnection._try_connect()`, rendant le
   bug invisible (la caméra semblait juste injoignable). Corrigé dans
   `bleak_transport.py` (`_approved`) et `connection.py` (`_link_lost`,
   `_connected_event`) en créant ces `Event` au moment de `connect()`/`start()`
   plutôt que dans `__init__`. Les exceptions de connexion sont maintenant
   journalisées (`  [nom] connexion échouée : ...`) au lieu d'être avalées.

## Architecture

```
launcher.py            <- racine, ne change quasiment jamais (mises à jour + démarrage)
manage_users.py          <- racine, CLI pour gérer les comptes (users.json)
manage_wifi.py           <- racine, CLI pour la config Wi-Fi du hotspot (wifi_config.json)
cameras.json             <- config, survit aux mises à jour
users.json               <- comptes (mots de passe hachés), survit aux mises à jour
wifi_config.json         <- config Wi-Fi hotspot (optionnelle), survit aux mises à jour
update_config.json       <- config (URL du manifeste), survit aux mises à jour
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
| `webserver.py` | Serveur web local (pont navigateur ↔ asyncio), routes protégées par session |
| `auth.py` | Comptes (hachage PBKDF2), rôles admin/operator, sessions en mémoire |
| `wifi_info.py` | Détection/config Wi-Fi + génération du payload QR `WIFI:` |
| `hotspot.py` | Démarrer/arrêter le point d'accès Wi-Fi du PC (Windows seulement ; repli réseau hébergé si aucune connexion à partager) |
| `updater.py` | Mise à jour automatique (manifeste, téléchargement, échange de dossiers) |

Le découplage clé : `connection.py` parle à une interface `Transport`
abstraite. `SimulatedTransport` pour la démo, `BleakTransport` pour le vrai
matériel — le reste de la pile ne change pas selon le transport utilisé.

## Reste à faire

- **Transport BLE réel, appairage, device_id** : faits et **prouvés sur
  caméra physique** (voir `bleak_transport.py`).
- Valider **3+ caméras en BLE simultané** (testé jusqu'à présent avec 1).
- **Support Mac** : FAIT et **vérifié réellement** sur une vraie machine Mac +
  vraie caméra (BCC-3). Séquence complète validée avec `hardware/scan_ble.py`
  puis `hardware/real_camera_test.py` : scan (caméra trouvée via son UUID
  CoreBluetooth + service 0xFFF0), connexion sans popup, statut en direct
  (batterie, capacité SD, température), démarrage/arrêt d'un enregistrement
  réel, déconnexion propre. ⚠️ Point d'attention macOS découvert au passage :
  Terminal.app (ou l'app qui lance Python) doit avoir la permission
  Bluetooth activée dans Réglages Système → Confidentialité et sécurité →
  Bluetooth, sinon bleak échoue avec l'erreur trompeuse « Bluetooth device is
  turned off » même quand le Bluetooth est bien actif.
- **Mise à jour automatique** : FAIT et branché (`launcher.py`), dépôt GitHub
  public en place et vérifié en conditions réelles (voir section ci-dessus).
- **Packaging** : `.exe` Windows fait et vérifié (voir section ci-dessus,
  `build_launcher.bat`). `.app` macOS : FAIT et **vérifié réellement**
  (`build_launcher_mac.sh` — voir section « Packager en .app (macOS) »
  ci-dessus) — double-clic Finder, simulation, mode réel avec BCC-3
  (connexion, statut, enregistrement, fermeture propre). Au passage, deux
  bugs de fond corrigés dans `bleak_transport.py`/`connection.py` (des
  `asyncio.Event()` créés hors de la bonne boucle asyncio) — invisibles avant
  parce que l'exception était silencieusement avalée ; les erreurs de
  connexion sont maintenant journalisées.
- **Accès iPad + comptes + code QR** : FAIT (voir section « Accès depuis un
  iPad » ci-dessus) — relais Wi-Fi vers le PC, comptes admin/operator, bouton
  QR pour se connecter sans taper d'adresse. Testé (curl + navigateur réel) :
  connexion, restrictions de rôle (403 pour un operator qui tente scan/quit),
  déconnexion, session expirée, QR scanné avec succès. Deux bugs trouvés par
  Jonathan en test réel, corrigés : `--host 0.0.0.0` faisait planter
  l'ouverture du navigateur, et un traceback inoffensif s'affichait à la
  déconnexion brutale d'un appareil.
- **Hotspot du PC démarrable/arrêtable depuis l'appli** : FAIT et **vérifié
  réellement** avec une connexion à partager (démarrage confirmé, adresse
  `192.168.137.1` active, arrêt propre, à répétition) — voir section
  ci-dessus. Windows seulement.
  **Cas "machine SANS AUCUNE connexion réseau du tout"** : vécu en tournoi —
  le Mobile Hotspot Windows refuse de démarrer sans connexion à partager,
  même si rien de plus n'est requis pour les appareils qui rejoignent le
  hotspot. Un repli sur le réseau hébergé legacy (`netsh wlan
  hostednetwork`, ne dépend d'aucune connexion existante) a été ajouté côté
  code — **pas encore validé sur du matériel réel en offline complet**,
  ni le support du pilote Wi-Fi utilisé en tournoi. À tester avant de
  compter dessus en compétition.
  **Reste à valider en vrai tournoi** : portée BLE d'un PC pour plusieurs
  terrains (peut-être plusieurs PC nécessaires).
  Si tu reconstruis le `.exe` (`build_launcher.bat`), ajoute
  `--collect-all qrcode --collect-all winrt` pour que les boutons QR et
  hotspot fonctionnent aussi depuis l'exe (pas encore fait dans le build actuel).
- **Vérification du cadrage (aperçu vidéo)** : mise en pause (bouton « à venir »,
  désactivé). Le flux vidéo sans fil (RTMP par WiFi) demande un gros travail de
  reverse-engineering non résolu ; à reprendre plus tard.
- **Réveil à distance depuis la veille** : EN COURS, 2 hypothèses testées.
  1. ❌ **Réfutée par Jonathan sur matériel réel** : renvoyer `power_mode=0`
     (`build_power_mode_command` / `hardware/wake_test.py`) sur la connexion
     existante NE réveille PAS la caméra (elle se met bien en veille, mais
     ne se réveille pas).
  2. 🧪 **Nouvelle piste, pas encore testée sur matériel** : la doc officielle
     DJI (`Q&A.md` + « Camera Power Mode Settings (001A) » du SDK) décrit en
     fait un mécanisme différent — le PC doit **diffuser** (broadcast) un
     paquet BLE spécial `"WKP" + adresse MAC de la caméra inversée` pendant
     ~2 s (la caméra le capte même en veille), PUIS **reconnecter** (le lien
     BLE se coupe pendant la veille, selon la doc). Conditions DJI : s'être
     connecté à cette caméra récemment, et veille de moins de 30 minutes.
     Implémenté dans `wake_broadcast.py` (`broadcast_wake`, via
     `winrt-Windows.Devices.Bluetooth.Advertisement` — déjà présent, c'est
     une dépendance de `bleak` sur Windows) + testable avec
     `python hardware/wake_broadcast_test.py`. **Vérifié seulement que l'API
     de diffusion fonctionne sans erreur** (démarré/arrêté avec succès) ;
     **pas encore testé contre la vraie caméra** (hors de portée). Rien
     n'est branché dans l'app tant que ce n'est pas confirmé.
