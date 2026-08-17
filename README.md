# Osmo Controller — Boccia Canada

Logiciel pour contrôler à distance plusieurs caméras **DJI Osmo Action 5 Pro**
(une par terrain de Boccia) : démarrer/arrêter l'enregistrement, suivre la
batterie, le temps restant, l'espace SD et la température — le tout depuis un
ordinateur (Mac ou PC), avec reconnexion automatique « erreur proof ».

---

# Guide d'utilisation

*(Cette section ne demande aucune connaissance en programmation. Pour le
fonctionnement interne et le développement, voir la « Section technique »
plus bas.)*

## 1. Télécharger et installer

👉 **[Dernière version — github.com/Icydragon1986/Osmo-Controller/releases](https://github.com/Icydragon1986/Osmo-Controller/releases/latest)**

Choisis le fichier pour ton appareil :
- **Windows** : `OsmoController-windows.zip`
- **Mac** : `OsmoController-Mac.zip`

Dézippe-le, puis double-clique `OsmoController.exe` (Windows) ou
`OsmoController.app` (Mac — clic droit → Ouvrir la toute première fois,
sinon macOS refuse de l'ouvrir).

**Mac uniquement**, une seule fois pendant que tu as encore internet, ouvre
un Terminal et lance :
```bash
xattr -cr OsmoController.app
```
Ça permet à l'app de s'ouvrir même sans connexion internet plus tard (utile
en tournoi, sur un Wi-Fi qui ne donne pas accès à internet).

## 2. Premier lancement : créer un compte

- Si le fichier que tu as téléchargé contient déjà un `users.json` (compte
  préparé à l'avance par quelqu'un de l'équipe), tu peux te connecter
  directement avec ce compte.
- Sinon, connecte-toi avec **admin / admin** — ce compte fonctionne toujours,
  sur toute installation, même une fois d'autres comptes créés.

Une fois connecté, tous les autres comptes peuvent être créés/retirés
directement depuis l'interface (bouton « 👤 Comptes ») — jamais besoin de
terminal.

⚠️ **admin / admin est un accès de secours permanent, pas un vrai compte** :
il ne peut ni être changé ni supprimé, même depuis le menu Comptes, et
fonctionne sur toute copie de l'app (le code est public sur GitHub). Sur un
PC exposé sur le réseau (`--host 0.0.0.0`, voir plus bas), n'importe qui sur
ce réseau peut s'en servir pour se connecter en admin — à garder en tête
pendant un tournoi sur un Wi-Fi partagé.

Deux types de comptes :
- **admin** : accès complet (enregistrement, gérer les caméras/comptes,
  fermer l'app pour tout le monde).
- **operator** : juste démarrer/arrêter l'enregistrement et voir le statut.

## 3. Se connecter depuis un iPad ou un téléphone

Aucune appli à installer sur l'iPad — Safari suffit. Une fois connecté sur
l'ordinateur qui pilote les caméras, clique le bouton **« 📶 Connexion
iPad »** : il affiche deux codes QR à scanner dans l'ordre :

1. Un code QR pour **rejoindre le Wi-Fi** (l'appareil photo native
   d'iPhone/iPad le reconnaît directement, pas besoin d'ouvrir Safari pour
   celui-là).
2. Un code QR pour **ouvrir la page de contrôle**.

Aucune adresse ni mot de passe à taper à la main.

## 4. Pas de Wi-Fi fiable sur place ? Le point d'accès de secours

Si le lieu du tournoi n'a pas de Wi-Fi fiable, l'ordinateur qui pilote les
caméras peut créer son propre réseau Wi-Fi (comme un routeur maison) — les
iPad/téléphones s'y connectent à la place, sans avoir besoin d'internet.

- **Sur Windows** : bouton dans la modale « Connexion iPad » pour démarrer/
  arrêter ce point d'accès directement depuis l'app.
- **Sur Mac** : à activer manuellement une fois dans Réglages Système
  (voir « Section technique » pour la marche à suivre détaillée).

## 5. Fermer l'application correctement

Le plus simple : le bouton **« Quitter »** dans l'interface web — il ferme
la connexion Bluetooth des caméras proprement avant d'arrêter l'app.

Si jamais ce bouton est oublié, l'app se ferme quand même correctement dans
la plupart des cas :
- **Windows** : fermer la fenêtre (le X), fermer la session ou éteindre le
  PC déclenche automatiquement la même déconnexion propre.
- **Mac** : l'app packagée n'a ni Dock ni fenêtre — utilise l'icône
  **« Osmo »** dans la barre de menu (en haut de l'écran) → Quitter. En
  tout dernier recours, **Moniteur d'activité → OsmoController → Quitter**
  (pas « Forcer à quitter », qui ne laisse aucune chance de déconnecter les
  caméras).

## 6. Limites à connaître

- **Une seule caméra en même temps par contrôleur** : la caméra n'accepte
  qu'**un** appareil connecté en Bluetooth. Si le téléphone de quelqu'un est
  encore associé à la caméra (même sans l'app Mimo ouverte), coupe son
  Bluetooth avant de connecter Osmo Controller.
- **Portée Bluetooth** : l'ordinateur qui pilote les caméras doit rester
  physiquement à portée Bluetooth de chaque caméra (environ 10-30 m selon
  les obstacles) pendant tout l'enregistrement — le Wi-Fi ne contourne pas
  cette limite. Sur Mac, cette portée est plus courte que sur PC et ne peut
  pas être améliorée avec un accessoire externe (limite du système
  d'Apple, pas du logiciel). Si les terrains sont trop éloignés pour qu'un
  seul poste les couvre tous, plusieurs postes peuvent être nécessaires.
- **Connexion non chiffrée (HTTP)** : sur le réseau Wi-Fi local, quelqu'un
  qui écoute activement ce même réseau pourrait techniquement intercepter
  un mot de passe. Risque réel mais faible sur un Wi-Fi de tournoi
  (demande un attaquant actif sur le même réseau, pas juste quelqu'un à
  proximité).
- **Réveil à distance d'une caméra éteinte** : impossible. Une caméra
  Osmo qui s'éteint automatiquement fait un vrai arrêt, pas une mise en
  veille — rien ne peut la rallumer à distance. Le mieux est d'ajuster le
  délai d'arrêt automatique directement dans les réglages de la caméra.

---

# Section technique (développement)

*(Tout ce qui suit s'adresse à quelqu'un qui développe, build ou dépanne le
logiciel — pas nécessaire pour l'utiliser en tournoi.)*

## Lancer depuis le code source

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

## Accès depuis un iPad — détails techniques

Aucune appli native n'est nécessaire — Safari sur iPad ne supporte pas le
Bluetooth de toute façon (Apple ne l'implémente pas). À la place, le PC/laptop
qui contrôle déjà les caméras en Bluetooth sert de relais : les autres
appareils (iPad, téléphone…) ouvrent simplement la page web du PC par le
Wi-Fi — ils ne font jamais de Bluetooth eux-mêmes.

**Comptes** (`users.json`, à la racine — jamais de mot de passe en clair,
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

**admin / admin fonctionne toujours**, codé en dur dans `auth.authenticate()`
(`app/osmo_controller/auth.py`) — indépendant du contenu de `users.json`, pas
listé dans `/api/users`, ne peut pas être retiré via `remove_user`. C'est un
accès de secours volontaire pour ne jamais rester bloqué, voir « Premier
lancement » dans le guide plus haut pour l'avertissement de sécurité associé
(le code étant public, ce compte est un accès permanent connu de tous sur
toute installation exposée sur le réseau).

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

**Rendre le PC accessible sur le réseau** : lance avec `--host 0.0.0.0`
(déjà fait dans `Lancer Osmo Controller.bat`/`.command`). Le PC affiche alors
dans sa console les adresses à utiliser (ex. `http://10.0.0.212:8765/`) —
tape-la dans Safari sur l'iPad, puis « Ajouter à l'écran d'accueil » pour une
icône comme une vraie appli.

**Le bouton « 📶 Connexion iPad »** affiche :
- un code QR **« rejoindre le Wi-Fi »** (format `WIFI:`, reconnu par
  l'appareil photo native d'iOS/Android — pas besoin de Safari pour celui-là) ;
- puis un code QR **par adresse réseau détectée** pour ouvrir la page.

Nécessite `pip install qrcode` sur le PC (sinon le reste de l'app fonctionne
quand même, juste sans ce bouton).

Le QR Wi-Fi vient de trois sources, dans cet ordre de priorité :
1. **Le point d'accès du PC, s'il est actif** (voir hotspot ci-dessous) —
   c'est la vérité du terrain, il prime sur tout le reste.
2. **Une config manuelle** (rare, pour un cas particulier) :
   ```bash
   python manage_wifi.py set MonHotspot motdepasse123
   python manage_wifi.py show
   python manage_wifi.py clear
   ```
3. **Le Wi-Fi normal du lieu**, détecté automatiquement (`netsh`) s'il est connecté.

**Démarrer/arrêter le point d'accès du PC depuis l'appli** (bouton admin
dans la modale « Connexion iPad »). Windows expose une API pour ça
(`NetworkOperatorTetheringManager` — le paquet s'appelle
`winrt-Windows.Networking.NetworkOperators`, au PLURIEL) : le PC peut
configurer, démarrer et arrêter son propre hotspot sans jamais ouvrir les
Réglages Windows. **Vérifié réellement** : démarrage confirmé (adresse
`192.168.137.1` active), lecture du SSID/mot de passe réels, arrêt propre,
à répétition.

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
python test_wake_broadcast.py  # diffusion BLE (réveil caméra, non branché dans l'app)
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

Seul `app/` est remplacé par une mise à jour — `cameras.json`, `users.json`,
`wifi_config.json` et `update_config.json` restent à la racine, à côté de
`launcher.py`, donc rien n'est perdu.

**Configuration** (`update_config.json`, à la racine) :

```json
{ "manifest_url": "https://raw.githubusercontent.com/Icydragon1986/Osmo-Controller/main/releases/manifest.json" }
```

Si le manifeste est injoignable (pas de Wi-Fi, mauvaise URL…), l'app continue
de fonctionner normalement — l'échec est seulement journalisé dans la console.

**Deux mécanismes de distribution séparés, ne pas confondre :**
- **`releases/` du dépôt** (`manifest.json` + un zip par version, juste le
  contenu de `app/`) — c'est ce que `launcher.py` vérifie tout seul en
  arrière-plan pour les installations déjà en place. Servi directement via
  `raw.githubusercontent.com`, pas besoin de GitHub Releases pour ça.
- **GitHub Releases** (page publique, zips complets `.exe`/`.app`) — c'est ce
  vers quoi pointe la section « Télécharger » tout en haut, pour quelqu'un
  qui n'a encore rien installé.

**Couper une nouvelle version, étape par étape :**
1. Bumper `VERSION` dans `app/osmo_controller/version.py`.
2. `python make_release.py X.Y.Z --notes "..."` — construit
   `releases/osmo-X.Y.Z.zip` + met à jour `releases/manifest.json` (pour
   l'auto-update silencieuse des installations existantes).
3. Rebuild `dist/OsmoController` (voir sections packaging plus bas), zipper
   le dossier complet.
4. `gh release create vX.Y.Z chemin/vers/OsmoController-windows.zip --title "..." --notes "..."`
   (et pareil côté Mac avec `OsmoController-Mac.zip`, depuis une machine Mac)
   — pour la page GitHub Releases publique.
5. Commit + push `releases/`, `app/osmo_controller/version.py`.

`make_release.py` existe spécifiquement parce que zipper `app/` à la main
(Compress-Archive PowerShell, Explorateur Windows…) stocke parfois les
chemins avec des antislashs au lieu de `/` — invisible sur Windows, mais ça
casse totalement l'extraction sur macOS/Linux (`ModuleNotFoundError` au
démarrage, vécu en prod). Le script force toujours `/`, peu importe la
plateforme utilisée pour couper la release.

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

⚠️ **Si tu oublies le bouton « Quitter » de l'interface web** : fermer la
fenêtre (le X), fermer la session Windows ou éteindre le PC déclenche quand
même la déconnexion Bluetooth propre avant que Windows ne tue le processus
(`SetConsoleCtrlHandler`, capte `CTRL_CLOSE_EVENT`/`CTRL_LOGOFF_EVENT`/
`CTRL_SHUTDOWN_EVENT` — aucun de ces trois événements n'est couvert par le
module `signal` standard de Python sur Windows). Limite honnête : Windows ne
laisse qu'environ 5 secondes avant de forcer la fermeture, donc avec
plusieurs caméras encore connectées au moment de fermer, la déconnexion
propre n'est pas garantie à 100 %, juste bien plus probable qu'avant.

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
la première fois si macOS refuse), navigateur ouvert automatiquement, mode
simulation, mode réel (connexion, statut en direct, démarrage/arrêt
d'enregistrement, fermeture propre via « Quitter »).

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
packagée (`--windowed`) n'a ni Dock ni fenêtre classique — une icône
**« Osmo »** dans la barre de menu (« Ouvrir l'interface » / « Quitter »)
sert de filet de secours en tout temps pendant que l'app tourne. Re-cliquer
sur l'app dans le Finder/Dock la réactive et rouvre l'interface au lieu de ne
rien faire de visible. En tout dernier recours : **Moniteur d'activité →
OsmoController → Quitter** (pas « Forcer à quitter », qui ne laisse aucune
chance de déconnecter les caméras proprement — vrai aussi côté Windows).
Fermer une fenêtre de Terminal si tu lances l'app en ligne de commande
déclenche aussi une déconnexion propre automatique (`SIGHUP`).

Quatre pièges macOS trouvés et corrigés en cours de route (aucun n'existe côté
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
4. **AppKit exige le vrai thread principal** : une icône de barre de menu
   (`NSStatusItem`) lancée depuis un thread à part plante. L'app tourne donc
   à l'envers de d'habitude sur Mac — `asyncio` (BLE + serveur web) roule
   dans un thread à part, pendant que le thread principal fait tourner la
   boucle `NSApplication`. Les signaux système, livrés par l'OS uniquement au
   thread principal, y sont enregistrés puis relayés vers l'arrêt propre une
   fois qu'asyncio est prêt. Un timer périodique sans effet évite aussi que
   la boucle AppKit (bloquante, en code natif) n'affame la livraison de ces
   signaux — sans lui, un SIGTERM restait enregistré mais ne se déclenchait
   jamais.

## Architecture

```
launcher.py            <- racine, ne change quasiment jamais (mises à jour + démarrage)
manage_users.py          <- racine, CLI pour gérer les comptes (users.json)
manage_wifi.py           <- racine, CLI pour la config Wi-Fi du hotspot (wifi_config.json)
make_release.py          <- racine, coupe une release (zip + manifest.json)
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
| `wake_broadcast.py` | Diffusion BLE pour tenter de réveiller une caméra (piste explorée, non branchée dans l'app) |

Le découplage clé : `connection.py` parle à une interface `Transport`
abstraite. `SimulatedTransport` pour la démo, `BleakTransport` pour le vrai
matériel — le reste de la pile ne change pas selon le transport utilisé.

## État du projet / reste à faire

**Fait et vérifié sur matériel réel** : transport BLE réel, appairage,
support Mac ET Windows, mise à jour automatique, packaging `.exe`/`.app`,
accès iPad + comptes + codes QR, hotspot Windows démarrable depuis l'app,
distribution via GitHub Releases, arrêt idiot-proof (Windows et Mac) même en
cas de fenêtre fermée/session fermée/PC éteint sans cliquer « Quitter »,
correction du double-lancement quand une instance était restée à l'écran de
connexion.

**Connu, pas encore réglé :**
- **Portée Bluetooth limitée sur Mac** : le radio interne des Mac a une
  portée plus courte que sur PC, et macOS n'accepte pas d'adaptateur
  Bluetooth externe pour l'améliorer (limite du système, pas du logiciel).
  Sur PC, un dongle USB Class 1 réglerait ça facilement — pas encore testé.
  Une piste à plus long terme (théorique, pas encore essayée) : un petit
  ordinateur dédié (type Raspberry Pi, qui accepte lui les adaptateurs
  Bluetooth externes via Linux) placé près d'un terrain, servant de
  relais/poste de contrôle pour cette caméra.
- **Plusieurs caméras simultanées** : testé jusqu'à présent avec **une
  seule** caméra en conditions réelles (à la maison et à l'INS). Le
  contrôle de plusieurs caméras en même temps n'a pas encore été validé
  sur du vrai matériel.
- **Sécurité réseau** : connexion en HTTP simple (pas HTTPS) sur le réseau
  local — passer en HTTPS demanderait de gérer des certificats, pas fait
  pour l'instant. Risque jugé réel mais faible sur un Wi-Fi de tournoi.
- **Réveil à distance depuis la veille** : confirmé **impossible**. Une
  caméra Osmo qui s'éteint après inactivité fait un vrai arrêt (pas une
  mise en veille BLE-aware) — aucune commande ni diffusion Bluetooth ne
  peut la rallumer à distance, vérifié avec deux approches différentes sur
  matériel réel (renvoi de `power_mode=0`, puis diffusion BLE `"WKP"` +
  reconnexion selon la doc officielle DJI). Même l'app Mimo officielle de
  DJI échoue à réveiller la caméra dans ce cas. La seule vraie mitigation
  est d'ajuster le délai d'arrêt automatique dans les réglages de la
  caméra elle-même.
- **Vérification du cadrage (aperçu vidéo)** : mis en pause. Le flux vidéo
  sans fil (RTMP par Wi-Fi) demande un gros travail de reverse-engineering
  non résolu.
