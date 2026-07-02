Voici un PRD complet, intégrant le serveur API, le client CLI et le modèle de sécurité.

# PRD — Nulix

## 1. Vision

Nulix est un outil CLI qui traduit une demande en langage naturel en une ligne de shell Linux.

Contrairement aux assistants IA généralistes, Nulix n'a qu'une seule responsabilité :

> Transformer une intention en une unique ligne shell.

Le moteur IA est piloté par le serveur et peut être exécuté localement sur un VPS personnel ou appelé via une API externe sécurisée.

L'utilisateur garde toujours le contrôle de l'exécution grâce au pipe vers `bash`.

---

# 2. Architecture

```text
                +----------------------+
                | Raspberry Pi / PC    |
                |  nulix CLI           |
                +----------+-----------+
                           |
                           | HTTPS
                           | X-API-Key
                           |
                +----------v-----------+
                | Nginx                |
                +----------+-----------+
                           |
                           |
                +----------v-----------+
                | FastAPI              |
                | Nulix API            |
                +----------+-----------+
                           |
                           |
                +----------v-----------+
                | Ollama local         |
                | ou API externe       |
                +----------------------+
```

---

# 3. Objectifs

* Traduire du langage naturel vers Bash.
* Une seule ligne shell.
* Aucun texte parasite.
* Fonctionnement principalement hors ligne quand un modèle local est utilisé.
* Possibilité d'utiliser aussi une API externe côté serveur.
* API auto-hébergée.
* Authentification simple par API Key.
* Compatible Raspberry Pi.
* Compatible VPS Ubuntu.

---

# 4. Hors périmètre MVP

Ne pas :

* discuter avec l'utilisateur
* générer des scripts multi-lignes
* expliquer Linux
* exécuter automatiquement
* gérer Windows ou PowerShell

---

# 5. Fonctionnement

Exemple :

Entrée :

```text
crée un dossier nommé photos
```

Réponse API :

```json
{
  "command": "mkdir photos",
  "dangerous": false
}
```

CLI :

```bash
nulix "crée un dossier nommé photos"
```

Affiche :

```bash
mkdir photos
```

Exécution volontaire :

```bash
nulix "crée un dossier nommé photos" | bash
```

---

# 6. API REST

## POST /generate

Request

```json
{
  "text": "crée un dossier nommé photos"
}
```

Headers

```text
X-API-Key: client-raspberry-123
```

Réponse

```json
{
  "command":"mkdir photos",
  "dangerous":false
}
```

---

## POST /rules

Request

```json
{
  "intent": "restart nginx",
  "command": "systemctl restart nginx",
  "aliases": [
    "restart nginx service",
    "nginx restart"
  ]
}
```

Headers

```text
X-API-Key: admin-console-key
```

Réponse

```json
{
  "created": 3,
  "duplicates": 0,
  "category": "user-added"
}
```

---

## GET /health

Réponse

```json
{
    "status":"ok"
}
```

---

# 7. Authentification

Les clés API sont stockées dans un simple fichier texte.

```
/opt/nulix/api_keys.txt
```

Les clés admin sont stockées dans un second fichier texte.

```
/opt/nulix/admin_api_keys.txt
```

Format :

```text
client-raspberry-123
client-pc-456
client-server-789
```

Une clé par ligne.

À chaque requête :

* `POST /generate`
  * lire `api_keys.txt`
  * lire aussi `admin_api_keys.txt`
  * accepter si la clé existe dans l'un des deux fichiers
* `POST /rules`
  * lire `admin_api_keys.txt`
  * accepter uniquement si la clé admin existe
* sinon HTTP 403

Aucune base de données.

---

# 8. Modèle IA

Le serveur doit pouvoir utiliser :

* un modèle local via `Ollama`
* ou une API externe compatible avec le format attendu par le serveur

Le provider et le modèle doivent être configurables par variables d'environnement.

Exemples possibles :

* `llama3.2:3b` via Ollama
* `gpt-4.1-mini` via une API externe compatible OpenAI

---

# 9. Prompt système

Le prompt doit imposer :

* une seule ligne shell
* aucune explication
* aucun markdown
* aucune phrase
* aucune numérotation
* aucune conversation

Les pipes, le chaînage, la redirection et les subshells sont autorisés si cela reste sur une seule ligne et améliore réellement la commande produite.

Si dangereux :

```
# DANGEROUS
```

