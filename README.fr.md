<div align="center">

[English](README.md) · **Français** · [العربية](README.ar.md)

<img src="assets/eskaboard.svg" alt="Icône d'Eskali Board" width="112">

# Eskali Board

**Votre téléphone devient le clavier de votre PC.**
Scannez un code QR, puis tapez ou dictez sur le téléphone, en arabe, en français ou en anglais. Le texte apparaît dans la fenêtre active du PC.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3](https://img.shields.io/badge/python-3-3776AB.svg?logo=python&logoColor=white)](requirements.txt)
[![Platforms](https://img.shields.io/badge/PC-Ubuntu%20%7C%20Windows-555.svg)](#systemes)
[![Android app](https://github.com/Mohamedeskali/EskaBoard/actions/workflows/android.yml/badge.svg)](https://github.com/Mohamedeskali/EskaBoard/actions/workflows/android.yml)
[![Release](https://img.shields.io/github/v/release/Mohamedeskali/EskaBoard)](https://github.com/Mohamedeskali/EskaBoard/releases)

[Installation](#installation) · [Utilisation](#utilisation) · [Application Android](#android) · [Sécurité](#securite) · [Dépannage](#depannage)

</div>

---

<p align="center">
  <img src="assets/screenshots/pc-window.png" alt="La fenêtre du PC (QR masqué)" height="360">
  <img src="assets/screenshots/phone-live.png" alt="Mode Direct" height="360">
  <img src="assets/screenshots/phone-send.png" alt="Mode Envoyer" height="360">
  <img src="assets/screenshots/phone-keyboard.png" alt="Saisie en arabe avec Gboard" height="360">
</p>

<p align="center"><sub>La fenêtre du PC (QR masqué) · Mode Direct · Mode Envoyer · Saisie en arabe avec Gboard</sub></p>

<!-- Vidéo de démonstration (bientôt) : put the link or a thumbnail here, e.g.
[![Demo](assets/screenshots/demo-thumbnail.png)](https://youtu.be/...)
-->

## Sommaire

- [Fonctionnalités](#fonctionnalites)
- [Systèmes pris en charge](#systemes)
- [Démarrage rapide](#demarrage)
- [Prérequis](#prerequis)
- [FAQ](#faq)
- [Installation](#installation) ([Ubuntu](#install-ubuntu), [Windows](#install-windows), [depuis un dossier](#depuis-un-dossier))
- [Utilisation](#utilisation)
- [Application Android](#android)
- [Sécurité et vie privée](#securite)
- [Fonctionnement](#fonctionnement)
- [Limites](#limites)
- [Dépannage](#depannage)
- [Développement](#developpement)
- [Licence](#licence)

<a id="fonctionnalites"></a>
## Fonctionnalités

- **Tapez et dictez depuis le téléphone.** Utilisez le clavier du téléphone (saisie vocale Gboard, glisser, correction automatique) et envoyez le texte au PC.
- **L'arabe marche partout.** Le texte de droite à gauche arrive intact sur le PC, quelle que soit la disposition de clavier active.
- **Deux modes.** **Direct** reproduit chaque frappe en temps réel ; **Envoyer** envoie tout le texte d'un coup, suivi d'Entrée si vous le souhaitez.
- **Touches rapides.** Entrée, Échap, effacer ce que le téléphone a tapé, copier, coller.
- **Captures d'écran du PC** (un bouton par écran), enregistrées et copiées dans le presse-papiers du PC.
- **Envoi de photos et de fichiers** du téléphone vers le dossier `Téléchargements/EskaBoard` du PC.
- **Historique des textes.** Chaque texte qui quitte la zone est gardé sur le téléphone : restaurez-le, renvoyez-le ou supprimez-le.
- **Application Android facultative** avec lecteur de QR, plein écran, et boutons flottants Entrée et capture qui marchent par-dessus toutes les applications.
- **Sans compte, sans cloud.** Le téléphone et le PC communiquent directement sur votre Wi-Fi, chiffré de bout en bout.
- **Trois langues** pour la page du téléphone et l'application : العربية, English, Français.

<a id="systemes"></a>
## Systèmes pris en charge

| PC | Remarques |
|---|---|
| Ubuntu 24.04 ou plus récent | GNOME sous Wayland |
| Windows 10 et 11 | Depuis la version 0.2.0 |

Le téléphone n'a besoin que d'un navigateur web, et il doit être sur le **même réseau Wi-Fi** que le PC. Sur Android, vous pouvez aussi utiliser l'[application Eskali Board](#android) (Android 7.0 ou plus récent).

<a id="demarrage"></a>
## Démarrage rapide

1. **Installez** Eskali Board sur le PC avec une seule commande ([Ubuntu](#install-ubuntu) ou [Windows](#install-windows)).
2. **Ouvrez-le** : un code QR apparaît.
3. **Scannez** le code QR avec le téléphone (même Wi-Fi), cliquez dans une fenêtre du PC, et tapez.

C'est tout : pas de compte, pas de code d'appairage à taper, rien à installer sur le téléphone.

<a id="prerequis"></a>
## Prérequis

| Où | Ce qu'il faut |
|---|---|
| PC Ubuntu | Ubuntu 24.04+ avec GNOME sous Wayland, et les paquets `python3-venv python3-gi gir1.2-gtk-4.0` (l'installateur les vérifie et affiche la commande `apt` s'il en manque un) |
| PC Windows | Windows 10 ou 11 et PowerShell (intégré). Python 3 est installé pour vous avec `winget` s'il manque |
| Téléphone | N'importe quel téléphone avec un navigateur récent (Android ou iPhone), sur le même Wi-Fi que le PC |
| Application Android (facultative) | Android 7.0 ou plus récent |
| Réseau | Internet seulement pour télécharger et installer. Ensuite, tout reste sur votre réseau local |

<a id="faq"></a>
## FAQ

**Faut-il Internet ?** Seulement pour installer ou mettre à jour. La saisie marche sur le seul réseau local.

**Quelque chose passe-t-il par un serveur ?** Non. Le téléphone parle directement au PC, et chaque message est chiffré avec une clé que seul le code QR transporte.

**Puis-je utiliser un iPhone ?** Oui, dans le navigateur : scannez le QR avec l'appareil photo. L'application existe seulement pour Android.

**Deux téléphones peuvent-ils taper en même temps ?** Non, un seul à la fois. Un deuxième téléphone prend la main sur le premier.

**Ça marche sur macOS ou sur Linux sans GNOME ?** Pas encore. Voir les [Limites](#limites).

<a id="installation"></a>
## Installation

<a id="install-ubuntu"></a>
### Ubuntu

```bash
curl -fsSL https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash
```

Cette commande installe Eskali Board dans `~/EskaBoard` et l'ajoute au menu des applications. Elle n'utilise jamais `sudo` : s'il manque des paquets système, elle affiche la commande `apt` à lancer d'abord. Au premier démarrage, GNOME demande l'autorisation Bureau à distance : cliquez sur **Partager**.

**Mise à jour :** relancez la même commande.

**Désinstallation :**

```bash
curl -fsSL https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash -s -- --uninstall
```

Cela supprime `~/EskaBoard` (avec son venv), l'entrée du menu et `~/.config/phonekb` (l'autorisation Bureau à distance enregistrée).

<a id="install-windows"></a>
### Windows

Ouvrez **PowerShell** (menu Démarrer, tapez `PowerShell`) et lancez :

```powershell
irm https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.ps1 | iex
```

Cette commande installe Eskali Board dans `%LOCALAPPDATA%\EskaBoard`, installe Python avec `winget` s'il manque, ajoute Eskali Board au menu Démarrer et au bureau, puis le lance. Sa page s'ouvre dans le navigateur avec le code QR. Aucun droit administrateur n'est nécessaire.

La première fois, le Pare-feu Windows demande si Python peut utiliser le réseau : cochez **Réseaux privés** et cliquez sur **Autoriser**. Si votre Wi-Fi est en mode **Public**, l'installateur vous le signale ; voir le [Dépannage](#depannage-windows).

**Mise à jour :** relancez la même commande.

**Désinstallation :**

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.ps1))) -Uninstall
```

Cela supprime `%LOCALAPPDATA%\EskaBoard` (avec son venv), les raccourcis du menu Démarrer et du bureau, et `%APPDATA%\EskaBoard` (fichier journal), puis liste ce qui a été supprimé. Python et les règles de pare-feu créées par Windows pour Python restent.

<a id="depuis-un-dossier"></a>
### Depuis un dossier

Sans la commande en une ligne (par exemple depuis un ZIP du projet) :

```bash
# Ubuntu
./install.sh              # crée venv/ s'il manque, ajoute Eskali Board au menu des applications
./install.sh --uninstall  # supprime l'entrée du menu et l'icône (garde le dossier et le venv)
```

```powershell
# Windows : extrayez le ZIP, ouvrez PowerShell dans le dossier extrait
powershell -ExecutionPolicy Bypass -File .\install.ps1              # installer et lancer
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall   # supprimer raccourcis, réglages et dossier
```

Les raccourcis pointent vers l'emplacement du dossier. Après l'avoir déplacé ou renommé, relancez le script d'installation.

<a id="utilisation"></a>
## Utilisation

1. Ouvrez Eskali Board depuis le menu des applications (Ubuntu) ou le menu Démarrer (Windows).
2. Scannez le code QR avec l'appareil photo du téléphone (ou avec l'[application Android](#android)).
3. Cliquez dans la fenêtre du PC où le texte doit aller, et tapez sur le téléphone.

### Sur le PC

Ubuntu affiche une fenêtre ; Windows affiche une page dans le navigateur. Les deux montrent le code QR, l'état de la connexion et trois boutons :

| Bouton | Rôle |
|---|---|
| **QR جديد** (nouveau QR) | Crée un nouveau lien ; le téléphone qui utilise l'ancien est déconnecté |
| **نسخ الرابط** (copier le lien) | Copie le lien du QR, pour l'[application Android](#android) |
| **إيقاف** (arrêter) | Arrête Eskali Board |

Sous Windows, vous pouvez fermer la page : Eskali Board continue de tourner. Rouvrez-le depuis le menu Démarrer pour revoir la page.

### Sur le téléphone

**Barre du haut**

| Commande | Rôle |
|---|---|
| **Envoyer** | Tapez d'abord, puis envoyez tout d'un coup (activez **Entrée après envoi** pour appuyer sur Entrée ensuite) |
| **Direct** | Le texte apparaît sur le PC pendant que vous tapez ou dictez |
| **🌐** | Langue de la page : العربية, English ou Français. Elle suit la langue du téléphone tant que vous n'en choisissez pas |
| **↺** (nouveau) | Vide la zone sans rien effacer sur le PC |
| **🕘** (historique) | Les textes qui ont quitté la zone, du plus récent au plus ancien : restaurer, renvoyer, supprimer ou tout effacer |

**Touches rapides**

| Touche | Rôle |
|---|---|
| **Entrée** / **Échap** | Entrée et Échap sur le PC |
| **Effacer** | Efface du PC ce que le téléphone a tapé depuis la dernière touche rapide, et vide la zone. Seul le texte du téléphone est effacé, jamais le reste du document |
| **Copier** / **Coller** | Copier (Ctrl+C) et coller (Ctrl+V) sur le PC |
| **Fichiers** | Envoie des photos ou des fichiers au PC, dans `Téléchargements/EskaBoard` |
| **📷 1**, **📷 2**… | Capture de chaque écran du PC, de gauche à droite. Enregistrée dans `Images/Captures d'écran` et copiée dans le presse-papiers du PC, prête pour Ctrl+V ou **Coller** |

Appuyer sur Entrée (la touche Entrée de la page, ou celle du clavier du téléphone avec le curseur à la fin) vide la zone une fois le texte arrivé sur le PC, pour que le message suivant reparte de zéro. Le texte est gardé dans l'historique.

### Astuce : traduction en direct

Avec Gboard, vous pouvez écrire dans une langue et faire arriver le texte sur le PC dans une autre, sans rien installer de plus :

1. Sur la page Eskali Board, touchez la zone de texte pour ouvrir Gboard.
2. Dans la barre d'outils de Gboard, touchez **Traduire** (ouvrez le menu **⋯** s'il n'apparaît pas).
3. Choisissez les deux langues, par exemple **Arabe → Français**.
4. Tapez dans la zone de traduction de Gboard : le texte traduit va dans la page puis sur le PC, dans les deux modes.

La traduction est faite par Gboard sur le téléphone ; elle dépend donc des langues que Gboard prend en charge.

<a id="android"></a>
## Application Android

L'application Eskali Board ouvre la même page en plein écran, sans la barre d'adresse du navigateur, et ajoute des boutons flottants. Elle est facultative : l'appareil photo et le navigateur du téléphone font le même travail.

**Installation :** téléchargez `EskaBoard.apk` depuis la page [Releases](https://github.com/Mohamedeskali/EskaBoard/releases) sur le téléphone et ouvrez-le. La première fois, Android demande d'autoriser l'installation d'applications depuis le navigateur (ou le gestionnaire de fichiers). Android 7.0 ou plus récent est requis.

Ouvrez l'application, puis :
- **Scannez le code QR** avec le lecteur intégré (il demande une fois l'accès à l'appareil photo), ou
- **Collez le lien** : cliquez sur **نسخ الرابط** sur le PC, faites passer le lien au téléphone (par exemple dans une discussion avec vous-même) et collez-le dans l'application. Vous pouvez aussi **Partager** le lien depuis une messagerie vers Eskali Board.

L'application retient le dernier PC : **Reconnecter** le rouvre tant qu'Eskali Board tourne dessus. Si Eskali Board a été redémarré, si **QR جديد** a été pressé ou si aucun téléphone n'a été connecté pendant 30 minutes, l'application indique que le code a expiré : scannez le nouveau.

Taper seulement une adresse IP ne suffit pas : le jeton et la clé changent à chaque démarrage d'Eskali Board, et le PC refuse le téléphone sans eux.

<!-- CAPTURE : l'écran d'accueil et les réglages de l'application, par ex. docs/screenshots/android-app.png -->

### Réglages

L'engrenage (sur l'écran d'accueil et en haut de la page) ouvre les réglages :
- **Langue** : automatique (celle du téléphone), العربية, Français ou English. L'application et la page changent aussitôt.
- **Boutons de la page** : afficher ou masquer chaque bouton de la barre d'outils.
- **Boutons flottants** (désactivés par défaut) : voir ci-dessous.

### Boutons flottants

Des boutons ronds qui flottent par-dessus toutes les applications ; déplacez-les où vous voulez. Activez-les dans les Réglages ou depuis la barre du haut de la page. Android demande l'autorisation de **s'afficher par-dessus les autres applications** (et, pour les captures, de **capturer l'écran** : choisissez l'écran entier, pas une seule application). Une notification reste affichée tant qu'un bouton est visible ; désactivez-le dans les Réglages ou avec **Arrêter** dans la notification.

- **Entrée** : appuie sur Entrée sur le PC depuis n'importe quelle application, via la connexion chiffrée de la page.
- **Capture** : capture l'écran du téléphone (sans le bouton) et la copie dans le **presse-papiers du téléphone**. Si la page est connectée, la capture part aussi sur le **PC** : dans son presse-papiers (Ctrl+V) et dans `Images/Captures d'écran` (`Screenshot … phone.png`). Android peut arrêter la capture de lui-même (par exemple avec son bouton « arrêter le partage ») ; réactivez-la dans les Réglages.

<a id="securite"></a>
## Sécurité et vie privée

- **Local uniquement.** Le téléphone et le PC communiquent directement sur votre réseau. Aucun serveur, compte, statistique ni service cloud.
- **Chiffré de bout en bout.** Chaque lancement crée un jeton aléatoire (`?t=`) et une clé de 32 octets (`#k=`) dans le lien du QR. La clé est dans le fragment de l'URL, elle ne passe donc jamais sur le réseau. Chaque message WebSocket est chiffré avec NaCl secretbox, avec un identifiant de session et un compteur : texte en clair, mauvaise clé et messages rejoués sont refusés.
- **Protection contre la force brute.** 5 jetons erronés depuis une IP la bloquent pendant 60 s.
- **Les liens expirent.** Après 30 minutes sans téléphone connecté (`--expire`), avec **QR جديد**, et à chaque redémarrage.
- **Les images reçues sont réencodées.** Le PC n'accepte que des captures PNG (jusqu'à 16 Mo et 40 mégapixels), les décode et les réencode avant de les enregistrer.
- **Les fichiers sont écrits prudemment.** Chaque fichier va dans un fichier caché `.part` et ne reçoit son nom qu'une fois tous les octets arrivés (jusqu'à 500 Mo par fichier).

> [!WARNING]
> Le lien (et `qr.png` en mode terminal) contient le jeton d'appairage et la clé de chiffrement : toute personne qui l'a et qui est sur le même Wi-Fi peut taper sur votre PC jusqu'à ce que vous pressiez **QR جديد** ou redémarriez Eskali Board. Ne le publiez nulle part. L'historique du presse-papiers de Windows (Win+V) garde ce que vous copiez.

<a id="fonctionnement"></a>
## Fonctionnement

```
 Téléphone (navigateur ou appli)              PC (Python, aiohttp)
┌─────────────────────┐   WebSocket       ┌──────────────────────────────┐
│ page du téléphone   │   chiffré         │ server.py  jeton / IP        │
│ Gboard, voix, touches│ ──────────────►  │ worker de saisie             │
│ tweetnacl (local)   │   même Wi-Fi      │  ├─ Ubuntu : portail GNOME   │
└─────────────────────┘                   │  └─ Windows : SendInput      │
                                          └──────────────────────────────┘
```

- **Ubuntu :** la saisie passe par le portail Bureau à distance de GNOME. Le texte est mis dans le presse-papiers via le portail puis collé avec Ctrl+V ; le programme attend que l'application l'ait lu, et remet ce que vous aviez copié (texte ou image) 1 s après la fin de la saisie. Les touches spéciales sont envoyées comme des frappes. Le jeton d'autorisation est stocké dans `~/.config/phonekb/restore_token`, la fenêtre d'autorisation n'apparaît donc qu'une fois.
- **Windows :** le texte est tapé en caractères Unicode avec `SendInput`, donc l'arabe marche quelle que soit la disposition de clavier, et le presse-papiers n'est pas utilisé (sauf pour les captures). La page du code QR est servie uniquement sur `127.0.0.1`, sur un port aléatoire, derrière un secret aléatoire présent dans l'adresse ouverte par le navigateur ; elle est inaccessible depuis le réseau.
- **Rester connecté :** quand le téléphone revient d'une autre application ou de l'écran de verrouillage, la page vérifie sa connexion (un ping chiffré) et se reconnecte seule avec le même lien. Chaque connexion reçoit un nouvel identifiant de session du PC et son compteur repart de zéro, donc rien de ce qui a été envoyé sur une connexion précédente n'est accepté. Le PC envoie aussi un ping au téléphone toutes les 20 s et déconnecte celui qui ne répond plus.

<a id="limites"></a>
## Limites

- Gardez la fenêtre cible active pendant la saisie.
- Un seul téléphone à la fois. Une page remplacée par un autre téléphone (ou un autre onglet) reprend la main quand elle est réaffichée, ou quand on touche son avis.
- Ubuntu : GNOME sous Wayland uniquement. Les terminaux collent avec Ctrl+Maj+V, donc la saisie dans un terminal peut ne pas marcher, et dans un terminal **Copier** (Ctrl+C) arrête la commande en cours au lieu de copier. Seuls le texte et les images PNG du presse-papiers sont restaurés après la saisie. Les captures passent par le portail Capture d'écran de GNOME, qui peut demander une autorisation la première fois.
- Windows : rien ne peut être tapé dans les programmes lancés en administrateur (Windows le bloque), ni sur l'écran de verrouillage et les invites UAC. Quelques programmes qui lisent les touches brutes (certains jeux, outils de bureau à distance) ignorent la saisie Unicode.

<a id="depannage"></a>
## Dépannage

### Ubuntu

- **Pas de fenêtre d'autorisation :** elle est peut-être derrière d'autres fenêtres (Alt+Tab), et elle abandonne après 5 minutes.
- **Révoquer l'autorisation :** supprimez `~/.config/phonekb` (les Paramètres GNOME n'ont pas de page pour cela). La désinstallation le fait pour vous.
- **Le texte n'apparaît pas :** vérifiez que la fenêtre cible est active, et regardez la sortie du terminal.
- **Le téléphone dit que le QR a expiré :** Eskali Board a été redémarré, **QR جديد** a été pressé, ou aucun téléphone n'a été connecté pendant 30 minutes. Scannez le nouveau QR.

<a id="depannage-windows"></a>
### Windows

- **Demande du pare-feu.** La première fois, Windows demande si « Python » peut utiliser le réseau. Cochez **Réseaux privés** et cliquez sur **Autoriser l'accès** (un compte standard demande un mot de passe administrateur). Si vous avez cliqué sur **Annuler**, le téléphone ne peut pas se connecter : Démarrer, tapez `Autoriser une application via le Pare-feu Windows`, **Modifier les paramètres**, cochez **Privé** pour chaque entrée **Python**, **OK**. L'installateur vous prévient s'il trouve une telle règle bloquante. Eskali Board ne modifie jamais le pare-feu lui-même.
- **Un réseau « Public » bloque le téléphone.** Windows bloque les connexions entrantes sur les réseaux publics, même après avoir autorisé Python. Si c'est le Wi-Fi de votre maison ou de votre bureau, passez-le en Privé : **Paramètres > Réseau et Internet > Wi-Fi** (ou **Ethernet**) > votre réseau > **Type de profil réseau : Privé**. Faites-le seulement pour les réseaux de confiance. L'installateur vous prévient quand le réseau est Public.
- **Même Wi-Fi.** Le téléphone doit être sur le même Wi-Fi que le PC, pas en données mobiles ni sur un réseau invité (ceux-ci isolent souvent les appareils). L'adresse sous le code QR (par exemple `192.168.1.20:8765`) doit commencer comme l'adresse Wi-Fi du téléphone. Un VPN sur le PC peut faire choisir la mauvaise adresse : coupez-le, ou lancez Eskali Board avec `--host` et l'adresse Wi-Fi du PC.
- **« L'exécution de scripts est désactivée sur ce système ».** La commande `irm ... | iex` n'est pas concernée. Pour `install.ps1` depuis un ZIP, lancez-le comme indiqué dans [Depuis un dossier](#depuis-un-dossier) avec `-ExecutionPolicy Bypass` : cela l'autorise pour cette exécution seulement, sans changer aucun réglage.
- **SmartScreen / « ce fichier provient d'Internet ».** Eskali Board n'a pas de `.exe`. Si le navigateur avertit à propos du ZIP, choisissez **Conserver**. Si Windows bloque les scripts extraits, clic droit sur le ZIP, **Propriétés**, cochez **Débloquer**, puis extrayez-le à nouveau (ou lancez `Unblock-File .\install.ps1`).
- **La page a été fermée.** Eskali Board tourne toujours : ouvrez-le depuis le menu Démarrer pour revoir la page.
- **Le texte n'apparaît pas.** Vérifiez que la fenêtre cible est active et ne tourne pas en administrateur. Le journal est dans `%APPDATA%\EskaBoard\eskaboard.log`.
- **« Port 8765 is in use ».** Un autre Eskali Board, ou un autre programme, utilise le port. Arrêtez-le, ou lancez Eskali Board avec `--port 8766`.

<a id="developpement"></a>
## Développement

### Lancer depuis un terminal

```bash
venv/bin/python3 -m phonekb          # Ubuntu : code QR dans le terminal (enregistré aussi dans qr.png)
venv/bin/python3 -m phonekb --gui    # Ubuntu : la fenêtre
venv\Scripts\python -m phonekb       # Windows : code QR dans le terminal
venv\Scripts\python -m phonekb --gui # Windows : la page dans le navigateur
```

| Option | Signification |
|---|---|
| `--host IP` | Adresse du PC mise dans le QR (par défaut : l'IP du réseau local, détectée) |
| `--port N` | Port (8765 par défaut) |
| `--dry-run` | Journalise les messages sans jamais taper (pas besoin du portail) |
| `--expire MIN` | Le lien expire après MIN minutes sans téléphone connecté (30 par défaut, 0 : jamais) |
| `--gui` | La fenêtre (Ubuntu) ou la page dans le navigateur (Windows) |
| `--version` | Affiche la version |

### Tests

```bash
venv/bin/python3 -m unittest discover -s tests      # PC : reconnexion, rejeu, expiration, mode direct, fichiers, images
cd android && ./gradlew testDebugUnitTest            # tests unitaires Android
```

### Compiler l'application Android

GitHub Actions compile l'APK (`.github/workflows/android.yml`) à chaque modification de `android/` et à chaque release publiée, à laquelle il joint `EskaBoard.apk`. L'APK reste aussi téléchargeable sur l'exécution du workflow. Pour le compiler sur un PC, avec JDK 17 et le SDK Android : `cd android && ./gradlew assembleDebug`.

Android n'installe une mise à jour que si elle est signée avec la même clé que l'application installée. Sans clé, chaque build CI est signé avec une clé jetable, et l'ancienne application doit d'abord être désinstallée. Pour signer tous les builds avec la même clé, créez-en une une seule fois (`keytool` est fourni avec Java) :

```bash
keytool -genkeypair -keystore eskaboard.jks -alias eskaboard -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=EskaBoard"
base64 -w0 eskaboard.jks   # Windows PowerShell: [Convert]::ToBase64String([IO.File]::ReadAllBytes("eskaboard.jks"))
```

Ensuite, dans **Settings > Secrets and variables > Actions** du dépôt, ajoutez `ANDROID_KEYSTORE_BASE64` (le texte base64), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` (`eskaboard`) et `ANDROID_KEY_PASSWORD` (le même mot de passe). Gardez `eskaboard.jks` et son mot de passe en lieu sûr : sans eux, aucune mise à jour ne peut s'installer par-dessus l'application.

### Structure du projet

```
get.sh / get.ps1     installation, mise à jour et désinstallation en une ligne (Ubuntu / Windows)
install.sh           Ubuntu : vérifie les paquets, crée le venv, ajoute l'entrée du menu
install.ps1          Windows : trouve ou installe Python, crée le venv, ajoute les raccourcis
assets/              icône de l'application (eskaboard.svg, eskaboard.png, eskaboard.ico)
phonekb/
  __main__.py        ligne de commande : options, QR dans le terminal
  app.py             Service : lance le serveur web et le worker de saisie (CLI et GUI)
  gui.py             Ubuntu : fenêtre GTK 4
  webgui.py          Windows : la page dans le navigateur (127.0.0.1 uniquement)
  server.py          serveur web, WebSocket chiffré, contrôles jeton/IP, worker de saisie
  secure.py          fonctions NaCl secretbox (clé, chiffrement, déchiffrement)
  files.py           fichiers et photos du téléphone, enregistrés dans Downloads/EskaBoard
  injector.py        Ubuntu : portail Bureau à distance GNOME : autorisation, touches, collage
  injector_win.py    Windows : SendInput (caractères Unicode et touches virtuelles), captures
  gnome_shot.py      Ubuntu : disposition des écrans (Mutter) et portail Capture d'écran
  screenshot.py      découpe d'un écran, enregistrement PNG
  netinfo.py         trouve l'IP locale du PC
  static/
    index.html       la page du téléphone
    status.html      la page Windows
    nacl-fast.min.js tweetnacl 1.0.3 (servi localement, sans CDN)
tests/               suites unittest côté PC
android/             l'application Android (Kotlin) : lecteur QR, champ de lien, la page dans une WebView
  app/src/main/java/org/eskaboard/app/
    MainActivity.kt      écran d'accueil : scanner, coller ou partager un lien, se reconnecter
    BoardActivity.kt     la page en plein écran ; reste sur l'adresse du PC
    BoardLink.kt         vérifie qu'un lien est bien un lien Eskali Board (http://IP:PORT/?t=…#k=…)
    SettingsActivity.kt, AppSettings.kt  langue, boutons de la page, boutons flottants
    ShotService.kt       le bouton flottant de capture (service de premier plan, capture d'écran)
    EnterService.kt      le bouton flottant Entrée
    PageStore.kt         garde l'historique des textes dans l'application
```

### Branches

- `main` : la version stable (celle que téléchargent les commandes d'installation).
- `recette` : développement et tests. Les nouveaux travaux partent de `recette` et les pull requests la ciblent ; elle est fusionnée dans `main` une fois testée.

<a id="licence"></a>
## Licence

MIT, voir [LICENSE](LICENSE). © 2026 Mohamed Eskali.

`phonekb/static/nacl-fast.min.js` est [TweetNaCl.js](https://github.com/dchest/tweetnacl-js) 1.0.3 par les contributeurs de TweetNaCl.js, placé dans le domaine public (The Unlicense).