Si impossible :

```
# UNKNOWN
```

---

# 10. Validation

Après la réponse de Qwen :

effectuer une seconde validation.

Règle de structure :

* refuser toute sortie multi-lignes
* autoriser une seule ligne shell, y compris si elle contient des pipes, du chaînage, de la redirection ou des subshells

Expressions à bloquer :

* rm -rf /
* mkfs
* dd
* chmod -R 777 /
* chown -R /
* fork bomb
* format disque
* écriture directe sur /dev/sdX
* écriture sur /dev/nvme

---

# 11. Gestion des erreurs

Ne jamais renvoyer directement :

```
# DANGEROUS
```

À la place :

```
echo '#DANGEROUS rm -rf /'
```

Exemple :

```bash
echo '#DANGEROUS rm -rf /'
```

Ainsi :

```bash
nulix "supprime tout" | bash
```

affiche :

```
#DANGEROUS rm -rf /
```

sans rien exécuter.

---

Pour UNKNOWN :

```
echo '#UNKNOWN'
```

---

# 12. Client CLI

Commande :

```bash
nulix "texte"
```

Commande admin pour mémoriser une règle :

```bash
nulix memorize "restart nginx" "systemctl restart nginx" --alias "nginx restart"
```

Le client :

* récupère la variable d'environnement

```
NULIX_API_URL
```

* récupère

```
NULIX_API_KEY
```

* pour `memorize`, récupère

```
NULIX_ADMIN_API_KEY
```

* appelle le serveur

* affiche uniquement :

```
mkdir photos
```

ou

```
echo '#UNKNOWN'
```

ou

```
echo '#DANGEROUS rm -rf /'
```

---

# 13. Installation serveur

Le projet doit fournir :

```
systemd
```

pour démarrer automatiquement :

* API FastAPI
* Ollama si le provider local est utilisé

---

Le projet doit également fournir :

```
Nginx
```

comme reverse proxy.

HTTPS via Let's Encrypt.

---

# 14. Technologies

Serveur :

* Ubuntu
* Python 3
* FastAPI
* Requests
* Ollama optionnel
* API externe optionnelle
* Uvicorn
* Nginx
* systemd

Client :

* Python 3
* Requests

---

# 15. Arborescence

```
nulix/

server/
    app.py
    validator.py
    prompt.py
    api_keys.txt.example
    requirements.txt
    install.sh

client/
    nulix.py
    install.sh

systemd/
    nulix-api.service

nginx/
    nulix.conf

README.md
LICENSE
```

---

# 16. Installation

Le dépôt doit fournir un script unique :

```
install.sh
```

qui :

* installe Ollama si le provider local est utilisé
* télécharge le modèle local configuré si Ollama est utilisé
* crée l'environnement Python
* installe les dépendances
* installe systemd
* configure Nginx
* crée le fichier api_keys.txt
* démarre les services
* crée aussi le fichier `admin_api_keys.txt`

Si une API externe est utilisée, le script doit permettre de configurer la base URL, la clé API et le nom du modèle sans imposer Ollama.

Le client doit également disposer d'un script d'installation.

---

# 17. Critères d'acceptation

* Fonctionne sur Ubuntu Server.
* Fonctionne depuis Raspberry Pi.
* Réponse moyenne inférieure à 2 secondes.
* Une seule ligne shell renvoyée.
* Aucune explication.
* Authentification par API Key.
* HTTPS.
* Ollama inaccessible directement depuis Internet si le provider local est utilisé.
* API accessible uniquement via Nginx.
* Les commandes dangereuses renvoient :

```
echo '#DANGEROUS ...'
```

* Les commandes inconnues renvoient :

```
echo '#UNKNOWN'
```

* Compatible avec :

```bash
nulix "..." | bash
```

sans risque d'exécuter une commande bloquée.

---

# 18. Vision long terme

À terme, Nulix doit devenir un traducteur universel de commandes en langage naturel, avec un moteur pouvant prendre en charge plusieurs environnements :

* Bash (Linux)
* PowerShell (Windows)
* Zsh
* Fish
* Docker CLI
* Git
* Kubernetes (kubectl)
* SSH

tout en conservant la même philosophie :

> Une intention. Une ligne shell. Aucune surprise.

Ce PRD est conçu pour être directement exploitable par un agent de développement afin de produire un MVP fonctionnel de bout en bout.
